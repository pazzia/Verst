"""Closed enumerations of the planner domain (A§4.1). The value of each member is its wire value."""

from enum import StrEnum


class PlaceType(StrEnum):
    SIGHT = "sight"
    FOOD = "food"
    FUEL = "fuel"
    REST = "rest"
    LODGING = "lodging"


class Tag(StrEnum):
    """The closed tag list of SPEC §9 (18 tags)."""

    DOGS_ALLOWED = "dogs_allowed"
    KIDS_MENU = "kids_menu"
    PLAYGROUND = "playground"
    FAMILY_ROOM = "family_room"
    PARKING = "parking"
    PARKING_GUARDED = "parking_guarded"
    EV_CHARGER = "ev_charger"
    WC = "wc"
    CAFE_AT_FUEL = "cafe_at_fuel"
    H24 = "24h"
    VIEW = "view"
    WALK = "walk"
    MUSEUM = "museum"
    KREMLIN = "kremlin"
    MONASTERY = "monastery"
    EVENING = "evening"
    FREE_ENTRY = "free_entry"
    CASH_ONLY = "cash_only"


class Source(StrEnum):
    CURATED = "curated"
    OSM = "osm"
    PARTNER = "partner"


class PlaceStatus(StrEnum):
    DRAFT = "draft"
    LIVE = "live"
    HIDDEN = "hidden"


class Mood(StrEnum):
    CALM = "calm"
    MORE_STOPS = "more_stops"  # v2 «Побольше остановок»; kept with its old behaviour for saved trips
    JUST_DRIVE = "just_drive"
    FUN = "fun"  # v3 «Весело и познавательно» (ADR-0015 §5)


class FuelType(StrEnum):
    AI92 = "ai92"
    AI95 = "ai95"
    DT = "dt"


class RoadClass(StrEnum):
    MOTORWAY = "motorway"
    TRUNK = "trunk"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    OTHER = "other"


class StopKind(StrEnum):
    START = "start"
    SIGHT = "sight"
    FOOD = "food"
    FUEL = "fuel"
    REST = "rest"
    OVERNIGHT = "overnight"
    VIA = "via"
    FINISH = "finish"
    BORDER = "border"  # CEO 29.10 (trips abroad, server only): a state border crossing on the route


class SignType(StrEnum):
    CITY = "city"
    TOURIST = "tourist"
    FUEL = "fuel"
    FOOD = "food"
    REST = "rest"
    HOTEL = "hotel"


class Meal(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


class OvernightFallback(StrEnum):
    NONE = "none"
    TEMPLATE = "template"
    WIDENED = "widened"
    EXTRA_DAY = "extra_day"
    NO_HOTEL = "no_hotel"


class WarningCode(StrEnum):
    NO_LODGING = "NO_LODGING"
    FUEL_GAP = "FUEL_GAP"
    DAY_OVER_BUDGET = "DAY_OVER_BUDGET"
    TOLLS_UNAVOIDABLE = "TOLLS_UNAVOIDABLE"
    UNVERIFIED_PLACES = "UNVERIFIED_PLACES"
    STOP_CLOSED = "STOP_CLOSED"
    TIME_ZONE = "TIME_ZONE"  # acceptance 2026-10-28 (QA B-4): a day crosses a time-zone border
    ABROAD = "ABROAD"  # CEO 29.10: the trip leaves Russia; prices and rules there are not verified


class StageKey(StrEnum):
    SPLIT = "split"
    LODGING = "lodging"
    HOURS = "hours"
    FUEL = "fuel"
    COST = "cost"
    BUDGET = "budget"


class CostKey(StrEnum):
    FUEL = "fuel"
    TOLLS = "tolls"
    LODGING = "lodging"
    FOOD = "food"
    TICKETS = "tickets"
    PARKING = "parking"  # API v3 (ADR-0015 §4); present only when the world has parking data
    RESERVE = "reserve"


SIGN_BY_KIND: dict[StopKind, SignType] = {
    StopKind.START: SignType.CITY,
    StopKind.FINISH: SignType.CITY,
    StopKind.VIA: SignType.CITY,
    StopKind.SIGHT: SignType.TOURIST,
    StopKind.FUEL: SignType.FUEL,
    StopKind.FOOD: SignType.FOOD,
    StopKind.REST: SignType.REST,
    StopKind.OVERNIGHT: SignType.HOTEL,
    StopKind.BORDER: SignType.CITY,
}
"""Stop kind → road sign (SPEC §5.5). A no-hotel overnight uses `SignType.CITY` instead (A§4.1)."""
