"""Sprint 4 acceptance trips G14–G17 on the real catalogue `russia_v1` (ADR-0015). Rule checks, not byte
snapshots: the open data changes with every data run. Skipped on the sandbox sample catalogue."""

from __future__ import annotations

import itertools
import json
import math
import re
import unittest
from pathlib import Path
from typing import Any

from tests.unit import test_mobile_v2
from verst_planner import mobile
from verst_planner.domain.model import LatLon
from verst_planner.geo.distance import haversine_km
from verst_planner.pipeline.sights import MIN_QUALITY, RELIGIOUS, category_of, effective_quality

CASES = Path(__file__).resolve().parent / "cases_s4"
MOSCOW = LatLon(55.7558, 37.6173)
BAD_NAMES = ("школа", "гимназия", "стадион", "администрация", "больница", "детский сад")


BARE_NAMES = ("Остановка у дороги", "Площадка отдыха", "АЗС у трассы", "Детская площадка")


def plan(case: str) -> dict[str, Any]:
    doc = json.loads((CASES / f"{case}.json").read_text("utf-8"))
    mobile.set_clock(doc["clock"])
    r = json.loads(mobile.plan("russia_v1", case, json.dumps(doc["input"], ensure_ascii=False), None))
    assert r["ok"], r
    trip: dict[str, Any] = r["result"]["trip"]
    check_m9(trip)
    return trip


def check_m9(trip: dict[str, Any]) -> None:
    """M9 on every S4 case: no bare roadside / rest / playground name, a parking object wherever the car is
    left, the Russian category label, the OSM attribution, `funFor` on the fun stops."""
    for d in trip["daysList"]:
        for s in d["stops"]:
            assert s["name"] not in BARE_NAMES, s["name"]
            if s["kind"] in ("sight", "food") or (s["kind"] == "rest" and s["placeId"]):
                assert s.get("parking") is not None, s["name"]
                assert "rub" in s["parking"] and "zoneRu" in s["parking"], s["name"]
            if s["kind"] == "sight" and s["placeId"]:
                assert s.get("poiKindRu"), s["name"]
                if s.get("placeSource") == "osm":
                    assert s["placeAttributionRu"] == "Данные о месте: © участники OpenStreetMap"
            if (s.get("reason") or "").startswith("Весело и познавательно"):
                assert s.get("funFor") and set(s["funFor"]) <= {"child", "dog", "adults"}, s["name"]


def _detour(s: dict[str, Any]) -> int:
    m = re.search(r"Крюк ≈ (\d+) мин", s.get("reason") or "")
    return int(m.group(1)) if m else 0


def sights(trip: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for d in trip["daysList"] for s in d["stops"] if s["kind"] == "sight"]


class S4AcceptanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        test_mobile_v2.MobileV2Test.setUpClass()
        cat = mobile._CATALOGUE[0]
        if cat.version == "sample" or not any(p.quality is not None for p in cat.pois):
            raise unittest.SkipTest("sample or pre-Sprint-4 catalogue (no quality data)")
        cls.world = mobile._WORLDS["russia_v1"].world
        cls.town_names = {t.name_ru.casefold() for t in cls.world.towns.values()}

    @classmethod
    def tearDownClass(cls) -> None:
        mobile.set_clock("system")

    def category(self, s: dict[str, Any]) -> str:
        p = self.world.places.get(s["placeId"])
        return category_of(p) if p is not None else "attraction"

    def check_quality_rules(self, trip: dict[str, Any]) -> None:
        ss = sights(trip)
        self.assertTrue(ss)
        for s in ss:
            with self.subTest(stop=s["name"]):
                self.assertFalse(any(s["name"].casefold().startswith(b) for b in BAD_NAMES))
                self.assertFalse(s["name"].casefold() in self.town_names, "a town filed as a sight")
        free = [s for s in ss if s.get("replaceable")]  # ready-route template sights are not replaceable
        religious = [s for s in free if self.category(s) in RELIGIOUS]
        if free:
            self.assertLessEqual(
                len(religious), math.floor(0.30 * len(free)) or 0, [s["name"] for s in religious]
            )
        for d in trip["daysList"]:
            day = [s for s in d["stops"] if s["kind"] == "sight"]
            for a, b in itertools.pairwise(day):
                if not (a.get("replaceable") and b.get("replaceable")):
                    continue
                self.assertNotEqual(self.category(a), self.category(b), (a["name"], b["name"]))

    def quality_sights(self, trip: dict[str, Any]) -> list[dict[str, Any]]:
        out = []
        for s in sights(trip):
            p = self.world.places.get(s["placeId"])
            if p is not None and effective_quality(p) >= MIN_QUALITY and category_of(p) != "playground":
                out.append(s)
        return out

    def test_g14_fryazino_ekaterinburg(self) -> None:
        """M8 tiered detours: Владимир (Золотые ворота, крюк ≈ 35 мин) on day 1. Days 2-3 (Горбатов →
        Мариинский Посад → Сарапул, 480 and 552 km at a child's pace) have no tier-eligible sight that fits
        the day limit — Козьмодемьянск (q 0.61, 24 min) needs 99 min the day does not have, Нижний is 59
        min off M-7 — so the per-day rule is checked on the days that have room (see dev-notes M8)."""
        trip = plan("G14_fryazino_ekaterinburg_child")
        self.check_quality_rules(trip)
        playgrounds = [s for s in sights(trip) if self.category(s) == "playground"]
        self.assertLessEqual(len(playgrounds), 2)
        days = {d["day"] for d in trip["daysList"]}
        with_quality = {s["day"] for s in self.quality_sights(trip)}
        self.assertTrue({min(days), max(days)} <= with_quality, with_quality)

    def test_g18_moscow_kazan_m12(self) -> None:
        """M8: ≥ 3 quality sights on Москва → Казань by M-12, one of them off the motorway with an honest
        «Крюк ≈ N мин.»; every long detour (> 25 min) is a top-quality sight, at most one a day."""
        trip = plan("G18_moscow_kazan_m12")
        self.check_quality_rules(trip)
        good = self.quality_sights(trip)
        self.assertGreaterEqual(len(good), 3, [s["name"] for s in good])
        self.assertTrue(any("Крюк ≈" in s["reason"] for s in good))
        for d in trip["daysList"]:
            long = [s for s in d["stops"] if s["kind"] == "sight" and _detour(s) > 25]
            self.assertLessEqual(len(long), 1, [s["name"] for s in long])

    def test_g15_fryazino_golden_ring(self) -> None:
        trip = plan("G15_fryazino_golden_ring")
        self.check_quality_rules(trip)
        for s in sights(trip):
            self.assertGreater(haversine_km(LatLon(s["lat"], s["lon"]), MOSCOW), 12.0, s["name"])

    def test_g16_parking_line(self) -> None:
        trip = plan("G16_moscow_tretyakovka_yaroslavl")
        lines = {x["key"]: x for x in trip["cost"]["lines"]}
        self.assertIn("parking", lines)
        units = trip["cost"]["units"]["parking"]
        self.assertEqual(lines["parking"]["rub"], sum(u["rub"] or 0 for u in units))
        stops = {s["id"]: s for d in trip["daysList"] for s in d["stops"]}  # sights, cafés, rest areas
        for u in units:  # a weekday sight in Moscow's paid zones (≤ 17 km) pays; outside the zones it is free
            s = stops[u["stopId"]]
            in_centre = haversine_km(LatLon(s["lat"], s["lon"]), MOSCOW) <= 17.0
            self.assertEqual(u["source"] == "zone" and u["rub"] > 0, in_centre, s["name"])
            self.assertEqual(s["parking"]["rub"], u["rub"])
            self.assertTrue(s["parking"]["zoneRu"])
        kremlin = json.loads(
            mobile.plan(
                "russia_v1",
                "g16b",
                json.dumps(
                    {
                        "origin": {"lat": 55.7558, "lon": 37.6173, "label": "Москва"},
                        "destination": {"lat": 54.1961, "lon": 37.6182, "label": "Тула"},
                        "crew": {"adults": 2},
                        "dailyKm": 500,
                        "startAt": "2026-10-26T09:00",
                    }
                ),
                None,
            )
        )["result"]["trip"]
        paid = [u for u in kremlin["cost"]["units"]["parking"] if u["source"] == "zone"]
        self.assertTrue(paid)
        self.assertGreater(next(x for x in kremlin["cost"]["lines"] if x["key"] == "parking")["rub"], 0)

    def test_g17_fun_moscow_spb(self) -> None:
        """M-11 has places within the 15-minute detour at the rest windows; M-12 and M-4 mostly do not
        (motorway rest areas, few towns near the road) — see dev-notes «Sprint 4 data»."""
        trip = plan("G17_moscow_spb_fun_family")
        fun = [s for s in sights(trip) if s["reason"].startswith("Весело и познавательно")]
        self.assertGreaterEqual(len(fun), 1)
        for s in fun:
            self.assertNotIn(self.category(s), ("museum", "theatre", "interactive"), s["name"])  # dog aboard
        for d in trip["daysList"]:
            roadside = [s for s in d["stops"] if "площадки рядом нет" in (s.get("reason") or "")]
            self.assertLessEqual(len(roadside), 1)


if __name__ == "__main__":
    unittest.main()
