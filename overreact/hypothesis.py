"""Event study: does the market overreact to SEC 8-Ks, judged against what the LLM read in them?

For each 8-K: entry at the close of the trading day AFTER filing (filing surely public, market reacted).
reaction = z (stretch from fair band) at entry. Overreaction = strong move against the LLM's reading:
dropped (z <= -cut) on neutral/positive news, or jumped (z >= cut) on neutral/negative news.
Outcome = forward excess return (demeaned per ticker) from entry over 1/5/10 days.

Usage: python -m overreact.hypothesis [--cut 1.5] [--split 2022-01-01]
"""
import argparse

import numpy as np
import pandas as pd

from overreact.db import connect
from overreact.fairvalue import HORIZONS, band, forward_return


def events_for(close: pd.Series, filings: pd.DataFrame, window: int) -> pd.DataFrame:
    """filings: rows with filed date + direction for ONE ticker. Returns one row per usable event."""
    z = band(close, window)["z"]
    excess = {h: forward_return(close, h) - forward_return(close, h).mean() for h in HORIZONS}
    dates = close.index.to_numpy()
    rows = []
    for filed, direction in filings[["filed", "direction"]].itertuples(index=False):
        i = np.searchsorted(dates, filed, side="right")  # first trading day strictly after filing date
        if i >= len(dates) or np.isnan(z.iloc[i]):
            continue
        row = {"entry": dates[i], "direction": direction, "z": z.iloc[i]}
        row |= {f"ex_{h}d": excess[h].iloc[i] for h in HORIZONS}
        rows.append(row)
    return pd.DataFrame(rows)


def label(ev: pd.DataFrame, cut: float) -> pd.Series:
    groups = np.select(
        [(ev["z"] <= -cut) & (ev["direction"] >= 0), (ev["z"] >= cut) & (ev["direction"] <= 0),
         (ev["z"] <= -cut) & (ev["direction"] < 0), (ev["z"] >= cut) & (ev["direction"] > 0)],
        ["OVERREACT: dropped, news not bad", "OVERREACT: jumped, news not good",
         "justified: dropped, bad news", "justified: jumped, good news"],
        default="no strong move",
    )
    return pd.Series(groups, index=ev.index)


def summary(ev: pd.DataFrame, cut: float) -> pd.DataFrame:
    """Mean excess return (%) and hit rate in the direction a contrarian would bet."""
    ev = ev.assign(group=label(ev, cut))
    # contrarian bet: buy after drops, short after jumps
    ev["bet"] = np.where(ev["z"] < 0, 1, -1)
    out = {}
    for name, g in ev.groupby("group"):
        row = {"n": len(g)}
        for h in HORIZONS:
            edge = (g[f"ex_{h}d"] * g["bet"]).dropna()
            row[f"rev_{h}d_%"] = edge.mean() * 100
            row[f"hit_{h}d_%"] = (edge > 0).mean() * 100
        out[name] = row
    return pd.DataFrame(out).T.round(2)


def load_events(window: int) -> pd.DataFrame:
    conn = connect()
    prices = pd.read_sql("SELECT ticker, date, close FROM prices ORDER BY ticker, date", conn)
    filings = pd.read_sql(
        "SELECT f.ticker, f.filed, e.direction FROM filing_extractions e JOIN filings f USING (accession)", conn)
    conn.close()
    frames = [events_for(g.set_index("date")["close"], filings[filings["ticker"] == t], window)
              for t, g in prices.groupby("ticker") if (filings["ticker"] == t).any()]
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cut", type=float, default=1.5)
    ap.add_argument("--window", type=int, default=20)
    ap.add_argument("--split", default="2022-01-01")
    a = ap.parse_args()
    pd.set_option("display.width", 200)
    ev = load_events(a.window)
    for name, part in (("ALL", ev), ("TRAIN <" + a.split, ev[ev["entry"] < a.split]),
                       ("TEST >=" + a.split, ev[ev["entry"] >= a.split])):
        print(f"\n== {name} | {len(part)} events | cut={a.cut} | rev = contrarian edge, positive = price reverted ==")
        print(summary(part, a.cut).to_string())
