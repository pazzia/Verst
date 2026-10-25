"""Sprint 4 extra-source fetchers: the pure parsing helpers on recorded-shape responses (no network)."""

from __future__ import annotations

import json
import unittest
from typing import Any

from tests.unit.test_data_fetchers import lit, load

E = "http://www.wikidata.org/entity/"


class ExtrasTest(unittest.TestCase):
    x = load("fetch_extras")

    def test_roots_check_and_tree(self) -> None:
        ok = [{"c": lit(E + q), "label": lit(kw[0])} for q, (_g, _l, kw) in self.x.ROOTS.items()]
        self.assertTrue(self.x.check_roots(ok)["ok"])
        bad = self.x.check_roots(ok[1:])
        self.assertEqual(list(bad["mismatches"]), [next(iter(self.x.ROOTS))])
        doc = self.x.tree_doc({"Q3914": "Q9"}, {"Q9": ["Q10"], "Q16970": ["Q11"]})
        self.assertIn("Q9", doc["groups"]["exclude"])
        self.assertIn("Q10", doc["groups"]["exclude"])
        self.assertNotIn("Q3914", doc["groups"]["exclude"])
        self.assertIn("Q11", doc["groups"]["religious"])

    def test_extra_from_bindings(self) -> None:
        rows = [
            {"item": lit(E + "Q1"), "p31": lit(E + "Q16970"), "hLabel": lit("объект федерального значения")},
            {
                "item": lit(E + "Q1"),
                "p31": lit(E + "Q2977"),
                "ruTitle": lit("Собор"),
                "voyTitle": lit("Город"),
            },
            {"item": lit(E + "Q2")},
        ]
        out = self.x.extra_from_bindings(rows)
        self.assertEqual(out["Q1"]["p31"], ["Q16970", "Q2977"])
        self.assertEqual(out["Q1"]["heritage"], ["объект федерального значения"])
        self.assertEqual((out["Q1"]["ruwiki"], out["Q1"]["ruvoyage"]), ("Собор", "Город"))
        self.assertEqual(out["Q2"], {"p31": [], "heritage": [], "ruwiki": None, "ruvoyage": None})

    def test_wiki_pages(self) -> None:
        doc = {
            "query": {
                "normalized": [{"from": "собор", "to": "Собор"}],
                "redirects": [{"from": "Собор", "to": "Собор (Москва)"}],
                "pages": [
                    {"title": "Собор (Москва)", "extract": "Собор — храм. ", "pageimage": "A.jpg"},
                    {"title": "Нет", "missing": True},
                ],
            }
        }
        self.assertEqual(self.x.wiki_pages(doc), {"собор": {"extract": "Собор — храм.", "image": "A.jpg"}})

    def test_voyage_listings(self) -> None:
        text = (
            "== Достопримечательности ==\n"
            "* {{listing|type=see|name=Кремль|wikidata=Q1|content=Главная [[крепость]] города|hours=10-18}}\n"
            "* {{Достопримечательность|название=Музей|wikidata=Q2|описание=Музей купечества}}\n"
            "* {{listing|name=Без|wikidata=}}\n"
        )
        out = self.x.voyage_from_texts([text])
        self.assertEqual(sorted(out), ["Q1", "Q2"])
        self.assertEqual(out["Q1"]["templates"], ["see"])
        self.assertEqual(out["Q1"]["text"], "Главная крепость города")
        self.assertEqual(out["Q1"]["hours"], "10-18")
        self.assertEqual(out["Q2"]["text"], "Музей купечества")

    def test_osm_features_and_geo_targets(self) -> None:
        def f(fid: str, lon: float, lat: float, **tags: Any) -> str:
            g = {"type": "Point", "coordinates": [lon, lat]}
            return json.dumps({"type": "Feature", "id": fid, "geometry": g, "properties": tags})

        lines = [
            f("n1", 37.6, 55.7, name="Парк", leisure="park", opening_hours="Mo-Su 08:00-22:00", foo="x"),
            f("n2", 37.6, 55.7, leisure="playground"),
            f("n3", 37.6, 55.7, amenity="parking", fee="yes", charge="100 RUB/hour"),
            f("n4", 37.6, 55.7, amenity="parking", fee="no"),
            f("n5", 37.6, 55.7, tourism="viewpoint"),  # unnamed, not a playground: dropped
        ]
        pois, parking = self.x.osm_from_features(lines)
        self.assertEqual([p["osm"] for p in pois], ["n1", "n2"])
        self.assertNotIn("foo", pois[0]["tags"])
        self.assertEqual([(p["osm"], p["charge"]) for p in parking], [("n3", "100 RUB/hour")])
        raw_pois = [
            {"qid": "Q1", "lat": 1, "lon": 2, "sitelinks": 3, "image": None},
            {"qid": "Q2", "lat": 1, "lon": 2, "sitelinks": 9, "image": "x.jpg"},
            {"qid": "Q3", "lat": 1, "lon": 2, "sitelinks": 5},
        ]
        osm = [{"osm": "n9", "lat": 1, "lon": 2, "tags": {"name": "Скала", "natural": "rock"}}]
        self.assertEqual([t["id"] for t in self.x.geo_targets(raw_pois, osm, 10)], ["Q3", "Q1", "n9"])
        self.assertEqual(len(self.x.geo_targets(raw_pois, osm, 1)), 1)

    def test_misplaced_poi(self) -> None:
        b = load("build_catalogue")
        by_name = {"москва": [(55.75, 37.62)]}
        self.assertTrue(
            b.misplaced({"name": "Памятник Чернышевскому (Москва)", "lat": 56.27, "lon": 38.09}, by_name)
        )
        self.assertFalse(
            b.misplaced({"name": "Памятник Пушкину (Москва)", "lat": 55.76, "lon": 37.60}, by_name)
        )
        self.assertFalse(b.misplaced({"name": "Дом (Нигде)", "lat": 56.27, "lon": 38.09}, by_name))
        self.assertFalse(b.misplaced({"name": "Собор", "lat": 56.27, "lon": 38.09}, by_name))

    def test_geosearch_pick_names_the_place(self) -> None:
        e = load("enrich")
        files = ["Дом № 102 по улице Шевченко (Шахты).jpg", "Памятник Тарасу Шевченко в Шахтах.jpg"]
        self.assertEqual(e.geosearch_pick("Памятник Тарасу Шевченко", files, {}), files[1])
        self.assertIsNone(e.geosearch_pick("Памятник Тарасу Шевченко", files[:1], {}))
        town = ["Прокуратура ЦАО в Тюмени (2).jpg"]
        self.assertIsNone(e.geosearch_pick("Аптекарский сад (Тюмень)", town, {}))  # the town is not the place
        self.assertIsNone(e.geosearch_pick("Лазаревская башня", ["Башня Волкова. Смоленск.jpg"], {}))
        small = {"Орлёнок.jpg": {"mime": "image/jpeg", "w": 640}}
        self.assertIsNone(e.geosearch_pick("Орлёнок", ["Орлёнок.jpg"], small))
        self.assertEqual(
            e.geosearch_pick("Памятник Курчатову", ["Памятник Курчатову f010.jpg"], {}),
            "Памятник Курчатову f010.jpg",
        )
        self.assertIsNone(
            e.geosearch_pick("Церковь", ["Церковь.jpg"], {})
        )  # a class word alone names nothing

    def test_osm_names_and_excludes(self) -> None:
        e = load("enrich")
        self.assertTrue(e.osm_name_ok("Детская площадка", "playground", {}))
        self.assertFalse(e.osm_name_ok("Набережная", "embankment", {}))
        self.assertFalse(e.osm_name_ok("马占山历史陈列馆", "museum", {}))
        self.assertFalse(e.osm_name_ok("Учебный склон 1", "nature", {"natural": "slope"}))
        self.assertFalse(e.osm_name_ok("Сопка Сапёрная", "nature", {"natural": "peak"}))
        self.assertTrue(e.osm_name_ok("Водопад Кивач", "nature", {"natural": "waterfall"}))
        self.assertTrue(e.osm_name_ok("Новый парк", "park", {}))
        for bad in (
            "Амурская улица 201А",
            "Главный дом (фундамент)",
            "Кафе «Белоснежка»",
            "Особняк",
            "Дом жилой",
        ):
            self.assertTrue(e.NOT_A_SIGHT.search(bad), bad)
        for good in ("Особняк Морозова", "Памятник борцам революции 1905 года", "Музей хлеба"):
            self.assertFalse(e.NOT_A_SIGHT.search(good), good)
        b = load("build_catalogue")
        self.assertIsNone(b.website({"website": "https://link.2gis.ru/4.3/x"}, ["2gis"]))
        self.assertIsNone(b.website({"website": "museum.ru"}, []))
        self.assertEqual(b.website({"website": " https://museum.ru "}, []), "https://museum.ru")

    def test_commons_names(self) -> None:
        self.assertEqual(self.x.commons_name("File:Abc_def.jpg"), "Abc def.jpg")
        self.assertEqual(self.x.commons_name("https://commons.wikimedia.org/wiki/File:X_y.jpg"), "X y.jpg")
        self.assertIsNone(self.x.commons_name("https://example.org/a.jpg"))
        self.assertIsNone(self.x.commons_name(None))


if __name__ == "__main__":
    unittest.main()
