"""CEO 03.11: roadside cafés for lunch («придорожные кафе вполне сносны»), but with a child only when the
crew said so («для маршрута с ребёнком надо в явном виде спрашивать»: a roadside café may lack a toilet)."""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest import mock

from tests.unit.test_mobile import call, load_worlds
from verst_planner import mobile
from verst_planner.catalogue import CatRoadside, load_packaged_roadside
from verst_planner.domain.model import Crew, LatLon, RouteRequest, roadside_food_default

R = "russia_v1"
MSK = {"lat": 55.7558, "lon": 37.6173, "label": "Москва"}
KZN = {"lat": 55.7963, "lon": 49.1088, "label": "Казань"}
TEST_ID = "osm_n9900000"


def lunches(r: dict[str, Any]) -> list[str]:
    return [s.get("placeId") or "" for d in r["trip"]["daysList"] for s in d["stops"] if s["kind"] == "food"]


def plan(rid: str, **extra: Any) -> dict[str, Any]:
    inp = {"origin": MSK, "destination": KZN, "dailyKm": 500, **extra}
    return dict(call(mobile.plan(R, rid, json.dumps(inp), None)))


class RoadsideFoodTest(unittest.TestCase):
    rows: list[CatRoadside]

    @classmethod
    def setUpClass(cls) -> None:
        load_worlds()
        call(mobile.set_clock("golden"))
        call(mobile.load_catalogue())
        # a test café every 25 km along the route line itself (no detour): the lunch has a roadside choice
        # wherever the lunch window falls
        w = mobile._WORLDS[R]
        req = RouteRequest((LatLon(MSK["lat"], MSK["lon"]), LatLon(KZN["lat"], KZN["lon"])), False)
        route = w.fakes.routing.route(req)
        cafes: list[CatRoadside] = []
        next_km = 25.0
        for pt, km in zip(route.points, route.cum_km, strict=True):
            if km >= next_km:
                cafes.append(
                    CatRoadside(
                        f"{TEST_ID}{len(cafes):03d}", f"Кафе у трассы {len(cafes)}", "cafe", pt, None,
                        frozenset(), frozenset(), True, None,
                    )
                )  # fmt: skip
                next_km = km + 25.0
        assert len(cafes) >= 20, len(cafes)
        real = {r.id: r for r in load_packaged_roadside()}
        cls.rows = list(real.values()) + cafes
        with mock.patch.object(mobile, "load_packaged_roadside", lambda: cls.rows):
            call(mobile.load_catalogue())

    @classmethod
    def tearDownClass(cls) -> None:
        call(mobile.load_catalogue())
        call(mobile.set_clock("system"))

    def test_default_follows_the_crew(self) -> None:
        self.assertTrue(roadside_food_default(Crew(2, 0, False)))
        self.assertFalse(roadside_food_default(Crew(2, 1, False)))

    def test_adults_lunch_at_a_roadside_cafe(self) -> None:
        r = plan("adults", crew={"adults": 2})
        test_lunches = [i for i in lunches(r) if i.startswith(TEST_ID)]
        self.assertTrue(test_lunches, lunches(r))
        stops = [s for d in r["trip"]["daysList"] for s in d["stops"]]
        stop = next(s for s in stops if s.get("placeId") == test_lunches[0])
        self.assertEqual("Обед в кафе у трассы, есть туалет.", stop["reason"])

    def test_child_town_cafes_only_unless_asked(self) -> None:
        child = {"adults": 2, "children": 1, "childAges": [6]}
        town_only = plan("child", crew=child)
        self.assertFalse([i for i in lunches(town_only) if i.startswith(TEST_ID)], lunches(town_only))
        self.assertNotIn("roadsideFood", town_only["trip"]["input"])  # the crew default is not echoed
        said_yes = plan("child-yes", crew=child, roadsideFood=True)
        self.assertTrue([i for i in lunches(said_yes) if i.startswith(TEST_ID)], lunches(said_yes))
        self.assertIs(True, said_yes["trip"]["input"]["roadsideFood"])

    def test_adults_may_refuse_roadside_cafes(self) -> None:
        r = plan("adults-no", crew={"adults": 2}, roadsideFood=False)
        self.assertFalse([i for i in lunches(r) if i.startswith(TEST_ID)], lunches(r))


if __name__ == "__main__":
    unittest.main()
