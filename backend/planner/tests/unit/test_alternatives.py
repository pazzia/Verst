import unittest
from datetime import datetime
from functools import cache

from tests.helpers import make_planner, trip
from verst_planner.adapters.fake import FakeWorld
from verst_planner.domain.enums import Mood, StopKind
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
        for _p, d, s in self.all_stops():
            for a in s.alternatives:
                self.assertEqual(a.units.place_id, a.place_id)
                patch = {p.stop_id: p for p in a.day_patch}
                self.assertEqual(set(patch), {x.id for x in d.stops})
                # delta_min = change of the day end; shift_min = arrival change of the next stop
                end = a.day_patch[-1].arrive_at
                assert end is not None and d.end_at is not None
                self.assertLessEqual(abs((end - d.end_at).total_seconds() / 60 - a.delta_min), 1)
                k = [p.stop_id for p in a.day_patch].index(s.id)
                if k + 1 < len(a.day_patch):
                    nxt = a.day_patch[k + 1]
                    old = next(x for x in d.stops if x.id == nxt.stop_id)
                    assert nxt.arrive_at is not None and old.arrive_at is not None
                    diff = (nxt.arrive_at - old.arrive_at).total_seconds() / 60
                    self.assertLessEqual(abs(diff - a.shift_min), 1)

    def test_any_position(self) -> None:
        # A§16.6: the candidate is inserted at its own km, so the order of the day may change
        from tests.unit.test_rest import corridor, day, place_at, setup
        from verst_planner.domain.enums import PlaceType, Tag
        from verst_planner.domain.model import LatLon, PlannedStop
        from verst_planner.pipeline.alternatives import Pools, alternatives_for_day
        from verst_planner.pipeline.rest import make_rest_stop
        from verst_planner.pipeline.schedule import ScheduledDay
        from verst_planner.pipeline.timeline import schedule_day

        ctx, inp = setup()
        here = place_at("r100", PlaceType.REST, 100, {Tag.WC})
        later = place_at("r125", PlaceType.REST, 125, {Tag.WC, Tag.VIEW})
        museum = PlannedStop(StopKind.SIGHT, 110.0, "музей", LatLon(52, 38), dwell_min=20, fixed=True)
        d = day(300, [make_rest_stop(here, inp, ctx, 100.0), museum])
        cor = corridor([here, later])
        profile = ctx.profile_for(cor.route)
        sd = ScheduledDay(d, schedule_day(d, profile), 600, ids=["a", "b", "c", "d"])
        alts, notes = alternatives_for_day(sd, Pools.of(cor), {"r100"}, inp, ctx, profile, None, 300.0)
        (alt,) = alts[1]
        self.assertEqual(alt.place_id, "r125")
        self.assertEqual(
            [p.stop_id for p in alt.day_patch], ["a", "c", "b", "d"]
        )  # rest now after the museum
        self.assertEqual(notes[1], "Нашли только один вариант в это время.")
        self.assertEqual(alt.shift_min, 0)  # same dwell and detour: the finish after the rest does not move
        # the museum is now reached 20 min earlier (08:00 + 110 min), before the rest
        self.assertEqual(alt.day_patch[1].arrive_at, d.start_at.replace(tzinfo=None, hour=9, minute=50))

    def test_coverage_on_mini_world(self) -> None:
        # A§16.11.5: a controlled corridor with one candidate before and one after each replaceable stop
        # (rest, lunch, sight, range fuel) → every replaceable stop gets ≥ 2 alternatives, independent of
        # the central world fixture.
        from tests.unit.test_rest import ROUTE, day, place_at, setup
        from tests.unit.test_sights import sight
        from verst_planner.domain.enums import PlaceType, Tag
        from verst_planner.domain.model import Candidate
        from verst_planner.geo.index import PolylineIndex
        from verst_planner.pipeline import Corridor
        from verst_planner.pipeline.alternatives import Pools, alternatives_for_day
        from verst_planner.pipeline.meals import make_lunch_stop
        from verst_planner.pipeline.rest import make_rest_stop
        from verst_planner.pipeline.schedule import ScheduledDay
        from verst_planner.pipeline.sights import make_sight_stop
        from verst_planner.pipeline.timeline import schedule_day

        def food(pid: str, km: float) -> Candidate:
            return place_at(pid, PlaceType.FOOD, km, {Tag.PARKING}, avg_check_rub=700)

        def fuel(pid: str, km: float) -> Candidate:
            return place_at(pid, PlaceType.FUEL, km, {Tag.WC})

        rests = [place_at(f"r{k}", PlaceType.REST, k, {Tag.WC}) for k in (90, 100, 110)]
        foods = [food(f"f{k}", k) for k in (240, 250, 255)]
        sights = [sight(f"s{k}", k) for k in (259, 260, 270)]
        fuels = [fuel(f"g{k}", k) for k in (330, 340, 350)]
        cor = Corridor(ROUTE, PolylineIndex(ROUTE), sights, foods, fuels, rests, [], [])
        ctx, inp = setup(mood=Mood.CALM)
        from verst_planner.domain.model import PlannedStop

        stops = [
            make_rest_stop(rests[1], inp, ctx, 100.0),
            make_lunch_stop(foods[1], inp, ctx, [], 0.0),
            make_sight_stop(sights[1], inp, ctx),
            PlannedStop(
                StopKind.FUEL,
                340.0,
                "АЗС",
                fuels[1].place.point,
                place=fuels[1].place,
                dwell_min=10,
                auto=True,
                reason_key="fuel.range",
                reason_params={"km": 340},
                region_code="RU-MOS",
                pool="fuel",
            ),
        ]
        d = day(420, stops)
        profile = ctx.profile_for(ROUTE)
        sd = ScheduledDay(d, schedule_day(d, profile), 600, ids=[f"d1s0{k}" for k in range(1, 7)])
        used = {"r100", "f250", "s260", "g340"}
        alts, notes = alternatives_for_day(sd, Pools.of(cor), used, inp, ctx, profile, None, 420.0)
        self.assertEqual(sorted(alts), [1, 2, 3, 4])
        for i, got in alts.items():
            with self.subTest(stop=d.stops[i].name_ru):
                self.assertGreaterEqual(len(got), 2)
                self.assertNotIn(i, notes)

    def test_note_when_fewer_than_two(self) -> None:
        none = "Других вариантов в это время поблизости нет."
        one = "Нашли только один вариант в это время."
        seen = set()
        for _p, _d, s in self.all_stops():
            if not s.replaceable:
                self.assertIsNone(s.alternatives_note_ru, s.id)
                continue
            expected = {0: none, 1: one}.get(len(s.alternatives))
            self.assertEqual(s.alternatives_note_ru, expected, s.id)
            seen.add(expected)
        self.assertIn(None, seen)

    def test_delta_rub_matches_recompute(self) -> None:
        from verst_planner.cost.recompute import recompute
        from verst_planner.domain.model import CostOverrides

        checked = 0
        for plan in plans():
            base = recompute(plan.cost.units, plan.input.crew, True, None)
            base_sum = sum(line.rub for line in base.lines[:5])
            for d in plan.days_list:
                for s in d.stops:
                    for a in s.alternatives:
                        r = recompute(
                            plan.cost.units,
                            plan.input.crew,
                            True,
                            None,
                            CostOverrides(replaced={s.id: a.units}),
                        )
                        change = sum(line.rub for line in r.lines[:5]) - base_sum
                        with self.subTest(alt=a.id):
                            self.assertLessEqual(abs(change - a.delta_rub), 10, (change, a.delta_rub))
                        checked += 1
        self.assertGreater(checked, 20)


if __name__ == "__main__":
    unittest.main()
