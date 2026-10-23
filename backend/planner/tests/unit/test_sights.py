import unittest
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from tests.helpers import make_ctx, trip
from tests.unit.test_rest import ROUTE, day, place_at
from verst_planner.domain.enums import Mood, PlaceType, StopKind, Tag
from verst_planner.domain.model import Candidate, Crew, DayPlan, NormalizedInput
from verst_planner.geo.index import PolylineIndex
from verst_planner.pipeline import Corridor, PlanContext
from verst_planner.pipeline.resolve import normalize_input
from verst_planner.pipeline.sights import plan_sights, sight_score
from verst_planner.pipeline.timeline import day_duration_min, local, schedule_day

MSK = ZoneInfo("Europe/Moscow")


def sight(
    pid: str,
    km: float,
    rating: float = 4.5,
    dwell: int = 60,
    hours: str | None = None,
    tags: set[Tag] | None = None,
) -> Candidate:
    return place_at(
        pid,
        PlaceType.SIGHT,
        km,
        tags or {Tag.MUSEUM},
        rating_internal=rating,
        dwell_min=dwell,
        opening_hours=hours,
    )


def corridor(sights: list[Candidate]) -> Corridor:
    return Corridor(ROUTE, PolylineIndex(ROUTE), sorted(sights, key=lambda c: c.km_at), [], [], [], [], [])


def setup(
    mood: Mood = Mood.MORE_STOPS, config: dict[str, Any] | None = None, **kw: Any
) -> tuple[PlanContext, NormalizedInput]:
    ctx, _ = make_ctx(config=config)
    return ctx, normalize_input(trip(mood=mood, **kw), ctx)


def sight_ids(d: DayPlan) -> list[str]:
    return [s.place.id for s in d.stops if s.kind is StopKind.SIGHT and s.place]


def monday(d: DayPlan) -> DayPlan:
    d.start_at = datetime(2026, 10, 26, 8, 0, tzinfo=MSK)
    return d


class SightsTest(unittest.TestCase):
    def test_score(self) -> None:
        _ctx, inp = setup(crew=Crew(2, 1, True))
        c = sight("s", 100, 4.0, tags={Tag.WALK, Tag.PLAYGROUND, Tag.VIEW})
        c.detour_min = 15
        self.assertAlmostEqual(sight_score(c, inp), 4.0 + 0.5 + 0.5 + 0.5 + 0.5 - 1.0)

    def test_closed_sight_skipped(self) -> None:
        ctx, inp = setup()
        d = monday(day(300))
        plan_sights(
            [d],
            corridor([sight("s_tusu", 100, 4.9, hours="Tu-Su 09:00-18:00"), sight("s_open", 150, 4.0)]),
            inp,
            ctx,
        )
        self.assertEqual(sight_ids(d), ["s_open"])
        d = day(300)  # Saturday: open
        plan_sights([d], corridor([sight("s_tusu", 100, 4.9, hours="Tu-Su 09:00-18:00")]), inp, ctx)
        self.assertEqual(sight_ids(d), ["s_tusu"])

    def test_visit_must_fit_hours(self) -> None:
        # no rest reserve here (R = 900): this test is about opening hours only
        ctx, inp = setup(
            config={"day_budget_min": {"more_stops": 900}, "rest_interval_min": {"more_stops": 900}}
        )
        d = day(600)
        # 08:00 + 510 min = 16:30; closes 17:00; dwell 60 → the visit would end at 17:30
        plan_sights([d], corridor([sight("s_late", 510, hours="Mo-Su 09:00-17:00")]), inp, ctx)
        self.assertEqual(sight_ids(d), [])
        plan_sights([d], corridor([sight("s_short", 510, dwell=30, hours="Mo-Su 09:00-17:00")]), inp, ctx)
        self.assertEqual(sight_ids(d), ["s_short"])

    def test_budget_respected(self) -> None:
        ctx, inp = setup(Mood.CALM)
        d = day(420)  # 420 min of driving; calm budget 540
        plan_sights(
            [d],
            corridor(
                [
                    sight("a", 100, 4.9, dwell=90),
                    sight("b", 200, 4.8, dwell=60),
                    sight("c", 300, 4.7, dwell=45),
                ]
            ),
            inp,
            ctx,
        )
        duration = day_duration_min(d, schedule_day(d, ctx.profile_for(ROUTE)))
        self.assertLessEqual(duration, 540)
        self.assertEqual(
            sight_ids(d), ["a"]
        )  # best first: 420 + 90 = 510; then b (570) and c (555) do not fit

    def test_just_drive_no_sights(self) -> None:
        ctx, inp = setup(Mood.JUST_DRIVE)
        d = day(300)
        plan_sights([d], corridor([sight("a", 100, 5.0)]), inp, ctx)
        self.assertEqual(sight_ids(d), [])

    def test_simplify_no_sights(self) -> None:
        ctx, inp = setup(simplify=True)
        d = day(300)
        plan_sights([d], corridor([sight("a", 100, 5.0)]), inp, ctx)
        self.assertEqual(sight_ids(d), [])

    def test_max_per_day(self) -> None:
        for mood, n in ((Mood.CALM, 2), (Mood.MORE_STOPS, 4)):
            with self.subTest(mood=mood.value):
                ctx, inp = setup(mood, config={"day_budget_min": {"calm": 2000, "more_stops": 2000}})
                d = day(300)
                plan_sights(
                    [d],
                    corridor([sight(f"s{k}", 20 * k, 4.0 + k / 100, dwell=30) for k in range(1, 9)]),
                    inp,
                    ctx,
                )
                self.assertEqual(len(sight_ids(d)), n)
                self.assertEqual(sight_ids(d)[-1], "s8")  # best scores first

    def test_min_score_and_frozen(self) -> None:
        ctx, inp = setup()
        d = day(300)
        plan_sights([d], corridor([sight("low", 100, 1.0, tags={Tag.WC})]), inp, ctx)  # 1.0 + 0.5 < 2.0
        self.assertEqual(sight_ids(d), [])
        plan_sights([d], corridor([sight("a", 100, 5.0)]), inp, ctx, frozen=True)
        self.assertEqual(sight_ids(d), [])

    def test_reason_dog_waits(self) -> None:
        ctx, inp = setup(crew=Crew(2, 0, True))
        d = day(300)
        plan_sights([d], corridor([sight("a", 100, 5.0, dwell=90)]), inp, ctx)
        s = next(x for x in d.stops if x.kind is StopKind.SIGHT)
        self.assertEqual((s.reason_key, s.reason_params), ("sight.dog_waits", {"dwell": "полтора часа"}))
        self.assertEqual(
            ctx.templates.render(s.reason_key, **s.reason_params),
            "Полтора часа на осмотр. Собака ждёт с одним из взрослых.",
        )
        slot = schedule_day(d, ctx.profile_for(ROUTE))[1]
        assert slot.arrive is not None
        self.assertEqual(local(slot.arrive, "Europe/Moscow"), datetime(2026, 10, 24, 9, 40))


if __name__ == "__main__":
    unittest.main()
