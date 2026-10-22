"""Tests for the ComEd client and price tools. Run with: pytest

All tests use offline sample data and a frozen clock, so they never touch
the live API and always give the same answers.
"""

from datetime import date, datetime, timedelta

import pytest

from offpeak import comed, planner, server

CHI = comed.CHICAGO


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("OFFPEAK_OFFLINE", "1")
    comed.clear_cache()
    yield
    comed.clear_cache()


def freeze(monkeypatch, *args):
    monkeypatch.setattr(comed, "now", lambda: datetime(*args, tzinfo=CHI))


# ---------------------------------------------------------------- parsing
def test_parse_json_sorts_oldest_first_and_skips_bad_rows():
    rows = [
        {"millisUTC": "1760000600000", "price": "3.1"},
        {"millisUTC": "1760000300000", "price": "2.9"},
        {"millisUTC": "oops", "price": "9.9"},
    ]
    assert [p.cents_per_kwh for p in comed.parse_json(rows)] == [2.9, 3.1]


def test_parse_table_converts_hour_ending_to_hour_starting():
    body = (
        "<tr><td>1:00 AM</td><td>2.0&cent;</td><td>2.1&cent;</td></tr>"
        "<tr><td>3:00 p.m.</td><td>4.5&cent;</td><td>n/a</td></tr>"
        "<tr><td>12:00 AM</td><td>1.9&cent;</td><td>n/a</td></tr>"
    )
    hours = comed.parse_table(body, date(2026, 10, 14), has_actual=True)
    starts = [h.start.hour for h in hours]
    assert starts == [0, 14, 23]  # 1AM-ending = midnight hour; 12AM-ending = 11pm hour
    assert hours[0].actual == 2.1 and hours[1].actual is None
    assert all(h.start.date() == date(2026, 10, 14) for h in hours)


def test_parse_table_handles_empty_feed():
    assert comed.parse_table("", date(2026, 10, 15), has_actual=False) == []


def test_price_levels():
    assert comed.price_level(-1).startswith("negative")
    assert comed.price_level(2) == "low"
    assert comed.price_level(4) == "normal"
    assert comed.price_level(8) == "high"
    assert comed.price_level(15).startswith("very high")


# ---------------------------------------------------------------- forward curve
def test_forward_curve_before_tomorrow_published(monkeypatch):
    freeze(monkeypatch, 2026, 10, 14, 11, 30)  # 11:30am, tomorrow not out yet
    curve = comed.forward_curve(24)
    assert curve[0].start.hour == 11
    assert len(curve) == 13  # 11am..11pm today only
    assert comed.tomorrow_prices() == []


def test_forward_curve_after_tomorrow_published(monkeypatch):
    freeze(monkeypatch, 2026, 10, 14, 17, 0)  # 5pm, tomorrow is out
    curve = comed.forward_curve(24)
    assert len(curve) == 24
    assert curve[-1].start == datetime(2026, 10, 15, 16, tzinfo=CHI)
    # hours are consecutive with no gaps or duplicates across midnight
    assert all(b.start - a.start == timedelta(hours=1) for a, b in zip(curve, curve[1:]))


# ---------------------------------------------------------------- planner
def _curve(prices, start=datetime(2026, 10, 14, 20, tzinfo=CHI)):
    return [comed.HourPrice(start + timedelta(hours=i), p) for i, p in enumerate(prices)]


def test_cheapest_block_must_be_back_to_back():
    curve = _curve([5, 1, 9, 1, 1, 5])
    w = planner.cheapest_block(curve, 2)
    assert [h.best for h in w.hours] == [1, 1] and w.is_contiguous
    assert w.start.hour == 23  # 8pm + 3


def test_cheapest_hours_can_split():
    curve = _curve([5, 1, 9, 1, 2, 5])
    w = planner.cheapest_hours(curve, 3)
    assert sorted(h.best for h in w.hours) == [1, 1, 2]
    assert not w.is_contiguous


def test_deadline_is_respected():
    curve = _curve([5, 4, 3, 2, 1, 0.5])  # cheapest hours are last
    deadline = curve[3].start + timedelta(hours=1)  # must finish after the 4th hour
    w = planner.cheapest_block(curve, 1, deadline)
    assert w.hours[0].best == 2


def test_not_enough_hours_returns_none():
    assert planner.cheapest_block(_curve([1, 2]), 3) is None
    assert planner.cheapest_hours(_curve([1, 2]), 3) is None


# ---------------------------------------------------------------- MCP tools
def test_get_live_price_offline():
    result = server.get_live_price()
    assert "spoken" in result and "error" not in result
    assert result["trend_last_30min"] in {"rising", "falling", "steady"}


def test_forecast_tool(monkeypatch):
    freeze(monkeypatch, 2026, 10, 14, 17, 0)
    result = server.get_price_forecast(24)
    assert result["tomorrow_prices_published"] is True
    assert len(result["hours"]) == 24
    assert "cheapest" in result["spoken"]


def test_find_cheapest_time_ev_overnight(monkeypatch):
    freeze(monkeypatch, 2026, 10, 14, 18, 0)  # 6pm, peak hour
    result = server.find_cheapest_time(4, finish_by_hour=7, can_split=True, energy_kwh=40)
    assert "error" not in result, result
    assert result["savings_vs_now_percent"] > 50  # overnight beats the 6pm peak by a lot
    assert result["estimated_cost_dollars"] < result["estimated_cost_if_now_dollars"]
    assert "tonight" in result["start"]


def test_find_cheapest_time_dishwasher_block(monkeypatch):
    freeze(monkeypatch, 2026, 10, 14, 18, 0)
    result = server.find_cheapest_time(2)
    assert result["is_one_block"] is True


def test_find_cheapest_time_reports_missing_data(monkeypatch):
    freeze(monkeypatch, 2026, 10, 14, 22, 0)  # 10pm, tomorrow is published
    result = server.find_cheapest_time(6, finish_by_hour=0)  # only 2 hours until midnight
    assert result["error"] == "not_enough_price_data"


def test_day_prices_tool(monkeypatch):
    freeze(monkeypatch, 2026, 10, 14, 12, 0)
    result = server.get_day_prices("2026-10-13")
    assert len(result["hours"]) == 24
    assert result["peak"]["start"] in {"5 PM", "6 PM"}
    assert server.get_day_prices("2026-12-25")["error"] == "future_date"
    assert server.get_day_prices("yesterday")["error"] == "bad_date"


def test_find_cheapest_time_warns_when_tomorrow_unpublished(monkeypatch):
    freeze(monkeypatch, 2026, 10, 14, 11, 0)  # morning: only today's prices exist
    result = server.find_cheapest_time(4, finish_by_hour=7, can_split=True)
    assert "note" in result and "4:30" in result["spoken"]
    freeze(monkeypatch, 2026, 10, 14, 18, 0)  # evening: tomorrow published, no warning
    comed.clear_cache()
    assert "note" not in server.find_cheapest_time(4, finish_by_hour=7, can_split=True)


def test_agent_skill_is_valid():
    from offpeak.agent import load_skill

    skill = load_skill()  # strict agentskills.io validation
    assert skill.name == "offpeak"
    for tool in ["get_live_price", "get_price_forecast", "find_cheapest_time", "get_day_prices",
                 "run_autopilot", "get_home_status", "update_settings", "control_device",
                 "check_for_price_spike", "start_spike_replay"]:
        assert tool in skill.instructions, f"skill doesn't mention {tool}"
