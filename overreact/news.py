"""Collect news from free RSS/Atom feeds into SQLite, deduplicated by link.

Usage: python -m overreact.news            (one pass)
       python -m overreact.news --loop 900 (every 15 min, forever)

SEC asks for a User-Agent with a contact: set SEC_USER_AGENT="name email" or EDGAR is skipped.
"""
import argparse
import os
import time
from datetime import datetime, timezone

import feedparser
import requests

from overreact.db import connect
from overreact.prices import load_tickers

FEEDS = {
    "prnewswire": "https://www.prnewswire.com/rss/news-releases-list.rss",
    "reddit_pennystocks": "https://www.reddit.com/r/pennystocks/new/.rss",
    "reddit_smallstreetbets": "https://www.reddit.com/r/smallstreetbets/new/.rss",
}
EDGAR_8K = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&count=100&output=atom"
YAHOO_TICKER = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={}&region=US&lang=en-US"
DEFAULT_UA = "overreact-research/0.1"


def all_feeds() -> dict[str, tuple[str, str]]:
    """source name -> (url, user agent)."""
    feeds = {name: (url, DEFAULT_UA) for name, url in FEEDS.items()}
    feeds |= {f"yahoo_{t}": (YAHOO_TICKER.format(t), DEFAULT_UA) for t in load_tickers()}
    sec_ua = os.environ.get("SEC_USER_AGENT")
    if sec_ua:
        feeds["edgar_8k"] = (EDGAR_8K, sec_ua)
    return feeds


def to_rows(source: str, entries: list, fetched: str) -> list[tuple]:
    return [
        (e.link, source, e.get("title", "").strip(), e.get("summary", ""),
         e.get("published") or e.get("updated"), fetched)
        for e in entries
        if e.get("link") and e.get("title")
    ]


def collect_once() -> int:
    conn = connect()
    added = 0
    for source, (url, ua) in all_feeds().items():
        try:
            resp = requests.get(url, headers={"User-Agent": ua}, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as err:
            print(f"{source}: {err}")
            continue
        fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
        rows = to_rows(source, feedparser.parse(resp.content).entries, fetched)
        before = conn.total_changes
        conn.executemany("INSERT OR IGNORE INTO news VALUES (?,?,?,?,?,?)", rows)
        conn.commit()
        added += conn.total_changes - before
        time.sleep(2)  # be polite; Reddit returns 429 on back-to-back requests
    conn.close()
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M}: +{added} new items")
    return added


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="seconds between passes; 0 = run once")
    interval = ap.parse_args().loop
    collect_once()
    while interval:
        time.sleep(interval)
        try:
            collect_once()
        except Exception as err:  # keep the 24/7 loop alive (e.g. locked DB); next pass retries
            print(f"pass failed: {err}")
