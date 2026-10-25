"""Domain model of the planner (A§4).

Frozen value types are ``@dataclass(frozen=True, slots=True)`` with tuple/frozenset collections.
The mutable working-state types of A§4.6 are plain ``slots`` dataclasses. ``Corridor`` (A§4.6) lives in
``verst_planner.pipeline`` because it holds a ``geo.PolylineIndex`` and ``domain`` may not import ``geo``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from verst_planner.domain.enums import (
    CostKey,
    FuelType,
    Meal,
    Mood,
    OvernightFallback,
    PlaceStatus,
    PlaceType,
    RoadClass,
    SignType,
    Source,
    StopKind,
    Tag,
    WarningCode,
)
from verst_planner.domain.errors import InvalidInput

# ---------------------------------------------------------------- 4.2 value objects


@dataclass(frozen=True, slots=True)
class LatLon:
    lat: float
    lon: float

    def __post_init__(self) -> None:
        if not -90.0 <= self.lat <= 90.0:
            raise InvalidInput("point", "lat_out_of_range")
        if not -180.0 <= self.lon <= 180.0:
            raise InvalidInput("point", "lon_out_of_range")


@dataclass(frozen=True, slots=True)
class PartnerIds:
    yandex_travel_id: str | None = None
    tripster_id: str | None = None


# ---------------------------------------------------------------- 4.3 input

MAX_ADULTS = 7
MAX_CHILDREN = 5
MAX_CHILD_AGE = 17


@dataclass(frozen=True, slots=True)
class PointInput:
    point: LatLon
    label: str | None = None
    place_id: str | None = None
    town_id: str | None = None


@dataclass(frozen=True, slots=True)
class Crew:
    adults: int
    children: int
    dog: bool
    child_ages: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.adults <= MAX_ADULTS:
            raise InvalidInput("crew.adults", "out_of_range")
        if not 0 <= self.children <= MAX_CHILDREN:
            raise InvalidInput("crew.children", "out_of_range")
        if self.child_ages is not None:
            if len(self.child_ages) != self.children:
                raise InvalidInput("crew.childAges", "length_mismatch")
            if any(not 0 <= a <= MAX_CHILD_AGE for a in self.child_ages):
                raise InvalidInput("crew.childAges", "out_of_range")

    @property
    def people(self) -> int:
        return self.adults + self.children


@dataclass(frozen=True, slots=True)
class Vehicle:
    consumption_l_per_100km: float = 8.0
    fuel_type: FuelType = FuelType.AI95
    tank_l: float = 50.0

    def __post_init__(self) -> None:
        if not 4.0 <= self.consumption_l_per_100km <= 20.0:
            raise InvalidInput("vehicle.consumption", "out_of_range")
        if not 20.0 <= self.tank_l <= 150.0:
            raise InvalidInput("vehicle.tankL", "out_of_range")


@dataclass(frozen=True, slots=True, kw_only=True)
class TripInput:
    origin: PointInput
    destination: PointInput | None
    vias: tuple[PointInput, ...] = ()
    ready_route_id: str | None = None
    round_trip: bool | None = None
    crew: Crew
    daily_km: int
    budget_rub: int | None = None
    vehicle: Vehicle = field(default_factory=Vehicle)
    start_at: datetime | None = None
    mood: Mood | None = None
    avoid_tolls: bool = False
    reserve_on: bool = True
    simplify: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizedInput:
    """`TripInput` with every default resolved. `start_at` is aware (origin tz); `tz` is the origin tz."""

    origin: PointInput
    destination: PointInput | None
    vias: tuple[PointInput, ...]
    ready_route_id: str | None
    round_trip: bool
    crew: Crew
    daily_km: int
    budget_rub: int | None
    vehicle: Vehicle
    start_at: datetime
    mood: Mood
    avoid_tolls: bool
    reserve_on: bool
    simplify: bool
    tz: str


# ---------------------------------------------------------------- 4.4 place DB read models


@dataclass(frozen=True, slots=True)
class Town:
    id: str
    name_ru: str
    name_prep_ru: str | None
    point: LatLon
    region_code: str
    population: int
    quality: int
    evening_walk: bool
    lodging_count_cache: int
    name_gen_ru: str | None = None


@dataclass(frozen=True, slots=True)
class Place:
    id: str
    type: PlaceType
    name_ru: str
    point: LatLon
    address: str | None
    region_code: str
    town_id: str | None
    opening_hours: str | None
    dwell_min: int | None
    avg_check_rub: int | None
    price_night_rub: int | None
    ticket_adult_rub: int | None
    ticket_child_rub: int | None
    rating_internal: float
    tags: frozenset[Tag]
    description_ru: str | None
    partner_ids: PartnerIds
    source: Source
    verified_at: date | None
    status: PlaceStatus
    breakfast_included: bool = True
    family_price_rub: int | None = None
    """Price per night of a family room (≤ 4 guests, ADR-0011); None = `price_night_rub x 1.4`."""
    category: str | None = None
    """ADR-0015 §2 kind of an open-data sight (museum, temple, park, …); None = derived from the tags."""
    quality: float | None = None
    """ADR-0015 §2 quality score 0..1 of an open-data sight; None = curated (no threshold)."""


@dataclass(frozen=True, slots=True)
class ReadyRoutePoint:
    seq: int
    role: Literal["via", "stop"]
    town_id: str | None
    place_id: str | None


@dataclass(frozen=True, slots=True)
class ReadyRoute:
    id: str
    hub_town_id: str
    title_ru: str
    subtitle_ru: str
    points: tuple[ReadyRoutePoint, ...]
    suggested_nights: tuple[str, ...]
    km_total: int
    km_sign: int
    ring: Literal["weekend", "long"]
    round_trip: bool
    days_min: int
    days_max: int
    tags: tuple[str, ...]
    cover_key: str | None
    sort: int
    parent_id: str | None = None
    """A hidden shorter variant of that ready route (ADR-0011 lever 5); never listed by itself."""


@dataclass(frozen=True, slots=True)
class RegionPrice:
    region_code: str
    fuel_type: FuelType
    price_rub: Decimal
    as_of: date


@dataclass(frozen=True, slots=True)
class TollSegment:
    id: str
    road_ref: str
    name_ru: str
    tariff_day_rub: Decimal
    tariff_night_rub: Decimal
    vehicle_class: int
    night_from: time
    night_to: time
    as_of: date


@dataclass(frozen=True, slots=True)
class TollHit:
    segment: TollSegment
    km_from: float
    km_to: float


@dataclass(frozen=True, slots=True)
class RegionInfo:
    code: str
    name_ru: str
    tz: str


@dataclass(frozen=True, slots=True)
class GeoSuggestion:
    kind: Literal["city", "street", "place"]
    name_ru: str
    subtitle_ru: str
    point: LatLon
    osm_id: str


@dataclass(frozen=True, slots=True)
class GeoLabel:
    name_ru: str
    subtitle_ru: str
    region_code: str | None


# ---------------------------------------------------------------- 4.5 routing


@dataclass(frozen=True, slots=True)
class RouteRequest:
    points: tuple[LatLon, ...]
    avoid_tolls: bool


@dataclass(frozen=True, slots=True)
class RouteDetail:
    from_idx: int
    to_idx: int
    road_class: RoadClass
    road_ref: str | None
    toll: bool


@dataclass(frozen=True, slots=True)
class Route:
    points: tuple[LatLon, ...]
    cum_km: tuple[float, ...]
    cum_min: tuple[float, ...]
    details: tuple[RouteDetail, ...]
    waypoint_idx: tuple[int, ...]
    snapped: tuple[LatLon, ...]
    km_total: float
    min_total: float
    synthetic: bool = False
    """Not a road network route: straight legs x the calibrated road model (ADR-0012 §4)."""


# ---------------------------------------------------------------- 4.6 working state (mutable)


@dataclass(slots=True)
class Candidate:
    place: Place
    km_at: float
    lateral_km: float
    detour_km: float
    detour_min: int
    road_class: RoadClass
    region_code: str


@dataclass(slots=True)
class TownCandidate:
    town: Town
    km_at: float
    lateral_km: float
    detour_min: int
    lodgings: list[Candidate]


@dataclass(slots=True)
class PlannedStop:
    kind: StopKind
    km_at: float
    name_ru: str
    point: LatLon
    place: Place | None = None
    town: Town | None = None
    detour_km: float = 0.0
    detour_min: int = 0
    dwell_min: int = 0
    fixed: bool = False
    auto: bool = False
    score: float = 0.0
    meal: Meal | None = None
    reason_key: str = ""
    reason_params: dict[str, str | int | float] = field(default_factory=dict)
    region_code: str = ""
    litres: float = 0.0
    coffee: bool = False
    pool: str = ""
    """Stage pool the stop came from (`rest`, `fuel`, `food`, `sight`; A§16.6), "" for anchors/fixed."""


@dataclass(slots=True)
class ScoredTown:
    town: Town
    km_at: float
    score: float
    h_fit: float
    q_town: int
    e_evening: int
    detour_min: int


@dataclass(slots=True)
class OvernightChoice:
    day: int
    km_at: float
    town: Town | None
    point: LatLon
    name_ru: str
    hotel: Candidate | None
    hotel_options: list[Candidate]
    considered: list[ScoredTown]
    fallback: OvernightFallback
    score: float
    target_km: float
    nearest: Candidate | None = None
    nearest_town: Town | None = None
    region_code: str = ""
    detour_km: float = 0.0
    detour_min: int = 0
    day_start_km: float = 0.0  # km of the day's start (the previous overnight), for `.limit` (A§16.8)


@dataclass(slots=True)
class DayPlan:
    day: int
    km_start: float
    km_end: float
    start_at: datetime
    stops: list[PlannedStop]
    tz: str


# ---------------------------------------------------------------- 7.4 cost units


@dataclass(frozen=True, slots=True)
class FuelRegionUnit:
    region_code: str
    region_name_ru: str
    km: float
    price_rub: Decimal


@dataclass(frozen=True, slots=True)
class FuelUnits:
    consumption_l_per_100km: float
    fuel_type: FuelType
    regions: tuple[FuelRegionUnit, ...]
    as_of: str
    trip_km: int | None = None
    """The km shown in the fuel formula: `TripPlan.km` (A§16.7); None = Σ region km (older units)."""


@dataclass(frozen=True, slots=True)
class TollUnit:
    segment_id: str
    road_ref: str
    rub: int
    night: bool
    as_of: str


@dataclass(frozen=True, slots=True)
class HotelPrice:
    place_id: str
    price_night_rub: int
    breakfast_included: bool = True
    rooms: int | None = None
    """Rooms the engine chose for this option (family rooms, ADR-0011); None = `ceil(adults / 2)`."""


@dataclass(frozen=True, slots=True)
class NightUnit:
    stop_id: str
    day: int
    town_name_ru: str
    selected_place_id: str | None
    price_night_rub: int
    options: tuple[HotelPrice, ...]
    default_price: bool
    breakfast_included: bool
    breakfast_check_rub: int
    rooms: int | None = None
    """Rooms of the selected option (ADR-0011); None = `ceil(adults / 2)`."""


@dataclass(frozen=True, slots=True)
class MealUnit:
    day: int
    meal: Meal
    stop_id: str | None
    check_rub: int


@dataclass(frozen=True, slots=True)
class TicketUnit:
    stop_id: str
    place_id: str
    name_ru: str
    adult_rub: int
    child_rub: int


@dataclass(frozen=True, slots=True)
class ParkingUnit:
    """ADR-0015 §4: paid parking at one car stop. `rub_per_hour` None = unknown (no zone, no OSM charge)."""

    stop_id: str
    name_ru: str
    rub_per_hour: int | None
    hours: int
    rub: int | None  # round10(rub_per_hour x hours); 0 = free; None = unknown
    source: str  # "zone" | "osm" | "free" | "unknown"


@dataclass(frozen=True, slots=True)
class CostUnits:
    fuel: FuelUnits
    tolls: tuple[TollUnit, ...]
    nights: tuple[NightUnit, ...]
    meals: tuple[MealUnit, ...]
    tickets: tuple[TicketUnit, ...]
    reserve_frac: Decimal
    line_step: int
    total_step: int
    child_ages: tuple[int, ...] | None
    assumed_child_age: int
    child_food_weight_under7: Decimal
    as_of: tuple[tuple[str, str], ...] = ()
    """`(line key, "YYYY-MM")` freshness per line, so offline recompute keeps `CostLine.as_of`."""
    mood_just_drive: bool = False
    """Mood is already «Только доехать» (then the `just_drive` overspend hint is not offered)."""
    parking: tuple[ParkingUnit, ...] = ()
    """ADR-0015 §4 per-stop parking; empty = no parking data (no «Парковки» line, fixture worlds)."""


@dataclass(frozen=True, slots=True)
class AltUnits:
    delta_km: float
    region_code: str
    check_rub: int | None
    adult_rub: int | None
    child_rub: int | None
    name_ru: str
    place_id: str
    price_rub: Decimal | None = None
    """Fuel price in `region_code`, so a replace into a region the trip did not cross adds its unit."""
    region_name_ru: str = ""
    trip_km_delta: int = 0
    """`round(day km of the trial day) - round(day km of the current day)` (A§16.11.4 rule 2)."""
    parking: ParkingUnit | None = None
    """API v3 (ADR-0015 §4): the alternative's own parking at its arrival and dwell, when the trip is priced
    with a parking model; None = no parking data (no line) or not a car-parked stop (rest, food, fuel)."""


@dataclass(frozen=True, slots=True)
class CostOverrides:
    hotel_by_stop: Mapping[str, str] = field(default_factory=dict)
    replaced: Mapping[str, AltUnits] = field(default_factory=dict)


# ---------------------------------------------------------------- 4.7 output


@dataclass(frozen=True, slots=True)
class HotelOption:
    place_id: str
    name_ru: str
    tags: tuple[Tag, ...]
    price_night_rub: int
    rooms: int
    price_crew_rub: int
    verified: bool
    # OI-41: distance from the route (motorway exit) to the hotel in metres, for the 5.7 exit sign «800 м».
    exit_distance_m: int = 0


@dataclass(frozen=True, slots=True)
class ScheduledStop:
    id: str
    seq: int
    day: int
    kind: StopKind
    sign: SignType
    place_id: str | None
    town_id: str | None
    name_ru: str
    note_ru: str | None
    point: LatLon
    arrive_at: datetime | None
    depart_at: datetime | None
    tz: str
    km_from_prev: int
    km_at: int
    dwell_min: int
    tags: tuple[Tag, ...]
    cost_rub: int
    verified: bool
    reason_ru: str
    replaceable: bool
    alternatives: tuple[Alternative, ...]
    hotel_options: tuple[HotelOption, ...]
    selected_hotel_id: str | None
    alternatives_note_ru: str | None = None
    """A§16.6: «Других вариантов…» / «Нашли только один…» when fewer than two alternatives were found."""
    fun_for: tuple[str, ...] = ()
    """ADR-0015 §5 (API v3 `funFor`): who a «Весело и познавательно» stop is for — child, dog, adults."""


@dataclass(frozen=True, slots=True)
class StopTime:
    """One row of an alternative's day patch (A§16.6): the day as it is after the replace."""

    stop_id: str
    seq: int
    arrive_at: datetime | None
    depart_at: datetime | None
    km_from_prev: int


@dataclass(frozen=True, slots=True)
class Alternative:
    id: str
    place_id: str
    name_ru: str
    delta_min: int
    delta_rub: int
    shift_min: int
    stop: ScheduledStop
    units: AltUnits
    day_patch: tuple[StopTime, ...] = ()
    breaks_budget: bool = False
    """ADR-0011: the trip total with this alternative exceeds the budget tolerance."""


@dataclass(frozen=True, slots=True)
class DayResult:
    day: int
    km: int
    drive_min: int
    tz: str
    start_at: datetime
    end_at: datetime
    stops: tuple[ScheduledStop, ...]
    over_budget: bool


@dataclass(frozen=True, slots=True)
class CostBreakdownRow:
    label_ru: str
    formula_ru: str
    rub: int


@dataclass(frozen=True, slots=True)
class CostLine:
    key: CostKey
    title_ru: str
    rub: int
    formula_ru: str
    as_of: str
    breakdown: tuple[CostBreakdownRow, ...]
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class CostResult:
    lines: tuple[CostLine, ...]
    reserve_on: bool
    subtotal_rub: int
    total_rub: int
    per_person_rub: int
    budget_rub: int | None
    remaining_rub: int | None
    over_budget: bool
    hint_keys: tuple[str, ...]
    prices_as_of: str
    units: CostUnits
    hints_ru: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OvernightReason:
    day: int
    town_id: str | None
    town: str
    text: str
    candidates: tuple[str, ...]
    fallback: OvernightFallback = OvernightFallback.NONE


@dataclass(frozen=True, slots=True)
class PlanWarning:
    code: WarningCode
    day: int | None
    message_ru: str
    detail: str


# ---------------------------------------------------------------- engine state (server-only)


@dataclass(frozen=True, slots=True)
class StopState:
    """Scheduling inputs of one planned stop, kept so `replace_stop` can re-schedule a day offline."""

    stop_id: str
    kind: StopKind
    km_at: float
    detour_km: float
    detour_min: int
    dwell_min: int
    fixed: bool
    auto: bool
    score: float
    place_id: str | None
    region_code: str
    reason_key: str = ""
    reason_params: tuple[tuple[str, str | int | float], ...] = ()
    meal: Meal | None = None
    litres: float = 0.0
    coffee: bool = False
    pool: str = ""


@dataclass(frozen=True, slots=True)
class DayState:
    day: int
    km_start: float
    km_end: float
    start_at: datetime
    tz: str
    budget_min: int
    stops: tuple[StopState, ...]


@dataclass(frozen=True, slots=True)
class CandidateState:
    """A corridor candidate (sight/food/fuel/rest) without its place body (re-read by id)."""

    place_id: str
    km_at: float
    lateral_km: float
    detour_km: float
    detour_min: int
    road_class: RoadClass
    region_code: str


@dataclass(frozen=True, slots=True)
class EngineState:
    profile_km: tuple[float, ...]
    profile_min: tuple[float, ...]
    region_km: tuple[tuple[str, float], ...]
    toll_hits: tuple[TollHit, ...]
    drive_time_factor: float
    days: tuple[DayState, ...] = ()
    candidates: tuple[CandidateState, ...] = ()
    rerun: int = 0
    town_kms: tuple[tuple[str, float], ...] = ()  # corridor towns (id, km_at), for reasons on replace


@dataclass(frozen=True, slots=True)
class FitKnobs:
    """ADR-0011 budget levers inside the stages (all off = the plain plan)."""

    lodging_cheap: bool = False
    family_rooms: bool = False
    food_economy: bool = False
    sights_free: bool = False

    @property
    def any(self) -> bool:
        return self.lodging_cheap or self.family_rooms or self.food_economy or self.sights_free


@dataclass(frozen=True, slots=True)
class BudgetLever:
    code: str
    saved_rub: int


@dataclass(frozen=True, slots=True)
class BudgetFit:
    status: str  # "fits" | "small_overrun"
    budget_rub: int
    allowed_rub: int
    initial_total_rub: int
    total_rub: int
    levers: tuple[BudgetLever, ...]
    text_ru: str
    variant_of: str | None = None


@dataclass(frozen=True, slots=True)
class TripPlan:
    title_ru: str
    km: int
    days: int
    nights: int
    round_trip: bool
    days_list: tuple[DayResult, ...]
    cost: CostResult
    overnight_reasons: tuple[OvernightReason, ...]
    warnings: tuple[PlanWarning, ...]
    input: NormalizedInput
    engine_version: str
    engine_state: EngineState
    approx_distances: bool = False
    """The route is synthetic (ADR-0012 §4): distances and times are estimates («≈»)."""
    budget_fit: BudgetFit | None = None
    """ADR-0011: set when the first plan exceeded the budget and the fitter changed the trip."""


class _Unset:
    _instance: _Unset | None = None

    def __new__(cls) -> _Unset:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNSET"


UNSET = _Unset()
Unset = _Unset


@dataclass(frozen=True, slots=True)
class CostPatch:
    """A§6.1: changes that only recompute cost (PATCH /v1/trips/{id})."""

    crew: Crew | None = None
    budget_rub: int | Unset | None = UNSET
    reserve_on: bool | None = None
    hotel_choice: tuple[str, str] | None = None


ReplaceableKinds = frozenset({StopKind.SIGHT, StopKind.FOOD, StopKind.FUEL, StopKind.REST})
