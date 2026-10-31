"""Indexed repositories over the composed world (ADR-0012 §4-5).

`IndexedPlaceRepository` answers the same queries as `FakePlaceRepository` with a grid index (the composed
world has ~25 000 places), and adds synthetic fuel/rest places along road segments that are far from the
fixture graph (one every `FUEL_EVERY_KM` / `REST_EVERY_KM` along the query line). Their ids carry their
coordinates, so `get_places` rebuilds them for `replace_stop` without any state.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence

from verst_planner.adapters.catalogue.synthetic import roadside, roadside_id, roadside_region_point
from verst_planner.adapters.fake.places import FakePlaceRepository, distance_to_line_km
from verst_planner.adapters.fake.world import FakeWorld, point_on_edge
from verst_planner.domain.enums import PlaceStatus, PlaceType
from verst_planner.domain.model import GeoLabel, GeoSuggestion, LatLon, Place, RegionInfo, Town
from verst_planner.geo.distance import haversine_km
from verst_planner.geo.grid import GridIndex
from verst_planner.ports import CorridorQuery

FUEL_EVERY_KM = 50.0
REST_EVERY_KM = 60.0
REST_OFFSET_KM = 25.0
GRAPH_COVER_KM = 20.0
LATERAL_KM = 0.2
REVERSE_RADIUS_KM = 30.0
FALLBACK_TZ = "Europe/Moscow"


class RegionByNearestTown:
    """`RegionLocator`: the region of the nearest town or fixture node (exact inside the fixture area)."""

    def __init__(self, world: FakeWorld) -> None:
        self.world = world
        self.index: GridIndex[str] = GridIndex(0.5)
        for t in sorted(world.towns.values(), key=lambda t: t.id):
            self.index.add(t.point, t.region_code)
        for n in sorted(world.nodes.values(), key=lambda n: n.id):
            self.index.add(n.point, n.region)
        self.calls = 0

    def code_at(self, p: LatLon) -> str:
        hit = self.index.nearest(p, 2000.0)
        return hit[1] if hit is not None else "RU"

    def locate(self, point: LatLon) -> RegionInfo:
        self.calls += 1
        code = self.code_at(point)
        return self.world.regions.get(code) or RegionInfo(code, code, FALLBACK_TZ)


class IndexedPlaceRepository(FakePlaceRepository):
    def __init__(self, world: FakeWorld, regions: RegionByNearestTown) -> None:
        super().__init__(world)
        self.regions = regions
        self.place_index: GridIndex[Place] = GridIndex(0.1)
        self.town_index: GridIndex[Town] = GridIndex(0.25)
        self.lodgings: dict[str, list[Place]] = {}
        for p in sorted(world.places.values(), key=lambda p: p.id):
            if p.status is not PlaceStatus.LIVE:
                continue
            self.place_index.add(p.point, p)
            if p.type is PlaceType.LODGING and p.town_id is not None:
                self.lodgings.setdefault(p.town_id, []).append(p)
        for t in sorted(world.towns.values(), key=lambda t: t.id):
            self.town_index.add(t.point, t)
        self.graph: GridIndex[bool] = GridIndex(0.25)
        for e in world.edges:
            n = max(1, round(e.km / 5.0))
            for k in range(n + 1):
                self.graph.add(point_on_edge(e.pa, e.pb, k / n), True)

    # ------------------------------------------------------------------ corridor
    def places_in_corridor(self, q: CorridorQuery) -> list[Place]:
        self._count("places_in_corridor")
        found: dict[str, Place] = {}
        for _pt, p in self.place_index.near_line(q.line, q.radius_km):
            if p.type in q.types and distance_to_line_km(p.point, q.line) <= q.radius_km:
                found[p.id] = p
        for p in self._roadside(q):
            found[p.id] = p
        return sorted(found.values(), key=lambda p: p.id)

    def _roadside(self, q: CorridorQuery) -> list[Place]:
        kinds = [
            (k, every, offset)
            for k, t, every, offset in (
                ("f", PlaceType.FUEL, FUEL_EVERY_KM, FUEL_EVERY_KM / 2),
                ("r", PlaceType.REST, REST_EVERY_KM, REST_OFFSET_KM),
            )
            if t in q.types
        ]
        if not kinds or len(q.line) < 2:
            return []
        out: list[Place] = []
        for kind, every, offset in kinds:
            walked = 0.0
            nxt = offset
            for a, b in itertools.pairwise(q.line):
                seg = haversine_km(a, b)
                while seg > 0 and nxt <= walked + seg:
                    f = (nxt - walked) / seg
                    p = point_on_edge(a, b, f, LATERAL_KM)
                    nxt += every
                    if self.graph.nearest(p, GRAPH_COVER_KM) is not None:
                        continue  # the fixture area has its own curated fuel and rest places
                    place = roadside(roadside_id(kind, p), self.regions.code_at(p))
                    assert place is not None
                    out.append(place)
                walked += seg
        return out

    def towns_in_corridor(self, line: tuple[LatLon, ...], radius_km: float) -> list[Town]:
        self._count("towns_in_corridor")
        found = {
            t.id: t
            for _pt, t in self.town_index.near_line(line, radius_km)
            if distance_to_line_km(t.point, line) <= radius_km
        }
        return [found[k] for k in sorted(found)]

    def lodgings_of_towns(self, town_ids: Sequence[str]) -> dict[str, list[Place]]:
        self._count("lodgings_of_towns")
        return {tid: list(self.lodgings.get(tid, [])) for tid in town_ids}

    def get_places(self, ids: Sequence[str]) -> dict[str, Place]:
        self._count("get_places")
        out: dict[str, Place] = {}
        for i in ids:
            p = self.world.places.get(i)
            if p is None:
                at = roadside_region_point(i)
                p = roadside(i, self.regions.code_at(at)) if at is not None else None
            if p is not None:
                out[i] = p
        return out

    def places_near(self, point: LatLon, radius_km: float, types: frozenset[PlaceType]) -> list[Place]:
        """Live places of `types` within `radius_km` (city walks, ADR-0013), nearest first, then id."""
        hits = [
            (round(d, 6), p.id, p) for d, p in self.place_index.within(point, radius_km) if p.type in types
        ]
        return [p for _d, _i, p in sorted(hits, key=lambda x: (x[0], x[1]))]


class CatalogueGeocoding:
    """Offline typeahead over all towns and places (ADR-0012 §5): prefix, then population/popularity."""

    def __init__(self, world: FakeWorld, popularity: dict[str, int], towns: GridIndex[Town]) -> None:
        self.world = world
        self.towns = towns
        self._keys: tuple[list[tuple[str, Town]], list[tuple[str, Place]]] | None = None
        self.popularity = popularity

    def _search_keys(self) -> tuple[list[tuple[str, Town]], list[tuple[str, Place]]]:
        """Built on the first query, not at catalogue load (M9: the load is on the app's start path)."""
        if self._keys is None:
            world = self.world
            self._keys = (
                [
                    (t.name_ru.casefold().replace("\u0451", "\u0435"), t)
                    for t in sorted(world.towns.values(), key=lambda t: t.id)
                ],
                [
                    (p.name_ru.casefold().replace("\u0451", "\u0435"), p)
                    for p in sorted(world.places.values(), key=lambda p: p.id)
                    if p.status is PlaceStatus.LIVE and p.type is PlaceType.SIGHT
                ],
            )
        return self._keys

    def _region_name(self, code: str) -> str:
        r = self.world.regions.get(code)
        return r.name_ru if r else code

    def suggest(self, q: str, near: LatLon | None, limit: int) -> list[GeoSuggestion]:
        needle = q.strip().casefold().replace("\u0451", "\u0435")
        if not needle:
            return []
        found: list[tuple[int, int, float, str, GeoSuggestion]] = []
        town_keys, place_keys = self._search_keys()
        for name, t in town_keys:
            if needle in name:
                rank = 0 if name.startswith(needle) else 2
                dist = haversine_km(near, t.point) if near else 0.0
                s = GeoSuggestion("city", t.name_ru, self._region_name(t.region_code), t.point, t.id)
                found.append((rank, -t.population, round(dist, 3), t.id, s))
        for name, p in place_keys:
            if needle in name:
                rank = 1 if name.startswith(needle) else 3
                dist = haversine_km(near, p.point) if near else 0.0
                s = GeoSuggestion("place", p.name_ru, self._region_name(p.region_code), p.point, p.id)
                found.append((rank, -self.popularity.get(p.id, 0), round(dist, 3), p.id, s))
        found.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
        return [x[4] for x in found[:limit]]

    def reverse(self, point: LatLon) -> GeoLabel | None:
        hit = self.towns.nearest(point, REVERSE_RADIUS_KM)
        if hit is None:
            return None
        t = hit[1]
        return GeoLabel(t.name_ru, self._region_name(t.region_code), t.region_code)

    def nearest_town(self, point: LatLon, max_km: float) -> tuple[float, Town] | None:
        return self.towns.nearest(point, max_km)
