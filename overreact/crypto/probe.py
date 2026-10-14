"""Hit every crypto data source once from this PC: HTTP status, round trip, key fields, robots.txt verdict.

Usage: python -m overreact.crypto.probe [--save data/probe]   (raw bodies saved there for test fixtures)
No keys, no auth: public endpoints only.
"""
import argparse
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
ENDPOINTS = {
    "binance_time": "https://api.binance.com/api/v3/time",
    "binance_klines_1s": "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1s&limit=3",
    "binance_book_all": "https://api.binance.com/api/v3/ticker/bookTicker",
    "binance_exchangeinfo": "https://api.binance.com/api/v3/exchangeInfo?symbol=BTCUSDT",
    "binance_fut_oi": "https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT",
    "binance_fut_premium": "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT",
    "vision_1s_checksum": f"https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1s/BTCUSDT-1s-{YESTERDAY}.zip.CHECKSUM",
    "bybit_ann": "https://api.bybit.com/v5/announcements/index?locale=en-US&type=new_crypto&limit=5",
    "okx_ann": "https://www.okx.com/api/v5/support/announcements?annType=announcements-new-listings",
    "okx_ann_types": "https://www.okx.com/api/v5/support/announcement-types",
    "upbit_ann": "https://api-manager.upbit.com/api/v1/announcements?os=web&page=1&per_page=5&category=trade",
    "coinbase_status": "https://status.coinbase.com/api/v2/summary.json",
    "coinbase_products": "https://api.exchange.coinbase.com/products",
    "rss_coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss",
    "rss_cointelegraph": "https://cointelegraph.com/rss",
    "rss_decrypt": "https://decrypt.co/feed",
    "rss_theblock": "https://www.theblock.co/rss.xml",
}
UA = "overreact-research/0.1 (personal, non-commercial)"


def robots_allows(url: str, cache: dict[str, RobotFileParser | None]) -> str:
    host = urlsplit(url).netloc
    if host not in cache:
        rp = RobotFileParser()
        try:
            resp = requests.get(f"https://{host}/robots.txt", timeout=10, headers={"User-Agent": UA})
            rp.parse(resp.text.splitlines() if resp.ok else [])
            cache[host] = rp
        except requests.RequestException:
            cache[host] = None
    rp = cache[host]
    if rp is None:
        return "no-robots"
    return "allow" if rp.can_fetch(UA, url) else "DENY"


def probe(save: Path | None) -> None:
    robots: dict[str, RobotFileParser | None] = {}
    print(f"{'name':22} {'status':>6} {'ms':>6} {'bytes':>8} robots  head")
    for name, url in ENDPOINTS.items():
        started = time.perf_counter()
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": UA})
            status, body = resp.status_code, resp.text
        except requests.RequestException as err:
            status, body = 0, f"{type(err).__name__}"
        ms = (time.perf_counter() - started) * 1000
        head = " ".join(body[:110].split())
        print(f"{name:22} {status:>6} {ms:6.0f} {len(body):>8} {robots_allows(url, robots):7} {head}")
        if save and status == 200:
            save.mkdir(parents=True, exist_ok=True)
            (save / f"{name}.txt").write_text(body[:200_000], encoding="utf-8")
        time.sleep(0.5)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", type=Path)
    probe(ap.parse_args().save)
