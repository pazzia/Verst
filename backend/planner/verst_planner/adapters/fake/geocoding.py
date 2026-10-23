"""`FakeGeocoding` (A§5.2): substring suggest over town and place names; nearest-town reverse."""

from __future__ import annotations

from verst_planner.adapters.fake.world import FakeWorld
from verst_planner.domain.enums import PlaceStatus
from verst_planner.domain.model import GeoLabel, GeoSuggestion, LatLon
from verst_planner.geo.distance import haversine_km

REVERSE_RADIUS_KM = 30.0


class FakeGeocoding:
    def __init__(self, world: FakeWorld) -> None:
        self.world = world

    def _region_name(self, code: str) -> str:
        r = self.world.regions.get(code)
        return r.name_ru if r else code

    def suggest(self, q: str, near: LatLon | None, limit: int) -> list[GeoSuggestion]:
        needle = q.strip().casefold()
        if not needle:
            return []
        found: list[tuple[int, float, str, GeoSuggestion]] = []
        for t in self.world.towns.values():
            name = t.name_ru.casefold()
            if needle in name:
                dist = haversine_km(near, t.point) if near else 0.0
                s = GeoSuggestion("city", t.name_ru, self._region_name(t.region_code), t.point, t.id)
                found.append((0 if name.startswith(needle) else 1, dist, t.id, s))
        for p in self.world.places.values():
            if p.status is not PlaceStatus.LIVE:
                continue
            name = p.name_ru.casefold()
            if needle in name:
                dist = haversine_km(near, p.point) if near else 0.0
                s = GeoSuggestion("place", p.name_ru, self._region_name(p.region_code), p.point, p.id)
                found.append((0 if name.startswith(needle) else 1, dist, p.id, s))
        found.sort(key=lambda x: (x[0], x[1], x[2]))
        return [x[3] for x in found[:limit]]

    def reverse(self, point: LatLon) -> GeoLabel | None:
        best = None
        best_d = REVERSE_RADIUS_KM
        for t in sorted(self.world.towns.values(), key=lambda t: t.id):
            d = haversine_km(point, t.point)
            if d <= best_d:
                best, best_d = t, d
        if best is None:
            return None
        return GeoLabel(best.name_ru, self._region_name(best.region_code), best.region_code)
