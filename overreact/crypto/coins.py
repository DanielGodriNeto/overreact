"""Which coins a news title mentions. Rules only (fast, no LLM): explicit patterns, cashtags, aliases, bare tickers.

bases = base assets that currently trade against USDT on Binance (from the exchangeInfo snapshot).
"""
import csv
import re
from pathlib import Path

ALIASES_FILE = Path(__file__).with_name("coins.csv")
PAREN = re.compile(r"\(([A-Z0-9]{2,12})\)")
PAIR = re.compile(r"\b([A-Z0-9]{2,12})[/-]?(?:USDT|USDC|KRW|USD)\b")
MARKETS = re.compile(r"(?:KRW|BTC|USDT)(?:\s*,\s*(?:KRW|BTC|USDT))*\s*마켓")
NAMED = re.compile(r"\b([A-Z0-9]{2,12}) \([A-Za-z][^)]*\)")  # OKX style: "MEGA (MegaETH)"
CASHTAG = re.compile(r"\$([A-Za-z][A-Za-z0-9]{1,11})\b")
WORD = re.compile(r"\b[A-Z][A-Z0-9]{2,9}\b")
STOP = {"SEC", "ETF", "ETFS", "CEO", "CFO", "USA", "USD", "USDT", "USDC", "NFT", "DAO", "DEFI", "CEX", "DEX", "IPO", "GDP",
        "CPI", "FED", "FOMC", "API", "KYC", "AML", "OTC", "ATH", "TVL", "APR", "APY", "EU", "UK", "FBI", "DOJ", "CFTC",
        "IMF", "AI", "NEW", "THE", "FOR", "AND", "NOT", "ALL", "ONE", "TOP", "BIG", "WIN", "BANK", "CRYPTO", "TRUMP"}


def load_aliases(path: Path = ALIASES_FILE) -> dict[str, str]:
    with path.open(encoding="utf-8") as f:
        return {row["name"].lower(): row["symbol"] for row in csv.DictReader(f)}


def extract(title: str, bases: set[str], aliases: dict[str, str]) -> dict[str, float]:
    """coin -> confidence. Explicit forms (pair, parentheses, cashtag) beat aliases beat bare uppercase words."""
    found: dict[str, float] = {}
    title = MARKETS.sub(" ", title)  # "(KRW, BTC, USDT 마켓)" names quote markets, not the coin (G1 audit)

    def add(coin: str, conf: float) -> None:
        found[coin] = max(found.get(coin, 0.0), conf)

    pairs = set(PAIR.findall(title))  # an explicit pair is unambiguous even for a stop word ("TRUMP/USDT")
    for coin in PAREN.findall(title) + list(pairs):
        add(coin, 1.0)
    for coin in NAMED.findall(title):
        if coin in bases:
            add(coin, 0.95)
    for coin in CASHTAG.findall(title):
        add(coin.upper(), 0.9)
    lower = title.lower()
    for name, coin in aliases.items():
        if re.search(rf"\b{re.escape(name)}\b", lower):
            add(coin, 0.8)
    for word in WORD.findall(title):
        if word in bases and word not in STOP:
            add(word, 0.6)
    return {c: v for c, v in found.items() if c not in STOP or c in pairs}
