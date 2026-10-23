"""Simulated smart home + autopilot.

The home's state (devices, guardrails, tonight's plan, action log, savings)
lives in a JSON file, so it survives restarts and new conversations. That's
what lets OffPeak say "same as last night?" or keep your 7 AM EV deadline.

Devices are simulated for the hackathon. Everything that touches a device
goes through `set_device`, so a real integration (Alexa smart home, a car
API, a smart thermostat) can replace that one function later.
"""

from __future__ import annotations

import json
import math
import os
import threading
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

from offpeak import comed, planner

STATE_PATH = Path(os.getenv("OFFPEAK_STATE", Path(__file__).resolve().parent.parent / "data" / "home.json"))
_lock = threading.RLock()

DEFAULT_STATE = {
    "guardrails": {
        "ev_ready_by_hour": 7,  # EV must hit its target by 7 AM
        "ev_target_percent": 80,
        "max_indoor_temp_f": 78,  # never let the house get warmer than this
        "min_indoor_temp_f": 66,  # or colder than this
        "spike_threshold_cents": 10.0,  # react automatically above this price
    },
    "devices": {
        "ev": {"name": "EV charger", "state": "idle", "battery_percent": 42,
               "battery_kwh": 75, "charger_kw": 7.2},
        "thermostat": {"name": "Thermostat", "state": "normal", "setpoint_f": 72, "mode": "heat"},
        "dishwasher": {"name": "Dishwasher", "state": "idle", "hours": 2, "kwh": 1.5},
        "dryer": {"name": "Dryer", "state": "idle", "hours": 1, "kwh": 3.0},
    },
    "plan": [],  # scheduled jobs, see run_autopilot
    "log": [],  # newest last: {"time", "text", "saved_dollars"}
    "saved_dollars": 0.0,
    "handled_spikes": [],  # hour keys we've already reacted to
    "demo": None,  # active spike replay, see start_spike_demo
}

APPLIANCES = ("ev", "dishwasher", "dryer")


# ---------------------------------------------------------------- persistence
def load() -> dict:
    with _lock:
        if STATE_PATH.exists():
            try:
                state = json.loads(STATE_PATH.read_text())
                # fill in anything added since the file was written
                merged = deepcopy(DEFAULT_STATE)
                merged.update(state)
                for k, v in DEFAULT_STATE["guardrails"].items():
                    merged["guardrails"].setdefault(k, v)
                return merged
            except (json.JSONDecodeError, OSError):
                pass
        return deepcopy(DEFAULT_STATE)


def save(state: dict) -> None:
    with _lock:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        state["log"] = state["log"][-50:]
        tmp = STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, default=str))
        tmp.replace(STATE_PATH)


def reset() -> dict:
    with _lock:
        state = deepcopy(DEFAULT_STATE)
        save(state)
        return state


def _log(state: dict, text: str, saved: float = 0.0) -> None:
    state["log"].append({
        "time": comed.now().strftime("%a %I:%M %p").replace(" 0", " "),
        "text": text,
        "saved_dollars": round(saved, 2),
    })
    state["saved_dollars"] = round(state.get("saved_dollars", 0.0) + saved, 2)


def set_device(home_state: dict, device: str, **changes) -> None:
    """The one place devices change. Swap this for a real integration later."""
    home_state["devices"][device].update(changes)


# ---------------------------------------------------------------- EV math
def ev_energy_needed(state: dict) -> float:
    ev = state["devices"]["ev"]
    target = state["guardrails"]["ev_target_percent"]
    return max(0.0, (target - ev["battery_percent"]) / 100 * ev["battery_kwh"])


def ev_hours_needed(state: dict) -> int:
    kwh = ev_energy_needed(state)
    return math.ceil(kwh / state["devices"]["ev"]["charger_kw"]) if kwh > 0 else 0


# ---------------------------------------------------------------- autopilot
def _deadline(hour: int) -> datetime:
    current = comed.now()
    target = current.replace(hour=hour, minute=0, second=0, microsecond=0)
    return target if target > current else target + timedelta(days=1)


def _job_entry(device: str, label: str, window: planner.Window, kwh: float, now_avg: float | None) -> dict:
    cost = planner.dollars(kwh, window.avg_cents)
    cost_now = planner.dollars(kwh, now_avg) if now_avg else cost
    return {
        "device": device,
        "label": label,
        "hours": [h.start.isoformat() for h in window.hours],
        "start": comed.fmt_day_hour(window.start),
        "end": comed.fmt_day_hour(window.end),
        "avg_cents": window.avg_cents,
        "kwh": round(kwh, 1),
        "cost_dollars": cost,
        "cost_if_now_dollars": cost_now,
        "saved_dollars": round(max(0.0, cost_now - cost), 2),
    }


def run_autopilot(devices: list[str] | None = None, curve: list | None = None) -> dict:
    """Plan the cheapest hours for each job within the guardrails and schedule it."""
    devices = [d for d in (devices or list(APPLIANCES)) if d in APPLIANCES]
    curve = curve if curve is not None else comed.forward_curve(36)
    with _lock:
        state = load()
        g = state["guardrails"]
        plan, skipped = [], []

        for device in devices:
            if device == "ev":
                hours = ev_hours_needed(state)
                if hours == 0:
                    skipped.append("EV is already at its target charge")
                    continue
                window = planner.cheapest_hours(curve, hours, _deadline(g["ev_ready_by_hour"]))
                if window is None:
                    skipped.append("not enough price data yet to schedule the EV")
                    continue
                kwh = ev_energy_needed(state)
                entry = _job_entry("ev", f"Charge car to {g['ev_target_percent']}%", window, kwh,
                                   planner.run_now_cost(curve, hours))
                set_device(state, "ev", state="scheduled", scheduled_for=entry["start"])
            else:
                spec = state["devices"][device]
                window = planner.cheapest_block(curve, spec["hours"])
                if window is None:
                    skipped.append(f"not enough price data to schedule the {spec['name'].lower()}")
                    continue
                entry = _job_entry(device, f"Run {spec['name'].lower()}", window, spec["kwh"],
                                   planner.run_now_cost(curve, spec["hours"]))
                set_device(state, device, state="scheduled", scheduled_for=entry["start"])
            plan.append(entry)

        uses_estimates = any(
            h.projected for h in curve if any(h.start.isoformat() in p["hours"] for p in plan)
        )
        state["plan"] = plan
        total_saved = round(sum(p["saved_dollars"] for p in plan), 2)
        total_cost = round(sum(p["cost_dollars"] for p in plan), 2)
        if plan:
            _log(state, "Autopilot scheduled " + ", ".join(
                f"{p['label'].lower()} {p['start']}" for p in plan), total_saved)
        save(state)

    parts = [f"{p['label'].split(' to ')[0].replace('Run ', 'the ').replace('Charge car', 'your car')} {p['start']}"
             for p in plan]
    spoken = "Autopilot's set. " if plan else "I couldn't schedule anything yet. "
    if parts:
        spoken += "I'll run " + (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]) + ". "
        spoken += f"That's about ${total_cost:.2f} total, ${total_saved:.2f} less than running it all now."
    if skipped:
        spoken += " Note: " + "; ".join(skipped) + "."
    result = {"plan": plan, "total_cost_dollars": total_cost, "total_saved_dollars": total_saved,
              "skipped": skipped, "spoken": spoken.strip()}
    if uses_estimates:
        result["note"] = ("Overnight prices are estimated until ComEd publishes tomorrow's "
                          "prices around 4:30pm Central; the autopilot re-checks then.")
    return result


# ---------------------------------------------------------------- spikes
def current_price() -> tuple[float, str]:
    """Live price, or the replay price if a spike demo is running."""
    state = load()
    demo = state.get("demo")
    if demo:
        seq = demo["sequence"]
        return seq[min(demo["step"], len(seq) - 1)], "replay"
    hour_avg = comed.fetch("currenthouraverage")
    five = comed.fetch("5minutefeed")
    price = five[-1].cents_per_kwh if five else hour_avg[-1].cents_per_kwh
    return price, "live"


def start_spike_demo() -> dict:
    """Set the scene for the spike replay: car plugged in and charging, dryer running.

    Each later call to check_for_spike advances the replay one step:
    a normal evening price, rising, then a spike.
    """
    with _lock:
        state = load()
        state["demo"] = {"step": 0, "sequence": [4.1, 5.6, 9.2, 16.8, 17.4]}
        state["handled_spikes"] = []
        set_device(state, "ev", state="charging", scheduled_for=None)
        set_device(state, "dryer", state="running", scheduled_for=None)
        set_device(state, "thermostat", state="normal", setpoint_f=72)
        _log(state, "Replay started: EV plugged in and charging, dryer running")
        save(state)
    return {"spoken": "Replay's running. Your car just started charging and the dryer's on. I'm watching prices."}


def stop_spike_demo() -> None:
    with _lock:
        state = load()
        state["demo"] = None
        save(state)


def check_for_spike(curve: list | None = None) -> dict:
    """Look at the price now. If it's above the guardrail threshold, act on our own.

    Returns {"spike": False, ...} normally, or the actions taken.
    """
    with _lock:
        state = load()
        price, source = current_price()
        if state.get("demo"):
            state["demo"]["step"] += 1  # advance the replay for next time
        threshold = state["guardrails"]["spike_threshold_cents"]
        hour_key = comed.now().strftime("%Y-%m-%d %H") + (":demo" if source == "replay" else "")

        if price < threshold or hour_key in state["handled_spikes"]:
            save(state)
            return {"spike": False, "price_cents": price, "source": source,
                    "already_handled": hour_key in state["handled_spikes"]}

        actions, avoided = [], 0.0
        curve = curve if curve is not None else comed.forward_curve(36)
        # Don't reschedule into the spike itself: skip this hour (and, for a
        # replayed evening spike, the next couple of hours too)
        current_hour = comed.now().replace(minute=0, second=0, microsecond=0)
        spike_ends = current_hour + timedelta(hours=3 if source == "replay" else 1)
        after_spike = [h for h in curve
                       if h.best is not None and h.best < threshold and h.start >= spike_ends]
        devices = state["devices"]

        # 1) Pause EV charging and move it to the cheapest hours before the deadline
        if devices["ev"]["state"] in ("charging", "scheduled"):
            hours = max(1, ev_hours_needed(state))
            window = planner.cheapest_hours(after_spike, hours,
                                            _deadline(state["guardrails"]["ev_ready_by_hour"]))
            kwh_this_hour = devices["ev"]["charger_kw"]
            new_price = window.avg_cents if window else price
            avoided += planner.dollars(kwh_this_hour, price - new_price)
            set_device(state, "ev", state="paused",
                       scheduled_for=comed.fmt_day_hour(window.start) if window else None)
            actions.append(f"paused your car and moved charging to {comed.fmt_day_hour(window.start)}"
                           if window else "paused your car")

        # 2) Delay the dryer
        if devices["dryer"]["state"] in ("running", "scheduled"):
            window = planner.cheapest_block(after_spike, devices["dryer"]["hours"])
            new_price = window.avg_cents if window else price
            avoided += planner.dollars(devices["dryer"]["kwh"], price - new_price)
            set_device(state, "dryer", state="delayed",
                       scheduled_for=comed.fmt_day_hour(window.start) if window else None)
            actions.append(f"held the dryer until {comed.fmt_day_hour(window.start)}" if window
                           else "held the dryer")

        # 3) Thermostat: coast within the comfort limits instead of running hard
        t = devices["thermostat"]
        g = state["guardrails"]
        if t["mode"] == "heat":
            new_set = max(g["min_indoor_temp_f"], t["setpoint_f"] - 3)
        else:
            new_set = min(g["max_indoor_temp_f"], t["setpoint_f"] + 3)
        if new_set != t["setpoint_f"]:
            avoided += planner.dollars(1.5, price)  # ~1.5 kWh less HVAC over the spike
            set_device(state, "thermostat", state="eco", setpoint_f=new_set, normal_setpoint_f=t["setpoint_f"])
            actions.append(f"eased the thermostat to {new_set} degrees for the spike")

        avoided = round(max(0.0, avoided), 2)
        state["handled_spikes"].append(hour_key)
        summary = "; ".join(actions) if actions else "nothing was running, so no changes needed"
        _log(state, f"Price spike {price:.1f}¢: {summary}", avoided)
        save(state)

    spoken = f"Heads up, power just spiked to {price:.0f} cents. "
    if actions:
        spoken += "I " + (", ".join(actions[:-1]) + ", and " + actions[-1] if len(actions) > 1 else actions[0])
        spoken += f". That saves you about ${avoided:.2f}, and your car will still be ready by " \
                  f"{state['guardrails']['ev_ready_by_hour']} AM."
    else:
        spoken += "Nothing was running, so you're fine."
    return {"spike": True, "price_cents": price, "source": source, "actions": actions,
            "saved_dollars": avoided, "spoken": spoken}


# ---------------------------------------------------------------- status
def status() -> dict:
    state = load()
    d = state["devices"]
    tiles = []
    for key, dev in d.items():
        if key == "ev":
            detail = f"{dev['battery_percent']}% · target {state['guardrails']['ev_target_percent']}%"
        elif key == "thermostat":
            detail = f"{dev['setpoint_f']}°F · {dev['mode']}"
        else:
            detail = f"{dev.get('hours', '')}h cycle"
        tiles.append({"id": key, "name": dev["name"], "state": dev["state"],
                      "detail": detail, "scheduled_for": dev.get("scheduled_for")})
    return {
        "devices": tiles,
        "guardrails": state["guardrails"],
        "plan": state["plan"],
        "recent_actions": state["log"][-5:],
        "saved_total_dollars": state.get("saved_dollars", 0.0),
        "replay_active": bool(state.get("demo")),
    }


def update_guardrails(**changes) -> dict:
    with _lock:
        state = load()
        applied = {k: v for k, v in changes.items() if v is not None and k in state["guardrails"]}
        state["guardrails"].update(applied)
        if applied:
            _log(state, "Updated settings: " + ", ".join(f"{k}={v}" for k, v in applied.items()))
        save(state)
        return {"guardrails": state["guardrails"], "changed": applied}


def control(device: str, action: str) -> dict:
    """Manual control: start, stop, pause."""
    if device not in DEFAULT_STATE["devices"]:
        return {"error": "unknown_device", "spoken": f"I don't have a device called {device}."}
    with _lock:
        state = load()
        new_state = {"start": "charging" if device == "ev" else "running",
                     "stop": "idle", "pause": "paused"}.get(action)
        if new_state is None:
            return {"error": "unknown_action", "spoken": "I can start, stop, or pause devices."}
        set_device(state, device, state=new_state, scheduled_for=None)
        state["plan"] = [p for p in state["plan"] if p["device"] != device]
        _log(state, f"{state['devices'][device]['name']}: {action} (manual)")
        save(state)
        return {"device": device, "state": new_state,
                "spoken": f"Done, the {state['devices'][device]['name'].lower()} is {new_state}."}
