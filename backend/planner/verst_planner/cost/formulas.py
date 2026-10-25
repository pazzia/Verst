"""Russian formula and breakdown strings for every cost line (A§7.1 table, copy review R-1/R-4)."""

from __future__ import annotations

from decimal import Decimal

from verst_planner.cost.money import quantize, round_to
from verst_planner.domain.enums import CostKey, FuelType, Meal
from verst_planner.domain.model import CostBreakdownRow, ParkingUnit
from verst_planner.explain import ru


def title(key: CostKey, fuel_type: FuelType, reserve_frac: Decimal) -> str:
    if key is CostKey.FUEL:
        if fuel_type is FuelType.DT:
            return ru.text("cost.title.fuel.dt")
        return ru.text("cost.title.fuel", fuel_type=ru.fuel_type_label(fuel_type.value))
    if key is CostKey.RESERVE:
        return ru.text("cost.title.reserve", pct=_pct(reserve_frac))
    return ru.text(f"cost.title.{key.value}")


def _pct(frac: Decimal) -> str:
    return ru.fmt_consumption(frac * 100)


def people_str(people: Decimal) -> str:
    return ru.fmt_consumption(people)


# ------------------------------------------------------------------ fuel


def fuel_formula(
    total_km: Decimal, cons: float, avg_price: Decimal, n_regions: int, single_price: Decimal
) -> str:
    if n_regions == 0:
        return ru.text("cost.fuel.none")
    km = ru.fmt_km(float(total_km))
    c = ru.fmt_consumption(cons)
    if n_regions == 1:
        return ru.text("cost.fuel.one", km=km, cons=c, price=ru.fmt_price(single_price))
    shown = quantize(avg_price, 1)  # the shown average is rounded to 0.10 ₽
    return ru.text(
        "cost.fuel.many",
        km=km,
        cons=c,
        price=ru.fmt_price(shown),
        n=n_regions,
        regions_word=ru.plural_word(n_regions, "plural.region_prep"),
    )


def fuel_row(name: str, km: Decimal, cons: float, price: Decimal, rub: int) -> CostBreakdownRow:
    formula = ru.text(
        "cost.fuel.row",
        km=ru.fmt_km(float(km)),
        cons=ru.fmt_consumption(cons),
        price=ru.fmt_price(price),
        rub=ru.fmt_rub(rub),
    )
    return CostBreakdownRow(name, formula, rub)


# ------------------------------------------------------------------ tolls


def tolls_formula(per_road: list[tuple[str, int]]) -> str:
    if not per_road:
        return ru.text("cost.tolls.none")
    return ru.text("cost.tolls.join").join(
        ru.text("cost.tolls.item", road=road, rub=ru.fmt_rub(rub)) for road, rub in per_road
    )


def toll_row(road: str, night: bool, rub: int) -> CostBreakdownRow:
    when = ru.text("cost.tolls.night" if night else "cost.tolls.day")
    return CostBreakdownRow(road, ru.text("cost.tolls.row", road=road, when=when), rub)


# ------------------------------------------------------------------ lodging


def lodging_formula(nights: list[tuple[str, int, int, bool]]) -> str:
    """`nights` = (town, rooms, price per room, default price)."""
    if not nights:
        return ru.text("cost.lodging.none")
    suffix = ru.text("cost.lodging.default_suffix")
    prices = {p for _t, _r, p, _d in nights}
    if len(prices) == 1 and all(r == 1 for _t, r, _p, _d in nights):
        towns = ru.text("cost.lodging.join").join(t for t, _r, _p, _d in nights)
        out = ru.text("cost.lodging.equal", towns=towns, nights=len(nights), price=ru.fmt_int(nights[0][2]))
        return out + (suffix if any(d for *_x, d in nights) else "")
    items = []
    for town, rooms, price, default in nights:
        if rooms == 1:
            item = ru.text("cost.lodging.item", town=town, price=ru.fmt_int(price))
        else:
            # rooms = ceil(adults / 2) <= 4: «2 номера»; the «номеров» form is kept for larger groups
            key = "cost.lodging.item_rooms" if rooms < 5 else "cost.lodging.item_rooms_many"
            item = ru.text(key, town=town, rooms=rooms, price=ru.fmt_int(price))
        items.append(item + (suffix if default else ""))
    return ru.text("cost.lodging.join").join(items)


def lodging_row(day: int, town: str, rooms: int, price: int, default: bool, rub: int) -> CostBreakdownRow:
    suffix = ru.text("cost.lodging.default_suffix") if default else ""
    return CostBreakdownRow(
        ru.text("cost.lodging.row", day=day, town=town),
        ru.text("cost.lodging.row_formula", rooms=rooms, price=ru.fmt_int(price)) + suffix,
        rub,
    )


# ------------------------------------------------------------------ food


def food_formula(people: Decimal, checks: list[int]) -> str:
    if not checks:
        return ru.text("cost.food.none")
    n = len(checks)
    meals_word = ru.plural_word(n, "plural.meal")
    if len(set(checks)) == 1:
        return ru.text(
            "cost.food.uniform",
            people=people_str(people),
            meals=n,
            meals_word=meals_word,
            check=ru.fmt_int(checks[0]),
        )
    avg10 = round_to(Decimal(sum(checks)) / n, 10)
    return ru.text(
        "cost.food.avg", people=people_str(people), meals=n, meals_word=meals_word, check=ru.fmt_int(avg10)
    )


def food_row(day: int, meals: list[tuple[Meal, int]], rub: int) -> CostBreakdownRow:
    items = ru.text("cost.food.meal_join").join(
        ru.text("cost.food.meal_item", meal=ru.text(f"cost.food.meal.{m.value}"), check=ru.fmt_int(c))
        for m, c in meals
    )
    return CostBreakdownRow(ru.text("cost.food.row", day=day), items, rub)


# ------------------------------------------------------------------ tickets


def tickets_formula(paid: int, adults: int, children: int) -> str:
    if paid == 0:
        return ru.text("cost.tickets.none")
    seats = ru.plural_word(paid, "plural.seat")
    if children == 0:
        return ru.text("cost.tickets.formula_adults", n=paid, seats_word=seats, adults=adults)
    return ru.text("cost.tickets.formula", n=paid, seats_word=seats, adults=adults, children=children)


def ticket_row(name: str, adults: int, adult: int, children: int, child: int, rub: int) -> CostBreakdownRow:
    if children == 0:
        formula = ru.text("cost.tickets.row", adults=adults, adult=ru.fmt_int(adult))
    else:
        formula = ru.text(
            "cost.tickets.row_children",
            adults=adults,
            adult=ru.fmt_int(adult),
            children=children,
            child=ru.fmt_int(child),
        )
    return CostBreakdownRow(name, formula, rub)


def reserve_formula() -> str:
    return ru.text("cost.reserve")


def parking_formula(known: list[ParkingUnit], unknown: int) -> str:
    paid = [x for x in known if (x.rub or 0) > 0]
    if not paid and not unknown:
        return ru.text("cost.parking.free")
    hours = sum(x.hours for x in paid)
    out = (
        ru.text(
            "cost.parking.formula",
            n=len(paid),
            stops_word=ru.plural_word(len(paid), "plural.parking"),
            hours=hours,
        )
        if paid
        else ru.text("cost.parking.no_paid")
    )
    if unknown:
        out += " " + ru.text("cost.parking.unknown", n=unknown)
    return out


def parking_row(x: ParkingUnit) -> CostBreakdownRow:
    if x.rub is None:
        return CostBreakdownRow(x.name_ru, ru.text("cost.parking.row_unknown"), 0)
    if x.rub == 0:
        return CostBreakdownRow(x.name_ru, ru.text("cost.parking.row_free"), 0)
    assert x.rub_per_hour is not None
    return CostBreakdownRow(
        x.name_ru, ru.text("cost.parking.row", hours=x.hours, rate=ru.fmt_int(x.rub_per_hour)), x.rub
    )
