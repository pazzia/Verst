"""Cost model (A§7, SPEC §8): `CostInput` -> `CostUnits` -> `recompute` -> `CostResult`.

The planner pipeline fills `CostInput` from the schedule (pipeline types never reach this package, A§3.1);
every SPEC §8 rule that turns trip facts into priced units lives here: meal counting [D-6], breakfast at the
hotel, toll day/night tariff by entry time, rooms [D-15], child weights [D-14], freshness `as_of`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from verst_planner.config import PlannerConfig
from verst_planner.cost.money import dec, round_to
from verst_planner.cost.recompute import child_ages, recompute, rooms_for
from verst_planner.domain.enums import CostKey, Meal, Mood
from verst_planner.domain.facts import breakfast_confirmed, ticket_known, ticket_prices
from verst_planner.domain.model import (
    CostOverrides,
    CostResult,
    CostUnits,
    Crew,
    FuelRegionUnit,
    FuelUnits,
    HotelPrice,
    MealUnit,
    NightUnit,
    NormalizedInput,
    ParkingUnit,
    Place,
    RegionPrice,
    TicketUnit,
    TollHit,
    TollUnit,
)
from verst_planner.domain.rooms import room_plan
from verst_planner.explain import ru


@dataclass(frozen=True, slots=True)
class RegionKm:
    code: str
    name_ru: str
    km: float
    price: RegionPrice


@dataclass(frozen=True, slots=True)
class TollInput:
    hit: TollHit
    entry_local: datetime  # naive local wall time when the car enters the segment


@dataclass(frozen=True, slots=True)
class NightInput:
    stop_id: str
    day: int
    town_name_ru: str
    hotel: Place | None
    options: tuple[Place, ...]  # passing lodgings (selected first)
    default_night_rub: int  # `lodging_default_night(population)`, used when there is no hotel
    town_check_rub: int  # dinner / breakfast base check of the overnight town (median or default)
    family_rooms: bool = False  # ADR-0011 lever: family rooms where they cost less


@dataclass(frozen=True, slots=True)
class DayInput:
    day: int
    lunch_overlap: bool  # the day's schedule overlaps the lunch window
    lunch_stop_id: str | None
    lunch_place: Place | None
    lunch_default_check: int  # default check of the nearest town at the lunch ETA
    finish_arrival_local: datetime | None  # last day only
    finish_is_origin: bool
    finish_check_rub: int


@dataclass(frozen=True, slots=True)
class SightInput:
    stop_id: str
    place: Place


@dataclass(frozen=True, slots=True)
class CostInput:
    regions: tuple[RegionKm, ...]
    tolls: tuple[TollInput, ...]
    nights: tuple[NightInput, ...]
    days: tuple[DayInput, ...]
    sights: tuple[SightInput, ...]
    defaults_as_of: date
    trip_km: int | None = None  # `TripPlan.km`, shown in the fuel formula (A§16.7)
    parking: tuple[ParkingUnit, ...] = ()  # ADR-0015 §4 (empty without parking data)
    parking_as_of: str | None = None
    tolls_unknown: bool = False  # QA B-1: an approximate route along no known toll corridor


def ym(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _in_window(t: time, lo: time, hi: time) -> bool:
    if lo == hi:
        return False
    if lo < hi:
        return lo <= t < hi
    return t >= lo or t < hi  # window across midnight


def toll_unit(t: TollInput, cfg: PlannerConfig) -> TollUnit:
    seg = t.hit.segment
    lo, hi = (seg.night_from, seg.night_to) if seg.night_from != seg.night_to else cfg.toll_night
    # a segment without a night discount is never «ночью» (and Friday nights still take the weekend tariff)
    night = seg.tariff_night_rub != seg.tariff_day_rub and _in_window(t.entry_local.time(), lo, hi)
    # [ENG-02] Автодор category 1: the weekend tariff is Friday to Sunday (holidays are not modelled)
    weekend = not night and seg.tariff_weekend_rub is not None and t.entry_local.weekday() >= 4
    tariff = seg.tariff_night_rub if night else seg.tariff_weekend_rub if weekend else seg.tariff_day_rub
    assert tariff is not None
    road = ru.text("cost.tolls.approx_road", road=seg.road_ref) if seg.approx else seg.road_ref
    return TollUnit(seg.id, road, round_to(tariff, 1), night, ym(seg.as_of), weekend)


def breakfast_check(base: int, cfg: PlannerConfig) -> int:
    return round_to(dec(base) * cfg.cost.breakfast_price_frac, 10)


def build_units(ci: CostInput, inp: NormalizedInput, cfg: PlannerConfig) -> CostUnits:
    c = cfg.cost
    fuel_as_of = min((r.price.as_of for r in ci.regions), default=ci.defaults_as_of)
    fuel = FuelUnits(
        consumption_l_per_100km=inp.vehicle.consumption_l_per_100km,
        fuel_type=inp.vehicle.fuel_type,
        regions=tuple(
            FuelRegionUnit(r.code, r.name_ru, round(r.km, 3), r.price.price_rub) for r in ci.regions
        ),
        as_of=ym(fuel_as_of),
        trip_km=ci.trip_km,
    )
    tolls = tuple(toll_unit(t, cfg) for t in ci.tolls)
    toll_as_of = min((t.hit.segment.as_of for t in ci.tolls), default=ci.defaults_as_of)

    nights: list[NightUnit] = []
    lodging_dates: list[date] = []
    for n in ci.nights:
        plans = {o.id: room_plan(o, inp.crew, n.family_rooms) for o in n.options}
        options = tuple(
            HotelPrice(
                o.id, plans[o.id][1], breakfast_confirmed(o), plans[o.id][0] if plans[o.id][2] else None
            )
            for o in n.options
        )
        rooms: int | None = None
        if n.hotel is not None:
            r, price, explicit = room_plan(n.hotel, inp.crew, n.family_rooms)
            rooms = r if explicit else None
            default, bf = False, breakfast_confirmed(n.hotel)  # E-3: unknown = breakfast costed
            if n.hotel.verified_at:
                lodging_dates.append(n.hotel.verified_at)
            else:
                lodging_dates.append(ci.defaults_as_of)
        else:
            price, default, bf = n.default_night_rub, True, False
            lodging_dates.append(ci.defaults_as_of)
        nights.append(
            NightUnit(
                n.stop_id,
                n.day,
                n.town_name_ru,
                n.hotel.id if n.hotel else None,
                price,
                options,
                default,
                bf,
                breakfast_check(n.town_check_rub, cfg),
                rooms,
            )
        )

    meals: list[MealUnit] = []
    food_dates: list[date] = []
    night_by_day = {n.day: n for n in ci.nights}
    for d in ci.days:
        if d.lunch_overlap:
            if d.lunch_place is not None and d.lunch_place.avg_check_rub is not None:
                meals.append(MealUnit(d.day, Meal.LUNCH, d.lunch_stop_id, d.lunch_place.avg_check_rub))
                food_dates.append(d.lunch_place.verified_at or ci.defaults_as_of)
            else:
                meals.append(MealUnit(d.day, Meal.LUNCH, d.lunch_stop_id, d.lunch_default_check))
                food_dates.append(ci.defaults_as_of)
        night = night_by_day.get(d.day)
        if night is not None:  # [D-5] dinner at the overnight town
            meals.append(MealUnit(d.day, Meal.DINNER, night.stop_id, night.town_check_rub))
            food_dates.append(ci.defaults_as_of)
        elif (
            d.finish_arrival_local is not None
            and not d.finish_is_origin
            and d.finish_arrival_local.time() > c.dinner_last_day_after
        ):
            meals.append(MealUnit(d.day, Meal.DINNER, None, d.finish_check_rub))
            food_dates.append(ci.defaults_as_of)

    tickets: list[TicketUnit] = []
    ticket_dates: list[date] = []
    for s in ci.sights:
        adult, child = ticket_prices(s.place)
        known = ticket_known(s.place)
        tickets.append(TicketUnit(s.stop_id, s.place.id, s.place.name_ru, adult, child, known))
        if adult > 0:
            ticket_dates.append(s.place.verified_at or ci.defaults_as_of)

    lodging_as_of = ym(min(lodging_dates, default=ci.defaults_as_of))
    as_of = (
        (CostKey.FUEL.value, fuel.as_of),
        (CostKey.TOLLS.value, ym(toll_as_of)),
        (CostKey.LODGING.value, lodging_as_of),
        (CostKey.FOOD.value, ym(min(food_dates, default=ci.defaults_as_of))),
        (CostKey.TICKETS.value, ym(min(ticket_dates, default=ci.defaults_as_of))),
        (CostKey.RESERVE.value, min(fuel.as_of, lodging_as_of)),
    ) + (((CostKey.PARKING.value, ci.parking_as_of),) if ci.parking and ci.parking_as_of else ())
    return CostUnits(
        fuel=fuel,
        tolls=tolls,
        nights=tuple(nights),
        meals=tuple(meals),
        tickets=tuple(tickets),
        reserve_frac=c.reserve_frac,
        line_step=c.line_step,
        total_step=c.total_step,
        child_ages=inp.crew.child_ages,
        assumed_child_age=c.assumed_child_age,
        child_food_weight_under7=c.child_food_weight_under7,
        as_of=as_of,
        mood_just_drive=inp.mood is Mood.JUST_DRIVE,
        parking=ci.parking,
        tolls_unknown=ci.tolls_unknown,
    )


def compute_cost(ci: CostInput, inp: NormalizedInput, cfg: PlannerConfig) -> CostResult:
    """Stage 12 (A§7): units from the trip facts, then the reference `recompute`."""
    units = build_units(ci, inp, cfg)
    return recompute(units, inp.crew, inp.reserve_on, inp.budget_rub, CostOverrides())


# ------------------------------------------------------------------------------- per-stop cost (A§7.1)


def people_weight(crew: Crew, cfg: PlannerConfig) -> float:
    w = float(cfg.cost.child_food_weight_under7)
    ages = crew.child_ages if crew.child_ages is not None else (cfg.cost.assumed_child_age,) * crew.children
    return crew.adults + sum(w if a < 7 else 1.0 for a in ages)


def sight_cost(p: Place, crew: Crew) -> int:
    adult, child = ticket_prices(p)
    return round_to(dec(crew.adults * adult + crew.children * child), 10)


def food_cost(check: int, crew: Crew, cfg: PlannerConfig) -> int:
    return round_to(dec(people_weight(crew, cfg)) * check, 10)


def overnight_cost(price_night: int, crew: Crew, rooms: int | None = None) -> int:
    return round_to(dec((rooms_for(crew) if rooms is None else rooms) * price_night), 10)


def fuel_stop_cost(litres: float, price: RegionPrice) -> int:
    """Informational only: the fuel line is distance-based (A§7.1)."""
    return round_to(dec(round(litres, 3)) * price.price_rub, 10)


__all__ = [
    "CostInput",
    "DayInput",
    "NightInput",
    "RegionKm",
    "SightInput",
    "TollInput",
    "build_units",
    "child_ages",
    "compute_cost",
    "food_cost",
    "fuel_stop_cost",
    "overnight_cost",
    "people_weight",
    "sight_cost",
    "ticket_prices",
    "ym",
]
