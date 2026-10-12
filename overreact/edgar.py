"""Historical SEC filings (point-in-time "hard news") for the ticker universe.

8-K = material event (item codes say which: 2.02 earnings, 1.01 deal, 3.02 share sale...),
10-Q/10-K = periodic reports, 424B* = share offerings (dilution).
Usage: python -m overreact.edgar   (needs SEC_USER_AGENT in .env)
"""
import os
import time

import requests

from overreact.db import connect
from overreact.env import load_env
from overreact.prices import load_tickers

TICKER_MAP = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS = "https://data.sec.gov/submissions/{}"
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


def update() -> None:
    load_env()
    ua = os.environ.get("SEC_USER_AGENT")
    if not ua:
        raise SystemExit("Set SEC_USER_AGENT in .env (SEC requires a contact)")
    session = requests.Session()
    session.headers["User-Agent"] = ua
    ciks = {v["ticker"]: v["cik_str"] for v in sec_get(session, TICKER_MAP).values()}
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
    update()
