"""M8: the tiered detour budget of open-data sights and the million-city exception (pure rules)."""

from __future__ import annotations

import unittest

from verst_planner.domain.enums import PlaceStatus, PlaceType, RoadClass, Source
from verst_planner.domain.model import Candidate, LatLon, PartnerIds, Place, Town
from verst_planner.pipeline.sights import detour_ok, effective_quality, in_foreign_centre, long_detour

KAZAN = LatLon(55.7963, 49.1088)
ROAD = LatLon(56.0, 40.0)


def place(quality: float | None, rating: float = 4.0, point: LatLon = ROAD) -> Place:
    return Place(
        "p", PlaceType.SIGHT, "Место", point, None, "RU-X", None, None, 30, None, None, None, None, rating,
        frozenset(), None, PartnerIds(), Source.OSM, None, PlaceStatus.LIVE, quality=quality,
    )  # fmt: skip


def cand(p: Place, minutes: int, km: float = 0.0) -> Candidate:
    return Candidate(p, 100.0, km / 2.6, km, minutes, RoadClass.MOTORWAY, "RU-X")


def town(pop: int) -> Town:
    return Town("t", "Город", None, KAZAN, "RU-TA", pop, 3, True, 10)


class DetourTiersTest(unittest.TestCase):
    def test_tiers(self) -> None:
        self.assertTrue(detour_ok(cand(place(0.75), 45, 25)))
        self.assertFalse(detour_ok(cand(place(0.75), 46, 26)))
        self.assertTrue(detour_ok(cand(place(0.60), 25, 13)))
        self.assertFalse(detour_ok(cand(place(0.60), 30, 15)))
        self.assertTrue(detour_ok(cand(place(0.45), 22, 10)))  # the plain rule: ≤ 10 km of detour
        self.assertFalse(detour_ok(cand(place(0.45), 24, 11)))
        self.assertFalse(detour_ok(cand(place(0.35), 0, 0)))  # below the 0.40 bar
        self.assertTrue(long_detour(cand(place(0.75), 30)))
        self.assertFalse(long_detour(cand(place(0.75), 25)))

    def test_curated_quality_from_rating(self) -> None:
        self.assertEqual(effective_quality(place(None, 4.9)), 1.0)
        self.assertEqual(effective_quality(place(None, 3.6)), 0.0)
        self.assertTrue(detour_ok(cand(place(None, 4.8), 40, 22)))

    def test_million_city_exception(self) -> None:
        top = cand(place(0.8, point=KAZAN), 30)
        mid = cand(place(0.6, point=KAZAN), 20)
        self.assertTrue(in_foreign_centre(top, [town(1_300_000)], set()))
        self.assertFalse(in_foreign_centre(top, [town(1_300_000)], set(), tiered=True))
        self.assertTrue(in_foreign_centre(mid, [town(1_300_000)], set(), tiered=True))
        self.assertTrue(in_foreign_centre(top, [town(13_000_000)], set(), tiered=True))  # never Moscow
        self.assertFalse(in_foreign_centre(mid, [town(1_300_000)], {"t"}))  # the trip's own city


if __name__ == "__main__":
    unittest.main()
