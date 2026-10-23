"""Ports the planner depends on (A§5.1). Real adapters live in `verst_api.adapters`, fakes in
`verst_planner.adapters.fake`."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import NamedTuple, Protocol

from verst_planner.domain.enums import FuelType, PlaceType
from verst_planner.domain.model import (
    GeoLabel,
    GeoSuggestion,
    LatLon,
    Place,
    ReadyRoute,
    RegionInfo,
    RegionPrice,
    Route,
    RouteRequest,
    TollHit,
    Town,
)


class RoutingPort(Protocol):
    def route(self, req: RouteRequest) -> Route:
        """Raises `Unreachable` (a point cannot be snapped / no car path) or `UpstreamUnavailable`."""
        ...


class GeocodingPort(Protocol):
    def suggest(self, q: str, near: LatLon | None, limit: int) -> list[GeoSuggestion]: ...

    def reverse(self, point: LatLon) -> GeoLabel | None: ...


class CorridorQuery(NamedTuple):
    line: tuple[LatLon, ...]  # simplified polyline (Douglas-Peucker 200 m) for the spatial prefilter
    radius_km: float
    types: frozenset[PlaceType]


class PlaceRepository(Protocol):
    def places_in_corridor(self, q: CorridorQuery) -> list[Place]:
        """Live places only."""
        ...

    def towns_in_corridor(self, line: tuple[LatLon, ...], radius_km: float) -> list[Town]: ...

    def lodgings_of_towns(self, town_ids: Sequence[str]) -> dict[str, list[Place]]: ...

    def get_places(self, ids: Sequence[str]) -> dict[str, Place]: ...

    def get_towns(self, ids: Sequence[str]) -> dict[str, Town]: ...

    def get_ready_route(self, route_id: str) -> ReadyRoute | None: ...

    def ready_routes_near(self, point: LatLon, hub_radius_km: float, limit: int) -> list[ReadyRoute]: ...


class PriceRepository(Protocol):
    def fuel_price(self, region_code: str, fuel_type: FuelType) -> RegionPrice:
        """Latest `as_of` for (region, fuel); falls back to region "RU"; raises `NotFound` if "RU" missing."""
        ...

    def food_default_check(self, town_population: int) -> int: ...

    def lodging_default_night(self, town_population: int) -> int: ...


class TollRepository(Protocol):
    def segments_on_route(self, route: Route) -> list[TollHit]:
        """Sorted by `km_from`."""
        ...


class RegionLocator(Protocol):
    def locate(self, point: LatLon) -> RegionInfo:
        """Never raises; unknown → RU / Europe/Moscow."""
        ...


class Clock(Protocol):
    def now(self) -> datetime:
        """Aware UTC."""
        ...
