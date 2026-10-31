"""`HybridRouting` (ADR-0012 §4): the fixture graph where it reaches, the calibrated road model elsewhere.

1. Every point within `snap_max_km` (2 km) of the graph → the fixture route, unchanged (`FakeRouting`).
2. Every point within `ACCESS_MAX_KM` of the graph → the graph route between the snapped points, plus
   straight access legs (x the road model) from the first point and to the last point.
3. Otherwise the whole route is synthetic: straight legs sampled every ~1 km, `km = straight x ratio(h)`,
   minutes from the calibrated speed, road class `primary`, no tolls, `Route.synthetic = True`.

A point farther than `REACH_KM` from every catalogue town and graph node is `Unreachable(point_index)`.
"""

from __future__ import annotations

import itertools

from verst_planner.adapters.fake.routing import FakeRouting
from verst_planner.adapters.fake.world import FakeWorld
from verst_planner.domain.enums import RoadClass
from verst_planner.domain.errors import Unreachable
from verst_planner.domain.model import LatLon, Route, RouteDetail, RouteRequest
from verst_planner.geo.distance import haversine_km
from verst_planner.geo.grid import GridIndex
from verst_planner.geo.roadmodel import RoadModel

ACCESS_MAX_KM = 20.0
REACH_KM = 60.0
ACCESS_MIN_KM = 0.3


def _leg(a: LatLon, b: LatLon, model: RoadModel) -> tuple[list[LatLon], list[float], list[float]]:
    """Points after `a` up to `b` with their cumulative km/min increments from `a`."""
    h = haversine_km(a, b)
    km = model.road_km(h) if h > 0 else 0.0
    minutes = model.minutes(h) if h > 0 else 0.0
    n = max(1, round(km))
    pts, kms, mins = [], [], []
    for k in range(1, n + 1):
        f = k / n
        pts.append(b if k == n else LatLon(a.lat + (b.lat - a.lat) * f, a.lon + (b.lon - a.lon) * f))
        kms.append(km * f)
        mins.append(minutes * f)
    return pts, kms, mins


class HybridRouting:
    def __init__(self, world: FakeWorld, reach: GridIndex[str], model: RoadModel) -> None:
        self.world = world
        self.graph = FakeRouting(world)
        self.wide = FakeRouting(world, snap_max_km=ACCESS_MAX_KM)
        self.reach = reach
        self.model = model
        self.calls = 0
        self.nodes: GridIndex[str] = GridIndex(0.2)
        for nid in sorted(n for n in world.nodes if world.adjacency.get(n)):
            self.nodes.add(world.nodes[nid].point, nid)

    def _check_reach(self, req: RouteRequest) -> None:
        for i, p in enumerate(req.points):
            if self.reach.nearest(p, REACH_KM) is None:
                raise Unreachable(i, None)

    def _near_graph(self, p: LatLon, km: float) -> bool:
        return self.nodes.nearest(p, km) is not None

    def route(self, req: RouteRequest) -> Route:
        self.calls += 1
        if len(req.points) < 2:
            raise Unreachable(0, None)
        if all(self._near_graph(p, 2.0 + 5.0) for p in req.points):
            try:
                return self.graph.route(req)
            except Unreachable:
                pass
        self._check_reach(req)
        if all(self._near_graph(p, ACCESS_MAX_KM + 5.0) for p in req.points):
            try:
                return self._with_access(req)
            except Unreachable:
                pass
        return self.synthetic(req)

    def _with_access(self, req: RouteRequest) -> Route:
        core = self.wide.route(req)
        points = list(core.points)
        cum_km = list(core.cum_km)
        cum_min = list(core.cum_min)
        details = list(core.details)
        wp = list(core.waypoint_idx)
        first, last = req.points[0], req.points[-1]
        if haversine_km(first, core.snapped[0]) > ACCESS_MIN_KM:
            pts, kms, mins = _leg(first, core.snapped[0], self.model)
            n = len(pts)
            points = [first, *pts[:-1], *points]
            cum_km = [0.0, *kms[:-1], *(kms[-1] + k for k in cum_km)]
            cum_min = [0.0, *mins[:-1], *(mins[-1] + m for m in cum_min)]
            details = [RouteDetail(0, n, RoadClass.PRIMARY, None, False)] + [
                RouteDetail(d.from_idx + n, d.to_idx + n, d.road_class, d.road_ref, d.toll) for d in details
            ]
            wp = [0] + [i + n for i in wp[1:]]
        if haversine_km(core.snapped[-1], last) > ACCESS_MIN_KM:
            pts, kms, mins = _leg(core.snapped[-1], last, self.model)
            base = len(points) - 1
            points += pts
            cum_km += [cum_km[-1] + k for k in kms]
            cum_min += [cum_min[-1] + m for m in mins]
            details.append(RouteDetail(base, len(points) - 1, RoadClass.PRIMARY, None, False))
            wp[-1] = len(points) - 1
        return Route(
            points=tuple(points),
            cum_km=tuple(cum_km),
            cum_min=tuple(cum_min),
            details=tuple(details),
            waypoint_idx=tuple(wp),
            snapped=(first, *core.snapped[1:-1], last),
            km_total=cum_km[-1],
            min_total=cum_min[-1],
            synthetic=False,
        )

    def synthetic(self, req: RouteRequest) -> Route:
        return synthetic_route(req.points, self.model)


def synthetic_route(waypoints: tuple[LatLon, ...], model: RoadModel) -> Route:
    """The road model between the waypoints: straight legs x the calibrated ratio (`Route.synthetic`)."""
    points = [waypoints[0]]
    cum_km = [0.0]
    cum_min = [0.0]
    wp = [0]
    for a, b in itertools.pairwise(waypoints):
        pts, kms, mins = _leg(a, b, model)
        k0, m0 = cum_km[-1], cum_min[-1]
        points += pts
        cum_km += [k0 + k for k in kms]
        cum_min += [m0 + m for m in mins]
        wp.append(len(points) - 1)
    return Route(
        points=tuple(points),
        cum_km=tuple(cum_km),
        cum_min=tuple(cum_min),
        details=(RouteDetail(0, len(points) - 1, RoadClass.PRIMARY, None, False),),
        waypoint_idx=tuple(wp),
        snapped=tuple(waypoints),
        km_total=cum_km[-1],
        min_total=cum_min[-1],
        synthetic=True,
    )
