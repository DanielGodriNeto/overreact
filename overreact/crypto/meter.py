"""Reaction meter: log returns around a timestamp from 1s bars, with no look-ahead.

A 1s bar stamped t (its open time) closes at t+1, so the price known at time T is the close of the last bar with
t + 1 <= T. Seconds without trades carry the previous close forward.
"""
import bisect
import math
import random

HORIZONS_S = (1, 3, 10, 30, 60, 300, 900, 3600)
PRE_S = (-60, -10)


def price_at(ts: list[int], closes: list[float], t: float) -> float | None:
    i = bisect.bisect_right(ts, t - 1) - 1
    return closes[i] if i >= 0 else None


def path(ts: list[int], closes: list[float], t0: float, offsets=PRE_S + HORIZONS_S) -> dict[int, float] | None:
    """ln(p(t0 + h) / p(t0)) for each offset h in seconds; None if any needed price is unknown (no earlier trade)."""
    prices = {h: price_at(ts, closes, t0 + h) for h in (0, *offsets)}
    if any(p is None for p in prices.values()):
        return None
    return {h: math.log(prices[h] / prices[0]) for h in offsets}


def cluster_ci(groups: list[list[float]], reps: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """Mean and 95% bootstrap CI, resampling whole groups (all coins of one news item move together)."""
    rng = random.Random(seed)
    flat = [x for g in groups for x in g]
    means = []
    for _ in range(reps):
        sample = [x for g in rng.choices(groups, k=len(groups)) for x in g]
        means.append(sum(sample) / len(sample))
    means.sort()
    return sum(flat) / len(flat), means[int(0.025 * reps)], means[int(0.975 * reps) - 1]
