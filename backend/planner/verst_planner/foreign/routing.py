"""Routing of a trip abroad (CEO 29.10): Russian legs as before, legs that touch abroad on the road model.

There is no road graph abroad. A request is cut into runs: consecutive waypoints all in Russia go to the
world's own routing in one request (the phone's `HybridRouting`, the server's GraphHopper), so a Russian
leg keeps its exact behaviour; every leg with an end outside Russia is the calibrated road model (straight
line x ratio, `Route.synthetic`). The parts are stitched into one route, `synthetic` when any part is, so the
trip says its distances are approximate (`approxDistances`).

`BorderTolls` prices the Russian parts with the world's toll port (real refs or the B-1 corridors); the
legs abroad have no toll here — the `abroad` block says what is known about tolls there.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from verst_planner.adapters.catalogue.routing import synthetic_route
from verst_planner.domain.errors import Unreachable
from verst_planner.domain.model import LatLon, Route, RouteDetail, RouteRequest, TollHit
from verst_planner.geo.roadmodel import RoadModel
from verst_planner.ports import RoutingPort, TollRepository

KEEP_PARTS = 16  # routes whose parts are remembered for the toll port (one plan needs one)


@dataclass(frozen=True, slots=True)
class Part:
    route: Route
    km0: float  # km of the part's start in the stitched route
    russian: bool


def stitch(parts: list[Route]) -> Route:
    first = parts[0]
    points = list(first.points)
    cum_km = list(first.cum_km)
    cum_min = list(first.cum_min)
    details = list(first.details)
    wp = list(first.waypoint_idx)
    snapped = list(first.snapped)
    for r in parts[1:]:
        off = len(points) - 1
        k0, m0 = cum_km[-1], cum_min[-1]
        points += r.points[1:]
        cum_km += [k0 + k for k in r.cum_km[1:]]
        cum_min += [m0 + m for m in r.cum_min[1:]]
        details += [
            RouteDetail(d.from_idx + off, d.to_idx + off, d.road_class, d.road_ref, d.toll) for d in r.details
        ]
        wp += [i + off for i in r.waypoint_idx[1:]]
        snapped += r.snapped[1:]
    return Route(
        points=tuple(points),
        cum_km=tuple(cum_km),
        cum_min=tuple(cum_min),
        details=tuple(details),
        waypoint_idx=tuple(wp),
        snapped=tuple(snapped),
        km_total=cum_km[-1],
        min_total=cum_min[-1],
        synthetic=any(r.synthetic for r in parts),
    )


class BorderRouting:
    def __init__(self, inner: RoutingPort, model: RoadModel, russian: Callable[[LatLon], bool]) -> None:
        self.inner = inner
        self.model = model
        self.russian = russian
        self._parts: dict[int, tuple[Route, list[Part]]] = {}
        self.calls = 0

    def route(self, req: RouteRequest) -> Route:
        self.calls += 1
        pts = req.points
        ru = [self.russian(p) for p in pts]
        if all(ru):
            return self.inner.route(req)
        pieces: list[tuple[Route, bool]] = []
        i = 0
        while i < len(pts) - 1:
            if ru[i] and ru[i + 1]:
                j = i + 1
                while j < len(pts) - 1 and ru[j + 1]:
                    j += 1
                try:
                    pieces.append((self.inner.route(RouteRequest(pts[i : j + 1], req.avoid_tolls)), True))
                except Unreachable as e:
                    raise Unreachable(i + e.point_index, e.snap_km) from e
                i = j
            else:
                pieces.append((synthetic_route(pts[i : i + 2], self.model), False))
                i += 1
        out = stitch([r for r, _ in pieces])
        parts, km0 = [], 0.0
        for r, russian in pieces:
            parts.append(Part(r, km0, russian))
            km0 += r.km_total
        self._parts[id(out)] = (out, parts)  # the route is kept alive with its id (no reuse)
        while len(self._parts) > KEEP_PARTS:
            del self._parts[next(iter(self._parts))]
        return out

    def parts_of(self, route: Route) -> list[Part] | None:
        hit = self._parts.get(id(route))
        return hit[1] if hit is not None and hit[0] is route else None


class BorderTolls:
    def __init__(self, inner: TollRepository, routing: BorderRouting) -> None:
        self.inner = inner
        self.routing = routing

    def segments_on_route(self, route: Route) -> list[TollHit]:
        parts = self.routing.parts_of(route)
        if parts is None:
            return self.inner.segments_on_route(route)
        hits: list[TollHit] = []
        for p in parts:
            if p.russian:
                hits += [
                    TollHit(h.segment, h.km_from + p.km0, h.km_to + p.km0)
                    for h in self.inner.segments_on_route(p.route)
                ]
        hits.sort(key=lambda h: (h.km_from, h.segment.id))
        return hits


__all__ = ["BorderRouting", "BorderTolls", "Part", "stitch"]
