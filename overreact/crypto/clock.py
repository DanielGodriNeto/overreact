"""Exchange clock: local time + offset measured against Binance /api/v3/time.

offset = server_ms - midpoint of the local request window; the min-RTT sample of a burst is the most accurate,
and the median of the last 10 bursts smooths outliers. Resolution is +/- RTT/2.
Usage: python -m overreact.crypto.clock [--bursts 10]   (measures and stores in clock_offset)
"""
import argparse
import statistics
import time
from collections import deque

import requests

from overreact.crypto.store import connect

TIME_URL = "https://api.binance.com/api/v3/time"


def local_ms() -> float:
    return time.time_ns() / 1e6


def best_sample(samples: list[tuple[float, int, float]]) -> tuple[float, float]:
    """samples: (local_before_ms, server_ms, local_after_ms). Returns (offset_ms, rtt_ms) of the min-RTT sample."""
    before, server, after = min(samples, key=lambda s: s[2] - s[0])
    return server - (before + after) / 2, after - before


def burst(session: requests.Session, n: int = 5) -> tuple[float, float]:
    samples = []
    for _ in range(n):
        before = local_ms()
        server = session.get(TIME_URL, timeout=5).json()["serverTime"]
        samples.append((before, int(server), local_ms()))
    return best_sample(samples)


class ExchangeClock:
    def __init__(self, keep: int = 10):
        self.offsets: deque[float] = deque(maxlen=keep)

    def add(self, offset_ms: float) -> None:
        self.offsets.append(offset_ms)

    @property
    def offset_ms(self) -> float:
        return statistics.median(self.offsets) if self.offsets else 0.0

    def now_ms(self) -> int:
        return int(local_ms() + self.offset_ms)


def measure(bursts: int) -> None:
    conn, session, clock = connect(), requests.Session(), ExchangeClock()
    for _ in range(bursts):
        offset, rtt = burst(session)
        clock.add(offset)
        conn.execute("INSERT OR REPLACE INTO clock_offset VALUES (?,?,?)", (int(local_ms()), offset, rtt))
        conn.commit()
        print(f"offset {offset:8.1f} ms  rtt {rtt:6.1f} ms")
        time.sleep(1)
    print(f"median offset {clock.offset_ms:.1f} ms")
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bursts", type=int, default=10)
    measure(ap.parse_args().bursts)
