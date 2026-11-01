"""Acceptance 2026-10-28, block 1 «plan quality»: the traveller's and QA's scenarios on the real catalogue
`russia_v1` (docs/review/acceptance-2026-10-28/traveller.md К1-К3, В1-В3, М2; qa.md B-1, B-4). Rule checks,
not byte snapshots (the open data changes with every data run). Skipped on the sandbox sample catalogue."""

from __future__ import annotations

import json
import unittest
from typing import Any

from tests.golden.test_s4_acceptance import MOSCOW
from tests.unit import test_mobile_v2
from verst_planner import mobile
from verst_planner.config import PlannerConfig
from verst_planner.domain.model import LatLon
from verst_planner.geo.distance import haversine_km
from verst_planner.pipeline.sights import dog_closed, lever_free_ok, minor_open_data

MSK = {"lat": 55.7558, "lon": 37.6173, "label": "Москва"}
KAZAN = {"lat": 55.7963, "lon": 49.1088, "label": "Казань"}
YAR = {"lat": 57.6261, "lon": 39.8845, "label": "Ярославль"}
KIDS = {"adults": 2, "children": 2, "childAges": [7, 12]}
CFG = PlannerConfig.from_dict(mobile.OPEN_DATA_CONFIG)


def plan(inp: dict[str, Any], clock: str = "2026-11-06T18:00+03:00") -> dict[str, Any]:
    mobile.set_clock(clock)
    r = json.loads(mobile.plan("russia_v1", "b1", json.dumps({"startAt": "2026-11-07T08:00", **inp}), None))
    assert r["ok"], r
    trip: dict[str, Any] = r["result"]["trip"]
    return trip


def stops(trip: dict[str, Any], kind: str | None = None) -> list[dict[str, Any]]:
    return [s for d in trip["daysList"] for s in d["stops"] if kind is None or s["kind"] == kind]


def nights(trip: dict[str, Any]) -> list[str]:
    return [d["stops"][-1]["name"] for d in trip["daysList"][:-1]]


class Block1AcceptanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        test_mobile_v2.MobileV2Test.setUpClass()
        cat = mobile._CATALOGUE[0]
        if cat.version == "sample" or not any(p.quality is not None for p in cat.pois):
            raise unittest.SkipTest("sample or pre-Sprint-4 catalogue (no quality data)")
        cls.world = mobile._WORLDS["russia_v1"].world

    @classmethod
    def tearDownClass(cls) -> None:
        mobile.set_clock("system")

    def added_sights(self, trip: dict[str, Any]) -> list[dict[str, Any]]:
        """Sights the engine added (not a ready route's own stops: those are not replaceable)."""
        return [s for s in stops(trip, "sight") if s["replaceable"] and s["placeId"] in self.world.places]

    def check_k1(self, trip: dict[str, Any]) -> None:
        for s in self.added_sights(trip):
            p = self.world.places[s["placeId"]]
            self.assertGreater(haversine_km(LatLon(s["lat"], s["lon"]), MOSCOW), 30.0, s["name"])
            self.assertFalse(minor_open_data(p, CFG), s["name"])

    def test_k1_k2_v1_moscow_kazan_children(self) -> None:
        """Москва → Казань, 2 adults + 7 and 12, 300 km/day, «весело и познавательно», no budget."""
        trip = plan({"origin": MSK, "destination": KAZAN, "crew": KIDS, "dailyKm": 300, "mood": "fun"})
        self.check_k1(trip)
        self.assertEqual(nights(trip)[:2], ["Владимир", "Нижний Новгород"])
        for d in trip["daysList"][:-1]:
            evening = [s for s in d["stops"] if s["reason"].startswith("Вечер в городе ночёвки")]
            if d["stops"][-1]["arriveAt"][11:] < "14:00":
                self.assertTrue(evening, f"day {d['day']}: arrived early, no evening in the town")
            for s in evening:  # the town's own sights, seen after the drive into town
                self.assertLessEqual(
                    haversine_km(
                        LatLon(s["lat"], s["lon"]), LatLon(d["stops"][-1]["lat"], d["stops"][-1]["lon"])
                    ),
                    CFG.town_visit.radius_km + 2.0,
                )

    def test_v2_budget_fit_says_the_raised_norm(self) -> None:
        trip = plan(
            {
                "origin": MSK,
                "destination": KAZAN,
                "crew": KIDS,
                "dailyKm": 300,
                "budget": 40000,
                "mood": "fun",
            }
        )
        self.check_k1(trip)
        fit = trip["budgetFit"]
        raised = [x for x in fit["levers"] if x["code"] == "fewer_nights"]
        if raised:
            self.assertEqual(trip["input"]["dailyKm"], raised[0]["dailyKm"])
            self.assertIn(f"норму подняли с 300 до {raised[0]['dailyKm']} км в день", fit["textRu"])
            for r in trip["reasons"]["overnights"]:  # «Ваши 350 км» would be the fitter's, not the user's
                self.assertNotIn(f"Ваши {trip['input']['dailyKm']} км", r["text"])
        if any(x["code"] == "sights_free" for x in fit["levers"]):  # K1 c: curated free or open spaces only
            from verst_planner.domain import codec

            norm = codec.normalized_from_json(trip["input"])
            for s in self.added_sights(trip):
                self.assertTrue(lever_free_ok(self.world.places[s["placeId"]], norm), s["name"])

    def test_k3_dog_weekend_yaroslavl(self) -> None:
        trip = plan(
            {
                "origin": MSK,
                "destination": YAR,
                "roundTrip": True,
                "crew": {"adults": 2, "dog": True},
                "dailyKm": 300,
                "budget": 25000,
                "mood": "fun",
            }
        )
        self.check_k1(trip)
        for s in self.added_sights(trip):
            self.assertFalse(dog_closed(self.world.places[s["placeId"]]), s["name"])
            for a in s["alternatives"]:
                self.assertFalse(dog_closed(self.world.places[a["placeId"]]), a["name"])

    def test_m2_last_fuel_only_on_the_last_day(self) -> None:
        trip = plan(
            {
                "origin": MSK,
                "readyRouteId": "rr_golden_ring",
                "crew": {"adults": 2, "children": 2},
                "dailyKm": 300,
                "budget": 40000,
                "mood": "fun",
            }
        )
        last = len(trip["daysList"])
        for s in stops(trip, "fuel"):
            if s["reason"].startswith("Последняя заправка до дома"):
                self.assertEqual(s["day"], last, s["name"])

    def test_k3_v3_dog_walk_moscow(self) -> None:
        mobile.set_clock("2026-11-07T10:00+03:00")
        r = json.loads(
            mobile.city_route(
                "russia_v1",
                "b1w",
                json.dumps(
                    {
                        "start": {"lat": 55.7558, "lon": 37.6173, "label": "Красная площадь"},
                        "preset": "dog_walk",
                        "crew": {"adults": 2, "dog": True},
                    }
                ),
            )
        )
        self.assertTrue(r["ok"], r)
        kinds = {s["kind"] for s in r["result"]["stops"] if s["kind"] != "meal"}
        self.assertLessEqual(kinds, {"park", "nature", "embankment", "viewpoint", "square"})
        names = {s["nameRu"] for s in r["result"]["stops"]}
        self.assertFalse(names & {"ГУМ", "Мавзолей Ленина", "Царь-пушка"}, names)

    def test_b1_tolls_on_the_road_model(self) -> None:
        spb = {"lat": 59.93, "lon": 30.3, "label": "Санкт-Петербург"}
        base = {
            "origin": MSK,
            "destination": spb,
            "crew": {"adults": 2},
            "dailyKm": 900,
            "startAt": "2026-11-02T08:00",
        }
        trip = plan(base, "2026-10-28T10:00+03:00")
        self.assertTrue(trip["approxDistances"])
        tolls = next(x for x in trip["cost"]["lines"] if x["key"] == "tolls")
        self.assertGreater(tolls["rub"], 4000)
        self.assertIn("М-11 (примерно)", tolls["formula"])
        avoid = plan({**base, "avoidTolls": True}, "2026-10-28T10:00+03:00")
        free = next(x for x in avoid["cost"]["lines"] if x["key"] == "tolls")
        self.assertEqual((free["rub"], free["formula"]), (0, "платных дорог нет"))
        self.assertLess(avoid["cost"]["totalRub"], trip["cost"]["totalRub"])
        ekb = plan(
            {**base, "destination": {"lat": 56.8389, "lon": 60.6057, "label": "Екатеринбург"}},
            "2026-10-28T10:00+03:00",
        )
        unknown = next(x for x in ekb["cost"]["lines"] if x["key"] == "tolls")
        self.assertEqual(unknown["formula"], "не учтены: маршрут приближённый")

    def test_b4_time_never_goes_back(self) -> None:
        """Уфа → Казань crosses МСК+2 → МСК: a day's times are on the clock of its start, the local time
        is said at the first stop in the new zone and the warning names the day."""
        trip = plan(
            {
                "origin": {"lat": 54.7261, "lon": 55.9475, "label": "Уфа"},
                "destination": KAZAN,
                "crew": {"adults": 2},
                "dailyKm": 500,
            }
        )
        for d in trip["daysList"]:
            times = [t for s in d["stops"] for t in (s["arriveAt"], s["departAt"]) if t]
            self.assertEqual(times, sorted(times), f"day {d['day']}")
            self.assertTrue(all(s["tz"] == d["tz"] for s in d["stops"]))
        local = [s for s in stops(trip) if s.get("localTz")]
        self.assertTrue(local)
        self.assertIn("По местному времени", local[0]["reason"])
        self.assertIn("TIME_ZONE", [w["code"] for w in trip["warnings"]])


if __name__ == "__main__":
    unittest.main()
