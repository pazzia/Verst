"""CEO 30.10: the walk «парки» uses the named OSM parks of `catalogue_parks` (Фрязино had none: no park
was a Wikidata sight there, so the walk said there was no data)."""

from __future__ import annotations

import json
import unittest
from typing import Any

from tests.unit.test_mobile import call, load_worlds
from verst_planner import mobile
from verst_planner.catalogue import CatalogueError, CatTown, parks_from_doc
from verst_planner.domain.model import LatLon

FRYAZINO = {"lat": 55.9606, "lon": 38.0456, "label": "Фрязино"}


def walk(interests: list[str], **kw: Any) -> dict[str, Any]:
    inp = {"start": FRYAZINO, "preset": "custom", "interests": interests, "durationMin": 120} | kw
    out: dict[str, Any] = call(mobile.city_route("russia_v1", "parks", json.dumps(inp)))
    return out


class ParksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_worlds()
        call(mobile.set_clock("golden"))
        if "russia_v1" not in call(mobile.selfcheck())["worlds"]:
            call(mobile.load_catalogue())

    def test_the_packaged_parks_load(self) -> None:
        self.assertGreater(len(mobile._PARKS), 3000)

    def test_fryazino_parks_walk_has_parks(self) -> None:
        r = walk(["parks"])
        parks = [s for s in r["stops"] if s["kind"] == "park"]
        self.assertGreaterEqual(len(parks), 2)
        for s in parks:
            self.assertEqual(s["poiKindRu"], "Парк")
            self.assertEqual(s["placeSource"], "osm")
        self.assertIsNone(r.get("noDataRu"))

    def test_park_card(self) -> None:
        pid = next(s["poiId"] for s in walk(["parks"])["stops"] if s["kind"] == "park")
        card = call(mobile.poi_details("russia_v1", pid))
        got = card["poiKind"], card["townName"], card["placeSource"]
        self.assertEqual(got, ("park", "Фрязино", "osm"))

    def test_parks_from_doc(self) -> None:
        towns = [CatTown.__new__(CatTown)]
        object.__setattr__(towns[0], "id", "Q1")
        doc = {
            "v": 1,
            "kinds": ["park", "garden"],
            "cols": {
                "id": ["osm_w1"],
                "name": ["Сад"],
                "kind": [1],
                "lat": [5500000],
                "lon": [3700000],
                "town": [0],
                "area": [12000],
                "poi": [None],
                "hours": [None],
            },
        }
        (p,) = parks_from_doc(doc, towns)
        self.assertEqual((p.kind, p.town, p.point, p.area_m2), ("garden", "Q1", LatLon(55.0, 37.0), 12000))
        with self.assertRaises(CatalogueError):
            parks_from_doc({"v": 2}, towns)


class AllInterestsTest(unittest.TestCase):
    """CEO 31.10: СПб, every interest, no time limit gave «мало мест»: 56 of the 60 pool places were cafés."""

    @classmethod
    def setUpClass(cls) -> None:
        load_worlds()
        call(mobile.set_clock("golden"))
        if "russia_v1" not in call(mobile.selfcheck())["worlds"]:
            call(mobile.load_catalogue())

    def test_spb_all_interests(self) -> None:
        every = ["history", "architecture", "museums", "parks", "food", "bars", "views"]
        for duration in (None, 240):
            inp = {
                "start": {"lat": 59.95, "lon": 30.3166, "label": "Петропавловская крепость"},
                "preset": "custom",
                "interests": every,
                "durationMin": duration,
                "adultConfirmed": True,
            }
            r = call(mobile.city_route("russia_v1", "spb", json.dumps(inp)))
            kinds = [s["kind"] for s in r["stops"]]
            self.assertGreaterEqual(len(kinds), 5, duration)
            eat = ("cafe", "restaurant", "fast_food", "food_court")
            self.assertGreaterEqual(sum(k not in eat for k in kinds), 3)
