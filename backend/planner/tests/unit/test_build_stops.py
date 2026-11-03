"""CEO 02.11 «настоящие точки»: `tools/data/build_stops.py` keeps what OSM says and invents nothing."""

from __future__ import annotations

import json
import unittest
from typing import Any

from tests.unit.test_data_fetchers import load
from verst_planner.catalogue import FUEL_BITS, LODGING_KINDS, ROADSIDE_KINDS

stops = load("build_stops")

TOWNS = [
    {"qid": "Q1", "name": "Ярославль", "lat": 57.62, "lon": 39.89, "population": 570_000},
    {"qid": "Q2", "name": "Ростов", "lat": 57.18, "lon": 39.41, "population": 30_000},
]
POS = {"Q1": 0, "Q2": 1}


def feature(fid: str, lat: float, lon: float, **tags: Any) -> str:
    return json.dumps(
        {
            "type": "Feature",
            "id": fid,
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": tags,
        }
    )


class LodgingTest(unittest.TestCase):
    def rows(self, *lines: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
        return stops.lodging_rows(lines, TOWNS, ["лукойл", "островок"], POS)

    def test_real_fields_only_unknowns_stay_null(self) -> None:
        rows, counts = self.rows(
            feature(
                "n1",
                57.625,
                39.88,
                tourism="hotel",
                name="Ярославская",
                stars="4",
                dog="yes",
                phone="+7 4852 000000; +7 4852 111111",
                website="https://example.org",
            ),
            feature("n2", 57.19, 39.40, tourism="guest_house", name="У реки"),
        )
        self.assertEqual(2, counts["kept"])
        a, b = rows
        self.assertEqual(
            ("osm_n1", "Ярославская", LODGING_KINDS.index("hotel"), 0),
            (a["id"], a["name"], a["kind"], a["town"]),
        )
        self.assertEqual(
            (4, 1, "+7 4852 000000", "https://example.org"), (a["stars"], a["dog"], a["phone"], a["site"])
        )
        # nothing assumed: no stars, rooms, dog policy, phone or site when OSM has none
        self.assertEqual(
            (None, None, None, None, None), (b["stars"], b["rooms"], b["dog"], b["phone"], b["site"])
        )
        self.assertEqual(1, b["town"])

    def test_dropped_unnamed_private_far_denied(self) -> None:
        rows, counts = self.rows(
            feature("n1", 57.62, 39.89, tourism="hotel"),  # no name
            feature("n2", 57.62, 39.89, tourism="hotel", name="Закрытый", access="private"),
            feature("n3", 58.50, 41.00, tourism="motel", name="В поле"),  # no town within reach
            feature("n4", 57.62, 39.89, tourism="hostel", name="Островок у вокзала"),  # deny-listed brand
            feature("n5", 57.62, 39.89, tourism="camp_site", name="Кемпинг"),  # not a lodging kind (yet)
        )
        self.assertEqual([], rows)
        self.assertEqual((1, 1, 1), (counts["private"], counts["noTown"], counts["kind"]))

    def test_dog_no_is_known_no(self) -> None:
        rows, _ = self.rows(feature("n1", 57.62, 39.89, tourism="hotel", name="Без собак", pets="no"))
        self.assertEqual(0, rows[0]["dog"])


class RoadsideTest(unittest.TestCase):
    def test_every_station_with_its_real_name_fuels_known(self) -> None:
        rows, counts = stops.roadside_rows(
            [
                feature(
                    "n5",
                    56.0,
                    38.0,
                    amenity="fuel",
                    brand="Лукойл",
                    name="Лукойл",
                    **{"fuel:octane_92": "yes", "fuel:diesel": "no"},
                    opening_hours="24/7",
                    toilets="yes",
                ),
                feature("n6", 56.1, 38.1, amenity="fuel"),  # unnamed: kept, the app says «АЗС»
                # brand only: the brand is its name
                feature("n9", 56.15, 38.15, amenity="fuel", brand="Татнефть"),
                feature("w7", 56.2, 38.2, highway="rest_area", name="Стоянка у моста"),
                feature("n8", 56.3, 38.3, amenity="fuel", **{"disused:amenity": "fuel"}),
            ]
        )
        self.assertEqual(4, counts["kept"])
        by_id = {r["id"]: r for r in rows}
        lukoil = by_id["osm_n5"]
        # CEO 03.11 «Добавляй настоящие имена заправок»: the real chain name stays
        self.assertEqual("Лукойл", lukoil["name"])
        self.assertEqual("Татнефть", by_id["osm_n9"]["name"])
        self.assertEqual(
            (FUEL_BITS["ai92"], FUEL_BITS["dt"], "24/7", 1),
            (lukoil["fuel"], lukoil["nofuel"], lukoil["hours"], lukoil["wc"]),
        )
        bare = by_id["osm_n6"]
        self.assertEqual(
            (None, None, None, None, None),
            (bare["name"], bare["fuel"], bare["nofuel"], bare["hours"], bare["wc"]),
        )
        rest = by_id["osm_w7"]
        self.assertEqual((ROADSIDE_KINDS.index("rest_area"), "Стоянка у моста"), (rest["kind"], rest["name"]))


def road(fid: str, *pts: tuple[float, float]) -> str:
    return json.dumps(
        {
            "type": "Feature",
            "id": fid,
            "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in pts]},
            "properties": {"highway": "trunk"},
        }
    )


class RoadsideFoodTest(unittest.TestCase):
    """CEO 03.11 «Добавляй конечно придорожные кафе»: named cafés near a main road and outside the towns."""

    def test_near_a_main_road_outside_towns_only(self) -> None:
        # a trunk road going east along 56.50° N, 38.00–38.20° E (no town there)
        cells = stops.road_cells([road("w1", (56.50, 38.00), (56.50, 38.20))])
        rows, counts = stops.roadside_food_rows(
            [
                feature("n1", 56.505, 38.10, amenity="cafe", name="Придорожное", toilets="yes"),  # ~0.6 km
                feature("n2", 56.56, 38.10, amenity="cafe", name="В лесу"),  # ~6.7 km off the road
                feature("n3", 57.62, 39.89, amenity="restaurant", name="В Ярославле"),  # a town café
                feature("n4", 56.50, 38.05, amenity="fast_food"),  # no name
                feature("n5", 56.50, 38.15, amenity="bar", name="Бар"),  # not food for lunch
            ],
            TOWNS,
            cells,
        )
        self.assertEqual(["osm_n1"], [r["id"] for r in rows])
        self.assertEqual((1, 1), (counts["farFromRoad"], counts["inTown"]))
        cafe = rows[0]
        self.assertEqual(
            (ROADSIDE_KINDS.index("cafe"), "Придорожное", 1), (cafe["kind"], cafe["name"], cafe["wc"])
        )
        self.assertIsNone(cafe["hours"])  # nothing assumed

    def test_road_cells_cover_the_whole_line(self) -> None:
        cells = stops.road_cells([road("w1", (56.0, 38.0), (56.0, 38.5))])  # ~31 km, sampled every 200 m
        self.assertTrue(stops.near_road(56.0, 38.25, cells))
        self.assertTrue(stops.near_road(56.0, 38.4999, cells))
        self.assertFalse(stops.near_road(56.05, 38.25, cells))  # ~5.6 km north


if __name__ == "__main__":
    unittest.main()
