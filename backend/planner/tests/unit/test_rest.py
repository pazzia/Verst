import itertools
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.helpers import line_north, make_ctx, make_place, make_route, trip
from verst_planner.domain.enums import Mood, PlaceType, RoadClass, StopKind, Tag
from verst_planner.domain.model import Candidate, Crew, DayPlan, LatLon, NormalizedInput, PlannedStop
from verst_planner.explain import ru
from verst_planner.geo.index import PolylineIndex
from verst_planner.pipeline import Corridor, PlanContext
from verst_planner.pipeline.resolve import normalize_input
from verst_planner.pipeline.rest import plan_rests
from verst_planner.pipeline.sights import plan_sights

MSK = ZoneInfo("Europe/Moscow")
# 66 km/h × drive-time factor 1.1 → exactly one driving minute per km
ROUTE = make_route(line_north(52.0, 38.0, 600), speed_kmh=66, cum_km=[float(i) for i in range(601)])


def place_at(
    pid: str, ptype: PlaceType, km: float, tags: set[Tag], detour_min: int = 0, **kw: object
) -> Candidate:
    p = make_place(pid, ptype, ROUTE.points[round(km)].lat, 38.002, tags, **kw)  # type: ignore[arg-type]
    return Candidate(p, km, 0.2, 0.52, detour_min, RoadClass.TRUNK, "RU-MOS")


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


def setup(
    crew: Crew | None = None, mood: Mood | None = None, config: dict[str, object] | None = None
) -> tuple[PlanContext, NormalizedInput]:
    ctx, _ = make_ctx(config=config)
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
        self.assertEqual(rest_kms(d)[0], 130)
        self.assertEqual([s.place for s in d.stops if s.auto][1:], [None])  # then a roadside break at 250
        ctx, inp = setup(mood=Mood.CALM)
        d = day(300)
        plan_rests([d], corridor([]), inp, ctx)  # no candidates at all: roadside breaks (A§16.11.1)
        self.assertEqual([round(k) for k in rest_kms(d)], [120, 240])
        self.assertTrue(all(s.place is None and s.dwell_min == 15 for s in d.stops if s.auto))

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
        # closed at the 09:52 ETA → a roadside break at R instead
        self.assertEqual([(round(s.km_at), s.place) for s in d.stops if s.auto], [(120, None)])


class BreaksTest(unittest.TestCase):
    def test_no_gap_over_R_plus_30(self) -> None:
        # A§16.11.1: whatever the pool, no stretch between breaks exceeds R + 30 minutes of driving
        from verst_planner.pipeline.rest import DriveClock, is_break

        for mood, pool in ((Mood.CALM, []), (Mood.MORE_STOPS, rests_every(37, 600)), (Mood.JUST_DRIVE, [])):
            with self.subTest(mood=mood.value, pool=len(pool)):
                ctx, inp = setup(mood=mood)
                d = day(600)
                plan_rests([d], corridor(pool), inp, ctx)
                clock = DriveClock.of(d, ctx.profile_for(ROUTE))
                marks = [clock.t_arr[i] for i, s in enumerate(d.stops) if is_break(s, 15)] + [clock.t_arr[-1]]
                limit = ctx.cfg.rest_interval_min.of(mood) + 30
                self.assertTrue(all(b - a <= limit + 1e-6 for a, b in itertools.pairwise(marks)))

    def test_roadside_break_when_no_place(self) -> None:
        ctx, inp = setup(mood=Mood.CALM)
        d = day(200)
        plan_rests([d], corridor([]), inp, ctx)
        (stop,) = [s for s in d.stops if s.auto]
        self.assertEqual(
            (stop.kind, stop.place, stop.name_ru, stop.dwell_min, stop.reason_key, stop.pool),
            (StopKind.REST, None, "Остановка у дороги", 15, "rest.roadside", "rest"),
        )
        self.assertAlmostEqual(stop.km_at, 120.0)
        self.assertEqual(
            ctx.templates.render("rest.roadside"),
            "Сделайте остановку на 15 минут — подходящей площадки рядом нет.",
        )
        from verst_planner.pipeline.alternatives import family
        from verst_planner.pipeline.assemble import render_stop
        from verst_planner.pipeline.timeline import schedule_day

        slot = schedule_day(d, ctx.profile_for(ROUTE))[1]
        rendered = render_stop(stop, slot, 1, 1, 2, 120, inp, ctx)
        self.assertEqual((rendered.sign.value, rendered.place_id, rendered.verified), ("rest", None, True))
        self.assertFalse(rendered.replaceable)
        self.assertIsNone(rendered.alternatives_note_ru)
        self.assertIsNone(family(stop))

    def test_extended_window_before_roadside(self) -> None:
        # calm R = 120: an area at 140 min (beyond R + 15) with a 14-min detour (beyond max_detour 10) is
        # outside steps 1-2 but inside the extended window [60, 150] / detour ≤ 15 → used, no roadside
        ctx, inp = setup(mood=Mood.CALM)
        area = place_at("r140", PlaceType.REST, 133, {Tag.WC}, detour_min=14)
        d = day(250)
        plan_rests([d], corridor([area]), inp, ctx)
        self.assertEqual(next(s.place.id if s.place else None for s in d.stops if s.auto), "r140")
        too_far = place_at("r150", PlaceType.REST, 150, {Tag.WC}, detour_min=14)  # 157 min > R + 30
        d = day(250)
        plan_rests([d], corridor([too_far]), inp, ctx)
        self.assertIsNone(next(s.place for s in d.stops if s.auto))

    """A§16.2 (D-17): rests fill only long gaps between breaks."""

    def test_min_gap_after_any_break(self) -> None:
        # more_stops: R = 90, G = 60. A sight (break) at km 100; the only rest area 40 min after it is
        # inside the old widened window [R - 60, R + 15] but closer than G to the break → not used.
        ctx, inp = setup(mood=Mood.MORE_STOPS)
        sight = PlannedStop(StopKind.SIGHT, 50.0, "музей", LatLon(52, 38), dwell_min=30, fixed=True)
        d = day(200, [sight])
        plan_rests([d], corridor([place_at("r090", PlaceType.REST, 90, {Tag.WC})]), inp, ctx)
        # 40 min < 45 also fails the extended window → a roadside break R = 90 min after the sight
        self.assertEqual([(round(s.km_at), s.place) for s in d.stops if s.auto], [(140, None)])
        # the same area 70 min after the break is admissible (window [60, 90])
        ctx, inp = setup(mood=Mood.MORE_STOPS)
        d = day(200, [sight])
        plan_rests([d], corridor([place_at("r120", PlaceType.REST, 120, {Tag.WC})]), inp, ctx)
        self.assertEqual(rest_kms(d), [120])
        # a lunch (break) right after the window: a candidate 10 min before it is admissible in step 2
        # (need_after = min(G, gap - R) = 10); one 5 min before it is not, and is taken by the extended
        # window of step 3 (A§16.11.1) instead of a roadside break
        lunch = PlannedStop(StopKind.FOOD, 100.0, "обед", LatLon(52, 38), dwell_min=60, fixed=True)
        for km, kept in ((90, [90]), (95, [95])):
            with self.subTest(km=km):
                ctx, inp = setup(mood=Mood.MORE_STOPS)
                d = day(140, [lunch])
                plan_rests([d], corridor([place_at(f"r{km}", PlaceType.REST, km, {Tag.WC})]), inp, ctx)
                self.assertEqual(rest_kms(d), kept)

    def test_rest_detour_cap(self) -> None:
        ctx, inp = setup(mood=Mood.CALM)
        far = place_at("r_far", PlaceType.REST, 115, {Tag.WC, Tag.VIEW}, detour_min=27)
        near = place_at("r_near", PlaceType.REST, 100, {Tag.WC}, detour_min=10)
        d = day(200)
        plan_rests([d], corridor([far]), inp, ctx)
        # 27 min > rest.max_detour_min (10) and > rest.extended_detour_min (15): roadside break at R
        self.assertEqual([(round(s.km_at), s.place) for s in d.stops if s.auto], [(120, None)])
        d = day(200)
        plan_rests([d], corridor([far, near]), inp, ctx)
        self.assertEqual([s.place.id for s in d.stops if s.place], ["r_near"])
        # G06 (Москва → Казань without tolls): the М-12 coffee 6.4 km off the М-7 is no longer chosen
        from tests.golden.test_golden import CASES, load_case, run_case

        plan, *_ = run_case(load_case(next(CASES.glob("G06_*.json"))))
        ids = {s.place_id for d2 in plan.days_list for s in d2.stops}
        self.assertNotIn("pl_m12_fuel_490", ids)
        for ds in plan.engine_state.days:
            for st in ds.stops:
                if st.pool == "rest":
                    self.assertLessEqual(st.detour_min, 10, st.place_id)

    def test_fuel_stop_upgraded_to_coffee(self) -> None:
        ctx, inp = setup(mood=Mood.CALM)
        cafe = make_place("f_cafe", PlaceType.FUEL, 52.9, 38.0, {Tag.CAFE_AT_FUEL})
        fuel = PlannedStop(
            StopKind.FUEL, 110.0, "АЗС", LatLon(52, 38), place=cafe, dwell_min=10, auto=True, pool="fuel"
        )
        d = day(300, [fuel])
        plan_rests([d], corridor(rests_every(2, 300)), inp, ctx)
        upgraded = next(s for s in d.stops if s.kind is StopKind.FUEL)
        self.assertEqual((upgraded.coffee, upgraded.dwell_min), (True, 15))
        # no extra stop in the first gap; the next rest is R = 120 min after the coffee
        self.assertEqual(rest_kms(d), [110, 230])
        # a fuel stop without a cafe is not upgraded and does not count as a break
        ctx, inp = setup(mood=Mood.CALM)
        plain = PlannedStop(
            StopKind.FUEL,
            110.0,
            "АЗС",
            LatLon(52, 38),
            place=make_place("f_plain", PlaceType.FUEL),
            dwell_min=10,
            auto=True,
            pool="fuel",
        )
        d = day(300, [plain])
        plan_rests([d], corridor(rests_every(2, 300)), inp, ctx)
        self.assertEqual(rest_kms(d), [110, 120, 240])
        self.assertFalse(d.stops[1].coffee)

    def test_rest_reason_drive_since_break(self) -> None:
        ctx, inp = setup(mood=Mood.CALM)
        sight = PlannedStop(StopKind.SIGHT, 100.0, "музей", LatLon(52, 38), dwell_min=30, fixed=True)
        d = day(300, [sight])
        plan_rests([d], corridor(rests_every(2, 300)), inp, ctx)
        rest = next(s for s in d.stops if s.auto)
        self.assertEqual(rest.km_at, 220)
        self.assertEqual(rest.reason_key, "rest.generic")
        self.assertEqual(rest.reason_params["drive"], ru.duration_genitive(120))  # not 220 since the start
        self.assertEqual(
            ctx.templates.render(rest.reason_key, **rest.reason_params),
            "Разминка 20 минут после двух часов за рулём.",
        )

    def test_sights_reserve_rest_time(self) -> None:
        # calm: budget 540, R = 120, 480 min of driving. A 30-min sight at km 240 is a break, but the day
        # still needs rests at km 120 and 360: 480 + 30 + 2 × 20 = 550 > 540 → stage 9 rejects it (it
        # would fit at 510 if the rests were ignored); without rest areas the two roadside breaks take
        # 2 × 15 min: 480 + 30 + 30 = 540 → it fits.
        from tests.unit.test_sights import sight as sight_cand

        ctx, inp = setup(mood=Mood.CALM)
        cand = sight_cand("s_short", 240, dwell=30)
        rests = rests_every(2, 480)
        d = day(480)
        plan_sights([d], corridor(rests, sights=[cand]), inp, ctx)
        self.assertEqual([s.kind for s in d.stops if s.kind is StopKind.SIGHT], [])
        d = day(480)
        plan_sights([d], corridor([], sights=[cand]), inp, ctx)
        self.assertEqual([s.place.id for s in d.stops if s.kind is StopKind.SIGHT and s.place], ["s_short"])


if __name__ == "__main__":
    unittest.main()
