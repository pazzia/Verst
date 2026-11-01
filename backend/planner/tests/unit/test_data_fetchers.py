"""ARCH-302: the pure parts of the CI data fetchers, on recorded-shape responses (no network)."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any, ClassVar

from tests.helpers import PLANNER_ROOT

DATA = PLANNER_ROOT / "tools" / "data"


def load(name: str) -> ModuleType:
    sys.path.insert(0, str(DATA))
    spec = importlib.util.spec_from_file_location(name, DATA / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def lit(v: Any) -> dict[str, Any]:
    return {"value": v}


class WikidataTest(unittest.TestCase):
    wd = load("fetch_wikidata")

    def test_point_and_files(self) -> None:
        self.assertEqual(self.wd.parse_point("Point(37.6173 55.7558)"), (55.7558, 37.6173))
        self.assertIsNone(self.wd.parse_point("nonsense"))
        self.assertEqual(
            self.wd.commons_file("http://commons.wikimedia.org/wiki/Special:FilePath/Moscow%20July_2011.jpg"),
            "Moscow July 2011.jpg",
        )
        self.assertIsNone(self.wd.commons_file(None))

    def test_class_check(self) -> None:
        ok = [
            {"c": lit(f"http://www.wikidata.org/entity/{q}"), "label": lit(keys[0])}
            for q, keys in self.wd.EXPECT.items()
        ]
        self.assertTrue(self.wd.class_check(ok)["ok"])
        bad = [
            *ok[:-1],
            {"c": lit("http://www.wikidata.org/entity/Q570116"), "label": lit("railway station")},
        ]
        report = self.wd.class_check(bad)
        self.assertFalse(report["ok"])
        self.assertEqual(report["mismatches"], {"Q570116": "railway station"})

    def test_resolve_classes(self) -> None:
        e = "http://www.wikidata.org/entity/"
        rows = {
            "кремль": [{"c": lit(e + "Q5"), "n": lit("40")}, {"c": lit(e + "Q4"), "n": lit("40")}],
            "набережная": [{"c": lit(e + "Q1851368"), "n": lit("3")}],
        }
        asked: list[str] = []

        def query(q: str) -> list[dict[str, Any]]:
            label = q.split('"')[1]
            asked.append(label)
            return rows.get(label, [])

        report = {"mismatches": {"Q263274": "kremlin?", "Q1851368": "x", "Q999": "y"}}
        self.assertEqual(self.wd.resolve_classes(report, query), {"Q263274": "Q4"})  # tie → smaller id
        self.assertEqual(
            asked, ["набережная", "кремль"]
        )  # sorted ids: Q1851368 < Q263274  # Q999 has no ru label
        self.assertIsNone(self.wd.pick_resolved([{"c": lit(e + "Q1"), "n": lit("0")}]))
        # the default country is Russia (CEO 29.10: the template takes the country of the run)
        self.assertIn("wdt:P17 wd:Q159", self.wd.Q_RESOLVE.format(label="кремль", country=self.wd.COUNTRY))

    def test_towns_aggregate(self) -> None:
        e = "http://www.wikidata.org/entity/"
        rows = [
            {
                "town": lit(e + "Q2"),
                "townLabel": lit("Ярославль"),
                "coord": lit("Point(39.88 57.62)"),
                "pop": lit("590000"),
                "popDate": lit("2010-01-01T00:00:00Z"),
                "iso": lit("RU-YAR"),
                "regionLabel": lit("Ярославская область"),
            },
            {
                "town": lit(e + "Q2"),
                "townLabel": lit("Ярославль"),
                "coord": lit("Point(39.88 57.62)"),
                "pop": lit("570000"),
                "popDate": lit("2021-01-01T00:00:00Z"),
                "iso": lit("RU-YAR"),
                "image": lit("http://x/Special:FilePath/B.jpg"),
            },
            {
                "town": lit(e + "Q2"),
                "townLabel": lit("Ярославль"),
                "coord": lit("Point(39.88 57.62)"),
                "image": lit("http://x/Special:FilePath/A.jpg"),
            },
            {"town": lit(e + "Q3"), "townLabel": lit("Q3"), "coord": lit("Point(1 2)")},  # no ru label
            {
                "town": lit(e + "Q4"),
                "townLabel": lit("Город"),
                "coord": lit("Point(1 2)"),
                "iso": lit("UA-43"),
            },
        ]
        towns = self.wd.towns_from_bindings(rows)
        self.assertEqual([t["qid"] for t in towns], ["Q2", "Q4"])
        y = towns[0]
        self.assertEqual((y["population"], y["regionIso"], y["image"]), (570000, "RU-YAR", "A.jpg"))
        self.assertIsNone(towns[1]["regionIso"])

    def test_pois_aggregate_and_radius(self) -> None:
        e = "http://www.wikidata.org/entity/"
        rows = [
            {
                "item": lit(e + "Q10"),
                "itemLabel": lit("Музей"),
                "coord": lit("Point(30.3 59.9)"),
                "root": lit(e + "Q33506"),
                "sitelinks": lit("40"),
                "heritage": lit(e + "Q1"),
            },
            {
                "item": lit(e + "Q10"),
                "itemLabel": lit("Музей"),
                "coord": lit("Point(30.3 59.9)"),
                "root": lit(e + "Q570116"),
                "sitelinks": lit("40"),
            },
            {
                "item": lit(e + "Q11"),
                "itemLabel": lit("Q11"),
                "coord": lit("Point(30.3 59.9)"),
                "root": lit(e + "Q33506"),
            },
        ]
        pois = self.wd.pois_from_bindings(rows, "Q656")
        self.assertEqual(len(pois), 1)
        self.assertEqual(
            (pois[0]["roots"], pois[0]["heritage"], pois[0]["townQid"]), (["Q33506", "Q570116"], True, "Q656")
        )
        self.assertEqual(self.wd.radius_for({"name": "Москва", "population": 1}), 15.0)
        self.assertEqual(self.wd.radius_for({"name": "x", "population": 50_000}), 4.0)
        self.assertIn("wikibase:around", self.wd.Q_POIS)


class OverpassTest(unittest.TestCase):
    op = load("fetch_overpass")

    def test_towns_and_elements(self) -> None:
        towns = [
            {"qid": "A", "name": "a", "population": 200_000},
            {"qid": "B", "name": "b", "population": 5_000},
            {"qid": "C", "name": "c", "population": 5_000},
        ]
        pois = [{"townQid": "B", "sitelinks": 90}]
        self.assertEqual([t["qid"] for t in self.op.towns_to_query(towns, pois)], ["A", "B"])
        self.assertEqual(self.op.radius_m({"population": 2_000_000}), 9000)
        els = [
            {"type": "node", "id": 5, "lat": 1.0, "lon": 2.0, "tags": {"name": "Бар", "amenity": "bar"}},
            {"type": "way", "id": 6, "center": {"lat": 3.0, "lon": 4.0}, "tags": {"name": "Паб"}},
            {"type": "relation", "id": 7, "tags": {}},
        ]
        bars = self.op.bars_from_elements(els, "A")
        self.assertEqual([(b["osm"], b["lat"]) for b in bars], [("n5", 1.0), ("w6", 3.0)])

    def test_assign_country_wide(self) -> None:
        towns = [
            {"qid": "A", "name": "a", "population": 2_000_000, "lat": 55.75, "lon": 37.62},  # 9 km
            {"qid": "B", "name": "b", "population": 150_000, "lat": 55.80, "lon": 37.70},  # 4 km
            {"qid": "C", "name": "c", "population": 150_000, "lat": 59.0, "lon": 30.0},
        ]
        els = [
            {"type": "node", "id": 1, "lat": 55.751, "lon": 37.621, "tags": {"name": "x"}},  # A only
            {"type": "node", "id": 2, "lat": 55.799, "lon": 37.699, "tags": {"name": "y"}},  # B nearer
            {"type": "node", "id": 3, "lat": 56.5, "lon": 37.6, "tags": {"name": "z"}},  # nobody's
            {"type": "way", "id": 4, "center": {"lat": 59.01, "lon": 30.01}, "tags": {"name": "w"}},
        ]
        got = [(b["osm"], b["townQid"]) for b in self.op.assign(els, towns)]
        self.assertEqual(got, [("n1", "A"), ("n2", "B"), ("w4", "C")])
        self.assertIn('"ISO3166-1"="RU"', self.op.QUERY_ALL)


class ExtractTest(unittest.TestCase):
    ex = load("bars_from_extract")

    def test_features(self) -> None:
        def f(fid: str, geom: dict[str, Any], **tags: Any) -> str:
            return "\x1e" + json.dumps({"type": "Feature", "id": fid, "geometry": geom, "properties": tags})

        lines = [
            f("n1", {"type": "Point", "coordinates": [37.6, 55.7]}, name="Бар", amenity="bar"),
            f("w2", {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2]]]}, name="Паб"),
            f("r3", {"type": "MultiPolygon", "coordinates": [[[[10, 10], [12, 12]]]]}, name="Пивоварня"),
            f("n4", {"type": "Point", "coordinates": [1, 1]}, amenity="pub"),  # no name
            f("x5", {"type": "Point", "coordinates": [1, 1]}, name="?"),
            # CEO 31.10: a bar drawn as its building is an osmium area: a246 = way 123, a91 = relation 45
            f("a246", {"type": "Polygon", "coordinates": [[[4, 4], [6, 4], [6, 6], [4, 6]]]}, name="Бар-дом"),
            f("a91", {"type": "MultiPolygon", "coordinates": [[[[8, 8], [9, 9]]]]}, name="Рюмочная"),
            # the same way 2 again as an area: the first feature of an object wins
            f("a4", {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2]]]}, name="Паб"),
            "",
        ]
        els = self.ex.elements_from_features(lines)
        got = [(e["type"], e["id"]) for e in els]
        self.assertEqual(got, [("node", 1), ("way", 2), ("relation", 3), ("way", 123), ("relation", 45)])
        self.assertEqual((els[1]["lat"], els[1]["lon"]), (1.0, 1.0))
        self.assertEqual((els[2]["lat"], els[2]["lon"]), (11.0, 11.0))
        self.assertEqual(els[0]["tags"], {"name": "Бар", "amenity": "bar"})


class FoodExtractTest(unittest.TestCase):
    """CEO 2026-10-29: food places from the same Geofabrik extract as the bars, for every catalogue town."""

    fe = load("food_from_extract")
    op = load("fetch_overpass")

    def test_food_features(self) -> None:
        def f(fid: str, lon: float, lat: float, **tags: Any) -> str:
            geom = {"type": "Point", "coordinates": [lon, lat]}
            return "\x1e" + json.dumps({"type": "Feature", "id": fid, "geometry": geom, "properties": tags})

        lines = [
            f("n1", 38.05, 55.96, name="Кафе", amenity="cafe", cuisine="russian", website="https://x"),
            f("n2", 38.05, 55.96, name="Бургерная", amenity="fast_food", brand="Пример", phone="1"),
            f("n3", 38.05, 55.96, amenity="restaurant"),  # no name
            f("n4", 38.05, 55.96, name="Бар", amenity="bar"),  # not food
        ]
        els = self.fe.food_from_features(lines)
        self.assertEqual([e["id"] for e in els], [1, 2])
        self.assertEqual(els[0]["tags"], {"amenity": "cafe", "name": "Кафе", "cuisine": "russian"})
        self.assertEqual(els[1]["tags"]["brand"], "Пример")

    def test_every_town_is_assigned(self) -> None:
        """Фрязино (60 000 people) gets its own places; the big-town Overpass pick would have skipped it."""
        towns = [
            {"qid": "FRY", "name": "Фрязино", "population": 60_000, "lat": 55.9606, "lon": 38.0456},
            {"qid": "SHL", "name": "Щёлково", "population": 130_000, "lat": 55.9233, "lon": 37.9786},
            {"qid": "V", "name": "деревня", "population": 300, "lat": 55.99, "lon": 38.10},
        ]
        pick = self.op.all_towns(towns)
        self.assertEqual([t["qid"] for t in pick], ["SHL", "FRY"])
        self.assertEqual(self.op.radius_all_m({"population": 900}), 2500)
        self.assertEqual(self.op.radius_all_m({"population": 60_000}), 4000)
        els = [
            {"type": "node", "id": 1, "lat": 55.962, "lon": 38.047, "tags": {"name": "a"}},  # Фрязино
            {"type": "node", "id": 2, "lat": 55.924, "lon": 37.980, "tags": {"name": "b"}},  # Щёлково
            {"type": "node", "id": 3, "lat": 55.99, "lon": 38.10, "tags": {"name": "c"}},  # nobody's
        ]
        got = [(b["osm"], b["townQid"]) for b in self.op.assign(els, pick, self.op.radius_all_m)]
        self.assertEqual(got, [("n1", "FRY"), ("n2", "SHL")])

    def test_main_writes_food_json(self) -> None:
        line = json.dumps(
            {
                "type": "Feature",
                "id": "n7",
                "geometry": {"type": "Point", "coordinates": [38.047, 55.962]},
                "properties": {"name": "Кафе", "amenity": "cafe"},
            }
        )
        towns = [{"qid": "FRY", "name": "Фрязино", "population": 60_000, "lat": 55.9606, "lon": 38.0456}]
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)
            (raw / "towns.json").write_text(json.dumps(towns), "utf-8")
            (raw / "f.geojsonseq").write_text("\x1e" + line + "\n", "utf-8")
            import contextlib
            import io

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.fe.main([str(raw), str(raw / "f.geojsonseq")]), 0)
            food = json.loads((raw / "food.json").read_text("utf-8"))
        self.assertEqual([(f["osm"], f["townQid"], f["name"]) for f in food], [("n7", "FRY", "Кафе")])


class CommonsTest(unittest.TestCase):
    cm = load("fetch_commons_meta")

    def test_credits(self) -> None:
        pages = [
            {
                "title": "File:A.jpg",
                "imageinfo": [
                    {
                        "extmetadata": {
                            "Artist": {"value": "<a href='u'>Иван</a>"},
                            "LicenseShortName": {"value": "CC BY-SA 4.0"},
                            "LicenseUrl": {"value": "https://cc"},
                        }
                    }
                ],
            },
            {
                "title": "File:B.jpg",
                "imageinfo": [{"extmetadata": {"LicenseShortName": {"value": "Fair use"}}}],
            },
            {
                "title": "File:C.jpg",
                "imageinfo": [
                    {"extmetadata": {"NonFree": {"value": "true"}, "LicenseShortName": {"value": "x"}}}
                ],
            },
            {"title": "Talk:x"},
        ]
        c = self.cm.credits_from_pages(pages)
        self.assertEqual(
            c["A.jpg"], {"author": "Иван", "licence": "CC BY-SA 4.0", "url": "https://cc", "free": True}
        )
        self.assertFalse(c["B.jpg"]["free"])
        self.assertFalse(c["C.jpg"]["free"])
        self.assertEqual(len(c), 3)

    def test_files_of_a_build(self) -> None:
        from tests.unit.test_catalogue import SAMPLES, builder

        b = builder()
        with tempfile.TemporaryDirectory() as tmp:
            b.write(b.build(SAMPLES, "s", ""), Path(tmp))
            files = self.cm.files_of(Path(tmp))
        self.assertIn("Hermitage sample.jpg", files)
        self.assertEqual(files, sorted(set(files)))


class PhotoCheckTest(unittest.TestCase):
    ph = load("check_photos")

    def test_sample_and_summary(self) -> None:
        names = [f"f{i}.jpg" for i in range(200)]
        a = self.ph.sample(names, 50, "7")
        self.assertEqual(len(a), 50)
        self.assertEqual(a, self.ph.sample(list(reversed(names)), 50, "7"))  # deterministic per seed
        self.assertEqual(self.ph.sample(names[:3], 50, "7"), names[:3])
        card, thumb = self.ph.CARD_WIDTH, self.ph.THUMB_WIDTH
        rows = [(f, i != 0, "200 image/jpeg" if i else "HTTP 404") for i, f in enumerate(a)]
        doc = self.ph.summary({card: rows, thumb: rows[:10]}, 200)
        self.assertEqual(doc["rates"][str(card)], 49 / 50)
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["failures"][str(card)], [{"file": a[0], "status": "HTTP 404"}])
        bad = [(f, i > 5, "x") for i, f in enumerate(a)]
        self.assertFalse(self.ph.summary({card: bad}, 200)["ok"])


class _Parse:
    def __init__(self, tag: str, forms: dict[str, str]) -> None:
        self.tag = tag
        self.forms = forms

    def inflect(self, cases: set[str]) -> Any:
        (case,) = cases
        word = self.forms.get(case)
        return None if word is None else type("F", (), {"word": word})()


class _Morph:
    """A stub morphology with pymorphy3's `parse` interface (lower-case word forms)."""

    TABLE: ClassVar[dict[str, _Parse]] = {
        "нижний": _Parse("ADJF,Qual masc,sing,nomn", {"gent": "нижнего", "loct": "нижнем"}),
        "новгород": _Parse("NOUN,inan,masc,Geox sing,nomn", {"gent": "новгорода", "loct": "новгороде"}),
        "ростов": _Parse("NOUN,inan,masc,Geox sing,nomn", {"gent": "ростова", "loct": "ростове"}),
        "посад": _Parse("NOUN,inan,masc sing,nomn", {"gent": "посада", "loct": "посаде"}),
        "дону": _Parse("NOUN,inan,masc,Geox sing,datv", {"gent": "дона", "loct": "доне"}),
    }

    def parse(self, word: str) -> list[_Parse]:
        hit = self.TABLE.get(word.lower())
        return [hit] if hit else [_Parse("UNKN", {})]


class InflectTest(unittest.TestCase):
    inf = load("inflect")

    def test_forms(self) -> None:
        m = _Morph()
        self.assertEqual(
            self.inf.forms("Нижний Новгород", m), {"gen": "Нижнего Новгорода", "prep": "Нижнем Новгороде"}
        )
        self.assertEqual(
            self.inf.forms("Ростов-на-Дону", m), {"gen": "Ростова-на-Дону", "prep": "Ростове-на-Дону"}
        )
        self.assertEqual(
            self.inf.forms("Сергиев Посад", m), {"gen": "Сергиева Посада", "prep": "Сергиевом Посаде"}
        )
        self.assertEqual(self.inf.forms("Сочи", m), {"gen": "Сочи", "prep": "Сочи"})  # does not parse → kept

    def test_oracle_counts_the_fixture_forms(self) -> None:
        r = self.inf.oracle(_Morph())
        self.assertGreaterEqual(r["total"], 40)
        self.assertEqual(r["total"], r["match"] + len(r["misses"]))


class LockTest(unittest.TestCase):
    def test_lock(self) -> None:
        from tests.unit.test_catalogue import SAMPLES, builder

        wl = load("write_lock")
        b = builder()
        with tempfile.TemporaryDirectory() as tmp:
            b.write(b.build(SAMPLES, "s", "2026-10-25"), Path(tmp))
            doc = wl.lock(SAMPLES, Path(tmp))
        self.assertEqual(doc["version"], "s")
        self.assertGreater(doc["counts"]["towns"], 10)
        self.assertEqual(len(doc["files"]), 5)  # + catalogue_food (CEO 2026-10-29)
        self.assertGreater(doc["counts"]["food"], 3)
        self.assertIsNone(doc["classCheck"])
        json.dumps(doc)


if __name__ == "__main__":
    unittest.main()
