import hashlib
import io
import math
import zipfile

import pytest

from overreact.crypto.dumps import parse_csv, read_zip, verify
from overreact.crypto.history import news_type
from overreact.crypto.meter import cluster_ci, path, price_at


def test_price_known_only_after_bar_closes():
    ts, closes = [100, 101, 105], [10.0, 11.0, 12.0]
    assert price_at(ts, closes, 100.5) is None  # bar 100 closes at 101
    assert price_at(ts, closes, 101) == 10.0
    assert price_at(ts, closes, 104) == 11.0  # 102-104 no trades: carried forward
    assert price_at(ts, closes, 106) == 12.0


def test_injected_jump_gives_exact_returns():
    ts = list(range(0, 4000))
    closes = [100.0 if t < 1000 else 101.0 for t in ts]  # +1% in the bar that opens at t=1000
    r = path(ts, closes, t0=1000.0)
    assert r[-60] == 0 and r[-10] == 0  # no leak before t0
    assert r[1] == pytest.approx(math.log(1.01))  # visible once bar 1000 closed at 1001
    assert r[3600] == pytest.approx(math.log(1.01))
    assert path(ts, closes, t0=0.5) is None  # nothing known before the first close
    assert path(ts, closes, t0=30.0) is None  # t0-60 precedes the first trade: unknown, not a crash


def test_cluster_ci_brackets_mean():
    mean, lo, hi = cluster_ci([[1.0, 1.0], [3.0], [2.0]], reps=500)
    assert mean == pytest.approx(1.75) and lo <= mean <= hi


def test_dump_csv_microseconds_header_and_empty_seconds():
    text = ("open_time,open,high,low,close,volume,close_time,quote_volume,count,a,b,c\n"
            "1735689600000000,1,2,0.5,1.5,3,1735689600999999,4.5,7,0,0,0\n"
            "1735689601000000,1.5,1.5,1.5,1.5,0,1735689601999999,0,0,0,0,0\n"
            "1704067200000,1,1,1,1,1,1704067200999,1,1,0,0,0\n")
    assert parse_csv(text) == [(1735689600, 1.5, 2.0, 0.5, 4.5, 7), (1704067200, 1.0, 1.0, 1.0, 1.0, 1)]


def test_checksum_and_member_name_enforced():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("X-1s-2026-01-01.csv", "1,1,1,1,1,1,1,1,1,0,0,0")
    blob = buf.getvalue()
    good = f"{hashlib.sha256(blob).hexdigest()}  X-1s-2026-01-01.zip"
    verify(blob, good, "X-1s-2026-01-01.zip")
    with pytest.raises(ValueError):
        verify(blob + b"x", good, "X-1s-2026-01-01.zip")
    with pytest.raises(ValueError):
        verify(blob, good, "../evil.zip")
    with pytest.raises(KeyError):
        read_zip(blob, "../../etc/passwd")
    assert read_zip(blob, "X-1s-2026-01-01.csv").startswith("1,")


def test_news_type():
    assert news_type("OKX to delist XYZ spot trading pairs") == "delisting"
    assert news_type("New listing: XYZUSDT Perpetual") == "listing"
    assert news_type("깃코인(GTC) KRW, USDT 마켓 디지털 자산 추가") == "listing"
    assert news_type("블라스트(BLAST) 거래지원 종료 안내") == "delisting"
    assert news_type("Maintenance notice") is None
