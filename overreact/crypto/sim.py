"""Execution simulator (G0 in LAB_crypto.md): pessimistic fills on 1s bars, latency sweeps, net log returns.

A 1s bar has no order book, so fills are the WORST trade of the second the order lands in and the next one
(buy = highest high, sell = lowest low), plus a slippage haircut and taker fees. No trade in those seconds = the
last known close (no look-ahead: only bars closed by then). Results are an upper bound for thin books.
"""
import bisect
import math

from overreact.crypto.dumps import Bar
from overreact.crypto.meter import price_at

FEE = 0.001  # Binance spot taker per side


def worst_fill(bars: list[Bar], t: float, side: str) -> float | None:
    ts = [b[0] for b in bars]
    s = math.floor(t)
    i = bisect.bisect_left(ts, s)
    hits = [b for b in bars[i:i + 2] if b[0] <= s + 1]
    if hits:
        return max(b[2] for b in hits) if side == "buy" else min(b[3] for b in hits)
    return price_at(ts, [b[1] for b in bars], t)


def trade(bars: list[Bar], t_in: float, t_out: float, slip: float, fee: float = FEE) -> float | None:
    """Net log return of a long bought at t_in and sold at t_out. None = no price known at entry or exit."""
    buy, sell = worst_fill(bars, t_in, "buy"), worst_fill(bars, t_out, "sell")
    if buy is None or sell is None:
        return None
    return math.log(sell * (1 - slip) * (1 - fee) / (buy * (1 + slip) * (1 + fee)))


def onset(bars: list[Bar], t0: float, thresh: float = 0.02, lo: int = -120, hi: int = 30) -> int | None:
    """Seconds from t0 to the open of the first bar whose close is >= thresh away from the price at t0+lo.
    Negative = the price moved before the announcement time we have (leak, or a late timestamp)."""
    ref = price_at([b[0] for b in bars], [b[1] for b in bars], t0 + lo)
    if ref is None:
        return None
    for b in bars:
        if t0 + lo <= b[0] < t0 + hi and abs(math.log(b[1] / ref)) >= thresh:
            return int(b[0] - t0)
    return None
