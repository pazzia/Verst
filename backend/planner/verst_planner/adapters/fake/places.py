"""`FakePlaceRepository` (A§5.2): brute-force corridor queries over world places and towns."""

from __future__ import annotations

import itertools
from collections.abc import Sequence

from verst_planner.adapters.fake.world import FakeWorld
from verst_planner.domain.enums import PlaceStatus, PlaceType
from verst_planner.domain.model import LatLon, Place, ReadyRoute, Town
from verst_planner.geo.distance import haversine_km, point_segment_km
from verst_planner.ports import CorridorQuery


def distance_to_line_km(p: LatLon, line: tuple[LatLon, ...]) -> float:
    if not line:
        return float("inf")
    if len(line) == 1:
        return haversine_km(p, line[0])
    return min(point_segment_km(p, a, b) for a, b in itertools.pairwise(line))


class FakePlaceRepository:
    def __init__(self, world: FakeWorld) -> None:
        self.world = world
        self.calls: dict[str, int] = {}

    def _count(self, name: str) -> None:
        self.calls[name] = self.calls.get(name, 0) + 1

    def places_in_corridor(self, q: CorridorQuery) -> list[Place]:
        self._count("places_in_corridor")
        out = [
            p
            for p in self.world.places.values()
            if p.status is PlaceStatus.LIVE
            and p.type in q.types
            and distance_to_line_km(p.point, q.line) <= q.radius_km
        ]
        return sorted(out, key=lambda p: p.id)

    def towns_in_corridor(self, line: tuple[LatLon, ...], radius_km: float) -> list[Town]:
        self._count("towns_in_corridor")
        out = [t for t in self.world.towns.values() if distance_to_line_km(t.point, line) <= radius_km]
        return sorted(out, key=lambda t: t.id)

    def lodgings_of_towns(self, town_ids: Sequence[str]) -> dict[str, list[Place]]:
        self._count("lodgings_of_towns")
        wanted = set(town_ids)
        out: dict[str, list[Place]] = {tid: [] for tid in town_ids}
        for p in sorted(self.world.places.values(), key=lambda x: x.id):
            if (
                p.type is PlaceType.LODGING
                and p.status is PlaceStatus.LIVE
                and p.town_id is not None
                and p.town_id in wanted
            ):
                out[p.town_id].append(p)
        return out

    def get_places(self, ids: Sequence[str]) -> dict[str, Place]:
        self._count("get_places")
        return {i: self.world.places[i] for i in ids if i in self.world.places}

    def get_towns(self, ids: Sequence[str]) -> dict[str, Town]:
        self._count("get_towns")
        return {i: self.world.towns[i] for i in ids if i in self.world.towns}

    def get_ready_route(self, route_id: str) -> ReadyRoute | None:
        self._count("get_ready_route")
        return self.world.ready_routes.get(route_id)

    def places_near(self, point: LatLon, radius_km: float, types: frozenset[PlaceType]) -> list[Place]:
        """Live places of `types` within `radius_km` of `point`, nearest first, then id (city walks)."""
        self._count("places_near")
        hits = [
            (round(haversine_km(point, p.point), 6), p.id, p)
            for p in self.world.places.values()
            if p.status is PlaceStatus.LIVE and p.type in types and haversine_km(point, p.point) <= radius_km
        ]
        return [p for _d, _i, p in sorted(hits, key=lambda x: (x[0], x[1]))]

    def ready_routes_near(self, point: LatLon, hub_radius_km: float, limit: int) -> list[ReadyRoute]:
        self._count("ready_routes_near")
        out = [
            r
            for r in self.world.ready_routes.values()
            if haversine_km(self.world.towns[r.hub_town_id].point, point) <= hub_radius_km
        ]
        out.sort(key=lambda r: (r.km_sign, r.sort, r.id))
        return out[:limit]
