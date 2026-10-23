import copy
import json
import unittest
from typing import Any

from tests.helpers import UNIT_DATA
from verst_planner.adapters.fake import FakeWorld
from verst_planner.adapters.fake.world import point_on_edge
from verst_planner.domain.enums import PlaceStatus, PlaceType, Tag
from verst_planner.geo.distance import point_segment_km


def mini() -> dict[str, Any]:
    with (UNIT_DATA / "mini_world.json").open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data


class FakeWorldTest(unittest.TestCase):
    def test_loads_mini_world(self) -> None:
        w = FakeWorld.load(UNIT_DATA / "mini_world.json")
        self.assertEqual(len(w.nodes), 8)
        self.assertEqual(len(w.towns), 3)
        self.assertEqual(len(w.places), 12)
        self.assertEqual(len(w.tolls), 1)
        self.assertEqual(len(w.regions), 2)
        self.assertEqual(w.towns["t_beta"].lodging_count_cache, 2)
        self.assertEqual(w.towns["t_beta"].point, w.nodes["N2"].point)
        self.assertEqual(w.places["pl_draft_sight"].status, PlaceStatus.DRAFT)
        self.assertEqual(w.places["pl_fuel_1"].tags, frozenset({Tag.CAFE_AT_FUEL, Tag.H24, Tag.WC}))
        self.assertEqual(w.places["pl_beta_hotel"].type, PlaceType.LODGING)
        self.assertFalse(w.places["pl_beta_hotel_dog"].breakfast_included)
        self.assertEqual(w.ready_routes["rr_mini"].suggested_nights, ("t_beta",))
        self.assertEqual(w.places["pl_alpha_hotel"].region_code, "RU-MOS")

    def test_anchor_lateral_is_left_of_travel(self) -> None:
        w = FakeWorld.load(UNIT_DATA / "mini_world.json")
        far = w.places["pl_sight_far"].point
        n2, n3 = w.nodes["N2"].point, w.nodes["N3"].point
        self.assertAlmostEqual(point_segment_km(far, n2, n3), 14.9, delta=1e-6)
        self.assertLess(far.lon, n2.lon)  # northbound: left = west
        p = point_on_edge(n2, n3, 0.5, -2.0)
        self.assertGreater(p.lon, n2.lon)

    def test_invalid_world_messages(self) -> None:
        d = mini()
        d["places"][3]["id"] = d["places"][0]["id"]
        with self.assertRaises(ValueError) as cm:
            FakeWorld.from_dict(d)
        self.assertIn("places[3].id", str(cm.exception))

        d = mini()
        d["edges"][2]["km"] = 40  # straight line N2-N3 is 50 km
        with self.assertRaises(ValueError) as cm:
            FakeWorld.from_dict(d)
        self.assertIn("edges[2].km", str(cm.exception))

    def test_other_validation_rules(self) -> None:
        cases: list[tuple[str, str]] = []

        def mutate(fn: Any, expect: str) -> None:
            d = copy.deepcopy(mini())
            fn(d)
            with self.subTest(expect=expect), self.assertRaises(ValueError) as cm:
                FakeWorld.from_dict(d)
            cases.append((expect, str(cm.exception)))
            self.assertIn(expect, str(cm.exception))

        mutate(lambda d: d["places"][0].update({"lat": 56.0, "lon": 38.0}), "places[0]")
        mutate(lambda d: d["places"][1].pop("anchor"), "places[1]")
        mutate(lambda d: d["places"][2]["tags"].append("cats_allowed"), "places[2].tags[1]")
        mutate(lambda d: d["towns"][1].update({"node": "NOPE"}), "towns[1].node")
        mutate(lambda d: d["readyRoutes"][0]["points"][1].update({"placeId": "pl_nope"}), "points[1].placeId")
        mutate(lambda d: d["readyRoutes"][0].update({"suggestedNights": ["t_nope"]}), "suggestedNights[0]")
        mutate(lambda d: d["regionPrices"].pop(), "missing RU row for dt")
        mutate(lambda d: d["edges"][0].update({"to": "ZZ"}), "edges[0].to")
        mutate(lambda d: d["places"][4]["anchor"].update({"edge": ["N1", "N3"]}), "places[4].anchor.edge")
        mutate(lambda d: d["nodes"][1].update({"id": "N0"}), "nodes[1].id")
        mutate(lambda d: d["tollSegments"][0].update({"toKm": 99}), "tollSegments[0].toKm")
        self.assertEqual(len(cases), 11)


if __name__ == "__main__":
    unittest.main()
