"""D1 baseline: how long each news source takes to answer, and how late the sequential loop makes the others.

Fetches every source a few times (the same calls the ear makes, with ETag validators after the first), then
replays the ear's real schedule over a simulated hour: sequential (old loop) vs one worker per source (new loop).
Usage: python scripts/bench_ear.py [--rounds 3]
"""
import argparse
import statistics
import time

import requests

from overreact.crypto.clock import burst
from overreact.crypto.newsear import SOURCES, fetch


def measure(rounds: int) -> dict[str, list[float]]:
    http, out = requests.Session(), {name: [] for name in SOURCES}
    out["clock_burst"] = []
    for _ in range(rounds):
        for name, src in SOURCES.items():
            validators: dict = {}
            started = time.monotonic()
            try:
                fetch(http, src, validators)
            except (requests.RequestException, ValueError) as err:
                print(f"{name}: {err}")
            out[name].append(time.monotonic() - started)
        started = time.monotonic()
        burst(http)
        out["clock_burst"].append(time.monotonic() - started)
        time.sleep(2)
    return out


def replay(durations: dict[str, float], sequential: bool, hours: float = 1.0, tick: float = 0.2) -> dict[str, list[float]]:
    """Lateness = start - due time per poll, replaying the ear's schedule with fixed per-source durations."""
    jobs = {name: src.interval_s for name, src in SOURCES.items()} | {"clock_burst": 60.0}
    next_at = {name: 0.0 for name in jobs}
    busy_until = {name: 0.0 for name in jobs}
    late: dict[str, list[float]] = {name: [] for name in jobs}
    now = 0.0
    while now < hours * 3600:
        for name in [n for n, t in next_at.items() if t <= now and busy_until[n] <= now]:
            late[name].append(now - next_at[name])
            if sequential:
                now += durations[name]  # everybody else waits
                end = now
            else:
                end = now + durations[name]
            busy_until[name] = end
            next_at[name] = end + jobs[name]
        now += tick
    return late


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    measured = measure(ap.parse_args().rounds)
    print(f"{'source':18} {'median_s':>9} {'max_s':>7}")
    for name, xs in measured.items():
        print(f"{name:18} {statistics.median(xs):9.2f} {max(xs):7.2f}")
    worst = {name: max(xs) for name, xs in measured.items()}
    for label, seq in (("sequential (old)", True), ("concurrent (new)", False)):
        late = replay(worst, seq)
        p95 = {n: sorted(v)[int(0.95 * len(v)) - 1] for n, v in late.items() if n in ("upbit", "okx", "bybit")}
        print(f"{label}: p95 lateness with worst-case durations, s: " + ", ".join(f"{k} {v:.2f}" for k, v in p95.items()))


if __name__ == "__main__":
    main()
