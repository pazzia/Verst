"""`RoadRateTolls` (ENG-02): tolls on a route with real geometry, priced per km of the road.

The world's explicit segments (`FakeTollRepository`) win where the route drives them. Every other run of
`RouteDetail.toll` is priced as its length x the road's rate from `resources/toll_rates.json` (category 1,
weekday and Friday to Sunday). A toll run on a road the table does not know is not costed: a price is never
invented.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, time
from decimal import ROUND_HALF_UP, Decimal

from verst_planner import resources
from verst_planner.domain.model import Route, TollHit, TollSegment
from verst_planner.ports import TollRepository

MIN_RUN_KM = 1.0
"""Shorter uncovered pieces are slivers of an explicit segment's ends, not a separate toll road."""


@dataclass(frozen=True, slots=True)
class RoadRate:
    ref: str
    weekday_rub_per_km: Decimal
    weekend_rub_per_km: Decimal | None
    confidence: str


@dataclass(frozen=True, slots=True)
class TollRates:
    as_of: date
    verified: bool
    by_ref: dict[str, RoadRate]

    @staticmethod
    def from_dict(d: dict[str, object]) -> TollRates:
        by_ref: dict[str, RoadRate] = {}
        roads = d["roads"]
        assert isinstance(roads, list)
        for r in roads:
            weekend = r.get("weekendRubPerKm")
            rate = RoadRate(
                str(r["ref"]),
                Decimal(str(r["weekdayRubPerKm"])),
                Decimal(str(weekend)) if weekend is not None else None,
                str(r.get("confidence", "low")),
            )
            for key in [rate.ref, *r.get("aliases", [])]:
                by_ref[_norm(str(key))] = rate
        return TollRates(date.fromisoformat(str(d["asOf"])), bool(d.get("verified", False)), by_ref)

    @staticmethod
    def from_resources() -> TollRates:
        return TollRates.from_dict(json.loads(resources.read_text("toll_rates.json")))

    def rate(self, road_ref: str | None) -> RoadRate | None:
        """The rate of the first ref of `road_ref` the table knows (OSM lists several refs with `;`)."""
        for part in (road_ref or "").replace(",", ";").split(";"):
            r = self.by_ref.get(_norm(part))
            if r is not None:
                return r
        return None


def _norm(ref: str) -> str:
    """Latin `M-11` and Cyrillic `M11` (any case, spaces) give one key: look-alikes to Cyrillic, no dashes."""
    s = ref.strip().upper().replace("-", "").replace(" ", "")
    return s.translate(_CYRILLIC)


_CYRILLIC = str.maketrans("MAP", "\u041c\u0410\u0420")


def _money(v: Decimal) -> Decimal:
    return v.quantize(Decimal(1), rounding=ROUND_HALF_UP)


class RoadRateTolls:
    def __init__(self, inner: TollRepository, rates: TollRates) -> None:
        self.inner = inner
        self.rates = rates

    def segments_on_route(self, route: Route) -> list[TollHit]:
        hits = list(self.inner.segments_on_route(route))
        covered = [(h.km_from, h.km_to) for h in hits]
        for ref, km_from, km_to in _toll_runs(route):
            rate = self.rates.rate(ref)
            if rate is None:
                continue
            for a, b in _uncovered(km_from, km_to, covered):
                if b - a < MIN_RUN_KM:
                    continue
                km = Decimal(str(round(b - a, 1)))
                day = _money(km * rate.weekday_rub_per_km)
                w = rate.weekend_rub_per_km
                weekend = _money(km * w) if w is not None else None
                seg = TollSegment(
                    id=f"rate:{rate.ref}:{round(a)}",
                    road_ref=rate.ref,
                    name_ru=rate.ref,
                    tariff_day_rub=day,
                    tariff_night_rub=day,  # night tariffs of these roads are not known
                    vehicle_class=1,
                    night_from=time(0),
                    night_to=time(0),
                    as_of=self.rates.as_of,
                    tariff_weekend_rub=weekend,
                )
                hits.append(TollHit(seg, a, b))
        hits.sort(key=lambda h: (h.km_from, h.segment.id))
        return hits


def _toll_runs(route: Route) -> list[tuple[str | None, float, float]]:
    """Consecutive toll details of one road merged into (ref, km_from, km_to)."""
    out: list[tuple[str | None, float, float]] = []
    for d in route.details:
        if not d.toll:
            continue
        a, b = route.cum_km[d.from_idx], route.cum_km[d.to_idx]
        if out and out[-1][0] == d.road_ref and abs(out[-1][2] - a) < 1e-6:
            out[-1] = (d.road_ref, out[-1][1], b)
        else:
            out.append((d.road_ref, a, b))
    return out


def _uncovered(a: float, b: float, covered: list[tuple[float, float]]) -> list[tuple[float, float]]:
    pieces = [(a, b)]
    for c0, c1 in covered:
        nxt: list[tuple[float, float]] = []
        for p0, p1 in pieces:
            if c1 <= p0 or c0 >= p1:
                nxt.append((p0, p1))
                continue
            if c0 > p0:
                nxt.append((p0, c0))
            if c1 < p1:
                nxt.append((c1, p1))
        pieces = nxt
    return pieces
