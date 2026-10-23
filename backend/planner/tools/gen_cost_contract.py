"""Writes backend/planner/tests/contract/cost_recompute_cases.json.

Expected numbers come from `expected()` below — an independent, deliberately naive implementation of
A§7.2 written from the architecture text (it does not import verst_planner).
"""

import copy
import json
import math
import os
from decimal import ROUND_HALF_UP
from decimal import Decimal as D
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "tests" / "contract" / "cost_recompute_cases.json"


def r(x, step):
    return int((D(x) / step).quantize(D(1), ROUND_HALF_UP)) * step


def region(code, name, km, price):
    return {"regionCode": code, "regionName": name, "km": km, "priceRub": price}


def night(stop, day, town, sel, price, options, default=False, bf=True, bf_check=360):
    return {
        "stopId": stop,
        "day": day,
        "townName": town,
        "selectedPlaceId": sel,
        "priceNightRub": price,
        "options": [{"placeId": p, "priceNightRub": pr, "breakfastIncluded": b} for p, pr, b in options],
        "defaultPrice": default,
        "breakfastIncluded": bf,
        "breakfastCheckRub": bf_check,
    }


def meal(day, m, stop, check):
    return {"day": day, "meal": m, "stopId": stop, "checkRub": check}


def ticket(stop, place, name, a, c):
    return {"stopId": stop, "placeId": place, "name": name, "adultRub": a, "childRub": c}


def toll(seg, ref, rub, n):
    return {"segmentId": seg, "roadRef": ref, "rub": rub, "night": n, "asOf": "2026-10"}


BASE = {
    "fuel": {
        "consumption": 8.0,
        "fuelType": "ai95",
        "regions": [region("RU-YAR", "Ярославская область", 750.0, "62.00")],
        "asOf": "2026-10",
    },
    "tolls": [],
    "nights": [
        night("d1s05", 1, "Ярославль", "h_yar", 6000, [("h_yar", 6000, True)]),
        night("d2s05", 2, "Суздаль", "h_suz", 6000, [("h_suz", 6000, True), ("h_suz2", 4500, False)]),
    ],
    "meals": [
        meal(1, "lunch", "d1s03", 600),
        meal(1, "dinner", "d1s05", 600),
        meal(2, "lunch", "d2s03", 600),
        meal(2, "dinner", "d2s05", 600),
        meal(3, "lunch", "d3s02", 600),
        meal(3, "dinner", None, 600),
        meal(3, "lunch", None, 600),
    ],
    "tickets": [ticket("d1s02", "pl_k", "Кремль", 1000, 1000)],
    "reserveFrac": "0.10",
    "lineStep": 10,
    "totalStep": 100,
    "childAges": None,
    "assumedChildAge": 8,
    "childFoodWeightUnder7": "0.50",
    "asOf": {"fuel": "2026-10", "lodging": "2026-09"},
    "moodJustDrive": False,
}


def expected(units, crew, reserve_on, budget, overrides):
    hotel_by_stop = overrides.get("hotelByStop", {})
    replaced = overrides.get("replaced", {})
    # fuel
    regions = list(units["fuel"]["regions"])
    kms = {g["regionCode"]: D(str(g["km"])) for g in regions}
    for alt in replaced.values():
        if alt["regionCode"] in kms:
            kms[alt["regionCode"]] += D(str(alt["deltaKm"]))
        elif alt.get("priceRub") is not None and alt["deltaKm"] > 0:
            # A§16.6: a region the trip did not cross joins with the alternative's price
            regions.append(region(alt["regionCode"], alt.get("regionName", ""), 0.0, alt["priceRub"]))
            kms[alt["regionCode"]] = D(str(alt["deltaKm"]))
        else:
            kms[regions[0]["regionCode"]] += D(str(alt["deltaKm"]))
    cons = D(str(units["fuel"]["consumption"]))
    fuel = sum(
        (max(D(0), kms[g["regionCode"]]) * cons / 100 * D(g["priceRub"]) for g in regions),
        D(0),
    )
    if units["fuel"].get("tripKm") is not None:  # A§16.7: the formula shows TripPlan.km
        shown_km = D(units["fuel"]["tripKm"]) + sum((D(str(a["deltaKm"])) for a in replaced.values()), D(0))
    else:
        shown_km = sum((max(D(0), k) for k in kms.values()), D(0))
    tolls = sum((D(t["rub"]) for t in units["tolls"]), D(0))
    rooms = math.ceil(crew["adults"] / 2)
    lodging = D(0)
    breakfasts = []
    cheaper = False
    for n in units["nights"]:
        price, bf, sel = n["priceNightRub"], n["breakfastIncluded"], n["selectedPlaceId"]
        want = hotel_by_stop.get(n["stopId"])
        for o in n["options"]:
            if o["placeId"] == want:
                price, bf, sel = o["priceNightRub"], o["breakfastIncluded"], o["placeId"]
        lodging += rooms * price
        if not bf:
            breakfasts.append(n["breakfastCheckRub"])
        if any(o["priceNightRub"] < price and o["placeId"] != sel for o in n["options"]):
            cheaper = True
    ages = crew.get("childAges")
    if ages is None:
        ua = units["childAges"]
        ages = (
            ua
            if ua is not None and len(ua) == crew["children"]
            else [units["assumedChildAge"]] * crew["children"]
        )
    people = D(crew["adults"]) + sum(
        (D(units["childFoodWeightUnder7"]) if a < 7 else D(1) for a in ages), D(0)
    )
    checks = list(breakfasts)
    for m in units["meals"]:
        c = m["checkRub"]
        if m["stopId"] in replaced and replaced[m["stopId"]]["checkRub"] is not None:
            c = replaced[m["stopId"]]["checkRub"]
        checks.append(c)
    food = people * sum((D(c) for c in checks), D(0))
    tickets = D(0)
    for t in units["tickets"]:
        a, c = t["adultRub"], t["childRub"]
        if t["stopId"] in replaced:
            alt = replaced[t["stopId"]]
            a = alt["adultRub"] or 0
            c = alt["childRub"] if alt["childRub"] is not None else a
        tickets += crew["adults"] * a + crew["children"] * c
    ticketed = {t["stopId"] for t in units["tickets"]}
    for sid, alt in replaced.items():  # a rest stop replaced by a sight (rest pool) adds its ticket
        if sid not in ticketed and alt["adultRub"] is not None:
            a = alt["adultRub"]
            c = alt["childRub"] if alt["childRub"] is not None else a
            tickets += crew["adults"] * a + crew["children"] * c
    lines = {
        "fuel": r(fuel, 10),
        "tolls": r(tolls, 10),
        "lodging": r(lodging, 10),
        "food": r(food, 10),
        "tickets": r(tickets, 10),
    }
    subtotal = sum(lines.values())
    lines["reserve"] = r(D(units["reserveFrac"]) * subtotal, 10)
    total = r(subtotal + (lines["reserve"] if reserve_on else 0), 100)
    per_person = r(D(total) / (crew["adults"] + crew["children"]), 100)
    remaining = None if budget is None else budget - total
    over = remaining is not None and remaining < 0
    hints = []
    if over:
        if cheaper:
            hints.append("cheaper_overnight")
        if lines["tickets"] > 0 or units["tickets"]:
            hints.append("fewer_sights")
        if not units["moodJustDrive"]:
            hints.append("just_drive")
    return {
        "lines": lines,
        "subtotalRub": subtotal,
        "totalRub": total,
        "perPersonRub": per_person,
        "remainingRub": remaining,
        "overBudget": over,
        "hintKeys": hints,
        "fuelFormulaKm": int(shown_km.quantize(D(1), ROUND_HALF_UP)) if regions else None,
    }


cases = []


def case(name, note, units=None, crew=None, reserve_on=True, budget=None, overrides=None):
    u = copy.deepcopy(units or BASE)
    c = crew or {"adults": 2, "children": 1, "dog": True, "childAges": None}
    ov = overrides or {}
    cases.append(
        {
            "name": name,
            "note": note,
            "units": u,
            "crew": c,
            "reserveOn": reserve_on,
            "budget": budget,
            "overrides": ov,
            "expected": expected(u, c, reserve_on, budget, ov),
        }
    )


def mod(**kw):
    u = copy.deepcopy(BASE)
    u.update(kw)
    return u


case("canvas_reserve_on", "Waybill canvas lines 3720/0/12000/12600/3000 → 34 500", budget=40000)
case("canvas_reserve_off", "reserve toggle off", reserve_on=False, budget=40000)
case("canvas_over_budget", "overspend → hints in order", budget=20000)
case("canvas_no_budget", "«не важно»: no remaining")
case("budget_exact", "remaining 0 is not an overspend", budget=34500)
case(
    "three_adults_two_rooms",
    "rooms = ceil(3 / 2) = 2",
    crew={"adults": 3, "children": 0, "dog": False, "childAges": None},
)
case(
    "seven_adults",
    "rooms = 4",
    crew={"adults": 7, "children": 0, "dog": False, "childAges": None},
    budget=150000,
)
case("one_adult", "single driver", crew={"adults": 1, "children": 0, "dog": False, "childAges": None})
case(
    "child_under7",
    "child age 5 eats as 0.5",
    crew={"adults": 2, "children": 1, "dog": False, "childAges": [5]},
)
case(
    "children_mixed_ages",
    "ages 3 and 10 → 0.5 + 1",
    crew={"adults": 2, "children": 2, "dog": False, "childAges": [3, 10]},
)
case(
    "children_unknown_ages",
    "unknown ages count as 8 (full)",
    crew={"adults": 2, "children": 2, "dog": False, "childAges": None},
)
case(
    "units_ages_reused",
    "units carry ages, crew omits them",
    units=mod(childAges=[4]),
    crew={"adults": 2, "children": 1, "dog": False, "childAges": None},
)
case(
    "units_ages_mismatch",
    "crew changed: units ages no longer match → assumed",
    units=mod(childAges=[4]),
    crew={"adults": 2, "children": 2, "dog": False, "childAges": None},
)
case(
    "four_plus_four",
    "8 people, rooms 2",
    crew={"adults": 4, "children": 4, "dog": True, "childAges": [2, 6, 7, 12]},
    budget=60000,
)
case(
    "fuel_two_regions",
    "fuel by region",
    units=mod(
        fuel={
            "consumption": 8.0,
            "fuelType": "ai95",
            "regions": [
                region("RU-MOS", "Московская область", 300.0, "61.80"),
                region("RU-YAR", "Ярославская область", 445.0, "61.90"),
            ],
            "asOf": "2026-10",
        }
    ),
)
case(
    "fuel_three_regions_7_5",
    "consumption 7.5, three regions",
    units=mod(
        fuel={
            "consumption": 7.5,
            "fuelType": "ai92",
            "regions": [
                region("RU-MOW", "Москва", 18.3, "57.90"),
                region("RU-VLA", "Владимирская область", 412.7, "56.90"),
                region("RU-NIZ", "Нижегородская область", 383.0, "56.40"),
            ],
            "asOf": "2026-10",
        }
    ),
)
case(
    "diesel",
    "ДТ at 70.30",
    units=mod(
        fuel={
            "consumption": 9.5,
            "fuelType": "dt",
            "regions": [region("RU-VLA", "Владимирская область", 222.0, "70.30")],
            "asOf": "2026-10",
        }
    ),
)
case(
    "no_fuel_regions",
    "degenerate: no attributed km",
    units=mod(fuel={"consumption": 8.0, "fuelType": "ai95", "regions": [], "asOf": "2026-10"}),
)
case(
    "tolls_day_night",
    "М-12 day + night units",
    units=mod(
        tolls=[
            toll("ts_m12_1", "М-12", 800, False),
            toll("ts_m12_2", "М-12", 700, True),
            toll("ts_m11_1", "М-11", 1200, False),
        ]
    ),
)
case(
    "hotel_override_cheaper",
    "pick the 4 500 option without breakfast",
    overrides={"hotelByStop": {"d2s05": "h_suz2"}},
)
case("hotel_override_unknown", "unknown option id is ignored", overrides={"hotelByStop": {"d2s05": "nope"}})
case(
    "replaced_sight",
    "alternative sight 200/100, +1.5 km",
    overrides={
        "replaced": {
            "d1s02": {
                "deltaKm": 1.5,
                "regionCode": "RU-YAR",
                "checkRub": None,
                "adultRub": 200,
                "childRub": 100,
                "name": "Музей",
                "placeId": "pl_m",
            }
        }
    },
)
case(
    "replaced_sight_free",
    "alternative sight with free entry",
    overrides={
        "replaced": {
            "d1s02": {
                "deltaKm": -0.8,
                "regionCode": "RU-YAR",
                "checkRub": None,
                "adultRub": None,
                "childRub": None,
                "name": "Сквер",
                "placeId": "pl_s",
            }
        }
    },
)
case(
    "replaced_lunch",
    "alternative lunch check 850",
    overrides={
        "replaced": {
            "d1s03": {
                "deltaKm": 2.6,
                "regionCode": "RU-YAR",
                "checkRub": 850,
                "adultRub": None,
                "childRub": None,
                "name": "Кафе",
                "placeId": "pl_c",
            }
        }
    },
)
case(
    "replaced_fuel_other_region",
    "fuel alternative in a region not on the trip → first region",
    overrides={
        "replaced": {
            "d1s04": {
                "deltaKm": -1.2,
                "regionCode": "RU-KOS",
                "checkRub": None,
                "adultRub": None,
                "childRub": None,
                "name": "АЗС",
                "placeId": "pl_f",
            }
        }
    },
)
case("free_tickets", "free sights only", units=mod(tickets=[ticket("d1s02", "pl_l", "Лавра", 0, 0)]))
case(
    "no_nights_one_day",
    "one-day trip",
    units=mod(nights=[], meals=[meal(1, "lunch", "d1s03", 650)], tickets=[]),
    crew={"adults": 2, "children": 0, "dog": False, "childAges": None},
)
case(
    "default_price_night",
    "NO_HOTEL night at the default price, no breakfast",
    units=mod(nights=[night("d1s05", 1, "Серединск", None, 3500, [], default=True, bf=False, bf_check=330)]),
)
case(
    "varied_checks",
    "checks 650 / 700 / 950",
    units=mod(
        meals=[meal(1, "lunch", "d1s03", 650), meal(1, "dinner", "d1s05", 950), meal(2, "lunch", None, 700)]
    ),
)
case(
    "just_drive_over_budget",
    "mood already «Просто доехать»: no just_drive hint",
    units=mod(moodJustDrive=True, tickets=[]),
    budget=10000,
)
case(
    "reserve_half_up",
    "line half-up: tickets 2 × 1005 + 1005 = 3015 → 3020; reserve 3134 → 3130",
    units=mod(tickets=[ticket("d1s02", "pl_k", "Кремль", 1005, 1005)]),
)

def alt(region_code, delta, check=None, adult=None, child=None, price=None, region_name=""):
    return {
        "deltaKm": delta,
        "regionCode": region_code,
        "checkRub": check,
        "adultRub": adult,
        "childRub": child,
        "name": "Замена",
        "placeId": "pl_alt",
        "priceRub": price,
        "regionName": region_name,
    }


case(
    "replaced_new_region_priced",
    "A§16.6: an alternative in a region the trip did not cross adds that region at its price",
    overrides={"replaced": {"d1s04": alt("RU-VLA", 6.5, price="63.10", region_name="Владимирская область")}},
)
case(
    "replaced_rest_by_sight",
    "A§16.6: a rest stop (no ticket unit) replaced by a short sight from the rest pool adds its ticket",
    overrides={"replaced": {"d2s02": alt("RU-YAR", 0.8, adult=250, child=100)}},
)
case(
    "trip_km_formula",
    "A§16.7: the fuel formula shows tripKm (Σ day km) plus the replaced detours",
    units=mod(fuel={**BASE["fuel"], "tripKm": 748}),
    overrides={"replaced": {"d1s04": alt("RU-YAR", 2.6)}},
)

TEXT = (
    json.dumps(
        {
            "version": 1,
            "note": "Shared Python/Kotlin cost recompute contract (ADR-0009). "
            "Expected values from an independent implementation of A§7.2.",
            "cases": cases,
        },
        ensure_ascii=False,
        indent=1,
    )
    + "\n"
)
if not os.environ.get("VERST_GEN_IN_MEMORY"):  # tests compare TEXT with the committed file (A§16.10)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(TEXT, encoding="utf-8")
    print(len(cases), "cases")
