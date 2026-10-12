import numpy as np
import pandas as pd
import pytest

from overreact.fairvalue import band, forward_return, reversion_table


def test_band_uses_only_past_data():
    close = pd.Series(np.linspace(10, 20, 50))
    full = band(close, window=10)
    cut = band(close.iloc[:30], window=10)
    # values up to day 29 must not change when future days are appended
    pd.testing.assert_frame_equal(full.iloc[:30], cut)


def test_spike_gives_high_z_and_sits_above_upper():
    close = pd.Series([10.0 + 0.01 * (i % 3) for i in range(60)] + [13.0])  # band needs ~2*window days of warm-up
    b = band(close, window=20).iloc[-1]
    assert b["z"] > 2
    assert 13.0 > b["upper"] > b["fair"] > b["lower"]


def test_forward_return_looks_ahead_h_days():
    fwd = forward_return(pd.Series([10.0, 11.0, 12.1]), 1)
    assert fwd.iloc[0] == pytest.approx(0.1)
    assert np.isnan(fwd.iloc[-1])


def test_reversion_sign_and_costs():
    sig = pd.DataFrame({
        "z": [-3, -3, 3, 0],
        "ex_1d": [0.02, 0.04, -0.01, 0.0], "ex_5d": [0.0] * 4, "ex_10d": [0.0] * 4,
    })
    t = reversion_table(sig, cut=2, cost_bps=10)
    assert t.loc["panic z<=-cut", "ex_1d_%"] == pytest.approx(3.0)
    assert t.loc["euphoria z>=cut", "ex_1d_%"] == pytest.approx(1.0)  # price fell after euphoria = reversion
    assert t.loc["panic z<=-cut", "net_1d_%"] == pytest.approx(2.8)
