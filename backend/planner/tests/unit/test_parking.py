"""ADR-0015 §4: the static parking model (zones, Sunday/holiday rules, OSM fee and charge)."""

from __future__ import annotations

import unittest
from datetime import datetime

from verst_planner.domain.model import LatLon
from verst_planner.parking import OsmParking, ParkingModel, charge_per_hour

KREMLIN = LatLon(55.752, 37.617)
MKAD_IN = LatLon(55.80, 37.45)  # ~12 km from the centre: the 80 ₽ band
YAR = LatLon(57.626, 39.884)
WED = datetime(2026, 10, 21, 12, 0)
SUN = datetime(2026, 10, 25, 12, 0)


class ParkingTest(unittest.TestCase):
    def test_charge(self) -> None:
        self.assertEqual(charge_per_hour("100 RUB/hour"), 100)
        self.assertEqual(charge_per_hour("60 ₽/ч"), 60)
        self.assertEqual(charge_per_hour("2 руб/мин"), 120)
        self.assertEqual(charge_per_hour("50 руб. в час"), 50)
        self.assertIsNone(charge_per_hour("platno"))
        self.assertIsNone(charge_per_hour(None))

    def test_zones_and_days(self) -> None:
        m = ParkingModel.from_resources()
        self.assertEqual(m.rate(KREMLIN, WED), (380, "zone"))
        self.assertEqual(m.rate(KREMLIN, WED.replace(hour=22)), (200, "zone"))
        self.assertEqual(m.rate(MKAD_IN, WED), (80, "zone"))
        self.assertEqual(m.rate(MKAD_IN, SUN), (0, "free"))  # Sunday free below the 380 zone
        self.assertEqual(m.rate(KREMLIN, SUN), (380, "zone"))  # the top zone is paid on Sundays
        self.assertEqual(m.rate(KREMLIN, datetime(2026, 11, 4, 12)), (0, "free"))  # a holiday
        self.assertEqual(
            m.rate(LatLon(59.9386, 30.3141), WED.replace(hour=21)), (0, "free")
        )  # СПб after 20:00
        self.assertEqual(m.rate(YAR, WED), (0, "free"))

    def test_osm_and_units(self) -> None:
        m = ParkingModel.from_resources([OsmParking(YAR, 50), OsmParking(LatLon(57.0, 40.0), None)])
        self.assertEqual(m.rate(YAR, WED), (50, "osm"))
        self.assertEqual(m.rate(LatLon(57.0005, 40.0), WED), (None, "unknown"))
        u = m.unit("d1s02", "Кремль", KREMLIN, WED, 95)
        self.assertEqual((u.rub_per_hour, u.hours, u.rub, u.source), (380, 2, 760, "zone"))
        self.assertIsNone(m.unit("x", "?", LatLon(57.0005, 40.0), WED, 30).rub)


if __name__ == "__main__":
    unittest.main()
