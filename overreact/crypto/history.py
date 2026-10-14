"""Exploratory backtest on public history (plan P4b): did Binance spot prices react to listing and delisting
announcements on OKX, Bybit and Upbit, and how much of the move was left after waiting L seconds?

Uses the sources' own publication times and Binance 1s dumps. No receive latency, no historical spread, many
looks at the data: this is exploration, NEVER evidence for the GO gate.
Usage: python -m overreact.crypto.history [--since 2025-10-01] [--no-fetch]
"""
import argparse
import re
import time
import zipfile
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

from overreact.crypto import dumps, sources
from overreact.crypto.coins import extract
from overreact.crypto.meter import HORIZONS_S, PRE_S, cluster_ci, path
from overreact.crypto.net import Throttled, get_json
from overreact.crypto.newsear import Ear, insert_news
from overreact.crypto.store import connect

DELISTING = re.compile(r"delist|거래지원 종료", re.I)
LISTING = re.compile(r"\b(will list|to list|listing|lists|list)\b|디지털 자산 추가", re.I)
DERIV = re.compile(r"perpetual|futures|derivatives|margin", re.I)
COST_BPS = 20  # round trip at ~0.1% taker per side; spread NOT included (no history) -> results are optimistic
WINDOW_S = (-600, 3600)
STALE_S = 600  # last trade before t0 older than this = pair not really trading
PAGERS = {  # name -> (url, params for a page, parser)
    "okx_listings": ("https://www.okx.com/api/v5/support/announcements",
                     lambda p: {"annType": "announcements-new-listings", "page": p}, sources.okx),
    "okx_delistings": ("https://www.okx.com/api/v5/support/announcements",
                       lambda p: {"annType": "announcements-delistings", "page": p}, sources.okx),
    "bybit_listings": ("https://api.bybit.com/v5/announcements/index",
                       lambda p: {"locale": "en-US", "type": "new_crypto", "page": p, "limit": 20}, sources.bybit),
    "bybit_delistings": ("https://api.bybit.com/v5/announcements/index",
                         lambda p: {"locale": "en-US", "type": "delistings", "page": p, "limit": 20}, sources.bybit),
    "upbit_trade": ("https://api-manager.upbit.com/api/v1/announcements",
                    lambda p: {"os": "web", "page": p, "per_page": 20, "category": "trade"}, sources.upbit),
}


def news_type(title: str) -> str | None:
    if DELISTING.search(title):  # first: "delisting" contains "listing"
        return "delisting"
    return "listing" if LISTING.search(title) else None


def fetch_history(conn, since_ms: int) -> None:
    """Page back until items are older than since. Stored as backlog (we did not receive them live)."""
    for name, (url, params, parse) in PAGERS.items():
        n = 0
        for page in range(1, 300):
            batch = parse(get_json(url, params(page)))
            with conn:
                for item in batch:
                    n += insert_news(conn, item, int(time.time() * 1000), 0.0, backlog=True) is not None
            if not batch or min(i.src_ts_ms for i in batch) < since_ms:
                break
            time.sleep(1)  # polite
        print(f"{name}: {n} new items")


def events(conn, since_ms: int, until_ms: int, bases: set[str]) -> pd.DataFrame:
    rows = conn.execute("SELECT id, source, src_cat, title, src_ts_ms FROM cnews WHERE source IN ('okx','bybit','upbit') "
                        "AND src_ts_ms BETWEEN ? AND ?", (since_ms, until_ms)).fetchall()
    out = []
    for news_id, source, cat, title, t0_ms in rows:
        kind = news_type(title)
        if not kind:
            continue
        market = "deriv" if DERIV.search(f"{title} {cat}") else "spot"
        for coin, conf in extract(title, bases, {}).items():
            if conf >= 0.9:  # explicit mentions only: (XYZ), XYZ/USDT, $XYZ
                out.append({"news_id": news_id, "source": source, "kind": kind, "market": market, "coin": coin,
                            "t0_ms": t0_ms, "title": title[:80]})
    return pd.DataFrame(out)


def utc_day(t_s: float) -> str:
    return datetime.fromtimestamp(t_s, timezone.utc).date().isoformat()


def window(sym: str, t0: float) -> tuple[list[int], list[float]] | None:
    start, end = t0 + WINDOW_S[0], t0 + WINDOW_S[1]
    bars = []
    for day in sorted({utc_day(start), utc_day(end)}):
        day_bars = dumps.day_bars(sym, day)
        if day_bars is None:
            return None
        bars += [b for b in day_bars if start <= b[0] <= end]
    return [b[0] for b in bars], [b[1] for b in bars]


def measure(sym: str, t0: float) -> dict[int, float] | str:
    w = window(sym, t0)
    if w is None:
        return "no_dump"
    ts, closes = w
    before = [t for t in ts if t + 1 <= t0]
    if not before or t0 - (before[-1] + 1) > STALE_S:
        return "stale"
    return path(ts, closes, t0) or "stale"  # None = some pre-event price unknown


def run_events(ev: pd.DataFrame, out) -> pd.DataFrame:
    """Measures every event; the CSV is rewritten every 25 events so a crash keeps what was done.
    A throttle from the dump host stops the run (partial results kept) instead of hammering it."""
    rows = []
    for i, e in enumerate(ev.itertuples(index=False)):
        t0 = e.t0_ms / 1000
        try:
            real, placebo = measure(f"{e.coin}USDT", t0), measure(f"{e.coin}USDT", t0 - 86_400)
        except Throttled as err:
            print(f"dump host throttled us ({err}); stopping with {len(rows)} events measured")
            break
        except (requests.RequestException, ValueError, KeyError, TypeError, zipfile.BadZipFile) as err:
            real, placebo = f"error {type(err).__name__}", "error"
        row = e._asdict() | {"status": real if isinstance(real, str) else "ok"}
        if isinstance(real, dict):
            row |= {f"r{h}": v for h, v in real.items()}
        if isinstance(placebo, dict):
            row |= {f"p{h}": v for h, v in placebo.items()}
        rows.append(row)
        if i % 25 == 0:
            pd.DataFrame(rows).to_csv(out, index=False)
            print(f"  {i}/{len(ev)} measured", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(out, index=False)
    return df


def capture_table(g: pd.DataFrame, sign: int) -> list[str]:
    """Move from t0+L to t0+h in the expected direction, minus costs, CI by news item."""
    lines = []
    for lag in (1, 3, 10, 60):
        for h in (300, 3600):
            x = (sign * (g[f"r{h}"] - g[f"r{lag}"]) * 1e4 - COST_BPS).dropna()
            if x.empty:
                continue
            mean, lo, hi = cluster_ci([list(v) for _, v in x.groupby(g.loc[x.index, "news_id"])])
            lines.append(f"    L={lag:>2}s -> {h // 60:>2}m: net {mean:7.1f} bps  CI [{lo:7.1f}, {hi:7.1f}]  "
                         f"hit {(x > 0).mean():.0%}")
    return lines


def report(df: pd.DataFrame) -> None:
    print(f"\n{len(df)} events, status: {df['status'].value_counts().to_dict()}")
    ok = df[df["status"] == "ok"]
    for (source, kind, market), g in ok.groupby(["source", "kind", "market"]):
        if len(g) < 5:
            continue
        sign = 1 if kind == "listing" else -1
        print(f"\n== {source} {kind} {market} | n={len(g)} events, {g['news_id'].nunique()} news items | "
              f"median signed move in bps (real / placebo same time D-1)")
        cols = PRE_S + HORIZONS_S
        real = [f"{h:>5}s {sign * g[f'r{h}'].median() * 1e4:7.1f}" for h in cols]
        plac = [f"{sign * g[f'p{h}'].median() * 1e4:7.1f}" if f"p{h}" in g else "    n/a" for h in cols]
        for r, p in zip(real, plac):
            print(f"  {r} / {p}")
        print("  capturable after waiting L, net of 20 bps (no spread):")
        print("\n".join(capture_table(g, sign)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2025-10-01")
    ap.add_argument("--no-fetch", action="store_true", help="reuse announcements already in the DB")
    a = ap.parse_args()
    since_ms = int(datetime.fromisoformat(a.since).replace(tzinfo=timezone.utc).timestamp() * 1000)
    until = datetime.combine(date.today() - timedelta(days=2), datetime.min.time(), timezone.utc)  # dumps lag ~1 day
    conn = connect()
    if not a.no_fetch:
        fetch_history(conn, since_ms)
    state = Ear.load_state("binance_symbols") or sources.binance_symbols(
        get_json("https://api.binance.com/api/v3/exchangeInfo", {"permissions": "SPOT", "showPermissionSets": "false"}))
    bases = {v.split("|")[1] for v in state.values() if v.endswith("|USDT")}  # any status: may have traded back then
    ev = events(conn, since_ms, int(until.timestamp() * 1000), bases)
    print(f"{len(ev)} coin events from {ev['news_id'].nunique() if len(ev) else 0} announcements")
    out = dumps.CACHE.parent / "history_events.csv"
    df = run_events(ev, out)
    report(df)
    print(f"\nrows saved to {out}")


if __name__ == "__main__":
    main()
