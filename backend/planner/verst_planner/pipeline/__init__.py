"""Planner pipeline (A§6): stage functions share a `PlanContext`.

`Corridor` (A§4.6) lives here because it holds a `geo.PolylineIndex` and `domain` must not import `geo`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from verst_planner.config import PlannerConfig
from verst_planner.domain.enums import RoadClass, WarningCode
from verst_planner.domain.model import (
    Candidate,
    FitKnobs,
    LatLon,
    NormalizedInput,
    Place,
    PlannedStop,
    PlanWarning,
    ReadyRoute,
    RegionInfo,
    Route,
    TownCandidate,
)
from verst_planner.explain.templates import ReasonTemplates
from verst_planner.geo.index import PolylineIndex
from verst_planner.hours import OpeningHours, parse
from verst_planner.pipeline.timeline import Profile
from verst_planner.ports import (
    Clock,
    GeocodingPort,
    ParkingPort,
    PlaceRepository,
    PriceRepository,
    RegionLocator,
    RoutingPort,
    TollRepository,
)

log = logging.getLogger("verst_planner")


@dataclass(slots=True)
class Ports:
    routing: RoutingPort
    places: PlaceRepository
    prices: PriceRepository
    tolls: TollRepository
    regions: RegionLocator
    geocoding: GeocodingPort
    parking: ParkingPort | None = None  # ADR-0015 §4; None = no parking data (fixture worlds)


def _zero_cost(stop: PlannedStop, inp: NormalizedInput) -> int:
    return 0


@dataclass(slots=True)
class PlanContext:
    cfg: PlannerConfig
    templates: ReasonTemplates
    ports: Ports
    clock: Clock
    stop_cost: Callable[[PlannedStop, NormalizedInput], int] = _zero_cost
    """Per-stop cost (A§7.1), injected by the engine from `cost.model` (pipeline may not import cost)."""
    ready_route: ReadyRoute | None = None
    knobs: FitKnobs = field(default_factory=FitKnobs)
    """ADR-0011 budget levers for this plan run (all off = the plain plan)."""
    fuel_warnings: list[PlanWarning] = field(default_factory=list)
    rerun: int = 0
    corridor_towns: list[TownCandidate] = field(default_factory=list)
    """Corridor towns (set once the corridor is built) for the default meal check near a km."""
    _regions: dict[tuple[float, float], RegionInfo] = field(default_factory=dict)
    _region_by_code: dict[str, RegionInfo] = field(default_factory=dict)
    _hours: dict[str, OpeningHours | None] = field(default_factory=dict)
    _profiles: dict[int, Profile] = field(default_factory=dict)

    def profile_for(self, route: Route) -> Profile:
        """The 1-km route profile (cached per route object)."""
        prof = self._profiles.get(id(route))
        if prof is None:
            prof = Profile.from_route(route, self.cfg.drive_time_factor)
            self._profiles = {id(route): prof}
        return prof

    # ------------------------------------------------------------------ regions / tz
    def region_at(self, p: LatLon) -> RegionInfo:
        """Memoised `RegionLocator.locate` keyed by (round(lat, 2), round(lon, 2)) (A§5.3.5)."""
        key = (round(p.lat, 2), round(p.lon, 2))
        hit = self._regions.get(key)
        if hit is None:
            hit = self.ports.regions.locate(p)
            self._regions[key] = hit
            self._region_by_code.setdefault(hit.code, hit)
        return hit

    def region_info(self, code: str) -> RegionInfo | None:
        """A region seen by `region_at` during this plan (None if it was never located)."""
        return self._region_by_code.get(code)

    def default_check_at(self, km: float) -> int:
        """`food_default_check` of the corridor town nearest to route km `km` (A§7.1, A§16.7): the lunch
        stop without `avg_check_rub` and the food line use the same default."""
        if not self.corridor_towns:
            return self.ports.prices.food_default_check(0)
        near = min(self.corridor_towns, key=lambda t: (abs(t.km_at - km), t.town.id))
        return self.ports.prices.food_default_check(near.town.population)

    def tz_of(self, region_code: str, p: LatLon) -> str:
        info = self._region_by_code.get(region_code)
        if info is None:
            info = self.region_at(p)
            if info.code != region_code:
                return info.tz
        return info.tz

    # ------------------------------------------------------------------ opening hours
    def hours(self, place: Place) -> OpeningHours | None:
        """Parsed opening hours (None = always open). Unparseable places were dropped in stage 3."""
        if place.opening_hours is None:
            return None
        if place.id not in self._hours:
            self._hours[place.id] = parse(place.opening_hours)
        return self._hours[place.id]

    def warning(
        self, code: WarningCode, day_no: int | None, detail: str, /, **params: str | int | float
    ) -> PlanWarning:
        return PlanWarning(code, day_no, self.templates.render(f"warning.{code.value}", **params), detail)


@dataclass(slots=True)
class Corridor:
    route: Route
    index: PolylineIndex
    sights: list[Candidate]
    food: list[Candidate]
    fuel: list[Candidate]
    rest: list[Candidate]
    lodgings: list[Candidate]
    towns: list[TownCandidate]


def round_half_up(x: float) -> int:
    """Round-half-up to an integer (Python's `round` is banker's rounding)."""
    return int(Decimal(repr(x)).quantize(Decimal(1), ROUND_HALF_UP))


def detour(lateral_km: float, road_class: RoadClass, cfg: PlannerConfig) -> tuple[float, int]:
    """A§6.3 detour model [D-9]: `(detour_km, detour_min)`."""
    d = cfg.detour
    detour_km = 2.0 * lateral_km * d.winding
    if lateral_km < d.on_road_km:
        return detour_km, 0
    minutes = round_half_up(detour_km / d.speed_kmh * 60.0) + d.access_min
    if road_class is RoadClass.MOTORWAY:
        minutes += d.motorway_exit_min
    return detour_km, minutes


def used_place_ids(stops: list[PlannedStop]) -> set[str]:
    return {s.place.id for s in stops if s.place is not None}
