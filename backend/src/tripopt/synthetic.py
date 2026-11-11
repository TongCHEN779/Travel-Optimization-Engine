"""Seeded synthetic flight-network generator (hub-and-spoke).

Designed so that objectives genuinely conflict:
  * nonstop spoke-to-spoke flights are fast but carry a price premium,
  * budget carriers are cheap but slower and more disruption-prone,
  * connecting via hubs is cheaper but adds duration, waiting and risk.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .models import MINUTES_PER_DAY, Airport, Flight

AIRLINES = {
    # name: (price multiplier, speed km/h, disruption probability per flight)
    "SkyPremium": (1.35, 850.0, 0.04),
    "Meridian": (1.00, 800.0, 0.08),
    "BudgetJet": (0.70, 740.0, 0.16),
}


@dataclass(frozen=True)
class SyntheticConfig:
    n_airports: int = 30
    n_hubs: int = 4
    days: int = 21
    spoke_direct_prob: float = 0.15  # chance a spoke pair has a nonstop route
    flights_per_route_day: int = 2
    seed: int = 7


@dataclass
class Dataset:
    airports: dict[str, Airport]
    flights: list[Flight]
    config: SyntheticConfig


def _code(i: int) -> str:
    a = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return a[(i // 26) % 26] + a[i % 26] + a[(i // 676) % 26 + 0]


def generate(cfg: SyntheticConfig = SyntheticConfig()) -> Dataset:
    rng = np.random.default_rng(cfg.seed)
    coords = rng.uniform(0, 5000, size=(cfg.n_airports, 2))  # km plane
    # hubs: the airports closest to the centroid of the map -> well connected
    centre = coords.mean(axis=0)
    hub_idx = set(np.argsort(np.linalg.norm(coords - centre, axis=1))[: cfg.n_hubs].tolist())
    airports = {
        _code(i): Airport(_code(i), f"Airport {_code(i)}", float(coords[i, 0]), float(coords[i, 1]), i in hub_idx)
        for i in range(cfg.n_airports)
    }
    codes = list(airports)
    hubs = [c for c in codes if airports[c].is_hub]

    def dist(a: str, b: str) -> float:
        pa, pb = airports[a], airports[b]
        return math.hypot(pa.x - pb.x, pa.y - pb.y)

    # route set (undirected pairs)
    routes: set[tuple[str, str]] = set()
    for i, h1 in enumerate(hubs):
        for h2 in hubs[i + 1 :]:
            routes.add((h1, h2))
    spokes = [c for c in codes if c not in hubs]
    for s in spokes:
        near = sorted(hubs, key=lambda h: dist(s, h))[:2]  # two nearest hubs
        for h in near:
            routes.add((s, h))
    for i, s1 in enumerate(spokes):
        for s2 in spokes[i + 1 :]:
            if rng.random() < cfg.spoke_direct_prob:
                routes.add((s1, s2))

    flights: list[Flight] = []
    fid = 0
    names = list(AIRLINES)
    for a, b in sorted(routes):
        d = dist(a, b)
        is_hub_route = airports[a].is_hub or airports[b].is_hub
        for o, t in ((a, b), (b, a)):
            for day in range(cfg.days):
                demand = 1.0 + 0.25 * math.sin(day / 3.0) + (0.2 if day % 7 in (4, 5) else 0.0)
                for _ in range(cfg.flights_per_route_day):
                    al = names[int(rng.choice(len(names), p=[0.25, 0.45, 0.30]))]
                    pm, speed, p_dis = AIRLINES[al]
                    dep = day * MINUTES_PER_DAY + int(rng.integers(5 * 60, 22 * 60))
                    dur = int(d / speed * 60 + 35 + rng.integers(0, 15))
                    price = (45 + d * 0.085) * pm * demand * rng.uniform(0.9, 1.15)
                    if not is_hub_route:
                        price *= 1.45  # nonstop convenience premium
                    p = min(0.5, p_dis * rng.uniform(0.7, 1.4) * (1.15 if airports[o].is_hub else 1.0))
                    flights.append(
                        Flight(
                            id=fid, origin=o, dest=t, dep=dep, arr=dep + dur,
                            price_cents=int(round(price * 100)), airline=al,
                            risk_micro=int(round(-math.log(1 - p) * 1e6)),
                            seats=int(rng.integers(1, 10)),
                        )
                    )
                    fid += 1
    return Dataset(airports, flights, cfg)
