import re
import unittest
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from tests.helpers import make_ctx, make_place, sample_normalized
from verst_planner.config import PlannerConfig
from verst_planner.cost.model import (
    CostInput,
    DayInput,
    NightInput,
    RegionKm,
    SightInput,
    TollInput,
    build_units,
    compute_cost,
    food_cost,
    overnight_cost,
    sight_cost,
    ticket_prices,
)
from verst_planner.cost.money import round_to
from verst_planner.cost.recompute import recompute
from verst_planner.domain.enums import CostKey, FuelType, Meal, Mood, PlaceType, Tag
from verst_planner.domain.model import (
    AltUnits,
    CostOverrides,
    CostResult,
    CostUnits,
    Crew,
    FuelRegionUnit,
    FuelUnits,
    HotelPrice,
    MealUnit,
    NightUnit,
    RegionPrice,
    TicketUnit,
    TollHit,
    TollSegment,
    TollUnit,
)
from verst_planner.explain.ru import NBSP, THIN

CFG = PlannerConfig.default()


def units(**kw: Any) -> CostUnits:
    base: dict[str, Any] = {
        "fuel": FuelUnits(
            8.0,
            FuelType.AI95,
            (FuelRegionUnit("RU-YAR", "Ярославская область", 750.0, Decimal("62.00")),),
            "2026-10",
        ),
        "tolls": (),
        "nights": (
            NightUnit("d1s05", 1, "Ярославль", "h_yar", 6000, (HotelPrice("h_yar", 6000),), False, True, 360),
            NightUnit("d2s05", 2, "Суздаль", "h_suz", 6000, (HotelPrice("h_suz", 6000),), False, True, 360),
        ),
        "meals": tuple(
            MealUnit(1 + i // 3, Meal.LUNCH if i % 2 else Meal.DINNER, None, 600) for i in range(7)
        ),
        "tickets": (TicketUnit("d1s02", "pl_x", "Кремль", 1000, 1000),),
        "reserve_frac": Decimal("0.10"),
        "line_step": 10,
        "total_step": 100,
        "child_ages": None,
        "assumed_child_age": 8,
        "child_food_weight_under7": Decimal("0.5"),
        "as_of": (("fuel", "2026-10"), ("lodging", "2026-09")),
    }
    base.update(kw)
    return CostUnits(**base)


def line(res: CostResult, key: CostKey) -> int:
    return next(x.rub for x in res.lines if x.key is key)


CANVAS_CREW = Crew(2, 1, True)  # child age unknown → counts as 8 → full food weight


class CostTest(unittest.TestCase):
    def test_waybill_canvas_rounding(self) -> None:
        res = recompute(units(), CANVAS_CREW, True, 40_000)
        self.assertEqual([x.rub for x in res.lines], [3720, 0, 12000, 12600, 3000, 3130])
        self.assertEqual([x.key for x in res.lines], list(CostKey))
        self.assertEqual(res.subtotal_rub, 31320)
        self.assertEqual(res.total_rub, 34500)
        self.assertEqual(res.remaining_rub, 5500)
        self.assertFalse(res.over_budget)
        off = recompute(units(), CANVAS_CREW, False, 40_000)
        self.assertEqual(off.total_rub, 31300)
        self.assertEqual(line(off, CostKey.RESERVE), 3130)  # the line stays, disabled
        self.assertFalse(off.lines[-1].enabled)
        self.assertEqual(off.remaining_rub, 8700)

    def test_per_person_rounding(self) -> None:
        self.assertEqual(recompute(units(), CANVAS_CREW, True, None).per_person_rub, 11500)  # 34 500 / 3
        self.assertIsNone(recompute(units(), CANVAS_CREW, True, None).remaining_rub)

    def test_half_up_rounding(self) -> None:
        self.assertEqual(round_to(Decimal("1245.00"), 10), 1250)
        self.assertEqual(round_to(Decimal("1244.99"), 10), 1240)
        self.assertEqual(round_to(Decimal("34450"), 100), 34500)
        self.assertEqual(round_to(Decimal("34449.99"), 100), 34400)

    def test_fuel_by_region(self) -> None:
        u = units(
            fuel=FuelUnits(
                8.0,
                FuelType.AI95,
                (
                    FuelRegionUnit("RU-MOS", "Московская область", 300.0, Decimal("61.80")),
                    FuelRegionUnit("RU-YAR", "Ярославская область", 445.0, Decimal("61.90")),
                ),
                "2026-10",
            )
        )
        res = recompute(u, CANVAS_CREW, True, None)
        fuel = res.lines[0]
        self.assertEqual(len(fuel.breakdown), 2)
        # 300 × 0.08 × 61.80 = 1483.20 ; 445 × 0.08 × 61.90 = 2203.64 ; Σ 3686.84 → 3690
        self.assertEqual(fuel.rub, 3690)
        self.assertEqual(fuel.formula_ru, "745 км × 8 л/100 × ≈ 61,90 ₽ (средняя по 2 регионам)")
        self.assertEqual(fuel.breakdown[0].label_ru, "Московская область")
        self.assertEqual(fuel.breakdown[0].formula_ru, f"300 км × 8 л/100 × 61,80 ₽ = 1{THIN}480{NBSP}₽")
        self.assertEqual(fuel.title_ru, "Бензин АИ-95")
        one = recompute(units(), CANVAS_CREW, True, None).lines[0]
        self.assertEqual(one.formula_ru, "750 км × 8 л/100 × 62,00 ₽")

    def test_toll_night_tariff(self) -> None:
        seg = TollSegment(
            "ts_1",
            "М-12",
            "М-12 Москва — Владимир",
            Decimal("800"),
            Decimal("560"),
            1,
            time(0, 0),
            time(6, 0),
            date(2026, 10, 1),
        )
        ctx, _ = make_ctx()
        hit = TollHit(seg, 18.0, 200.0)
        ci = CostInput(
            (),
            (TollInput(hit, datetime(2026, 10, 24, 2, 30)), TollInput(hit, datetime(2026, 10, 24, 6, 0))),
            (),
            (),
            (),
            date(2026, 10, 1),
        )
        u = build_units(ci, sample_normalized(), ctx.cfg)
        self.assertEqual([(t.rub, t.night) for t in u.tolls], [(560, True), (800, False)])
        res = recompute(u, Crew(2, 0, False), True, None)
        tolls = res.lines[1]
        self.assertEqual(tolls.rub, 1360)
        self.assertEqual(tolls.formula_ru, f"М-12: 1{THIN}360{NBSP}₽")
        self.assertEqual([b.formula_ru for b in tolls.breakdown], ["М-12, ночью", "М-12, днём"])
        self.assertEqual(recompute(units(), CANVAS_CREW, True, None).lines[1].formula_ru, "платных дорог нет")

    def test_rooms_ceil(self) -> None:
        res = recompute(units(), Crew(3, 0, False), True, None)
        self.assertEqual(line(res, CostKey.LODGING), 2 * 2 * 6000)
        self.assertEqual(
            res.lines[2].formula_ru, f"Ярославль 2 номера × 6{THIN}000 + Суздаль 2 номера × 6{THIN}000"
        )
        self.assertEqual(overnight_cost(6000, Crew(3, 0, False)), 12000)
        self.assertEqual(
            recompute(units(), CANVAS_CREW, True, None).lines[2].formula_ru,
            f"Ярославль + Суздаль, 2 × 6{THIN}000",
        )

    def test_child_under7_half_food(self) -> None:
        res = recompute(units(), Crew(2, 1, False, (5,)), True, None)
        self.assertEqual(line(res, CostKey.FOOD), round_to(Decimal("2.5") * 4200, 10))
        self.assertTrue(res.lines[3].formula_ru.startswith("2,5 чел. × 7 приёмов × 600"))
        self.assertEqual(food_cost(700, Crew(2, 1, False, (5,)), CFG), 1750)

    def test_unknown_child_age_counts_full(self) -> None:
        res = recompute(units(), Crew(2, 1, False), True, None)
        self.assertEqual(line(res, CostKey.FOOD), 3 * 4200)
        self.assertEqual(food_cost(700, Crew(2, 1, False), CFG), 2100)

    def test_child_ticket_fallback_to_adult(self) -> None:
        p = make_place("s", PlaceType.SIGHT, ticket_adult_rub=400, ticket_child_rub=None)
        self.assertEqual(ticket_prices(p), (400, 400))
        self.assertEqual(sight_cost(p, Crew(2, 1, False)), 1200)
        p2 = make_place("s2", PlaceType.SIGHT, ticket_adult_rub=400, ticket_child_rub=200)
        self.assertEqual(sight_cost(p2, Crew(2, 1, False)), 1000)

    def test_free_entry_zero(self) -> None:
        free = make_place("s", PlaceType.SIGHT, tags={Tag.FREE_ENTRY}, ticket_adult_rub=300)
        self.assertEqual(ticket_prices(free), (0, 0))
        self.assertEqual(ticket_prices(make_place("n", PlaceType.SIGHT)), (0, 0))
        res = recompute(units(tickets=(TicketUnit("d1s02", "s", "Лавра", 0, 0),)), CANVAS_CREW, True, None)
        self.assertEqual(line(res, CostKey.TICKETS), 0)
        self.assertEqual(res.lines[4].formula_ru, "вход свободный")

    def test_over_budget_hints_order(self) -> None:
        cheap_option = units(
            nights=(
                NightUnit(
                    "d1s05",
                    1,
                    "Ярославль",
                    "h_yar",
                    6000,
                    (HotelPrice("h_yar", 6000), HotelPrice("h_2", 4000)),
                    False,
                    True,
                    360,
                ),
            )
        )
        res = recompute(cheap_option, CANVAS_CREW, True, 10_000)
        self.assertTrue(res.over_budget)
        self.assertEqual(res.hint_keys, ("cheaper_overnight", "fewer_sights", "just_drive"))
        jd = recompute(units(mood_just_drive=True, tickets=()), CANVAS_CREW, True, 10_000)
        self.assertEqual(jd.hint_keys, ())
        self.assertEqual(recompute(units(), CANVAS_CREW, True, 100_000).hint_keys, ())

    def test_overrides(self) -> None:
        u = units(
            nights=(
                NightUnit(
                    "d1s05",
                    1,
                    "Ярославль",
                    "h_yar",
                    6000,
                    (HotelPrice("h_yar", 6000, True), HotelPrice("h_2", 4000, False)),
                    False,
                    True,
                    360,
                ),
            )
        )
        res = recompute(u, CANVAS_CREW, True, None, CostOverrides(hotel_by_stop={"d1s05": "h_2"}))
        self.assertEqual(line(res, CostKey.LODGING), 4000)
        # no breakfast at h_2: + 3 people × 360 on day 2
        self.assertEqual(line(res, CostKey.FOOD), 3 * 4200 + 3 * 360)
        alt = AltUnits(1.5, "RU-YAR", None, 200, 100, "Музей", "pl_m")
        res2 = recompute(units(), CANVAS_CREW, True, None, CostOverrides(replaced={"d1s02": alt}))
        self.assertEqual(line(res2, CostKey.TICKETS), 2 * 200 + 100)
        self.assertEqual(line(res2, CostKey.FUEL), round_to(Decimal("751.5") * Decimal("0.08") * 62, 10))

    def test_as_of_oldest(self) -> None:
        ctx, _ = make_ctx()
        old = RegionPrice("RU-MOS", FuelType.AI95, Decimal("61.0"), date(2026, 8, 1))
        new = RegionPrice("RU-YAR", FuelType.AI95, Decimal("62.0"), date(2026, 10, 1))
        hotel = make_place("h", PlaceType.LODGING, price_night_rub=5000, verified_at=date(2026, 7, 20))
        ci = CostInput(
            (RegionKm("RU-MOS", "М", 100, old), RegionKm("RU-YAR", "Я", 100, new)),
            (),
            (NightInput("d1s03", 1, "Ростов", hotel, (hotel,), 4000, 700),),
            (DayInput(1, False, None, None, 700, None, False, 700),),
            (),
            date(2026, 10, 1),
        )
        res = compute_cost(ci, sample_normalized(), ctx.cfg)
        self.assertEqual(res.lines[0].as_of, "2026-08")
        self.assertEqual(res.lines[2].as_of, "2026-07")
        self.assertEqual(res.prices_as_of, "2026-07")
        self.assertEqual(res.lines[1].as_of, "2026-10")  # no tolls → defaults

    def test_formula_km_equals_trip_km(self) -> None:
        from tests.helpers import make_planner, trip
        from verst_planner.domain.model import CostOverrides

        planner, _ = make_planner()
        plan = planner.plan(trip(round_trip=True))
        fuel = plan.cost.lines[0]
        self.assertTrue(fuel.formula_ru.startswith(f"{plan.km} км ×"), fuel.formula_ru)
        self.assertEqual(plan.cost.units.fuel.trip_km, plan.km)
        regions_km = sum(r.km for r in plan.cost.units.fuel.regions)
        self.assertAlmostEqual(regions_km, plan.km, delta=len(plan.days_list))  # exact km stay in the units
        stop = next(s for d in plan.days_list for s in d.stops if s.alternatives)
        alt = stop.alternatives[0]
        offline = recompute(
            plan.cost.units, plan.input.crew, True, None, CostOverrides(replaced={stop.id: alt.units})
        )
        shown = round(plan.km + alt.units.delta_km)
        self.assertTrue(offline.lines[0].formula_ru.startswith(f"{shown} км ×"))
        replaced = planner.replace_stop(plan, stop.id, alt.id)
        self.assertTrue(replaced.cost.lines[0].formula_ru.startswith(f"{replaced.km} км ×"))

    def test_as_of_uses_defaults_date(self) -> None:
        from tests.helpers import make_planner, trip

        planner, fakes = make_planner()
        self.assertEqual(fakes.prices.defaults_as_of(), date(2026, 10, 1))  # the world's asOf
        fakes.prices.defaults_as_of = lambda: date(2026, 6, 15)  # type: ignore[method-assign]
        plan = planner.plan(trip(round_trip=True))  # no tolls, default-priced breakfast/dinner checks
        lines = {x.key.value: x for x in plan.cost.lines}
        self.assertEqual(lines["tolls"].as_of, "2026-06")
        self.assertEqual(lines["food"].as_of, "2026-06")  # dinner is priced at defaults
        self.assertNotEqual(lines["fuel"].as_of, "2026-06")  # fuel keeps its own price dates

    def test_meal_rules_d6(self) -> None:
        ctx, _ = make_ctx()
        inp = sample_normalized()
        lunch = make_place("f", PlaceType.FOOD, avg_check_rub=650)
        hotel_nb = make_place("h", PlaceType.LODGING, price_night_rub=5000, breakfast_included=False)
        days = (
            DayInput(1, True, "d1s03", lunch, 700, None, False, 700),
            DayInput(2, False, None, None, 700, datetime(2026, 10, 25, 19, 30), False, 800),
        )
        ci = CostInput(
            (),
            (),
            (NightInput("d1s05", 1, "Ростов", hotel_nb, (hotel_nb,), 4000, 700),),
            days,
            (),
            date(2026, 10, 1),
        )
        u = build_units(ci, inp, ctx.cfg)
        self.assertEqual(
            [(m.day, m.meal, m.check_rub) for m in u.meals],
            [(1, Meal.LUNCH, 650), (1, Meal.DINNER, 700), (2, Meal.DINNER, 800)],
        )
        self.assertEqual(u.nights[0].breakfast_check_rub, 420)  # 0.6 × 700
        res = recompute(u, Crew(2, 0, False), True, None)
        self.assertEqual(line(res, CostKey.FOOD), 2 * (650 + 700 + 420 + 800))
        self.assertEqual(res.lines[3].breakdown[1].formula_ru, "завтрак 420 + ужин 800")
        home = (days[0], DayInput(2, False, None, None, 700, datetime(2026, 10, 25, 19, 30), True, 800))
        u2 = build_units(CostInput((), (), ci.nights, home, (), date(2026, 10, 1)), inp, ctx.cfg)
        self.assertEqual(len(u2.meals), 2)  # finish at home: no extra dinner

    def test_tickets_formula(self) -> None:
        sights = (
            SightInput("d1s02", make_place("a", PlaceType.SIGHT, ticket_adult_rub=400, ticket_child_rub=200)),
            SightInput("d1s03", make_place("b", PlaceType.SIGHT, tags={Tag.FREE_ENTRY})),
        )
        ctx, _ = make_ctx()
        u = build_units(CostInput((), (), (), (), sights, date(2026, 10, 1)), sample_normalized(), ctx.cfg)
        res = recompute(u, Crew(2, 1, True), True, None)
        self.assertEqual(res.lines[4].formula_ru, "1 место × (2 взр. + 1 реб.)")
        self.assertEqual(res.lines[4].breakdown[0].formula_ru, "2 × 400 + 1 × 200")
        self.assertEqual(recompute(u, Crew(2, 0, True), True, None).lines[4].formula_ru, "1 место × 2 взр.")

    def test_formula_strings_russian(self) -> None:
        latin = re.compile(r"[A-Za-z]")
        res = recompute(units(), CANVAS_CREW, True, 40_000)
        u2 = units(
            fuel=FuelUnits(
                7.5,
                FuelType.DT,
                (
                    FuelRegionUnit("RU-MOS", "Московская область", 1300.0, Decimal("61.80")),
                    FuelRegionUnit("RU-YAR", "Ярославская область", 445.0, Decimal("61.90")),
                ),
                "2026-10",
            ),
            tolls=(TollUnit("ts", "М-12", 800, False, "2026-10"),),
        )
        for r in (res, recompute(u2, Crew(3, 2, True, (3, 10)), True, 10_000)):
            for x in r.lines:
                for text in (
                    x.title_ru,
                    x.formula_ru,
                    *(b.label_ru for b in x.breakdown),
                    *(b.formula_ru for b in x.breakdown),
                ):
                    with self.subTest(text=text):
                        self.assertIsNone(latin.search(text))
                        self.assertNotIn(
                            ".", text.replace("чел.", "").replace("взр.", "").replace("реб.", "")
                        )
        fuel2 = recompute(u2, Crew(3, 2, True), True, None).lines[0]
        self.assertIn(f"1{THIN}745 км × 7,5 л/100", fuel2.formula_ru)
        self.assertEqual(fuel2.title_ru, "Дизель")
        self.assertEqual(res.lines[3].title_ru, "Питание")
        self.assertEqual(res.lines[5].title_ru, "Резерв 10%")
        self.assertEqual(res.lines[5].formula_ru, "на пробки и «давай заедем»")

    def test_mood_flag_from_input(self) -> None:
        ctx, _ = make_ctx()
        inp = sample_normalized()
        u = build_units(CostInput((), (), (), (), (), date(2026, 10, 1)), inp, ctx.cfg)
        self.assertFalse(u.mood_just_drive)
        self.assertEqual(inp.mood, Mood.CALM)


if __name__ == "__main__":
    unittest.main()
