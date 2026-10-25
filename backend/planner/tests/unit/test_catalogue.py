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

    def test_author_and_poi_name(self) -> None:
        self.assertEqual(self.b.clean_author("Иван (tibr1984@yandex.ru)"), "Иван")
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
        c = cat.from_docs(self.docs["meta"], self.docs["towns"], self.docs["pois"], self.docs["bars"])
        self.assertEqual(c.version, "sample")
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

    def test_bars_filters(self) -> None:
        bars = {b["name"]: b for b in self.table("bars", cat.BAR_COLS)}
        self.assertNotIn("Сетевой бар (пример)", bars)  # brand tag → chain
        kinds = {n: cat.BAR_KINDS[b["kind"]] for n, b in bars.items()}
        self.assertEqual(kinds["Пивоварня (пример) «Волжская»"], "craft")
        self.assertEqual(kinds["Паб (пример) «Старый мост»"], "pub")
        self.assertEqual(kinds["Бар (пример) «Угол»"], "bar")
        self.assertEqual(kinds["Рюмочная (пример) на Советской"], "ryumochnaya")

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
