"""Historical SEC filings (point-in-time "hard news") for the ticker universe.

8-K = material event (item codes say which: 2.02 earnings, 1.01 deal, 3.02 share sale...),
10-Q/10-K = periodic reports, 424B* = share offerings (dilution).
Usage: python -m overreact.edgar          filing list (needs SEC_USER_AGENT in .env)
       python -m overreact.edgar --texts  download 8-K text + press-release exhibits (resumable)
"""
import argparse
import html
import os
import re
import time

import requests

from overreact.db import connect
from overreact.env import load_env
from overreact.prices import load_tickers

TICKER_MAP = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS = "https://data.sec.gov/submissions/{}"
FULL_TEXT = "https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{accession}.txt"
TEXT_CHARS = 2500
HARD_FORMS = ("8-K", "8-K/A", "10-Q", "10-K", "424B")
SCHEMA = """
CREATE TABLE IF NOT EXISTS filings (
    accession TEXT PRIMARY KEY,
    ticker    TEXT NOT NULL,
    form      TEXT NOT NULL,
    filed     TEXT NOT NULL,  -- filing date (YYYY-MM-DD)
    accepted  TEXT,           -- SEC acceptance time (Eastern, despite the trailing Z)
    items     TEXT
);
CREATE TABLE IF NOT EXISTS filing_texts (
    accession TEXT PRIMARY KEY REFERENCES filings(accession),
    text      TEXT NOT NULL
);
"""


def sec_get(session: requests.Session, url: str) -> dict:
    time.sleep(0.15)  # SEC limit is 10 requests/second
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def is_hard(form: str) -> bool:
    return form.startswith(HARD_FORMS)


def to_rows(ticker: str, block: dict) -> list[tuple]:
    """block: column-oriented dict from the submissions API ('recent' or an older file)."""
    return [
        (acc, ticker, form, filed, accepted, items)
        for acc, form, filed, accepted, items in zip(
            block["accessionNumber"], block["form"], block["filingDate"],
            block["acceptanceDateTime"], block["items"])
        if is_hard(form)
    ]


def sec_session() -> tuple[requests.Session, dict[str, int]]:
    """Session with the SEC-required User-Agent, plus the ticker -> CIK map."""
    load_env()
    ua = os.environ.get("SEC_USER_AGENT")
    if not ua:
        raise SystemExit("Set SEC_USER_AGENT in .env (SEC requires a contact)")
    session = requests.Session()
    session.headers["User-Agent"] = ua
    return session, {v["ticker"]: v["cik_str"] for v in sec_get(session, TICKER_MAP).values()}


def clean(raw: str) -> str:
    """Full submission .txt -> readable text of the 8-K body and its EX-99 press releases."""
    docs = re.findall(r"<DOCUMENT>\s*<TYPE>([^\s<]+)(.*?)</DOCUMENT>", raw, flags=re.S)
    keep = [body for kind, body in docs if kind.startswith(("8-K", "EX-99"))]
    text = re.sub(r"<[^>]+>", " ", " ".join(keep))
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    start = re.search(r"Item\s+\d\.\d\d", text)  # skip the cover page boilerplate
    return text[start.start() if start else 0:][:TEXT_CHARS]


def fetch_texts(limit: int | None = None) -> int:
    """Download text for 8-Ks since 2016 that we don't have yet. Safe to kill and rerun."""
    session, ciks = sec_session()
    conn = connect()
    conn.executescript(SCHEMA)
    pending = conn.execute(
        "SELECT accession, ticker FROM filings WHERE form LIKE '8-K%' AND filed >= '2016-01-01' "
        "AND accession NOT IN (SELECT accession FROM filing_texts) ORDER BY filed LIMIT ?",
        (limit or -1,)).fetchall()
    for accession, ticker in pending:
        url = FULL_TEXT.format(cik=ciks[ticker], folder=accession.replace("-", ""), accession=accession)
        try:
            time.sleep(0.15)
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as err:
            print(f"{accession}: {err}")
            continue
        conn.execute("INSERT OR REPLACE INTO filing_texts VALUES (?,?)", (accession, clean(resp.text)))
        conn.commit()
    conn.close()
    print(f"fetched {len(pending)} filing texts")
    return len(pending)


def update() -> None:
    session, ciks = sec_session()
    conn = connect()
    conn.executescript(SCHEMA)
    for ticker in load_tickers():
        if ticker not in ciks:
            print(f"{ticker}: no SEC CIK (ETF?), skipped")
            continue
        sub = sec_get(session, SUBMISSIONS.format(f"CIK{ciks[ticker]:010d}.json"))
        rows = to_rows(ticker, sub["filings"]["recent"])
        for older in sub["filings"]["files"]:
            rows += to_rows(ticker, sec_get(session, SUBMISSIONS.format(older["name"])))
        conn.executemany("INSERT OR REPLACE INTO filings VALUES (?,?,?,?,?,?)", rows)
        conn.commit()
        print(f"{ticker}: {len(rows)} hard filings")
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--texts", action="store_true")
    if ap.parse_args().texts:
        fetch_texts()
    else:
        update()
