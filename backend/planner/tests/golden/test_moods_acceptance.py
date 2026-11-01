"""CEO 2026-10-29 (build 0.3.164): «Как едем» must change the trip the way the labels promise.

Фрязино → Санкт-Петербург, 2 adults, 500 km/day, 1 Nov 2026 08:00, on the real catalogue `russia_v1`:

- «Только доехать» (`just_drive`): no sights and no town visits at all — fuel, food and rests only;
- «Спокойно» (`calm`): few sights, long rests, no evening sightseeing in the overnight town;
- «Весело и познавательно» (`fun`): strictly more sights than «Спокойно», the evening in the overnight town.

Rule checks, not byte snapshots (the open data changes with every data run). Skipped on the sample catalogue.
"""

from __future__ import annotations

import json
import unittest
from typing import Any

from tests.unit import test_mobile_v2
from verst_planner import mobile
from verst_planner.config import PlannerConfig

FRYAZINO = {"lat": 55.9606, "lon": 38.0456, "label": "Фрязино"}
SPB = {"lat": 59.9386, "lon": 30.3141, "label": "Санкт-Петербург"}
CFG = PlannerConfig.from_dict(mobile.OPEN_DATA_CONFIG)
EVENING = "Вечер в городе ночёвки"


def plan(mood: str) -> dict[str, Any]:
    mobile.set_clock("2026-10-31T18:00+03:00")
    body = {
        "origin": FRYAZINO,
        "destination": SPB,
        "crew": {"adults": 2, "children": 0},
        "dailyKm": 500,
        "startAt": "2026-11-01T08:00",
        "mood": mood,
    }
    r = json.loads(mobile.plan("russia_v1", f"mood-{mood}", json.dumps(body), None))
    assert r["ok"], r
    trip: dict[str, Any] = r["result"]["trip"]
    return trip


def stops(trip: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for d in trip["daysList"] for s in d["stops"]]


def sights(trip: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in stops(trip) if s["kind"] == "sight"]


def signature(trip: dict[str, Any]) -> list[tuple[str, str]]:
    return [(s["kind"], s["name"]) for s in stops(trip)]


class MoodsFryazinoSpbTest(unittest.TestCase):
    trips: dict[str, dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        test_mobile_v2.MobileV2Test.setUpClass()
        cat = mobile._CATALOGUE[0]
        if cat.version == "sample" or not any(p.quality is not None for p in cat.pois):
            raise unittest.SkipTest("sample or pre-Sprint-4 catalogue (no quality data)")
        cls.trips = {m: plan(m) for m in ("calm", "fun", "just_drive")}

    @classmethod
    def tearDownClass(cls) -> None:
        mobile.set_clock("system")

    def test_just_drive_has_no_sights_and_no_town_visits(self) -> None:
        trip = self.trips["just_drive"]
        self.assertEqual(sights(trip), [])
        self.assertFalse([s for s in stops(trip) if s["reason"].startswith(EVENING)])
        kinds = {s["kind"] for s in stops(trip)}
        self.assertLessEqual(kinds, {"start", "fuel", "food", "rest", "overnight", "finish"})
        alt_kinds = {a["stop"]["kind"] for s in stops(trip) for a in s["alternatives"]}
        self.assertNotIn("sight", alt_kinds)  # a break's alternatives are breaks, not sights

    def test_fun_has_more_sights_than_calm(self) -> None:
        fun, calm = sights(self.trips["fun"]), sights(self.trips["calm"])
        self.assertGreater(len(fun), len(calm), [s["name"] for s in fun])
        self.assertTrue([s for s in fun if s["reason"].startswith(EVENING)], "fun: no evening in the town")

    def test_calm_has_no_evening_run_and_long_rests(self) -> None:
        trip = self.trips["calm"]
        self.assertFalse([s for s in stops(trip) if s["reason"].startswith(EVENING)])
        rests = [s for s in stops(trip) if s["kind"] == "rest" and s["dwellMin"] > CFG.rest.break_min_dwell]
        self.assertTrue(rests)
        for s in rests:
            self.assertEqual(s["dwellMin"], CFG.rest_dwell_min.calm, s["name"])

    def test_the_three_stop_lists_differ(self) -> None:
        sig = {m: signature(t) for m, t in self.trips.items()}
        self.assertNotEqual(sig["calm"], sig["fun"])
        self.assertNotEqual(sig["calm"], sig["just_drive"])
        self.assertNotEqual(sig["fun"], sig["just_drive"])

    def test_config_orders_the_moods(self) -> None:
        """The labels' promises in numbers: «Только доехать» has the longest day and rarest breaks,
        «Спокойно» the shortest day, the longest breaks and the fewest sights."""
        b, r, d, n = CFG.day_budget_min, CFG.rest_interval_min, CFG.rest_dwell_min, CFG.sights.max_per_day
        self.assertGreater(b.just_drive, max(b.calm, b.fun, b.more_stops))
        self.assertLess(b.calm, min(b.fun, b.more_stops))
        self.assertGreater(r.just_drive, r.calm)
        self.assertGreater(r.calm, r.fun)
        self.assertGreater(d.calm, max(d.fun, d.just_drive))
        self.assertEqual(n.just_drive, 0)
        self.assertLess(n.calm, n.fun)
        tv = CFG.town_visit
        self.assertEqual((tv.evening_max.just_drive, tv.morning_max.just_drive), (0, 0))
        self.assertEqual(tv.evening_max.calm, 0)
        self.assertGreater(tv.evening_max.fun, 0)


if __name__ == "__main__":
    unittest.main()
