import unittest
from datetime import time

from tests.unit.test_rest import ROUTE, day, place_at, setup
from verst_planner.domain.enums import Meal, PlaceType, StopKind, Tag
from verst_planner.domain.model import Candidate, Crew, DayPlan
from verst_planner.geo.index import PolylineIndex
from verst_planner.pipeline import Corridor
from verst_planner.pipeline.meals import plan_meals
from verst_planner.pipeline.timeline import local, schedule_day


def food(pid: str, km: float, tags: set[Tag], rating: float = 4.0, hours: str | None = None) -> Candidate:
    return place_at(
        pid, PlaceType.FOOD, km, tags, rating_internal=rating, avg_check_rub=700, opening_hours=hours
    )


def corridor(foods: list[Candidate]) -> Corridor:
    return Corridor(ROUTE, PolylineIndex(ROUTE), [], sorted(foods, key=lambda c: c.km_at), [], [], [], [])


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


if __name__ == "__main__":
    unittest.main()
