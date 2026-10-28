"""`RoadRateTolls` (ENG-02): tolls on a route with real geometry, priced per km of the road; `CorridorTolls`
(acceptance 2026-10-28, QA B-1): tolls on an approximate route, by the toll corridor it follows.

The world's explicit segments (`FakeTollRepository`) win where the route drives them. Every other run of
`RouteDetail.toll` is priced as its length x the road's rate from `resources/toll_rates.json` (category 1,
weekday and Friday to Sunday). A toll run on a road the table does not know is not costed: a price is never
invented.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from datetime import date, time
from decimal import ROUND_HALF_UP, Decimal

from verst_planner import resources
from verst_planner.domain.model import LatLon, Route, TollHit, TollSegment
from verst_planner.geo.distance import haversine_km, project_on_segment
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


# ---------------------------------------------------------------------------------- approximate routes


@dataclass(frozen=True, slots=True)
class TollCorridor:
    """A toll road as a polyline through the towns it passes, with its whole-road price (toll_rates.json)."""

    ref: str
    anchors: tuple[LatLon, ...]
    weekday_rub: Decimal
    weekend_rub: Decimal | None

    def length_km(self) -> float:
        return sum(haversine_km(a, b) for a, b in itertools.pairwise(self.anchors))

    def project(self, p: LatLon) -> tuple[float, float]:
        """`(km along the polyline, distance from it)` of the nearest point of the corridor to `p`."""
        best = (0.0, float("inf"))
        along = 0.0
        for a, b in itertools.pairwise(self.anchors):
            seg = haversine_km(a, b)
            t, d = project_on_segment(p, a, b)
            if d < best[1]:
                best = (along + t * seg, d)
            along += seg
        return best


@dataclass(frozen=True, slots=True)
class TollCorridors:
    as_of: date
    follow_km: float
    min_span_km: float
    end_snap_km: float
    corridors: tuple[TollCorridor, ...]

    @staticmethod
    def from_dict(d: dict[str, object]) -> TollCorridors:
        rows = d["corridors"]
        assert isinstance(rows, list)
        out = []
        for c in rows:
            weekend = c.get("weekendRub")
            out.append(
                TollCorridor(
                    str(c["ref"]),
                    tuple(LatLon(float(a["lat"]), float(a["lon"])) for a in c["anchors"]),
                    Decimal(str(c["weekdayRub"])),
                    Decimal(str(weekend)) if weekend is not None else None,
                )
            )
        return TollCorridors(
            date.fromisoformat(str(d["asOf"])),
            float(str(d["followKm"])),
            float(str(d["minSpanKm"])),
            float(str(d["endSnapKm"])),
            tuple(out),
        )

    @staticmethod
    def from_resources() -> TollCorridors:
        return TollCorridors.from_dict(json.loads(resources.read_text("toll_corridors.json")))


class CorridorTolls:
    """`TollRepository` of the composed world (acceptance 2026-10-28, QA B-1): `inner` (the world's segments
    and the per-km rates, ENG-02) on routes with road geometry; on an approximate route (`Route.synthetic`,
    no road refs) a leg whose both ends lie within `follow_km` of a toll corridor drives that road between
    their projections, priced as the corridor's whole-road price x the covered share, marked approximate.
    A leg along no known corridor has no tolls here; the engine says they are not counted."""

    def __init__(self, inner: TollRepository, corridors: TollCorridors) -> None:
        self.inner = inner
        self.corridors = corridors

    def segments_on_route(self, route: Route) -> list[TollHit]:
        if not route.synthetic:
            return self.inner.segments_on_route(route)
        hits: list[TollHit] = []
        wp = route.waypoint_idx
        for i, j in itertools.pairwise(wp):
            a, b = route.points[i], route.points[j]
            for c in self.corridors.corridors:
                hit = self._leg_hit(c, a, b, route.cum_km[i], route.cum_km[j])
                if hit is not None:
                    hits.append(hit)
                    break  # one toll road per leg: the corridors do not overlap beyond their shared start
        hits.sort(key=lambda h: (h.km_from, h.segment.id))
        return hits

    def _leg_hit(self, c: TollCorridor, a: LatLon, b: LatLon, km_a: float, km_b: float) -> TollHit | None:
        (fa, da), (fb, db) = c.project(a), c.project(b)
        follow = self.corridors.follow_km
        if da > follow or db > follow or abs(fb - fa) < self.corridors.min_span_km:
            return None
        length = c.length_km()
        lo, hi = sorted((fa, fb))
        snap = self.corridors.end_snap_km
        lo = 0.0 if lo <= snap else lo
        hi = length if length - hi <= snap else hi
        share = Decimal(str(round((hi - lo) / length, 4)))
        day = _money(c.weekday_rub * share)
        weekend = _money(c.weekend_rub * share) if c.weekend_rub is not None else None
        seg = TollSegment(
            id=f"corridor:{c.ref}:{round(km_a)}",
            road_ref=c.ref,
            name_ru=c.ref,
            tariff_day_rub=day,
            tariff_night_rub=day,  # no night tariffs are known for a whole road
            vehicle_class=1,
            night_from=time(0),
            night_to=time(0),
            as_of=self.corridors.as_of,
            tariff_weekend_rub=weekend,
            approx=True,
        )
        return TollHit(seg, min(km_a, km_b), max(km_a, km_b))
