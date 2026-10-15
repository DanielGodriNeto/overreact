import math

import pytest

from overreact.crypto.sim import onset, trade, worst_fill

# t_s, close, high, low, quote_vol, trades
BARS = [(100, 10.0, 10.0, 10.0, 1, 1), (101, 10.0, 10.0, 10.0, 1, 1),
        (102, 11.0, 12.0, 10.5, 1, 1), (103, 11.5, 11.8, 11.2, 1, 1), (110, 11.0, 11.1, 10.9, 1, 1)]


def test_worst_fill_takes_the_bad_side_of_the_landing_seconds():
    assert worst_fill(BARS, 102.4, "buy") == 12.0  # highest high of seconds 102-103
    assert worst_fill(BARS, 102.4, "sell") == 10.5
    assert worst_fill(BARS, 106.0, "buy") == 11.5  # no trades 104-107: last close known (bar 103 closed at 104)
    assert worst_fill(BARS, 98.0, "buy") is None  # no trade in 98-99 and nothing known before


def test_trade_is_net_of_fees_and_slippage():
    r = trade(BARS, 106.0, 110.2, slip=0.01, fee=0.001)
    assert r == pytest.approx(math.log(10.9 * 0.99 * 0.999 / (11.5 * 1.01 * 1.001)))
    assert trade(BARS, 98.0, 110.0, slip=0) is None


def test_onset_finds_first_move_and_leaks():
    assert onset(BARS, t0=101, thresh=0.05, lo=0, hi=5) == 1  # bar 102 closes 10% above the price known at 101
    assert onset(BARS, t0=104, thresh=0.05, lo=-3, hi=5) == -2  # moved before the stamp
    assert onset(BARS, t0=101, thresh=0.5, lo=0, hi=5) is None  # never moved that much
