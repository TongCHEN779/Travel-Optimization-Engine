"""Core domain types.

All objectives are stored as *integers* (price in cents, time in minutes, risk in
micro-units) so that path costs are exactly additive and dominance comparisons
are free of floating-point drift. This lets us verify the exact algorithms
against brute force with strict equality.
"""
from __future__ import annotations

from dataclasses import dataclass, field

MINUTES_PER_DAY = 1440

# Objective vector layout (all minimised).
OBJECTIVES = ("price", "duration", "stops", "wait", "risk")
N_OBJ = len(OBJECTIVES)
PRICE, DURATION, STOPS, WAIT, RISK = range(N_OBJ)

Vec = tuple[int, int, int, int, int]


@dataclass(frozen=True, slots=True)
class Flight:
    id: int
    origin: str
    dest: str
    dep: int  # minutes since scenario epoch (day 0, 00:00)
    arr: int
    price_cents: int  # per passenger
    airline: str
    risk_micro: int  # -log(1 - p_disruption) * 1e6, additive survival-log risk
    seats: int = 9

    @property
    def duration(self) -> int:
        return self.arr - self.dep

    @property
    def dep_day(self) -> int:
        return self.dep // MINUTES_PER_DAY

    @property
    def arr_day(self) -> int:
        return self.arr // MINUTES_PER_DAY


@dataclass(frozen=True, slots=True)
class Airport:
    code: str
    name: str
    x: float
    y: float
    is_hub: bool = False


@dataclass(frozen=True, slots=True)
class Constraints:
    """Hard constraints applied to a single leg (and checked again on totals)."""

    max_stops: int = 2
    min_connection: int = 60  # minutes
    max_layover: int = 480  # minutes
    passengers: int = 1
    max_price_cents: int | None = None  # per-leg upper bound (total checked later)
    max_duration: int | None = None
    max_wait: int | None = None
    max_risk_micro: int | None = None

    def bounds(self) -> tuple[float, ...]:
        inf = float("inf")
        return (
            inf if self.max_price_cents is None else self.max_price_cents,
            inf if self.max_duration is None else self.max_duration,
            self.max_stops,
            inf if self.max_wait is None else self.max_wait,
            inf if self.max_risk_micro is None else self.max_risk_micro,
        )


@dataclass(frozen=True, slots=True)
class LegQuery:
    origin: str
    dest: str
    dep_from: int  # earliest departure of first flight (minutes)
    dep_to: int  # latest departure of first flight (minutes, inclusive)
    constraints: Constraints = field(default_factory=Constraints)


@dataclass(frozen=True, slots=True)
class RoundTripQuery:
    origin: str
    dest: str
    depart_from_day: int
    depart_to_day: int  # inclusive
    min_stay_days: int = 1
    max_stay_days: int = 14
    constraints: Constraints = field(default_factory=Constraints)


@dataclass(frozen=True, slots=True)
class Itinerary:
    """A path (one leg) or a concatenation of legs (round trip)."""

    flights: tuple[int, ...]  # flight ids in travel order
    vec: Vec
    split: int | None = None  # index where the return leg starts (round trips)
