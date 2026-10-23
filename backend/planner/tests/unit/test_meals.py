import unittest
from datetime import time

from tests.unit.test_rest import ROUTE, day, place_at, setup
from tests.unit.test_sights import sight, sight_ids
from verst_planner.domain.enums import Meal, Mood, PlaceType, StopKind, Tag
from verst_planner.domain.model import Candidate, Crew, DayPlan, NormalizedInput
from verst_planner.geo.index import PolylineIndex
from verst_planner.pipeline import Corridor, PlanContext
from verst_planner.pipeline.meals import plan_meals
from verst_planner.pipeline.sights import plan_lunch_after_sights, plan_lunches, plan_sights
from verst_planner.pipeline.timeline import local, schedule_day


def food(pid: str, km: float, tags: set[Tag], rating: float = 4.0, hours: str | None = None) -> Candidate:
    return place_at(
        pid, PlaceType.FOOD, km, tags, rating_internal=rating, avg_check_rub=700, opening_hours=hours
    )


def corridor(foods: list[Candidate], sights: list[Candidate] | None = None) -> Corridor:
    return Corridor(
        ROUTE,
        PolylineIndex(ROUTE),
        sorted(sights or [], key=lambda c: c.km_at),
        sorted(foods, key=lambda c: c.km_at),
        [],
        [],
        [],
        [],
    )


def stage_8_9_8b(d: DayPlan, cor: Corridor, inp: NormalizedInput, ctx: PlanContext) -> None:
    plan_lunches([d], cor, inp, ctx)
    plan_sights([d], cor, inp, ctx)
    plan_lunch_after_sights([d], cor, inp, ctx)


def lunches(d: DayPlan) -> list[str]:
    return [s.place.id for s in d.stops if s.meal is Meal.LUNCH and s.place]


class MealsTest(unittest.TestCase):
    def test_lunch_in_window(self) -> None:
        ctx, inp = setup()
        # 08:00 start, 1 driving minute per km: km 200 = 11:20, km 260 = 12:20, km 450 = 15:30
        d = day(500)
        plan_meals(
            [d],
            corridor(
                [food("f200", 200, set(), 4.9), food("f260", 260, set()), food("f450", 450, set(), 4.9)]
            ),
            inp,
            ctx,
        )
        self.assertEqual(lunches(d), ["f260"])
        stop = next(s for s in d.stops if s.meal is Meal.LUNCH)
        self.assertEqual((stop.kind, stop.dwell_min, stop.auto), (StopKind.FOOD, 60, True))
        slot = schedule_day(d, ctx.profile_for(ROUTE))[d.stops.index(stop)]
        assert slot.arrive is not None
        arrive = local(slot.arrive, "Europe/Moscow").time()
        self.assertTrue(time(12, 0) <= arrive <= time(14, 30))
        self.assertEqual(stop.reason_key, "lunch.default")

    def test_kids_menu_preferred(self) -> None:
        cands = [food("f_plain", 300, {Tag.VIEW}, 4.6), food("f_kids", 280, {Tag.KIDS_MENU}, 4.0)]
        ctx, inp = setup(crew=Crew(2, 1, False))
        d = day(500)
        plan_meals([d], corridor(cands), inp, ctx)
        self.assertEqual(lunches(d), ["f_kids"])  # 4.0 + 2 + 0.5 > 4.6 + 0.5 + 0.5
        self.assertEqual(next(s for s in d.stops if s.meal).reason_key, "lunch.kids")
        ctx, inp = setup(crew=Crew(2, 0, False))
        d = day(500)
        plan_meals([d], corridor(cands), inp, ctx)
        self.assertEqual(lunches(d), ["f_plain"])

    def test_no_lunch_when_day_outside_window(self) -> None:
        ctx, inp = setup()
        d = day(210)  # ends at 11:30
        plan_meals([d], corridor([food("f100", 100, set()), food("f200", 200, set())]), inp, ctx)
        self.assertEqual(lunches(d), [])

    def test_hours_must_cover_the_meal(self) -> None:
        ctx, inp = setup()
        d = day(500)
        closing = food("f_close", 300, {Tag.PARKING}, 5.0, hours="Mo-Su 10:00-13:30")  # 13:00 + 60 > 13:30
        plan_meals([d], corridor([closing, food("f_ok", 320, set())]), inp, ctx)
        self.assertEqual(lunches(d), ["f_ok"])

    def test_parking_reason(self) -> None:
        ctx, inp = setup()
        d = day(500)
        plan_meals([d], corridor([food("f_park", 300, {Tag.PARKING_GUARDED})]), inp, ctx)
        self.assertEqual(next(s for s in d.stops if s.meal).reason_key, "lunch.parking")


NO_RESTS = {"rest_interval_min": {"calm": 900}}  # keep the minute arithmetic free of rest breaks


class LunchAfterSightsTest(unittest.TestCase):
    """Stage 8b (A§16.2, D-18)."""

    def test_lunch_after_sights_shift(self) -> None:
        # 200 km from 08:00 ends at 11:20: stage 8 plans no lunch. The 2-hour sight at km 50 moves the end
        # to 13:20, so stage 8b plans one: the café at km 190 is reached at 08:00 + 190 + 120 = 13:10.
        ctx, inp = setup()
        cor = corridor([food("f190", 190, set())], sights=[sight("s050", 50, dwell=120)])
        d = day(200)
        plan_lunches([d], cor, inp, ctx)
        self.assertEqual(lunches(d), [])
        plan_sights([d], cor, inp, ctx)
        self.assertEqual([s.place.id for s in d.stops if s.kind is StopKind.SIGHT and s.place], ["s050"])
        plan_lunch_after_sights([d], cor, inp, ctx)
        self.assertEqual(lunches(d), ["f190"])
        lunch = next(s for s in d.stops if s.meal is Meal.LUNCH)
        self.assertEqual(lunch.pool, "food")

    def test_sight_dropped_for_lunch(self) -> None:
        # calm (budget 540): 300 min of driving + sights A (km 50, 2 h, 4.9) and B (km 100, 2 h, 4.5) = 540.
        # Stage 8 finds no lunch (the café at km 140 is reached at 10:20). With A and B the café is reached at
        # 14:20, but 540 + 60 > max(540, mandatory 360): B (lower score) is dropped, A stays, lunch at 12:20.
        ctx, inp = setup(mood=Mood.CALM, config=NO_RESTS)
        cor = corridor(
            [food("f140", 140, set())],
            sights=[sight("A", 50, rating=4.9, dwell=120), sight("B", 100, rating=4.5, dwell=120)],
        )
        d = day(300)
        plan_lunches([d], cor, inp, ctx)
        self.assertEqual(lunches(d), [])
        plan_sights([d], cor, inp, ctx)
        self.assertEqual(sight_ids(d), ["A", "B"])
        plan_lunch_after_sights([d], cor, inp, ctx)
        self.assertEqual((sight_ids(d), lunches(d)), (["A"], ["f140"]))
        slot = schedule_day(d, ctx.profile_for(ROUTE))[next(i for i, s in enumerate(d.stops) if s.meal)]
        assert slot.arrive is not None
        self.assertEqual(local(slot.arrive, "Europe/Moscow").time(), time(12, 20))
        # no feasible food place at all: the sights are kept and no lunch is planned
        ctx, inp = setup(mood=Mood.CALM, config=NO_RESTS)
        cor = corridor(
            [food("f010", 10, set())], sights=[sight("A", 50, dwell=120), sight("B", 100, dwell=120)]
        )
        d = day(300)
        stage_8_9_8b(d, cor, inp, ctx)
        self.assertEqual((sight_ids(d), lunches(d)), (["A", "B"], []))


if __name__ == "__main__":
    unittest.main()
