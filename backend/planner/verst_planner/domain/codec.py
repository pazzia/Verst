"""JSON codec between domain dataclasses and the camelCase wire format of A§10.3.

Conventions: datetimes are local wall-time strings ``YYYY-MM-DDTHH:MM`` (no offset) next to a ``tz`` field;
``Decimal`` values inside cost units and engine state are strings with 2 decimals; enums are their values.
``engineState`` is emitted only by ``plan_to_json(plan, public=False)``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast
from zoneinfo import ZoneInfo

from verst_planner.domain.enums import (
    CostKey,
    FuelType,
    Meal,
    Mood,
    OvernightFallback,
    RoadClass,
    SignType,
    StopKind,
    Tag,
    WarningCode,
)
from verst_planner.domain.errors import InvalidInput
from verst_planner.domain.model import (
    Alternative,
    AltUnits,
    CandidateState,
    CostBreakdownRow,
    CostLine,
    CostResult,
    CostUnits,
    Crew,
    DayResult,
    DayState,
    EngineState,
    FuelRegionUnit,
    FuelUnits,
    HotelOption,
    HotelPrice,
    LatLon,
    MealUnit,
    NightUnit,
    NormalizedInput,
    OvernightReason,
    PlanWarning,
    PointInput,
    ScheduledStop,
    StopState,
    StopTime,
    TicketUnit,
    TollHit,
    TollSegment,
    TollUnit,
    TripInput,
    TripPlan,
    Vehicle,
)

Json = dict[str, Any]

_DT_FMT = "%Y-%m-%dT%H:%M"
_CENT = Decimal("0.01")

# ---------------------------------------------------------------- primitives


def dt_to_str(dt: datetime | None) -> str | None:
    """Naive local datetime → ``YYYY-MM-DDTHH:MM``."""
    if dt is None:
        return None
    return dt.strftime(_DT_FMT)


def dt_from_str(s: str | None) -> datetime | None:
    if s is None:
        return None
    return datetime.fromisoformat(s)


def _local_naive(dt: datetime, tz: str) -> datetime:
    return dt.astimezone(ZoneInfo(tz)).replace(tzinfo=None)


def _aware_from_local(s: str, tz: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=ZoneInfo(tz))


def dec_to_str(x: Decimal) -> str:
    return str(x.quantize(_CENT, ROUND_HALF_UP))


def _dec(s: str | int | float) -> Decimal:
    return Decimal(str(s))


def _time_to_str(t: time) -> str:
    return t.strftime("%H:%M")


# ---------------------------------------------------------------- input

_INPUT_KEYS = frozenset(
    {
        "origin",
        "destination",
        "vias",
        "readyRouteId",
        "roundTrip",
        "crew",
        "dailyKm",
        "budget",
        "vehicle",
        "startAt",
        "mood",
        "avoidTolls",
        "reserveOn",
        "simplify",
    }
)
_POINT_KEYS = frozenset({"lat", "lon", "label", "placeId", "townId"})
_CREW_KEYS = frozenset({"adults", "children", "dog", "childAges"})
_VEHICLE_KEYS = frozenset({"consumption", "fuelType", "tankL"})


def _check_keys(d: Mapping[str, Any], allowed: frozenset[str], path: str) -> None:
    for k in d:
        if k not in allowed:
            raise InvalidInput(f"{path}{k}", "unknown_field")


def _point_input_from_json(d: Any, path: str) -> PointInput:
    if not isinstance(d, Mapping):
        raise InvalidInput(path, "not_an_object")
    _check_keys(d, _POINT_KEYS, path + ".")
    try:
        point = LatLon(float(d["lat"]), float(d["lon"]))
    except KeyError as e:
        raise InvalidInput(f"{path}.{e.args[0]}", "required") from None
    return PointInput(point=point, label=d.get("label"), place_id=d.get("placeId"), town_id=d.get("townId"))


def _point_input_to_json(p: PointInput) -> Json:
    return {
        "lat": p.point.lat,
        "lon": p.point.lon,
        "label": p.label,
        "placeId": p.place_id,
        "townId": p.town_id,
    }


def _crew_from_json(d: Any) -> Crew:
    if not isinstance(d, Mapping):
        raise InvalidInput("crew", "not_an_object")
    _check_keys(d, _CREW_KEYS, "crew.")
    ages = d.get("childAges")
    return Crew(
        adults=int(d.get("adults", 0)),
        children=int(d.get("children", 0)),
        dog=bool(d.get("dog", False)),
        child_ages=None if ages is None else tuple(int(a) for a in ages),
    )


def crew_from_json(d: Any) -> Crew:
    """Public form of the crew decoder (used by the app-facing `mobile.patch_cost`)."""
    return _crew_from_json(d)


def _crew_to_json(c: Crew) -> Json:
    return {
        "adults": c.adults,
        "children": c.children,
        "dog": c.dog,
        "childAges": None if c.child_ages is None else list(c.child_ages),
    }


def _vehicle_from_json(d: Any) -> Vehicle:
    if d is None:
        return Vehicle()
    if not isinstance(d, Mapping):
        raise InvalidInput("vehicle", "not_an_object")
    _check_keys(d, _VEHICLE_KEYS, "vehicle.")
    try:
        fuel_type = FuelType(d.get("fuelType", "ai95"))
    except ValueError:
        raise InvalidInput("vehicle.fuelType", "unknown_value") from None
    return Vehicle(
        consumption_l_per_100km=float(d.get("consumption", 8.0)),
        fuel_type=fuel_type,
        tank_l=float(d.get("tankL", 50.0)),
    )


def _vehicle_to_json(v: Vehicle) -> Json:
    return {"consumption": v.consumption_l_per_100km, "fuelType": v.fuel_type.value, "tankL": v.tank_l}


def input_from_json(d: Mapping[str, Any]) -> TripInput:
    """Request body (TripInputDTO shape) → `TripInput`. Unknown keys raise `InvalidInput`."""
    _check_keys(d, _INPUT_KEYS, "")
    if "origin" not in d:
        raise InvalidInput("origin", "required")
    if "crew" not in d:
        raise InvalidInput("crew", "required")
    if "dailyKm" not in d:
        raise InvalidInput("dailyKm", "required")
    dest = d.get("destination")
    start_raw = d.get("startAt")
    start_at = None
    if start_raw is not None:
        try:
            start_at = datetime.fromisoformat(start_raw)
        except (TypeError, ValueError):
            raise InvalidInput("startAt", "bad_format") from None
        if start_at.tzinfo is not None:
            raise InvalidInput("startAt", "must_be_local_without_offset")
    mood_raw = d.get("mood")
    try:
        mood = None if mood_raw is None else Mood(mood_raw)
    except ValueError:
        raise InvalidInput("mood", "unknown_value") from None
    budget = d.get("budget")
    return TripInput(
        origin=_point_input_from_json(d["origin"], "origin"),
        destination=None if dest is None else _point_input_from_json(dest, "destination"),
        vias=tuple(_point_input_from_json(v, f"vias[{i}]") for i, v in enumerate(d.get("vias") or ())),
        ready_route_id=d.get("readyRouteId"),
        round_trip=d.get("roundTrip"),
        crew=_crew_from_json(d["crew"]),
        daily_km=int(d["dailyKm"]),
        budget_rub=None if budget is None else int(budget),
        vehicle=_vehicle_from_json(d.get("vehicle")),
        start_at=start_at,
        mood=mood,
        avoid_tolls=bool(d.get("avoidTolls", False)),
        reserve_on=bool(d.get("reserveOn", True)),
        simplify=bool(d.get("simplify", False)),
    )


def input_to_json(i: TripInput) -> Json:
    return {
        "origin": _point_input_to_json(i.origin),
        "destination": None if i.destination is None else _point_input_to_json(i.destination),
        "vias": [_point_input_to_json(v) for v in i.vias],
        "readyRouteId": i.ready_route_id,
        "roundTrip": i.round_trip,
        "crew": _crew_to_json(i.crew),
        "dailyKm": i.daily_km,
        "budget": i.budget_rub,
        "vehicle": _vehicle_to_json(i.vehicle),
        "startAt": dt_to_str(i.start_at),
        "mood": None if i.mood is None else i.mood.value,
        "avoidTolls": i.avoid_tolls,
        "reserveOn": i.reserve_on,
        "simplify": i.simplify,
    }


def normalized_to_json(n: NormalizedInput) -> Json:
    return {
        "origin": _point_input_to_json(n.origin),
        "destination": None if n.destination is None else _point_input_to_json(n.destination),
        "vias": [_point_input_to_json(v) for v in n.vias],
        "readyRouteId": n.ready_route_id,
        "roundTrip": n.round_trip,
        "crew": _crew_to_json(n.crew),
        "dailyKm": n.daily_km,
        "budget": n.budget_rub,
        "vehicle": _vehicle_to_json(n.vehicle),
        "startAt": dt_to_str(_local_naive(n.start_at, n.tz)),
        "tz": n.tz,
        "mood": n.mood.value,
        "avoidTolls": n.avoid_tolls,
        "reserveOn": n.reserve_on,
        "simplify": n.simplify,
    }


def normalized_from_json(d: Mapping[str, Any]) -> NormalizedInput:
    dest = d.get("destination")
    return NormalizedInput(
        origin=_point_input_from_json(d["origin"], "origin"),
        destination=None if dest is None else _point_input_from_json(dest, "destination"),
        vias=tuple(_point_input_from_json(v, f"vias[{i}]") for i, v in enumerate(d["vias"])),
        ready_route_id=d["readyRouteId"],
        round_trip=bool(d["roundTrip"]),
        crew=_crew_from_json(d["crew"]),
        daily_km=int(d["dailyKm"]),
        budget_rub=d["budget"],
        vehicle=_vehicle_from_json(d["vehicle"]),
        start_at=_aware_from_local(d["startAt"], d["tz"]),
        mood=Mood(d["mood"]),
        avoid_tolls=bool(d["avoidTolls"]),
        reserve_on=bool(d["reserveOn"]),
        simplify=bool(d["simplify"]),
        tz=d["tz"],
    )


# ---------------------------------------------------------------- plan: stops and days


def _tags_to_json(tags: tuple[Tag, ...]) -> list[str]:
    return [t.value for t in tags]


def _tags_from_json(tags: list[str]) -> tuple[Tag, ...]:
    return tuple(Tag(t) for t in tags)


def _hotel_option_to_json(h: HotelOption) -> Json:
    return {
        "placeId": h.place_id,
        "name": h.name_ru,
        "tags": _tags_to_json(h.tags),
        "priceNightRub": h.price_night_rub,
        "rooms": h.rooms,
        "priceCrewRub": h.price_crew_rub,
        "verified": h.verified,
        "exitDistanceM": h.exit_distance_m,
    }


def _hotel_option_from_json(d: Mapping[str, Any]) -> HotelOption:
    return HotelOption(
        place_id=d["placeId"],
        name_ru=d["name"],
        tags=_tags_from_json(d["tags"]),
        price_night_rub=d["priceNightRub"],
        rooms=d["rooms"],
        price_crew_rub=d["priceCrewRub"],
        verified=d["verified"],
        exit_distance_m=int(d.get("exitDistanceM", 0)),
    )


def alt_units_to_json(u: AltUnits) -> Json:
    return {
        "deltaKm": u.delta_km,
        "regionCode": u.region_code,
        "checkRub": u.check_rub,
        "adultRub": u.adult_rub,
        "childRub": u.child_rub,
        "name": u.name_ru,
        "placeId": u.place_id,
        "priceRub": None if u.price_rub is None else dec_to_str(u.price_rub),
        "regionName": u.region_name_ru,
        "tripKmDelta": u.trip_km_delta,
    }


def alt_units_from_json(d: Mapping[str, Any]) -> AltUnits:
    return AltUnits(
        delta_km=float(d["deltaKm"]),
        region_code=d["regionCode"],
        check_rub=d["checkRub"],
        adult_rub=d["adultRub"],
        child_rub=d["childRub"],
        name_ru=d["name"],
        place_id=d["placeId"],
        price_rub=None if d.get("priceRub") is None else _dec(d["priceRub"]),
        region_name_ru=d.get("regionName", ""),
        trip_km_delta=int(d.get("tripKmDelta", 0)),
    )


def _alternative_to_json(a: Alternative) -> Json:
    return {
        "id": a.id,
        "placeId": a.place_id,
        "name": a.name_ru,
        "deltaMin": a.delta_min,
        "deltaRub": a.delta_rub,
        "shiftMin": a.shift_min,
        "units": alt_units_to_json(a.units),
        "stop": stop_to_json(a.stop),
        "dayPatch": [
            {
                "stopId": p.stop_id,
                "seq": p.seq,
                "arriveAt": dt_to_str(p.arrive_at),
                "departAt": dt_to_str(p.depart_at),
                "kmFromPrev": p.km_from_prev,
            }
            for p in a.day_patch
        ],
    }


def _alternative_from_json(d: Mapping[str, Any]) -> Alternative:
    return Alternative(
        id=d["id"],
        place_id=d["placeId"],
        name_ru=d["name"],
        delta_min=d["deltaMin"],
        delta_rub=d["deltaRub"],
        shift_min=d["shiftMin"],
        stop=stop_from_json(d["stop"]),
        units=alt_units_from_json(d["units"]),
        day_patch=tuple(
            StopTime(
                p["stopId"], p["seq"], dt_from_str(p["arriveAt"]), dt_from_str(p["departAt"]), p["kmFromPrev"]
            )
            for p in d.get("dayPatch", [])
        ),
    )


def stop_to_json(s: ScheduledStop) -> Json:
    return {
        "id": s.id,
        "seq": s.seq,
        "day": s.day,
        "kind": s.kind.value,
        "sign": s.sign.value,
        "placeId": s.place_id,
        "townId": s.town_id,
        "name": s.name_ru,
        "note": s.note_ru,
        "lat": s.point.lat,
        "lon": s.point.lon,
        "arriveAt": dt_to_str(s.arrive_at),
        "departAt": dt_to_str(s.depart_at),
        "tz": s.tz,
        "kmFromPrev": s.km_from_prev,
        "kmAt": s.km_at,
        "dwellMin": s.dwell_min,
        "tags": _tags_to_json(s.tags),
        "costRub": s.cost_rub,
        "reason": s.reason_ru,
        "verified": s.verified,
        "replaceable": s.replaceable,
        "alternatives": [_alternative_to_json(a) for a in s.alternatives],
        "alternativesNote": s.alternatives_note_ru,
        "hotelOptions": [_hotel_option_to_json(h) for h in s.hotel_options],
        "selectedHotelId": s.selected_hotel_id,
    }


def stop_from_json(d: Mapping[str, Any]) -> ScheduledStop:
    return ScheduledStop(
        id=d["id"],
        seq=d["seq"],
        day=d["day"],
        kind=StopKind(d["kind"]),
        sign=SignType(d["sign"]),
        place_id=d["placeId"],
        town_id=d["townId"],
        name_ru=d["name"],
        note_ru=d["note"],
        point=LatLon(d["lat"], d["lon"]),
        arrive_at=dt_from_str(d["arriveAt"]),
        depart_at=dt_from_str(d["departAt"]),
        tz=d["tz"],
        km_from_prev=d["kmFromPrev"],
        km_at=d["kmAt"],
        dwell_min=d["dwellMin"],
        tags=_tags_from_json(d["tags"]),
        cost_rub=d["costRub"],
        verified=d["verified"],
        reason_ru=d["reason"],
        replaceable=d["replaceable"],
        alternatives=tuple(_alternative_from_json(a) for a in d["alternatives"]),
        hotel_options=tuple(_hotel_option_from_json(h) for h in d["hotelOptions"]),
        selected_hotel_id=d["selectedHotelId"],
        alternatives_note_ru=d.get("alternativesNote"),
    )


def _day_to_json(d: DayResult) -> Json:
    return {
        "day": d.day,
        "km": d.km,
        "driveMin": d.drive_min,
        "tz": d.tz,
        "startAt": dt_to_str(d.start_at),
        "endAt": dt_to_str(d.end_at),
        "overBudget": d.over_budget,
        "stops": [stop_to_json(s) for s in d.stops],
    }


def _day_from_json(d: Mapping[str, Any]) -> DayResult:
    start = dt_from_str(d["startAt"])
    end = dt_from_str(d["endAt"])
    assert start is not None and end is not None
    return DayResult(
        day=d["day"],
        km=d["km"],
        drive_min=d["driveMin"],
        tz=d["tz"],
        start_at=start,
        end_at=end,
        stops=tuple(stop_from_json(s) for s in d["stops"]),
        over_budget=d["overBudget"],
    )


# ---------------------------------------------------------------- cost


def units_to_json(u: CostUnits) -> Json:
    return {
        "fuel": {
            "consumption": u.fuel.consumption_l_per_100km,
            "fuelType": u.fuel.fuel_type.value,
            "regions": [
                {
                    "regionCode": r.region_code,
                    "regionName": r.region_name_ru,
                    "km": r.km,
                    "priceRub": dec_to_str(r.price_rub),
                }
                for r in u.fuel.regions
            ],
            "asOf": u.fuel.as_of,
            "tripKm": u.fuel.trip_km,
        },
        "tolls": [
            {
                "segmentId": t.segment_id,
                "roadRef": t.road_ref,
                "rub": t.rub,
                "night": t.night,
                "asOf": t.as_of,
            }
            for t in u.tolls
        ],
        "nights": [
            {
                "stopId": n.stop_id,
                "day": n.day,
                "townName": n.town_name_ru,
                "selectedPlaceId": n.selected_place_id,
                "priceNightRub": n.price_night_rub,
                "options": [
                    {
                        "placeId": o.place_id,
                        "priceNightRub": o.price_night_rub,
                        "breakfastIncluded": o.breakfast_included,
                    }
                    for o in n.options
                ],
                "defaultPrice": n.default_price,
                "breakfastIncluded": n.breakfast_included,
                "breakfastCheckRub": n.breakfast_check_rub,
            }
            for n in u.nights
        ],
        "meals": [
            {"day": m.day, "meal": m.meal.value, "stopId": m.stop_id, "checkRub": m.check_rub}
            for m in u.meals
        ],
        "tickets": [
            {
                "stopId": t.stop_id,
                "placeId": t.place_id,
                "name": t.name_ru,
                "adultRub": t.adult_rub,
                "childRub": t.child_rub,
            }
            for t in u.tickets
        ],
        "reserveFrac": dec_to_str(u.reserve_frac),
        "lineStep": u.line_step,
        "totalStep": u.total_step,
        "childAges": None if u.child_ages is None else list(u.child_ages),
        "assumedChildAge": u.assumed_child_age,
        "childFoodWeightUnder7": dec_to_str(u.child_food_weight_under7),
        "asOf": {k: v for k, v in u.as_of},
        "moodJustDrive": u.mood_just_drive,
    }


def units_from_json(d: Mapping[str, Any]) -> CostUnits:
    f = d["fuel"]
    ages = d["childAges"]
    return CostUnits(
        fuel=FuelUnits(
            consumption_l_per_100km=float(f["consumption"]),
            fuel_type=FuelType(f["fuelType"]),
            regions=tuple(
                FuelRegionUnit(r["regionCode"], r["regionName"], float(r["km"]), _dec(r["priceRub"]))
                for r in f["regions"]
            ),
            as_of=f["asOf"],
            trip_km=f.get("tripKm"),
        ),
        tolls=tuple(
            TollUnit(t["segmentId"], t["roadRef"], t["rub"], t["night"], t["asOf"]) for t in d["tolls"]
        ),
        nights=tuple(
            NightUnit(
                stop_id=n["stopId"],
                day=n["day"],
                town_name_ru=n["townName"],
                selected_place_id=n["selectedPlaceId"],
                price_night_rub=n["priceNightRub"],
                options=tuple(
                    HotelPrice(o["placeId"], o["priceNightRub"], o.get("breakfastIncluded", True))
                    for o in n["options"]
                ),
                default_price=n["defaultPrice"],
                breakfast_included=n["breakfastIncluded"],
                breakfast_check_rub=n["breakfastCheckRub"],
            )
            for n in d["nights"]
        ),
        meals=tuple(MealUnit(m["day"], Meal(m["meal"]), m["stopId"], m["checkRub"]) for m in d["meals"]),
        tickets=tuple(
            TicketUnit(t["stopId"], t["placeId"], t["name"], t["adultRub"], t["childRub"])
            for t in d["tickets"]
        ),
        reserve_frac=_dec(d["reserveFrac"]),
        line_step=d["lineStep"],
        total_step=d["totalStep"],
        child_ages=None if ages is None else tuple(ages),
        assumed_child_age=d["assumedChildAge"],
        child_food_weight_under7=_dec(d["childFoodWeightUnder7"]),
        as_of=tuple((str(k), str(v)) for k, v in d.get("asOf", {}).items()),
        mood_just_drive=bool(d.get("moodJustDrive", False)),
    )


def _line_to_json(line: CostLine) -> Json:
    return {
        "key": line.key.value,
        "title": line.title_ru,
        "rub": line.rub,
        "formula": line.formula_ru,
        "asOf": line.as_of,
        "enabled": line.enabled,
        "breakdown": [{"label": b.label_ru, "formula": b.formula_ru, "rub": b.rub} for b in line.breakdown],
    }


def _line_from_json(d: Mapping[str, Any]) -> CostLine:
    return CostLine(
        key=CostKey(d["key"]),
        title_ru=d["title"],
        rub=d["rub"],
        formula_ru=d["formula"],
        as_of=d["asOf"],
        breakdown=tuple(CostBreakdownRow(b["label"], b["formula"], b["rub"]) for b in d["breakdown"]),
        enabled=d["enabled"],
    )


def cost_to_json(c: CostResult) -> Json:
    return {
        "lines": [_line_to_json(line) for line in c.lines],
        "reserveOn": c.reserve_on,
        "subtotalRub": c.subtotal_rub,
        "totalRub": c.total_rub,
        "perPersonRub": c.per_person_rub,
        "budgetRub": c.budget_rub,
        "remainingRub": c.remaining_rub,
        "overBudget": c.over_budget,
        "hints": list(c.hints_ru),
        "hintKeys": list(c.hint_keys),
        "pricesAsOf": c.prices_as_of,
        "units": units_to_json(c.units),
    }


def cost_from_json(d: Mapping[str, Any]) -> CostResult:
    return CostResult(
        lines=tuple(_line_from_json(line) for line in d["lines"]),
        reserve_on=d["reserveOn"],
        subtotal_rub=d["subtotalRub"],
        total_rub=d["totalRub"],
        per_person_rub=d["perPersonRub"],
        budget_rub=d["budgetRub"],
        remaining_rub=d["remainingRub"],
        over_budget=d["overBudget"],
        hint_keys=tuple(d["hintKeys"]),
        prices_as_of=d["pricesAsOf"],
        units=units_from_json(d["units"]),
        hints_ru=tuple(d["hints"]),
    )


# ---------------------------------------------------------------- engine state


def _segment_to_json(s: TollSegment) -> Json:
    return {
        "id": s.id,
        "roadRef": s.road_ref,
        "name": s.name_ru,
        "tariffDayRub": dec_to_str(s.tariff_day_rub),
        "tariffNightRub": dec_to_str(s.tariff_night_rub),
        "vehicleClass": s.vehicle_class,
        "nightFrom": _time_to_str(s.night_from),
        "nightTo": _time_to_str(s.night_to),
        "asOf": s.as_of.isoformat(),
    }


def _segment_from_json(d: Mapping[str, Any]) -> TollSegment:
    return TollSegment(
        id=d["id"],
        road_ref=d["roadRef"],
        name_ru=d["name"],
        tariff_day_rub=_dec(d["tariffDayRub"]),
        tariff_night_rub=_dec(d["tariffNightRub"]),
        vehicle_class=d["vehicleClass"],
        night_from=time.fromisoformat(d["nightFrom"]),
        night_to=time.fromisoformat(d["nightTo"]),
        as_of=date.fromisoformat(d["asOf"]),
    )


def _stop_state_to_json(s: StopState) -> Json:
    return {
        "stopId": s.stop_id,
        "kind": s.kind.value,
        "kmAt": s.km_at,
        "detourKm": s.detour_km,
        "detourMin": s.detour_min,
        "dwellMin": s.dwell_min,
        "fixed": s.fixed,
        "auto": s.auto,
        "score": s.score,
        "placeId": s.place_id,
        "regionCode": s.region_code,
        "reasonKey": s.reason_key,
        "reasonParams": [[k, v] for k, v in s.reason_params],
        "meal": None if s.meal is None else s.meal.value,
        "litres": s.litres,
        "coffee": s.coffee,
        "pool": s.pool,
    }


def _stop_state_from_json(d: Mapping[str, Any]) -> StopState:
    return StopState(
        stop_id=d["stopId"],
        kind=StopKind(d["kind"]),
        km_at=float(d["kmAt"]),
        detour_km=float(d["detourKm"]),
        detour_min=int(d["detourMin"]),
        dwell_min=int(d["dwellMin"]),
        fixed=bool(d["fixed"]),
        auto=bool(d["auto"]),
        score=float(d["score"]),
        place_id=d["placeId"],
        region_code=d["regionCode"],
        reason_key=d.get("reasonKey", ""),
        reason_params=tuple((str(k), v) for k, v in d.get("reasonParams", [])),
        meal=None if d.get("meal") is None else Meal(d["meal"]),
        litres=float(d.get("litres", 0.0)),
        coffee=bool(d.get("coffee", False)),
        pool=str(d.get("pool", "")),
    )


def engine_state_to_json(e: EngineState) -> Json:
    return {
        "profileKm": list(e.profile_km),
        "profileMin": list(e.profile_min),
        "regionKm": [[code, km] for code, km in e.region_km],
        "tollHits": [
            {"segment": _segment_to_json(h.segment), "kmFrom": h.km_from, "kmTo": h.km_to}
            for h in e.toll_hits
        ],
        "driveTimeFactor": e.drive_time_factor,
        "days": [
            {
                "day": d.day,
                "kmStart": d.km_start,
                "kmEnd": d.km_end,
                "startAt": dt_to_str(_local_naive(d.start_at, d.tz)),
                "tz": d.tz,
                "budgetMin": d.budget_min,
                "stops": [_stop_state_to_json(s) for s in d.stops],
            }
            for d in e.days
        ],
        "candidates": [
            {
                "placeId": c.place_id,
                "kmAt": c.km_at,
                "lateralKm": c.lateral_km,
                "detourKm": c.detour_km,
                "detourMin": c.detour_min,
                "roadClass": c.road_class.value,
                "regionCode": c.region_code,
            }
            for c in e.candidates
        ],
        "rerun": e.rerun,
        "townKms": [[t, km] for t, km in e.town_kms],
    }


def engine_state_from_json(d: Mapping[str, Any]) -> EngineState:
    return EngineState(
        profile_km=tuple(float(x) for x in d["profileKm"]),
        profile_min=tuple(float(x) for x in d["profileMin"]),
        region_km=tuple((str(code), float(km)) for code, km in d["regionKm"]),
        toll_hits=tuple(
            TollHit(_segment_from_json(h["segment"]), float(h["kmFrom"]), float(h["kmTo"]))
            for h in d["tollHits"]
        ),
        drive_time_factor=float(d["driveTimeFactor"]),
        days=tuple(
            DayState(
                day=x["day"],
                km_start=float(x["kmStart"]),
                km_end=float(x["kmEnd"]),
                start_at=_aware_from_local(x["startAt"], x["tz"]),
                tz=x["tz"],
                budget_min=x["budgetMin"],
                stops=tuple(_stop_state_from_json(s) for s in x["stops"]),
            )
            for x in d["days"]
        ),
        candidates=tuple(
            CandidateState(
                place_id=c["placeId"],
                km_at=float(c["kmAt"]),
                lateral_km=float(c["lateralKm"]),
                detour_km=float(c["detourKm"]),
                detour_min=int(c["detourMin"]),
                road_class=RoadClass(c["roadClass"]),
                region_code=c["regionCode"],
            )
            for c in d["candidates"]
        ),
        rerun=int(d.get("rerun", 0)),
        town_kms=tuple((str(t), float(km)) for t, km in d.get("townKms", [])),
    )


# ---------------------------------------------------------------- plan


def plan_to_json(p: TripPlan, public: bool = True, trip_id: str | None = None) -> Json:
    """`TripPlan` → PlanResponse-shaped dict. `public=True` (API default) omits `engineState`.

    `id` is owned by the API; the planner emits `trip_id` (None unless given). API-only fields
    (`saved`, `shareSlug`, `createdAt`, `shareText`) are added by the API.
    """
    out: Json = {
        "id": trip_id,
        "title": p.title_ru,
        "km": p.km,
        "days": p.days,
        "nights": p.nights,
        "roundTrip": p.round_trip,
        "daysList": [_day_to_json(d) for d in p.days_list],
        "cost": cost_to_json(p.cost),
        "reasons": {
            "overnights": [
                {
                    "day": r.day,
                    "townId": r.town_id,
                    "town": r.town,
                    "text": r.text,
                    "candidates": list(r.candidates),
                    "fallback": r.fallback.value,
                }
                for r in p.overnight_reasons
            ]
        },
        "warnings": [
            {"code": w.code.value, "day": w.day, "message": w.message_ru, "detail": w.detail}
            for w in p.warnings
        ],
        "input": normalized_to_json(p.input),
        "engineVersion": p.engine_version,
    }
    if not public:
        out["engineState"] = engine_state_to_json(p.engine_state)
    return out


def plan_from_json(d: Mapping[str, Any]) -> TripPlan:
    """Inverse of `plan_to_json(p, public=False)`; requires `engineState` (persisted server-side)."""
    if "engineState" not in d:
        raise ValueError("engineState missing: load the server-side plan, not the public payload")
    return TripPlan(
        title_ru=d["title"],
        km=d["km"],
        days=d["days"],
        nights=d["nights"],
        round_trip=d["roundTrip"],
        days_list=tuple(_day_from_json(x) for x in d["daysList"]),
        cost=cost_from_json(d["cost"]),
        overnight_reasons=tuple(
            OvernightReason(
                r["day"],
                r["townId"],
                r["town"],
                r["text"],
                tuple(r["candidates"]),
                OvernightFallback(r.get("fallback", "none")),
            )
            for r in cast(Mapping[str, Any], d["reasons"])["overnights"]
        ),
        warnings=tuple(
            PlanWarning(WarningCode(w["code"]), w["day"], w["message"], w.get("detail", ""))
            for w in d["warnings"]
        ),
        input=normalized_from_json(d["input"]),
        engine_version=d["engineVersion"],
        engine_state=engine_state_from_json(d["engineState"]),
    )
