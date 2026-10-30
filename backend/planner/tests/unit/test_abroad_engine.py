"""CEO 29.10 (trips abroad, wave 1, server only): the world `world_v1` = `russia_v1` + catalogues abroad.

Fixture world: the packaged Russian catalogue + tiny catalogues of Georgia, Azerbaijan and Belarus in the CI
format (`tests/abroad_fixture.py`).
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any

from tests.abroad_fixture import write_abroad, write_country
from tests.helpers import PLANNER_ROOT
from tests.unit.test_mobile import call, fail, load_worlds
from verst_planner import mobile
from verst_planner.catalogue import CatalogueError
from verst_planner.domain.enums import FuelType
from verst_planner.domain.model import LatLon
from verst_planner.foreign import catalogues
from verst_planner.foreign.rates import Rates
from verst_planner.foreign.rules import Rules

W = mobile.ABROAD_WORLD
R = "russia_v1"
SOURCES_DOC = PLANNER_ROOT.parents[1] / "docs" / "plan" / "abroad-wave1-sources.md"
MOSCOW = {"lat": 55.7558, "lon": 37.6173, "label": "Москва"}
TBILISI = {"lat": 41.7151, "lon": 44.8271, "label": "Тбилиси"}
BAKU = {"lat": 40.4093, "lon": 49.8671, "label": "Баку"}
MINSK = {"lat": 53.9023, "lon": 27.5619, "label": "Минск"}
BATUMI = {"lat": 41.6168, "lon": 41.6367, "label": "Батуми"}
YAROSLAVL = {"lat": 57.6261, "lon": 39.8845, "label": "Ярославль"}
CREW = {"adults": 2, "children": 0, "dog": False}


def trip_input(destination: dict[str, Any], **kw: Any) -> str:
    return json.dumps({"origin": MOSCOW, "destination": destination, "crew": CREW, "dailyKm": 600} | kw)


def plan(world: str, inp: str) -> dict[str, Any]:
    env: dict[str, Any] = json.loads(mobile.plan(world, "abroad-test", inp, None))
    return env


def stops(trip: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for d in trip["daysList"] for s in d["stops"]]


def without_ms(text: str) -> str:
    return re.sub(r'"ms": \d+', '"ms": 0', text)


class AbroadWorldTest(unittest.TestCase):
    tmp: tempfile.TemporaryDirectory[str]
    root: Path

    @classmethod
    def setUpClass(cls) -> None:
        load_worlds()
        call(mobile.set_clock("golden"))  # 2026-10-23: the Azerbaijani border is closed
        if R not in call(mobile.selfcheck())["worlds"]:
            call(mobile.load_catalogue())
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = write_abroad(Path(cls.tmp.name))
        cls.info = call(mobile.load_abroad(str(cls.root)))
        cls.tbilisi = plan(W, trip_input(TBILISI))

    @classmethod
    def tearDownClass(cls) -> None:
        mobile._WORLDS.pop(W, None)  # the bridge's state is process-wide: later tests see the phone's worlds
        call(mobile.set_clock("system"))
        cls.tmp.cleanup()

    def test_world_info(self) -> None:
        self.assertEqual(self.info["world"], W)
        self.assertEqual(self.info["countries"], ["AZ", "BY", "GE", "KZ"])
        self.assertIsNone(self.info["rates"])
        self.assertIn(W, call(mobile.selfcheck())["worlds"])  # the zones abroad resolve too

    def test_moscow_tbilisi_through_verkhny_lars(self) -> None:
        self.assertTrue(self.tbilisi["ok"], self.tbilisi)
        trip = self.tbilisi["result"]["trip"]
        self.assertEqual(trip["title"], "Москва → Тбилиси")
        self.assertIs(trip["approxDistances"], True)
        rows = stops(trip)
        border = [s for s in rows if s["kind"] == "border"]
        self.assertEqual(len(border), 1)
        b = border[0]
        info = b["border"]
        self.assertEqual((info["crossingId"], info["from"], info["to"]), ("verkhny_lars", "RU", "GE"))
        self.assertTrue(info["coordsApprox"] and info["unverified"])
        self.assertIn("Владикавказ", info["coordsNoteRu"])
        self.assertFalse(info["waitKnown"])
        self.assertIn("неизвестно", info["waitRu"])
        self.assertEqual(
            (b["dwellMin"], info["bufferMin"]), (120, 120)
        )  # planner_config.json border.buffer_min
        self.assertIn("не факт", info["bufferRu"])
        self.assertIn("Загранпаспорт", [d["textRu"] for d in info["documents"]])
        self.assertTrue(all(src["url"].startswith("https://") for f in info["facts"] for src in f["sources"]))
        self.assertEqual([r["appliesOnTripDate"] for r in info["risks"]], [False])  # October: no Nov–Mar risk
        # the Georgian part is after the border, on Tbilisi's clock (+1 h: the block-1 local-time rule)
        after = rows[rows.index(b) + 1 :]
        self.assertTrue(after and all(s["localTz"] == "Asia/Tbilisi" for s in after), after)
        self.assertEqual(rows[-1]["kind"], "finish")
        self.assertIn("ABROAD", [w["code"] for w in trip["warnings"]])

    def test_fuel_in_lari_flagged(self) -> None:
        trip = self.tbilisi["result"]["trip"]
        abroad = trip["abroad"]
        self.assertTrue(abroad["unverified"] and abroad["roubleTotalIncomplete"])
        self.assertIsNone(abroad["rates"])  # no rates file: the lari stay lari
        ge = abroad["countries"][0]
        self.assertEqual((ge["code"], ge["currency"]), ("GE", "GEL"))
        fuel = ge["fuel"]
        self.assertEqual(
            (fuel["fuelType"], fuel["pricePerLitre"], fuel["validFrom"]), ("ai95", "4.29", "2026-10-07")
        )
        self.assertEqual(fuel["priceRange"], ["4.16", "4.29"])
        self.assertEqual(
            Decimal(fuel["amount"]),
            (Decimal(str(fuel["litres"])) * Decimal("4.29")).quantize(Decimal("0.01")),
        )
        self.assertIsNone(fuel["rub"])
        self.assertFalse(fuel["inRoubleTotal"])
        self.assertTrue(fuel["unverified"])
        self.assertEqual(fuel["sources"][0]["type"], "secondary")
        self.assertGreater(ge["km"], 0)
        self.assertNotIn(
            "Грузия", json.dumps(trip["cost"]["lines"][0], ensure_ascii=False)
        )  # no rate: not in ₽
        self.assertIn("За границей посчитано не всё", trip["cost"]["totalNoteRu"])
        tpl = next(f for f in ge["fees"] if f["key"] == "tpl")
        self.assertFalse(tpl["counted"])  # the price is from a secondary source only
        self.assertEqual(tpl["notCountedWhy"], "secondary_source")

    def test_round_trip_crosses_twice(self) -> None:
        trip = plan(W, trip_input(TBILISI, roundTrip=True, dailyKm=700))["result"]["trip"]
        self.assertEqual(trip["title"], "Москва → Тбилиси → Москва")  # border waypoints are not labels
        rows = stops(trip)
        self.assertEqual([s["border"]["to"] for s in rows if s["kind"] == "border"], ["GE", "RU"])
        back = [s for s in rows if s["kind"] == "border"][1]["border"]
        self.assertEqual((back["documents"], back["fees"]), ([], []))  # nothing sourced about entering Russia

    def test_a_night_abroad_has_no_price(self) -> None:
        trip = plan(W, trip_input(BATUMI, dailyKm=300))["result"]["trip"]
        rows = stops(trip)
        b = next(i for i, s in enumerate(rows) if s["kind"] == "border")
        self.assertTrue(all(s["kind"] != "sight" for s in rows[b + 1 :]))  # no Russian sight after the border
        nights = [s for s in rows[b + 1 :] if s["kind"] == "overnight"]
        self.assertTrue(nights)
        for s in nights:
            self.assertEqual(s["costRub"], 0)
            self.assertIn("price", s["unknownFacts"])
            self.assertIn("за границей", s["reason"].lower())
        priced = {n["stopId"] for n in trip["cost"]["units"]["nights"]}
        self.assertFalse({s["id"] for s in nights} & priced)
        ge = trip["abroad"]["countries"][0]
        self.assertEqual(ge["nightsUnpriced"], len(nights))
        self.assertGreaterEqual(ge["mealsUnpriced"], 2 * len(nights))
        self.assertIn("Грузия: ночёвки (1) — цен нет", trip["abroad"]["notInRoubleTotalRu"])

    def test_closed_border(self) -> None:
        e = fail(mobile.plan(W, "baku", trip_input(BAKU), None))
        self.assertEqual(
            (e["code"], e["field"], e["reason"], e["country"]),
            ("INVALID_INPUT", "destination", "border_closed", "AZ"),
        )
        self.assertIn("граница закрыта для легковых до 2 января 2027", e["messageRu"].lower())
        self.assertEqual(e["until"], "2027-01-02T06:00:00+04:00")

    def test_border_opens_after_the_date(self) -> None:
        call(mobile.set_clock("2027-01-10T09:00:00+03:00"))
        try:
            out = plan(W, trip_input(BAKU))
        finally:
            call(mobile.set_clock("golden"))
        self.assertTrue(out["ok"], out)
        trip = out["result"]["trip"]
        self.assertEqual(
            [s["border"]["crossingId"] for s in stops(trip) if s["kind"] == "border"], ["yarag_kazmalyar"]
        )
        az = trip["abroad"]["countries"][0]
        self.assertEqual(az["fuel"]["pricePerLitre"], None)  # no АИ-95 price in the sources doc

    def test_belarus_border_is_a_marker(self) -> None:
        trip = plan(W, trip_input(MINSK))["result"]["trip"]
        border = [s for s in stops(trip) if s["kind"] == "border"]
        self.assertEqual(len(border), 1)
        self.assertEqual(border[0]["dwellMin"], 0)
        self.assertTrue(border[0]["border"]["marker"])
        by = trip["abroad"]["countries"][0]
        self.assertEqual((by["tolls"]["status"], by["tolls"]["counted"]), ("zero", True))
        self.assertEqual((by["fuel"]["pricePerLitre"], by["fuel"]["validFrom"]), ("2.67", "2026-04-04"))

    def test_kazakhstan_crossing_without_coordinates(self) -> None:
        trip = plan(W, trip_input({"lat": 50.2839, "lon": 57.1670, "label": "Актобе"}))["result"]["trip"]
        [b] = [s for s in stops(trip) if s["kind"] == "border"]
        info = b["border"]
        self.assertEqual(info["crossingId"], "ru_kz")
        self.assertIn("прямая линия маршрута", info["coordsNoteRu"])
        self.assertIn("Бугристое, Сагарчин, Караузек", info["facts"][0]["textRu"])
        self.assertIn("Сырым", info["facts"][1]["textRu"])
        self.assertEqual(stops(trip)[-1]["localTz"], "Asia/Almaty")
        kz = trip["abroad"]["countries"][0]
        self.assertEqual(
            (kz["currency"], kz["fuel"]["pricePerLitre"], kz["tolls"]["status"]), ("KZT", "322", "unknown")
        )

    def test_points_outside(self) -> None:
        e = fail(mobile.plan(W, "x", trip_input({"lat": 48.1, "lon": 11.6}), None))  # Munich: outside the box
        self.assertEqual((e["reason"], e.get("country")), ("outside_supported", None))
        self.assertIn("вне России", e["messageRu"])
        locator = mobile._WORLDS[W].planner.aw.locator
        self.assertEqual(locator.country_at(LatLon(44.95, 34.10)), "RU")  # Crimea stays Russia
        self.assertEqual(locator.country_at(LatLon(41.70, 44.80)), "GE")
        self.assertEqual(locator.country_at(LatLon(51.70, 87.65)), "RU")  # Телецкое озеро: no town in 60 km

    def test_far_from_towns_in_russia_is_as_before(self) -> None:
        """Coordinator 29.10: no regression for Russia — a point with no town within 60 km inside the old
        Russia box is Russia and gets exactly what `russia_v1` gives (the sea off Magadan: UNREACHABLE)."""
        inp = trip_input({"lat": 55.0, "lon": 150.0})
        a, b = mobile.plan(R, "far", inp, None), mobile.plan(W, "far", inp, None)
        self.assertEqual(fail(b)["code"], "UNREACHABLE")
        self.assertEqual(without_ms(a), without_ms(b))

    def test_russian_trips_are_unchanged(self) -> None:
        cases = [
            trip_input(YAROSLAVL),
            json.dumps(
                {
                    "origin": MOSCOW,
                    "destination": YAROSLAVL,
                    "crew": {"adults": 2, "children": 1, "dog": True},
                    "dailyKm": 300,
                    "roundTrip": True,
                }
            ),
            json.dumps(
                {
                    "origin": {"lat": 59.9386, "lon": 30.3141},
                    "destination": {"lat": 43.5853, "lon": 39.7231, "label": "Сочи"},
                    "crew": CREW,
                    "dailyKm": 800,
                }
            ),
        ]
        for inp in cases:
            with self.subTest(inp=inp[:60]):
                a = mobile.plan(R, "same", inp, None)
                b = mobile.plan(W, "same", inp, None)
                self.assertTrue(json.loads(a)["ok"])
                self.assertEqual(without_ms(a), without_ms(b))
                self.assertEqual(
                    without_ms(mobile.estimate(R, "e", inp)), without_ms(mobile.estimate(W, "e", inp))
                )
        ready = call(mobile.ready_routes(R, 55.7558, 37.6173, 50, 1))[0]["id"]
        inp = json.dumps({"origin": MOSCOW, "readyRouteId": ready, "crew": CREW, "dailyKm": 400})
        self.assertEqual(
            without_ms(mobile.plan(R, "rr", inp, None)), without_ms(mobile.plan(W, "rr", inp, None))
        )

    def test_replace_and_patch_keep_the_part_abroad(self) -> None:
        trip = plan(W, trip_input(TBILISI, roundTrip=True, dailyKm=700))["result"]["trip"]
        stop = next(s for s in stops(trip) if s["alternatives"])
        out = call(mobile.replace_stop(W, json.dumps(trip), stop["id"], stop["alternatives"][0]["id"]))[
            "trip"
        ]
        self.assertEqual(out["abroad"], trip["abroad"])
        self.assertIn("За границей", out["cost"]["totalNoteRu"])
        self.assertEqual(
            [s["border"] for s in stops(out) if s["kind"] == "border"],
            [s["border"] for s in stops(trip) if s["kind"] == "border"],
        )
        patched = call(
            mobile.patch_cost(
                W, json.dumps(trip), json.dumps({"crew": {"adults": 3, "children": 0, "dog": False}})
            )
        )["trip"]
        self.assertIn("За границей", patched["cost"]["totalNoteRu"])
        self.assertGreater(patched["cost"]["totalRub"], trip["cost"]["totalRub"])

    def test_rates_convert_fuel_into_the_fuel_line(self) -> None:
        rates = self.root / "rates.json"
        rates.write_text(
            json.dumps({"asOf": "2026-10-29", "source": "test", "rubPerUnit": {"GEL": 30.0}}), "utf-8"
        )
        call(mobile.load_abroad(str(self.root), str(rates)))
        try:
            trip = plan(W, trip_input(TBILISI))["result"]["trip"]
        finally:
            call(mobile.load_abroad(str(self.root)))
        fuel = trip["abroad"]["countries"][0]["fuel"]
        self.assertTrue(fuel["inRoubleTotal"])
        self.assertEqual(trip["abroad"]["rates"]["rubPerUnit"], {"GEL": "30.0"})
        rows = trip["cost"]["lines"][0]["breakdown"]
        georgian = [r for r in rows if r["label"].startswith("Грузия: ")]
        self.assertTrue(georgian)
        self.assertIn("128,70 ₽", georgian[0]["formula"])  # 4.29 GEL x 30.0 ₽

    def test_without_data_abroad_the_world_is_russia(self) -> None:
        with tempfile.TemporaryDirectory() as empty:
            info = call(mobile.load_abroad(empty))
            try:
                self.assertEqual(info["countries"], [])
                for dest in (TBILISI, YAROSLAVL, MINSK):  # Tbilisi and Minsk: inside the old box, as before
                    inp = trip_input(dest)
                    with self.subTest(dest=dest["label"]):
                        a, b = mobile.plan(R, "same", inp, None), mobile.plan(W, "same", inp, None)
                        self.assertEqual(without_ms(a), without_ms(b))
                e = fail(mobile.plan(W, "x", trip_input({"lat": 48.1, "lon": 11.6}), None))
                self.assertEqual((e["field"], e["reason"]), ("destination", "outside_supported"))
            finally:
                call(mobile.load_abroad(str(self.root)))


class AbroadDataTest(unittest.TestCase):
    """The curated tables: every fact from the sources doc (its URLs and its numbers), and the loader."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.rules = Rules.from_resources()
        cls.doc = SOURCES_DOC.read_text("utf-8")

    def test_every_url_is_in_the_sources_doc(self) -> None:
        from verst_planner import resources

        for name in ("abroad_rules.json", "border_crossings.json"):
            for url in re.findall(r'"url": "([^"]+)"', resources.read_text(name)):
                with self.subTest(url=url):
                    self.assertIn(url, self.doc)

    def test_every_fuel_price_is_in_the_sources_doc(self) -> None:
        for code, c in self.rules.countries.items():
            for fuel, price in c.fuel.items():
                for v in price.values:
                    text = f"{v:,}".replace(",", " ").replace(".", ",")
                    with self.subTest(country=code, fuel=fuel.value, value=text):
                        self.assertIn(text, self.doc)

    def test_paths_between_countries(self) -> None:
        all_ = frozenset({"RU", "BY", "KZ", "GE", "AB", "AM", "UZ", "KG", "TR"})

        def ids(a: str, b: str) -> list[str] | None:
            p = self.rules.path(a, b, all_)
            return None if p is None else [c.id for c in p]

        self.assertEqual(ids("RU", "GE"), ["verkhny_lars"])
        self.assertEqual(ids("RU", "AM"), ["verkhny_lars", "sadakhlo"])
        self.assertEqual(ids("RU", "TR"), ["verkhny_lars", "sarpi"])
        self.assertEqual(ids("RU", "AB"), ["psou"])
        self.assertEqual(ids("AB", "GE"), ["psou", "verkhny_lars"])  # never across the Inguri
        self.assertEqual(ids("RU", "UZ"), ["ru_kz", "kz_uz"])
        self.assertEqual(ids("GE", "GE"), [])
        self.assertIsNone(ids("RU", "AZ"))  # not in the allowed set: closed

    def test_fees_counted_only_from_official_or_primary(self) -> None:
        am = {f.key: f for f in self.rules.countries["AM"].fees}
        self.assertTrue(am["road"].counted)
        self.assertEqual(am["road"].amount_for(10), (Decimal("10000"), 15))
        self.assertEqual(am["road"].amount_for(20), (Decimal("20000"), 30))
        self.assertIsNone(am["road"].amount_for(40))
        self.assertFalse(am["eco"].counted)  # the sources disagree
        self.assertFalse(am["insurance"].counted)  # secondary only
        uz = {f.key: f for f in self.rules.countries["UZ"].fees}
        self.assertTrue(uz["entry"].counted and uz["insurance"].counted)
        self.assertFalse(uz["tint"].counted)  # only with tinted front windows
        self.assertEqual(self.rules.countries["KZ"].fuel[FuelType.DT].budget, Decimal("351"))

    def test_rates_file(self) -> None:
        self.assertIsNone(Rates.from_doc({"asOf": None, "rubPerUnit": {}}))  # the app's placeholder
        r = Rates.from_doc({"asOf": "2026-10-29", "source": "cbr", "rubPerUnit": {"GEL": 29.5}})
        assert r is not None
        self.assertEqual((r.rate("GEL"), r.rate("RUB"), r.rate("UZS")), (Decimal("29.5"), Decimal(1), None))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(Rates.load(Path(tmp) / "missing.json"))

    def test_catalogue_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(catalogues.load_dir(root / "missing"), [])
            write_country(root, "GE")
            (root / "notes").mkdir()  # a folder without a catalogue is ignored
            [ge] = catalogues.load_dir(root)
            self.assertEqual((ge.code, ge.currency, len(ge.catalogue.towns)), ("GE", "GEL", 6))
            (root / "abroad.lock").write_text(
                json.dumps(
                    {"countries": {"ge": {"files": {"catalogue_towns.json.gz": {"sha256": "0" * 64}}}}}
                ),
                "utf-8",
            )
            with self.assertRaises(CatalogueError):
                catalogues.load_dir(root)
            (root / "abroad.lock").unlink()
            (root / "ge").rename(root / "tr")
            with self.assertRaises(CatalogueError):  # meta.country.code must match the folder
                catalogues.load_dir(root)


if __name__ == "__main__":
    unittest.main()
