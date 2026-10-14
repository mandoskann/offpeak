"""ComEd Hourly Pricing client.

ComEd publishes the real-time electricity supply price for its Hourly Pricing
customers (Chicago area, PJM's ComEd zone) as a free, public JSON API:
  https://hourlypricing.comed.com/hp-api/

Prices come back in cents per kWh. Each reading has a UTC timestamp in
milliseconds ("millisUTC") and a price ("price"), both as strings.

Set OFFPEAK_OFFLINE=1 to use built-in sample data instead of the live API
(handy for tests, demos, and machines that can't reach ComEd).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx

BASE_URL = "https://hourlypricing.comed.com/api"
CHICAGO = ZoneInfo("America/Chicago")
CACHE_SECONDS = 60  # ComEd updates every 5 min; don't hammer it


@dataclass
class PricePoint:
    time: datetime  # timezone-aware, America/Chicago
    cents_per_kwh: float


_cache: dict[str, tuple[float, list[PricePoint]]] = {}


def _offline() -> bool:
    return os.getenv("OFFPEAK_OFFLINE", "").strip() in {"1", "true", "yes"}


def _sample(feed: str) -> list[dict]:
    """Fake readings shaped exactly like ComEd's JSON, for offline mode."""
    now_ms = int(time.time() * 1000)
    if feed == "currenthouraverage":
        return [{"millisUTC": str(now_ms), "price": "3.4"}]
    # 24h of 5-minute prices with an evening bump, newest first (like ComEd)
    rows = []
    for i in range(288):
        t = now_ms - i * 5 * 60 * 1000
        hour = datetime.fromtimestamp(t / 1000, CHICAGO).hour
        price = 2.2 + (4.5 if 16 <= hour <= 19 else 0.0) + (i % 7) * 0.15
        rows.append({"millisUTC": str(t), "price": f"{price:.1f}"})
    return rows


def _parse(rows: list[dict]) -> list[PricePoint]:
    points = []
    for r in rows:
        try:
            ts = datetime.fromtimestamp(int(r["millisUTC"]) / 1000, timezone.utc)
            points.append(PricePoint(ts.astimezone(CHICAGO), float(r["price"])))
        except (KeyError, ValueError, TypeError):
            continue  # skip malformed rows instead of crashing
    points.sort(key=lambda p: p.time)  # oldest -> newest
    return points


def fetch(feed: str) -> list[PricePoint]:
    """Fetch a ComEd feed: 'currenthouraverage' or '5minutefeed'."""
    hit = _cache.get(feed)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]

    if _offline():
        rows = _sample(feed)
    else:
        resp = httpx.get(BASE_URL, params={"type": feed, "format": "json"}, timeout=10)
        resp.raise_for_status()
        rows = resp.json()

    points = _parse(rows)
    _cache[feed] = (time.time(), points)
    return points


def price_level(cents: float) -> str:
    """Rough plain-English label for a supply price, in cents/kWh.

    Starting thresholds, to be tuned against real history on Day 2.
    """
    if cents < 0:
        return "negative (you're basically paid to use power)"
    if cents < 3:
        return "low"
    if cents < 6:
        return "normal"
    if cents < 10:
        return "high"
    return "very high (spike)"
