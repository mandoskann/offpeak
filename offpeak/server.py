"""OffPeak MCP server.

A self-hosted MCP server (Streamable HTTP) that gives an Alexa+ agent live
electricity prices and the math to act on them.

Run:   python -m offpeak.server
URL:   http://localhost:8000/mcp
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Annotated

from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import Field

from offpeak import comed, home, planner

load_dotenv()

mcp = FastMCP(
    name="OffPeak",
    instructions=(
        "OffPeak is a home energy autopilot. Use these tools to check live and "
        "upcoming electricity prices before advising when to run appliances or "
        "charge an EV. Prices are ComEd hourly supply prices in cents per kWh "
        "(Chicago area, PJM ComEd zone). Each tool returns a 'spoken' field: a "
        "short sentence suitable for reading aloud on a voice assistant."
    ),
    version="0.4.0",
)


def _error(msg: str) -> dict:
    return {"error": msg, "spoken": "Sorry, I couldn't get power prices right now. Try again in a minute."}


def _next_occurrence(hour: int) -> datetime:
    """The next time the clock hits `hour`:00 (today if still ahead, else tomorrow)."""
    current = comed.now()
    target = current.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= current:
        target += timedelta(days=1)
    return target


@mcp.tool
def get_live_price() -> dict:
    """Get the live electricity supply price right now (ComEd, cents per kWh).

    Returns the latest 5-minute price, the current-hour average (what hourly
    pricing customers actually pay), a plain-English level, a 30-minute trend,
    and a short sentence to read out loud.
    """
    try:
        hour_avg = comed.fetch("currenthouraverage")
        five_min = comed.fetch("5minutefeed")
    except Exception as exc:  # network / ComEd down
        return _error(f"ComEd feed unavailable: {exc}")
    if not hour_avg or not five_min:
        return _error("ComEd price feed returned no data.")

    avg = hour_avg[-1]
    latest = five_min[-1]
    replay_price, source = home.current_price()
    if source == "replay":  # demo spike replay is running
        avg = comed.PricePoint(comed.now(), replay_price)
        latest = avg
    level = comed.price_level(avg.cents_per_kwh)

    recent = five_min[-7:]  # last 30 minutes of 5-minute readings
    change = round(recent[-1].cents_per_kwh - recent[0].cents_per_kwh, 2)
    trend = "rising" if change > 0.5 else "falling" if change < -0.5 else "steady"

    return {
        "current_hour_average_cents_per_kwh": avg.cents_per_kwh,
        "latest_5min_cents_per_kwh": latest.cents_per_kwh,
        "latest_5min_time": latest.time.strftime("%I:%M %p %Z").lstrip("0"),
        "level": level,
        "trend_last_30min": trend,
        "change_last_30min_cents": change,
        "source": "ComEd Hourly Pricing (PJM ComEd zone)" if source == "live" else "spike replay (demo)",
        "spoken": (
            f"Power is {avg.cents_per_kwh:.1f} cents per kilowatt hour this hour, "
            f"which is {level.split(' (')[0]}, and it's {trend}."
        ),
    }


@mcp.tool
def get_price_forecast(
    hours: Annotated[int, Field(ge=1, le=36, description="How many hours ahead to look")] = 24,
) -> dict:
    """Get the hourly price outlook from now forward (cents per kWh).

    Uses ComEd's day-ahead estimates for the rest of today, plus tomorrow's
    once ComEd publishes them (around 4:30pm Central). Includes the cheapest
    and most expensive upcoming hours. Use this before planning anything.
    """
    try:
        curve = comed.forward_curve(hours)
        tomorrow_published = bool(comed.tomorrow_prices())
    except Exception as exc:
        return _error(f"ComEd feed unavailable: {exc}")
    if not curve:
        return _error("No upcoming hourly prices available.")

    cheapest = min(curve, key=lambda h: h.best)
    priciest = max(curve, key=lambda h: h.best)
    avg = round(sum(h.best for h in curve) / len(curve), 2)

    return {
        "hours": [
            {"start": h.start.strftime("%a %I %p").replace(" 0", " "), "cents_per_kwh": h.best}
            for h in curve
        ],
        "average_cents_per_kwh": avg,
        "cheapest": {"start": comed.fmt_day_hour(cheapest.start), "cents_per_kwh": cheapest.best},
        "most_expensive": {"start": comed.fmt_day_hour(priciest.start), "cents_per_kwh": priciest.best},
        "covers_until": comed.fmt_day_hour(curve[-1].start + timedelta(hours=1)),
        "tomorrow_prices_published": tomorrow_published,
        "note": (
            "Day-ahead estimates; real-time prices can differ."
            if tomorrow_published
            else "Tomorrow's prices aren't published yet (ComEd posts them around 4:30pm Central)."
        ),
        "spoken": (
            f"The cheapest hour coming up is {comed.fmt_day_hour(cheapest.start)} at "
            f"{cheapest.best:.1f} cents. The priciest is {comed.fmt_day_hour(priciest.start)} "
            f"at {priciest.best:.1f} cents."
        ),
    }


@mcp.tool
def find_cheapest_time(
    duration_hours: Annotated[int, Field(ge=1, le=12, description="How many hours the job needs")],
    finish_by_hour: Annotated[
        int | None,
        Field(ge=0, le=23, description="Must be done by this hour, 24h clock (7 = 7am). Omit for no deadline."),
    ] = None,
    can_split: Annotated[
        bool,
        Field(description="True if the job can pause and resume across separate hours (EV charging). False for appliances that must run in one go."),
    ] = False,
    energy_kwh: Annotated[
        float | None,
        Field(ge=0, le=200, description="Total energy the job uses, for a dollar estimate (EV ~30-60 kWh, dryer ~3, dishwasher ~1.5)"),
    ] = None,
) -> dict:
    """Find the cheapest upcoming time to run something.

    Examples: dishwasher (2 hours, no split), dryer (1 hour), EV charging
    (5 hours, can split, finish by 7am). Returns when to run it, the average
    price, and how much that saves compared with starting right now.
    """
    try:
        curve = comed.forward_curve(36)
    except Exception as exc:
        return _error(f"ComEd feed unavailable: {exc}")

    deadline = _next_occurrence(finish_by_hour) if finish_by_hour is not None else None
    window = (
        planner.cheapest_hours(curve, duration_hours, deadline)
        if can_split
        else planner.cheapest_block(curve, duration_hours, deadline)
    )
    if window is None:
        when = f" before {comed.fmt_hour(deadline)}" if deadline else ""
        return {
            "error": "not_enough_price_data",
            "spoken": f"I don't have enough price data to fit {duration_hours} hours{when} yet.",
        }

    now_avg = planner.run_now_cost(curve, duration_hours)
    savings_pct = round((now_avg - window.avg_cents) / now_avg * 100) if now_avg else None

    result = {
        "start": comed.fmt_day_hour(window.start),
        "end": comed.fmt_day_hour(window.end),
        "hours": [comed.fmt_day_hour(h.start) for h in window.hours],
        "is_one_block": window.is_contiguous,
        "average_cents_per_kwh": window.avg_cents,
        "if_started_now_cents_per_kwh": now_avg,
        "savings_vs_now_percent": savings_pct,
    }
    if energy_kwh:
        result["estimated_cost_dollars"] = planner.dollars(energy_kwh, window.avg_cents)
        if now_avg:
            result["estimated_cost_if_now_dollars"] = planner.dollars(energy_kwh, now_avg)

    if window.is_contiguous:
        spoken = f"Best time is {comed.fmt_day_hour(window.start)}, running until {comed.fmt_hour(window.end)}"
    else:
        spoken = f"Best is to split it across {len(window.hours)} hours, starting {comed.fmt_day_hour(window.start)}"
    spoken += f", averaging {window.avg_cents:.1f} cents"
    if savings_pct and savings_pct > 0:
        spoken += f", about {savings_pct} percent cheaper than starting now"
    spoken += "."

    # Before ~4:30pm CT we only know today's prices. If the job could run
    # later than what we can see, say so: overnight is usually cheaper.
    known_until = curve[-1].start + timedelta(hours=1) if curve else None
    if known_until and (deadline is None or deadline > known_until) and not comed.tomorrow_prices():
        result["note"] = (
            "Only today's prices are published so far. Tomorrow's come out around "
            "4:30pm Central, and overnight hours are usually cheapest, so this may improve."
        )
        spoken += " Tomorrow's prices aren't out yet, so check back after 4:30 Central, overnight is usually cheaper."
        result["prices_known_until"] = comed.fmt_day_hour(known_until)

    result["spoken"] = spoken
    return result


@mcp.tool
def get_day_prices(
    day: Annotated[str, Field(description="Date as YYYY-MM-DD. Use for past days, e.g. reviewing a price spike.")],
) -> dict:
    """Get one day's 24 hourly prices: day-ahead estimate and actual settled price.

    Good for 'what happened yesterday?' or replaying a past price spike.
    """
    try:
        target = date.fromisoformat(day)
    except ValueError:
        return {"error": "bad_date", "spoken": "I need the date as year, month, day."}
    if target > comed.now().date():
        return {"error": "future_date", "spoken": "That's in the future. Ask me for the forecast instead."}

    try:
        hours = comed.day_prices(target)
    except Exception as exc:
        return _error(f"ComEd feed unavailable: {exc}")
    settled = [h for h in hours if h.actual is not None]
    if not hours:
        return _error("No prices for that day.")

    peak = max(settled or hours, key=lambda h: h.best)
    low = min(settled or hours, key=lambda h: h.best)
    return {
        "date": target.isoformat(),
        "hours": [
            {"start": comed.fmt_hour(h.start), "estimated": h.estimated, "actual": h.actual}
            for h in hours
        ],
        "peak": {"start": comed.fmt_hour(peak.start), "cents_per_kwh": peak.best},
        "low": {"start": comed.fmt_hour(low.start), "cents_per_kwh": low.best},
        "spoken": (
            f"On {target.strftime('%A, %B %-d')}, prices peaked at {peak.best:.1f} cents "
            f"at {comed.fmt_hour(peak.start)} and bottomed at {low.best:.1f} cents at {comed.fmt_hour(low.start)}."
        ),
    }


# ================================================================ autopilot
@mcp.tool
def run_autopilot(
    devices: Annotated[
        list[str] | None,
        Field(description="Which jobs to schedule: any of 'ev', 'dishwasher', 'dryer'. Omit for all three."),
    ] = None,
) -> dict:
    """Plan and schedule tonight: put each job in its cheapest hours, within the
    household's guardrails (EV ready by its deadline and target charge).

    Use for "autopilot tonight", "plan my night", "schedule everything".
    The plan is saved, so it persists across conversations.
    """
    try:
        return home.run_autopilot(devices)
    except Exception as exc:
        return _error(f"Autopilot failed: {exc}")


@mcp.tool
def get_home_status() -> dict:
    """What the home is doing: each device's state, tonight's saved plan, the
    household's guardrails, recent autopilot actions, and total money saved.

    Use for "what's running?", "what did you do?", "how much have I saved?",
    or to recall settings from earlier sessions.
    """
    s = home.status()
    running = [t["name"].lower() for t in s["devices"] if t["state"] in ("charging", "running")]
    planned = [f"{p['label'].lower()} {p['start']}" for p in s["plan"]]
    spoken = (f"Right now the {' and '.join(running)} {'is' if len(running) == 1 else 'are'} on. "
              if running else "Nothing's running right now. ")
    if planned:
        spoken += "Planned: " + ", ".join(planned) + ". "
    spoken += f"Autopilot has saved you ${s['saved_total_dollars']:.2f} so far."
    s["spoken"] = spoken
    return s


@mcp.tool
def update_settings(
    ev_ready_by_hour: Annotated[int | None, Field(ge=0, le=23, description="EV must be charged by this hour (24h)")] = None,
    ev_target_percent: Annotated[int | None, Field(ge=20, le=100, description="Charge the EV to this percent")] = None,
    max_indoor_temp_f: Annotated[int | None, Field(ge=60, le=90, description="Never let the house get warmer than this")] = None,
    min_indoor_temp_f: Annotated[int | None, Field(ge=50, le=80, description="Never let the house get colder than this")] = None,
    spike_threshold_cents: Annotated[float | None, Field(ge=1, le=100, description="Autopilot reacts on its own above this price")] = None,
) -> dict:
    """Change the household's autopilot guardrails. They're saved and apply to
    every future plan, e.g. "I need the car by 6 tomorrow", "charge to 90 percent",
    "react if power goes over 8 cents"."""
    result = home.update_guardrails(
        ev_ready_by_hour=ev_ready_by_hour, ev_target_percent=ev_target_percent,
        max_indoor_temp_f=max_indoor_temp_f, min_indoor_temp_f=min_indoor_temp_f,
        spike_threshold_cents=spike_threshold_cents,
    )
    changed = result["changed"]
    result["spoken"] = ("Got it, I'll remember that." if changed else "Nothing to change.")
    return result


@mcp.tool
def control_device(
    device: Annotated[str, Field(description="'ev', 'dishwasher', 'dryer', or 'thermostat'")],
    action: Annotated[str, Field(description="'start', 'stop', or 'pause'")],
) -> dict:
    """Manually start, stop, or pause a device (overrides the autopilot for it)."""
    return home.control(device.lower().strip(), action.lower().strip())


@mcp.tool
def check_for_price_spike() -> dict:
    """Check the live price against the household's spike threshold. If it's a
    spike, the autopilot acts immediately on its own: pauses EV charging and
    reschedules it before the deadline, delays the dryer, eases the thermostat
    within comfort limits, and reports the money saved.

    The OffPeak watcher calls this every few minutes; you can also call it.
    """
    try:
        return home.check_for_spike()
    except Exception as exc:
        return _error(f"Spike check failed: {exc}")


@mcp.tool
def start_spike_replay() -> dict:
    """Demo mode: replay an evening price spike so you can watch the autopilot
    react. Sets the scene (car charging, dryer running), then prices climb past
    the threshold over the next few checks."""
    return home.start_spike_demo()


def main() -> None:
    host = os.getenv("OFFPEAK_HOST", "127.0.0.1")
    port = int(os.getenv("OFFPEAK_PORT", "8000"))
    mcp.run(transport="http", host=host, port=port)  # Streamable HTTP at /mcp


if __name__ == "__main__":
    main()
