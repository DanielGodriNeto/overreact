"""Crypto news sources: pure parsers from a response body to Items. Fetching and timing live in newsear.py.

Timestamp precision (verified 2026-10-14): OKX pTime is real ms; Bybit publishTime is ms-typed but always ...000
(second precision); Upbit listed_at and RSS pubDate are seconds; exchange symbol diffs have no publication time.
"""
import calendar
import html
import io
import re
from datetime import datetime
from typing import NamedTuple

import feedparser

BODY_CAP = 20_000
TAG = re.compile(r"<[^>]+>")
SPACE = re.compile(r"\s+")


class Item(NamedTuple):
    source: str
    ext_id: str
    url: str
    title: str
    body: str
    lang: str
    src_cat: str
    src_ts_ms: int | None
    src_ts_prec: str  # ms | s | none


def clean(text: str | None, cap: int = BODY_CAP) -> str:
    return SPACE.sub(" ", html.unescape(TAG.sub(" ", text or ""))).strip()[:cap]


def bybit(js: dict) -> list[Item]:
    return [Item("bybit", a["url"], a["url"], clean(a["title"], 500), clean(a.get("description")), "en",
                 a["type"]["key"], int(a["publishTime"]), "s") for a in js["result"]["list"]]


def okx(js: dict) -> list[Item]:
    # pTime = publication; businessPTime is the effective time of the change, NOT when it was published
    return [Item("okx", a["url"].rstrip("/").rsplit("/", 1)[-1], a["url"], clean(a["title"], 500), "", "en",
                 a["annType"], int(a["pTime"]), "ms") for page in js["data"] for a in page["details"]]


def upbit(js: dict) -> list[Item]:
    items = []
    for n in js["data"]["notices"]:
        published = datetime.fromisoformat(n.get("first_listed_at") or n["listed_at"])  # edits bump listed_at
        url = f"https://upbit.com/service_center/notice?id={int(n['id'])}"
        items.append(Item("upbit", str(n["id"]), url, clean(n["title"], 500), "", "ko", str(n.get("category", "")),
                          int(published.timestamp() * 1000), "s"))
    return items


def rss(source: str, body: bytes) -> list[Item]:
    """body as bytes in a stream: given a str, feedparser would fetch it if it looks like a URL or path (SSRF)."""
    items = []
    for e in feedparser.parse(io.BytesIO(body)).entries:
        stamp = e.get("published_parsed")
        ts = calendar.timegm(stamp) * 1000 if stamp else None
        items.append(Item(source, e.get("id") or e.get("link", ""), e.get("link", ""), clean(e.get("title"), 500),
                          clean(e.get("summary")), "en", "rss", ts, "s" if ts else "none"))
    return [i for i in items if i.ext_id]


def binance_symbols(js: dict) -> dict[str, str]:
    return {s["symbol"]: f"{s['status']}|{s['baseAsset']}|{s['quoteAsset']}" for s in js["symbols"]}


def coinbase_products(js: list) -> dict[str, str]:
    return {p["id"]: f"{p['status']}|trading_disabled={p.get('trading_disabled')}|auction={p.get('auction_mode')}"
            for p in js}


def symbol_diff(source: str, old: dict[str, str], new: dict[str, str]) -> list[Item]:
    """New symbols and status changes as news items. No publication time: t0 comes from the first trade later."""
    items = []
    for sym, state in new.items():
        if old.get(sym) == state:
            continue
        cat = "new_symbol" if sym not in old else "status_change"
        title = f"{source} {sym}: {old.get(sym, 'absent')} -> {state}"
        items.append(Item(source, f"{sym}:{state}", "", title, "", "en", cat, None, "none"))
    return items
