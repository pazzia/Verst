"""ADR-0013: walk input, presets, the orienteering solver (incl. a brute-force quality check) and assembly."""

from __future__ import annotations

import itertools
import random
import unittest
from datetime import datetime

from verst_planner.city import presets as P
from verst_planner.city.route import NotEnoughPois, WalkTown, build_walk
from verst_planner.city.walk import (
    Candidate,
    Solver,
    WalkInput,
    caps_for,
    dwell_for,
    earliest_hour,
    parse_input,
    rounded_start,
    weights_for,
)
from verst_planner.domain.errors import InvalidInput, PlanCancelled
from verst_planner.domain.model import LatLon
from verst_planner.events import CancelToken
from verst_planner.hours import parse

START = LatLon(57.6261, 39.8845)
NOW = datetime(2026, 10, 23, 9, 7)
T0 = datetime(2026, 10, 23, 10, 0)  # a Friday


def cand(i: int, kind: str = "church", dlat: float = 0.0, dlon: float = 0.0, **kw: object) -> Candidate:
    base = {
        "id": f"c{i:02d}",
        "name": f"место {i}",
        "kind": kind,
        "point": LatLon(START.lat + dlat, START.lon + dlon),
        "popularity": 0.5,
        "heritage": False,
        "hours": None,
        "hours_verified": True,
        "cost_rub": 0,
        "dwell_min": 20,
        "has_photo": False,
        "weight": 1.0,
    }
    base.update(kw)
    return Candidate(**base)  # type: ignore[arg-type]


def inp(**kw: object) -> WalkInput:
    d: dict[str, object] = {"start": {"lat": START.lat, "lon": START.lon, "label": "старт"}}
    d.update(kw)
    return parse_input(d, NOW)


class InputTest(unittest.TestCase):
    def test_defaults(self) -> None:
        w = inp()
        self.assertEqual(
            (w.preset, w.duration_min, w.pace, w.adults, w.return_to_start),
            ("overview", 240, "normal", 1, True),
        )
        m = inp(preset="museums")
        self.assertEqual((m.duration_min, m.pace), (360, "slow"))

    def test_errors(self) -> None:
        bad: list[tuple[dict[str, object], str]] = [
            ({"start": None}, "start"),
            ({"start": {"lat": "x"}}, "start"),
            ({"preset": "spa"}, "preset"),
            ({"durationMin": 90}, "durationMin"),
            ({"durationMin": True}, "durationMin"),
            ({"interests": ["golf"]}, "interests"),
            ({"preset": "custom"}, "interests"),
            ({"pace": "run"}, "pace"),
            ({"budgetRub": -1}, "budgetRub"),
            ({"crew": []}, "crew"),
            ({"crew": {"adults": 0}}, "crew"),
            ({"preset": "beer"}, "adultConfirmed"),
            ({"preset": "beer", "adultConfirmed": True, "crew": {"adults": 2, "children": 1}}, "preset"),
            ({"adultConfirmed": "yes"}, "adultConfirmed"),
            ({"startAt": "завтра"}, "startAt"),
            ({"startAt": "2030-01-01T10:00"}, "startAt"),
            ({"exclude": [1]}, "exclude"),
            ({"townId": 5}, "townId"),
        ]
        for extra, field in bad:
            d: dict[str, object] = {"start": {"lat": START.lat, "lon": START.lon}}
            d.update(extra)
            with self.subTest(extra=extra), self.assertRaises(InvalidInput) as e:
                parse_input(d, NOW)
            self.assertEqual(e.exception.field, field)

    def test_weights_caps_dwell_start(self) -> None:
        w = weights_for(inp(preset="custom", interests=["museums"]))
        self.assertEqual((w["museum"], w["church"], w["bar"]), (1.0, 0.15, 0.0))
        self.assertEqual(caps_for(inp(preset="custom", interests=["parks"]))["drinks"], 5)
        self.assertEqual(caps_for(inp(preset="museums"))["museum"], 4)
        self.assertEqual(dwell_for("museum", 50, inp(preset="museums")), round(90 * 1.25))
        self.assertEqual(dwell_for("museum", 50, inp()), 45)
        self.assertEqual(rounded_start(NOW), datetime(2026, 10, 23, 9, 15))
        self.assertEqual(rounded_start(NOW, 18), datetime(2026, 10, 23, 18, 0))
        self.assertEqual(earliest_hour(inp(preset="beer", adultConfirmed=True)), 18)
        self.assertEqual(earliest_hour(inp(preset="museums")), 10)
        self.assertEqual(earliest_hour(inp()), 0)
        self.assertLessEqual(P.radius_km(480, 5.5), 6.0)


def solver(
    cands: list[Candidate],
    T: float = 240,
    budget: int | None = None,
    caps: dict[str, int] | None = None,
    finish: bool = True,
) -> Solver:
    return Solver(cands, START, START if finish else None, T, 4.5, T0, budget, caps or {})


class SolverTest(unittest.TestCase):
    def test_respects_hours_with_waiting(self) -> None:
        opens_late = cand(1, "museum", 0.002, hours=parse("Mo-Su 10:30-18:00"), dwell_min=30)
        closed = cand(2, "museum", 0.003, hours=parse("Mo-Su 06:00-07:00"))
        s = solver([opens_late, closed])
        seq = s.solve()
        self.assertEqual([s.c[i].id for i in seq], ["c01"])
        ev = s.evaluate(seq)
        self.assertGreaterEqual(ev.legs[0].arrive, 30)  # waited for 10:30

    def test_leg_cap_budget_and_caps(self) -> None:
        far = cand(1, "church", 0.05)  # ~5.6 km away
        paid = cand(2, "museum", 0.001, cost_rub=900)
        free = cand(3, "park", -0.001)
        s = solver([far, paid, free], budget=500)
        self.assertEqual([s.c[i].id for i in s.solve()], ["c03"])
        drinks = [cand(i, "bar", i / 2000) for i in range(1, 8)]
        s2 = solver(drinks, caps={"drinks": 3}, T=480)
        self.assertEqual(len(s2.solve()), 3)

    def test_time_budget_and_return(self) -> None:
        many = [cand(i, "church", (1 + i % 5) / 1500, (1 + i // 5) / 1500, dwell_min=40) for i in range(12)]
        s = solver(many, T=120)
        seq = s.solve()
        ev = s.evaluate(seq)
        self.assertTrue(ev.ok)
        self.assertLessEqual(ev.total_min, 120)
        self.assertGreater(ev.back_km, 0)
        open_end = solver(many, T=120, finish=False)
        self.assertEqual(open_end.evaluate(open_end.solve()).back_km, 0.0)

    def test_deterministic(self) -> None:
        rnd = random.Random(7)
        cands = [
            cand(
                i,
                rnd.choice(P.SIGHT_KINDS),
                rnd.uniform(-0.01, 0.01),
                rnd.uniform(-0.02, 0.02),
                popularity=rnd.random(),
            )
            for i in range(40)
        ]
        a = solver(cands).solve()
        b = solver(list(cands)).solve()
        self.assertEqual(a, b)

    def test_cancel(self) -> None:
        tok = CancelToken()
        tok.cancel()
        s = Solver([cand(1)], START, START, 240, 4.5, T0, None, {}, tok)
        with self.assertRaises(PlanCancelled):
            s.solve()

    def test_diversity(self) -> None:
        s = solver([cand(1), cand(2), cand(3)])
        one = s.c[0].base_score
        self.assertAlmostEqual(s.score([0, 1, 2]), one * (1 + 1 + P.DIVERSITY))

    def test_near_optimal_against_brute_force(self) -> None:
        """ADR-0013: ≥ 0.9 x the optimum in ≥ 95 % of 200 random 8-candidate pools."""
        good = 0
        for seed in range(200):
            rnd = random.Random(seed)
            cands = [
                cand(
                    i,
                    rnd.choice(("church", "museum", "park", "monument", "viewpoint")),
                    rnd.uniform(-0.012, 0.012),
                    rnd.uniform(-0.02, 0.02),
                    popularity=rnd.uniform(0.1, 1.0),
                    dwell_min=rnd.choice((10, 20, 40, 60)),
                )
                for i in range(8)
            ]
            s = solver(cands, T=150)
            got = s.score(s.solve())
            subsets = [
                c
                for r in range(1, 9)
                for c in itertools.combinations(range(8), r)
                if sum(s.c[i].dwell_min for i in c) <= 150  # cannot fit otherwise
            ]
            subsets.sort(key=lambda sub: -s.score(sub))
            best = next(
                (
                    s.score(sub)
                    for sub in subsets
                    if any(s.evaluate(p).ok for p in itertools.permutations(sub))
                ),
                0.0,
            )
            if best == 0 or got >= 0.9 * best - 1e-9:
                good += 1
        self.assertGreaterEqual(good, 190)


class AssembleTest(unittest.TestCase):
    town = WalkTown("Q1", "Ярославль", "Ярославле", "Europe/Moscow")

    def test_walk_json(self) -> None:
        cands = [
            cand(i, ("church", "museum", "park")[i % 3], i / 1500, cost_rub=100 * (i % 3 == 1))
            for i in range(6)
        ]
        w = inp(preset="custom", interests=["history", "parks", "food"], durationMin=240, budgetRub=5000)
        r = build_walk(w, cands, self.town, T0, "0.1.0", "wlk_t")
        self.assertEqual(r["titleRu"], "Ярославль: прогулка по интересам")
        kinds = [s["kind"] for s in r["stops"]]
        self.assertIn("meal", kinds)
        meal = r["stops"][kinds.index("meal")]
        self.assertFalse(meal["tappable"])
        self.assertEqual(r["cost"]["totalRub"], sum(x["rub"] for x in r["cost"]["lines"]))
        self.assertTrue(r["returnToStart"])
        self.assertEqual(r["polyline"][0], r["polyline"][-1])
        times = [s["arriveAt"] for s in r["stops"]]
        self.assertEqual(times, sorted(times))
        self.assertIsNone(r["responsibleNoteRu"])
        self.assertEqual(r["input"]["budgetRub"], 5000)

    def test_drinks_and_unverified_hours(self) -> None:
        bars = [cand(i, "ryumochnaya", i / 2000, hours_verified=False, cost_rub=300) for i in range(1, 5)]
        w = inp(preset="ryumochnye", adultConfirmed=True, returnToStart=False)
        r = build_walk(w, bars, self.town, datetime(2026, 10, 23, 18, 0), "0.1.0", "wlk_b")
        self.assertIsNotNone(r["responsibleNoteRu"])
        self.assertEqual(r["warnings"][0]["code"], "HOURS_UNVERIFIED")
        self.assertEqual([x["key"] for x in r["cost"]["lines"]], ["tickets", "drinks"])
        self.assertEqual(r["finish"]["label"], r["stops"][-1]["nameRu"])

    def test_not_enough(self) -> None:
        with self.assertRaises(NotEnoughPois) as e:
            build_walk(inp(), [cand(1)], self.town, T0, "0.1.0", "wlk_x")
        self.assertEqual(e.exception.field, "preset")


if __name__ == "__main__":
    unittest.main()
