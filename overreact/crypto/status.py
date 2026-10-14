"""Health of the crypto processes: heartbeat age, gaps, rows in the last hour, BTC coverage, clock, disk.

Usage: python -m overreact.crypto.status
"""
import shutil
import time

import requests

from overreact.crypto.store import DB_PATH, connect

KLINES = "https://api.binance.com/api/v3/klines"
STALE_S = 60
RECENT = {  # static SQL per table: no identifiers built at runtime
    "bars_1s": "SELECT count(*) FROM bars_1s WHERE t_s * 1000 > ?",
    "spread_5s": "SELECT count(*) FROM spread_5s WHERE t_s * 1000 > ?",
    "spread_evt": "SELECT count(*) FROM spread_evt WHERE t_ms > ?",
    "liq": "SELECT count(*) FROM liq WHERE recv_ms > ?",
    "funding": "SELECT count(*) FROM funding WHERE ts_ms > ?",
    "oi": "SELECT count(*) FROM oi WHERE ts_ms > ?",
    "cnews": "SELECT count(*) FROM cnews WHERE recv_ms > ?",
}


def coverage(conn, sym: str, start_ms: int, end_ms: int) -> str:
    """Seconds that had trades (per Binance REST) but are missing in bars_1s. Empty seconds are normal, even for BTC."""
    try:
        klines = requests.get(KLINES, timeout=10, params={"symbol": sym, "interval": "1s", "startTime": start_ms,
                                                          "endTime": end_ms, "limit": 1000}).json()
    except (requests.RequestException, ValueError) as err:
        return f"coverage {sym}: REST failed ({err})"
    traded = {k[0] // 1000 for k in klines if int(k[8]) > 0}
    have = {t for (t,) in conn.execute("SELECT t_s FROM bars_1s WHERE sym = ? AND t_s BETWEEN ? AND ?",
                                       (sym, start_ms // 1000, end_ms // 1000))}
    missing = len(traded - have)
    return f"coverage {sym} last ~16 min: {1 - missing / max(1, len(traded)):.2%} of {len(traded)} traded seconds"


def main() -> None:
    conn = connect()
    now = time.time() * 1000
    for proc, ts, info in conn.execute("SELECT proc, ts_ms, info FROM heartbeat"):
        age = (now - ts) / 1000
        print(f"heartbeat {proc:5} {age:7.0f} s ago {'STALE' if age > STALE_S else 'ok':5} {info}")
    for proc, cause, n, secs, filled in conn.execute(
            "SELECT proc, cause, count(*), sum(t_to - t_from) / 1000.0, group_concat(DISTINCT filled_by) FROM gaps "
            "WHERE t_to > ? GROUP BY proc, cause", (now - 86_400_000,)):
        print(f"gaps 24h  {proc:5} {cause:10} n={n} total={secs:.0f} s filled_by={filled}")
    for table, sql in RECENT.items():
        n = conn.execute(sql, (now - 3_600_000,)).fetchone()[0]
        print(f"rows 1h   {table:12} {n}")
    print(coverage(conn, "BTCUSDT", int(now) - 1_020_000, int(now) - 20_000))
    row = conn.execute("SELECT offset_ms, rtt_ms FROM clock_offset ORDER BY ts_ms DESC LIMIT 1").fetchone()
    if row:
        print(f"clock offset {row[0]:.1f} ms rtt {row[1]:.0f} ms{'  WARN: run w32tm /resync' if abs(row[0]) > 500 else ''}")
    free_gb = shutil.disk_usage(DB_PATH.parent).free / 1e9
    size_mb = sum(p.stat().st_size for p in DB_PATH.parent.glob("crypto.db*")) / 1e6
    print(f"db {size_mb:.1f} MB, disk free {free_gb:.0f} GB{'  WARN: < 10 GB' if free_gb < 10 else ''}")


if __name__ == "__main__":
    main()
