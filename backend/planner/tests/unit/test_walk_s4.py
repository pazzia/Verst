"""Sprint 4 walks on the real catalogue (ADR-0015 §6, docs/bugs/s4-walk-filters.md): reach, filters, group,
unlimited duration, checked suggestions. Skipped on the sandbox sample catalogue."""

from __future__ import annotations

import json
import unittest
from typing import Any

from tests.unit import test_mobile_v2
from verst_planner import mobile
from verst_planner.city.presets import DURATIONS, INDOOR_KINDS

R = "russia_v1"
FRY = {"lat": 55.9606, "lon": 38.0456, "label": "Фрязино, проезд Павла Блинова, 8"}
KZN = {"lat": 55.7963, "lon": 49.1088, "label": "Казань"}


def walk(**kw: Any) -> dict[str, Any]:
    inp: dict[str, Any] = {
        "start": FRY,
        "preset": "custom",
        "interests": ["history", "architecture"],
        "durationMin": 240,
        "pace": "normal",
        "returnToStart": True,
        "crew": {"adults": 2},
    }
    inp.update(kw)
    out: dict[str, Any] = json.loads(mobile.city_route(R, "t", json.dumps(inp, ensure_ascii=False)))
    return out


class WalkS4Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        test_mobile_v2.MobileV2Test.setUpClass()
        if mobile._CATALOGUE[0].version == "sample":
            raise unittest.SkipTest("sample catalogue")
        mobile.set_clock("2026-10-25T11:00:00+03:00")

    @classmethod
    def tearDownClass(cls) -> None:
        mobile.set_clock("system")

    def test_fryazino_reaches_grebnevo(self) -> None:
        """Bug b3: 4 h, normal pace, with the return — the Гребнево cluster behind the 2.5 km leg cap."""
        w = walk()["result"]
        self.assertGreaterEqual(len(w["stops"]), 4)
        self.assertGreaterEqual(w["durationMin"], 180)
        self.assertTrue(any("Гребнев" in s["nameRu"] for s in w["stops"]))

    def test_interests_filter_or_say_so(self) -> None:
        parks = walk(interests=["parks"])["result"]
        kinds = {s["kind"] for s in parks["stops"]}
        if not kinds & {"park", "embankment", "nature", "zoo", "playground"}:
            self.assertTrue(parks["interestsWidened"])  # never a monument-only walk without saying so
            self.assertTrue(parks["crewNotesRu"])

    def test_suggestions_are_checked_and_new(self) -> None:
        base = walk()["result"]
        exclude = [s["poiId"] for s in base["stops"] if s["poiId"]]
        err = walk(exclude=exclude * 1 + ["Q4426361"])
        if err["ok"]:
            self.skipTest("enough places remain")
        sugg = err["error"]["suggestions"]
        self.assertTrue(sugg)
        for sg in sugg:
            self.assertNotEqual(sg.get("durationMin", -1), 240)
            self.assertNotEqual(sg.get("preset"), "custom")
            kw: dict[str, Any] = {"exclude": [] if sg.get("clearExclude") else exclude}
            if "durationMin" in sg:
                kw["durationMin"] = sg["durationMin"]
            if "preset" in sg:
                kw["preset"] = sg["preset"]
                kw["interests"] = (
                    ["history", "architecture", "parks", "views"] if sg["preset"] == "custom" else []
                )
            self.assertTrue(walk(**kw)["ok"], sg)

    def test_group_warnings_and_dog_walk(self) -> None:
        dog = walk(start=KZN, preset="dog_walk", durationMin=120, crew={"adults": 2, "dog": True})["result"]
        self.assertFalse({s["kind"] for s in dog["stops"]} & INDOOR_KINDS)
        kids = walk(start=KZN, preset="beer", adultConfirmed=True, crew={"adults": 2, "children": 1})
        self.assertTrue(kids["ok"])  # children never block
        self.assertIn("CHILD_BARS", [x["code"] for x in kids["result"]["warnings"]])
        museums = walk(start=KZN, preset="museums", crew={"adults": 2, "dog": True})["result"]
        self.assertIn("DOG_INDOOR", [x["code"] for x in museums["warnings"]])
        self.assertTrue(any(s["noteRu"] and "собак" in s["noteRu"] for s in museums["stops"]))

    def test_unlimited_has_no_timetable_but_hours(self) -> None:
        w = walk(start=KZN, preset="overview", durationMin=None)["result"]
        self.assertTrue(w["unlimited"])
        self.assertIsNone(w["durationMin"])
        self.assertTrue(w["stops"])
        for s in w["stops"]:
            self.assertIsNone(s["arriveAt"])
            self.assertTrue(s["hours"]["todayRu"])
        self.assertLessEqual(len(w["stops"]), 12)

    def test_durations_constant(self) -> None:
        self.assertEqual(DURATIONS, (120, 240, 360, 480))


if __name__ == "__main__":
    unittest.main()
