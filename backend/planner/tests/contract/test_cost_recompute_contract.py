"""Runs every case of the shared cost-recompute contract (ADR-0009) against `cost.recompute`."""

import json
import unittest
from pathlib import Path
from typing import Any

from verst_planner.cost.recompute import recompute
from verst_planner.domain.codec import alt_units_from_json, units_from_json
from verst_planner.domain.model import CostOverrides, Crew
from verst_planner.explain import ru

CASES = Path(__file__).resolve().parent / "cost_recompute_cases.json"


def load() -> list[dict[str, Any]]:
    with CASES.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    cases: list[dict[str, Any]] = data["cases"]
    return cases


class CostRecomputeContractTest(unittest.TestCase):
    def test_case_count(self) -> None:
        self.assertGreaterEqual(len(load()), 35)  # A§16.11.4: ≥ 1 case per rule, ≥ 35
        names = [c["name"] for c in load()]
        self.assertEqual(len(names), len(set(names)))

    def test_every_case(self) -> None:
        for case in load():
            with self.subTest(case=case["name"]):
                c = case["crew"]
                ages = c.get("childAges")
                crew = Crew(c["adults"], c["children"], c["dog"], None if ages is None else tuple(ages))
                ov = case["overrides"]
                overrides = CostOverrides(
                    hotel_by_stop=dict(ov.get("hotelByStop", {})),
                    replaced={k: alt_units_from_json(v) for k, v in ov.get("replaced", {}).items()},
                )
                res = recompute(
                    units_from_json(case["units"]), crew, case["reserveOn"], case["budget"], overrides
                )
                exp = case["expected"]
                self.assertEqual({line.key.value: line.rub for line in res.lines}, exp["lines"])
                self.assertEqual(res.subtotal_rub, exp["subtotalRub"])
                self.assertEqual(res.total_rub, exp["totalRub"])
                self.assertEqual(res.per_person_rub, exp["perPersonRub"])
                self.assertEqual(res.remaining_rub, exp["remainingRub"])
                self.assertEqual(res.over_budget, exp["overBudget"])
                self.assertEqual(list(res.hint_keys), exp["hintKeys"])
                self.assertEqual(res.lines[-1].enabled, case["reserveOn"])
                if exp["fuelFormulaKm"] is not None:  # the km shown in the fuel formula (A§16.7)
                    km = ru.fmt_km(exp["fuelFormulaKm"])
                    self.assertTrue(res.lines[0].formula_ru.startswith(f"{km} км"), res.lines[0].formula_ru)

    def test_generator_matches_committed_json(self) -> None:
        """A§16.10: `tools/gen_cost_contract.py` reproduces the committed cases byte for byte."""
        text = generated("gen_cost_contract.py")["TEXT"]
        self.assertEqual(text, CASES.read_text(encoding="utf-8"))


def generated(script: str) -> dict[str, Any]:
    """Run a fixture generator in memory (`VERST_GEN_IN_MEMORY=1`) and return its globals."""
    import contextlib
    import io
    import os
    import runpy

    path = Path(__file__).resolve().parents[2] / "tools" / script
    old = os.environ.get("VERST_GEN_IN_MEMORY")
    os.environ["VERST_GEN_IN_MEMORY"] = "1"
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return runpy.run_path(str(path), run_name="generator")
    finally:
        if old is None:
            del os.environ["VERST_GEN_IN_MEMORY"]
        else:
            os.environ["VERST_GEN_IN_MEMORY"] = old


if __name__ == "__main__":
    unittest.main()
