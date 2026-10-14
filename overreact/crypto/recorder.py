"""Live recorder: Binance spot 1s bars + top of book, futures liquidations/funding/OI -> data/crypto.db.

Its job is what cannot be rebuilt later (bid/ask, liquidations, funding, OI); price bars also exist in the free dumps.
One asyncio process, no keys, public streams only. Exchange-clock timestamps (see clock.py).
Usage: python -m overreact.crypto.recorder [--rotate-after 82800] [--force-reconnect-after SECONDS]
"""
import argparse
import asyncio
import json
import math
import random
import sqlite3
import time
from array import array
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import requests
import websockets

from overreact.crypto import retention
from overreact.crypto.clock import ExchangeClock, burst, local_ms
from overreact.crypto.logsafe import setup
from overreact.crypto.store import connect

PAIRS_FILE = Path(__file__).resolve().parent.parent.parent / "crypto_pairs.txt"
SPOT_WS = "wss://stream.binance.com:9443/stream?streams="
FUT_WS = "wss://fstream.binance.com/market/stream?streams="
SPOT_REST = "https://api.binance.com/api/v3"
FUT_REST = "https://fapi.binance.com/fapi/v1"
NO_PERP = {"PEPEUSDT"}  # futures lists it as 1000PEPEUSDT
WATCH_TAIL_MS = 600_000  # keep streaming bid/ask 10 min after a watch window ends
MAX_WATCHED = 50
SLEEP_GAP_MS = 10_000  # wall-clock jump between 1 s ticks = PC slept or process froze
BACKFILL_MAX_S = 1000  # REST 1s klines per request
SQL = {
    "bars_1s": "INSERT OR REPLACE INTO bars_1s VALUES (?,?,?,?,?,?,?,?)",
    "bars_rest": "INSERT OR IGNORE INTO bars_1s VALUES (?,?,?,?,?,?,?,?)",  # backfill never overwrites live bars
    "spread_5s": "INSERT OR REPLACE INTO spread_5s VALUES (?,?,?,?)",
    "spread_evt": "INSERT OR REPLACE INTO spread_evt VALUES (?,?,?,?,?,?,?)",
    "spread_day": "INSERT OR REPLACE INTO spread_day VALUES (?,?,?,?)",
    "liq": "INSERT OR IGNORE INTO liq VALUES (?,?,?,?,?,?,?,?)",
    "funding": "INSERT OR REPLACE INTO funding VALUES (?,?,?,?)",
    "oi": "INSERT OR REPLACE INTO oi VALUES (?,?,?)",
    "clock_offset": "INSERT OR REPLACE INTO clock_offset VALUES (?,?,?)",
    "latency_probe": "INSERT INTO latency_probe VALUES (?,?,?)",
    "gaps": "INSERT INTO gaps VALUES (?,?,?,?,?,?)",
}


def load_pairs(path: Path = PAIRS_FILE) -> list[str]:
    # same format as prices.load_tickers; not imported to keep yfinance/pandas out of this 24/7 process
    lines = (line.split("#")[0].strip().upper() for line in path.read_text().splitlines())
    return [p for p in lines if p]


def num(value: str | float, positive: bool = True) -> float:
    x = float(value)
    if not math.isfinite(x) or (positive and x <= 0):
        raise ValueError(f"bad number {value!r}")
    return x


def parse_kline(d: dict) -> tuple | None:
    """Closed 1s bar with trades -> bars_1s row; open bars and empty seconds are skipped."""
    k = d["k"]
    if not k["x"] or int(k["n"]) == 0:
        return None
    return (k["s"], int(k["t"]) // 1000, num(k["c"]), num(k["h"]), num(k["l"]), num(k["q"], False), int(k["n"]), "live")


def parse_book(d: dict, recv_ms: int) -> tuple:
    """bookTicker has no event time: stamped with our exchange-clock receive time."""
    return (d["s"], recv_ms, num(d["b"]), num(d["a"]), num(d["B"], False), num(d["A"], False), "ws")


def parse_liq(d: dict, recv_ms: int) -> tuple:
    o = d["o"]
    return ("binance_um", o["s"], o["S"], num(o["q"]), num(o["p"]), num(o["ap"]), int(o["T"]), recv_ms)


def parse_mark(d: dict) -> tuple:
    return (d["s"], int(d["E"]), num(d["r"], False), int(d["T"]))


def rest_bar(sym: str, k: list) -> tuple:
    return (sym, int(k[0]) // 1000, num(k[4]), num(k[2]), num(k[3]), num(k[7], False), int(k[8]), "rest")


def watch_messages(have: set[str], want: set[str], msg_id: int) -> list[dict]:
    msgs = []
    if want - have:
        msgs.append({"method": "SUBSCRIBE", "params": sorted(want - have), "id": msg_id})
    if have - want:
        msgs.append({"method": "UNSUBSCRIBE", "params": sorted(have - want), "id": msg_id + 1})
    return msgs


def utc_day(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).date().isoformat()


def spread_stats(values: array) -> tuple[float, float]:
    s = sorted(values)
    return s[len(s) // 2], s[int(0.9 * (len(s) - 1))]


def get_json(url: str, params: dict | None = None) -> list | dict:
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


class Recorder:
    def __init__(self, pairs: list[str], log, conn: sqlite3.Connection):
        self.pairs, self.log, self.conn = pairs, log, conn
        self.perps = [p for p in pairs if p not in NO_PERP]
        self.clock = ExchangeClock()
        self.buf: dict[str, list[tuple]] = {table: [] for table in SQL}
        self.last_book: dict[str, tuple] = {}
        self.last_funding: dict[str, int] = {}
        self.last_msg: dict[str, int] = {}  # per stream, start of any outage
        self.watched: set[str] = set()
        self.spot_ws = None
        self.bad = self.last_probe = self.msg_id = 0
        self.day_spreads: dict[str, array] = {}
        self.day = utc_day(local_ms())

    # ---- message handlers (sync, no I/O) ----
    def on_spot(self, msg: dict, recv_ms: int) -> None:
        stream, d = msg.get("stream", ""), msg.get("data")
        if stream.endswith("@kline_1s"):
            if recv_ms - self.last_probe >= 60_000:
                self.last_probe = recv_ms
                self.buf["latency_probe"].append((recv_ms, d["s"], recv_ms - int(d["E"])))
            row = parse_kline(d)
            if row:
                self.buf["bars_1s"].append(row)
        elif stream.endswith("@bookTicker"):
            row = parse_book(d, recv_ms)
            if self.last_book.get(row[0]) != row[2:4]:  # store price changes only, not qty-only updates
                self.last_book[row[0]] = row[2:4]
                self.buf["spread_evt"].append(row)

    def on_fut(self, msg: dict, recv_ms: int) -> None:
        stream, d = msg.get("stream", ""), msg.get("data")
        if stream == "!forceOrder@arr":
            # since 2026-04-14 Binance sends only the largest liquidation per symbol per second: sizes are a lower bound
            self.buf["liq"].append(parse_liq(d, recv_ms))
        elif stream.endswith("@markPrice"):
            row = parse_mark(d)
            if row[1] - self.last_funding.get(row[0], 0) >= 60_000:
                self.last_funding[row[0]] = row[1]
                self.buf["funding"].append(row)

    # ---- websocket streams ----
    async def read(self, name: str, ws, handler) -> None:
        try:
            async for raw in ws:
                recv_ms = self.last_msg[name] = self.clock.now_ms()
                try:
                    handler(json.loads(raw), recv_ms)
                except (KeyError, TypeError, ValueError):
                    self.bad += 1
        finally:
            await ws.close()

    async def connect_ws(self, name: str, url: str, recent: deque):
        """Connect with exponential backoff + jitter; circuit breaker after 10 reconnects in 10 min."""
        backoff = 1.0
        while True:
            if len(recent) == recent.maxlen and time.monotonic() - recent[0] < 600:
                self.log.warning("%s: %d reconnects in 10 min, pausing 10 min", name, recent.maxlen)
                await asyncio.sleep(600)
            try:
                ws = await websockets.connect(url, open_timeout=10, max_size=2**20)
                recent.append(time.monotonic())
                return ws
            except (OSError, TimeoutError, websockets.WebSocketException) as err:
                self.log.warning("%s connect failed: %s", name, err)
                await asyncio.sleep(backoff + random.random())
                backoff = min(60.0, backoff * 2)

    async def stream(self, name: str, url: str, handler, life_s: float) -> None:
        """Keeps one live connection; every life_s opens a replacement before closing the old (PK upserts dedup)."""
        current, down_since, recent = None, None, deque(maxlen=10)
        while True:
            ws = await self.connect_ws(name, url, recent)
            if name == "spot":
                self.spot_ws, self.watched = ws, set()  # watch_loop resubscribes on the new connection
            old = current if current and not current.done() else None
            current = asyncio.create_task(self.read(name, ws, handler))
            if old:
                await asyncio.sleep(5)
                old.cancel()
                self.log.info("%s rotated", name)
            if down_since:
                await self.gap(name, down_since, self.clock.now_ms(), "disconnect")
                down_since = None
            done, _ = await asyncio.wait({current}, timeout=life_s)
            if done:
                down_since = self.last_msg.get(name, self.clock.now_ms())  # data stopped here, not at close
                err = None if current.cancelled() else current.exception()
                self.log.warning("%s stream ended: %r", name, err)

    async def gap(self, proc: str, t_from: int, t_to: int, cause: str) -> None:
        """Record a gap; spot bars up to BACKFILL_MAX_S are refilled from REST 1s klines (liquidations cannot be)."""
        filled = None
        if proc in ("spot", "rec"):
            end = min(t_to, t_from + BACKFILL_MAX_S * 1000)
            try:
                for sym in self.pairs:
                    params = {"symbol": sym, "interval": "1s", "startTime": t_from - 2000, "endTime": end, "limit": 1000}
                    klines = await asyncio.to_thread(get_json, f"{SPOT_REST}/klines", params)
                    self.buf["bars_rest"].extend(rest_bar(sym, k) for k in klines if int(k[8]) > 0)
                filled = "rest" if end == t_to else "rest_partial"
            except (requests.RequestException, ValueError, KeyError, IndexError) as err:
                self.log.warning("backfill failed: %s", err)
        self.buf["gaps"].append((proc, None, t_from, t_to, cause, filled))
        self.log.info("gap %s %s %.1f s filled_by=%s", proc, cause, (t_to - t_from) / 1000, filled)

    async def force_reconnect(self, after_s: float) -> None:
        """Test hook for the P2 gate: drop the spot connection once."""
        await asyncio.sleep(after_s)
        self.log.info("forcing spot reconnect")
        await self.spot_ws.close()

    # ---- periodic loops ----
    async def watch_loop(self) -> None:
        """Subscribe bookTicker for coins the news ear flagged (table watch), for the window + 10 min."""
        while True:
            await asyncio.sleep(1)
            now = self.clock.now_ms()
            rows = self.conn.execute("SELECT DISTINCT sym FROM watch WHERE from_ms <= ? AND until_ms + ? >= ? LIMIT ?",
                                     (now, WATCH_TAIL_MS, now, MAX_WATCHED)).fetchall()
            want = {f"{sym.lower()}@bookTicker" for (sym,) in rows}
            msgs = watch_messages(self.watched, want, self.msg_id)
            if not msgs or self.spot_ws is None:
                continue
            try:
                for m in msgs:
                    await self.spot_ws.send(json.dumps(m))
                    await asyncio.sleep(0.5)  # far below the 5 msgs/s limit
                self.watched, self.msg_id = want, self.msg_id + 2
            except websockets.ConnectionClosed:
                pass  # stream() reconnects and resets self.watched

    async def watchdog(self) -> None:
        last = self.clock.now_ms()
        while True:
            await asyncio.sleep(1)
            now = self.clock.now_ms()
            if now - last > SLEEP_GAP_MS:
                await self.gap("rec", last, now, "sleep")
            last = self.clock.now_ms()

    async def rest_loop(self) -> None:
        tick = 0
        while True:
            started = time.monotonic()
            try:
                await self.rest_tick(tick)
            except requests.HTTPError as err:
                self.log.warning("rest: %s", err)
                if err.response is not None and err.response.status_code in (418, 429):
                    await asyncio.sleep(int(err.response.headers.get("Retry-After", 60)))
            except (requests.RequestException, ValueError, KeyError) as err:
                self.log.warning("rest: %s", err)
            tick += 1
            await asyncio.sleep(max(0.0, 5 - (time.monotonic() - started)))

    async def rest_tick(self, tick: int) -> None:
        """Every 5 s top of book for live pairs; every minute clock + all-pair spreads; every 5 min open interest."""
        now = self.clock.now_ms()
        books = await asyncio.to_thread(get_json, f"{SPOT_REST}/ticker/bookTicker",
                                        {"symbols": json.dumps(self.pairs, separators=(",", ":"))})
        self.buf["spread_5s"].extend((b["symbol"], now // 1000, num(b["bidPrice"]), num(b["askPrice"])) for b in books)
        if tick % 12 == 0:
            offset, rtt = await asyncio.to_thread(burst, requests.Session())
            self.clock.add(offset)
            self.buf["clock_offset"].append((int(local_ms()), offset, rtt))
            self.sample_spreads(await asyncio.to_thread(get_json, f"{SPOT_REST}/ticker/bookTicker"), now)
        if tick % 720 == 0:
            self.write_spread_day()
        if tick % 60 == 0:
            for sym in self.perps:
                oi = await asyncio.to_thread(get_json, f"{FUT_REST}/openInterest", {"symbol": sym})
                self.buf["oi"].append((sym, int(oi["time"]), num(oi["openInterest"], False)))

    def sample_spreads(self, books: list[dict], now: int) -> None:
        if utc_day(now) != self.day:
            self.write_spread_day()
            self.day_spreads.clear()
            self.day = utc_day(now)
        for b in books:
            bid, ask = float(b["bidPrice"]), float(b["askPrice"])
            if b["symbol"].endswith("USDT") and 0 < bid <= ask:
                self.day_spreads.setdefault(b["symbol"], array("f")).append((ask - bid) / ((ask + bid) / 2) * 1e4)

    def write_spread_day(self) -> None:
        # ponytail: a restart mid-day overwrites the day with fewer samples; fine for a fallback spread
        self.buf["spread_day"].extend((sym, self.day, *spread_stats(v)) for sym, v in self.day_spreads.items() if v)

    async def flush_loop(self) -> None:
        last_rollup = 0.0
        while True:
            await asyncio.sleep(5)
            self.flush()
            if time.monotonic() - last_rollup > 3600:
                last_rollup = time.monotonic()
                now_s = self.clock.now_ms() // 1000
                with self.conn:
                    retention.rollup(self.conn, now_s - 3600)  # an hour of slack for late REST backfill
                    retention.prune(self.conn, now_s)

    def flush(self) -> None:
        """One transaction per 5 s; buffers are kept (retried next flush) if the write fails."""
        try:
            with self.conn:
                for table, rows in self.buf.items():
                    if rows:
                        self.conn.executemany(SQL[table], rows)
                info = json.dumps({"bad": self.bad, "watched": len(self.watched)})
                self.conn.execute("INSERT OR REPLACE INTO heartbeat VALUES ('rec', ?, ?)", (self.clock.now_ms(), info))
        except sqlite3.OperationalError as err:
            self.log.error("flush failed, keeping %d rows: %s", sum(map(len, self.buf.values())), err)
            return
        for rows in self.buf.values():
            rows.clear()


async def run(rotate_after: float, force_reconnect_after: float | None) -> None:
    log = setup("rec")
    pairs = load_pairs()
    rec = Recorder(pairs, log, connect())
    offset, _ = await asyncio.to_thread(burst, requests.Session())
    rec.clock.add(offset)
    last_beat = rec.conn.execute("SELECT ts_ms FROM heartbeat WHERE proc = 'rec'").fetchone()
    if last_beat and rec.clock.now_ms() - last_beat[0] > SLEEP_GAP_MS:  # crash, reboot or task stopped
        await rec.gap("rec", last_beat[0], rec.clock.now_ms(), "down")
    spot_url = SPOT_WS + "/".join(f"{p.lower()}@kline_1s" for p in pairs)
    fut_url = FUT_WS + "/".join(["!forceOrder@arr"] + [f"{p.lower()}@markPrice" for p in rec.perps])
    log.info("recorder start: %d pairs, %d perps, offset %.1f ms", len(pairs), len(rec.perps), offset)
    tasks = [rec.stream("spot", spot_url, rec.on_spot, rotate_after), rec.stream("fut", fut_url, rec.on_fut, rotate_after),
             rec.rest_loop(), rec.watch_loop(), rec.watchdog(), rec.flush_loop()]
    if force_reconnect_after:
        tasks.append(rec.force_reconnect(force_reconnect_after))
    await asyncio.gather(*tasks)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rotate-after", type=float, default=23 * 3600, help="seconds before replacing a connection")
    ap.add_argument("--force-reconnect-after", type=float, help="test hook: drop the spot connection once")
    a = ap.parse_args()
    log = setup("rec")
    while True:  # never die under the scheduler: log, wait, start over
        try:
            asyncio.run(run(a.rotate_after, a.force_reconnect_after))
        except KeyboardInterrupt:
            return
        except Exception:
            log.exception("recorder crashed, restarting in 30 s")
            time.sleep(30)


if __name__ == "__main__":
    main()
