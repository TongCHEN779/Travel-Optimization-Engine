"""Global world model: REAL airports/geography/carriers, SIMULATED schedules and prices.

Real:      IATA codes, airport/city/country names, coordinates, standard UTC offsets, calendar dates.
Simulated: which routes exist, timetables, fares, disruption risk and which carrier flies a route.
           None of this is a real offer; the UI says so.

The schedule is a set of *weekly templates*; `instantiate` expands them for a range of real calendar
days. Prices/seat counts use integer-only hashing so the TypeScript port (frontend/lib/world.ts)
produces bit-identical flights (checked by `npm run verify`).

Time convention: minutes since 2024-01-01 00:00 UTC. Offsets are *standard* time (no DST), a
documented simplification.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np

from .models import MINUTES_PER_DAY, Flight

EPOCH = date(2024, 1, 1)  # a Monday: weekday(day_index) = day_index % 7


def day_index(d: date) -> int:
    return (d - EPOCH).days


# code, name, city, country, region, lat, lon, standard UTC offset (hours), network hub
_A = [
    # North America
    ("JFK", "John F. Kennedy Intl", "New York", "United States", "North America", 40.64, -73.78, -5, 1),
    ("LAX", "Los Angeles Intl", "Los Angeles", "United States", "North America", 33.94, -118.41, -8, 1),
    ("ORD", "O'Hare Intl", "Chicago", "United States", "North America", 41.98, -87.90, -6, 1),
    ("ATL", "Hartsfield-Jackson Intl", "Atlanta", "United States", "North America", 33.64, -84.43, -5, 0),
    ("SFO", "San Francisco Intl", "San Francisco", "United States", "North America", 37.62, -122.38, -8, 0),
    ("MIA", "Miami Intl", "Miami", "United States", "North America", 25.79, -80.29, -5, 1),
    ("SEA", "Seattle-Tacoma Intl", "Seattle", "United States", "North America", 47.45, -122.31, -8, 0),
    ("DFW", "Dallas/Fort Worth Intl", "Dallas", "United States", "North America", 32.90, -97.04, -6, 0),
    ("BOS", "Logan Intl", "Boston", "United States", "North America", 42.36, -71.01, -5, 0),
    ("YYZ", "Toronto Pearson Intl", "Toronto", "Canada", "North America", 43.68, -79.63, -5, 1),
    ("YVR", "Vancouver Intl", "Vancouver", "Canada", "North America", 49.19, -123.18, -8, 0),
    ("MEX", "Benito Juárez Intl", "Mexico City", "Mexico", "North America", 19.44, -99.07, -6, 0),
    # South America
    ("GRU", "São Paulo/Guarulhos Intl", "São Paulo", "Brazil", "South America", -23.43, -46.47, -3, 1),
    ("GIG", "Galeão Intl", "Rio de Janeiro", "Brazil", "South America", -22.81, -43.25, -3, 0),
    ("EZE", "Ministro Pistarini Intl", "Buenos Aires", "Argentina", "South America", -34.82, -58.54, -3, 0),
    ("SCL", "Arturo Merino Benítez Intl", "Santiago", "Chile", "South America", -33.39, -70.79, -4, 0),
    ("LIM", "Jorge Chávez Intl", "Lima", "Peru", "South America", -12.02, -77.11, -5, 0),
    ("BOG", "El Dorado Intl", "Bogotá", "Colombia", "South America", 4.70, -74.15, -5, 0),
    ("PTY", "Tocumen Intl", "Panama City", "Panama", "South America", 9.07, -79.38, -5, 1),
    # Europe
    ("LHR", "Heathrow", "London", "United Kingdom", "Europe", 51.47, -0.45, 0, 1),
    ("CDG", "Charles de Gaulle", "Paris", "France", "Europe", 49.01, 2.55, 1, 1),
    ("FRA", "Frankfurt am Main", "Frankfurt", "Germany", "Europe", 50.03, 8.57, 1, 1),
    ("AMS", "Schiphol", "Amsterdam", "Netherlands", "Europe", 52.31, 4.76, 1, 0),
    ("MAD", "Adolfo Suárez Madrid-Barajas", "Madrid", "Spain", "Europe", 40.49, -3.57, 1, 0),
    ("FCO", "Leonardo da Vinci–Fiumicino", "Rome", "Italy", "Europe", 41.80, 12.25, 1, 0),
    ("IST", "Istanbul Airport", "Istanbul", "Türkiye", "Europe", 41.26, 28.74, 3, 1),
    ("ZRH", "Zürich Airport", "Zürich", "Switzerland", "Europe", 47.46, 8.55, 1, 0),
    ("CPH", "Copenhagen Airport", "Copenhagen", "Denmark", "Europe", 55.62, 12.66, 1, 0),
    ("ATH", "Athens Intl", "Athens", "Greece", "Europe", 37.94, 23.94, 2, 0),
    ("LIS", "Humberto Delgado", "Lisbon", "Portugal", "Europe", 38.77, -9.13, 0, 0),
    ("DUB", "Dublin Airport", "Dublin", "Ireland", "Europe", 53.43, -6.27, 0, 0),
    ("MUC", "Munich Airport", "Munich", "Germany", "Europe", 48.35, 11.79, 1, 0),
    ("VIE", "Vienna Intl", "Vienna", "Austria", "Europe", 48.11, 16.57, 1, 0),
    # Middle East
    ("DXB", "Dubai Intl", "Dubai", "United Arab Emirates", "Middle East", 25.25, 55.36, 4, 1),
    ("DOH", "Hamad Intl", "Doha", "Qatar", "Middle East", 25.27, 51.61, 3, 1),
    ("AUH", "Zayed Intl", "Abu Dhabi", "United Arab Emirates", "Middle East", 24.43, 54.65, 4, 0),
    ("TLV", "Ben Gurion Intl", "Tel Aviv", "Israel", "Middle East", 32.01, 34.89, 2, 0),
    # Africa
    ("JNB", "O. R. Tambo Intl", "Johannesburg", "South Africa", "Africa", -26.14, 28.25, 2, 1),
    ("CPT", "Cape Town Intl", "Cape Town", "South Africa", "Africa", -33.97, 18.60, 2, 0),
    ("CAI", "Cairo Intl", "Cairo", "Egypt", "Africa", 30.12, 31.41, 2, 0),
    ("ADD", "Bole Intl", "Addis Ababa", "Ethiopia", "Africa", 8.98, 38.80, 3, 1),
    ("NBO", "Jomo Kenyatta Intl", "Nairobi", "Kenya", "Africa", -1.32, 36.93, 3, 0),
    ("LOS", "Murtala Muhammed Intl", "Lagos", "Nigeria", "Africa", 6.58, 3.32, 1, 0),
    ("CMN", "Mohammed V Intl", "Casablanca", "Morocco", "Africa", 33.37, -7.59, 1, 0),
    # Asia
    ("SIN", "Changi", "Singapore", "Singapore", "Asia", 1.36, 103.99, 8, 1),
    ("HKG", "Hong Kong Intl", "Hong Kong", "Hong Kong SAR", "Asia", 22.31, 113.91, 8, 1),
    ("NRT", "Narita Intl", "Tokyo", "Japan", "Asia", 35.77, 140.39, 9, 1),
    ("HND", "Haneda", "Tokyo", "Japan", "Asia", 35.55, 139.78, 9, 0),
    ("KIX", "Kansai Intl", "Osaka", "Japan", "Asia", 34.43, 135.24, 9, 0),
    ("ICN", "Incheon Intl", "Seoul", "South Korea", "Asia", 37.46, 126.44, 9, 0),
    ("PEK", "Beijing Capital Intl", "Beijing", "China", "Asia", 40.08, 116.58, 8, 0),
    ("PVG", "Shanghai Pudong Intl", "Shanghai", "China", "Asia", 31.14, 121.81, 8, 0),
    ("TPE", "Taoyuan Intl", "Taipei", "Taiwan", "Asia", 25.08, 121.23, 8, 0),
    ("BKK", "Suvarnabhumi", "Bangkok", "Thailand", "Asia", 13.69, 100.75, 7, 0),
    ("KUL", "Kuala Lumpur Intl", "Kuala Lumpur", "Malaysia", "Asia", 2.75, 101.71, 8, 0),
    ("CGK", "Soekarno–Hatta Intl", "Jakarta", "Indonesia", "Asia", -6.13, 106.66, 7, 0),
    ("MNL", "Ninoy Aquino Intl", "Manila", "Philippines", "Asia", 14.51, 121.02, 8, 0),
    ("SGN", "Tan Son Nhat Intl", "Ho Chi Minh City", "Vietnam", "Asia", 10.82, 106.66, 7, 0),
    ("DEL", "Indira Gandhi Intl", "Delhi", "India", "Asia", 28.56, 77.10, 5.5, 1),
    ("BOM", "Chhatrapati Shivaji Maharaj Intl", "Mumbai", "India", "Asia", 19.09, 72.87, 5.5, 0),
    ("CMB", "Bandaranaike Intl", "Colombo", "Sri Lanka", "Asia", 7.18, 79.88, 5.5, 0),
    # Oceania
    ("SYD", "Kingsford Smith", "Sydney", "Australia", "Oceania", -33.94, 151.18, 10, 1),
    ("MEL", "Melbourne Airport", "Melbourne", "Australia", "Oceania", -37.67, 144.84, 10, 0),
    ("BNE", "Brisbane Airport", "Brisbane", "Australia", "Oceania", -27.38, 153.12, 10, 0),
    ("PER", "Perth Airport", "Perth", "Australia", "Oceania", -31.94, 115.97, 8, 0),
    ("AKL", "Auckland Airport", "Auckland", "New Zealand", "Oceania", -37.01, 174.79, 12, 0),
]

# Real carriers per home region, with a simulated fare/speed/reliability tier.
TIERS = {"premium": (1.35, 880.0, 0.04), "standard": (1.00, 840.0, 0.08), "budget": (0.70, 780.0, 0.16)}
CARRIERS: dict[str, list[tuple[str, str]]] = {
    "North America": [("Delta Air Lines", "standard"), ("United Airlines", "standard"), ("American Airlines", "standard"),
                      ("Air Canada", "standard"), ("Southwest Airlines", "budget"), ("Alaska Airlines", "premium")],
    "South America": [("LATAM Airlines", "standard"), ("Avianca", "standard"), ("Copa Airlines", "premium"), ("Sky Airline", "budget")],
    "Europe": [("Lufthansa", "premium"), ("Air France", "standard"), ("British Airways", "standard"),
               ("KLM", "standard"), ("Turkish Airlines", "standard"), ("Ryanair", "budget"), ("easyJet", "budget")],
    "Middle East": [("Emirates", "premium"), ("Qatar Airways", "premium"), ("Etihad Airways", "premium"), ("flydubai", "budget")],
    "Africa": [("Ethiopian Airlines", "standard"), ("South African Airways", "standard"), ("Kenya Airways", "standard"), ("Royal Air Maroc", "standard")],
    "Asia": [("Singapore Airlines", "premium"), ("Cathay Pacific", "premium"), ("ANA", "premium"), ("Korean Air", "standard"),
             ("Air India", "standard"), ("Thai Airways", "standard"), ("AirAsia", "budget"), ("Scoot", "budget")],
    "Oceania": [("Qantas", "premium"), ("Air New Zealand", "standard"), ("Virgin Australia", "standard"), ("Jetstar", "budget")],
}
AIRLINES: list[tuple[str, str]] = sorted({c for lst in CARRIERS.values() for c in lst})
_AIRLINE_IDX = {c[0]: i for i, c in enumerate(AIRLINES)}

MAX_RANGE_KM = 14500.0
BUDGET_MAX_KM = 5000.0


@dataclass(frozen=True)
class AirportInfo:
    code: str
    name: str
    city: str
    country: str
    region: str
    lat: float
    lon: float
    offset_min: int
    hub: bool


@dataclass(frozen=True)
class Template:
    origin: str
    dest: str
    local_dep: int  # minutes after local midnight
    duration: int  # minutes
    base_price: int  # cents per passenger
    airline: int  # index into AIRLINES
    risk: int  # micro-units
    days_mask: int  # bit w set => operates on weekday w (0 = Monday)


@dataclass
class World:
    airports: dict[str, AirportInfo]
    templates: list[Template]


def haversine_km(a: AirportInfo, b: AirportInfo) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dl = math.radians(b.lon - a.lon)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def build_world(seed: int = 2024) -> World:
    rng = np.random.default_rng(seed)
    ap = {a[0]: AirportInfo(a[0], a[1], a[2], a[3], a[4], a[5], a[6], int(round(a[7] * 60)), bool(a[8])) for a in _A}
    hubs = [c for c, a in ap.items() if a.hub]
    spokes = [c for c in ap if c not in hubs]
    dist = lambda x, y: haversine_km(ap[x], ap[y])  # noqa: E731

    # (pair, frequency per day, operating days mask)
    pairs: dict[tuple[str, str], tuple[int, int]] = {}
    for i, h1 in enumerate(hubs):
        for h2 in hubs[i + 1:]:
            if dist(h1, h2) <= MAX_RANGE_KM:
                pairs[(h1, h2)] = (2, 0b1111111)
    for s in spokes:
        for h in sorted(hubs, key=lambda h: dist(s, h))[:3]:
            pairs[tuple(sorted((s, h)))] = (int(rng.integers(1, 3)), 0b1111111 if rng.random() < 0.7 else 0b1110111)
    for i, s1 in enumerate(spokes):
        for s2 in spokes[i + 1:]:
            d = dist(s1, s2)
            p = 0.45 if d < 2500 else 0.12 if d < 8000 else 0.0  # nonstop spoke-to-spoke mostly short/medium haul
            if rng.random() < p:
                mask = int(rng.choice([0b1111111, 0b0101010, 0b1010101, 0b0111110]))
                pairs[tuple(sorted((s1, s2)))] = (1, mask)

    templates: list[Template] = []
    for (a, b), (freq, mask) in sorted(pairs.items()):
        d = dist(a, b)
        direct_spoke = a in spokes and b in spokes
        for o, t in ((a, b), (b, a)):
            # low-cost carriers only operate short/medium-haul routes
            carriers = [c for c in CARRIERS[ap[o].region] if c[1] != "budget" or d <= BUDGET_MAX_KM]
            for _ in range(freq):
                name, tier = carriers[int(rng.integers(0, len(carriers)))]
                pm, speed, p_dis = TIERS[tier]
                price = (55 + d * 0.08) * pm * rng.uniform(0.92, 1.12) * (1.4 if direct_spoke else 1.0)
                p = min(0.5, p_dis * rng.uniform(0.7, 1.4) * (1.15 if ap[o].hub else 1.0))
                templates.append(Template(
                    o, t, int(rng.integers(6 * 60, 23 * 60)), int(d / speed * 60 + 40 + rng.integers(0, 15)),
                    int(round(price * 100)), _AIRLINE_IDX[name], int(round(-math.log(1 - p) * 1e6)), mask,
                ))
    return World(ap, templates)


def _hash32(tidx: int, day: int) -> int:
    return ((tidx * 7919 + day * 104729) * 2654435761) & 0xFFFFFFFF


def instantiate(world: World, day_from: int, day_to: int) -> list[Flight]:
    """Expand weekly templates for local origin-dates day_from..day_to (inclusive)."""
    out: list[Flight] = []
    for day in range(day_from, day_to + 1):
        wd = day % 7
        weekend = 8 if wd in (4, 6) else 0  # Fri/Sun demand uplift (percent)
        for ti, t in enumerate(world.templates):
            if not (t.days_mask >> wd) & 1:
                continue
            h = _hash32(ti, day)
            pct = 82 + (h >> 8) % 41 + weekend
            dep = day * MINUTES_PER_DAY + t.local_dep - world.airports[t.origin].offset_min
            out.append(Flight(
                id=day * 10000 + ti, origin=t.origin, dest=t.dest, dep=dep, arr=dep + t.duration,
                price_cents=t.base_price * pct // 100, airline=AIRLINES[t.airline][0], risk_micro=t.risk,
                seats=1 + (h >> 16) % 9,
            ))
    return out
