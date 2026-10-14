"""Basic tests for the ComEd client. Run with: pytest"""

import os

os.environ["OFFPEAK_OFFLINE"] = "1"  # never hit the live API in tests

from offpeak import comed
from offpeak.server import get_live_price


def test_parse_sorts_oldest_first_and_skips_bad_rows():
    rows = [
        {"millisUTC": "1760000600000", "price": "3.1"},
        {"millisUTC": "1760000300000", "price": "2.9"},
        {"millisUTC": "oops", "price": "9.9"},  # malformed, should be skipped
    ]
    points = comed._parse(rows)
    assert [p.cents_per_kwh for p in points] == [2.9, 3.1]


def test_price_levels():
    assert comed.price_level(-1).startswith("negative")
    assert comed.price_level(2) == "low"
    assert comed.price_level(4) == "normal"
    assert comed.price_level(8) == "high"
    assert comed.price_level(15).startswith("very high")


def test_get_live_price_offline():
    result = get_live_price()
    assert "spoken" in result
    assert result["current_hour_average_cents_per_kwh"] > 0
    assert result["trend_last_30min"] in {"rising", "falling", "steady"}
