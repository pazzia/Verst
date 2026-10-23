"""`FakePriceRepository` (A§5.2): latest price per (region, fuel), fallback ``RU``; defaults by town size."""

from __future__ import annotations

from datetime import date

from verst_planner.adapters.fake.world import FakeWorld
from verst_planner.domain.enums import FuelType
from verst_planner.domain.errors import NotFound
from verst_planner.domain.model import RegionPrice


def _by_population(table: list[tuple[int, int]], population: int) -> int:
    """First row (sorted by threshold descending) whose threshold the population reaches."""
    for threshold, value in table:
        if population >= threshold:
            return value
    return table[-1][1]


class FakePriceRepository:
    def __init__(self, world: FakeWorld) -> None:
        self.world = world
        latest: dict[tuple[str, FuelType], RegionPrice] = {}
        for p in world.region_prices:
            key = (p.region_code, p.fuel_type)
            if key not in latest or p.as_of > latest[key].as_of:
                latest[key] = p
        self._latest = latest

    def fuel_price(self, region_code: str, fuel_type: FuelType) -> RegionPrice:
        hit = self._latest.get((region_code, fuel_type)) or self._latest.get(("RU", fuel_type))
        if hit is None:
            raise NotFound("region_price", f"RU/{fuel_type.value}")
        return hit

    def food_default_check(self, town_population: int) -> int:
        return _by_population(self.world.food_check_by_population, town_population)

    def lodging_default_night(self, town_population: int) -> int:
        return _by_population(self.world.lodging_night_by_population, town_population)

    def defaults_as_of(self) -> date:
        """The world's `asOf` (A§16.7)."""
        return self.world.as_of
