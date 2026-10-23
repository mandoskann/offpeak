"""ComEd Hourly Pricing client.

ComEd publishes the electricity supply price for its Hourly Pricing customers
(Chicago area, PJM's ComEd zone) through free, public feeds:
  https://hourlypricing.comed.com/hp-api/

Feeds we use (prices are in cents per kWh):
  - 5minutefeed         JSON, real-time 5-minute prices, last 24 hours
  - currenthouraverage  JSON, running average for the current hour
  - pricingtabledual    HTML rows, one day: day-ahead estimate + actual settled, per hour
  - pricingtabledaynexttomorrow
                        HTML rows, tomorrow's day-ahead estimates. Empty until
                        ComEd publishes them, around 4:30pm Central.

Hourly rows are labeled by HOUR ENDING ("3:00 PM" = the 2pm-3pm hour). We
convert everything to HOUR STARTING, because that's how people think about
"run the dishwasher at 2pm".

Set OFFPEAK_OFFLINE=1 to use built-in sample data instead of the live API
(for tests, demos, and machines that can't reach ComEd).

Hour-ending parsing approach adapted from the MIT-licensed
comed-hourly-pricing library (github.com/jjlawren/comed-hourly-pricing).
"""

from __future__ import annotations

import html
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

API_URL = "https://hourlypricing.comed.com/api"
TABLE_URL = "https://hourlypricing.comed.com/rrtp/ServletFeed"
CHICAGO = ZoneInfo("America/Chicago")

# How long to reuse a response before asking ComEd again (seconds)
CACHE_TTL = {
    "5minutefeed": 60,
    "currenthouraverage": 60,
    "dual": 300,
    "nextday": 600,
}


@dataclass
class PricePoint:
    """One real-time reading."""

    time: datetime  # timezone-aware, America/Chicago
    cents_per_kwh: float


@dataclass
class HourPrice:
    """One hour of prices. `start` is the beginning of the hour, Chicago time."""

    start: datetime
    estimated: float | None  # day-ahead estimate, cents/kWh
    actual: float | None = None  # settled real price, cents/kWh (None until settled)
    projected: bool = False  # True if estimated from earlier hours (tomorrow not published yet)

    @property
    def best(self) -> float | None:
        """Actual if we have it, otherwise the estimate."""
        return self.actual if self.actual is not None else self.estimated


_cache: dict[str, tuple[float, object]] = {}


def now() -> datetime:
    """Current time in Chicago. Tests can monkeypatch this."""
    return datetime.now(CHICAGO)


def offline() -> bool:
    return os.getenv("OFFPEAK_OFFLINE", "").strip().lower() in {"1", "true", "yes"}


def _cached(key: str, ttl: int, loader):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    value = loader()
    _cache[key] = (time.time(), value)
    return value


def clear_cache() -> None:
    _cache.clear()


# ---------------------------------------------------------------- sample data
def _sample_curve(hour: int, day_seed: int) -> float:
    """A realistic-looking shoulder-season day: cheap overnight, evening peak."""
    base = {
        0: 2.1, 1: 1.8, 2: 1.6, 3: 1.5, 4: 1.6, 5: 2.0, 6: 2.8, 7: 3.4,
        8: 3.3, 9: 3.1, 10: 3.0, 11: 3.0, 12: 3.1, 13: 3.3, 14: 3.6, 15: 4.2,
        16: 5.4, 17: 7.9, 18: 8.6, 19: 6.1, 20: 4.4, 21: 3.5, 22: 2.9, 23: 2.4,
    }[hour]
    return round(base + ((hour * 7 + day_seed) % 5) * 0.1, 1)


def _sample_json(feed: str) -> list[dict]:
    now_ms = int(time.time() * 1000)
    if feed == "currenthouraverage":
        hour = now().hour
        return [{"millisUTC": str(now_ms), "price": str(_sample_curve(hour, 1))}]
    rows = []
    for i in range(288):  # 24h of 5-minute readings, newest first (like ComEd)
        t = now_ms - i * 5 * 60 * 1000
        hour = datetime.fromtimestamp(t / 1000, CHICAGO).hour
        rows.append({"millisUTC": str(t), "price": f"{_sample_curve(hour, 1) + (i % 3) * 0.2 - 0.2:.1f}"})
    return rows


def _hour_label(hour_ending: int) -> str:
    h = hour_ending % 24
    suffix = "AM" if h < 12 else "PM"
    return f"{(h % 12) or 12}:00 {suffix}"


def _sample_table(day: date, with_actual: bool) -> str:
    rows = []
    current = now()
    for start_hour in range(24):
        est = _sample_curve(start_hour, day.toordinal())
        cells = [f"<td>{_hour_label(start_hour + 1)}</td>", f"<td>{est}&cent;</td>"]
        if with_actual:
            hour_end = datetime(day.year, day.month, day.day, tzinfo=CHICAGO) + timedelta(hours=start_hour + 1)
            actual = f"{est + 0.3:.1f}&cent;" if hour_end <= current else "n/a"
            cells.append(f"<td>{actual}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return "\n".join(rows)


# ---------------------------------------------------------------- fetching
def _get(url: str, params: dict) -> str:
    resp = httpx.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.text


def fetch(feed: str) -> list[PricePoint]:
    """Real-time JSON feeds: 'currenthouraverage' or '5minutefeed'. Oldest first."""

    def load():
        if offline():
            rows = _sample_json(feed)
        else:
            rows = json.loads(_get(API_URL, {"type": feed, "format": "json"}))
        return parse_json(rows)

    return _cached(feed, CACHE_TTL[feed], load)


def day_prices(day: date) -> list[HourPrice]:
    """All 24 hours for one day: day-ahead estimate + actual where settled."""

    def load():
        body = (
            _sample_table(day, with_actual=True)
            if offline()
            else _get(TABLE_URL, {"type": "pricingtabledual", "date": day.strftime("%Y%m%d")})
        )
        return parse_table(body, day, has_actual=True)

    return _cached(f"dual:{day}", CACHE_TTL["dual"], load)


def tomorrow_prices() -> list[HourPrice]:
    """Tomorrow's day-ahead estimates. Empty list until ComEd publishes (~4:30pm CT)."""
    tomorrow = (now() + timedelta(days=1)).date()

    def load():
        if offline():
            # pretend it's published after 4:30pm, like the real feed
            published = now().hour * 60 + now().minute >= 16 * 60 + 30
            body = _sample_table(tomorrow, with_actual=False) if published else ""
        else:
            body = _get(TABLE_URL, {"type": "pricingtabledaynexttomorrow"})
        rows = parse_table(body, tomorrow, has_actual=False)
        # Before publishing, the feed can return placeholder rows with no prices
        return [h for h in rows if h.estimated is not None]

    return _cached(f"next:{tomorrow}", CACHE_TTL["nextday"], load)


def forward_curve(hours: int = 24) -> list[HourPrice]:
    """Best available hourly prices from the current hour forward.

    Uses today's day-ahead estimates for the rest of today, then tomorrow's
    once published. This is what the autopilot plans against.
    """
    current_hour = now().replace(minute=0, second=0, microsecond=0)
    today = day_prices(current_hour.date())
    tomorrow = tomorrow_prices()
    candidates = today + tomorrow
    upcoming = [h for h in candidates if h.start >= current_hour and h.estimated is not None]
    upcoming.sort(key=lambda h: h.start)

    # Before ComEd publishes tomorrow (~4:30pm Central), project the missing
    # hours from the same clock hours today (the best available guess), and
    # flag them so tools can say they're estimates.
    if not tomorrow and len(upcoming) < hours:
        known = {h.start for h in upcoming}
        for h in sorted(today, key=lambda h: h.start):
            if h.best is None:
                continue
            start = h.start + timedelta(days=1)
            if start not in known and start >= current_hour:
                upcoming.append(HourPrice(start=start, estimated=h.best, projected=True))
                known.add(start)
        upcoming.sort(key=lambda h: h.start)
    return upcoming[:hours]


# ---------------------------------------------------------------- parsing
_ROW_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_CELL_RE = re.compile(r"<td\b[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_HOUR_RE = re.compile(r"(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?", re.IGNORECASE)


def _clean(cell: str) -> str:
    return html.unescape(_TAG_RE.sub("", cell)).strip()


def _cents(cell: str) -> float | None:
    text = _clean(cell).rstrip("¢").strip()
    if not text or text.lower() == "n/a":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_json(rows: list[dict]) -> list[PricePoint]:
    points = []
    for r in rows:
        try:
            ts = datetime.fromtimestamp(int(r["millisUTC"]) / 1000, timezone.utc)
            points.append(PricePoint(ts.astimezone(CHICAGO), float(r["price"])))
        except (KeyError, ValueError, TypeError):
            continue  # skip malformed rows instead of crashing
    points.sort(key=lambda p: p.time)
    return points


def parse_table(body: str, day: date, has_actual: bool) -> list[HourPrice]:
    """Parse ComEd's <tr><td>hour ending</td><td>price</td>[<td>actual</td>]</tr> rows."""
    midnight = datetime(day.year, day.month, day.day, tzinfo=CHICAGO)
    hours: dict[datetime, HourPrice] = {}
    for row in _ROW_RE.findall(body or ""):
        cells = _CELL_RE.findall(row)
        if len(cells) < 2:
            continue
        match = _HOUR_RE.search(_clean(cells[0]))
        if not match:
            continue
        hour = int(match.group(1)) % 12 + (12 if match.group(3).lower() == "p" else 0)
        hour_ending = hour if hour != 0 else 24  # "12:00 AM" ends the last hour of the day
        start = midnight + timedelta(hours=hour_ending - 1)
        actual = _cents(cells[2]) if has_actual and len(cells) > 2 else None
        hours[start] = HourPrice(start=start, estimated=_cents(cells[1]), actual=actual)
    return [hours[k] for k in sorted(hours)]


# ---------------------------------------------------------------- helpers
def price_level(cents: float) -> str:
    """Rough plain-English label for a ComEd supply price (cents/kWh)."""
    if cents < 0:
        return "negative (you're basically paid to use power)"
    if cents < 3:
        return "low"
    if cents < 6:
        return "normal"
    if cents < 10:
        return "high"
    return "very high (spike)"


def fmt_hour(dt: datetime) -> str:
    """'2 AM', '5 PM'."""
    return dt.strftime("%I %p").lstrip("0")


def fmt_day_hour(dt: datetime) -> str:
    """'tonight at 2 AM', 'today at 5 PM', 'tomorrow at 3 PM'."""
    today = now().date()
    if dt.date() == today:
        when = "tonight" if dt.hour >= 20 else "today"
    elif dt.date() == today + timedelta(days=1):
        when = "tonight" if dt.hour < 6 else "tomorrow"
    else:
        when = dt.strftime("%A")
    return f"{when} at {fmt_hour(dt)}"
