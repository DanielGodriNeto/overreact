from overreact.crypto import sources
from overreact.crypto.coins import extract, load_aliases
from overreact.crypto.net import next_delay
from overreact.crypto.newsear import insert_news, usdt_bases
from overreact.crypto.store import connect

BYBIT = {"result": {"list": [{"title": "New listing: XYZUSDT", "description": "<p>Spot</p>", "type": {"key": "new_crypto"},
                              "url": "https://announcements.bybit.com/a/", "publishTime": 1791878804000}]}}
OKX = {"data": [{"details": [{"annType": "announcements-new-listings", "title": "OKX to list CT/USDT (Concrete)",
                              "url": "https://www.okx.com/pt-br/help/okx-to-list-ct-usdt/", "pTime": "1790740812658",
                              "businessPTime": "1790740800000"}], "totalPage": 1}]}
UPBIT = {"data": {"notices": [{"listed_at": "2026-10-14T18:00:00+09:00", "first_listed_at": "2026-10-14T16:00:41+09:00",
                               "id": 6658, "title": "깃코인(GTC) KRW, USDT 마켓 디지털 자산 추가", "category": "거래"}]}}
RSS = """<?xml version="1.0"?><rss version="2.0"><channel><item><title>Solana jumps</title>
<link>https://x.test/a</link><guid>g1</guid><pubDate>Wed, 14 Oct 2026 20:56:22 +0000</pubDate>
<description><![CDATA[<p>Big &amp; fast</p>]]></description></item></channel></rss>"""


def test_parsers_map_fields_and_timestamps():
    b = sources.bybit(BYBIT)[0]
    assert (b.src_ts_ms, b.src_ts_prec, b.src_cat, b.body) == (1791878804000, "s", "new_crypto", "Spot")
    o = sources.okx(OKX)[0]
    assert (o.src_ts_ms, o.src_ts_prec, o.ext_id) == (1790740812658, "ms", "okx-to-list-ct-usdt")  # pTime, not business
    u = sources.upbit(UPBIT)[0]
    assert (u.src_ts_ms, u.src_ts_prec, u.lang) == (1791961241000, "s", "ko")  # first_listed_at 07:00:41 UTC
    r = sources.rss("cointelegraph", RSS.encode())[0]
    assert (r.ext_id, r.src_ts_ms, r.body) == ("g1", 1792011382000, "Big & fast")


def test_symbol_diff_new_and_changed():
    old = {"AUSDT": "TRADING|A|USDT", "BUSDT": "BREAK|B|USDT"}
    new = {"AUSDT": "TRADING|A|USDT", "BUSDT": "TRADING|B|USDT", "CUSDT": "BREAK|C|USDT"}
    items = sources.symbol_diff("binance_symbols", old, new)
    assert [(i.ext_id, i.src_cat, i.src_ts_prec) for i in items] == [
        ("BUSDT:TRADING|B|USDT", "status_change", "none"), ("CUSDT:BREAK|C|USDT", "new_symbol", "none")]
    assert usdt_bases(new) == {"A", "B"}


def test_coin_extraction():
    aliases, bases = load_aliases(), {"BTC", "ETH", "SOL", "GTC", "AI", "XYZ"}
    assert extract("깃코인(GTC) KRW, USDT 마켓", bases, aliases) == {"GTC": 1.0}
    assert set(extract("Bitcoin and SOL rally as SEC delays ETF; AI tokens flat", bases, aliases)) == {"BTC", "SOL"}
    assert extract("New listing: XYZUSDT on Bybit", bases, aliases) == {"XYZ": 1.0}
    assert extract("$pepe pumps", bases, aliases) == {"PEPE": 0.9}


def test_insert_dedup_revision_keeps_original_times(tmp_path):
    conn = connect(tmp_path / "c.db")
    item = sources.okx(OKX)[0]
    first = insert_news(conn, item, recv_ms=1790740813000, offset_ms=95.0, backlog=False)
    assert first is not None
    assert insert_news(conn, item, 1790740818000, 95.0, False) is None  # same poll result again
    edited = item._replace(title=item.title + " (updated)")
    for recv in (1790740900000, 1790740905000):
        assert insert_news(conn, edited, recv, 95.0, False) is None
    assert conn.execute("SELECT count(*) FROM cnews").fetchone() == (1,)
    assert conn.execute("SELECT count(*), min(recv_ms) FROM cnews_rev").fetchone() == (1, 1790740900000)
    assert conn.execute("SELECT recv_ms, src_ts_ms FROM cnews").fetchone() == (1790740813000, 1790740812658)


def test_skew_flag_when_received_before_publication(tmp_path):
    conn = connect(tmp_path / "c.db")
    item = sources.okx(OKX)[0]
    insert_news(conn, item, recv_ms=item.src_ts_ms - 2000, offset_ms=0.0, backlog=True)
    assert conn.execute("SELECT src_skew, backlog FROM cnews").fetchone() == (1, 1)


def test_backoff():
    assert next_delay(5, 0, False, None) == 5
    assert next_delay(5, 2, False, None) == 20
    assert next_delay(5, 1, True, 120) == 120
    assert next_delay(5, 2, True, None) == 120
    assert next_delay(5, 3, True, None) == 900


def test_rss_never_fetches_a_url_body(monkeypatch):
    import urllib.request
    def boom(*a, **k):
        raise AssertionError("feedparser tried to open a URL")
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", boom)
    assert sources.rss("x", b"http://127.0.0.1:9/probe") == []


def test_slow_source_does_not_delay_the_others(monkeypatch, tmp_path):
    import logging
    import time

    from overreact.crypto import newsear

    def fake_fetch(http, src, validators):
        if src is newsear.SOURCES["bybit"]:
            time.sleep(1.0)  # a read timeout on one host
        return None  # 304: nothing new

    monkeypatch.setattr(newsear, "fetch", fake_fetch)
    ear = newsear.Ear(connect(tmp_path / "c.db"), logging.getLogger("test"), None)
    started = time.monotonic()
    while time.monotonic() - started < 0.3:
        ear.step()
        time.sleep(0.01)
    assert set(ear.inflight) == {"bybit"}  # still waiting on the slow one
    assert all(ear.next_at[n] > started for n in newsear.SOURCES if n != "bybit")  # every other source already polled
    ear.pool.shutdown(wait=True)
