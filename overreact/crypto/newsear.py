"""News ear: polls exchange announcements, crypto RSS and exchange symbol lists; stores every item with our
exchange-clock receive time (recv_ms) next to the source's own publication time. Never trades.
Telegram comes later as one more source calling insert_news.

Usage: python -m overreact.crypto.newsear            (loop, runs forever)
       python -m overreact.crypto.newsear --report   (ear latency per source: recv_ms - src_ts_ms)
"""
import argparse
import hashlib
import json
import os
import sqlite3
import statistics
import time
from typing import Callable, NamedTuple

import requests

from overreact.crypto import sources
from overreact.crypto.net import UA, Throttled, next_delay, raise_for_throttle
from overreact.crypto.clock import ExchangeClock, burst
from overreact.crypto.coins import extract, load_aliases
from overreact.crypto.logsafe import clip, setup
from overreact.crypto.store import DB_PATH, connect

STATE_DIR = DB_PATH.parent
MAX_BYTES = 2_000_000
DEADLINE_S = 20  # whole-response deadline; requests timeouts are per read
SKEW_MS = 500  # receive earlier than publication by more than clock resolution = source clock is off
WATCH_MS = 15 * 60_000  # ask the recorder for bid/ask on a mentioned coin for 15 min (+10 min tail there)
DOWN_GAP_MS = 60_000


class Source(NamedTuple):
    url: str
    params: dict | None
    interval_s: float
    parse: Callable  # body -> list[Item], or -> dict state for kind "diff"
    kind: str = "json"  # json | xml | diff
    max_bytes: int = MAX_BYTES


def rss(name: str, url: str) -> Source:
    return Source(url, None, 60, lambda body: sources.rss(name, body), "xml")


SOURCES = {
    "bybit": Source("https://api.bybit.com/v5/announcements/index", {"locale": "en-US", "limit": 20}, 5, sources.bybit),
    "okx": Source("https://www.okx.com/api/v5/support/announcements", None, 5, sources.okx),
    "upbit": Source("https://api-manager.upbit.com/api/v1/announcements",
                    {"os": "web", "page": 1, "per_page": 20, "category": "trade"}, 10, sources.upbit),
    "binance_symbols": Source("https://api.binance.com/api/v3/exchangeInfo",
                              {"permissions": "SPOT", "showPermissionSets": "false"}, 60, sources.binance_symbols,
                              "diff", 20_000_000),
    "coinbase_products": Source("https://api.exchange.coinbase.com/products", None, 60, sources.coinbase_products, "diff"),
    "coindesk": rss("coindesk", "https://www.coindesk.com/arc/outboundfeeds/rss"),
    "cointelegraph": rss("cointelegraph", "https://cointelegraph.com/rss"),
    "decrypt": rss("decrypt", "https://decrypt.co/feed"),
    "theblock": rss("theblock", "https://www.theblock.co/rss.xml"),
}


def fetch(http: requests.Session, src: Source, validators: dict) -> bytes | None:
    """GET with size cap and ETag/Last-Modified. None = not modified."""
    headers = {"User-Agent": UA}
    if validators.get("etag"):
        headers["If-None-Match"] = validators["etag"]
    if validators.get("modified"):
        headers["If-Modified-Since"] = validators["modified"]
    with http.get(src.url, params=src.params, headers=headers, timeout=5, stream=True) as resp:
        raise_for_throttle(resp)
        if resp.status_code == 304:
            return None
        resp.raise_for_status()
        body, started = b"", time.monotonic()
        for chunk in resp.iter_content(65_536):
            body += chunk
            if len(body) > src.max_bytes:
                raise ValueError(f"response over {src.max_bytes} bytes")
            if time.monotonic() - started > DEADLINE_S:
                raise ValueError(f"response slower than {DEADLINE_S} s")
        validators.update(etag=resp.headers.get("ETag"), modified=resp.headers.get("Last-Modified"))
    return body


def digest(item: sources.Item) -> str:
    return hashlib.sha256(f"{item.title}\n{item.body}".encode()).hexdigest()


def insert_news(conn: sqlite3.Connection, item: sources.Item, recv_ms: int, offset_ms: float, backlog: bool) -> int | None:
    """New item -> its id. Known item with changed text -> revision row; the original times are never touched."""
    h = digest(item)
    row = conn.execute("SELECT id, hash FROM cnews WHERE source = ? AND ext_id = ?", (item.source, item.ext_id)).fetchone()
    if row:
        seen = row[1] == h or conn.execute("SELECT 1 FROM cnews_rev WHERE news_id = ? AND hash = ?", (row[0], h)).fetchone()
        if not seen:
            conn.execute("INSERT INTO cnews_rev VALUES (?,?,?,?,?)", (row[0], recv_ms, item.title, item.body, h))
        return None
    skew = item.src_ts_ms is not None and recv_ms - item.src_ts_ms < -SKEW_MS
    cur = conn.execute(
        "INSERT INTO cnews (source, ext_id, url, title, body, lang, src_cat, src_ts_ms, src_ts_prec, recv_ms, offset_ms,"
        " hash, backlog, src_skew) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (*item, recv_ms, offset_ms, h, int(backlog), int(skew)))
    return cur.lastrowid


def usdt_bases(state: dict[str, str]) -> set[str]:
    bases = set()
    for value in state.values():
        status, base, quote = value.split("|")
        if status == "TRADING" and quote == "USDT":
            bases.add(base)
    return bases


class Ear:
    def __init__(self, conn: sqlite3.Connection, log, http: requests.Session):
        self.conn, self.log, self.http = conn, log, http
        self.clock = ExchangeClock()
        self.next_at = {name: 0.0 for name in SOURCES}
        self.fails = {name: 0 for name in SOURCES}
        self.validators: dict[str, dict] = {name: {} for name in SOURCES}
        self.unpolled = set(SOURCES)  # first poll after start: new items may be old news -> backlog
        self.state = {name: self.load_state(name) for name, s in SOURCES.items() if s.kind == "diff"}
        self.bases = usdt_bases(self.state.get("binance_symbols") or {})
        self.aliases = load_aliases()

    @staticmethod
    def load_state(name: str) -> dict | None:
        path = STATE_DIR / f"crypto_state_{name}.json"
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):  # missing or corrupt file = no baseline; never crash-loop on it
            return None

    def save_state(self, name: str, state: dict) -> None:
        """Atomic: a kill mid-write leaves the previous file intact."""
        path = STATE_DIR / f"crypto_state_{name}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state))
        os.replace(tmp, path)
        self.state[name] = state
        if name == "binance_symbols":
            self.bases = usdt_bases(state)

    def items_for(self, name: str, src: Source, body: bytes) -> tuple[list[sources.Item], dict | None]:
        """Items to store, plus the new diff baseline (saved only after the items are stored)."""
        if src.kind == "xml":
            return src.parse(body), None  # bytes, never str: feedparser treats a str as a URL or path to open
        parsed = src.parse(json.loads(body))
        if src.kind != "diff":
            return parsed, None
        old = self.state[name]
        return ([] if old is None else sources.symbol_diff(name, old, parsed)), parsed  # first run = baseline

    def poll(self, name: str) -> None:
        src = SOURCES[name]
        throttled, retry_s = False, None
        validators = dict(self.validators[name])
        try:
            body = fetch(self.http, src, validators)
            recv_ms = self.clock.now_ms()
            items, new_state = ([], None) if body is None else self.items_for(name, src, body)
            self.store(items, recv_ms, backlog=name in self.unpolled)
            if new_state is not None:
                self.save_state(name, new_state)
            self.validators[name] = validators  # only now: a failed store must not turn the next poll into a 304
            self.unpolled.discard(name)
            self.fails[name] = 0
        except Throttled as err:
            self.fails[name] += 1
            throttled, retry_s = True, err.retry_after
            self.log.warning("%s throttled (%s), fail %d", name, err, self.fails[name])
        except (requests.RequestException, ValueError, KeyError, TypeError, OSError, sqlite3.Error) as err:
            self.fails[name] += 1
            self.log.warning("%s failed: %s", name, clip(str(err)))
        self.next_at[name] = time.monotonic() + next_delay(src.interval_s, self.fails[name], throttled, retry_s)

    def store(self, items: list[sources.Item], recv_ms: int, backlog: bool) -> None:
        with self.conn:
            for item in items:
                news_id = insert_news(self.conn, item, recv_ms, self.clock.offset_ms, backlog)
                if news_id is None:
                    continue
                coins = extract(item.title, self.bases, self.aliases)
                self.conn.executemany("INSERT OR IGNORE INTO cnews_coins VALUES (?,?,'rule',?)",
                                      [(news_id, c, conf) for c, conf in coins.items()])
                if not backlog:
                    self.conn.executemany("INSERT OR IGNORE INTO watch VALUES (?,?,?,?)",
                                          [(f"{c}USDT", recv_ms, recv_ms + WATCH_MS, f"news {news_id}")
                                           for c in coins if c in self.bases])
                    self.log.info("NEW %s [%s] %s coins=%s", item.source, clip(item.src_cat, 40), clip(item.title, 120),
                                  ",".join(coins))

    def mark_downtime(self) -> None:
        row = self.conn.execute("SELECT ts_ms FROM heartbeat WHERE proc = 'news'").fetchone()
        now = self.clock.now_ms()
        if row and now - row[0] > DOWN_GAP_MS:
            with self.conn:
                self.conn.execute("INSERT INTO gaps VALUES ('news', NULL, ?, ?, 'down', NULL)", (row[0], now))

    def run(self) -> None:
        self.clock.add(burst(self.http)[0])
        self.mark_downtime()
        last_clock = last_beat = time.monotonic()
        while True:
            for name in [n for n, t in self.next_at.items() if t <= time.monotonic()]:
                self.poll(name)
            if time.monotonic() - last_clock > 60:
                last_clock = time.monotonic()
                try:
                    self.clock.add(burst(self.http)[0])
                except (requests.RequestException, ValueError, KeyError) as err:
                    self.log.warning("clock: %s", err)
            if time.monotonic() - last_beat > 5:
                last_beat = time.monotonic()
                with self.conn:
                    self.conn.execute("INSERT OR REPLACE INTO heartbeat VALUES ('news', ?, ?)",
                                      (self.clock.now_ms(), json.dumps({"fails": {k: v for k, v in self.fails.items() if v}})))
            time.sleep(0.2)


def report(conn: sqlite3.Connection) -> None:
    """Ear latency = our receive time - source publication time, live items only (no backlog, no skew)."""
    rows = conn.execute("SELECT source, src_ts_prec, recv_ms - src_ts_ms FROM cnews WHERE backlog = 0 AND src_skew = 0 "
                        "AND src_ts_ms IS NOT NULL ORDER BY source").fetchall()
    by_source: dict[tuple[str, str], list[int]] = {}
    for source, prec, lag in rows:
        by_source.setdefault((source, prec), []).append(lag)
    print(f"{'source':16} {'prec':4} {'n':>5} {'median_s':>9} {'p90_s':>9}")
    for (source, prec), lags in by_source.items():
        p90 = statistics.quantiles(lags, n=10)[-1] if len(lags) > 1 else lags[0]
        print(f"{source:16} {prec:4} {len(lags):5} {statistics.median(lags) / 1000:9.1f} {p90 / 1000:9.1f}")
    print(conn.execute("SELECT count(*), sum(backlog), sum(src_skew) FROM cnews").fetchone(), "(all, backlog, skew)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    if ap.parse_args().report:
        report(connect())
        return
    log = setup("news")
    while True:  # never die under the scheduler
        try:
            Ear(connect(), log, requests.Session()).run()
        except KeyboardInterrupt:
            return
        except Exception:
            log.exception("news ear crashed, restarting in 30 s")
            time.sleep(30)


if __name__ == "__main__":
    main()
