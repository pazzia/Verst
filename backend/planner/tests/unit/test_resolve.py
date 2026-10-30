import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.helpers import make_ctx, trip
from verst_planner.domain.enums import Mood, StopKind
from verst_planner.domain.errors import InvalidInput, NotFound, TooShort, Unreachable
from verst_planner.domain.model import Crew, LatLon, PointInput, TripInput
from verst_planner.pipeline.base_route import build_base_route, toll_warnings
from verst_planner.pipeline.resolve import next_saturday, normalize_input, resolve_points

MSK = ZoneInfo("Europe/Moscow")


class NormalizeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx, self.fakes = make_ctx()

    def test_default_start_next_saturday(self) -> None:
        inp = normalize_input(trip(start_at=None), self.ctx)  # clock: Fri 2026-10-23 09:00 MSK
        self.assertEqual(inp.start_at, datetime(2026, 10, 24, 8, 0, tzinfo=MSK))
        self.assertEqual(inp.tz, "Europe/Moscow")
        sat = datetime(2026, 10, 24, 10, 0, tzinfo=MSK)
        self.assertEqual(next_saturday(sat).date().isoformat(), "2026-10-31")  # strictly after today

    def test_default_mood(self) -> None:
        self.assertEqual(normalize_input(trip(crew=Crew(2, 1, False)), self.ctx).mood, Mood.CALM)
        self.assertEqual(normalize_input(trip(crew=Crew(2, 0, True)), self.ctx).mood, Mood.MORE_STOPS)
        explicit = trip(crew=Crew(2, 1, False), mood=Mood.JUST_DRIVE)
        self.assertEqual(normalize_input(explicit, self.ctx).mood, Mood.JUST_DRIVE)

    def test_ready_route_defaults_round_trip(self) -> None:
        rr = trip(destination=None, ready_route_id="rr_golden_ring")
        self.assertTrue(normalize_input(rr, self.ctx).round_trip)
        self.assertFalse(normalize_input(trip(), self.ctx).round_trip)
        ctx2, _ = make_ctx()
        self.assertFalse(
            normalize_input(
                trip(destination=None, ready_route_id="rr_golden_ring", round_trip=False), ctx2
            ).round_trip
        )
        with self.assertRaises(NotFound):
            normalize_input(trip(destination=None, ready_route_id="rr_nope"), make_ctx()[0])

    def test_outside_russia_invalid(self) -> None:
        paris = TripInput(
            origin=PointInput(LatLon(48.85, 2.35), "Париж"),
            destination=trip().destination,
            crew=Crew(2, 0, False),
            daily_km=300,
        )
        with self.assertRaises(InvalidInput) as cm:
            normalize_input(paris, self.ctx)
        self.assertEqual((cm.exception.field, cm.exception.reason), ("origin", "outside_russia"))
        chukotka = TripInput(
            origin=trip().origin,
            destination=PointInput(LatLon(65.0, -172.0)),
            crew=Crew(2, 0, False),
            daily_km=300,
        )
        normalize_input(chukotka, self.ctx)  # across the antimeridian is still Russia

    def test_daily_km_step(self) -> None:
        for bad in (100, 149, 325, 950):
            with self.subTest(daily=bad), self.assertRaises(InvalidInput) as cm:
                normalize_input(trip(daily_km=bad), self.ctx)
            self.assertEqual(cm.exception.field, "dailyKm")
        for good in (150, 300, 900):
            self.assertEqual(normalize_input(trip(daily_km=good), self.ctx).daily_km, good)

    def test_other_validation(self) -> None:
        cases = {
            "destination": trip(destination=None),
            "vias": trip(vias=("t_pushkino", "t_sergiev_posad", "t_pereslavl", "t_rostov")),
            "budget": trip(budget_rub=500),
            "startAt": trip(start_at=datetime(2028, 1, 1, 8, 0)),
            "crew": trip(crew=Crew(4, 5, False)),
        }
        for field, raw in cases.items():
            with self.subTest(field=field), self.assertRaises(InvalidInput) as cm:
                normalize_input(raw, self.ctx)
            self.assertEqual(cm.exception.field, field)
        both = trip(ready_route_id="rr_golden_ring")
        with self.assertRaises(InvalidInput) as cm:
            normalize_input(both, self.ctx)
        self.assertEqual(cm.exception.reason, "conflicts_with_ready_route")


class ResolveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx, self.fakes = make_ctx()

    def test_round_trip_appends_origin(self) -> None:
        inp = normalize_input(trip(round_trip=True), self.ctx)
        pts = resolve_points(inp, self.ctx)
        self.assertEqual(len(pts.points), 3)
        self.assertEqual(pts.points[0], pts.points[-1])
        self.assertEqual(pts.labels, ("Москва", "Ярославль", "Москва"))

    def test_vias_in_order_and_labels(self) -> None:
        raw = trip(destination="t_suzdal", vias=("t_vladimir",))
        unlabeled = TripInput(
            origin=PointInput(LatLon(56.33, 44.01)),
            destination=raw.destination,
            vias=raw.vias,
            crew=raw.crew,
            daily_km=300,
            start_at=raw.start_at,
        )
        pts = resolve_points(normalize_input(unlabeled, self.ctx), self.ctx)
        self.assertEqual(pts.labels, ("Нижний Новгород", "Владимир", "Суздаль"))
        middle_of_nowhere = TripInput(
            origin=PointInput(LatLon(60.5, 60.5)),
            destination=raw.destination,
            crew=raw.crew,
            daily_km=300,
            start_at=raw.start_at,
        )
        self.assertEqual(
            resolve_points(normalize_input(middle_of_nowhere, self.ctx), self.ctx).labels[0], "Точка на карте"
        )

    def test_ready_route_points(self) -> None:
        inp = normalize_input(trip(destination=None, ready_route_id="rr_golden_ring"), self.ctx)
        pts = resolve_points(inp, self.ctx)
        self.assertEqual(len(pts.points), 1 + 8 + 1)
        self.assertEqual(pts.labels[1], "Сергиев Посад")
        self.assertEqual([s.place.id for s in pts.fixed_stops if s.place], ["pl_sps_lavra", "pl_kos_ipatiev"])
        self.assertTrue(all(s.fixed and s.kind is StopKind.SIGHT for s in pts.fixed_stops))
        self.assertEqual(pts.fixed_after, [1, 4])  # after via Сергиев Посад and via Ярославль
        self.assertEqual(pts.fixed_stops[0].dwell_min, 90)

    def test_template_vias_are_not_stops(self) -> None:
        # A§16.3 (D-21): the 8 via towns of the Golden Ring route the car but produce no VIA stop/row
        from tests.helpers import make_planner

        planner, _ = make_planner()
        plan = planner.plan(trip(destination=None, ready_route_id="rr_golden_ring"))
        kinds = [s.kind for d in plan.days_list for s in d.stops]
        self.assertNotIn(StopKind.VIA, kinds)
        self.assertIn("pl_sps_lavra", {s.place_id for d in plan.days_list for s in d.stops})
        # a user via still is a stop
        plan = planner.plan(trip(destination="t_suzdal", vias=("t_vladimir",)))
        vias = [s for d in plan.days_list for s in d.stops if s.kind is StopKind.VIA]
        self.assertEqual([v.name_ru for v in vias], ["Владимир"])


class BaseRouteTest(unittest.TestCase):
    def test_route_and_tolls_warning(self) -> None:
        ctx, fakes = make_ctx()
        inp = normalize_input(trip(destination="t_kazan", avoid_tolls=True), ctx)
        route = build_base_route(resolve_points(inp, ctx), inp, ctx)
        self.assertAlmostEqual(route.km_total, 814, delta=1)
        self.assertEqual(toll_warnings(route, inp, ctx), [])
        self.assertEqual(fakes.routing.calls, 1)

    def test_too_short(self) -> None:
        ctx, _ = make_ctx("edge_cases_v1")
        inp = normalize_input(trip("t_tst_testovsk", "t_tst_blizhny", world="edge_cases_v1"), ctx)
        with self.assertRaises(TooShort) as cm:
            build_base_route(resolve_points(inp, ctx), inp, ctx)
        self.assertAlmostEqual(cm.exception.road_km, 12, delta=0.5)
        # a 12 km round trip (24 km) is still below 2 × 20 km
        inp = normalize_input(
            trip("t_tst_testovsk", "t_tst_blizhny", world="edge_cases_v1", round_trip=True), ctx
        )
        with self.assertRaises(TooShort):
            build_base_route(resolve_points(inp, ctx), inp, ctx)

    def test_unreachable_rechecked(self) -> None:
        ctx, fakes = make_ctx("edge_cases_v1")
        inp = normalize_input(trip("t_tst_testovsk", "t_tst_glukhovo", world="edge_cases_v1"), ctx)
        with self.assertRaises(Unreachable) as cm:
            build_base_route(resolve_points(inp, ctx), inp, ctx)
        self.assertEqual(cm.exception.point_index, 1)
        fakes.routing.snap_max_km = 5.0  # a service that snaps anything: the planner re-check still fails
        with self.assertRaises(Unreachable) as cm:
            build_base_route(resolve_points(inp, ctx), inp, ctx)
        self.assertEqual(cm.exception.point_index, 1)
        self.assertAlmostEqual(cm.exception.snap_km or 0, 2.5, delta=0.05)


if __name__ == "__main__":
    unittest.main()
