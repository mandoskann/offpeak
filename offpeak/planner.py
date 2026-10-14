"""Planning math: find the cheapest hours to run something.

Pure functions over a list of HourPrice, so they're easy to test and reuse
(the autopilot on Day 4 builds on these).

Two kinds of jobs:
  - contiguous: must run in one block (dishwasher, dryer, laundry)
  - splittable: can be spread across separate hours (EV charging)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from offpeak.comed import HourPrice


@dataclass
class Window:
    hours: list[HourPrice]  # the chosen hours, in time order

    @property
    def start(self) -> datetime:
        return self.hours[0].start

    @property
    def end(self) -> datetime:
        return self.hours[-1].start + timedelta(hours=1)

    @property
    def avg_cents(self) -> float:
        return round(sum(h.best for h in self.hours) / len(self.hours), 2)

    @property
    def is_contiguous(self) -> bool:
        return all(
            b.start - a.start == timedelta(hours=1) for a, b in zip(self.hours, self.hours[1:])
        )


def _eligible(curve: list[HourPrice], deadline: datetime | None) -> list[HourPrice]:
    hours = [h for h in curve if h.best is not None]
    if deadline is not None:
        hours = [h for h in hours if h.start + timedelta(hours=1) <= deadline]
    return sorted(hours, key=lambda h: h.start)


def cheapest_block(
    curve: list[HourPrice], duration: int, deadline: datetime | None = None
) -> Window | None:
    """Cheapest run of `duration` back-to-back hours that finishes by `deadline`."""
    hours = _eligible(curve, deadline)
    best: Window | None = None
    for i in range(len(hours) - duration + 1):
        block = hours[i : i + duration]
        candidate = Window(block)
        if not candidate.is_contiguous:
            continue  # gap in the data, skip
        if best is None or candidate.avg_cents < best.avg_cents:
            best = candidate
    return best


def cheapest_hours(
    curve: list[HourPrice], count: int, deadline: datetime | None = None
) -> Window | None:
    """Cheapest `count` hours (not necessarily back-to-back) before `deadline`."""
    hours = _eligible(curve, deadline)
    if len(hours) < count:
        return None
    chosen = sorted(hours, key=lambda h: h.best)[:count]
    return Window(sorted(chosen, key=lambda h: h.start))


def run_now_cost(curve: list[HourPrice], duration: int) -> float | None:
    """Average price if you started right now instead (for 'you save X%')."""
    hours = _eligible(curve, None)[:duration]
    if len(hours) < duration:
        return None
    return round(sum(h.best for h in hours) / duration, 2)


def dollars(kwh: float, cents_per_kwh: float) -> float:
    return round(kwh * cents_per_kwh / 100, 2)
