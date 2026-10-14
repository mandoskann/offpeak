"""OffPeak MCP server.

A self-hosted MCP server (Streamable HTTP) that gives an Alexa+ agent live
electricity prices. Day 1: one tool, get_live_price. More tools land daily.

Run:   python -m offpeak.server
URL:   http://localhost:8000/mcp
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastmcp import FastMCP

from offpeak import comed

load_dotenv()

mcp = FastMCP(
    name="OffPeak",
    instructions=(
        "OffPeak is a home energy autopilot. Use these tools to check live "
        "electricity prices before advising when to run appliances or charge an EV. "
        "Prices are the ComEd real-time supply price in cents per kWh."
    ),
    version="0.1.0",
)


@mcp.tool
def get_live_price() -> dict:
    """Get the live electricity supply price right now (ComEd, cents per kWh).

    Returns the latest 5-minute price, the current-hour average (what hourly
    pricing customers actually pay), a plain-English level, and a short
    sentence an Alexa voice response can read out loud.
    """
    hour_avg = comed.fetch("currenthouraverage")
    five_min = comed.fetch("5minutefeed")
    if not hour_avg or not five_min:
        return {"error": "ComEd price feed returned no data. Try again in a few minutes."}

    avg = hour_avg[-1]
    latest = five_min[-1]
    level = comed.price_level(avg.cents_per_kwh)

    # trend over the last 30 minutes (6 x 5-min readings)
    recent = five_min[-7:]
    change = round(recent[-1].cents_per_kwh - recent[0].cents_per_kwh, 2)
    trend = "rising" if change > 0.5 else "falling" if change < -0.5 else "steady"

    return {
        "current_hour_average_cents_per_kwh": avg.cents_per_kwh,
        "latest_5min_cents_per_kwh": latest.cents_per_kwh,
        "latest_5min_time": latest.time.strftime("%-I:%M %p %Z"),
        "level": level,
        "trend_last_30min": trend,
        "change_last_30min_cents": change,
        "source": "ComEd Hourly Pricing (PJM ComEd zone)",
        "spoken": (
            f"Power is {avg.cents_per_kwh:.1f} cents per kilowatt hour this hour, "
            f"which is {level.split(' (')[0]}, and it's {trend}."
        ),
    }


def main() -> None:
    host = os.getenv("OFFPEAK_HOST", "127.0.0.1")
    port = int(os.getenv("OFFPEAK_PORT", "8000"))
    mcp.run(transport="http", host=host, port=port)  # Streamable HTTP at /mcp


if __name__ == "__main__":
    main()
