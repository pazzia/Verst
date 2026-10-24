"""DEV-112: `tools/gen_mobile_contracts.py` reproduces the committed Kotlin contract bundles (`*.json.gz`)."""

from __future__ import annotations

import gzip
import json
import unittest
from typing import Any

from tests.contract.test_cost_recompute_contract import generated
from tests.helpers import PLANNER_ROOT

CONTRACTS = PLANNER_ROOT.parents[1] / "docs" / "contracts"
SNAPSHOTS = PLANNER_ROOT / "tests" / "golden" / "snapshots"
MAX_BYTES = 2_000_000


class MobileContractsTest(unittest.TestCase):
    out: dict[str, str]
    gen: dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.gen = generated("gen_mobile_contracts.py")
        cls.out = cls.gen["GENERATED"]

    def bundles(self, sub: str) -> list[dict[str, Any]]:
        return [json.loads(v) for k, v in sorted(self.out.items()) if k.startswith(f"{sub}/")]

    def test_generator_matches_committed_files(self) -> None:
        committed = {
            f"{sub}/{p.name}": p for sub in ("replace", "patch") for p in sorted((CONTRACTS / sub).iterdir())
        }
        self.assertEqual(sorted(self.out), sorted(committed))
        for rel, text in self.out.items():
            with self.subTest(file=rel):
                self.assertEqual(text, gzip.decompress(committed[rel].read_bytes()).decode("utf-8"))

    def test_size_budget(self) -> None:
        files = [p for sub in ("replace", "patch") for p in (CONTRACTS / sub).iterdir()]
        self.assertTrue(all(p.name.endswith(".json.gz") for p in files))
        self.assertLessEqual(sum(p.stat().st_size for p in files), MAX_BYTES)

    def test_counts(self) -> None:
        replace, patch = self.bundles("replace"), self.bundles("patch")
        self.assertEqual(len(replace), 11)  # G01-G08, G11, G12 + Sprint 3 G13
        self.assertEqual(len(patch), 11)
        self.assertGreaterEqual(sum(len(b["items"]) for b in replace), 40)
        self.assertGreaterEqual(sum(len(b["items"]) for b in patch), 12)
        per_stop: dict[tuple[str, str], int] = {}
        for b in replace:
            for it in b["items"]:
                key = (b["case"], it["stopId"])
                per_stop[key] = per_stop.get(key, 0) + 1
        self.assertLessEqual(max(per_stop.values()), self.gen["MAX_ALTERNATIVES"])
        self.assertEqual(self.gen["MAX_ALTERNATIVES"], 3)
        kinds = {it["kind"].split("_")[0] for b in patch for it in b["items"]}
        self.assertEqual(kinds, {"reserve", "budget", "hotel"})

    def test_shape(self) -> None:
        b = self.bundles("replace")[0]
        self.assertEqual(sorted(b), ["before", "case", "items"])
        snap = next(SNAPSHOTS.glob(f"{b['case']}_*.json"))
        self.assertEqual(b["before"], json.loads(snap.read_text("utf-8")))
        self.assertNotIn("engineState", b["before"])
        it = b["items"][0]
        self.assertEqual(sorted(it), ["afterCost", "afterDay", "afterKm", "altId", "stopId"])
        stop = next(s for d in b["before"]["daysList"] for s in d["stops"] if s["id"] == it["stopId"])
        alt = next(a for a in stop["alternatives"] if a["id"] == it["altId"])
        self.assertEqual(
            [(s["id"], s["arriveAt"], s["departAt"], s["kmFromPrev"]) for s in it["afterDay"]["stops"]],
            [(p["stopId"], p["arriveAt"], p["departAt"], p["kmFromPrev"]) for p in alt["dayPatch"]],
        )
        p = self.bundles("patch")[0]["items"]
        self.assertEqual(sorted(p[0]), ["afterCost", "afterHotel", "afterInput", "kind", "patch"])
        hotel = next(x["afterHotel"] for x in p if x["kind"].startswith("hotel_"))
        self.assertEqual(sorted(hotel), ["costRub", "placeId", "selectedHotelId", "stopId", "tags"])


if __name__ == "__main__":
    unittest.main()
