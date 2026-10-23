"""`FakeTollRepository` (A§5.2).

A segment's geometry is the sub-polyline of its edge between ``fromKm`` and ``toKm`` (vertices every ~1 km).
A hit is reported when >= 70 % of its vertices are within 0.1 km of the route (the PostGIS rule of A§5.3.4).
``km_from/km_to`` are the projections of the segment endpoints on the route; a route that drives the segment
twice (out and back) yields one hit per pass.
"""

from __future__ import annotations

from verst_planner.adapters.fake.world import FakeWorld, TollDef, point_on_edge
from verst_planner.domain.model import LatLon, Route, TollHit
from verst_planner.geo.index import PolylineIndex

HIT_TOLERANCE_KM = 0.1
HIT_SHARE = 0.7


def _geometry(t: TollDef) -> list[LatLon]:
    e = t.edge
    pa, pb = (e.pa, e.pb) if t.a == e.a else (e.pb, e.pa)
    n = max(1, round(t.to_km - t.from_km))
    return [point_on_edge(pa, pb, (t.from_km + (t.to_km - t.from_km) * k / n) / e.km) for k in range(n + 1)]


class FakeTollRepository:
    def __init__(self, world: FakeWorld) -> None:
        self.world = world
        self._geoms = {t.segment.id: _geometry(t) for t in world.tolls}

    def segments_on_route(self, route: Route) -> list[TollHit]:
        index = PolylineIndex(route)
        hits: list[TollHit] = []
        for t in self.world.tolls:
            geom = self._geoms[t.segment.id]
            near = sum(1 for p in geom if index.project_all(p, HIT_TOLERANCE_KM))
            if near < HIT_SHARE * len(geom):
                continue
            starts = index.project_all(geom[0], HIT_TOLERANCE_KM * 2)
            ends = index.project_all(geom[-1], HIT_TOLERANCE_KM * 2)
            used: set[int] = set()
            for s in starts:
                best_j = None
                for j, e in enumerate(ends):
                    if j in used:
                        continue
                    if best_j is None or abs(e.km_at - s.km_at) < abs(ends[best_j].km_at - s.km_at):
                        best_j = j
                if best_j is None:
                    continue
                used.add(best_j)
                e = ends[best_j]
                hits.append(TollHit(t.segment, min(s.km_at, e.km_at), max(s.km_at, e.km_at)))
        hits.sort(key=lambda h: (h.km_from, h.segment.id))
        return hits
