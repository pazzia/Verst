"""Sprint 4 M6: the API v3 answers to the Developer (docs/dev-notes.md «Sprint 4 engine»): the walk
`requestKey`, the trip stop `poiKind` / `whyRu` / `photoSource` / `parking` sheet, the alternative's own
parking (`parkingRub`…) in the replace and the recompute."""

from __future__ import annotations

import dataclasses
import json
import unittest
from datetime import datetime
from typing import Any

from tests.unit import test_mobile_v2
from verst_planner import mobile
from verst_planner.cost.recompute import effective_parking, recompute
from verst_planner.domain import codec
from verst_planner.domain.model import AltUnits, CostOverrides, Crew, LatLon, ParkingUnit
from verst_planner.engine import _units_after_replace
from verst_planner.parking import OsmParking, ParkingModel

R = "russia_v1"
YAR = {"lat": 57.6261, "lon": 39.8845, "label": "Ярославль"}
KREMLIN = LatLon(55.752, 37.617)
WED = datetime(2026, 10, 21, 12, 0)


def walk(**kw: Any) -> dict[str, Any]:
    out: dict[str, Any] = json.loads(mobile.city_route(R, "v3", json.dumps({"start": YAR, **kw})))
    return out


class ParkingSheetTest(unittest.TestCase):
    def sheet(self, point: LatLon, at: datetime, model: ParkingModel | None = None) -> dict[str, Any]:
        m = model or ParkingModel.from_resources()
        return mobile.parking_sheet(m.explain(point, at), {})

    def test_zone_texts(self) -> None:
        s = self.sheet(KREMLIN, WED)
        self.assertEqual(
            s["zoneRu"], "Москва: платная зона до 2 км от центра, 380 ₽/ч с 08:00 до 21:00, ночью 200 ₽/ч"
        )
        self.assertEqual(s["sundayRu"], "В воскресенье здесь тоже платно; в праздники бесплатно")
        self.assertIsNone(s["freeRu"])
        far = self.sheet(LatLon(55.80, 37.45), datetime(2026, 10, 25, 12))
        self.assertEqual(
            (far["sundayRu"], far["freeRu"]),
            (
                "По воскресеньям бесплатно; в праздники бесплатно",
                "Бесплатно: воскресенье",
            ),
        )
        self.assertEqual(
            self.sheet(KREMLIN, datetime(2026, 11, 4, 12))["freeRu"], "Бесплатно: праздничный день"
        )
        spb = self.sheet(LatLon(59.9386, 30.3141), WED.replace(hour=21))
        self.assertIn("2,5 км", spb["zoneRu"])
        self.assertIn("ночью бесплатно", spb["zoneRu"])
        self.assertEqual(spb["sundayRu"], "В воскресенье платно")
        self.assertEqual(spb["freeRu"], "Бесплатно ночью; платно с 08:00 до 20:00")

    def test_osm_and_none(self) -> None:
        yar = LatLon(57.626, 39.884)
        m = ParkingModel.from_resources([OsmParking(yar, 50)])
        s = self.sheet(LatLon(57.627, 39.884), WED, m)
        self.assertEqual(s["zoneRu"], "Платная парковка по данным OpenStreetMap")
        self.assertEqual(s["whereRu"], "Парковка в 111 м от объекта")
        self.assertIsNone(s["sundayRu"])
        none = self.sheet(LatLon(57.0, 41.0), WED)
        self.assertEqual(
            (none["zoneRu"], none["freeRu"]), ("Платных зон рядом нет", "Бесплатно: вне платных зон")
        )


class AltParkingTest(unittest.TestCase):
    def test_replace_bakes_the_same_as_recompute(self) -> None:
        """`_units_after_replace` + recompute == recompute with the override (rule 5)."""
        units = codec.units_from_json(
            json.loads((test_mobile_v2.V2 / "plan-budget-fit.json").read_text("utf-8"))["response"]["result"][
                "trip"
            ]["cost"]["units"]
        )
        units = dataclasses.replace(
            units, parking=(ParkingUnit("d1s02", "Кремль", 380, 2, 760, "zone"), *units.parking[1:])
        )
        alt = AltUnits(
            0.4, "RU-MOS", None, 500, 0, "Музей", "pl_m", parking=ParkingUnit("", "", 200, 1, 200, "zone")
        )
        crew = Crew(2, 0, False)
        a = recompute(units, crew, True, None, CostOverrides(replaced={"d1s02": alt}))
        b = recompute(_units_after_replace(units, "d1s02", alt), crew, True, None)
        self.assertEqual((a.lines, a.total_rub, a.subtotal_rub), (b.lines, b.total_rub, b.subtotal_rub))
        parks = effective_parking(units, CostOverrides(replaced={"d1s02": alt}))
        self.assertEqual((parks[0].stop_id, parks[0].name_ru, parks[0].rub), ("d1s02", "Музей", 200))
        line = next(x for x in a.lines if x.key.value == "parking")
        self.assertEqual(line.rub, 200)

    def test_alt_units_json_roundtrip(self) -> None:
        alt = AltUnits(
            0.4,
            "RU-MOS",
            None,
            500,
            0,
            "Музей",
            "pl_m",
            parking=ParkingUnit("", "Музей", None, 1, None, "unknown"),
        )
        j = codec.alt_units_to_json(alt)
        self.assertEqual(
            {k: j[k] for k in j if k.startswith("parking")},
            {"parkingRub": None, "parkingRubPerHour": None, "parkingHours": 1, "parkingSource": "unknown"},
        )
        self.assertEqual(codec.alt_units_from_json(j), alt)
        bare = codec.alt_units_to_json(dataclasses.replace(alt, parking=None))
        self.assertNotIn("parkingRub", bare)  # no parking data: the v2 shape, byte for byte


class BridgeV3Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        test_mobile_v2.MobileV2Test.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        mobile.set_clock("system")

    def test_walk_request_key(self) -> None:
        a = walk(preset="overview")
        b = walk(preset="overview")
        c = walk(preset="overview", pace="slow")
        self.assertTrue(a["ok"] and c["ok"])
        key = a["result"]["requestKey"]
        self.assertRegex(key, "^[0-9a-f]{16}$")
        self.assertEqual(key, b["result"]["requestKey"])
        self.assertNotEqual(key, c["result"]["requestKey"])
        self.assertIs(a["result"]["input"]["crew"]["dog"], False)
        dry = json.loads(
            mobile.city_route(
                R,
                "v3e",
                json.dumps(
                    {
                        "start": test_mobile_v2.MobileV2Test._town_without_bars(),
                        "preset": "beer",
                        "adultConfirmed": True,
                    }
                ),
            )
        )
        self.assertEqual(dry["error"]["code"], "NOT_ENOUGH_POIS")
        self.assertRegex(dry["error"]["requestKey"], "^[0-9a-f]{16}$")

    def test_trip_stop_details(self) -> None:
        mobile.set_clock("2026-10-21T08:00:00+03:00")
        inp = {
            "origin": {"lat": 55.7414, "lon": 37.6208, "label": "Третьяковская"},
            "destination": YAR,
            "crew": {"adults": 2},
            "dailyKm": 500,
            "startAt": "2026-10-22T09:00",
        }
        r = json.loads(mobile.plan(R, "v3p", json.dumps(inp, ensure_ascii=False), None))
        trip = r["result"]["trip"]
        sights = [s for d in trip["daysList"] for s in d["stops"] if s["kind"] == "sight"]
        self.assertTrue(sights)
        units = {u["stopId"]: u for u in trip["cost"]["units"]["parking"]}
        for s in sights:
            self.assertIsInstance(s["poiKind"], str)
            self.assertNotEqual(s["poiKind"], "")
            self.assertIn(s["photoSource"], (None, "p18", "wikipedia", "osm", "geosearch"))
            self.assertIn("whyRu", s)
            self.assertEqual(s["parking"]["rub"], units[s["id"]]["rub"])
            for k in ("zoneRu", "whereRu", "sundayRu", "freeRu"):
                self.assertIn(k, s["parking"])
            for a in s["alternatives"]:
                if a["stop"]["kind"] == "sight":
                    self.assertIn("parkingSource", a["units"])
                    self.assertEqual(a["stop"]["parking"]["rub"], a["units"]["parkingRub"])
        rest = [s for d in trip["daysList"] for s in d["stops"] if s["kind"] != "sight"]
        self.assertFalse(any("poiKind" in s for s in rest))
        card = json.loads(mobile.poi_details(R, sights[0]["placeId"]))["result"]
        self.assertEqual(card["poiKind"], sights[0]["poiKind"])
        self.assertIn("whyRu", card)
        if card["image"] is not None:
            self.assertIn(card["image"]["source"], ("p18", "wikipedia", "osm", "geosearch"))

    def test_fixture_trips_have_no_parking(self) -> None:
        mobile.set_clock("golden")
        inp = {
            "origin": {"lat": 55.7558, "lon": 37.6173},
            "destination": YAR,
            "crew": {"adults": 2},
            "dailyKm": 500,
        }
        trip = json.loads(mobile.plan("central_russia_v1", "v3f", json.dumps(inp), None))["result"]["trip"]
        stops = [s for d in trip["daysList"] for s in d["stops"] if s["kind"] == "sight"]
        self.assertTrue(stops)
        self.assertTrue(all(s["parking"] is None for s in stops))
        self.assertNotIn("parking", trip["cost"]["units"])


if __name__ == "__main__":
    unittest.main()
