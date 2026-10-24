"""DEV-112: `tools/gen_mobile_contracts.py` reproduces the committed Kotlin contracts byte for byte."""

from __future__ import annotations

import json
import unittest

from tests.contract.test_cost_recompute_contract import generated
from tests.helpers import PLANNER_ROOT

CONTRACTS = PLANNER_ROOT.parents[1] / "docs" / "contracts"


class MobileContractsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.out: dict[str, str] = generated("gen_mobile_contracts.py")["GENERATED"]

    def test_generator_matches_committed_files(self) -> None:
        committed = {
            f"{sub}/{p.name}": p
            for sub in ("replace", "patch")
            for p in sorted((CONTRACTS / sub).glob("*.json"))
        }
        self.assertEqual(sorted(self.out), sorted(committed))
        for rel, text in self.out.items():
            with self.subTest(file=rel):
                self.assertEqual(text, committed[rel].read_text("utf-8"))

    def test_counts_and_shape(self) -> None:
        replace = [k for k in self.out if k.startswith("replace/")]
        patch = [k for k in self.out if k.startswith("patch/")]
        self.assertGreaterEqual(len(replace), 40)
        self.assertGreaterEqual(len(patch), 12)
        doc = json.loads(self.out[replace[0]])
        self.assertEqual(sorted(doc), ["after", "altId", "before", "case", "stopId"])
        self.assertNotIn("engineState", doc["before"])
        stop = next(s for d in doc["before"]["daysList"] for s in d["stops"] if s["id"] == doc["stopId"])
        alt = next(a for a in stop["alternatives"] if a["id"] == doc["altId"])
        day = next(d for d in doc["after"]["daysList"] if any(s["id"] == doc["stopId"] for s in d["stops"]))
        self.assertEqual(
            [(s["id"], s["arriveAt"], s["departAt"], s["kmFromPrev"]) for s in day["stops"]],
            [(p["stopId"], p["arriveAt"], p["departAt"], p["kmFromPrev"]) for p in alt["dayPatch"]],
        )
        kinds = {json.loads(self.out[k])["kind"].split("_")[0] for k in patch}
        self.assertEqual(kinds, {"reserve", "budget", "hotel"})


if __name__ == "__main__":
    unittest.main()
