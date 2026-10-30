"""`FakeRegionLocator` (A§5.2): region of the nearest node; never raises."""

from __future__ import annotations

from verst_planner.adapters.fake.world import FakeWorld
from verst_planner.domain.model import LatLon, RegionInfo

FALLBACK_TZ = "Europe/Moscow"


class FakeRegionLocator:
    def __init__(self, world: FakeWorld) -> None:
        self.world = world
        self.calls = 0

    def locate(self, point: LatLon) -> RegionInfo:
        self.calls += 1
        if not self.world.nodes:
            return self.world.regions.get("RU") or RegionInfo("RU", "RU", FALLBACK_TZ)
        code = self.world.region_of_point(point)
        return self.world.regions.get(code) or RegionInfo(code, code, FALLBACK_TZ)
