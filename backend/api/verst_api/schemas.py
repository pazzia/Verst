"""HTTP models (pydantic v2, ADR-0020 §3). The trip shapes are owned by the engine's codec and the bridge
(`docs/contracts/v2`): request models mirror `codec.input_from_json` key for key and are strict about JSON
types (as the bridge is); response models describe the contract for OpenAPI and are checked against every
v2 example in the tests, while handlers return the engine's JSON as is (no re-serialisation, no forked shape).
Value ranges (crew size, daily km, …) are validated once, by the engine."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt

Num = StrictInt | StrictFloat


def _id() -> Any:
    """An optional engine id (place, town, ready route)."""
    return Field(None, min_length=1, max_length=64)


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Contract(BaseModel):
    """A response shape owned by the engine: declared fields are checked, the rest passes through."""

    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------------------------- devices


class DeviceIn(Request):
    appVersion: str = Field(min_length=1, max_length=32, pattern=r"^[0-9A-Za-z.+_-]+$")
    locale: str = Field(
        "ru-RU", min_length=2, max_length=16, pattern=r"^[A-Za-z]{2,3}([-_][A-Za-z0-9]{2,8})*$"
    )


class DeviceOut(BaseModel):
    deviceId: str
    token: str


# ---------------------------------------------------------------------------------------------- trip input


class PointIn(Request):
    lat: Num
    lon: Num
    label: str | None = Field(None, max_length=200)
    placeId: str | None = _id()
    townId: str | None = _id()


class CrewIn(Request):
    adults: StrictInt
    children: StrictInt | None = None
    dog: StrictBool | None = None
    childAges: list[StrictInt] | None = Field(None, max_length=10)


class VehicleIn(Request):
    consumption: Num | None = None
    fuelType: Literal["ai92", "ai95", "dt"] | None = None
    tankL: Num | None = None


class TripInputIn(Request):
    """`codec.input_from_json` / architecture §10.3 TripInputDTO; forwarded with exactly the keys sent."""

    origin: PointIn
    destination: PointIn | None = None
    vias: list[PointIn] | None = Field(
        None, max_length=10
    )  # the engine allows 3 (INVALID_INPUT vias/too_many)
    readyRouteId: str | None = _id()
    roundTrip: StrictBool | None = None
    crew: CrewIn
    dailyKm: StrictInt
    budget: StrictInt | None = None
    vehicle: VehicleIn | None = None
    startAt: str | None = Field(None, max_length=32)
    # "fun" is the v3 «Весело и познавательно» the phone sends; "more_stops" its v2 name (saved trips)
    mood: Literal["calm", "fun", "more_stops", "just_drive"] | None = None
    avoidTolls: StrictBool | None = None
    reserveOn: StrictBool | None = None
    simplify: StrictBool | None = None

    def engine_json(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)


# ---------------------------------------------------------------------------------------------- plan result


class Stop(Contract):
    id: str
    kind: str
    name: str
    lat: float
    lon: float


class Day(Contract):
    day: int
    km: int
    stops: list[Stop]


class Trip(Contract):
    """`codec.plan_to_json(public=False)` + the bridge's v3 decorations (`mobile._trip_result`)."""

    id: str | None = None
    title: str
    km: int
    days: int
    nights: int
    roundTrip: bool
    daysList: list[Day]
    cost: dict[str, Any]
    reasons: dict[str, Any]
    warnings: list[dict[str, Any]]
    input: dict[str, Any]
    engineVersion: str
    engineState: dict[str, Any]
    approxDistances: bool = False  # present (true) only for road-model distances


class PlanOk(Contract):
    outcome: Literal["plan"]
    trip: Trip
    shareText: str
    pricesMonthRu: str
    pricesYear: str
    townPrepRu: dict[str, str]
    townGenRu: dict[str, str]


class PlanNoFit(Contract):
    """ADR-0011 «не помещается в бюджет»: the minimum trip and the options."""

    outcome: Literal["no_fit"]
    budgetRub: int
    allowedRub: int
    minimum: dict[str, Any]
    options: list[dict[str, Any]]
    textRu: str


PlanResult = PlanOk | PlanNoFit


# ---------------------------------------------------------------------------------------------- routes


class RouteIn(Request):
    """ADR-0017 §5: the points the engine's base-route stage will request (`[lat, lon]` each)."""

    points: list[tuple[Num, Num]] = Field(min_length=2, max_length=30)
    avoidTolls: StrictBool = False


class RouteDetailOut(BaseModel):
    fromIdx: int
    toIdx: int
    roadClass: Literal["motorway", "trunk", "primary", "secondary", "other"]
    roadRef: str | None
    toll: bool


class RouteOut(BaseModel):
    points: list[tuple[float, float]]
    cumKm: list[float]
    cumMin: list[float]
    details: list[RouteDetailOut]
    waypointIdx: list[int]
    snapped: list[tuple[float, float]]
    kmTotal: float
    minTotal: float
    synthetic: bool


class ReadyRoute(Contract):
    """`mobile.ready_routes` item."""

    id: str
    title: str
    subtitle: str
    kmTotal: int
    kmSign: int
    ring: Literal["weekend", "long"]  # the home-screen shelf (SPEC §7.6)
    roundTrip: bool
    daysMin: int
    daysMax: int
    tags: list[str]
    hubTownId: str
    bearing8: str
    coverKey: str | None


class ReadyRoutesOut(BaseModel):
    items: list[ReadyRoute]


# ---------------------------------------------------------------------------------------------- trips


class SaveTripIn(Request):
    trip: Trip


class SavedTripOut(BaseModel):
    tripId: str
    shareSlug: str
    shareUrl: str
    title: str
    startTown: str


class SharedTripOut(BaseModel):
    title: str
    startTown: str
    km: int
    days: int
    approxDistances: bool
    shareText: str
    trip: dict[str, Any]


# ------------------------------------------------------------------------------------- feedback, links


class FeedbackIn(Request):
    kind: Literal["closed", "wrong_tag", "price", "other"]
    placeId: str | None = _id()
    tripId: str | None = Field(None, pattern=r"^trp_[0-9a-hjkmnp-tv-z]{12}$")
    text: str | None = Field(None, max_length=1000)


class FeedbackOut(BaseModel):
    id: str


class HotelLinkQuery(Request):
    placeId: str = Field(min_length=1, max_length=64)
    checkin: date
    nights: int = Field(1, ge=1, le=30)
    adults: int = Field(2, ge=1, le=7)
    childrenAges: list[int] = Field(default_factory=list, max_length=5)


class LinkOut(BaseModel):
    url: str | None
    partner: Literal["yandex_travel"]
    affiliate: Literal[False]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any]


class ErrorOut(BaseModel):
    error: ErrorBody
