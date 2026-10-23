import unittest
from datetime import datetime

from tests.helpers import make_ctx, make_town, sample_normalized, trip
from verst_planner.domain.enums import OvernightFallback, StopKind
from verst_planner.domain.model import Crew, LatLon, OvernightChoice, PlannedStop, ScoredTown
from verst_planner.explain.reasons import overnight_reason, stop_reason
from verst_planner.pipeline import fuel as fuel_stage
from verst_planner.pipeline.base_route import build_base_route
from verst_planner.pipeline.corridor import build_corridor, place_fixed
from verst_planner.pipeline.day_split import split_days
from verst_planner.pipeline.meals import plan_meals
from verst_planner.pipeline.overnight import choose_overnights
from verst_planner.pipeline.resolve import normalize_input, resolve_points
from verst_planner.pipeline.rest import plan_rests
from verst_planner.pipeline.schedule import schedule_with_rerun
from verst_planner.pipeline.sights import plan_sights
from verst_planner.pipeline.timeline import build_day_plans, local_minute

YAR = make_town("t_yaroslavl", 57.6261, 39.8845, name_ru="Ярославль", name_prep_ru="Ярославле")
RST = make_town("t_rostov", 57.1853, 39.4146, name_ru="Ростов", name_prep_ru="Ростове")
HOTEL = object()


def choice(
    pick: ScoredTown,
    others: list[ScoredTown],
    target: float,
    fallback: OvernightFallback = OvernightFallback.NONE,
    hotel: bool = True,
) -> OvernightChoice:
    from tests.helpers import make_place
    from verst_planner.domain.enums import PlaceType, RoadClass
    from verst_planner.domain.model import Candidate

    h = (
        Candidate(
            make_place("h", PlaceType.LODGING, price_night_rub=6000),
            pick.km_at,
            0.5,
            1.3,
            4,
            RoadClass.TRUNK,
            "RU-YAR",
        )
        if hotel
        else None
    )
    return OvernightChoice(
        1,
        pick.km_at,
        pick.town,
        pick.town.point,
        pick.town.name_ru,
        h,
        [h] if h else [],
        [*others, pick],
        fallback,
        pick.score,
        target,
    )


class ReasonsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx, _ = make_ctx()
        self.t = self.ctx.templates
        self.cfg = self.ctx.cfg

    def inp(self, crew: Crew) -> object:
        return normalize_input(trip(crew=crew), self.ctx)

    def test_overnight_shift_hotels_text(self) -> None:
        pick = ScoredTown(YAR, 259.0, 20.0, 4.0, 3, 1, 4)
        other = ScoredTown(RST, 204.0, 12.0, 1.0, 3, 1, 3)
        res = overnight_reason(
            choice(pick, [other], 210.0),
            259,
            self.inp(Crew(2, 0, True)),
            self.cfg,  # type: ignore[arg-type]
            self.t,
        )
        self.assertEqual(
            res.text,
            "Не в Ростове, а на 55 км дальше: здесь больше отелей, куда пускают с собакой. "
            "Ваши 300 км в день не превышены.",
        )
        self.assertEqual(res.candidates, ("Ростов", "Ярославль"))

    def test_shift_quality_earlier_and_no_cap(self) -> None:
        pick = ScoredTown(RST, 204.0, 20.0, 2.0, 3, 0, 4)
        other = ScoredTown(YAR, 259.0, 12.0, 2.0, 1, 0, 3)
        res = overnight_reason(
            choice(pick, [other], 250.0),
            320,
            self.inp(Crew(2, 0, False)),
            self.cfg,  # type: ignore[arg-type]
            self.t,
        )
        self.assertEqual(res.text, "Не в Ярославле, а на 55 км раньше: город интереснее для вечера и утра.")

    def test_on_target(self) -> None:
        pick = ScoredTown(YAR, 263.0, 20.0, 4.0, 3, 1, 4)
        other = ScoredTown(RST, 256.0, 12.0, 1.0, 3, 1, 3)
        res = overnight_reason(
            choice(pick, [other], 260.0),
            263,
            self.inp(Crew(2, 0, False)),
            self.cfg,  # type: ignore[arg-type]
            self.t,
        )
        self.assertEqual(res.text, "Как раз на вашей дневной норме. Ваши 300 км в день не превышены.")
        alone = overnight_reason(choice(pick, [], 265.0), 263, self.inp(Crew(2, 0, False)), self.cfg, self.t)  # type: ignore[arg-type]
        self.assertTrue(alone.text.startswith("Как раз на вашей дневной норме."))

    def test_limit_distance_to_daily_cap(self) -> None:
        # A§16.8: no other town considered and the pick is before the target → distance to the user's
        # limit (day start + daily km), not to the even-split target. G03: Тамбов at km 467 on a 500-km day.
        tam = make_town("t_tambov", 52.72, 41.45, name_ru="Тамбов", name_prep_ru="Тамбове")
        pick = ScoredTown(tam, 467.0, 20.0, 4.0, 2, 1, 3)
        c = choice(pick, [], 490.0)
        c.day_start_km = 0.0
        inp = normalize_input(trip(crew=Crew(2, 1, True), daily_km=500), self.ctx)
        res = overnight_reason(c, 473, inp, self.cfg, self.t)  # type: ignore[arg-type]
        self.assertEqual(
            res.text,
            "На 33 км раньше вашего предела: здесь больше отелей, куда пускают с собакой. "
            "Ваши 500 км в день не превышены.",
        )
        c.day_start_km = 100.0  # a later day: the limit is km 600
        res = overnight_reason(c, 367, inp, self.cfg, self.t)  # type: ignore[arg-type]
        self.assertTrue(res.text.startswith("На 133 км раньше вашего предела"))

    def test_no_hotel_text(self) -> None:
        pick = ScoredTown(RST, 300.0, 5.0, 0.0, 1, 0, 0)
        c = choice(pick, [], 300.0, OvernightFallback.NO_HOTEL, hotel=False)
        res = overnight_reason(c, 300, self.inp(Crew(2, 0, True)), self.cfg, self.t)  # type: ignore[arg-type]
        self.assertTrue(
            res.text.startswith(
                "Не нашли отель с вашими условиями — заложили среднюю цену, уточните при бронировании."
            )
        )

    def test_widened_and_template(self) -> None:
        pick = ScoredTown(RST, 220.0, 5.0, 1.0, 1, 0, 0)
        res = overnight_reason(
            choice(pick, [], 300.0, OvernightFallback.WIDENED),
            220,
            self.inp(Crew(2, 0, True)),  # type: ignore[arg-type]
            self.cfg,
            self.t,
        )
        self.assertTrue(
            res.text.startswith("Ночёвку с вашими условиями нашли только на 80 км раньше цели дня.")
        )
        tpl = overnight_reason(
            choice(pick, [], 220.0, OvernightFallback.TEMPLATE),
            220,
            self.inp(Crew(2, 0, True)),
            self.cfg,
            self.t,
            "Золотое кольцо",
        )  # type: ignore[arg-type]
        self.assertTrue(tpl.text.startswith("Ночёвка из готового маршрута «Золотое кольцо»."))

    def test_user_via_reason(self) -> None:
        from tests.helpers import make_planner
        from verst_planner.domain.enums import SignType

        planner, _ = make_planner()
        plan = planner.plan(trip(destination="t_suzdal", vias=("t_vladimir",)))
        via = next(s for d in plan.days_list for s in d.stops if s.kind is StopKind.VIA)
        self.assertEqual(via.reason_ru, "Заезд по вашей просьбе.")
        self.assertEqual(self.t.raw("via.user"), "Заезд по вашей просьбе.")
        self.assertEqual((via.dwell_min, via.sign, via.replaceable), (30, SignType.CITY, False))
        self.assertEqual(via.alternatives, ())

    def test_start_finish_reasons(self) -> None:
        inp = sample_normalized()
        p = LatLon(55.75, 37.61)
        start = PlannedStop(StopKind.START, 0, "Москва", p)
        finish = PlannedStop(StopKind.FINISH, 526, "Москва", p)
        self.assertEqual(
            stop_reason(start, inp, self.cfg, self.t, datetime(2026, 10, 24, 8, 0), False), "Выезд в 08:00."
        )
        self.assertEqual(
            stop_reason(finish, inp, self.cfg, self.t, datetime(2026, 10, 25, 18, 5), True), "Дома к вечеру."
        )
        self.assertEqual(
            stop_reason(finish, inp, self.cfg, self.t, datetime(2026, 10, 25, 18, 5), False), "Финиш."
        )

    def test_every_auto_stop_has_reason(self) -> None:
        for raw in (
            trip(round_trip=True),
            trip(crew=Crew(2, 1, True), destination="t_volgograd", daily_km=500),
            trip(destination="t_kazan", daily_km=900, crew=Crew(1, 0, False)),
        ):
            ctx, _ = make_ctx()
            inp = normalize_input(raw, ctx)
            pts = resolve_points(inp, ctx)
            route = build_base_route(pts, inp, ctx)
            cor = build_corridor(route, inp, ctx)
            nights = choose_overnights(split_days(route, cor, inp, None, ctx), cor, inp, ctx)
            profile = ctx.profile_for(route)
            days = build_day_plans(
                route, nights.choices, place_fixed(pts, cor, inp, ctx), inp, ctx, pts, profile
            )
            fuel_stage.plan_fuel(days, cor, inp, ctx)
            plan_rests(days, cor, inp, ctx)
            plan_meals(days, cor, inp, ctx)
            plan_sights(days, cor, inp, ctx)
            sched, _ = schedule_with_rerun(days, cor, inp, ctx)
            autos = 0
            for sd in sched:
                for s, slot in zip(sd.plan.stops, sd.slots, strict=True):
                    if s.kind is StopKind.OVERNIGHT:
                        continue
                    at = slot.depart if s.kind is StopKind.START else slot.arrive
                    assert at is not None
                    text = stop_reason(
                        s, inp, ctx.cfg, ctx.templates, local_minute(at, sd.plan.tz), inp.round_trip
                    )
                    if s.auto or s.kind is StopKind.SIGHT:
                        autos += 1
                        with self.subTest(stop=s.name_ru):
                            self.assertTrue(text)
                            self.assertEqual(text[0], text[0].upper())
                            self.assertNotIn("{", text)
            self.assertGreater(autos, 0)


if __name__ == "__main__":
    unittest.main()
