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
        self.assertEqual(len(doc["files"]), 4)
        self.assertIsNone(doc["classCheck"])
        json.dumps(doc)


if __name__ == "__main__":
    unittest.main()
