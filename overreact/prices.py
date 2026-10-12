"""Download daily OHLCV for the ticker universe into SQLite.

Usage: python -m overreact.prices [--period 10y] [--tickers tickers_train.txt]
"""
import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf

from overreact.db import connect

ROOT = Path(__file__).resolve().parent.parent
TICKERS_FILE = ROOT / "tickers.txt"          # trading universe (news feeds per ticker)
TRAIN_TICKERS_FILE = ROOT / "tickers_train.txt"  # bigger universe, only for training data


def load_tickers(path: Path = TICKERS_FILE) -> list[str]:
    lines = (line.split("#")[0].strip().upper() for line in path.read_text().splitlines())
    return [t for t in lines if t]


def to_rows(ticker: str, df: pd.DataFrame) -> list[tuple]:
    df = df.dropna(subset=["Open", "Close"])
    return [
        (ticker, idx.strftime("%Y-%m-%d"), r.Open, r.High, r.Low, r.Close, 0 if pd.isna(r.Volume) else int(r.Volume))
        for idx, r in df.iterrows()
    ]


def update(period: str, tickers: Path = TICKERS_FILE) -> None:
    conn = connect()
    have = {r[0] for r in conn.execute("SELECT DISTINCT ticker FROM prices")} if tickers != TICKERS_FILE else set()
    for ticker in load_tickers(tickers):
        if ticker in have:  # big universe: only fill missing tickers; daily refresh uses tickers.txt
            continue
        # auto_adjust keeps open/close ratios consistent across splits and dividends
        try:
            df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        except Exception as err:  # yfinance raises many types; one bad ticker must not stop the run
            print(f"{ticker}: {err}")
            continue
        if df.empty:
            print(f"{ticker}: no data, skipped")
            continue
        conn.executemany("INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?)", to_rows(ticker, df))
        conn.commit()
        print(f"{ticker}: {len(df)} days")
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="10y")
    ap.add_argument("--tickers", type=Path, default=TICKERS_FILE)
    a = ap.parse_args()
    update(a.period, a.tickers)
