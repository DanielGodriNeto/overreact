"""1s bars -> 1m bars (kept forever); live 1s bars and 5s spreads deleted after their retention window.

P4 adds the rule that event and placebo windows are never pruned (src='dump' rows are never touched here).
"""
import sqlite3

BARS_KEEP_DAYS, SPREAD_KEEP_DAYS = 14, 30
ROLLUP = """
WITH b AS (SELECT sym, t_s, t_s / 60 * 60 AS m, c, h, l, qv, n FROM bars_1s WHERE t_s >= ? AND t_s < ?),
     first AS (SELECT sym, m, min(t_s), c AS o FROM b GROUP BY sym, m),
     last AS (SELECT sym, m, max(t_s), c FROM b GROUP BY sym, m),
     agg AS (SELECT sym, m, max(h) AS h, min(l) AS l, sum(qv) AS qv, sum(n) AS n FROM b GROUP BY sym, m)
INSERT OR REPLACE INTO bars_1m
SELECT agg.sym, agg.m, first.o, agg.h, agg.l, last.c, agg.qv, agg.n
FROM agg JOIN first USING (sym, m) JOIN last USING (sym, m)
"""


def rollup(conn: sqlite3.Connection, until_s: int) -> None:
    """Roll every whole minute before until_s that is newer than the last rolled minute (bare-column min/max trick)."""
    start = conn.execute("SELECT coalesce(max(t_m) + 60, 0) FROM bars_1m").fetchone()[0]
    conn.execute(ROLLUP, (start, until_s // 60 * 60))


def prune(conn: sqlite3.Connection, now_s: int) -> None:
    conn.execute("DELETE FROM bars_1s WHERE t_s < ? AND src != 'dump'", (now_s - BARS_KEEP_DAYS * 86400,))
    conn.execute("DELETE FROM spread_5s WHERE t_s < ?", (now_s - SPREAD_KEEP_DAYS * 86400,))
