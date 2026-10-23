"""Reference cost algorithm over `CostUnits` (A§7.2-7.4, ADR-0009).

`recompute` is the single algorithm both the server (`compute_cost`) and the Android `CostCalculator`
implement; `tests/contract/cost_recompute_cases.json` pins it.
"""

from __future__ import annotations

import math
from decimal import Decimal

from verst_planner.cost import formulas as fm
from verst_planner.cost.money import ZERO, dec, round_to
from verst_planner.domain.enums import CostKey, Meal
from verst_planner.domain.model import (
    AltUnits,
    CostBreakdownRow,
    CostLine,
    CostOverrides,
    CostResult,
    CostUnits,
    Crew,
    FuelRegionUnit,
    NightUnit,
    TicketUnit,
)

HINT_ORDER = ("cheaper_overnight", "fewer_sights", "just_drive")
CHILD_AGE_LIMIT = 7


def rooms_for(crew: Crew) -> int:
    """[D-15] `ceil(adults / 2)`; children share."""
    return math.ceil(crew.adults / 2)


def child_ages(units: CostUnits, crew: Crew) -> tuple[int, ...]:
    """Crew ages win, else the units' ages when they still match; unknown ages = `assumed_child_age`."""
    if crew.child_ages is not None:
        return crew.child_ages
    if units.child_ages is not None and len(units.child_ages) == crew.children:
        return units.child_ages
    return (units.assumed_child_age,) * crew.children


def food_people(units: CostUnits, crew: Crew) -> Decimal:
    """`adults + sum child_weight` (0.5 under 7, else 1) [D-14]."""
    w = units.child_food_weight_under7
    return dec(crew.adults) + sum(
        (w if a < CHILD_AGE_LIMIT else Decimal(1) for a in child_ages(units, crew)), ZERO
    )


def _as_of(units: CostUnits, key: CostKey, fallback: str) -> str:
    return dict(units.as_of).get(key.value, fallback)


def _selected(n: NightUnit, overrides: CostOverrides) -> tuple[int, bool, str | None]:
    """(price per room, breakfast included, selected id) after a hotel override."""
    pid = overrides.hotel_by_stop.get(n.stop_id)
    if pid is not None:
        for o in n.options:
            if o.place_id == pid:
                return o.price_night_rub, o.breakfast_included, o.place_id
    return n.price_night_rub, n.breakfast_included, n.selected_place_id


def effective_tickets(units: CostUnits, ov: CostOverrides) -> list[TicketUnit]:
    """The ticket units after the replaces (A§16.11.4 rule 4), in stop order of the units."""
    out: list[TicketUnit] = []
    for t in units.tickets:
        alt = ov.replaced.get(t.stop_id)
        if alt is None:
            out.append(t)
        elif alt.adult_rub is not None:
            out.append(_alt_ticket(t.stop_id, alt))
    ticketed = {t.stop_id for t in units.tickets}
    out += [
        _alt_ticket(sid, a)
        for sid, a in ov.replaced.items()
        if sid not in ticketed and a.adult_rub is not None
    ]
    return out


def _alt_ticket(stop_id: str, alt: AltUnits) -> TicketUnit:
    adult = alt.adult_rub or 0
    child = alt.child_rub if alt.child_rub is not None else adult
    return TicketUnit(stop_id, alt.place_id, alt.name_ru, adult, child)


def recompute(
    units: CostUnits,
    crew: Crew,
    reserve_on: bool,
    budget_rub: int | None,
    overrides: CostOverrides | None = None,
) -> CostResult:
    ov = overrides or CostOverrides()
    step = units.line_step
    fuel_t = units.fuel.fuel_type
    lines: list[CostLine] = []

    # ---- fuel: sum km_r x consumption / 100 x price_r. A§16.11.4 rule 1: the alternative's region gets
    # + delta_km; a region the trip did not cross is appended at the alternative's price when delta_km > 0;
    # a region whose km drops to <= 0 is kept with 0 km.
    regions = list(units.fuel.regions)
    km_by_region = {r.region_code: dec(r.km) for r in regions}
    for alt in ov.replaced.values():
        if alt.region_code in km_by_region:
            km_by_region[alt.region_code] += dec(alt.delta_km)
        elif alt.price_rub is not None and alt.delta_km > 0:
            regions.append(FuelRegionUnit(alt.region_code, alt.region_name_ru, 0.0, alt.price_rub))
            km_by_region[alt.region_code] = dec(alt.delta_km)
    cons = dec(units.fuel.consumption_l_per_100km)
    fuel_exact = ZERO
    litres = ZERO
    fuel_rows: list[CostBreakdownRow] = []
    for r in regions:
        km = max(ZERO, km_by_region[r.region_code])
        cost = km * cons / 100 * r.price_rub
        fuel_exact += cost
        litres += km * cons / 100
        fuel_rows.append(
            fm.fuel_row(
                r.region_name_ru, km, units.fuel.consumption_l_per_100km, r.price_rub, round_to(cost, step)
            )
        )
    total_km = sum((max(ZERO, k) for k in km_by_region.values()), ZERO)
    shown_km = total_km  # rule 2: the formula shows TripPlan.km (A§16.7) when the units carry it
    if units.fuel.trip_km is not None:
        shown_km = dec(units.fuel.trip_km + sum(a.trip_km_delta for a in ov.replaced.values()))
    avg = fuel_exact / litres if litres > 0 else ZERO
    single = regions[0].price_rub if regions else ZERO
    fuel_rub = round_to(fuel_exact, step)
    lines.append(
        CostLine(
            CostKey.FUEL,
            fm.title(CostKey.FUEL, fuel_t, units.reserve_frac),
            fuel_rub,
            fm.fuel_formula(shown_km, units.fuel.consumption_l_per_100km, avg, len(regions), single),
            units.fuel.as_of,
            tuple(fuel_rows),
        )
    )

    # ---- tolls
    per_road: dict[str, int] = {}
    toll_rows = []
    toll_exact = ZERO
    for toll in units.tolls:
        toll_exact += dec(toll.rub)
        per_road[toll.road_ref] = per_road.get(toll.road_ref, 0) + toll.rub
        toll_rows.append(fm.toll_row(toll.road_ref, toll.night, toll.rub))
    lines.append(
        CostLine(
            CostKey.TOLLS,
            fm.title(CostKey.TOLLS, fuel_t, units.reserve_frac),
            round_to(toll_exact, step),
            fm.tolls_formula(list(per_road.items())),
            _as_of(units, CostKey.TOLLS, units.fuel.as_of),
            tuple(toll_rows),
        )
    )

    # ---- lodging: sum nights rooms x price
    rooms = rooms_for(crew)
    lodging_exact = ZERO
    night_info = []
    lodging_rows = []
    breakfasts: dict[int, int] = {}  # day -> breakfast check (the morning after night d is day d + 1)
    cheaper = False
    for n in units.nights:
        price, breakfast, sel = _selected(n, ov)
        cost = dec(rooms) * price
        lodging_exact += cost
        night_info.append((n.town_name_ru, rooms, price, n.default_price))
        lodging_rows.append(
            fm.lodging_row(n.day, n.town_name_ru, rooms, price, n.default_price, round_to(cost, step))
        )
        if not breakfast:
            breakfasts[n.day + 1] = n.breakfast_check_rub
        if any(o.price_night_rub < price for o in n.options if o.place_id != sel):
            cheaper = True
    lines.append(
        CostLine(
            CostKey.LODGING,
            fm.title(CostKey.LODGING, fuel_t, units.reserve_frac),
            round_to(lodging_exact, step),
            fm.lodging_formula(night_info),
            _as_of(units, CostKey.LODGING, units.fuel.as_of),
            tuple(lodging_rows),
        )
    )

    # ---- food: people x sum checks (lunch, dinner, breakfast where the hotel has none)
    people = food_people(units, crew)
    per_day: dict[int, list[tuple[Meal, int]]] = {}
    for d, check in breakfasts.items():
        per_day.setdefault(d, []).append((Meal.BREAKFAST, check))
    for m in units.meals:
        check = m.check_rub
        if m.stop_id is not None and m.stop_id in ov.replaced:
            alt_check = ov.replaced[m.stop_id].check_rub
            if alt_check is not None:
                check = alt_check
        per_day.setdefault(m.day, []).append((m.meal, check))
    order = {Meal.BREAKFAST: 0, Meal.LUNCH: 1, Meal.DINNER: 2}
    checks: list[int] = []
    food_rows = []
    food_exact = ZERO
    for d in sorted(per_day):
        meals = sorted(per_day[d], key=lambda mc: order[mc[0]])
        day_exact = people * sum((dec(c) for _m, c in meals), ZERO)
        food_exact += day_exact
        checks.extend(c for _m, c in meals)
        food_rows.append(fm.food_row(d, meals, round_to(day_exact, step)))
    lines.append(
        CostLine(
            CostKey.FOOD,
            fm.title(CostKey.FOOD, fuel_t, units.reserve_frac),
            round_to(food_exact, step),
            fm.food_formula(people, checks),
            _as_of(units, CostKey.FOOD, units.fuel.as_of),
            tuple(food_rows),
        )
    )

    # ---- tickets: sum adults x adult + children x (child ?? adult). Rule 4: a replaced stop's ticket is
    # removed; an alternative that is a sight (adult_rub not null) brings its own ticket.
    tickets = effective_tickets(units, ov)
    ticket_exact = ZERO
    paid = 0
    ticket_rows = []
    for t in tickets:
        cost = dec(crew.adults * t.adult_rub + crew.children * t.child_rub)
        if cost > 0:
            paid += 1
            ticket_rows.append(
                fm.ticket_row(
                    t.name_ru, crew.adults, t.adult_rub, crew.children, t.child_rub, round_to(cost, step)
                )
            )
        ticket_exact += cost
    tickets_rub = round_to(ticket_exact, step)
    lines.append(
        CostLine(
            CostKey.TICKETS,
            fm.title(CostKey.TICKETS, fuel_t, units.reserve_frac),
            tickets_rub,
            fm.tickets_formula(paid, crew.adults, crew.children),
            _as_of(units, CostKey.TICKETS, units.fuel.as_of),
            tuple(ticket_rows),
        )
    )

    # ---- totals (A§7.2)
    subtotal = sum(line.rub for line in lines)
    reserve = round_to(units.reserve_frac * subtotal, step)
    lodging_as_of = _as_of(units, CostKey.LODGING, units.fuel.as_of)
    prices_as_of = min(units.fuel.as_of, lodging_as_of)
    lines.append(
        CostLine(
            CostKey.RESERVE,
            fm.title(CostKey.RESERVE, fuel_t, units.reserve_frac),
            reserve,
            fm.reserve_formula(),
            _as_of(units, CostKey.RESERVE, prices_as_of),
            (),
            reserve_on,
        )
    )
    total = round_to(dec(subtotal + (reserve if reserve_on else 0)), units.total_step)
    per_person = round_to(dec(total) / (crew.adults + crew.children), units.total_step)
    remaining = None if budget_rub is None else budget_rub - total
    over = remaining is not None and remaining < 0
    hints: list[str] = []
    if over:
        if cheaper:
            hints.append("cheaper_overnight")
        if tickets_rub > 0 or tickets:
            hints.append("fewer_sights")
        if not units.mood_just_drive:
            hints.append("just_drive")
    return CostResult(
        lines=tuple(lines),
        reserve_on=reserve_on,
        subtotal_rub=subtotal,
        total_rub=total,
        per_person_rub=per_person,
        budget_rub=budget_rub,
        remaining_rub=remaining,
        over_budget=over,
        hint_keys=tuple(hints),
        prices_as_of=prices_as_of,
        units=units,
    )
