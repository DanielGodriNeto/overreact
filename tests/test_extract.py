from unittest import mock

from overreact.extract import throttle, validate

KNOWN = {"PLUG", "SOFI"}


def test_valid_output_passes():
    assert validate({"ticker": "$plug", "direction": -1, "confidence": 0.7, "category": "offering"}, KNOWN) \
        == ("PLUG", -1, 0.7, "offering")


def test_unknown_ticker_and_bad_values_are_neutralized():
    assert validate({"ticker": "XYZ", "direction": 5, "confidence": 3, "category": "moon"}, KNOWN) \
        == (None, 1, 1.0, "other")
    assert validate({"direction": "up", "confidence": None}, KNOWN) == (None, 0, 0.0, "other")
    assert validate({}, KNOWN) == (None, 0, 0.0, "other")
    assert validate({"direction": 1e999, "category": ["x"]}, KNOWN) == (None, 0, 0.0, "other")


def test_feed_ticker_is_fallback():
    assert validate({"ticker": "Plug Power"}, KNOWN, hint="PLUG")[0] == "PLUG"
    assert validate({"ticker": "SOFI"}, KNOWN, hint="PLUG")[0] == "SOFI"


def test_throttle_pause_matches_duty():
    with mock.patch("overreact.extract.time.sleep") as sleep:
        throttle(2.0, 0.25)  # 2 s of work at 25% duty -> 6 s pause
    sleep.assert_called_once_with(6.0)
