import math

import numpy as np
import pandas as pd

from overreact.crypto import lab


def test_cascade_needs_price_drop_and_open_interest_drop(monkeypatch):
    ts = np.arange(0, 7200, 60, dtype=np.int64)
    cl = np.where(ts < 3000, 100.0, 95.0)  # -5% at minute 50
    monkeypatch.setattr(lab.OpenInterest, "at", lambda self, t: 100.0 if t < 3000 else 96.0)  # -4% OI
    assert lab.cascade_events("X", ts, cl) == [3060.0]  # first bar close after the drop; then 6 h cooldown
    monkeypatch.setattr(lab.OpenInterest, "at", lambda self, t: 100.0)  # price fell but OI flat: not a cascade
    assert lab.cascade_events("X", ts, cl) == []


def test_funding_events_threshold_and_no_overlap(monkeypatch):
    csv = "calc_time,funding_interval_hours,last_funding_rate\n0,8,-0.0006\n28800000,8,-0.001\n" \
          "57600000,8,-0.0004\n300000000,8,-0.0005\n"
    monkeypatch.setattr(lab.dumps, "csv_text", lambda rel: csv)
    monkeypatch.setattr(lab, "months", lambda a, b: ["2024-01"])
    assert lab.funding_events("X", 0, 1, gap_s=72 * 3600) == [0.0, 300000.0]  # 8 h later still in the trade


def test_net_uses_only_closed_bars_and_costs():
    ts, cl = np.array([0, 60, 120], dtype=np.int64), np.array([10.0, 11.0, 12.0])
    r = lab.net(ts, cl, 60, 180)  # buy at the close known at 60 (bar 0), sell at 180 (bar 120)
    assert math.isclose(r, math.log(12 * 0.999 * 0.999 / (10 * 1.001 * 1.001)))
    assert lab.net(ts, cl, 30, 180) is None  # no bar closed yet


def test_period_labels_split_confirmation_exploration_live():
    t = pd.Series([lab.CONF_END - 1, lab.CONF_END, lab.LIVE_START])
    assert [p.split()[0] for p in lab.period(t)] == ["CONFIRMATION", "EXPLORATION", "LIVE"]


def test_universe_is_frozen():
    assert lab.universe() == lab.FROZEN.read_text().split() and len(lab.universe()) == 30
