import numpy as np
import pandas as pd
import pytest

from overreact.hypothesis import events_for, label, summary


def test_entry_is_trading_day_after_filing():
    dates = pd.date_range("2024-01-01", periods=60, freq="B").strftime("%Y-%m-%d")
    close = pd.Series(np.linspace(10, 12, 60), index=dates)
    filed = dates[45]
    ev = events_for(close, pd.DataFrame({"filed": [filed, "2030-01-01"], "direction": [1, 0]}), window=10)
    assert ev["entry"].tolist() == [dates[46]]  # future filing dropped, entry strictly after filing day


def test_groups_and_contrarian_sign():
    ev = pd.DataFrame({
        "z": [-2.0, -2.0, 2.0, 0.0],
        "direction": [1, -1, 0, 1],
        "ex_1d": [0.03, -0.01, -0.02, 0.0], "ex_5d": [0.0] * 4, "ex_10d": [0.0] * 4,
    })
    assert label(ev, 1.5).tolist() == ["OVERREACT: dropped, news not bad", "justified: dropped, bad news",
                                       "OVERREACT: jumped, news not good", "no strong move"]
    s = summary(ev, 1.5)
    assert s.loc["OVERREACT: dropped, news not bad", "rev_1d_%"] == pytest.approx(3.0)
    assert s.loc["OVERREACT: jumped, news not good", "rev_1d_%"] == pytest.approx(2.0)  # fell after jump = reverted
