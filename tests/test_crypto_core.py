from overreact.crypto import logsafe
from overreact.crypto.clock import ExchangeClock, best_sample
from overreact.crypto.store import connect


def test_best_sample_uses_min_rtt():
    # second sample: rtt 20 ms, server 1000 vs midpoint 990 -> offset +10
    offset, rtt = best_sample([(0, 500, 300), (980, 1000, 1000), (2000, 2600, 2400)])
    assert (offset, rtt) == (10, 20)


def test_clock_median():
    clock = ExchangeClock(keep=3)
    for o in (5, 100, 7, 9):  # oldest (5) falls out
        clock.add(o)
    assert clock.offset_ms == 9


def test_store_upsert_dedups(tmp_path):
    conn = connect(tmp_path / "c.db")
    for c in (1.0, 2.0):  # same second arrives twice (reconnect overlap)
        conn.execute("INSERT OR REPLACE INTO bars_1s VALUES ('BTCUSDT', 1, ?, 2, 1, 10, 3, 'live')", (c,))
    assert conn.execute("SELECT count(*), max(c) FROM bars_1s").fetchone() == (1, 2.0)
    conn.close()


def test_log_never_contains_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("BINANCE_TESTNET_API_SECRET", "s3cr3tvalue")
    log = logsafe.setup("t", tmp_path)
    log.info("sent key %s url /order?x=1&signature=abcdef123", "s3cr3tvalue")
    for h in list(log.handlers):
        h.close()
        log.removeHandler(h)
    text = (tmp_path / "crypto_t.log").read_text()
    assert "s3cr3tvalue" not in text and "abcdef123" not in text and "***" in text


def test_clip_strips_control_chars():
    assert logsafe.clip("a\nb\x1b[31m" + "x" * 300) == "a b [31m" + "x" * 192
