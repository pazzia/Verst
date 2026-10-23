import json
import unittest
from datetime import datetime, timedelta

from tests.helpers import make_planner, trip
from verst_planner.domain import codec
from verst_planner.domain.errors import NotFound
from verst_planner.domain.model import Crew, ScheduledStop, TripPlan


def first_with_alternatives(plan: TripPlan) -> tuple[int, ScheduledStop]:
    for di, d in enumerate(plan.days_list):
        for s in d.stops:
            if s.alternatives:
                return di, s
    raise AssertionError("no stop with alternatives")


def dump(x: object) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


class ReplaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.planner, self.fakes = make_planner()
        self.plan = self.planner.plan(
            trip(
                crew=Crew(2, 1, True, (5,)),
                destination="t_volgograd",
                daily_km=500,
                start_at=datetime(2026, 10, 24, 7, 0),
            )
        )

    def test_replace_updates_only_that_day(self) -> None:
        di, stop = first_with_alternatives(self.plan)
        alt = stop.alternatives[0]
        new = self.planner.replace_stop(self.plan, stop.id, alt.id)
        old_json = codec.plan_to_json(self.plan)
        new_json = codec.plan_to_json(new)
        for k, (a, b) in enumerate(zip(old_json["daysList"], new_json["daysList"], strict=True)):
            if k != di:
                self.assertEqual(dump(a), dump(b))
        changed = next(s for s in new.days_list[di].stops if s.id == stop.id)
        self.assertEqual(changed.place_id, alt.place_id)
        self.assertEqual(changed.name_ru, alt.name_ru)
        self.assertNotIn(alt.place_id, [a.place_id for a in changed.alternatives])
        self.assertIn(stop.place_id, [a.place_id for a in changed.alternatives] + [stop.place_id])
        self.assertEqual(len(new.days_list[di].stops), len(self.plan.days_list[di].stops))

    def test_replace_no_routing_call(self) -> None:
        _di, stop = first_with_alternatives(self.plan)
        before = self.fakes.routing.calls
        self.planner.replace_stop(self.plan, stop.id, stop.alternatives[0].id)
        self.assertEqual(self.fakes.routing.calls, before)

    def test_replace_unknown_ids_not_found(self) -> None:
        _di, stop = first_with_alternatives(self.plan)
        with self.assertRaises(NotFound) as cm:
            self.planner.replace_stop(self.plan, "d9s99", stop.alternatives[0].id)
        self.assertEqual(cm.exception.entity, "stop")
        with self.assertRaises(NotFound) as cm:
            self.planner.replace_stop(self.plan, stop.id, "alt_nope")
        self.assertEqual(cm.exception.entity, "alternative")

    def test_replace_matches_offline_shift(self) -> None:
        checked = 0
        for d in self.plan.days_list:
            for s in d.stops:
                for alt in s.alternatives:
                    new = self.planner.replace_stop(self.plan, s.id, alt.id)
                    nd = new.days_list[d.day - 1]
                    later_old = [x for x in d.stops if x.seq > s.seq]
                    later_new = [x for x in nd.stops if x.seq > s.seq]
                    for o, n in zip(later_old, later_new, strict=True):
                        assert o.arrive_at is not None and n.arrive_at is not None
                        shifted = o.arrive_at + timedelta(minutes=alt.shift_min)
                        self.assertLessEqual(abs((shifted - n.arrive_at).total_seconds()), 60)
                        checked += 1
                    replaced = next(x for x in nd.stops if x.id == s.id)
                    self.assertEqual(replaced.arrive_at, alt.stop.arrive_at)
        self.assertGreater(checked, 3)

    def test_replace_recomputes_cost_and_survives_json(self) -> None:
        di, stop = first_with_alternatives(self.plan)
        alt = stop.alternatives[0]
        restored = codec.plan_from_json(json.loads(json.dumps(codec.plan_to_json(self.plan, public=False))))
        a = self.planner.replace_stop(self.plan, stop.id, alt.id)
        b = self.planner.replace_stop(restored, stop.id, alt.id)
        self.assertEqual(dump(codec.plan_to_json(a, public=False)), dump(codec.plan_to_json(b, public=False)))
        from verst_planner.cost.recompute import recompute
        from verst_planner.domain.model import CostOverrides

        offline = recompute(
            self.plan.cost.units,
            self.plan.input.crew,
            True,
            self.plan.input.budget_rub,
            CostOverrides(replaced={stop.id: alt.units}),
        )
        self.assertEqual(a.cost.total_rub, offline.total_rub)  # server == offline recompute
        self.assertEqual([x.rub for x in a.cost.lines], [x.rub for x in offline.lines])
        self.assertEqual(
            a.engine_state.days[di].stops[[s.id for s in a.days_list[di].stops].index(stop.id)].place_id,
            alt.place_id,
        )


if __name__ == "__main__":
    unittest.main()
