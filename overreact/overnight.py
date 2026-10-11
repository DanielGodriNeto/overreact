"""Backtest the overnight anomaly: buy at close, sell at next open, vs buy & hold and intraday.

Usage: python -m overreact.overnight [--cost-bps 10] [--since 2016-01-01]
cost-bps is charged per side (spread + slippage); overnight trades twice per day.
"""
import argparse

import pandas as pd

from overreact.db import connect


def split_returns(df: pd.DataFrame) -> pd.DataFrame:
    """df: one ticker, columns open/close, sorted by date. Returns daily overnight/intraday/hold returns."""
    prev_close = df["close"].shift(1)
    out = pd.DataFrame({
        "overnight": df["open"] / prev_close - 1,
        "intraday": df["close"] / df["open"] - 1,
        "hold": df["close"] / prev_close - 1,
    })
    return out.dropna()


def summarize(rets: pd.DataFrame, cost_bps: float) -> dict[str, float]:
    """Total compounded return (%) of each strategy; overnight_net pays 2 sides every day."""
    cost = 2 * cost_bps / 10_000
    growth = (1 + rets).prod()
    net = (1 + rets["overnight"] - cost).prod()
    return {
        "days": len(rets),
        "hold_%": (growth["hold"] - 1) * 100,
        "overnight_gross_%": (growth["overnight"] - 1) * 100,
        "overnight_net_%": (net - 1) * 100,
        "intraday_%": (growth["intraday"] - 1) * 100,
        "breakeven_bps": rets["overnight"].mean() / 2 * 10_000,
    }


def run(cost_bps: float, since: str) -> pd.DataFrame:
    conn = connect()
    prices = pd.read_sql(
        "SELECT ticker, date, open, close FROM prices WHERE date >= ? ORDER BY ticker, date",
        conn, params=(since,),
    )
    conn.close()
    table = {t: summarize(split_returns(g), cost_bps) for t, g in prices.groupby("ticker")}
    return pd.DataFrame(table).T.round(1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cost-bps", type=float, default=10)
    ap.add_argument("--since", default="2016-01-01")
    args = ap.parse_args()
    pd.set_option("display.width", 140)
    print(run(args.cost_bps, args.since).sort_values("overnight_net_%", ascending=False))
