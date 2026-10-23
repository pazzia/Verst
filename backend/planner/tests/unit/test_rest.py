import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.helpers import line_north, make_ctx, make_place, make_route, trip
from verst_planner.domain.enums import Mood, PlaceType, RoadClass, StopKind, Tag
from verst_planner.domain.model import Candidate, Crew, DayPlan, LatLon, NormalizedInput, PlannedStop
from verst_planner.geo.index import PolylineIndex
from verst_planner.pipeline import Corridor, PlanContext
from verst_planner.pipeline.resolve import normalize_input
from verst_planner.pipeline.rest import plan_rests

MSK = ZoneInfo("Europe/Moscow")
# 66 km/h × drive-time factor 1.1 → exactly one driving minute per km
ROUTE = make_route(line_north(52.0, 38.0, 600), speed_kmh=66, cum_km=[float(i) for i in range(601)])


def place_at(pid: str, ptype: PlaceType, km: float, tags: set[Tag], **kw: object) -> Candidate:
    p = make_place(pid, ptype, ROUTE.points[round(km)].lat, 38.002, tags, **kw)  # type: ignore[arg-type]
    return Candidate(p, km, 0.2, 0.52, 0, RoadClass.TRUNK, "RU-MOS")


def rests_every(step: int, until: int, tags: set[Tag] | None = None) -> list[Candidate]:
    return [place_at(f"r{k:03d}", PlaceType.REST, k, tags or {Tag.WC}) for k in range(step, until, step)]


def corridor(
    rest: list[Candidate], sights: list[Candidate] | None = None, fuel: list[Candidate] | None = None
) -> Corridor:
    return Corridor(
        ROUTE,
        PolylineIndex(ROUTE),
        sorted(sights or [], key=lambda c: c.km_at),
        [],
        sorted(fuel or [], key=lambda c: c.km_at),
        sorted(rest, key=lambda c: c.km_at),
        [],
        [],
    )


def day(km: float, extra: list[PlannedStop] | None = None) -> DayPlan:
    stops = [
        PlannedStop(StopKind.START, 0.0, "старт", LatLon(52, 38), fixed=True),
        *(extra or []),
        PlannedStop(StopKind.FINISH, km, "финиш", LatLon(52, 38), fixed=True),
    ]
    return DayPlan(1, 0.0, km, datetime(2026, 10, 24, 8, 0, tzinfo=MSK), stops, "Europe/Moscow")


def setup(crew: Crew | None = None, mood: Mood | None = None) -> tuple[PlanContext, NormalizedInput]:
    ctx, _ = make_ctx()
    return ctx, normalize_input(trip(crew=crew or Crew(2, 0, False), mood=mood), ctx)


def rest_kms(d: DayPlan) -> list[float]:
    return [s.km_at for s in d.stops if s.auto]


class RestTest(unittest.TestCase):
    def test_rest_interval_by_mood(self) -> None:
        expected = {Mood.CALM: [120, 240], Mood.MORE_STOPS: [90, 180, 270], Mood.JUST_DRIVE: [180]}
        for mood, kms in expected.items():
            with self.subTest(mood=mood.value):
                ctx, inp = setup(mood=mood)
                d = day(360)  # six hours of driving
                plan_rests([d], corridor(rests_every(2, 360)), inp, ctx)
                self.assertEqual(rest_kms(d), kms)
                self.assertTrue(all(s.kind is StopKind.REST and s.dwell_min == 20 for s in d.stops if s.auto))

    def test_existing_stop_counts_as_break(self) -> None:
        ctx, inp = setup(mood=Mood.CALM)
        sight = PlannedStop(StopKind.SIGHT, 100.0, "музей", LatLon(52, 38), dwell_min=30, fixed=True)
        d = day(360, [sight])
        plan_rests([d], corridor(rests_every(2, 360)), inp, ctx)
        self.assertEqual(rest_kms(d), [220])  # 120 min after the sight, not after the start
        # a fuel stop of 10 min is not a break
        ctx, inp = setup(mood=Mood.CALM)
        fuel = PlannedStop(StopKind.FUEL, 100.0, "АЗС", LatLon(52, 38), dwell_min=10, auto=True)
        d = day(360, [fuel])
        plan_rests([d], corridor(rests_every(2, 360)), inp, ctx)
        self.assertEqual(rest_kms(d), [100, 120, 240])

    def test_playground_preferred_with_children(self) -> None:
        pool = [
            place_at("r_wc", PlaceType.REST, 110, {Tag.WC}),
            place_at("r_play", PlaceType.REST, 100, {Tag.WC, Tag.PLAYGROUND}),
        ]
        ctx, inp = setup(crew=Crew(2, 1, False))  # calm
        d = day(200)
        plan_rests([d], corridor(pool), inp, ctx)
        chosen = [s for s in d.stops if s.auto]
        self.assertEqual([s.place.id for s in chosen if s.place], ["r_play"])
        self.assertEqual(chosen[0].reason_key, "rest.who")
        self.assertEqual(chosen[0].reason_params["who"], "ребёнку побегать")
        ctx, inp = setup(crew=Crew(2, 0, False), mood=Mood.CALM)
        d = day(200)
        plan_rests([d], corridor(pool), inp, ctx)
        self.assertEqual([s.place.id for s in d.stops if s.auto and s.place], ["r_wc"])  # tie → closer to R

    def test_walk_preferred_with_dog(self) -> None:
        pool = [
            place_at("r_wc", PlaceType.REST, 110, {Tag.WC}),
            place_at("r_walk", PlaceType.REST, 100, {Tag.WALK}),
        ]
        ctx, inp = setup(crew=Crew(2, 0, True), mood=Mood.CALM)
        d = day(200)
        plan_rests([d], corridor(pool), inp, ctx)
        chosen = [s for s in d.stops if s.auto]
        self.assertEqual([s.place.id for s in chosen if s.place], ["r_walk"])  # 1 + 1.5 > 1 + 1
        self.assertEqual(chosen[0].reason_params["who"], "собаке погулять")

    def test_no_rest_near_day_end(self) -> None:
        ctx, inp = setup(mood=Mood.CALM)
        d = day(140)  # 120 min reached at km 120, only 20 min left
        plan_rests([d], corridor(rests_every(2, 140)), inp, ctx)
        self.assertEqual(rest_kms(d), [])

    def test_widened_window_and_virtual_break(self) -> None:
        ctx, inp = setup(mood=Mood.CALM)
        d = day(300)
        # nothing in [90, 120]; the widened window [60, 135] has km 130
        plan_rests([d], corridor([place_at("r130", PlaceType.REST, 130, {Tag.WC})]), inp, ctx)
        self.assertEqual(rest_kms(d), [130])
        ctx, inp = setup(mood=Mood.CALM)
        d = day(300)
        plan_rests([d], corridor([]), inp, ctx)  # no candidates at all: virtual breaks, no stops
        self.assertEqual(rest_kms(d), [])

    def test_coffee_and_short_sight_in_pool(self) -> None:
        ctx, inp = setup(mood=Mood.CALM)
        cafe = place_at("f_cafe", PlaceType.FUEL, 115, {Tag.CAFE_AT_FUEL, Tag.WC})
        d = day(200)
        plan_rests([d], corridor([], fuel=[cafe]), inp, ctx)
        coffee = next(s for s in d.stops if s.auto)
        self.assertEqual((coffee.kind, coffee.dwell_min, coffee.coffee), (StopKind.FUEL, 15, True))
        ctx, inp = setup(mood=Mood.CALM)
        view = place_at(
            "s_view", PlaceType.SIGHT, 112, {Tag.VIEW}, dwell_min=20, opening_hours="Mo-Su 06:00-09:00"
        )
        d = day(200)
        plan_rests([d], corridor([], sights=[view]), inp, ctx)
        self.assertEqual(rest_kms(d), [])  # closed at the 09:52 ETA → virtual break instead
        self.assertEqual(d.stops[1].kind, StopKind.FINISH)


if __name__ == "__main__":
    unittest.main()
