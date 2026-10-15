"""Lab experiments G4 (liquidation-cascade rebound) and G5 (negative funding), with the rules pre-registered in
LAB_crypto.md. Spot long only, 1m closes + slippage + taker fees, CI by bootstrap clustered on the UTC day.

Universe: the recorder pairs + the 20 biggest Binance perps (24h quote volume today) that have a spot USDT pair
and were listed before 2024-01-01. Picking by today's volume is survivorship bias (dead coins are missing);
it is recorded as a caveat, not fixed.
Usage: python -m overreact.crypto.lab cascade|funding|upbit
"""
import argparse
import math
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from overreact.crypto import dumps, history, sim
from overreact.crypto.coins import extract
from overreact.crypto.meter import cluster_ci, price_at
from overreact.crypto.net import get_json
from overreact.crypto.newsear import Ear
from overreact.crypto.store import connect

FEE, SLIP = 0.001, 0.001  # per side; slippage pre-registered at 0.1% for non-listing events
CONF_END = datetime(2025, 10, 1, tzinfo=timezone.utc).timestamp()  # before: confirmation, after: exploration
START = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
PAIRS = Path(__file__).resolve().parents[2] / "crypto_pairs.txt"
OUT = dumps.CACHE.parent


def universe(extra: int = 20) -> list[str]:
    base = [s.strip() for s in PAIRS.read_text().splitlines() if s.strip() and not s.startswith("#")]
    spot = {v.split("|")[1] + "USDT" for v in (Ear.load_state("binance_symbols") or {}).values()
            if v.startswith("TRADING|") and v.endswith("|USDT")}
    info = get_json("https://fapi.binance.com/fapi/v1/exchangeInfo")
    old = {s["symbol"] for s in info["symbols"] if s["onboardDate"] < START * 1000 and s["contractType"] == "PERPETUAL"}
    vol = sorted(get_json("https://fapi.binance.com/fapi/v1/ticker/24hr"), key=lambda r: -float(r["quoteVolume"]))
    picked = [r["symbol"] for r in vol if r["symbol"] in old & spot and r["symbol"] not in base][:extra]
    return base + picked


def months(start: float, end: float) -> list[str]:
    d, out = datetime.fromtimestamp(start, timezone.utc).date().replace(day=1), []
    while d <= datetime.fromtimestamp(end, timezone.utc).date():
        out.append(d.strftime("%Y-%m"))
        d = (d + timedelta(days=32)).replace(day=1)
    return out


def spot_1m(sym: str, start: float, end: float) -> tuple[np.ndarray, np.ndarray]:
    ts, cl = [], []
    for m in months(start, end):
        bars = dumps.month_bars(sym, "1m", m)
        if bars:
            ts.append(np.array([b[0] for b in bars], dtype=np.int64))
            cl.append(np.array([b[1] for b in bars]))
    if not ts:
        return np.array([], dtype=np.int64), np.array([])
    return np.concatenate(ts), np.concatenate(cl)


def net(ts: np.ndarray, cl: np.ndarray, t_in: float, t_out: float) -> float | None:
    p_in, p_out = price_at(ts, cl, t_in, 60), price_at(ts, cl, t_out, 60)
    if p_in is None or p_out is None or t_out > ts[-1] + 60:
        return None
    return math.log(p_out * (1 - SLIP) * (1 - FEE) / (p_in * (1 + SLIP) * (1 + FEE)))


class OpenInterest:
    """5-min open interest from the daily futures metrics dumps, downloaded only for days we ask about."""

    def __init__(self, sym: str):
        self.sym, self.days = sym, {}

    def at(self, t: float) -> float | None:
        day = datetime.fromtimestamp(t, timezone.utc).date().isoformat()
        if day not in self.days:
            text = dumps.csv_text(f"futures/um/daily/metrics/{self.sym}/{self.sym}-metrics-{day}.zip")
            rows = [line.split(",") for line in (text or "").splitlines()[1:]]
            self.days[day] = sorted((datetime.fromisoformat(r[0]).replace(tzinfo=timezone.utc).timestamp(), float(r[2]))
                                    for r in rows if r[2])
        known = [v for ts, v in self.days[day] if ts <= t]  # snapshot stamped at or before t
        return known[-1] if known else None


def cascade_events(sym: str, ts: np.ndarray, cl: np.ndarray) -> list[float]:
    """Pre-registered: close drop >= 4% over 15 min AND open interest down >= 3% over the same 15 min.
    Evaluated at the close of each 1m bar; one event per coin per 6 h."""
    t_close = ts + 60
    j = np.searchsorted(ts, t_close - 900 - 60, side="right") - 1  # last bar closed 15 min earlier
    ok = j >= 0
    drop = np.full(len(ts), 0.0)
    drop[ok] = np.log(cl[ok] / cl[j[ok]])
    oi, events, last = OpenInterest(sym), [], -math.inf
    for i in np.flatnonzero(drop <= math.log(0.96)):
        t = float(t_close[i])
        if t - last < 6 * 3600:
            continue
        now, then = oi.at(t), oi.at(t - 900)
        if now and then and now / then - 1 <= -0.03:
            events.append(t)
            last = t
    return events


def funding_events(sym: str, start: float, end: float, gap_s: float) -> list[float]:
    """Pre-registered: published funding <= -0.05%. A new event only after the previous trade has exited."""
    events, last = [], -math.inf
    for m in months(start, end):
        text = dumps.csv_text(f"futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{m}.zip")
        for line in (text or "").splitlines()[1:]:
            calc_ms, _, rate = line.split(",")
            t = int(calc_ms) / 1000
            if float(rate) <= -0.0005 and t - last >= gap_s:
                events.append(t)
                last = t
    return events


def evaluate(sym: str, ts: np.ndarray, cl: np.ndarray, events: list[float], lags: tuple, horizons: tuple,
             rng: random.Random) -> list[dict]:
    rows = []
    for t in events:
        for lag in lags:
            for h in horizons:
                r = net(ts, cl, t + lag, t + lag + h)
                if r is not None:
                    rows.append({"sym": sym, "t": t, "lag": lag, "h": h, "net": r, "placebo": False})
    for _ in range(5 * len(events)):  # same coin, random times in the same span, every horizon
        t = rng.uniform(float(ts[0]) + 3600, float(ts[-1]) - max(horizons))
        for h in horizons:
            r = net(ts, cl, t + lags[0], t + lags[0] + h)
            if r is not None:
                rows.append({"sym": sym, "t": t, "lag": lags[0], "h": h, "net": r, "placebo": True})
    return rows


def summarize(df: pd.DataFrame, title: str) -> str:
    df = df.assign(period=np.where(df["t"] < CONF_END, "CONFIRMATION 2024-01..2025-09", "EXPLORATION 2025-10.."),
                   day=pd.to_datetime(df["t"], unit="s").dt.date)
    lines = [f"\n== {title}"]
    for (period, lag, h), g in df[~df["placebo"]].groupby(["period", "lag", "h"]):
        x = g["net"] * 1e4
        mean, lo, hi = cluster_ci([list(v) for _, v in x.groupby(g["day"])])
        plac = df[df["placebo"] & (df["period"] == period) & (df["h"] == h)]["net"].mean() * 1e4
        lines.append(f"  {period} entry +{lag // 60}m hold {h // 60}m: n={len(g)} ({g['day'].nunique()} days) "
                     f"net {mean:7.1f} bps CI [{lo:7.1f}, {hi:7.1f}] hit {(x > 0).mean():.0%} | placebo {plac:6.1f} bps")
    return "\n".join(lines)


def upbit_listings(conn, bases: set[str]) -> list[tuple[int, str, float]]:
    """(news_id, coin, t0) for Upbit listing notices with the fixed G1 rules; same coin within 1 h counts once."""
    out, seen = [], {}
    rows = conn.execute("SELECT id, title, src_ts_ms FROM cnews WHERE source = 'upbit' AND src_ts_ms >= ? "
                        "ORDER BY src_ts_ms", (START * 1000,)).fetchall()
    for news_id, title, t_ms in rows:
        if history.news_type(title) != "listing":
            continue
        for coin, conf in extract(title, bases, {}).items():
            if conf >= 0.6 and coin in bases and t_ms / 1000 - seen.get(coin, -math.inf) > 3600:
                seen[coin] = t_ms / 1000
                out.append((news_id, coin, t_ms / 1000))
    return out


def detection_lags(interval_s: float, rng: random.Random, n: int = 200) -> list[float]:
    """Seconds from publication to our order at the exchange when polling every interval_s (D1/D2 measurements):
    wait for the next poll + Cloudflare cache age (max-age=1) + fetch ~0.35 s + loop tick + order RTT ~0.27 s."""
    return [rng.uniform(0, interval_s) + rng.uniform(0, 1) + 0.35 + 0.05 + 0.27 for _ in range(n)]


def upbit(end: float) -> None:
    """G3 + D2: Upbit listing -> buy Binance spot at latency L, sell at +5 min (primary) or +60 min (secondary)."""
    conn = connect()
    state = Ear.load_state("binance_symbols") or {}
    bases = {v.split("|")[1] for v in state.values() if v.endswith("|USDT")}
    rng, rows = random.Random(0), []
    for news_id, coin, t0 in upbit_listings(conn, bases):
        if t0 > end:
            continue
        bars = history.bars_window(f"{coin}USDT", t0 - 600, t0 + 3700)
        if not bars or t0 - (max((b[0] for b in bars if b[0] + 1 <= t0), default=-math.inf) + 1) > history.STALE_S:
            continue  # no Binance pair then, or not really trading
        row = {"news_id": news_id, "coin": coin, "t": t0}
        for lag in (1, 2, 3, 5, 10, 15):
            for h in (300, 3600):
                row[f"L{lag}_h{h}"] = sim.trade(bars, t0 + lag, t0 + h, slip=0.005)
        for interval in (1, 2, 3, 5, 10):
            nets = [sim.trade(bars, t0 + lag, t0 + 300, slip=0.005) for lag in detection_lags(interval, rng)]
            nets = [x for x in nets if x is not None]
            row[f"poll{interval}_h300"] = sum(nets) / len(nets) if nets else None
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "lab_upbit.csv", index=False)
    df["period"] = np.where(df["t"] < CONF_END, "CONFIRMATION 2024-01..2025-09", "EXPLORATION 2025-10..")
    for period, g in df.groupby("period"):
        print(f"\n== Upbit listings {period}: n={len(g)} events, {g['news_id'].nunique()} notices")
        for col in [c for c in df.columns if c.startswith(("L", "poll"))]:
            x = (g[col].dropna() * 1e4)
            if x.empty:
                continue
            mean, lo, hi = cluster_ci([list(v) for _, v in x.groupby(g.loc[x.index, "news_id"])])
            print(f"  {col:12} net {mean:8.1f} bps  CI [{lo:8.1f}, {hi:8.1f}]  hit {(x > 0).mean():.0%}  n={len(x)}")


def run(kind: str) -> None:
    end = datetime.combine(date.today() - timedelta(days=3), datetime.min.time(), timezone.utc).timestamp()
    if kind == "upbit":
        upbit(end)
        return
    syms, rng, rows = universe(), random.Random(0), []
    print("universe:", " ".join(syms))
    for sym in syms:
        ts, cl = spot_1m(sym, START, end)
        if not len(ts):
            continue
        if kind == "cascade":
            ev = cascade_events(sym, ts, cl)
            rows += evaluate(sym, ts, cl, ev, (60, 300, 900), (3600, 4 * 3600), rng)
        else:
            ev = funding_events(sym, START, end, 72 * 3600)
            rows += evaluate(sym, ts, cl, ev, (60, 300), (24 * 3600, 72 * 3600), rng)
        print(f"  {sym}: {len(ev)} events", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / f"lab_{kind}.csv", index=False)
    print(summarize(df, kind))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["cascade", "funding", "upbit"])
    run(ap.parse_args().kind)
