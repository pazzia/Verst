"""Fake adapters driven by JSON world fixtures (A§5.2)."""

from __future__ import annotations

from datetime import datetime
from typing import NamedTuple

from verst_planner.adapters.fake.clock import FixedClock
from verst_planner.adapters.fake.geocoding import FakeGeocoding
from verst_planner.adapters.fake.places import FakePlaceRepository
from verst_planner.adapters.fake.prices import FakePriceRepository
from verst_planner.adapters.fake.regions import FakeRegionLocator
from verst_planner.adapters.fake.routing import FakeRouting
from verst_planner.adapters.fake.tolls import FakeTollRepository
from verst_planner.adapters.fake.world import FakeWorld
from verst_planner.ports import (
    Clock,
    GeocodingPort,
    PlaceRepository,
    PriceRepository,
    RegionLocator,
    RoutingPort,
    TollRepository,
)

GOLDEN_CLOCK = datetime.fromisoformat("2026-10-23T09:00:00+03:00")

__all__ = [
    "GOLDEN_CLOCK",
    "FakeGeocoding",
    "FakePlaceRepository",
    "FakePorts",
    "FakePriceRepository",
    "FakeRegionLocator",
    "FakeRouting",
    "FakeTollRepository",
    "FakeWorld",
    "FixedClock",
    "build_fakes",
]


class FakePorts(NamedTuple):
    routing: FakeRouting
    geocoding: FakeGeocoding
    places: FakePlaceRepository
    prices: FakePriceRepository
    tolls: FakeTollRepository
    regions: FakeRegionLocator
    clock: FixedClock


def build_fakes(world: FakeWorld, now: datetime = GOLDEN_CLOCK) -> FakePorts:
    return FakePorts(
        routing=FakeRouting(world),
        geocoding=FakeGeocoding(world),
        places=FakePlaceRepository(world),
        prices=FakePriceRepository(world),
        tolls=FakeTollRepository(world),
        regions=FakeRegionLocator(world),
        clock=FixedClock(now),
    )


def _conformance(p: FakePorts) -> None:  # pragma: no cover - checked by mypy, never called
    routing: RoutingPort = p.routing
    geocoding: GeocodingPort = p.geocoding
    places: PlaceRepository = p.places
    prices: PriceRepository = p.prices
    tolls: TollRepository = p.tolls
    regions: RegionLocator = p.regions
    clock: Clock = p.clock
    del routing, geocoding, places, prices, tolls, regions, clock
