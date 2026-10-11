"""Download daily OHLCV for the ticker universe into SQLite.

Usage: python -m overreact.prices [--period 10y]
"""
import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf

from overreact.db import connect

TICKERS_FILE = Path(__file__).resolve().parent.parent / "tickers.txt"


def load_tickers(path: Path = TICKERS_FILE) -> list[str]:
    lines = (line.split("#")[0].strip().upper() for line in path.read_text().splitlines())
    return [t for t in lines if t]


def to_rows(ticker: str, df: pd.DataFrame) -> list[tuple]:
    df = df.dropna(subset=["Open", "Close"])
    return [
        (ticker, idx.strftime("%Y-%m-%d"), r.Open, r.High, r.Low, r.Close, int(r.Volume))
        for idx, r in df.iterrows()
    ]


def update(period: str) -> None:
    conn = connect()
    for ticker in load_tickers():
        # auto_adjust keeps open/close ratios consistent across splits and dividends
        df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
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
    update(ap.parse_args().period)
