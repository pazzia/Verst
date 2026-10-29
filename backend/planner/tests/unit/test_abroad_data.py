"""CEO 29.10 (trips abroad, wave 1; parks): the country-parametrised data pipeline, on synthetic fixtures.

- the Russian path is unchanged (the same Wikidata queries as runs 1-7, the same build);
- the wave-1 countries: config, Wikidata parsing (label languages, regions, Abkhazia), time zones, the build;
- parks (`parks_from_extract.py`, `build_parks.py`, `catalogue_parks.json.gz`);
- the abroad catalogue never reaches the APK (location outside `verst_planner/`, `diagnose.py apk`).
"""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

from tests.helpers import PLANNER_ROOT
from tests.unit.test_catalogue import SAMPLES, builder
from tests.unit.test_data_fetchers import lit, load
from verst_planner import catalogue as cat

ABROAD_SAMPLES = PLANNER_ROOT / "tests" / "data" / "samples" / "abroad_ge"
REPO = PLANNER_ROOT.parents[1]
E = "http://www.wikidata.org/entity/"

# The Russian queries of runs 1-7, verbatim (fetch_wikidata.py before the country parameter).
OLD_Q_TOWNS = """SELECT ?town ?townLabel ?coord ?pop ?popDate ?iso ?regionLabel ?image WHERE {{
  VALUES ?cls {{ {classes} }}
  ?town wdt:P31 ?cls; wdt:P17 wd:{country}; wdt:P625 ?coord .
  FILTER NOT EXISTS {{ ?town wdt:P576 [] }}
  OPTIONAL {{ ?town p:P1082 ?ps . ?ps ps:P1082 ?pop . OPTIONAL {{ ?ps pq:P585 ?popDate }} }}
  OPTIONAL {{ ?town wdt:P131* ?region . ?region wdt:P300 ?iso . FILTER(STRSTARTS(?iso, "RU-")) }}
  OPTIONAL {{ ?town wdt:P18 ?image }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "ru" . }}
}}"""
OLD_Q_POIS = """SELECT ?item ?itemLabel ?itemDescription ?coord ?root ?sitelinks ?image ?heritage WHERE {{
  SERVICE wikibase:around {{ ?item wdt:P625 ?coord .
    bd:serviceParam wikibase:center "Point({lon} {lat})"^^geo:wktLiteral; wikibase:radius "{radius}" . }}
  VALUES ?root {{ {roots} }}
  ?item wdt:P31/wdt:P279* ?root .
  ?item wikibase:sitelinks ?sitelinks .
  OPTIONAL {{ ?item wdt:P18 ?image }}
  OPTIONAL {{ ?item wdt:P1435 ?heritage }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "ru" . }}
}}"""


def label(v: str, lang: str | None) -> dict[str, Any]:
    out: dict[str, Any] = {"value": v}
    if lang:
        out["xml:lang"] = lang
    return out


def town_row(
    q: str, name: str, lang: str | None, iso: str | None, country: str = "Q230", **kw: Any
) -> dict[str, Any]:
    b = {
        "town": lit(E + q),
        "townLabel": label(name, lang),
        "coord": lit(kw.get("coord", "Point(44.8 41.7)")),
        "country": lit(E + country),
        "pop": lit(str(kw.get("pop", 10000))),
    }
    if iso:
        b["iso"] = lit(iso)
        b["regionLabel"] = label(kw.get("region", iso), "ru")
    return b


def ci_module(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / "ci" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CountriesTest(unittest.TestCase):
    c = load("countries")

    def test_wave1_is_the_ceo_list(self) -> None:
        got = {x.code: x.qids[0] for x in self.c.WAVE1}
        self.assertEqual(
            got,
            {
                "BY": "Q184",
                "KZ": "Q232",
                "GE": "Q230",
                "AB": "Q23334",
                "AM": "Q399",
                "AZ": "Q227",
                "UZ": "Q265",
                "KG": "Q813",
                "TR": "Q43",
            },
        )
        for x in self.c.WAVE1:
            self.assertTrue(x.abroad)
            self.assertTrue(x.label_langs.startswith("ru,") and x.label_langs.endswith(",en"), x.code)
            self.assertEqual(len(x.currency), 3)
            self.assertTrue(x.iso_prefix.endswith("-"))
        self.assertEqual(self.c.get("ab").currency, "RUB")
        self.assertEqual({x.geofabrik_iso for x in self.c.WAVE1 if x.code in ("GE", "AB")}, {"GE"})

    def test_russia_keeps_the_old_constants(self) -> None:
        ru = self.c.get(None)
        self.assertFalse(ru.abroad)
        self.assertEqual((ru.qids, ru.iso_prefix, ru.label_langs), (("Q159",), "RU-", "ru"))
        self.assertEqual(ru.town_classes, ("Q7930989", "Q183342"))
        with self.assertRaises(SystemExit):
            self.c.get("XX")

    def test_abkhazia_carve(self) -> None:
        ge, ab = self.c.get("GE"), self.c.get("AB")
        for region, p17, in_ab in (
            ("GE-AB", ["Q230"], True),
            (None, ["Q23334"], True),
            ("GE-AB", ["Q23334", "Q230"], True),
            ("GE-TB", ["Q230"], False),
            (None, ["Q230"], False),
        ):
            self.assertEqual(self.c.keeps(ab, region, p17), in_ab, (region, p17))
            self.assertEqual(self.c.keeps(ge, region, p17), not in_ab, (region, p17))
        self.assertTrue(self.c.keeps(self.c.get("BY"), None, []))


class QueriesTest(unittest.TestCase):
    wd = load("fetch_wikidata")
    c = load("countries")

    def test_russian_queries_are_the_old_ones(self) -> None:
        classes = ["Q7930989", "Q183342", "Q515"]
        old = OLD_Q_TOWNS.format(classes=" ".join(f"wd:{x}" for x in classes), country="Q159")
        self.assertEqual(self.wd.towns_query(self.c.RU, classes), old)
        kw = {"lat": 55.1, "lon": 37.2, "radius": 4.0, "roots": "wd:Q1 wd:Q2"}
        self.assertEqual(self.wd.Q_POIS.format(**kw, langs=self.c.RU.label_langs), OLD_Q_POIS.format(**kw))
        self.assertEqual(self.wd.expect_for(self.c.RU), self.wd.EXPECT)
        self.assertEqual(self.wd.COUNTRY, "Q159")

    def test_abroad_queries(self) -> None:
        q = self.wd.towns_query(self.c.get("GE"), ["Q7930989"])
        self.assertIn("VALUES ?country { wd:Q230 wd:Q23334 }", q)
        self.assertIn("wdt:P17 ?country;", q)
        self.assertIn('STRSTARTS(?iso, "GE-")', q)
        self.assertIn('wikibase:language "ru,en"', q)
        self.assertIn(" ?country WHERE", q)
        kz = self.wd.towns_query(self.c.get("KZ"), ["Q7930989"])
        self.assertIn("wdt:P17 wd:Q232;", kz)
        self.assertNotIn("?country", kz)
        expect = self.wd.expect_for(self.c.get("TR"))
        self.assertNotIn("Q159", expect)
        self.assertEqual(expect["Q43"], ("turkey", "türkiye"))
        self.assertIn("Q32815", expect)  # mosque
        self.assertEqual(self.wd.Q_RESOLVE.format(label="мечеть", country="Q43").count("wd:Q43"), 1)
        self.assertEqual(self.wd.parse_args(["towns", "/tmp/x", "--country", "kz"])[2].code, "KZ")
        self.assertEqual(self.wd.parse_args(["pois", "/tmp/x"])[2].code, "RU")

    def test_class_check_with_the_country(self) -> None:
        expect = self.wd.expect_for(self.c.get("KG"))
        rows = [{"c": lit(E + q), "label": lit(kw[0])} for q, kw in expect.items()]
        self.assertTrue(self.wd.class_check(rows, expect)["ok"])
        rows[-1] = {"c": lit(E + "Q813"), "label": lit("Kazakhstan")}
        self.assertEqual(self.wd.class_check(rows, expect)["mismatches"], {"Q813": "Kazakhstan"})


class TownsAbroadTest(unittest.TestCase):
    wd = load("fetch_wikidata")
    c = load("countries")

    def test_label_language_region_and_countries(self) -> None:
        by = self.c.get("BY")
        rows = [
            town_row("Q1", "Минск", "ru", "BY-HM", "Q184", pop=2000000),
            town_row("Q1", "Минск", "ru", "BY-HA", "Q184"),  # a second coded region: the smallest code wins
            town_row("Q2", "Ivanava", "be", "BY-BR", "Q184"),
            town_row("Q3", "Q3", None, "BY-BR", "Q184"),  # no label in ru, be or en: dropped
            town_row("Q4", "Elsewhere", "en", "RU-MOS", "Q184"),  # a region of another prefix: none
        ]
        towns = {t["qid"]: t for t in self.wd.towns_from_bindings(rows, by)}
        self.assertEqual(sorted(towns), ["Q1", "Q2", "Q4"])
        self.assertEqual(towns["Q1"]["regionIso"], "BY-HA")
        self.assertEqual(towns["Q1"]["population"], 2000000)
        self.assertEqual((towns["Q1"]["nameLang"], towns["Q2"]["nameLang"]), ("ru", "be"))
        self.assertEqual(towns["Q1"]["countries"], ["Q184"])
        self.assertIsNone(towns["Q4"]["regionIso"])
        # the Russian rows keep their old keys (no nameLang, no countries)
        ru = self.wd.towns_from_bindings([town_row("Q5", "Тверь", "ru", "RU-TVE", "Q159")])
        self.assertNotIn("nameLang", ru[0])
        self.assertNotIn("countries", ru[0])

    def test_abkhazia_goes_to_its_own_catalogue(self) -> None:
        rows = [
            town_row("Q10", "Сухум", "ru", "GE-AB", "Q230", region="Автономная Республика Абхазия"),
            town_row("Q10", "Сухум", "ru", None, "Q23334"),
            town_row("Q11", "Гагра", "ru", None, "Q23334"),  # P17 Abkhazia only, no coded region
            town_row("Q12", "Тбилиси", "ru", "GE-TB", "Q230"),
        ]
        ab = self.wd.towns_from_bindings(rows, self.c.get("AB"))
        ge = self.wd.towns_from_bindings(rows, self.c.get("GE"))
        self.assertEqual([t["qid"] for t in ab], ["Q10", "Q11"])
        self.assertEqual({(t["regionIso"], t["regionName"]) for t in ab}, {("GE-AB", "Абхазия")})
        self.assertEqual(ab[0]["countries"], ["Q230", "Q23334"])
        self.assertEqual([t["qid"] for t in ge], ["Q12"])

    def test_pois_and_must_have(self) -> None:
        b = {
            "item": lit(E + "Q20"),
            "itemLabel": label("Narikala", "en"),
            "coord": lit("Point(44.81 41.69)"),
            "root": lit(E + "Q57821"),
            "sitelinks": lit("30"),
        }
        p = self.wd.pois_from_bindings([b], "Q12", self.c.get("GE"))[0]
        self.assertEqual((p["nameLang"], p["roots"], p["townQid"]), ("en", ["Q57821"], "Q12"))
        self.assertNotIn("nameLang", self.wd.pois_from_bindings([b], "Q12")[0])
        towns = [{"qid": "Q12", "name": "Тбилиси"}]
        self.assertEqual(self.wd.missing_towns(towns, ("Q12",)), [])
        self.assertEqual(self.wd.missing_towns(towns, ("Q99",)), ["Q99"])

    def test_towns_abroad_are_fetched_in_chunks_with_regions_apart(self) -> None:
        """Run 1 (29.10): the single towns query timed out for KZ, UZ, KG, AZ, AB. Abroad: class chunks
        without the region path, then the regions per batch of towns; a failing chunk is halved."""
        ab = self.c.get("AB")
        classes = [f"Q{i}" for i in range(1, 131)]  # 3 chunks of ≤ 60
        asked: list[str] = []

        def query(q: str) -> list[dict[str, Any]]:
            asked.append(q)
            if "VALUES ?cls" in q:
                self.assertNotIn("P131", q)  # no region path in the towns chunks
                self.assertRegex(q, r"VALUES \?country \{ wd:Q2(30|3334) wd:Q2(30|3334) \}")
                n = q.split("VALUES ?cls {")[1].split("}")[0].count("wd:")
                if n > 40:  # WDQS gives up on big chunks: they must be halved
                    raise TimeoutError("The read operation timed out")
                if "wd:Q1 " not in q:
                    return []
                return [
                    town_row("Q10", "Сухум", "ru", None, "Q230"),
                    town_row("Q10", "Сухум", "ru", None, "Q23334"),
                    town_row("Q12", "Тбилиси", "ru", None, "Q230"),
                ]
            self.assertIn("wdt:P131*", q)
            self.assertIn("wd:Q10 wd:Q12", q)
            return [
                {"town": lit(E + "Q10"), "iso": lit("GE-AB"), "regionLabel": label("Абхазия (регион)", "ru")},
                {"town": lit(E + "Q12"), "iso": lit("GE-TB"), "regionLabel": label("Тбилиси", "ru")},
                {"town": lit(E + "Q99"), "iso": lit("GE-TB")},  # not a town of the chunks: ignored
            ]

        with contextlib.redirect_stdout(io.StringIO()):
            ab_towns = self.wd.fetch_towns_abroad(ab, classes, query)
            ge_towns = self.wd.fetch_towns_abroad(self.c.get("GE"), classes, query)
        self.assertEqual(
            [(t["qid"], t["regionIso"], t["regionName"]) for t in ab_towns], [("Q10", "GE-AB", "Абхазия")]
        )
        self.assertEqual([(t["qid"], t["regionIso"]) for t in ge_towns], [("Q12", "GE-TB")])
        self.assertEqual(ab_towns[0]["population"], 10000)
        self.assertEqual(ab_towns[0]["countries"], ["Q230", "Q23334"])
        chunks = [q for q in asked if "VALUES ?cls" in q]
        self.assertGreater(len(chunks), 3)  # the failing chunks of 60 were halved
        with self.assertRaises(TimeoutError):  # one class that still fails: the error stays visible
            self.wd.split_query(["Q1"], lambda c: (_ for _ in ()).throw(TimeoutError("x")))
        self.assertEqual(self.wd.with_regions([], [{"town": lit(E + "Q1"), "iso": lit("GE-TB")}]), [])

    def test_country_report(self) -> None:
        kz = self.c.get("KZ")
        head = [
            {
                "c": lit(E + "Q232"),
                "cLabel": lit("Kazakhstan"),
                "capital": lit(E + "Q1520"),
                "curCode": lit("KZT"),
                "tzLabel": lit("UTC+05:00"),
            },
        ]
        regions = [
            {"r": lit(E + "Q1"), "iso": lit("KZ-75"), "rLabel": lit("Алматы"), "tzLabel": lit("UTC+05:00")},
            {"r": lit(E + "Q1"), "iso": lit("KZ-75"), "rLabel": lit("Алматы"), "tzLabel": lit("UTC+06:00")},
        ]
        r = self.wd.country_report(kz, head, regions)
        self.assertTrue(r["ok"] and r["currencyOk"])
        self.assertEqual(r["capitals"], ["Q1520"])
        self.assertEqual(r["regions"]["KZ-75"]["tz"], ["UTC+05:00", "UTC+06:00"])
        head[0]["cLabel"] = lit("Kyrgyzstan")
        head[0]["curCode"] = lit("USD")
        bad = self.wd.country_report(kz, head, [])
        self.assertFalse(bad["ok"])
        self.assertFalse(bad["currencyOk"])


class TimeZoneTest(unittest.TestCase):
    b = builder()
    c = load("countries")

    def test_every_country_has_a_zone_with_the_right_offset(self) -> None:
        table = self.b.read_tz_abroad()
        want = {
            "BY": 180,
            "TR": 180,
            "AB": 180,
            "GE": 240,
            "AM": 240,
            "AZ": 240,
            "UZ": 300,
            "KZ": 300,
            "KG": 360,
        }
        for x in self.c.WAVE1:
            zone = self.b.zone_for(x, f"{x.iso_prefix}ANY", table)
            self.assertIsNotNone(zone, x.code)
            self.assertEqual(self.b.zone_minutes(zone, "2026-10-29"), want[x.code], (x.code, zone))
            self.assertEqual(self.b.zone_minutes(zone, "2026-07-01"), want[x.code], (x.code, "summer"))
        self.assertIsNone(self.b.zone_for(self.c.get("RU"), "RU-MOW", table))

    def test_utc_labels_and_check(self) -> None:
        self.assertEqual(self.b.utc_minutes("UTC+04:00"), 240)
        self.assertEqual(self.b.utc_minutes("UTC−05:30"), -330)
        self.assertEqual(self.b.utc_minutes("UTC+6"), 360)
        self.assertEqual(self.b.utc_minutes("UTC"), 0)
        self.assertIsNone(self.b.utc_minutes("Moscow Time"))
        check = {"tz": ["UTC+04:00"], "regions": {"GE-AB": {"tz": ["UTC+03:00"]}, "GE-TB": {"tz": []}}}
        r = self.b.tz_check({"GE-AB": "Asia/Tbilisi", "GE-TB": "Asia/Tbilisi"}, check, "2026-10-29")
        self.assertEqual(r["mismatches"], ["GE-AB"])
        self.assertTrue(r["regions"]["GE-TB"]["ok"])  # no zone of its own: the country's
        self.assertTrue(self.b.tz_check({"GE-AB": "Europe/Moscow"}, check, "")["ok"])
        self.assertFalse(self.b.tz_check({"X-1": "Asia/Tbilisi"}, {}, "")["checked"])


class BuildAbroadTest(unittest.TestCase):
    b: Any
    docs: dict[str, dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.b = builder()
        cls.ge = load("countries").get("GE")
        cls.docs = cls.b.build(ABROAD_SAMPLES, "t", "2026-10-29", None, cls.ge)

    def cols(self, key: str) -> dict[str, list[Any]]:
        return dict(self.docs[key]["cols"])

    def test_towns_regions_and_meta(self) -> None:
        towns = self.cols("towns")
        self.assertEqual(towns["id"], ["Q900201", "Q900202"])  # no village, no town without a region
        self.assertEqual(towns["nameLang"], ["ru", "en"])
        self.assertEqual(towns["gen"], [None, None])  # no forms.json, no Russian name tables abroad
        meta = self.docs["meta"]
        self.assertEqual(list(meta)[:5], ["v", "version", "builtAt", "licence", "country"])
        self.assertEqual(meta["country"]["currency"], "GEL")
        self.assertEqual(meta["country"]["labelLangs"], ["ru", "en"])
        self.assertEqual([r["code"] for r in meta["regions"]], ["GE-IM", "GE-TB"])
        self.assertEqual({r["tz"] for r in meta["regions"]}, {"Asia/Tbilisi"})
        self.assertTrue(meta["tzCheck"]["checked"] and meta["tzCheck"]["ok"])
        self.assertEqual(meta["links"], {})
        lic = meta["licence"]
        self.assertEqual(lic["database"]["licence"], "ODbL-1.0")
        self.assertIn("catalogue_parks", lic["database"]["scope"])
        self.assertEqual(lic["copy"], self.b.ABROAD_COPY_URI)
        self.assertIn(self.b.ABROAD_COPY_URI, lic["notice"])
        self.assertIn("parks (catalogue_parks)", lic["attribution"][0]["parts"])
        self.assertEqual(self.b.licence_block("x")["copy"], self.b.CATALOGUE_COPY_URI)  # Russia unchanged

    def test_pois_kinds_and_names(self) -> None:
        pois = self.cols("pois")
        kinds = dict(zip(pois["id"], (cat.POI_KINDS[k] for k in pois["kind"]), strict=True))
        self.assertEqual(kinds["Q900301"], "church")  # a mosque (ABROAD_CLASS_KIND)
        self.assertEqual(kinds["Q900302"], "museum")
        langs = dict(zip(pois["id"], pois["nameLang"], strict=True))
        self.assertEqual((langs["Q900302"], langs["osm_w7301"]), ("en", "ru"))
        names = dict(zip(pois["id"], pois["name"], strict=True))
        self.assertEqual(names["osm_w7301"], "Тестовая смотровая")  # name:ru wins over the Georgian name
        self.assertEqual(self.b.poi_kind(["Q32815"]), None)  # not a Russian class

    def test_osm_names_in_russian_first(self) -> None:
        bars = self.cols("bars")
        self.assertEqual(bars["name"], ["Пивной тест", "Beer Test Bar", "Тест-бар", "ღვინო"])
        self.assertEqual(bars["nameLang"], ["local", "en", "ru", "local"])
        food = self.cols("food")
        self.assertEqual(food["name"], ["Тестовая столовая", "Test Cafe", "Test Khachapuri"])
        self.assertEqual(food["nameLang"], ["ru", "local", "en"])
        self.assertEqual(self.b.osm_name({"name": "ბარი"}), ("ბარი", "local"))
        self.assertEqual(self.b.osm_name({}), (None, None))
        self.assertTrue(self.b.readable("Kutaisi-2 «Бар»"))
        self.assertFalse(self.b.readable("Երևան"))

    def test_parking_has_no_rouble_rate_abroad(self) -> None:
        parking = self.docs["meta"]["parking"]
        self.assertEqual(parking["rph"], [None, None])  # «1 р/ч» abroad is not ₽
        self.assertEqual(parking["charge"], ["2 GEL/hour", "1 р/ч"])
        ru = self.b.parking_meta(
            [{"osm": "w1", "lat": 1.0, "lon": 1.0, "charge": "60 ₽/ч"}], [{"lat": 100000, "lon": 100000}]
        )
        self.assertEqual(ru, {"lat": [100000], "lon": [100000], "rph": [60]})

    def test_loadable_by_the_engine_format_and_deterministic(self) -> None:
        d = self.docs
        c = cat.from_docs(d["meta"], d["towns"], d["pois"], d["bars"], d["food"])
        self.assertEqual(c.regions["GE-TB"].tz, "Asia/Tbilisi")
        self.assertEqual(c.town_by_id["Q900202"].region, "GE-IM")
        again = self.b.build(ABROAD_SAMPLES, "t", "2026-10-29", None, self.ge)
        self.assertEqual(json.dumps(again, ensure_ascii=False), json.dumps(d, ensure_ascii=False))

    def test_russian_build_is_unchanged_by_the_parameter(self) -> None:
        ru = load("countries").get("RU")
        a = self.b.build(SAMPLES, "s", "2026-10-25")
        b = self.b.build(SAMPLES, "s", "2026-10-25", None, ru)
        self.assertEqual(json.dumps(a, ensure_ascii=False), json.dumps(b, ensure_ascii=False))
        self.assertNotIn("country", a["meta"])
        self.assertNotIn("tzCheck", a["meta"])
        self.assertNotIn("nameLang", a["towns"]["cols"])
        self.assertNotIn("charge", a["meta"]["parking"])


def feature(fid: str, geom: dict[str, Any], **tags: Any) -> str:
    return "\x1e" + json.dumps({"type": "Feature", "id": fid, "geometry": geom, "properties": tags})


def square(lon: float, lat: float, d: float) -> list[list[float]]:
    return [[lon, lat], [lon + d, lat], [lon + d, lat + d], [lon, lat + d], [lon, lat]]


class ParksExtractTest(unittest.TestCase):
    px = load("parks_from_extract")

    def test_area_and_centre(self) -> None:
        # 0.01° × 0.01° at the equator ≈ 1113 m × 1112 m
        got = self.px.area_and_centre({"type": "Polygon", "coordinates": [square(0.0, 0.0, 0.01)]})
        assert got is not None
        self.assertAlmostEqual(got[0] / 1_237_000, 1.0, delta=0.01)
        self.assertAlmostEqual(got[1], 0.005, places=6)
        self.assertAlmostEqual(got[2], 0.005, places=6)
        holed = self.px.area_and_centre(
            {"type": "Polygon", "coordinates": [square(0.0, 0.0, 0.01), square(0.0, 0.0, 0.005)]}
        )
        assert holed is not None
        self.assertAlmostEqual(holed[0] / got[0], 0.75, delta=0.01)
        multi = self.px.area_and_centre(
            {"type": "MultiPolygon", "coordinates": [[square(0.0, 0.0, 0.01)], [square(0.02, 0.0, 0.01)]]}
        )
        assert multi is not None
        self.assertAlmostEqual(multi[0] / got[0], 2.0, delta=0.01)
        self.assertAlmostEqual(multi[2], 0.015, places=5)
        self.assertIsNone(self.px.area_and_centre({"type": "Point", "coordinates": [1, 1]}))
        self.assertIsNone(self.px.area_and_centre({"type": "LineString", "coordinates": square(0, 0, 1)}))

    def test_features(self) -> None:
        big = {"type": "Polygon", "coordinates": [square(37.0, 55.0, 0.003)]}  # ~190 m × 330 m
        tiny = {"type": "Polygon", "coordinates": [square(37.0, 55.0, 0.0002)]}
        lines = [
            feature("w1", big, leisure="park", name="Парк Победы", **{"name:ru": "Парк Победы", "ref": "x"}),
            feature(
                "r2",
                {"type": "MultiPolygon", "coordinates": [[square(37.1, 55.0, 0.003)]]},
                leisure="garden",
                name="Ботанический сад",
            ),
            feature("n3", {"type": "Point", "coordinates": [37.0, 55.0]}, leisure="park", name="Точка"),
            feature("w4", big, leisure="park"),  # no name
            feature("w5", big, leisure="park", name="Двор", access="private"),
            feature("w6", big, leisure="garden", name="Огород", **{"garden:type": "residential"}),
            feature("w7", tiny, leisure="park", name="Клумба"),
            feature("w8", big, leisure="playground", name="Площадка"),
            feature(
                "w9",
                {"type": "LineString", "coordinates": square(37.0, 55.0, 0.003)},
                leisure="park",
                name="Аллея",
            ),
            "",
        ]
        got = self.px.parks_from_features(lines)
        self.assertEqual([(p["type"], p["id"]) for p in got], [("way", 1), ("relation", 2)])
        self.assertEqual(got[0]["tags"], {"leisure": "park", "name": "Парк Победы", "name:ru": "Парк Победы"})
        self.assertGreater(got[0]["area"], 30_000)

    def test_assign_and_catalogue_towns(self) -> None:
        towns = [
            {"qid": "Q1", "name": "А", "lat": 55.0, "lon": 37.0, "population": 60_000},
            {"qid": "Q2", "name": "Б", "lat": 56.0, "lon": 38.0, "population": 900},
        ]
        els = [
            {
                "type": "way",
                "id": 1,
                "lat": 55.01,
                "lon": 37.01,
                "area": 5000,
                "tags": {"name": "П", "leisure": "park"},
            },
            {
                "type": "way",
                "id": 2,
                "lat": 57.0,
                "lon": 39.0,
                "area": 5000,
                "tags": {"name": "Д", "leisure": "park"},
            },
        ]
        rows = self.px.assign_parks(els, towns)
        self.assertEqual([(r["osm"], r["townQid"], r["area"]) for r in rows], [("w1", "Q1", 5000)])
        b = builder()
        with tempfile.TemporaryDirectory() as tmp:
            b.write(b.build(SAMPLES, "s", "2026-10-25"), Path(tmp))
            got = self.px.catalogue_towns(Path(tmp))
        self.assertEqual(got[0]["qid"], "Q649")
        self.assertAlmostEqual(got[0]["lat"], 55.7558, places=4)
        self.assertGreater(got[0]["population"], 10_000_000)

    def test_osmium_area_ids(self) -> None:
        """Run 1 (29.10): «parks: 0 rows from 0 named parks» in Russia, Belarus and Georgia — osmium writes a
        park polygon as `a<area id>` (2 × way id, 2 × relation id + 1); the `w…` feature of a closed way is
        its LineString. The osmium-shaped fixture has both."""
        self.assertEqual(self.px.osm_object("a246"), ("way", 123))
        self.assertEqual(self.px.osm_object("a91"), ("relation", 45))
        self.assertEqual(self.px.osm_object("w7"), ("way", 7))
        self.assertEqual(self.px.osm_object("r8"), ("relation", 8))
        for bad in ("", "a", "x1", "a1b"):
            self.assertIsNone(self.px.osm_object(bad))
        seq = ABROAD_SAMPLES / "parks.geojsonseq"
        with seq.open(encoding="utf-8") as fh:
            got = self.px.parks_from_features(fh)
        self.assertEqual([(p["type"], p["id"]) for p in got], [("way", 7201), ("relation", 7203)])
        self.assertEqual(got[0]["tags"]["wikidata"], "Q900304")
        self.assertGreater(got[0]["area"], 200_000)  # 0.005° × 0.005° at 41.7° N ≈ 230 000 m²
        self.assertLess(got[1]["area"], 37_000)  # the hole of the relation is subtracted
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)
            (raw / "towns.json").write_text((ABROAD_SAMPLES / "towns.json").read_text("utf-8"), "utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = self.px.main([str(raw), str(seq)])
            parks = json.loads((raw / "parks.json").read_text("utf-8"))
        self.assertEqual(rc, 0)
        self.assertEqual(
            {(p["osm"], p["townQid"]) for p in parks}, {("w7201", "Q900201"), ("r7203", "Q900202")}
        )


class BuildParksTest(unittest.TestCase):
    bp = load("build_parks")

    def test_russian_parks_against_the_sample_catalogue(self) -> None:
        b = builder()
        raw = [
            {
                "osm": "w1",
                "name": "Парк Горького",
                "lat": 55.73,
                "lon": 37.60,
                "area": 1_200_000,
                "tags": {"leisure": "park", "name": "Парк Горького", "opening_hours": "24/7"},
                "townQid": "Q649",
            },
            {
                "osm": "w2",
                "name": "Сад",
                "lat": 55.75,
                "lon": 37.61,
                "area": 9_000,
                "tags": {"leisure": "garden", "name": "Сад", "opening_hours": "nonsense"},
                "townQid": "Q649",
            },
            {
                "osm": "r3",
                "name": "Парк Горького",
                "lat": 55.73,
                "lon": 37.60,
                "area": 400_000,
                "tags": {"leisure": "park", "name": "Парк Горького"},
                "townQid": "Q649",
            },  # the same park, smaller
            {
                "osm": "w4",
                "name": "Парк",
                "lat": 1.0,
                "lon": 1.0,
                "area": 9_000,
                "tags": {"leisure": "park", "name": "Парк"},
                "townQid": "Q0",
            },  # not a catalogue town
            *[
                {
                    "osm": f"w{10 + i}",
                    "name": f"Сквер {i}",
                    "lat": 56.42,
                    "lon": 40.44,
                    "area": 3_000 + i,
                    "tags": {"leisure": "park", "name": f"Сквер {i}"},
                    "townQid": "Q900003",
                }
                for i in range(8)
            ],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "raw").mkdir()
            (out / "raw" / "parks.json").write_text(json.dumps(raw, ensure_ascii=False), "utf-8")
            b.write(b.build(SAMPLES, "s", "2026-10-25"), out)
            doc = self.bp.parks_doc(out / "raw", out, lambda h: h != "nonsense")
            self.assertEqual(
                doc["townsSha256"], hashlib.sha256((out / cat.FILES["towns"]).read_bytes()).hexdigest()
            )
            with contextlib.redirect_stdout(io.StringIO()):
                rc = self.bp.main([str(out / "raw"), str(out), "--lock", str(out / "p.lock")])
            self.assertEqual(rc, 0)
            on_disk = json.loads(gzip.decompress((out / cat.PARKS_FILE).read_bytes()))
            lock = json.loads((out / "p.lock").read_text("utf-8"))
        self.assertEqual(doc["version"], "s")
        self.assertEqual(doc["kinds"], list(cat.PARK_KINDS))
        self.assertEqual(doc["licence"]["licence"], "ODbL-1.0")
        rows = cat.decode_table(doc, cat.PARK_COLS, "parks")
        self.assertNotIn("nameLang", doc["cols"])
        moscow = [r for r in rows if r["town"] == 0]
        self.assertEqual(
            [r["id"] for r in moscow], ["osm_w1", "osm_w2"]
        )  # one row per name, the largest first
        self.assertEqual(moscow[0]["hours"], "24/7")
        self.assertIsNone(moscow[1]["hours"])
        self.assertEqual(cat.PARK_KINDS[moscow[1]["kind"]], "garden")
        suzdal = [r for r in rows if r["town"] != 0]
        self.assertEqual(len(suzdal), self.bp.park_cap(9286))
        self.assertEqual(suzdal[0]["area"], 3_007)
        self.assertEqual(lock["count"], on_disk["n"])
        self.assertEqual(on_disk["n"], len(rows))
        self.assertEqual(
            (self.bp.park_cap(0), self.bp.park_cap(200_000), self.bp.park_cap(13_000_000)), (5, 10, 60)
        )

    def test_abroad_parks_link_the_pois(self) -> None:
        b = builder()
        ge = load("countries").get("GE")
        with tempfile.TemporaryDirectory() as tmp:
            b.write(b.build(ABROAD_SAMPLES, "t", "2026-10-29", None, ge), Path(tmp))
            doc = self.bp.parks_doc(ABROAD_SAMPLES, Path(tmp), None, ge)
        rows = cat.decode_table(doc, (*cat.PARK_COLS, "nameLang"), "parks")
        by_id = {r["id"]: r for r in rows}
        self.assertEqual(
            sorted(by_id), ["osm_w7201", "osm_w7202", "osm_w7204"]
        )  # no village park, no duplicate
        self.assertEqual(by_id["osm_w7201"]["poi"], "Q900304")  # its wikidata tag is a shipped POI
        self.assertEqual((by_id["osm_w7202"]["name"], by_id["osm_w7202"]["nameLang"]), ("Сквер", "ru"))
        self.assertEqual((by_id["osm_w7204"]["name"], by_id["osm_w7204"]["nameLang"]), ("Test Park", "en"))


class ToolsTest(unittest.TestCase):
    def test_geofabrik_url(self) -> None:
        g = load("geofabrik_url")

        def f(i: str, parent: str | None, iso: list[str], url: str) -> dict[str, Any]:
            return {"properties": {"id": i, "parent": parent, "iso3166-1:alpha2": iso, "urls": {"pbf": url}}}

        index = {
            "features": [
                f("europe", None, [], "e"),
                f("georgia", "europe", ["GE"], "https://x/europe/georgia-latest.osm.pbf"),
                f("us/georgia", "north-america", [], "https://x/us/georgia-latest.osm.pbf"),
                f("russia", None, ["RU"], "https://x/russia-latest.osm.pbf"),
                f("central-fed-district", "russia", ["RU"], "https://x/russia/central.osm.pbf"),
                f("a", None, ["XX"], "1"),
                f("b", None, ["XX"], "2"),
            ]
        }
        self.assertEqual(g.pbf_url(index, "ge"), "https://x/europe/georgia-latest.osm.pbf")
        self.assertEqual(g.pbf_url(index, "RU"), "https://x/russia-latest.osm.pbf")
        for bad in ("XX", "KZ"):
            with self.assertRaises(LookupError):
                g.pbf_url(index, bad)

    def test_merge_abroad_lock(self) -> None:
        wl = load("write_lock")
        b = builder()
        ge = load("countries").get("GE")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "ge"
            b.write(b.build(ABROAD_SAMPLES, "t", "2026-10-29", None, ge), out)
            (out / "lock.json").write_text(json.dumps(wl.lock(ABROAD_SAMPLES, out)), "utf-8")
            (out / "parks.lock.json").write_text(json.dumps({"bytes": 100, "count": 3}), "utf-8")
            (root / "empty").mkdir()
            doc = wl.merge_abroad(root)
        self.assertEqual(list(doc["countries"]), ["ge"])
        ge_lock = doc["countries"]["ge"]
        self.assertEqual(ge_lock["counts"]["towns"], 2)
        self.assertEqual(doc["totalBytes"], ge_lock["totalBytes"] + 100)

    def test_inflect_only_russian_labels(self) -> None:
        inf = load("inflect")
        towns = [
            {"qid": "Q1", "name": "Минск", "nameLang": "ru"},
            {"qid": "Q2", "name": "Kutaisi", "nameLang": "en"},
            {"qid": "Q3", "name": "Тверь"},
        ]
        self.assertEqual([t["qid"] for t in inf.russian_named(towns)], ["Q1", "Q3"])

    def test_extras_keep_russian_names_abroad(self) -> None:
        fx = load("fetch_extras")
        food = load("food_from_extract")
        line = feature(
            "n1",
            {"type": "Point", "coordinates": [44.8, 41.7]},
            name="ხედი",
            tourism="viewpoint",
            amenity="cafe",
            **{"name:ru": "Вид", "name:en": "View"},
        )
        self.assertNotIn("name:ru", fx.osm_from_features([line])[0][0]["tags"])  # Russia: the old raw file
        self.assertEqual(fx.osm_from_features([line], True)[0][0]["tags"]["name:ru"], "Вид")
        self.assertNotIn("name:ru", food.food_from_features([line])[0]["tags"])
        self.assertEqual(food.food_from_features([line], True)[0]["tags"]["name:en"], "View")


class NotInTheApkTest(unittest.TestCase):
    """The catalogue abroad is server-only: outside the package the APK stages, and checked in the APK."""

    def test_location_is_outside_the_packaged_package(self) -> None:
        c = load("countries")
        abroad = (PLANNER_ROOT / c.ABROAD_DIR).resolve()
        pkg = (PLANNER_ROOT / "verst_planner").resolve()
        self.assertFalse(abroad.is_relative_to(pkg))
        self.assertEqual([p for p in pkg.rglob("*") if "abroad" in p.parts], [])
        gradle = (REPO / "android" / "app" / "build.gradle.kts").read_text("utf-8")
        stage = gradle[gradle.index('register<Sync>("stagePlannerSources")') :]
        stage = stage[: stage.index("into(")]
        self.assertIn('include("verst_planner/**")', stage)
        self.assertEqual(stage.count("include("), 1)  # only the package: abroad/ cannot be staged
        workflow = (REPO / ".github" / "workflows" / "data-abroad.yml").read_text("utf-8")
        self.assertIn("ABROAD: backend/planner/abroad", workflow)
        self.assertNotIn("verst_planner/resources/abroad", workflow)

    def test_diagnose_apk_finds_nested_abroad_entries(self) -> None:
        d = ci_module("diagnose")

        def apk(with_abroad: bool) -> bytes:
            inner = io.BytesIO()
            with zipfile.ZipFile(inner, "w") as z:
                z.writestr("verst_planner/resources/catalogue_meta.json.gz", b"x")
                if with_abroad:
                    z.writestr("verst_planner/resources/abroad/ge/catalogue_meta.json.gz", b"x")
            outer = io.BytesIO()
            with zipfile.ZipFile(outer, "w") as z:
                z.writestr("assets/chaquopy/app.imy", inner.getvalue())
                z.writestr("assets/worlds/central_russia_v1.json", b"{}")
            return outer.getvalue()

        with zipfile.ZipFile(io.BytesIO(apk(False))) as z:
            self.assertEqual(d.abroad_entries(z), [])
        with zipfile.ZipFile(io.BytesIO(apk(True))) as z:
            self.assertEqual(
                d.abroad_entries(z),
                ["assets/chaquopy/app.imy!/verst_planner/resources/abroad/ge/catalogue_meta.json.gz"],
            )
        with tempfile.TemporaryDirectory() as tmp:
            for flag, code in ((False, 0), (True, 1)):
                path = Path(tmp) / f"a{int(flag)}.apk"
                path.write_bytes(apk(flag))
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = d.main(["--out", str(Path(tmp) / "diag"), "apk", "--apk", str(path)])
                self.assertEqual(rc, code)


if __name__ == "__main__":
    unittest.main()
