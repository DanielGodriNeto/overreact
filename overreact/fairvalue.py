"""Fair-value band ("theoretical price") and the test: do big deviations revert?

fair  = rolling mean of log close (window days)
z     = (log close - fair) / rolling std of that deviation  -> how stretched the price is
Question: after z <= -cut (panic selling) or z >= +cut (euphoria), what is the forward return
over h days compared with an average day? Only past data feeds the band (no look-ahead).

Usage: python -m overreact.fairvalue [--window 20] [--cut 2] [--split 2022-01-01] [--cost-bps 10]
"""
import argparse

import numpy as np
import pandas as pd

from overreact.db import connect

BENCHMARKS = {"SPY", "IWM"}
HORIZONS = (1, 5, 10)


def band(close: pd.Series, window: int, k: float = 2.0) -> pd.DataFrame:
    """Theoretical price and its band; z = stretch from fair in rolling std units."""
    log_c = np.log(close)
    fair = log_c.rolling(window).mean()
    std = (log_c - fair).rolling(window).std()
    return pd.DataFrame({
        "fair": np.exp(fair),
        "upper": np.exp(fair + k * std),
        "lower": np.exp(fair - k * std),
        "z": (log_c - fair) / std,
    })


def forward_return(close: pd.Series, h: int) -> pd.Series:
    """Return from today's close to the close h days later (what a signal today would earn)."""
    return close.shift(-h) / close - 1


def news_flag(dates: pd.Index, filed: pd.Series, lookback: int = 3) -> np.ndarray:
    """True on trading day i if a hard filing was filed within the last `lookback` trading days (incl. today).
    ponytail: date-level, so a filing after today's close also flags today; use acceptance time if this matters."""
    if filed.empty:
        return np.zeros(len(dates), dtype=bool)
    days = np.asarray(dates)
    start = np.concatenate([days[:1].repeat(lookback - 1), days])[: len(days)]
    filed = np.sort(filed.to_numpy())
    return np.searchsorted(filed, days, side="right") > np.searchsorted(filed, start, side="left")


def signals(prices: pd.DataFrame, window: int, filings: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per ticker/day: z, hard-news flag and forward returns, demeaned per ticker."""
    filings = filings if filings is not None else pd.DataFrame(columns=["ticker", "filed"])
    frames = []
    for ticker, g in prices.groupby("ticker"):
        close = g.set_index("date")["close"]
        df = pd.DataFrame({"ticker": ticker, "z": band(close, window)["z"]})
        df["news"] = news_flag(close.index, filings.loc[filings["ticker"] == ticker, "filed"])
        for h in HORIZONS:
            fwd = forward_return(close, h)
            df[f"ex_{h}d"] = fwd - fwd.mean()
        frames.append(df)
    return pd.concat(frames).dropna()


def reversion_table(sig: pd.DataFrame, cut: float, cost_bps: float) -> pd.DataFrame:
    """Mean excess forward return (%) after stretched days; net_* assumes a long reversal trade (2 sides)."""
    buckets = {"panic z<=-cut": sig["z"] <= -cut, "euphoria z>=cut": sig["z"] >= cut}
    rows = {}
    for name, mask in buckets.items():
        sel = sig[mask]
        row = {"n": len(sel)}
        for h in HORIZONS:
            col = sel[f"ex_{h}d"]
            # reversal trade: buy panic, short euphoria -> flip sign so positive = reversion paid
            edge = col if name.startswith("panic") else -col
            row[f"ex_{h}d_%"] = edge.mean() * 100
            row[f"hit_{h}d_%"] = (edge > 0).mean() * 100
            row[f"net_{h}d_%"] = (edge.mean() - 2 * cost_bps / 10_000) * 100
        rows[name] = row
    return pd.DataFrame(rows).T.round(2)


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    conn = connect()
    prices = pd.read_sql("SELECT ticker, date, close FROM prices ORDER BY ticker, date", conn)
    try:
        filings = pd.read_sql("SELECT ticker, filed FROM filings", conn)
    except pd.errors.DatabaseError:  # edgar not run yet
        filings = pd.DataFrame(columns=["ticker", "filed"])
    conn.close()
    return prices, filings


def report(window: int, cut: float, split: str, cost_bps: float) -> None:
    prices, filings = load()
    sig = signals(prices, window, filings)
    small = sig[~sig["ticker"].isin(BENCHMARKS)]
    parts = {
        "TRAIN before " + split: small[small.index < split],
        "TEST from " + split: small[small.index >= split],
        "BENCHMARKS (SPY, IWM) all": sig[sig["ticker"].isin(BENCHMARKS)],
    }
    for label, part in parts.items():
        print(f"\n== {label} | window={window} cut={cut} cost={cost_bps}bps/side ==")
        print(reversion_table(part, cut, cost_bps).to_string())
    for label in list(parts)[:2]:
        part = parts[label]
        for flag, name in ((False, "NO hard news"), (True, "WITH hard news (SEC filing in last 3 days)")):
            print(f"\n== {label} | small caps, {name} ==")
            print(reversion_table(part[part["news"] == flag], cut, cost_bps).to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=20)
    ap.add_argument("--cut", type=float, default=2.0)
    ap.add_argument("--split", default="2022-01-01")
    ap.add_argument("--cost-bps", type=float, default=10)
    a = ap.parse_args()
    pd.set_option("display.width", 200)
    report(a.window, a.cut, a.split, a.cost_bps)
