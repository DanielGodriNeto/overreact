"""SQLite store for the crypto subsystem: its own file so heavy writes never lock the equity DB."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "crypto.db"
SCHEMA = """
CREATE TABLE IF NOT EXISTS bars_1s (sym TEXT, t_s INTEGER, c REAL, h REAL, l REAL, qv REAL, n INTEGER, src TEXT,
    PRIMARY KEY (sym, t_s)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS bars_1m (sym TEXT, t_m INTEGER, o REAL, h REAL, l REAL, c REAL, qv REAL, n INTEGER,
    PRIMARY KEY (sym, t_m)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS spread_5s (sym TEXT, t_s INTEGER, bid REAL, ask REAL, PRIMARY KEY (sym, t_s)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS spread_day (sym TEXT, day TEXT, median_bps REAL, p90_bps REAL, PRIMARY KEY (sym, day));
CREATE TABLE IF NOT EXISTS watch (sym TEXT, from_ms INTEGER, until_ms INTEGER, why TEXT, PRIMARY KEY (sym, from_ms));
CREATE TABLE IF NOT EXISTS spread_evt (sym TEXT, t_ms INTEGER, bid REAL, ask REAL, bq REAL, aq REAL, spread_src TEXT,
    PRIMARY KEY (sym, t_ms)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS gaps (proc TEXT, sym TEXT, t_from INTEGER, t_to INTEGER, cause TEXT, filled_by TEXT);
CREATE TABLE IF NOT EXISTS heartbeat (proc TEXT PRIMARY KEY, ts_ms INTEGER, info TEXT);
CREATE TABLE IF NOT EXISTS clock_offset (ts_ms INTEGER PRIMARY KEY, offset_ms REAL, rtt_ms REAL);
CREATE TABLE IF NOT EXISTS latency_probe (ts_ms INTEGER, sym TEXT, recv_minus_e_ms REAL);
CREATE TABLE IF NOT EXISTS liq (venue TEXT, symbol TEXT, side TEXT, qty REAL, price REAL, avg_price REAL,
    trade_ms INTEGER, recv_ms INTEGER, UNIQUE (venue, symbol, side, trade_ms, qty));
CREATE TABLE IF NOT EXISTS funding (sym TEXT, ts_ms INTEGER, rate REAL, next_ms INTEGER, PRIMARY KEY (sym, ts_ms));
CREATE TABLE IF NOT EXISTS oi (sym TEXT, ts_ms INTEGER, oi REAL, PRIMARY KEY (sym, ts_ms));
CREATE TABLE IF NOT EXISTS cnews (id INTEGER PRIMARY KEY, source TEXT NOT NULL, ext_id TEXT NOT NULL, url TEXT,
    title TEXT, body TEXT, lang TEXT, src_cat TEXT, src_ts_ms INTEGER, src_ts_prec TEXT, recv_ms INTEGER NOT NULL,
    offset_ms REAL, hash TEXT, dup_of INTEGER, backlog INTEGER DEFAULT 0, src_skew INTEGER DEFAULT 0,
    UNIQUE (source, ext_id));
CREATE TABLE IF NOT EXISTS cnews_rev (news_id INTEGER, recv_ms INTEGER, title TEXT, body TEXT, hash TEXT);
CREATE TABLE IF NOT EXISTS cnews_coins (news_id INTEGER, coin TEXT, method TEXT, conf REAL, PRIMARY KEY (news_id, coin));
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    return conn
