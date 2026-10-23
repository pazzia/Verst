import unittest
from unittest import mock

from tests.helpers import make_ctx, trip
from tests.unit.test_rest import day
from tests.unit.test_sights import corridor, setup, sight, sight_ids
from verst_planner.domain.enums import Mood, StopKind, WarningCode
from verst_planner.domain.model import LatLon, PlannedStop
from verst_planner.pipeline import fuel as fuel_stage
from verst_planner.pipeline.base_route import build_base_route
from verst_planner.pipeline.corridor import build_corridor, place_fixed
from verst_planner.pipeline.day_split import split_days
from verst_planner.pipeline.meals import plan_meals
from verst_planner.pipeline.overnight import choose_overnights
from verst_planner.pipeline.resolve import normalize_input, resolve_points
from verst_planner.pipeline.rest import plan_rests
from verst_planner.pipeline.schedule import day_km, drive_minutes, schedule_with_rerun, stop_km_from_prev
from verst_planner.pipeline.sights import plan_sights
from verst_planner.pipeline.timeline import build_day_plans


def planned_sight(pid: str, km: float, score: float, dwell: int, fixed: bool = False) -> PlannedStop:
    s = sight(pid, km)
    return PlannedStop(
        StopKind.SIGHT,
        km,
        pid,
        LatLon(52, 38),
        place=s.place,
        dwell_min=dwell,
        score=score,
        fixed=fixed,
        region_code="RU-MOS",
    )


class ScheduleTest(unittest.TestCase):
    def test_rerun_drops_lowest_first(self) -> None:
        ctx, inp = setup(Mood.CALM)
        # 400 min driving + 90 + 90 = 580 > 540 → drop the lower-score sight (B), keep A
        d = day(400, [planned_sight("A", 100, 5.0, 90), planned_sight("B", 200, 3.0, 90)])
        sched, warnings = schedule_with_rerun([d], corridor([]), inp, ctx)
        self.assertEqual(sight_ids(d), ["A"])
        self.assertEqual(warnings, [])
        self.assertFalse(sched[0].over_budget)
        self.assertEqual(ctx.rerun, 1)

    def test_rerun_tie_drops_later(self) -> None:
        ctx, inp = setup(Mood.CALM)
        d = day(400, [planned_sight("A", 100, 4.0, 90), planned_sight("B", 200, 4.0, 90)])
        schedule_with_rerun([d], corridor([]), inp, ctx)
        self.assertEqual(sight_ids(d), ["A"])

    def test_rerun_only_once(self) -> None:
        ctx, inp = setup(Mood.CALM)
        d = day(
            400,
            [planned_sight("F1", 100, 5.0, 240, fixed=True), planned_sight("F2", 200, 5.0, 240, fixed=True)],
        )
        real = fuel_stage.plan_fuel
        with mock.patch.object(fuel_stage, "plan_fuel", side_effect=real) as spy:
            fuel_stage.plan_fuel([d], corridor([]), inp, ctx)  # the engine's first pass
            schedule_with_rerun([d], corridor([]), inp, ctx)
        self.assertEqual(spy.call_count, 2)
        self.assertEqual(ctx.rerun, 1)

    def test_day_over_budget_warning(self) -> None:
        ctx, inp = setup(Mood.CALM)
        d = day(
            400,
            [planned_sight("F1", 100, 5.0, 120, fixed=True), planned_sight("F2", 200, 5.0, 120, fixed=True)],
        )
        sched, warnings = schedule_with_rerun([d], corridor([]), inp, ctx)
        self.assertEqual([(w.code, w.day) for w in warnings], [(WarningCode.DAY_OVER_BUDGET, 1)])
        self.assertEqual(warnings[0].message_ru, "День 1 получился длинным — можно убрать остановку")
        self.assertTrue(sched[0].over_budget)
        self.assertEqual(sight_ids(d), ["F1", "F2"])  # fixed sights are never dropped
        self.assertGreater(sched[0].duration_min, 540)

    def test_no_rerun_when_fine(self) -> None:
        ctx, inp = setup(Mood.CALM)
        d = day(300)
        _sched, warnings = schedule_with_rerun([d], corridor([]), inp, ctx)
        self.assertEqual((warnings, ctx.rerun), ([], 0))

    def test_km_rounding_sum(self) -> None:
        ctx, _ = make_ctx()
        inp = normalize_input(trip(round_trip=True), ctx)
        pts = resolve_points(inp, ctx)
        route = build_base_route(pts, inp, ctx)
        cor = build_corridor(route, inp, ctx)
        nights = choose_overnights(split_days(route, cor, inp, None, ctx), cor, inp, ctx)
        profile = ctx.profile_for(route)
        days = build_day_plans(route, nights.choices, place_fixed(pts, cor, inp, ctx), inp, ctx, pts, profile)
        ctx.fuel_warnings = fuel_stage.plan_fuel(days, cor, inp, ctx)
        plan_rests(days, cor, inp, ctx)
        plan_meals(days, cor, inp, ctx)
        plan_sights(days, cor, inp, ctx)
        sched, _w = schedule_with_rerun(days, cor, inp, ctx)
        kms = [day_km(sd.plan) for sd in sched]
        trip_km = sum(kms)
        self.assertEqual(sum(kms), trip_km)
        self.assertAlmostEqual(trip_km, 526 + sum(s.detour_km for d in days for s in d.stops), delta=1)
        for sd, row in zip(sched, stop_km_from_prev(days), strict=True):
            self.assertTrue(all(k >= 0 for k in row))
            self.assertAlmostEqual(sum(row), day_km(sd.plan), delta=len(row))  # each row rounds once
            self.assertGreater(drive_minutes(sd.slots), 0)


if __name__ == "__main__":
    unittest.main()
