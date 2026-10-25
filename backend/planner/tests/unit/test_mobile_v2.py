"""ARCH-305: the mobile API v2 (M§5.4) and its contract files `docs/contracts/v2/`."""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest import mock

from tests.contract.test_cost_recompute_contract import generated
from tests.helpers import PLANNER_ROOT
from tests.unit.test_mobile import call, fail, load_worlds
from verst_planner import mobile
from verst_planner.catalogue import CatalogueError

V2 = PLANNER_ROOT.parents[1] / "docs" / "contracts" / "v2"
R = "russia_v1"
YAR = {"lat": 57.6261, "lon": 39.8845, "label": "Ярославль"}
SPB = {"lat": 59.9386, "lon": 30.3141, "label": "Санкт-Петербург"}


def walk(**kw: Any) -> str:
    return json.dumps({"start": YAR, **kw})


class MobileV2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_worlds()
        call(mobile.set_clock("golden"))
        cls.info = call(mobile.load_catalogue())

    @classmethod
    def tearDownClass(cls) -> None:
        call(mobile.set_clock("system"))

    def test_catalogue_and_selfcheck(self) -> None:
        self.assertEqual(self.info["world"], R)
        self.assertGreater(self.info["places"], self.info["pois"])
        check = call(mobile.selfcheck())
        self.assertEqual(check["apiVersion"], 3)
        self.assertEqual(check["catalogue"]["towns"], self.info["towns"])
        self.assertIn(R, check["worlds"])

    def test_catalogue_errors(self) -> None:
        with mock.patch.object(mobile, "load_packaged", side_effect=CatalogueError("x: missing")):
            self.assertEqual(fail(mobile.load_catalogue())["code"], "NO_CATALOGUE")
        saved = mobile._WORLDS.pop("central_russia_v1")
        try:
            self.assertEqual(fail(mobile.load_catalogue())["code"], "NO_WORLD")
        finally:
            mobile._WORLDS["central_russia_v1"] = saved

    def test_geo_search(self) -> None:
        rows = call(mobile.geo_search(R, "Санкт", 55.75, 37.61, 5))
        self.assertEqual((rows[0]["kind"], rows[0]["name"]), ("city", "Санкт-Петербург"))
        self.assertEqual(rows[0]["nameGenRu"], "Санкт-Петербурга")
        pois = call(mobile.geo_search(R, "Эрми", 59.93, 30.31, 5, '["poi"]'))
        self.assertTrue(pois and all(r["kind"] == "poi" for r in pois))
        self.assertEqual(pois[0]["poiKind"], "museum")
        towns_only = call(mobile.geo_search("central_russia_v1", "Яро", None, None, 5, '["city"]'))
        self.assertEqual([r["name"] for r in towns_only], ["Ярославль"])
        self.assertEqual(fail(mobile.geo_search(R, "x", None, None, 5, '["shop"]'))["code"], "INVALID_INPUT")

    def test_geo_nearest(self) -> None:
        r = call(mobile.geo_nearest(R, 57.6205, 39.873))
        self.assertEqual(r["town"]["name"], "Ярославль")
        self.assertTrue(r["insideRussia"])
        self.assertEqual(call(mobile.geo_nearest("central_russia_v1", 55.75, 37.6))["town"]["id"], "t_moscow")
        self.assertFalse(call(mobile.geo_nearest(R, 48.85, 2.35))["insideRussia"])
        self.assertEqual(fail(mobile.geo_nearest(R, None, None))["code"], "INVALID_INPUT")  # type: ignore[arg-type]

    def test_plan_and_estimate_v2_fields(self) -> None:
        inp = json.dumps(
            {
                "origin": SPB,
                "destination": {"lat": 58.0105, "lon": 56.2502, "label": "Пермь"},
                "crew": {"adults": 2},
                "dailyKm": 500,
            }
        )
        r = call(mobile.plan(R, "v2-p", inp, None))
        self.assertEqual(r["outcome"], "plan")
        self.assertTrue(r["trip"]["approxDistances"])
        est = call(mobile.estimate(R, "v2-e", inp))
        self.assertEqual(
            (est["outcome"], est["km"], est["totalRub"]),
            ("plan", r["trip"]["km"], r["trip"]["cost"]["totalRub"]),
        )
        graph = call(
            mobile.plan(
                R,
                "v2-g",
                json.dumps(
                    {
                        "origin": {"lat": 55.7558, "lon": 37.6173},
                        "destination": YAR,
                        "crew": {"adults": 2},
                        "dailyKm": 500,
                    }
                ),
                None,
            )
        )
        self.assertNotIn("approxDistances", graph["trip"])

    def test_city_presets_and_routes(self) -> None:
        presets = {p["preset"]: p for p in call(mobile.city_presets(R, YAR["lat"], YAR["lon"]))["presets"]}
        self.assertTrue(presets["overview"]["available"])
        self.assertTrue(presets["ryumochnye"]["adultOnly"])
        r = call(mobile.city_route(R, "v2-w1", walk(preset="overview")))
        self.assertEqual((r["kind"], r["townName"]), ("walk", "Ярославль"))
        self.assertGreaterEqual(len(r["stops"]), 2)
        again = call(mobile.city_route(R, "v2-w1", walk(preset="overview")))
        self.assertEqual(json.dumps(r, ensure_ascii=False), json.dumps(again, ensure_ascii=False))
        other = call(mobile.city_route(R, "v2-w2", walk(preset="overview", exclude=[r["stops"][0]["poiId"]])))
        self.assertNotIn(r["stops"][0]["poiId"], [s["poiId"] for s in other["stops"]])
        bars = call(mobile.city_route(R, "v2-w3", walk(preset="ryumochnye", adultConfirmed=True)))
        self.assertTrue(bars["startAt"].endswith("18:00"))
        self.assertIsNotNone(bars["responsibleNoteRu"])

    def test_city_errors(self) -> None:
        self.assertEqual(fail(mobile.city_route(R, "e1", walk(preset="beer")))["field"], "adultConfirmed")
        far = json.dumps({"start": {"lat": 61.5, "lon": 90.0}, "preset": "overview"})
        self.assertEqual(fail(mobile.city_route(R, "e2", far))["code"], "NO_CITY")
        dry = json.dumps({"start": self._town_without_bars(), "preset": "beer", "adultConfirmed": True})
        self.assertEqual(fail(mobile.city_route(R, "e3", dry))["code"], "NOT_ENOUGH_POIS")
        self.assertEqual(fail(mobile.city_route(R, "e4", "[]"))["code"], "INVALID_INPUT")
        self.assertEqual(
            fail(mobile.city_route(R, "e5", json.dumps({"preset": "overview"})))["field"], "start"
        )
        unknown = walk(preset="overview", townId="Q0")
        self.assertEqual(fail(mobile.city_route(R, "e6", unknown))["code"], "NOT_FOUND")
        call(mobile.cancel("e7"))
        self.assertEqual(fail(mobile.city_route(R, "e7", walk()))["code"], "CANCELLED")
        self.assertEqual(fail(mobile.city_presets(R, None, None))["code"], "INVALID_INPUT")  # type: ignore[arg-type]

    def test_area_photos_are_single_photographs(self) -> None:
        """S3-FINAL P1-04 (5.9 §3): no area photo is a collage, map, flag, coat of arms or blocked file."""
        import re

        from verst_planner.adapters.catalogue import CataloguePorts

        w = mobile._WORLDS[R]
        self.assertIsInstance(w.fakes, CataloguePorts)
        cat = mobile._CATALOGUE[0]
        words = re.compile(
            r"collage|colage|montage|коллаж|\bmaps?\b|карта|\bflags?\b|флаг|coat of arms|герб"
            r"|\.(svg|png|gif)$",
            re.I,
        )
        kept = 0
        for t in w.world.towns.values():
            file, _credit = mobile._area_photo(w, t)
            if file is None:
                continue
            kept += 1
            with self.subTest(town=t.name_ru, file=file):
                self.assertNotIn(file, cat.area_blocked)
                self.assertIsNone(words.search(file))
        if cat.version != "sample":
            self.assertTrue(cat.area_blocked)
            self.assertGreaterEqual(kept, 900)  # 971 of 1 116 in wd-20261025-r7.2

    @staticmethod
    def _town_without_bars() -> dict[str, float]:
        from verst_planner.geo.distance import haversine_km

        cat = mobile._CATALOGUE[0]
        for t in sorted(cat.towns, key=lambda t: (t.population, t.id)):
            if t.population >= 5000 and all(haversine_km(t.point, b.point) > 6 for b in cat.bars):
                return {"lat": t.point.lat, "lon": t.point.lon}
        raise AssertionError("no town without bars")

    def test_poi_details(self) -> None:
        sight = call(mobile.poi_details(R, "pl_yar_ilya"))
        self.assertEqual((sight["kind"], sight["isFictional"]), ("sight", False))
        hotel = call(mobile.poi_details(R, "pl_yar_hotel_strelka"))
        self.assertTrue(hotel["isFictional"])
        if hotel["image"] is not None:
            self.assertTrue(hotel["image"]["isArea"])
            self.assertIn("Фото района", hotel["image"]["labelRu"])
        cat = mobile._CATALOGUE[0]
        bar = call(mobile.poi_details(R, cat.bars[0].id))
        self.assertEqual(bar["kind"], "bar")
        self.assertIn("© участники OpenStreetMap", bar["attributionRu"])
        with_photo = next(p for p in cat.pois if p.image and p.credit is not None)
        card = call(mobile.poi_details(R, with_photo.id))
        self.assertTrue(
            card["image"]["card"].startswith("https://commons.wikimedia.org/wiki/Special:FilePath/")
        )
        self.assertTrue(card["image"]["card"].endswith("?width=800"))
        self.assertIn("Wikimedia Commons", card["image"]["labelRu"])
        self.assertEqual(fail(mobile.poi_details(R, "pl_m8_fuel_022"))["code"], "NOT_FOUND")
        plain = call(mobile.poi_details("central_russia_v1", "pl_yar_ilya"))
        self.assertIsNone(plain["wikidataId"])

    def test_handoff(self) -> None:
        trip = call(
            mobile.plan(
                R,
                "h1",
                json.dumps(
                    {
                        "origin": {"lat": 55.7558, "lon": 37.6173},
                        "destination": YAR,
                        "crew": {"adults": 2},
                        "dailyKm": 500,
                    }
                ),
                None,
            )
        )["trip"]
        r = call(mobile.handoff(R, json.dumps(trip), json.dumps({"mode": "car", "day": 1})))
        self.assertTrue(r["parts"][0]["links"]["navigator"].startswith("yandexnavi://build_route_on_map?"))
        self.assertEqual(
            fail(mobile.handoff(R, json.dumps(trip), json.dumps({"mode": "x"})))["field"], "mode"
        )
        self.assertEqual(fail(mobile.handoff(R, "[]", "{}"))["code"], "INVALID_INPUT")
        self.assertEqual(
            fail(
                mobile.handoff(
                    R,
                    json.dumps({"daysList": [{"day": 1, "stops": [{}]}]}),
                    json.dumps({"mode": "car", "fromStopId": None, "day": 1}),
                )
            )["code"],
            "INVALID_INPUT",
        )


class ContractsV2Test(unittest.TestCase):
    def test_generator_matches_committed_files(self) -> None:
        try:
            out = generated("gen_api_contracts.py")["GENERATED"]
        finally:
            mobile.set_clock("system")
        committed = {p.name: p.read_text("utf-8") for p in sorted(V2.iterdir())}
        self.assertEqual(sorted(out), sorted(committed))
        for name, text in out.items():
            with self.subTest(name):
                self.assertEqual(text, committed[name])
        index = json.loads(committed["index.json"])
        self.assertEqual(index["apiVersion"], mobile.API_VERSION)


if __name__ == "__main__":
    unittest.main()
