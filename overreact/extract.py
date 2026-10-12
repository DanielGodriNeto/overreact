"""Turn news text into numbers with a local LLM (Ollama). The LLM never decides trades.

Usage: python -m overreact.extract [--limit 200]   (news not yet extracted)
       python -m overreact.extract --filings      (SEC 8-K texts not yet extracted)
Model: OLLAMA_MODEL in .env (default qwen3:1.7b).
"""
import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone

import requests

from overreact.db import connect
from overreact.env import load_env

OLLAMA_URL = "http://localhost:11434/api/generate"
CATEGORIES = {"offering", "earnings", "regulatory", "contract", "management", "listing", "other"}
PROMPT = (
    'You are a financial news classifier. Text: "{text}". Return JSON: {{"ticker": str or "" if none, '
    '"direction": -1|0|1 (expected short-term stock impact), "confidence": 0-1, '
    '"category": "offering|earnings|regulatory|contract|management|listing|other"}}'
)
SCHEMA = """
CREATE TABLE IF NOT EXISTS extractions (
    link       TEXT PRIMARY KEY REFERENCES news(link),
    ticker     TEXT,
    direction  INTEGER NOT NULL,
    confidence REAL NOT NULL,
    category   TEXT NOT NULL,
    model      TEXT NOT NULL,
    extracted  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS filing_extractions (
    accession  TEXT PRIMARY KEY REFERENCES filings(accession),
    direction  INTEGER NOT NULL,
    confidence REAL NOT NULL,
    category   TEXT NOT NULL,
    model      TEXT NOT NULL,
    extracted  TEXT NOT NULL
);
"""


def validate(raw: dict, known: set[str], hint: str | None = None) -> tuple[str | None, int, float, str]:
    """Clamp/clean LLM output; unknown tickers fall back to the feed's ticker (hint) or None."""
    ticker = str(raw.get("ticker") or "").upper().strip().lstrip("$")
    ticker = ticker if ticker in known else hint
    try:
        direction = max(-1, min(1, int(raw.get("direction", 0))))
        confidence = max(0.0, min(1.0, float(raw.get("confidence", 0))))
    except (TypeError, ValueError, OverflowError):
        direction, confidence = 0, 0.0
    category = raw.get("category")
    category = category if isinstance(category, str) and category in CATEGORIES else "other"
    return ticker, direction, confidence, category


def ask(model: str, text: str, max_chars: int = 1500) -> dict:
    resp = requests.post(OLLAMA_URL, timeout=300, json={
        "model": model, "prompt": PROMPT.format(text=text[:max_chars].replace('"', "'")), "format": "json",
        "stream": False, "think": False, "options": {"temperature": 0},
    })
    resp.raise_for_status()
    try:
        parsed = json.loads(resp.json()["response"])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


GAMES = ("RobloxPlayerBeta.exe",)
DUTY_NORMAL, DUTY_GAMING = 0.6, 0.25  # share of time the GPU works; the rest is pause


def gaming() -> bool:
    out = subprocess.run(["tasklist", "/NH"], capture_output=True, text=True).stdout
    return any(game in out for game in GAMES)


def throttle(busy_seconds: float, duty: float) -> None:
    """Sleep so that work / (work + pause) == duty."""
    time.sleep(busy_seconds * (1 - duty) / duty)


def model_name() -> str:
    load_env()
    return os.environ.get("OLLAMA_MODEL", "qwen3:1.7b")


def run_filings(limit: int | None = None, share_gpu: bool = False) -> int:
    """LLM over historical 8-K texts; the ticker is already known from the filing. Resumable."""
    model = model_name()
    conn = connect()
    conn.executescript(SCHEMA)
    pending = conn.execute(
        "SELECT t.accession, f.ticker, t.text FROM filing_texts t JOIN filings f USING (accession) "
        "WHERE t.accession NOT IN (SELECT accession FROM filing_extractions) ORDER BY f.filed LIMIT ?",
        (limit or -1,)).fetchall()
    for accession, ticker, text in pending:
        started = time.monotonic()
        _, direction, confidence, category = validate(ask(model, f"[{ticker}] {text}", 2500), {ticker}, ticker)
        if share_gpu:
            throttle(time.monotonic() - started, DUTY_GAMING if gaming() else DUTY_NORMAL)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn.execute("INSERT OR REPLACE INTO filing_extractions VALUES (?,?,?,?,?,?)",
                     (accession, direction, confidence, category, model, now))
        conn.commit()
    conn.close()
    print(f"extracted {len(pending)} filings with {model}")
    return len(pending)


def run(limit: int) -> None:
    model = model_name()
    conn = connect()
    conn.executescript(SCHEMA)
    known = {r[0] for r in conn.execute("SELECT DISTINCT ticker FROM prices")}
    pending = conn.execute(
        "SELECT link, source, title, summary FROM news WHERE link NOT IN (SELECT link FROM extractions) "
        "ORDER BY fetched DESC LIMIT ?", (limit,)).fetchall()
    for link, source, title, summary in pending:
        hint = source.removeprefix("yahoo_") if source.startswith("yahoo_") else None
        values = validate(ask(model, f"{title}. {summary or ''}"), known, hint)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn.execute("INSERT OR REPLACE INTO extractions VALUES (?,?,?,?,?,?,?)", (link, *values, model, now))
        conn.commit()
    print(f"extracted {len(pending)} items with {model}")
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--filings", action="store_true")
    ap.add_argument("--share-gpu", action="store_true", help="pause between items; pause more while a game runs")
    args = ap.parse_args()
    if args.filings:
        run_filings(share_gpu=args.share_gpu)
    else:
        run(args.limit)
