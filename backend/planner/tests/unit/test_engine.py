import json
import time
import unittest
from datetime import datetime

from tests.helpers import make_planner, trip
from verst_planner import ENGINE_VERSION, Planner, TripInput, TripPlan
from verst_planner.domain import codec
from verst_planner.domain.enums import StageKey, StopKind
from verst_planner.domain.errors import PlanCancelled, UpstreamUnavailable
from verst_planner.domain.model import UNSET, CostPatch, Crew
from verst_planner.events import CancelToken, ListSink, PlanEvent, StageEvent, StopEvent

G03 = {
    "crew": Crew(2, 1, True, (5,)),
    "destination": "t_volgograd",
    "daily_km": 500,
    "start_at": datetime(2026, 10, 24, 7, 0),
}


def as_json(plan: TripPlan) -> str:
    return json.dumps(codec.plan_to_json(plan, public=False), ensure_ascii=False, sort_keys=True)


class EngineTest(unittest.TestCase):
    def test_public_api(self) -> None:
        self.assertTrue(callable(Planner))
        self.assertIs(TripInput, type(trip()))
        planner, _ = make_planner()
        plan = planner.plan(trip())
        self.assertIsInstance(plan, TripPlan)
        self.assertEqual(plan.engine_version, ENGINE_VERSION)

    def test_event_order(self) -> None:
        planner, _ = make_planner()
        sink = ListSink()
        plan = planner.plan(trip(**G03), sink)
        first = sink.events[0]
        self.assertIsInstance(first, StageEvent)
        assert isinstance(first, StageEvent)
        self.assertEqual((first.key, first.progress), (StageKey.SPLIT, 0.05))
        self.assertEqual(first.text_ru, "Прокладываем дорогу")
        stages = [e for e in sink.events if isinstance(e, StageEvent)]
        progress = [e.progress for e in stages]
        self.assertEqual(progress, sorted(progress))
        self.assertEqual(
            [e.key for e in stages],
            [StageKey.SPLIT, StageKey.SPLIT, StageKey.LODGING, StageKey.FUEL, StageKey.HOURS, StageKey.COST],
        )
        self.assertEqual(stages[1].text_ru, "Делим путь на 2 дня по ≈ 490 км")
        self.assertEqual(stages[2].text_ru, "Ищем отели, куда пустят с собакой")
        self.assertEqual(stages[3].text_ru, "Считаем бензин: 8,0 л на 100 км")
        provisional = [e for e in sink.events if isinstance(e, StopEvent) and e.provisional]
        self.assertEqual([(e.stop_id, e.kind) for e in provisional], [("night1", StopKind.OVERNIGHT)])
        final = [e for e in sink.events if isinstance(e, StopEvent) and not e.provisional]
        stops = [s for d in plan.days_list for s in d.stops]
        self.assertEqual(
            [(e.stop_id, e.kind, e.km_at, e.name_ru) for e in final],
            [(s.id, s.kind, s.km_at, s.name_ru) for s in stops],
        )
        self.assertIs(sink.events[-1], final[-1])

    def test_one_day_trip_has_no_lodging_stage(self) -> None:
        planner, _ = make_planner()
        sink = ListSink()
        plan = planner.plan(trip(destination="t_suzdal", vias=("t_vladimir",)), sink)
        self.assertEqual(plan.days, 1)
        keys = [e.key for e in sink.events if isinstance(e, StageEvent)]
        self.assertNotIn(StageKey.LODGING, keys)
        self.assertFalse(any(isinstance(e, StopEvent) and e.provisional for e in sink.events))

    def test_cancel_before_corridor(self) -> None:
        planner, fakes = make_planner()
        token = CancelToken()

        class CancelOnFirst:
            def emit(self, event: PlanEvent) -> None:
                token.cancel()

        with self.assertRaises(PlanCancelled):
            planner.plan(trip(), CancelOnFirst(), token)
        self.assertEqual(fakes.routing.calls, 1)
        self.assertEqual(fakes.places.calls.get("places_in_corridor", 0), 0)

    def test_cancel_later_stage(self) -> None:
        planner, _ = make_planner()
        token = CancelToken()

        class CancelAtFuel:
            def emit(self, event: PlanEvent) -> None:
                if isinstance(event, StageEvent) and event.key is StageKey.FUEL:
                    token.cancel()

        with self.assertRaises(PlanCancelled):
            planner.plan(trip(**G03), CancelAtFuel(), token)

    def test_upstream_error_propagates(self) -> None:
        planner, fakes = make_planner()
        fakes.routing.fail_with = UpstreamUnavailable("graphhopper")
        with self.assertRaises(UpstreamUnavailable) as cm:
            planner.plan(trip())
        self.assertEqual(cm.exception.code, "UPSTREAM")

    def test_patch_reserve_and_crew(self) -> None:
        planner, _ = make_planner()
        plan = planner.plan(trip(**G03))
        off = planner.recompute_cost(plan, CostPatch(reserve_on=False))
        self.assertEqual(off.days_list, plan.days_list)
        self.assertEqual(off.engine_state, plan.engine_state)
        self.assertFalse(off.cost.reserve_on)
        self.assertLess(off.cost.total_rub, plan.cost.total_rub)
        bigger = planner.recompute_cost(plan, CostPatch(crew=Crew(4, 1, True, (5,)), budget_rub=None))
        self.assertEqual(len(bigger.days_list), len(plan.days_list))
        self.assertEqual(bigger.engine_state, plan.engine_state)
        self.assertGreater(bigger.cost.total_rub, plan.cost.total_rub)
        self.assertIsNone(bigger.cost.budget_rub)
        self.assertEqual(bigger.input.crew.adults, 4)
        same = planner.recompute_cost(plan, CostPatch(budget_rub=UNSET))
        self.assertEqual(same.cost, plan.cost)

    def test_patch_hotel_choice(self) -> None:
        planner, _ = make_planner()
        plan = planner.plan(trip(**G03))
        night = next(s for d in plan.days_list for s in d.stops if s.kind is StopKind.OVERNIGHT)
        other = next(h for h in night.hotel_options if h.place_id != night.selected_hotel_id)
        patched = planner.recompute_cost(plan, CostPatch(hotel_choice=(night.id, other.place_id)))
        n2 = next(s for d in patched.days_list for s in d.stops if s.id == night.id)
        self.assertEqual(n2.selected_hotel_id, other.place_id)
        self.assertEqual(n2.cost_rub, other.price_crew_rub)
        lodging = next(x for x in patched.cost.lines if x.key.value == "lodging")
        self.assertEqual(lodging.rub, other.price_crew_rub)
        from verst_planner.domain.errors import NotFound

        with self.assertRaises(NotFound):
            planner.recompute_cost(plan, CostPatch(hotel_choice=(night.id, "pl_nope")))

    def test_patch_dog_change_rejected(self) -> None:
        from verst_planner.domain.errors import InvalidInput

        planner, _ = make_planner()
        plan = planner.plan(trip(**G03))  # 2 adults + 1 child + dog
        for crew in (Crew(2, 1, False, (5,)), Crew(2, 0, True), Crew(3, 0, True)):
            with self.subTest(crew=crew), self.assertRaises(InvalidInput) as cm:
                planner.recompute_cost(plan, CostPatch(crew=crew))
            self.assertEqual((cm.exception.field, cm.exception.reason), ("crew", "replan_required"))
        planner.recompute_cost(plan, CostPatch(crew=Crew(3, 2, True, (5, 9))))  # 1 → 2 children is fine

    def test_patch_crew_updates_stop_costs(self) -> None:
        planner, _ = make_planner()
        plan = planner.plan(trip(**G03))
        patched = planner.recompute_cost(plan, CostPatch(crew=Crew(4, 1, True, (5,))))
        stops = [s for d in patched.days_list for s in d.stops]
        lines = {x.key.value: x for x in patched.cost.lines}
        night = next(s for s in stops if s.kind is StopKind.OVERNIGHT)
        self.assertEqual(night.cost_rub, lines["lodging"].rub)  # one night: 2 rooms × price
        for h in night.hotel_options:
            self.assertEqual((h.rooms, h.price_crew_rub), (2, 2 * h.price_night_rub))
        food_stops = sum(s.cost_rub for s in stops if s.kind is StopKind.FOOD)
        lunch_units = [m for m in patched.cost.units.meals if m.meal.value == "lunch" and m.stop_id]
        self.assertEqual(food_stops, sum(round(4.5 * m.check_rub / 10 + 1e-9) * 10 for m in lunch_units))
        for s in stops:
            if s.kind is StopKind.SIGHT and s.place_id:
                t = next(x for x in patched.cost.units.tickets if x.stop_id == s.id)
                self.assertEqual(s.cost_rub, round((4 * t.adult_rub + t.child_rub) / 10 + 1e-9) * 10)
        old = {s.id: s.cost_rub for d in plan.days_list for s in d.stops}
        self.assertGreater(sum(s.cost_rub for s in stops), sum(old.values()))

    def test_determinism(self) -> None:
        a, _ = make_planner()
        b, _ = make_planner()
        for kw in (
            {},
            G03,
            {"destination": None, "ready_route_id": "rr_golden_ring", "crew": Crew(2, 1, True)},
        ):
            with self.subTest(case=str(kw)[:40]):
                self.assertEqual(as_json(a.plan(trip(**kw))), as_json(b.plan(trip(**kw))))  # type: ignore[arg-type]

    def test_engine_state_size_1500km(self) -> None:
        # A§16.1 #2 / A§16.9: the server-only EngineState of a 1,500 km trip stays ≤ 400 KB of JSON
        import json

        from verst_planner.domain import codec

        planner, _ = make_planner()
        plan = planner.plan(trip(destination="t_volgograd", round_trip=True, daily_km=600))
        self.assertGreaterEqual(plan.km, 1500)
        size = len(json.dumps(codec.engine_state_to_json(plan.engine_state), ensure_ascii=False).encode())
        self.assertLessEqual(size, 400 * 1024, f"{size} bytes")

    def test_perf_1500km(self) -> None:
        planner, _ = make_planner()
        raw = trip(destination="t_volgograd", round_trip=True, daily_km=600)
        planner.plan(raw)  # warm caches (world indexes are shared)
        t0 = time.perf_counter()
        plan = planner.plan(raw)
        elapsed = time.perf_counter() - t0
        self.assertGreaterEqual(plan.km, 1400)
        self.assertLess(elapsed, 1.0, f"{plan.km} km planned in {elapsed:.3f} s")


if __name__ == "__main__":
    unittest.main()
