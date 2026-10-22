"""Autopilot + spike tests. Offline data, frozen clock, temp state file."""

from datetime import datetime

import pytest

from offpeak import comed, home, server

CHI = comed.CHICAGO


@pytest.fixture(autouse=True)
def setup(monkeypatch, tmp_path):
    monkeypatch.setenv("OFFPEAK_OFFLINE", "1")
    monkeypatch.setattr(home, "STATE_PATH", tmp_path / "home.json")
    monkeypatch.setattr(comed, "now", lambda: datetime(2026, 10, 22, 17, 40, tzinfo=CHI))
    comed.clear_cache()
    home.reset()


def test_autopilot_schedules_all_jobs_overnight_and_saves_money():
    r = server.run_autopilot()
    assert {p["device"] for p in r["plan"]} == {"ev", "dishwasher", "dryer"}
    assert r["total_saved_dollars"] > 0
    assert all("tonight" in p["start"] for p in r["plan"])


def test_plan_and_settings_persist_across_sessions():
    server.run_autopilot(["ev"])
    server.update_settings(ev_ready_by_hour=6, ev_target_percent=90)
    reloaded = home.load()  # a "new session" reads the file again
    assert reloaded["guardrails"]["ev_ready_by_hour"] == 6
    assert reloaded["plan"][0]["device"] == "ev"


def test_spike_replay_triggers_autonomous_reaction():
    server.start_spike_replay()
    results = [server.check_for_price_spike() for _ in range(5)]
    spikes = [r for r in results if r.get("spike")]
    assert len(spikes) == 1  # reacts once, not every check
    s = spikes[0]
    assert s["saved_dollars"] > 0 and len(s["actions"]) == 3
    devices = home.load()["devices"]
    assert devices["ev"]["state"] == "paused" and devices["dryer"]["state"] == "delayed"
    assert devices["thermostat"]["setpoint_f"] >= home.load()["guardrails"]["min_indoor_temp_f"]


def test_no_spike_means_no_action():
    r = server.check_for_price_spike()
    assert r["spike"] is False
    assert home.load()["devices"]["ev"]["state"] == "idle"


def test_manual_control():
    assert server.control_device("dryer", "start")["state"] == "running"
    assert server.control_device("toaster", "start")["error"] == "unknown_device"
