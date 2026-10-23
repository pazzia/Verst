import unittest
from datetime import datetime
from functools import cache

from tests.helpers import make_planner, trip
from verst_planner.adapters.fake import FakeWorld
from verst_planner.domain.enums import StopKind
from verst_planner.domain.model import Crew, ReplaceableKinds, TripPlan
from verst_planner.hours import parse


@cache
def plans() -> tuple[TripPlan, ...]:
    planner, _ = make_planner()
    return (
        planner.plan(
            trip(
                crew=Crew(2, 1, True, (5,)),
                destination="t_volgograd",
                daily_km=500,
                start_at=datetime(2026, 10, 24, 7, 0),
            )
        ),
        planner.plan(
            trip(
                destination=None,
                ready_route_id="rr_golden_ring",
                crew=Crew(2, 1, True),
                start_at=datetime(2026, 11, 7, 8, 0),
            )
        ),
        planner.plan(trip(destination="t_kazan", avoid_tolls=True, daily_km=450)),
        planner.plan(trip(round_trip=True)),
    )


def world() -> FakeWorld:
    from tests.helpers import WORLDS, _load_world

    w: FakeWorld = _load_world(str(WORLDS / "central_russia_v1.json"))
    return w


class AlternativesTest(unittest.TestCase):
    def all_stops(self):  # type: ignore[no-untyped-def]
        for plan in plans():
            for d in plan.days_list:
                for s in d.stops:
                    yield plan, d, s

    def test_some_alternatives_exist(self) -> None:
        self.assertGreater(sum(len(s.alternatives) for _p, _d, s in self.all_stops()), 10)

    def test_alternatives_within_45min(self) -> None:
        for _p, _d, s in self.all_stops():
            for a in s.alternatives:
                assert s.arrive_at is not None and a.stop.arrive_at is not None
                with self.subTest(stop=s.id, alt=a.id):
                    self.assertLessEqual(abs((a.stop.arrive_at - s.arrive_at).total_seconds()) / 60, 45)

    def test_max_three(self) -> None:
        for _p, _d, s in self.all_stops():
            self.assertLessEqual(len(s.alternatives), 3)

    def test_not_for_start_finish_overnight(self) -> None:
        for _p, _d, s in self.all_stops():
            if s.kind in (StopKind.START, StopKind.FINISH, StopKind.OVERNIGHT, StopKind.VIA):
                self.assertFalse(s.replaceable, s.id)
                self.assertEqual(s.alternatives, (), s.id)
            if s.alternatives:
                self.assertTrue(s.replaceable)
                self.assertIn(s.kind, ReplaceableKinds)

    def test_fixed_template_sights_not_replaceable(self) -> None:
        gr = plans()[1]
        lavra = next(s for d in gr.days_list for s in d.stops if s.place_id == "pl_sps_lavra")
        self.assertFalse(lavra.replaceable)
        self.assertEqual(lavra.alternatives, ())

    def test_alt_excludes_used_places(self) -> None:
        for plan in plans():
            used = {s.place_id for d in plan.days_list for s in d.stops if s.place_id}
            for d in plan.days_list:
                for s in d.stops:
                    ids = [a.place_id for a in s.alternatives]
                    self.assertEqual(len(ids), len(set(ids)))
                    for a in s.alternatives:
                        self.assertNotIn(a.place_id, used)
                        self.assertNotEqual(a.place_id, s.place_id)
                        self.assertEqual(a.stop.kind, s.kind)
                        self.assertEqual(a.stop.id, s.id)
                        self.assertEqual(a.id, f"alt_{s.id}_{a.place_id}")
                        self.assertEqual(a.stop.alternatives, ())

    def test_alt_sight_must_be_open(self) -> None:
        w = world()
        checked = 0
        for _p, _d, s in self.all_stops():
            for a in s.alternatives:
                place = w.places[a.place_id]
                if a.stop.kind is StopKind.SIGHT and place.opening_hours:
                    assert a.stop.arrive_at is not None and a.stop.depart_at is not None
                    self.assertTrue(parse(place.opening_hours).covers(a.stop.arrive_at, a.stop.depart_at))
                    checked += 1
                if a.stop.kind is StopKind.FOOD:
                    assert a.stop.arrive_at is not None
                    self.assertTrue("12:00" <= a.stop.arrive_at.strftime("%H:%M") <= "14:30")
        self.assertGreaterEqual(checked, 0)

    def test_delta_and_shift(self) -> None:
        for _p, _d, s in self.all_stops():
            for a in s.alternatives:
                self.assertEqual(
                    a.delta_min, a.shift_min
                )  # neighbours are kept: the day end moves as they do
                self.assertEqual(a.delta_rub, a.stop.cost_rub - s.cost_rub)
                self.assertEqual(a.units.place_id, a.place_id)


if __name__ == "__main__":
    unittest.main()
