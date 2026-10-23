import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.helpers import line_north, make_ctx, make_place, make_route, trip
from verst_planner.domain.enums import PlaceType, RoadClass, StopKind, Tag, WarningCode
from verst_planner.domain.model import Candidate, DayPlan, LatLon, PlannedStop, Vehicle
from verst_planner.geo.index import PolylineIndex
from verst_planner.pipeline import Corridor, PlanContext
from verst_planner.pipeline.fuel import fuel_range, plan_fuel
from verst_planner.pipeline.resolve import normalize_input

MSK = ZoneInfo("Europe/Moscow")


def route(total: int) -> object:
    return make_route(
        line_north(50.0, 38.0, total), speed_kmh=80, cum_km=[float(i) for i in range(total + 1)]
    )


def station(pid: str, km: float, tags: set[Tag] = frozenset(), detour_min: int = 0) -> Candidate:  # type: ignore[assignment]
    p = make_place(pid, PlaceType.FUEL, 50.0 + km / 111.195, 38.0, tags)
    return Candidate(p, km, 0.2, 0.52, detour_min, RoadClass.TRUNK, "RU-MOS")


def corridor(total: int, fuel: list[Candidate]) -> Corridor:
    r = route(total)
    return Corridor(r, PolylineIndex(r), [], [], sorted(fuel, key=lambda c: c.km_at), [], [], [])  # type: ignore[arg-type]


def days_for(total: int, nights: list[float]) -> list[DayPlan]:
    bounds = [0.0, *nights, float(total)]
    out = []
    for d in range(1, len(bounds)):
        a, b = bounds[d - 1], bounds[d]
        end_kind = StopKind.OVERNIGHT if d < len(bounds) - 1 else StopKind.FINISH
        stops = [
            PlannedStop(StopKind.START, a, "старт", LatLon(50, 38), fixed=True),
            PlannedStop(end_kind, b, "конец", LatLon(50, 38), fixed=True),
        ]
        out.append(DayPlan(d, a, b, datetime(2026, 10, 23 + d, 8, 0, tzinfo=MSK), stops, "Europe/Moscow"))
    return out


def ctx_inp(tank: float = 50.0, round_trip: bool = False) -> tuple[PlanContext, object]:
    ctx, _ = make_ctx()
    return ctx, normalize_input(trip(vehicle=Vehicle(8.0, tank_l=tank), round_trip=round_trip), ctx)


def fuel_stops(days: list[DayPlan]) -> list[PlannedStop]:
    return [s for d in days for s in d.stops if s.kind is StopKind.FUEL]


class FuelTest(unittest.TestCase):
    def test_fuel_range_math(self) -> None:
        ctx, _ = make_ctx()
        r = fuel_range(Vehicle(8.0, tank_l=50.0), ctx)
        self.assertAlmostEqual(r.full_km, 625.0)
        self.assertAlmostEqual(r.usable_km, 500.0)  # trigger: 20 % of the full range left

    def test_fuel_in_lookahead_window(self) -> None:
        ctx, inp = ctx_inp()
        cor = corridor(900, [station("f_490", 490), station("f_520", 520), station("f_560", 560)])
        days = days_for(900, [])
        self.assertEqual(plan_fuel(days, cor, inp, ctx), [])  # type: ignore[arg-type]
        stops = fuel_stops(days)
        self.assertEqual([s.place.id for s in stops if s.place], ["f_520"])  # window [500, 540]
        self.assertEqual(stops[0].reason_key, "fuel.range")
        self.assertEqual(stops[0].reason_params, {"km": 500})
        self.assertAlmostEqual(stops[0].litres, (520 + 0.52) * 0.08)

    def test_fuel_prefers_coincide(self) -> None:
        ctx, inp = ctx_inp()
        cor = corridor(
            900, [station("f_best", 505, {Tag.CAFE_AT_FUEL, Tag.H24, Tag.WC}), station("f_near", 511.5)]
        )
        days = days_for(900, [])
        lunch = PlannedStop(StopKind.FOOD, 510.0, "обед", LatLon(50, 38), dwell_min=60)
        days[0].stops.insert(1, lunch)
        plan_fuel(days, cor, inp, ctx)  # type: ignore[arg-type]
        stops = fuel_stops(days)
        self.assertEqual([s.place.id for s in stops if s.place], ["f_near"])  # 3 (coincide) > 2.5
        self.assertEqual(stops[0].reason_key, "fuel.coincide")

    def test_fuel_evening_before_overnight(self) -> None:
        ctx, inp = ctx_inp()
        cor = corridor(
            900, [station("f_300", 300), station("f_430", 430), station("f_470", 470), station("f_510", 510)]
        )
        days = days_for(900, [460])
        plan_fuel(days, cor, inp, ctx)  # type: ignore[arg-type]
        stops = fuel_stops(days)
        self.assertEqual([s.place.id for s in stops if s.place], ["f_430"])
        self.assertTrue(420 <= stops[0].km_at <= 460)
        self.assertEqual(stops[0].reason_key, "fuel.evening")
        self.assertIn(stops[0], days[0].stops)  # day 1, before the overnight
        self.assertIs(days[0].stops[-1].kind, StopKind.OVERNIGHT)

    def test_no_fuel_near_finish(self) -> None:
        ctx, inp = ctx_inp()
        cor = corridor(540, [station("f_500", 500), station("f_520", 520)])
        days = days_for(540, [])
        self.assertEqual(plan_fuel(days, cor, inp, ctx), [])  # type: ignore[arg-type]
        self.assertEqual(fuel_stops(days), [])  # trigger 500 ≥ 540 − 10 % of 625

    def test_lookback_prefers_latest(self) -> None:
        ctx, inp = ctx_inp()
        # nothing in [500, 540]: look back to [400, 500] and prefer the latest (score + 0.01·km)
        cor = corridor(900, [station("f_410", 410), station("f_470", 470)])
        days = days_for(900, [])
        plan_fuel(days, cor, inp, ctx)  # type: ignore[arg-type]
        self.assertEqual([s.place.id for s in fuel_stops(days) if s.place], ["f_470"])  # 4.7 > 4.1
        # a 24 h station 60 km earlier still wins: 1 + 4.1 = 5.1 > 4.7
        cor = corridor(900, [station("f_410", 410, {Tag.H24}), station("f_470", 470)])
        days = days_for(900, [])
        plan_fuel(days, cor, inp, ctx)  # type: ignore[arg-type]
        self.assertEqual([s.place.id for s in fuel_stops(days) if s.place], ["f_410"])

    def test_fuel_gap_warning(self) -> None:
        ctx, inp = ctx_inp(tank=30.0)  # full 375 km, trigger at 300
        cor = corridor(450, [station("f_40", 40), station("f_80", 80), station("f_420", 420)])
        days = days_for(450, [])
        warnings = plan_fuel(days, cor, inp, ctx)  # type: ignore[arg-type]
        self.assertEqual([w.code for w in warnings], [WarningCode.FUEL_GAP])
        self.assertEqual(warnings[0].detail, "km=300.0")
        self.assertEqual(warnings[0].message_ru, "На участке 300 км мало заправок — заправьтесь заранее")
        self.assertEqual(warnings[0].day, 1)
        self.assertEqual(fuel_stops(days), [])

    def test_fuel_stage_does_not_upgrade_coffee(self) -> None:
        # A§16.2: coffee upgrades belong to stage 7 (only where a break is due); stage 6 plans 10-min fills
        ctx, inp = ctx_inp()
        cor = corridor(1100, [station("f_cafe", 520, {Tag.CAFE_AT_FUEL}), station("f_plain", 1020)])
        days = days_for(1100, [])
        plan_fuel(days, cor, inp, ctx)  # type: ignore[arg-type]
        cafe, plain = fuel_stops(days)
        self.assertEqual((cafe.coffee, cafe.dwell_min, cafe.pool), (False, 10, "fuel"))
        self.assertFalse(plain.coffee)
        self.assertEqual(plain.dwell_min, 10)
        self.assertAlmostEqual(plain.litres, (1020 - 520 + 0.52) * 0.08)

    def test_evening_reason_precedes_last(self) -> None:
        # A§16.7: the last fill of a round trip that is an evening fill keeps «Заправиться вечером…»
        ctx, inp = ctx_inp(round_trip=True)
        cor = corridor(900, [station("f_460", 460)])
        days = days_for(900, [470])  # trigger 500 is within 60 km after the overnight at 470
        plan_fuel(days, cor, inp, ctx)  # type: ignore[arg-type]
        (only,) = fuel_stops(days)
        self.assertEqual((only.km_at, only.reason_key), (460, "fuel.evening"))
        days = days_for(900, [])  # no overnight: the same station is a range fill → «Последняя…»
        cor = corridor(900, [station("f_510", 510)])
        plan_fuel(days, cor, inp, ctx)  # type: ignore[arg-type]
        self.assertEqual(fuel_stops(days)[0].reason_key, "fuel.last")

    def test_last_fill_before_home(self) -> None:
        ctx, inp = ctx_inp(round_trip=True)
        cor = corridor(900, [station("f_520", 520)])
        days = days_for(900, [])
        plan_fuel(days, cor, inp, ctx)  # type: ignore[arg-type]
        self.assertEqual(fuel_stops(days)[0].reason_key, "fuel.last")


if __name__ == "__main__":
    unittest.main()
