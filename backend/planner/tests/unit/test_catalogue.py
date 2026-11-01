"""ADR-0012 §1-3: the catalogue format, the builder on recorded samples, and the packaged files."""

from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tests.helpers import PLANNER_ROOT
from verst_planner import catalogue as cat
from verst_planner import resources

SAMPLES = PLANNER_ROOT / "tests" / "data" / "samples" / "raw"
TOOLS = PLANNER_ROOT / "tools" / "data"
TARGET_BYTES = 2_500_000
HARD_LIMIT_BYTES = 4_000_000


def builder() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_catalogue", TOOLS / "build_catalogue.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FormatTest(unittest.TestCase):
    def test_table_round_trip(self) -> None:
        rows = [{"a": 1, "b": "x"}, {"a": 2}]
        doc = cat.encode_table(rows, ("a", "b"))
        self.assertEqual(doc, {"v": 1, "n": 2, "cols": {"a": [1, 2], "b": ["x", None]}})
        self.assertEqual(cat.decode_table(doc, ("a", "b"), "t"), [{"a": 1, "b": "x"}, {"a": 2, "b": None}])

    def test_bad_tables(self) -> None:
        for doc in ({"v": 2}, [], {"v": 1, "n": "2", "cols": {}}, {"v": 1, "n": 1, "cols": {"a": [1, 2]}}):
            with self.subTest(doc=doc), self.assertRaises(cat.CatalogueError):
                cat.decode_table(doc, ("a",), "t")
        with self.assertRaises(cat.CatalogueError):
            cat.load_gz(b"not gzip", "x")
        with self.assertRaises(cat.CatalogueError):
            cat.from_docs({"v": 9}, {}, {}, {})

    def test_gzip_is_deterministic(self) -> None:
        a = cat.dump_gz({"k": "значение"})
        self.assertEqual(a, cat.dump_gz({"k": "значение"}))
        self.assertEqual(json.loads(gzip.decompress(a)), {"k": "значение"})
        self.assertEqual(cat.to_coord(57.62615), 5762615)

    def test_packaged_catalogue_loads(self) -> None:
        c = cat.load_packaged()
        self.assertGreater(len(c.towns), 10)
        self.assertGreater(len(c.pois), 10)
        self.assertGreater(len(c.bars), 5)
        self.assertEqual(c.info()["towns"], len(c.towns))
        self.assertIsNone(c.credit(None))
        self.assertIsNone(c.credit(10_000))
        self.assertTrue(all(t.region in c.regions for t in c.towns))
        self.assertTrue(all(p.town in c.town_by_id for p in c.pois))
        self.assertTrue(all(b.kind in cat.BAR_KINDS for b in c.bars))
        self.assertTrue(all(f.kind in cat.FOOD_KINDS and f.town in c.town_by_id for f in c.food))
        self.assertEqual(c.info()["food"], len(c.food))

    def test_credits_are_short_names(self) -> None:
        """Release S3: every shipped photo credit is a short name: no sentence, URL, e-mail or licence."""
        import re

        c = cat.load_packaged()
        bad = re.compile(
            r"https?://|www\.|\S@\S+\.\w|\[at\]|<|>|\b(?:was|is|please|uploader|uploaded|own work|"
            r"taken by|created by|photo by|licen[cs]e|cc[ -]by|public domain|camera location|derivative)\b"
            r"|[^\W\d_]{3}\.\s+[A-ZА-ЯЁ]|\n",
            re.I,
        )
        for credit in c.credits:
            a = credit.author
            if a is None:
                continue
            with self.subTest(author=a):
                self.assertLessEqual(len(a), 40)
                self.assertLessEqual(len(a.split()), 4)
                self.assertIsNone(bad.search(a))
                self.assertEqual(a, a.strip())

    def test_real_catalogue_coverage(self) -> None:
        """ARCH-302 acceptance on the CI-built data (skipped for the sandbox sample)."""
        c = cat.load_packaged()
        if c.version == "sample":
            self.skipTest("sample catalogue")
        self.assertGreaterEqual(len(c.towns), 1000)
        self.assertGreaterEqual(len(c.pois), 10000)
        self.assertGreaterEqual(len(c.bars), 2000)
        names = {t.name: t for t in c.towns}
        big_towns = ("Москва", "Санкт-Петербург", "Екатеринбург", "Новосибирск", "Казань", "Пермь")
        for big in big_towns:
            self.assertIn(big, names)
            self.assertTrue(names[big].gen and names[big].prep, big)
        self.assertEqual(names["Москва"].gen, "Москвы")
        with_forms = sum(1 for t in c.towns if t.gen and t.prep)
        self.assertGreaterEqual(with_forms / len(c.towns), 0.95)
        self.assertGreaterEqual(sum(1 for p in c.pois if p.image) / len(c.pois), 0.3)

    def test_packaged_licence_and_photos(self) -> None:
        """ODbL package (D-IR-07): the shipped catalogue carries the builder's licence block for its own
        build id, right after `builtAt`, and no GFDL-only photo credit (R-10)."""
        b = builder()
        meta = cat.load_gz(resources.read_bytes(cat.FILES["meta"]), "meta")
        self.assertEqual(meta["licence"], b.licence_block(meta["version"]))
        self.assertEqual(list(meta)[:4], ["v", "version", "builtAt", "licence"])
        self.assertEqual(meta["licence"]["database"]["licence"], "ODbL-1.0")
        self.assertEqual(meta["licence"]["build"], meta["version"])
        self.assertEqual([c for c in meta["credits"] if b.gfdl_only(c.get("licence"))], [])

    def test_size_budget(self) -> None:
        total = sum(len(resources.read_bytes(name)) for name in cat.FILES.values())
        self.assertLessEqual(total, HARD_LIMIT_BYTES)
        self.assertLessEqual(total, TARGET_BYTES)


class BuilderRulesTest(unittest.TestCase):
    """Run 3/7 data findings: villages and districts as towns, e-mails in credits, «(Казань)» suffixes."""

    b = builder()

    def test_is_town(self) -> None:
        ok = {"name": "Плёс", "population": 1796}
        self.assertTrue(self.b.is_town(ok))
        for name, pop in (
            ("Деревня Габнаволок (Тамбицы)", 5000),
            ("Адлерский район", 125715),
            ("город Тельмана", 23407),
            ("Серпухов-15", 3484),
            ("73-й километр", 2000),
            ("Зубалово", 0),
            ("Старинный Суздаль историко градостроительный комплекс", 5000),
        ):
            self.assertFalse(self.b.is_town({"name": name, "population": pop}), name)

    def test_area_ok(self) -> None:
        jpeg = {"w": 3600, "h": 2400, "mime": "image/jpeg", "cats": ["Flag tower (Peter & Paul Fortress)"]}
        self.assertTrue(self.b.area_ok("Peter & Paul fortress in SPB 03.jpg", jpeg))
        self.assertTrue(self.b.area_ok("x.jpg", None))  # no metadata: the file-name rule only
        for name, meta in (
            ("KAZ Collage 2015.png", None),
            ("Новокузнецк Коллаж.jpg", None),
            ("Montage-of-Makhachkala-(2016).png", None),
            ("Coat of Arms of Tver.jpg", None),
            ("Ufa.jpg", {**jpeg, "cats": ["Montages of Ufa"]}),
            ("Dolgoprudny.jpg", {**jpeg, "cats": ["Flags of cities and villages of Moscow Oblast"]}),
            ("small.jpg", {**jpeg, "w": 640, "h": 480}),
            ("wide.jpg", {**jpeg, "w": 5992, "h": 2056}),  # 2.9 : 1
            ("map.jpg", {**jpeg, "mime": "image/png"}),
        ):
            self.assertFalse(self.b.area_ok(name, meta), name)
        self.assertTrue(self.b.area_ok("Belogorsk.jpg", {**jpeg, "cats": ["Belogorsk"]}))  # not «logo»

    def test_gfdl_only(self) -> None:
        """R-10: GFDL-only Commons files are dropped; a file that also offers another licence stays."""
        gfdl = ("GFDL", "gfdl", "GFDL 1.2", "GFDL-1.3", "GNU Free Documentation License", "GFDL, GFDL 1.2")
        for licence in gfdl:
            self.assertTrue(self.b.gfdl_only(licence), licence)
        for licence in (
            None,
            "",
            "CC BY-SA 4.0",
            "Public domain",
            "GFDL, CC BY-SA 3.0",
            "CC BY-SA 3.0 or GFDL",
            "GFDL/CC BY 2.5",
            "Attribution",
        ):
            self.assertFalse(self.b.gfdl_only(licence), licence)

    def test_licence_block(self) -> None:
        """ODbL 4.2/4.4/4.6: ODbL 1.0 for the whole database, every source with its licence and URIs,
        the free copy."""
        block = self.b.licence_block("wd-x")
        self.assertEqual(block["database"]["uri"], "https://opendatacommons.org/licenses/odbl/1-0/")
        self.assertEqual(block["build"], "wd-x")
        self.assertEqual(block["copy"], "https://github.com/pazzia/Verst/tree/main/data/catalogue")
        by_source = {a["source"]: a for a in block["attribution"]}
        self.assertEqual(
            sorted(by_source),
            ["OpenStreetMap", "Wikidata", "Wikimedia Commons", "Wikipedia (ru)", "Wikivoyage (ru)"],
        )
        osm = by_source["OpenStreetMap"]
        self.assertEqual((osm["text"], osm["licence"]), ("© OpenStreetMap contributors", "ODbL-1.0"))
        self.assertEqual(osm["uri"], "https://www.openstreetmap.org/copyright")
        self.assertEqual(by_source["Wikidata"]["licence"], "CC0-1.0")
        for wiki in ("Wikipedia (ru)", "Wikivoyage (ru)"):
            self.assertEqual(by_source[wiki]["licence"], "CC-BY-SA-4.0")
            self.assertTrue(by_source[wiki]["abridged"])
        for uri in (block["database"]["uri"], osm["uri"], block["copy"]):
            self.assertIn(uri, block["notice"])

    def test_author_and_poi_name(self) -> None:
        self.assertEqual(self.b.clean_author("Иван (tibr1984@yandex.ru)"), "Иван")
        cases = {
            "This photo was taken by Anton Zelenov. Please credit this with: Anton Zelenov in the line": (
                "Anton Zelenov"
            ),
            "This photography was created by Artem Topchiy (user Art-top)": "Artem Topchiy",
            "Анатолий Горлов. Original uploader was Szn-lordi at ru.wikipedia": "Анатолий Горлов",
            "The original uploader was Digr at Russian Wikipedia.": "Digr",
            "No machine-readable author provided. Muad'Dib~commonswiki assumed": "Muad'Dib",
            "Photo: user:NVO. Architects: ???.": "NVO",
            "ru:User:Al Silonov": "Al Silonov",
            "Чурилов Д. А.. Original uploader was Skydrinker at ru.wikipedia": "Чурилов Д. А.",
            "Zac allan (talk) 21:00, 14 July 2009 (UTC)": "Zac allan",
            "<a href='x'>Bob</a>, CC BY-SA 4.0": "Bob",
            "Own work": None,
            "Unknown authorUnknown author": None,
            "The Krasnoyarsk National and Cultural Autonomy of the Chuvash People": None,
            "Иерей Максим Массалитин Camera location 55° 47′ N": "Иерей Максим Массалитин",
        }
        for raw, want in cases.items():
            self.assertEqual(self.b.clean_author(raw), want, raw)
        self.assertIsNone(self.b.clean_author("https://flickr.com/x"))
        self.assertEqual(self.b.poi_name("Площадь Свободы (Казань)", "Казань"), "Площадь Свободы")
        self.assertEqual(self.b.poi_name("Собор (Москва)", "Казань"), "Собор (Москва)")


class BuilderTest(unittest.TestCase):
    docs: dict[str, dict[str, Any]]
    b: Any

    @classmethod
    def setUpClass(cls) -> None:
        cls.b = builder()
        cls.docs = cls.b.build(SAMPLES, "sample", "2026-10-25")

    def table(self, key: str, cols: tuple[str, ...]) -> list[dict[str, Any]]:
        return cat.decode_table(self.docs[key], cols, key)

    def test_deterministic_and_loadable(self) -> None:
        again = self.b.build(SAMPLES, "sample", "2026-10-25")
        self.assertEqual(json.dumps(again, ensure_ascii=False), json.dumps(self.docs, ensure_ascii=False))
        c = cat.from_docs(
            self.docs["meta"], self.docs["towns"], self.docs["pois"], self.docs["bars"], self.docs["food"]
        )
        self.assertEqual(c.version, "sample")
        self.assertEqual(len(c.food), self.docs["food"]["n"])
        old = cat.from_docs(self.docs["meta"], self.docs["towns"], self.docs["pois"], self.docs["bars"])
        self.assertEqual(old.food, [])  # a catalogue built before the food data: no food, «no data yet»
        with tempfile.TemporaryDirectory() as tmp:
            sizes = self.b.write(self.docs, Path(tmp))
            self.assertEqual(set(sizes), set(cat.FILES.values()))

    def test_towns_regions_and_forms(self) -> None:
        towns = {t["name"]: t for t in self.table("towns", cat.TOWN_COLS)}
        self.assertNotIn("Пример вне списка", towns)  # region outside ISO 3166-2:RU
        self.assertEqual(
            (towns["Москва"]["gen"], towns["Москва"]["prep"]), ("Москвы", "Москве")
        )  # fixture form
        self.assertEqual((towns["Сочи"]["gen"], towns["Сочи"]["prep"]), ("Сочи", "Сочи"))  # override wins
        self.assertEqual(towns["Пермь"]["gen"], "Перми")  # pymorphy3 form
        pops = [t["pop"] for t in self.table("towns", cat.TOWN_COLS)]
        self.assertEqual(pops, sorted(pops, reverse=True))

    def test_pois_filters(self) -> None:
        pois = {p["name"]: p for p in self.table("pois", cat.POI_COLS)}
        self.assertNotIn("Музей Лукойл", pois)  # deny-list
        self.assertNotIn("Станция метро", pois)  # class not in the list
        self.assertIsNone(pois["Исаакиевский собор"]["image"])  # non-free file dropped
        self.assertEqual(cat.POI_KINDS[pois["Петропавловская крепость"]["kind"]], "kremlin")
        meta = self.docs["meta"]
        self.assertEqual(meta["credits"][0]["author"], "Пример Автор")  # HTML stripped

    def test_meta_licence(self) -> None:
        meta = self.docs["meta"]
        self.assertEqual(meta["licence"], self.b.licence_block("sample"))
        self.assertEqual(list(meta)[:4], ["v", "version", "builtAt", "licence"])

    def test_gfdl_only_photo_is_dropped(self) -> None:
        """R-10 regression: the same recorded samples with the Hermitage photo re-licensed GFDL-only → no
        image and no credit for it; a GFDL + CC BY-SA file keeps its image."""
        import shutil

        name = "Эрмитаж"
        base = {p["name"]: p for p in self.table("pois", cat.POI_COLS)}
        self.assertEqual(base[name]["image"], "Hermitage sample.jpg")
        for licence, kept in (("GFDL", False), ("GFDL 1.2", False), ("GFDL, CC BY-SA 3.0", True)):
            with self.subTest(licence=licence), tempfile.TemporaryDirectory() as tmp:
                raw = Path(tmp)
                for f in SAMPLES.iterdir():
                    shutil.copy(f, raw / f.name)
                credits = json.loads((raw / "credits.json").read_text("utf-8"))
                credits["Hermitage sample.jpg"]["licence"] = licence
                (raw / "credits.json").write_text(json.dumps(credits, ensure_ascii=False), "utf-8")
                docs = self.b.build(raw, "sample", "2026-10-25")
                poi = {p["name"]: p for p in cat.decode_table(docs["pois"], cat.POI_COLS, "pois")}[name]
                licences = [c["licence"] for c in docs["meta"]["credits"]]
                if kept:
                    self.assertEqual(poi["image"], "Hermitage sample.jpg")
                    self.assertIn(licence, licences)
                else:
                    self.assertIsNone(poi["image"])
                    self.assertIsNone(poi["credit"])
                    self.assertNotIn(licence, licences)
                    towns = cat.decode_table(docs["towns"], cat.TOWN_COLS, "towns")
                    used = [r["image"] for r in towns] + [v["image"] for v in docs["meta"]["links"].values()]
                    self.assertNotIn("Hermitage sample.jpg", used)

    def test_bars_filters(self) -> None:
        bars = {b["name"]: b for b in self.table("bars", cat.BAR_COLS)}
        self.assertNotIn("Сетевой бар (пример)", bars)  # brand tag → chain
        kinds = {n: cat.BAR_KINDS[b["kind"]] for n, b in bars.items()}
        self.assertEqual(kinds["Пивоварня (пример) «Волжская»"], "craft")
        self.assertEqual(kinds["Паб (пример) «Старый мост»"], "pub")
        self.assertEqual(kinds["Бар (пример) «Угол»"], "bar")
        self.assertEqual(kinds["Рюмочная (пример) на Советской"], "ryumochnaya")

    def test_bar_kinds_by_name_and_tags(self) -> None:
        """CEO 2026-10-29: «По рюмочным» = strong spirits and shots, «Пивной» = beer places, by a name word
        beginning or the OSM tags; anything else is a generic bar."""
        k = self.b.bar_kind
        bar = {"amenity": "bar"}
        for name, tags, kind in (
            ("Рюмка", bar, "ryumochnaya"),
            ("Советская рюмочная", bar, "ryumochnaya"),
            ("Наливайка Под Мостом", bar, "ryumochnaya"),
            ("Настоечная (812)", {"amenity": "pub"}, "ryumochnaya"),  # the name wins over amenity=pub
            ("Стопка", bar, "ryumochnaya"),
            ("Икра и водки", bar, "ryumochnaya"),
            ("Угол", {"amenity": "bar", "bar": "shot_bar"}, "ryumochnaya"),
            ("Brewmen taproom", bar, "craft"),
            ("Крафтовый бар", bar, "craft"),
            ("Tap 22", bar, "craft"),
            ("Угол", {"amenity": "bar", "microbrewery": "yes"}, "craft"),
            ("Угол", {"amenity": "bar", "craft_beer": "yes"}, "craft"),
            ("Угол", {"craft": "brewery"}, "craft"),
            ("Beerhead", bar, "pub"),
            ("BeerHere", bar, "pub"),
            ("Пивная № 1", bar, "pub"),
            ("Эль и Вино", bar, "pub"),
            ("Tower Pub", bar, "pub"),
            ("Культура", {"amenity": "bar", "brewery": "various"}, "pub"),  # the beers on tap
            ("Угол", {"amenity": "bar", "drink:beer": "yes"}, "pub"),
            ("Ирландец", {"amenity": "pub"}, "pub"),
            ("Шотландский паб", bar, "pub"),  # «шот» is not a shot bar here
            ("Lovecraft", bar, "bar"),  # «craft» does not begin a word
            ("Пабло", bar, "bar"),
            ("Белый налив", bar, "bar"),
            ("Угол", {"amenity": "bar", "brewery": "no", "drink:beer": "served"}, "bar"),
            ("Mixo", bar, "bar"),
        ):
            with self.subTest(name=name, tags=tags):
                self.assertEqual(k(name, tags), kind)

    def test_caps_grow_with_the_town(self) -> None:
        b = self.b
        self.assertEqual((b.bar_cap(5_652_922), b.bar_cap(13_274_285)), (b.BAR_CAP_MAX, b.BAR_CAP_MAX))
        self.assertEqual(b.bar_cap(60_000), b.BAR_CAP_MIN)
        self.assertGreater(b.bar_cap(5_652_922), 60)
        self.assertEqual(b.food_cap(60_000), 24)  # Фрязино
        self.assertEqual(b.food_cap(900), b.FOOD_CAP_MIN)
        self.assertEqual(b.food_cap(13_274_285), b.FOOD_CAP_MAX)
        self.assertEqual(b.cuisine({"cuisine": "Russian; georgian;russian"}), "russian;georgian")
        self.assertIsNone(b.cuisine({}))
        self.assertLessEqual(len(b.cuisine({"cuisine": ";".join(["x" * 15] * 5)}) or ""), b.CUISINE_MAX)

    def test_food_filters(self) -> None:
        """CEO 2026-10-29: named OSM restaurants, cafés, fast food of a catalogue town; deny-listed and
        unnamed places dropped, unparseable hours dropped, `cuisine` kept; over the cap chain fast food
        goes first, then other chains."""
        food = {f["name"]: f for f in self.table("food", cat.FOOD_COLS)}
        kinds = {n: cat.FOOD_KINDS[f["kind"]] for n, f in food.items()}
        self.assertEqual(kinds["Ресторан (пример) «Волжский»"], "restaurant")
        self.assertEqual(kinds["Кафе (пример) «Пирожковая»"], "cafe")
        self.assertEqual(kinds["Чебуречная (пример)"], "fast_food")
        self.assertEqual(food["Ресторан (пример) «Волжский»"]["cuisine"], "russian;regional")
        self.assertEqual(food["Ресторан (пример) «Волжский»"]["hours"], "Mo-Su 12:00-23:00")
        self.assertNotIn("Кафе Лукойл", food)  # deny-list
        self.assertNotIn("", food)  # unnamed
        self.assertNotIn("Ресторан (пример) без города", food)  # not a catalogue town
        self.assertNotIn("Бар не еда (пример)", food)  # not a food amenity
        self.assertIn("Сетевой фастфуд (пример)", food)  # a chain stays while the town is under its cap
        self.assertEqual(self.docs["meta"]["foodKinds"], list(cat.FOOD_KINDS))
        towns = cat.decode_table(self.docs["towns"], cat.TOWN_COLS, "towns")
        yar = next(i for i, t in enumerate(towns) if t["name"] == "Ярославль")
        raw = json.loads((SAMPLES / "food.json").read_text("utf-8"))
        town_pos = {t["id"]: i for i, t in enumerate(towns)}
        old = self.b.FOOD_CAP_MIN
        self.b.FOOD_CAP_MIN = 4  # population 0 below → a cap of 4 places per town
        try:
            pops = [{"population": 0}] * len(towns)
            capped = self.b.food_rows(raw, town_pos, pops, self.b.denylist(), None)
        finally:
            self.b.FOOD_CAP_MIN = old
        names = [r["name"] for r in capped if r["town"] == yar]
        self.assertEqual(len(names), 4)
        self.assertNotIn("Сетевой фастфуд (пример)", names)  # chain fast food goes first
        self.assertNotIn("Сетевая кофейня (пример)", names)  # then the other chains

    def test_links_are_one_to_one(self) -> None:
        links = self.docs["meta"]["links"]
        qids = [v["wikidata"] for v in links.values()]
        self.assertEqual(len(qids), len(set(qids)))
        self.assertEqual(links["t_moscow"]["wikidata"], "Q649")

    def test_caps_and_helpers(self) -> None:
        b = self.b
        self.assertEqual(b.poi_cap(2_000_000, False), 120)
        self.assertEqual(b.poi_cap(200_000, False), 50)
        self.assertEqual(b.poi_cap(5_000, True), b.POI_CAP_TOURIST)
        self.assertEqual(b.poi_cap(5_000, False), b.POI_CAP_OTHER)
        self.assertTrue(b.similar("Стрелка и Волжская набережная", "Волжская набережная"))
        self.assertFalse(b.similar("Эрмитаж", "Русский музей"))
        self.assertIsNone(b.poi_kind(["Q1"]))

    def test_cli_main_writes_files(self) -> None:
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(self.b.main([str(SAMPLES), "--out", tmp, "--version", "t"]), 0)
            self.assertEqual(json.loads(out.getvalue())["towns"], self.docs["towns"]["n"])
            hours = cat.decode_table(
                cat.load_gz((Path(tmp) / cat.FILES["bars"]).read_bytes(), "bars"), cat.BAR_COLS, "bars"
            )
            self.assertNotIn("bad hours text", [h["hours"] for h in hours])  # unparseable hours dropped


if __name__ == "__main__":
    unittest.main()
