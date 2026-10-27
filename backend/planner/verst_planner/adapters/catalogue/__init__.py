"""Adapters of the composed world `russia_v1` (ADR-0012 §4): catalogue + fixture + fictional services."""

from __future__ import annotations

import json
from datetime import datetime
from typing import NamedTuple

from verst_planner import resources
from verst_planner.adapters.catalogue.repos import (
    CatalogueGeocoding,
    IndexedPlaceRepository,
    RegionByNearestTown,
)
from verst_planner.adapters.catalogue.routing import HybridRouting
from verst_planner.adapters.catalogue.tolls import RoadRateTolls, TollRates
from verst_planner.adapters.catalogue.world import WORLD_ID, CatalogueWorld, compose
from verst_planner.adapters.fake import GOLDEN_CLOCK, FakePriceRepository, FakeTollRepository, FixedClock
from verst_planner.geo.grid import GridIndex
from verst_planner.geo.roadmodel import RoadModel
from verst_planner.parking import OsmParking, ParkingModel

__all__ = [
    "WORLD_ID",
    "CataloguePorts",
    "CatalogueWorld",
    "HybridRouting",
    "IndexedPlaceRepository",
    "build_catalogue_ports",
    "compose",
    "road_model",
]


class CataloguePorts(NamedTuple):
    routing: HybridRouting
    geocoding: CatalogueGeocoding
    places: IndexedPlaceRepository
    prices: FakePriceRepository
    tolls: RoadRateTolls  # ENG-02: the world's segments, then km x the road's rate on real geometry
    regions: RegionByNearestTown
    clock: FixedClock
    world: CatalogueWorld
    parking: ParkingModel | None = None  # ADR-0015 §4


def road_model() -> RoadModel:
    return RoadModel.from_dict(json.loads(resources.read_text("detour_model.json")))


def build_catalogue_ports(cw: CatalogueWorld, now: datetime = GOLDEN_CLOCK) -> CataloguePorts:
    world = cw.world
    regions = RegionByNearestTown(world)
    places = IndexedPlaceRepository(world, regions)
    reach: GridIndex[str] = GridIndex(0.5)
    for t in sorted(world.towns.values(), key=lambda t: t.id):
        reach.add(t.point, t.id)
    popularity = {
        pid: cw.catalogue.poi_by_id[q].sitelinks
        for pid, q in cw.qid_of_place.items()
        if q in cw.catalogue.poi_by_id
    }
    return CataloguePorts(
        routing=HybridRouting(world, reach, road_model()),
        geocoding=CatalogueGeocoding(world, popularity, places.town_index),
        places=places,
        prices=FakePriceRepository(world),
        tolls=RoadRateTolls(FakeTollRepository(world), TollRates.from_resources()),
        regions=regions,
        clock=FixedClock(now),
        world=cw,
        parking=ParkingModel.from_resources(
            [OsmParking(p.point, p.rub_per_hour) for p in cw.catalogue.parking]
        ),
    )
