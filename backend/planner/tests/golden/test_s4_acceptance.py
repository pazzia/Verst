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
from verst_planner.pipeline.sights import MIN_QUALITY, RELIGIOUS, category_of, effective_quality, signature

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
        # the cap counts the added open-data sights: not the ready-route template stops (not replaceable)
        # and not the ring's signature sites (hand-curated kremlins and monasteries, M9 follow-up)
        free = [
            s
            for s in ss
            if s.get("replaceable")
            and not (s["placeId"] in self.world.places and signature(self.world.places[s["placeId"]]))
        ]
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
        """Acceptance 2026-10-28 (K2): the anchor towns. Day 1 now ends in Нижний Новгород (509 km at a
        child's pace, arrival ≈ 17:00) instead of Горбатов, so the Владимир detour (Золотые ворота) no longer
        fits day 1 and the last day (≈ 630 km) has no room either; the quality sight is the morning in
        Нижний (its kremlin). Before: Владимир on day 1 (M8 tiered detours, see dev-notes M8)."""
        trip = plan("G14_fryazino_ekaterinburg_child")
        self.check_quality_rules(trip)
        playgrounds = [s for s in sights(trip) if self.category(s) == "playground"]
        self.assertLessEqual(len(playgrounds), 2)
        nights = [d["stops"][-1]["name"] for d in trip["daysList"][:-1]]
        self.assertEqual(nights[0], "Нижний Новгород")
        good = self.quality_sights(trip)
        self.assertTrue(good, [s["name"] for s in sights(trip)])
        morning = [s for s in good if s["day"] == 2 and s["reason"].startswith("Утро в городе ночёвки")]
        self.assertTrue(morning, [s["name"] for s in good])

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
        """The ring keeps its signature sites (Лавра, Ипатьевский, the Суздаль and Ростов kremlins) and its
        template days; the religious cap applies to the added open-data sights only."""
        trip = plan("G15_fryazino_golden_ring")
        self.check_quality_rules(trip)
        names = {s["name"] for s in sights(trip)}
        signature = {
            "Троице-Сергиева лавра",
            "Ипатьевский монастырь",
            "Суздальский кремль",
            "Ростовский кремль",
        }
        self.assertTrue(signature <= names, names)
        # M9: a ready route keeps its template days and night towns (3 days; Ярославль, Суздаль)
        self.assertEqual(len(trip["daysList"]), 3)
        nights = [d["stops"][-1]["name"] for d in trip["daysList"][:-1]]
        self.assertEqual(nights, ["Ярославль", "Суздаль"])
        self.assertFalse(any("филармони" in n.casefold() for n in names))
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
        # acceptance 2026-10-28 (K1 a): a trip *from* Москва has no sight in Москва any more (the home
        # zone), so the paid-zone check runs the other way: Москва is the destination, its centre is allowed
        kremlin = json.loads(
            mobile.plan(
                "russia_v1",
                "g16b",
                json.dumps(
                    {
                        "origin": {"lat": 54.1961, "lon": 37.6182, "label": "Тула"},
                        "destination": {"lat": 55.7558, "lon": 37.6173, "label": "Москва"},
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
