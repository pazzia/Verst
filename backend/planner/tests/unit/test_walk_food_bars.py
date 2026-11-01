"""CEO 2026-10-29 (build 0.3.164), walks:

- «Свой маршрут» with «Еда» walks to catalogue restaurants and cafés (OSM `catalogue_food`): no invented price
  (the stop says «цена не указана», `PRICE_UNKNOWN`), no generic «Обед» stop, the place's own category label;
- where the catalogue has no such data for the town, the walk says so («нет данных … пробел нашей базы»),
  never that the town has few places (`NOT_ENOUGH_POIS` `reason: no_data`, presets `noData`);
- «По рюмочным» walks only рюмочные and «Пивной» only beer places — no generic bars in either.

The food rows here are a small fixture injected into the loaded catalogue (the packaged catalogue gets real
OSM food places from `.github/workflows/data-osm.yml`); the bars are the packaged catalogue's.
"""

from __future__ import annotations

import itertools
import json
import unittest
from typing import Any

from tests.unit import test_mobile_v2
from tests.unit.test_mobile import call
from verst_planner import mobile
from verst_planner.catalogue import CatFood
from verst_planner.domain.model import LatLon
from verst_planner.geo.grid import GridIndex

R = "russia_v1"
YAR = {"lat": 57.6261, "lon": 39.8845, "label": "Ярославль"}
FRYAZINO = {"lat": 55.9606, "lon": 38.0456, "label": "Фрязино"}
SPB = {"lat": 59.9386, "lon": 30.3141, "label": "Санкт-Петербург"}
EAT = {"restaurant", "cafe", "fast_food", "food_court"}
# (id, name, kind, lat, lon, hours, cuisine): central Ярославль, hand-placed fixture rows
FIXTURE = (
    ("n_test_1", "Ресторан (пример) «Волжский»", "restaurant", 57.6268, 39.888, "Mo-Su 11:00-23:00", "ru"),
    ("n_test_2", "Кафе (пример) «Пирожковая»", "cafe", 57.6250, 39.8860, "Mo-Su 08:00-21:00", None),
    ("n_test_3", "Кафе (пример) у Стрелки", "cafe", 57.6225, 39.8935, None, None),
    ("n_test_4", "Чебуречная (пример)", "fast_food", 57.6280, 39.8800, "Mo-Su 10:00-22:00", "chebureki"),
)


def city_route(body: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = json.loads(mobile.city_route(R, "food", json.dumps({"durationMin": 240, **body})))
    return out


class WalkFoodAndBarsTest(unittest.TestCase):
    saved: tuple[list[CatFood], GridIndex[str] | None]

    @classmethod
    def setUpClass(cls) -> None:
        test_mobile_v2.MobileV2Test.setUpClass()
        call(mobile.set_clock("2026-10-31T11:00+03:00"))
        cat = mobile._CATALOGUE[0]
        w = mobile._WORLDS[R]
        cls.saved = (cat.food, w.food)
        yar = next(t.id for t in cat.towns if t.name == "Ярославль")
        rows = [CatFood(i, n, k, LatLon(la, lo), yar, h, c) for i, n, k, la, lo, h, c in FIXTURE]
        cat.food = [f for f in cat.food if f.town != yar] + rows
        cat.__post_init__()
        index: GridIndex[str] = GridIndex(0.05)
        for f in cat.food:
            index.add(f.point, f.id)
        w.food = index

    @classmethod
    def tearDownClass(cls) -> None:
        cat = mobile._CATALOGUE[0]
        cat.food, mobile._WORLDS[R].food = cls.saved
        cat.__post_init__()
        call(mobile.set_clock("system"))

    def test_food_walk_goes_to_food_places(self) -> None:
        r = city_route({"start": YAR, "preset": "custom", "interests": ["food", "history"]})
        self.assertTrue(r["ok"], r)
        walk = r["result"]
        eats = [s for s in walk["stops"] if s["kind"] in EAT]
        self.assertTrue(eats, [s["nameRu"] for s in walk["stops"]])
        self.assertNotIn("meal", [s["kind"] for s in walk["stops"]])  # a real place, not «Обед — кафе рядом»
        self.assertLessEqual(len(eats), 2)  # with other interests: at most one per two hours
        kinds = [s["kind"] for s in walk["stops"]]
        self.assertFalse([a for a, b in itertools.pairwise(kinds) if a in EAT and b in EAT], kinds)
        for s in eats:
            self.assertEqual((s["costRub"], s["unknownFacts"]), (0, ["price"]), s["nameRu"])  # never invented
            self.assertIn(s["poiKindRu"], ("Ресторан", "Кафе", "Фастфуд"))
            self.assertEqual(s["placeSource"], "osm")
        self.assertIn("PRICE_UNKNOWN", [x["code"] for x in walk["warnings"]])
        self.assertNotIn("food", [line["key"] for line in walk["cost"]["lines"]])
        self.assertFalse(any("нет данных" in n for n in walk["crewNotesRu"]))
        with_hours = [s for s in eats if s["poiId"] in ("n_test_1", "n_test_2", "n_test_4")]
        for s in with_hours:
            self.assertEqual(s["hours"]["source"], "osm")

    def test_food_only_walk(self) -> None:
        r = city_route({"start": YAR, "preset": "custom", "interests": ["food"]})
        self.assertTrue(r["ok"], r)
        kinds = [s["kind"] for s in r["result"]["stops"]]
        self.assertTrue(set(kinds) <= EAT, kinds)
        self.assertLessEqual(len(kinds), 3)  # FOOD_STOPS_MAX
        self.assertFalse(r["result"]["interestsWidened"])

    def _bare_town(self) -> dict[str, Any]:
        """A catalogue town with no food, рюмочные or beer rows at all (the CEO 2026-10-29 build has them for
        Фрязино): there the walk must say «нет данных», never «мест мало»."""
        cat = mobile._CATALOGUE[0]
        drinks = ("ryumochnaya", "pub", "craft")
        have = {f.town for f in cat.food} | {b.town for b in cat.bars if b.kind in drinks}
        t = next(t for t in sorted(cat.towns, key=lambda t: t.id) if t.id not in have)
        return {"lat": t.point.lat, "lon": t.point.lon, "label": t.name}

    def test_no_food_data_is_said_as_such(self) -> None:
        bare = self._bare_town()
        r = city_route({"start": bare, "preset": "custom", "interests": ["food"]})
        # a town with nothing else to walk to: the error says it; otherwise the walk's note does
        said = r["error"]["messageRu"] if not r["ok"] else " ".join(r["result"]["crewNotesRu"])
        if not r["ok"]:
            self.assertEqual((r["error"]["reason"], r["error"]["noData"]), ("no_data", ["food"]))
        self.assertIn("нет данных о ресторанах и кафе", said)
        self.assertNotIn("мест мало", said)
        both = city_route({"start": bare, "preset": "custom", "interests": ["food", "history"]})
        if both["ok"]:
            self.assertIn("нет данных о ресторанах и кафе", " ".join(both["result"]["crewNotesRu"]))

    def test_fryazino_food_walk_uses_its_real_places(self) -> None:
        """CEO 2026-10-29: «Фрязино, Еда» built a walk without one restaurant and blamed the town."""
        cat = mobile._CATALOGUE[0]
        fry = next(t.id for t in cat.towns if t.name == "Фрязино")
        if not any(f.town == fry for f in cat.food):
            self.skipTest("catalogue without OSM food places")
        r = city_route({"start": FRYAZINO, "preset": "custom", "interests": ["food"]})
        self.assertTrue(r["ok"], r)
        stops = r["result"]["stops"]
        seen = [(s["kind"], s["nameRu"]) for s in stops]
        self.assertTrue(stops and {s["kind"] for s in stops} <= EAT, seen)
        self.assertFalse(any("нет данных" in n or "мест мало" in n for n in r["result"]["crewNotesRu"]))

    def test_no_bar_data_error_and_presets(self) -> None:
        bare = self._bare_town()
        r = city_route({"start": bare, "preset": "beer", "adultConfirmed": True})
        self.assertFalse(r["ok"])
        e = r["error"]
        self.assertEqual((e["code"], e["reason"], e["noData"]), ("NOT_ENOUGH_POIS", "no_data", ["beer"]))
        self.assertIn("нет данных о пивных барах", e["messageRu"])
        presets = {p["preset"]: p for p in call(mobile.city_presets(R, bare["lat"], bare["lon"]))["presets"]}
        self.assertTrue(presets["ryumochnye"]["noData"])
        self.assertIn("нет данных о рюмочных", presets["ryumochnye"]["noDataRu"])
        self.assertFalse(presets["overview"]["noData"])

    def test_ryumochnye_and_beer_are_strict_and_differ(self) -> None:
        cat = mobile._CATALOGUE[0]
        spb = next(t.id for t in cat.towns if t.name == "Санкт-Петербург")
        have = {k for b in cat.bars if b.town == spb for k in [b.kind]}
        if not {"ryumochnaya", "pub"} <= have:
            self.skipTest("catalogue without the CEO 2026-10-29 bar kinds")
        ryu = city_route({"start": SPB, "preset": "ryumochnye", "adultConfirmed": True})
        beer = city_route({"start": SPB, "preset": "beer", "adultConfirmed": True})
        self.assertTrue(ryu["ok"] and beer["ok"], (ryu, beer))
        ryu_kinds = {s["kind"] for s in ryu["result"]["stops"]}
        beer_kinds = {s["kind"] for s in beer["result"]["stops"]}
        self.assertEqual(ryu_kinds, {"ryumochnaya"})
        self.assertTrue(beer_kinds <= {"pub", "craft"}, beer_kinds)
        ids = lambda w: {s["poiId"] for s in w["result"]["stops"]}  # noqa: E731
        self.assertFalse(ids(ryu) & ids(beer))


if __name__ == "__main__":
    unittest.main()
