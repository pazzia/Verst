"""Golden trips (A§13.2): one test per case file, every invariant of A§13.3 as a subTest, exact snapshots.

Snapshots are regenerated only with ``VERST_GOLDEN_UPDATE=1`` (``make golden-update``); a mismatch writes
``snapshots/<case>.actual.json`` and fails with the first 80 lines of a unified diff.
"""

from __future__ import annotations

import difflib
import json
import os
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tests.golden.invariants import ALL, GoldenRun
from verst_planner.adapters.fake import FakeWorld, build_fakes
from verst_planner.config import PlannerConfig
from verst_planner.domain import codec
from verst_planner.domain.errors import PlannerError, Unreachable
from verst_planner.domain.model import Route, RouteRequest, TripPlan
from verst_planner.engine import Planner
from verst_planner.events import ListSink
from verst_planner.explain.templates import ReasonTemplates

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases"
SNAPSHOTS = HERE / "snapshots"
WORLDS = HERE.parent.parent / "fixtures" / "worlds"
UPDATE = os.environ.get("VERST_GOLDEN_UPDATE") == "1"

_worlds: dict[str, FakeWorld] = {}


def world(name: str) -> FakeWorld:
    if name not in _worlds:
        _worlds[name] = FakeWorld.load(WORLDS / f"{name}.json")
    return _worlds[name]


class RecordingRouting:
    """Wraps the fake routing to keep the last route (route refs are not part of the plan payload)."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.last: Route | None = None

    def route(self, req: RouteRequest) -> Route:
        self.last = self.inner.route(req)
        return self.last


def load_case(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data


def run_case(case: dict[str, Any]) -> tuple[TripPlan, ListSink, RecordingRouting, Callable[[], TripPlan]]:
    from datetime import datetime

    def make() -> tuple[Planner, RecordingRouting]:
        f = build_fakes(world(case["world"]), datetime.fromisoformat(case["clock"]))
        routing = RecordingRouting(f.routing)
        planner = Planner(
            routing=routing,
            places=f.places,
            prices=f.prices,
            tolls=f.tolls,
            regions=f.regions,
            geocoding=f.geocoding,
            clock=f.clock,
            config=PlannerConfig.from_dict(case.get("config") or {}),
            templates=ReasonTemplates.default(),
        )
        return planner, routing

    planner, routing = make()
    sink = ListSink()
    plan = planner.plan(codec.input_from_json(case["input"]), sink)

    def replan() -> TripPlan:
        p2, _ = make()
        return p2.plan(codec.input_from_json(case["input"]))

    return plan, sink, routing, replan


def snapshot_path(case: dict[str, Any]) -> Path:
    return SNAPSHOTS / f"{case['id']}_{case['slug']}.json"


def snapshot_text(plan: TripPlan) -> str:
    return json.dumps(codec.plan_to_json(plan, trip_id="trp_golden"), ensure_ascii=False, indent=2) + "\n"


def within(actual: int, spec: dict[str, Any]) -> bool:
    value, pct = spec["value"], spec.get("tolerancePct", 0)
    return abs(actual - value) <= abs(value) * pct / 100


class GoldenTest(unittest.TestCase):
    maxDiff = None

    def check_expectations(self, case: dict[str, Any], plan: TripPlan, routing: RecordingRouting) -> None:
        e = case["expect"]
        stops = [s for d in plan.days_list for s in d.stops]
        lines = {line.key.value: line for line in plan.cost.lines}
        with self.subTest(expect="shape"):
            if "days" in e:
                self.assertEqual(plan.days, e["days"])
            if "nights" in e:
                self.assertEqual(plan.nights, e["nights"])
            if "kmRange" in e:
                lo, hi = e["kmRange"]
                self.assertTrue(lo <= plan.km <= hi, f"km {plan.km} not in {e['kmRange']}")
            if "maxDayKm" in e:
                self.assertLessEqual(max(d.km for d in plan.days_list), e["maxDayKm"])
        with self.subTest(expect="overnights"):
            if "overnightTownIds" in e:
                self.assertEqual([r.town_id for r in plan.overnight_reasons], e["overnightTownIds"])
            if "overnightFallbacks" in e:
                self.assertEqual([r.fallback.value for r in plan.overnight_reasons], e["overnightFallbacks"])
        with self.subTest(expect="warnings"):
            codes = sorted(w.code.value for w in plan.warnings)
            if "warnings" in e:
                self.assertEqual(codes, sorted(e["warnings"]))
            for code in e.get("warningsContain", []):
                self.assertIn(code, codes)
        with self.subTest(expect="places"):
            used = {s.place_id for s in stops if s.place_id} | {
                s.selected_hotel_id for s in stops if s.selected_hotel_id
            }
            offered = (
                used
                | {h.place_id for s in stops for h in s.hotel_options}
                | {a.place_id for s in stops for a in s.alternatives}
            )
            for pid in e.get("mustIncludePlaceIds", []):
                self.assertIn(pid, used)
            for pid in e.get("mustExcludePlaceIds", []):
                self.assertNotIn(pid, offered)
        with self.subTest(expect="stops"):
            for day, kinds in e.get("stopKindsPerDay", {}).items():
                d = plan.days_list[int(day) - 1]
                for kind, (lo, hi) in kinds.items():
                    n = sum(1 for s in d.stops if s.kind.value == kind)
                    self.assertTrue(lo <= n <= hi, f"day {day}: {n} × {kind} not in [{lo}, {hi}]")
            for day, kinds in e.get("stopKmRange", {}).items():
                d = plan.days_list[int(day) - 1]
                for kind, (lo, hi) in kinds.items():
                    for s in d.stops:
                        if s.kind.value == kind:
                            self.assertTrue(lo <= s.km_at <= hi, f"{s.name_ru} at km {s.km_at}")
            if "viaBeforeFinish" in e:
                last = plan.days_list[-1].stops
                names = [s.name_ru for s in last]
                via = [s for s in last if s.kind.value == "via"]
                self.assertTrue(via and via[0].name_ru == e["viaBeforeFinish"])
                self.assertLess(names.index(e["viaBeforeFinish"]), len(names) - 1)
            if "roadRefs" in e:
                assert routing.last is not None
                refs = {d.road_ref for d in routing.last.details if d.road_ref}
                self.assertEqual(refs, set(e["roadRefs"]))
            if "rerun" in e:
                self.assertEqual(plan.engine_state.rerun, e["rerun"])
            if "overBudgetDays" in e:
                self.assertEqual([d.day for d in plan.days_list if d.over_budget], e["overBudgetDays"])
        with self.subTest(expect="budgetFit"):
            if "budgetFit" in e:  # ADR-0011 (G13)
                bf, want = plan.budget_fit, e["budgetFit"]
                assert bf is not None
                self.assertEqual(bf.status, want["status"])
                self.assertLessEqual(plan.cost.total_rub, want["totalMax"])
                self.assertEqual(bf.total_rub, plan.cost.total_rub)
                self.assertEqual([x.code for x in bf.levers], want["levers"])
                self.assertEqual(bf.variant_of, want.get("variantOf"))
                self.assertEqual(bf.initial_total_rub - bf.total_rub, sum(x.saved_rub for x in bf.levers))
        with self.subTest(expect="cost"):
            if "costTotalRub" in e:
                self.assertTrue(
                    within(plan.cost.total_rub, e["costTotalRub"]),
                    f"total {plan.cost.total_rub} vs {e['costTotalRub']}",
                )
                self.assertTrue(e.get("costWorkings"), "costTotalRub needs costWorkings")
            for key, spec in e.get("costLinesRub", {}).items():
                self.assertTrue(within(lines[key].rub, spec), f"{key} {lines[key].rub} vs {spec}")
            for key, text in e.get("costFormulaContains", {}).items():
                self.assertIn(_soft(text), _soft(lines[key].formula_ru))
            for key, texts in e.get("costBreakdownContains", {}).items():
                rows = " | ".join(f"{b.label_ru} {b.formula_ru}" for b in lines[key].breakdown)
                for t in texts:
                    self.assertIn(_soft(t), _soft(rows))
            if e.get("remainingIsBudgetMinusTotal"):
                self.assertEqual(
                    plan.cost.remaining_rub,
                    plan.input.budget_rub - plan.cost.total_rub
                    if plan.input.budget_rub is not None
                    else None,
                )

    def check_snapshot(self, case: dict[str, Any], plan: TripPlan) -> None:
        path = snapshot_path(case)
        text = snapshot_text(plan)
        actual = path.with_suffix(".actual.json")
        if UPDATE:
            SNAPSHOTS.mkdir(exist_ok=True)
            path.write_text(text, encoding="utf-8")
            actual.unlink(missing_ok=True)
            return
        if not path.exists():
            SNAPSHOTS.mkdir(exist_ok=True)
            actual.write_text(text, encoding="utf-8")
            self.fail(f"missing snapshot {path.name} (run make golden-update after review)")
        expected = path.read_text(encoding="utf-8")
        if expected != text:
            actual.write_text(text, encoding="utf-8")
            diff = list(
                difflib.unified_diff(
                    expected.splitlines(), text.splitlines(), path.name, actual.name, lineterm=""
                )
            )
            self.fail("snapshot mismatch:\n" + "\n".join(diff[:80]))
        actual.unlink(missing_ok=True)

    def run_golden(self, path: Path) -> None:
        case = load_case(path)
        e = case["expect"]
        if e.get("error"):
            with self.assertRaises(PlannerError) as cm:
                run_case(case)
            self.assertEqual(cm.exception.code, e["error"])
            if "errorPointIndex" in e:
                assert isinstance(cm.exception, Unreachable)
                self.assertEqual(cm.exception.point_index, e["errorPointIndex"])
            return
        plan, sink, routing, replan = run_case(case)
        self.check_expectations(case, plan, routing)
        run = GoldenRun(case, plan, world(case["world"]), sink.events, replan)
        names = list(ALL) if e.get("invariants", ["all"]) == ["all"] else e["invariants"]
        for name in names:
            with self.subTest(invariant=name):
                ALL[name](run)
        with self.subTest(snapshot=path.name):
            self.check_snapshot(case, plan)


GATE_CASES = ("G01", "G02", "G03", "G06", "G07", "G08")
GATE_SHARE = 0.70
GATE_CASE_SHARE = 0.60  # A§16.11.5: each case too


class AlternativesGateTest(unittest.TestCase):
    def test_alternatives_coverage_gate(self) -> None:
        """A§16.6/16.11.5: ≥ 70 % of the replaceable stops of the central-world calm/more_stops goldens have
        ≥ 2 alternatives, and ≥ 60 % in each of those cases (the share per case is printed)."""
        from tests.golden.invariants import alternatives_share

        ok = total = 0
        rows = []
        for path in sorted(CASES.glob("G*.json")):
            case = load_case(path)
            if case["id"] not in GATE_CASES:
                continue
            plan, *_ = run_case(case)
            k, n = alternatives_share(plan)
            rows.append(f"{case['id']} {k}/{n} = {k / n:.0%}")
            with self.subTest(case=case["id"]):
                self.assertGreaterEqual(k / n, GATE_CASE_SHARE)
            ok, total = ok + k, total + n
        share = ok / total
        print(f"\nalternatives coverage: {', '.join(rows)}; total {ok}/{total} = {share:.0%}")
        self.assertGreaterEqual(share, GATE_SHARE)


class TiePicksTest(unittest.TestCase):
    def test_no_pick_decided_by_a_tie(self) -> None:
        """A§16.12 S2-01: in every golden plan the winner of each stage pick (lunch, fuel, rest, overnight
        town, hotel, the sight cap and every sight drop — DEV-113 T1) beats the runner-up by ≥ 0.05, so no
        pick depends on a tie-break."""
        from tests.golden.ties import MIN_MARGIN, record_picks

        checked = 0
        for path in sorted(CASES.glob("G*.json")):
            case = load_case(path)
            if case["expect"].get("error"):
                continue
            for p in record_picks(case):
                checked += 1
                with self.subTest(case=case["id"], stage=p.stage, place=p.place_id):
                    self.assertGreaterEqual(p.margin, MIN_MARGIN, f"{p.best} vs {p.second}")
        self.assertGreaterEqual(checked, 35)  # 39 picks across the 10 plans (9 of them sight picks)


def _soft(s: str) -> str:
    """Compare formula text ignoring the kind of space (U+202F / U+00A0 / ' ')."""
    return s.replace(" ", " ").replace(" ", " ")


def _make_test(path: Path) -> Callable[[GoldenTest], None]:
    def test(self: GoldenTest) -> None:
        self.run_golden(path)

    test.__doc__ = load_case(path)["titleRu"]
    return test


for _path in sorted(CASES.glob("G*.json")):
    setattr(GoldenTest, f"test_{_path.stem}", _make_test(_path))


if __name__ == "__main__":
    unittest.main()
