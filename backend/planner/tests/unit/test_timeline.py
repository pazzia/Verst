import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tests.helpers import UNIT_DATA, line_north, make_ctx, make_route, trip
from verst_planner.domain.enums import StopKind
from verst_planner.domain.model import Crew, DayPlan, LatLon, PlannedStop
from verst_planner.pipeline.base_route import build_base_route
from verst_planner.pipeline.corridor import build_corridor, place_fixed
from verst_planner.pipeline.day_split import split_days
from verst_planner.pipeline.overnight import choose_overnights
from verst_planner.pipeline.resolve import normalize_input, resolve_points
from verst_planner.pipeline.timeline import (
    Profile,
    build_day_plans,
    day_duration_min,
    day_end,
    eta_if_inserted,
    local_minute,
    next_day_start,
    schedule_day,
)

MSK = ZoneInfo("Europe/Moscow")
P = LatLon(56.0, 38.0)


def stop(kind: StopKind, km: float, dwell: int = 0, detour_min: int = 0) -> PlannedStop:
    return PlannedStop(kind, km, kind.value, P, dwell_min=dwell, detour_min=detour_min)


def plan(world: str, **kw: object) -> tuple[object, list[DayPlan], Profile]:
    ctx, _ = make_ctx(world)
    inp = normalize_input(trip(world=world, **kw), ctx)  # type: ignore[arg-type]
    pts = resolve_points(inp, ctx)
    route = build_base_route(pts, inp, ctx)
    corridor = build_corridor(route, inp, ctx)
    split = split_days(route, corridor, inp, pts.template, ctx)
    nights = choose_overnights(split, corridor, inp, ctx)
    profile = ctx.profile_for(route)
    days = build_day_plans(
        route, nights.choices, place_fixed(pts, corridor, inp, ctx), inp, ctx, pts, profile
    )
    return ctx, days, profile


class TimelineTest(unittest.TestCase):
    def test_schedule_simple(self) -> None:
        route = make_route(line_north(56.0, 38.0, 100), speed_kmh=60, cum_km=[float(i) for i in range(101)])
        profile = Profile.from_route(route, 1.1)
        start = datetime(2026, 10, 24, 8, 0, tzinfo=MSK)
        day = DayPlan(
            1,
            0.0,
            100.0,
            start,
            [
                stop(StopKind.START, 0),
                stop(StopKind.SIGHT, 50, dwell=30, detour_min=10),
                stop(StopKind.FINISH, 100),
            ],
            "Europe/Moscow",
        )
        slots = schedule_day(day, profile)
        self.assertIsNone(slots[0].arrive)
        self.assertEqual(slots[0].depart, start)
        self.assertEqual(slots[1].arrive, start + timedelta(minutes=55 + 5))
        self.assertEqual(slots[1].depart, start + timedelta(minutes=55 + 5 + 30))
        self.assertEqual(day_end(slots), start + timedelta(minutes=110 + 30 + 10))
        self.assertIsNone(slots[2].depart)
        self.assertAlmostEqual(day_duration_min(day, slots), 150)
        self.assertAlmostEqual(sum(s.drive_min for s in slots), 120)  # driving incl. the 10 min detour

    def test_eta_if_inserted_does_not_mutate(self) -> None:
        route = make_route(line_north(56.0, 38.0, 100), speed_kmh=60, cum_km=[float(i) for i in range(101)])
        profile = Profile.from_route(route, 1.0)
        start = datetime(2026, 10, 24, 8, 0, tzinfo=MSK)
        day = DayPlan(
            1, 0.0, 100.0, start, [stop(StopKind.START, 0), stop(StopKind.FINISH, 100)], "Europe/Moscow"
        )
        slot, slots = eta_if_inserted(day, stop(StopKind.REST, 30, dwell=20), profile)
        self.assertEqual(slot.arrive, start + timedelta(minutes=30))
        self.assertEqual(day_end(slots), start + timedelta(minutes=120))
        self.assertEqual(len(day.stops), 2)

    def test_day2_starts_0900_next_day(self) -> None:
        _ctx, days, _p = plan("central_russia_v1", round_trip=True)
        self.assertEqual(len(days), 2)
        self.assertEqual(days[0].start_at, datetime(2026, 10, 24, 8, 0, tzinfo=MSK))
        self.assertEqual(days[1].start_at, datetime(2026, 10, 25, 9, 0, tzinfo=MSK))
        self.assertEqual(days[0].stops[-1].kind, StopKind.OVERNIGHT)
        self.assertEqual(days[1].stops[0].name_ru, "Ярославль")
        self.assertEqual(days[1].stops[-1].kind, StopKind.FINISH)
        late = datetime(2026, 10, 25, 0, 40, tzinfo=MSK)  # arrival after midnight → the day after that
        self.assertEqual(next_day_start(late, "Europe/Moscow", days[0].start_at.time()).day, 26)

    def test_local_tz_rendering(self) -> None:
        ctx, days, profile = plan(
            UNIT_DATA / "mini_world.json",
            origin="t_alpha",
            destination="t_gamma",  # type: ignore[arg-type]
            daily_km=300,
        )
        finish = days[-1].stops[-1]
        self.assertEqual(finish.region_code, "RU-SAM")
        tz = ctx.tz_of(finish.region_code, finish.point)  # type: ignore[attr-defined]
        self.assertEqual(tz, "Europe/Samara")
        arrive = day_end(schedule_day(days[-1], profile))
        self.assertEqual(local_minute(arrive, tz) - local_minute(arrive, "Europe/Moscow"), timedelta(hours=1))
        self.assertEqual(days[0].tz, "Europe/Moscow")

    def test_local_minute_rounding(self) -> None:
        t = datetime(2026, 10, 24, 5, 0, 29, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(local_minute(t, "Europe/Moscow"), datetime(2026, 10, 24, 8, 0))
        self.assertEqual(
            local_minute(t + timedelta(seconds=1), "Europe/Moscow"), datetime(2026, 10, 24, 8, 1)
        )

    def test_template_vias_and_fixed_stops(self) -> None:
        _ctx, days, _p = plan(
            "central_russia_v1",
            destination=None,
            ready_route_id="rr_golden_ring",
            crew=Crew(2, 1, True),
        )
        self.assertEqual(len(days), 3)
        kinds1 = [s.kind.value for s in days[0].stops]
        self.assertEqual(kinds1[0], "start")
        self.assertEqual(kinds1[-1], "overnight")
        self.assertEqual(kinds1.count("via"), 3)  # Сергиев Посад, Переславль, Ростов (Ярославль = overnight)
        self.assertIn("sight", kinds1)  # the lavra
        self.assertEqual([s.name_ru for s in days[2].stops if s.kind is StopKind.VIA], ["Владимир"])
        self.assertEqual(days[2].stops[-1].kind, StopKind.FINISH)


if __name__ == "__main__":
    unittest.main()
