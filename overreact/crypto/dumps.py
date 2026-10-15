"""Binance public data dumps (data.binance.vision): verified files cached under data/dumps/ mirroring the server path.

Untrusted download: sha256 checked against the .CHECKSUM file, size-capped, host pinned (HTTPS), the one expected
CSV member read by name (never extractall), parsed in memory. Spot kline timestamps are microseconds from
2025-01-01, milliseconds before.
"""
import hashlib
import io
import os
import time
import zipfile

from overreact.crypto.net import get_capped
from overreact.crypto.store import DB_PATH

ROOT = "https://data.binance.vision/data/"
CACHE = DB_PATH.parent / "dumps"
MAX_ZIP, MAX_CSV = 300_000_000, 1_500_000_000
Bar = tuple[int, float, float, float, float, int]  # t_s, close, high, low, quote volume, trades


def verify(blob: bytes, checksum: str, name: str) -> None:
    """CHECKSUM file format: '<sha256>  <file name>'."""
    digest, _, fname = checksum.strip().partition(" ")
    if fname.strip() != name or hashlib.sha256(blob).hexdigest() != digest.lower():
        raise ValueError(f"checksum mismatch for {name}")


def parse_csv(text: str) -> list[Bar]:
    """Klines of any interval: open_time, open, high, low, close, volume, close_time, quote_volume, count, ...
    Intervals without trades dropped."""
    bars = []
    for line in text.splitlines():
        f = line.split(",")
        if not f[0].isdigit():  # header line (futures files have one)
            continue
        t, n = int(f[0]), int(f[8])
        if n == 0:
            continue
        t_s = t // 1_000_000 if t > 10**14 else t // 1000  # microseconds since 2025-01-01
        bars.append((t_s, float(f[4]), float(f[2]), float(f[3]), float(f[7]), n))
    return bars


def download(rel: str) -> bool:
    """Verified zip into the cache. False = no such file (pair not trading then, or not published yet)."""
    name = rel.rsplit("/", 1)[1]
    url = ROOT + rel
    checksum = get_capped(url + ".CHECKSUM", 10_000)
    blob = get_capped(url, MAX_ZIP) if checksum else None
    if blob is None:
        return False
    verify(blob, checksum.decode(), name)
    path = CACHE / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(name + ".tmp")
    tmp.write_bytes(blob)
    os.replace(tmp, path)
    time.sleep(0.2)  # polite: one download at a time
    return True


def read_zip(blob: bytes, member: str) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        if z.getinfo(member).file_size > MAX_CSV:  # KeyError if the expected member is missing
            raise ValueError(f"{member} too large")
        return z.read(member).decode()


def csv_text(rel: str) -> str | None:
    """The CSV inside a cached-or-downloaded dump, e.g. 'futures/um/monthly/fundingRate/X/X-fundingRate-2024-01.zip'."""
    path = CACHE / rel
    if not path.exists() and not download(rel):
        return None
    name = rel.rsplit("/", 1)[1]
    return read_zip(path.read_bytes(), name.removesuffix(".zip") + ".csv")


def day_bars(sym: str, day: str, interval: str = "1s") -> list[Bar] | None:
    text = csv_text(f"spot/daily/klines/{sym}/{interval}/{sym}-{interval}-{day}.zip")
    return None if text is None else parse_csv(text)


def month_bars(sym: str, interval: str, month: str, market: str = "spot") -> list[Bar] | None:
    base = "spot" if market == "spot" else "futures/um"
    text = csv_text(f"{base}/monthly/klines/{sym}/{interval}/{sym}-{interval}-{month}.zip")
    return None if text is None else parse_csv(text)
