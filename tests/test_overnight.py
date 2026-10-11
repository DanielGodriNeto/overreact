import pandas as pd
import pytest

from overreact.overnight import split_returns, summarize


def prices(opens, closes):
    return pd.DataFrame({"open": opens, "close": closes})


def test_split_returns_decomposes_hold():
    rets = split_returns(prices([10, 11, 9], [10, 12, 9.9]))
    # day 2: overnight 10->11, intraday 11->12, hold 10->12
    assert rets.iloc[0]["overnight"] == pytest.approx(0.10)
    assert rets.iloc[0]["intraday"] == pytest.approx(12 / 11 - 1)
    # overnight and intraday compound to hold every day
    composed = (1 + rets["overnight"]) * (1 + rets["intraday"]) - 1
    assert composed.tolist() == pytest.approx(rets["hold"].tolist())


def test_costs_reduce_net_and_zero_cost_matches_gross():
    rets = split_returns(prices([10, 11, 12, 13], [10.5, 11.5, 12.5, 13.5]))
    free = summarize(rets, cost_bps=0)
    assert free["overnight_net_%"] == pytest.approx(free["overnight_gross_%"])
    assert summarize(rets, cost_bps=20)["overnight_net_%"] < free["overnight_net_%"]


def test_flat_market_returns_zero():
    s = summarize(split_returns(prices([5, 5, 5], [5, 5, 5])), cost_bps=0)
    assert s["hold_%"] == 0 and s["overnight_gross_%"] == 0 and s["intraday_%"] == 0
