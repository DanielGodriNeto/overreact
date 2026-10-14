import logging

import pytest

from overreact.crypto import retention
from overreact.crypto.recorder import Recorder, num, parse_kline, parse_liq, spread_stats, watch_messages
from overreact.crypto.store import connect


def kline(closed=True, n=5, c="100.5"):
    return {"e": "kline", "E": 2_000, "s": "BTCUSDT", "k": {"t": 1_000, "s": "BTCUSDT", "c": c, "h": "101", "l": "99",
                                                            "q": "1234.5", "n": n, "x": closed}}


def test_kline_closed_only_and_skips_empty_seconds():
    assert parse_kline(kline()) == ("BTCUSDT", 1, 100.5, 101.0, 99.0, 1234.5, 5, "live")
    assert parse_kline(kline(closed=False)) is None
    assert parse_kline(kline(n=0)) is None


def test_num_rejects_garbage():
    for bad in ("nan", "inf", "0", "-1"):
        with pytest.raises(ValueError):
            num(bad)
    assert num("-0.0001", positive=False) == -0.0001  # funding rates can be negative


def test_liq_row():
    d = {"e": "forceOrder", "o": {"s": "ETHUSDT", "S": "SELL", "q": "2", "p": "2400", "ap": "2399.5", "T": 77}}
    assert parse_liq(d, 80) == ("binance_um", "ETHUSDT", "SELL", 2.0, 2400.0, 2399.5, 77, 80)


def test_watch_messages_diff():
    msgs = watch_messages({"a@bookTicker", "b@bookTicker"}, {"b@bookTicker", "c@bookTicker"}, 7)
    assert msgs == [{"method": "SUBSCRIBE", "params": ["c@bookTicker"], "id": 7},
                    {"method": "UNSUBSCRIBE", "params": ["a@bookTicker"], "id": 8}]
    assert watch_messages({"x"}, {"x"}, 1) == []


def test_handlers_buffer_rows_and_dedup_book(tmp_path):
    rec = Recorder(["BTCUSDT"], logging.getLogger("t"), connect(tmp_path / "c.db"))
    rec.on_spot({"stream": "btcusdt@kline_1s", "data": kline()}, 60_000)
    book = {"s": "BTCUSDT", "b": "100", "a": "101", "B": "1", "A": "2"}
    for t, qty in ((1, "1"), (2, "5"), (3, "5")):  # second/third update change qty only -> not stored
        rec.on_spot({"stream": "btcusdt@bookTicker", "data": book | {"B": qty}}, t)
    rec.on_spot({"result": None, "id": 1}, 4)  # subscribe ack ignored
    assert len(rec.buf["bars_1s"]) == 1 and len(rec.buf["spread_evt"]) == 1
    assert rec.buf["latency_probe"] == [(60_000, "BTCUSDT", 58_000)]
    rec.flush()
    assert rec.conn.execute("SELECT count(*) FROM bars_1s").fetchone() == (1,)
    assert all(not rows for rows in rec.buf.values())


def test_spread_stats():
    med, p90 = spread_stats([float(x) for x in range(1, 11)])
    assert (med, p90) == (6.0, 9.0)


def test_rollup_and_prune(tmp_path):
    conn = connect(tmp_path / "c.db")
    rows = [("BTCUSDT", 60, 10.0, 11.0, 9.0, 1.0, 1, "live"), ("BTCUSDT", 90, 12.0, 13.0, 8.0, 2.0, 2, "live"),
            ("BTCUSDT", 130, 14.0, 14.0, 14.0, 1.0, 1, "live"), ("BTCUSDT", 5, 1.0, 1.0, 1.0, 1.0, 1, "dump")]
    conn.executemany("INSERT INTO bars_1s VALUES (?,?,?,?,?,?,?,?)", rows)
    retention.rollup(conn, until_s=125)  # minute 120 is still open -> not rolled
    assert conn.execute("SELECT * FROM bars_1m WHERE t_m = 60").fetchone() == ("BTCUSDT", 60, 10.0, 13.0, 8.0, 12.0, 3.0, 3)
    assert conn.execute("SELECT count(*) FROM bars_1m WHERE t_m = 120").fetchone() == (0,)
    retention.prune(conn, now_s=100 + retention.BARS_KEEP_DAYS * 86400)
    assert conn.execute("SELECT t_s FROM bars_1s ORDER BY t_s").fetchall() == [(5,), (130,)]  # dump kept, old live gone
