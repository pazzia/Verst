"""ADR-0012 §4-5: composed world `russia_v1`, `HybridRouting`, indexed repositories, grid and model."""

from __future__ import annotations

import unittest

from tests.helpers import PLANNER_ROOT, WORLDS
from verst_planner.adapters.catalogue import build_catalogue_ports, compose, road_model
from verst_planner.adapters.catalogue.synthetic import cafes_for, hotels_for, roadside, roadside_id
from verst_planner.adapters.catalogue.world import poi_rating, town_quality
from verst_planner.adapters.fake import FakeWorld
from verst_planner.adapters.fake.routing import FakeRouting
from verst_planner.catalogue import Catalogue, from_docs
from verst_planner.domain.enums import PlaceType, Source, Tag
from verst_planner.domain.errors import Unreachable
from verst_planner.domain.model import LatLon, RouteRequest
from verst_planner.geo.distance import haversine_km
from verst_planner.geo.grid import GridIndex
from verst_planner.geo.roadmodel import RoadModel
from verst_planner.ports import CorridorQuery


def sample_catalogue() -> Catalogue:
    """The catalogue built from the recorded samples (independent of the packaged data)."""
    from tests.unit.test_catalogue import SAMPLES, builder

    d = builder().build(SAMPLES, "sample", "2026-10-25")
    return from_docs(d["meta"], d["towns"], d["pois"], d["bars"])


MOSCOW = LatLon(55.7558, 37.6173)
YAROSLAVL = LatLon(57.6261, 39.8845)
SPB = LatLon(59.9386, 30.3141)
PERM = LatLon(58.0105, 56.2502)


class ComposeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = FakeWorld.load(WORLDS / "central_russia_v1.json")
        cls.cat = sample_catalogue()
        cls.cw = compose(cls.fixture, cls.cat)
        cls.ports = build_catalogue_ports(cls.cw)

    def test_fixture_items_win_and_keep_ids(self) -> None:
        w = self.cw.world
        self.assertEqual(w.id, "russia_v1")
        for fid, link in self.cat.links.items():
            self.assertNotIn(link.wikidata, w.places if fid.startswith("pl_") else w.towns)
            self.assertIn(fid, w.places if fid.startswith("pl_") else w.towns)
        self.assertEqual(self.cw.town_of_qid["Q649"], "t_moscow")
        self.assertEqual(set(self.fixture.places) - set(w.places), set())

    def test_catalogue_towns_get_fictional_services(self) -> None:
        w = self.cw.world
        for tid in sorted(self.cw.synthetic_towns):
            hotels = [p for p in w.places.values() if p.town_id == tid and p.type is PlaceType.LODGING]
            cafes = [p for p in w.places.values() if p.town_id == tid and p.type is PlaceType.FOOD]
            self.assertEqual((len(hotels), len(cafes)), (3, 2), tid)
            self.assertEqual(sum(Tag.DOGS_ALLOWED in h.tags for h in hotels), 1)
            self.assertTrue(all(h.price_night_rub and h.price_night_rub % 100 == 0 for h in hotels))
        town = w.towns["Q900006"]
        self.assertEqual(hotels_for(town, 5000), hotels_for(town, 5000))  # deterministic
        self.assertEqual(len(cafes_for(town, 700)), 2)

    def test_pois_become_open_data_sights(self) -> None:
        p = self.cw.world.places["Q900101"]
        self.assertEqual((p.type, p.source), (PlaceType.SIGHT, Source.OSM))
        self.assertEqual(p.ticket_adult_rub, 400)
        self.assertEqual(p.dwell_min, 90)  # big museum
        self.assertIn(Tag.FREE_ENTRY, self.cw.world.places["Q900107"].tags)
        self.assertLess(poi_rating(0), poi_rating(150))
        self.assertEqual([town_quality(x) for x in (0, 20, 100, 300)], [0, 1, 2, 3])

    def test_roadside_ids_round_trip(self) -> None:
        pid = roadside_id("f", LatLon(58.1, 50.2))
        p = roadside(pid, "RU-KIR")
        assert p is not None
        self.assertEqual((p.type, p.point), (PlaceType.FUEL, LatLon(58.1, 50.2)))
        rest = roadside(roadside_id("r", LatLon(58.1, 50.2)), "RU-KIR")
        assert rest is not None
        self.assertIs(rest.type, PlaceType.REST)
        for bad in ("syn_h_x_0", "syn_f_a_b", "x"):
            self.assertIsNone(roadside(bad, "RU"))

    # ------------------------------------------------------------------ routing
    def test_graph_route_unchanged(self) -> None:
        req = RouteRequest((MOSCOW, YAROSLAVL), False)
        a = self.ports.routing.route(req)
        b = FakeRouting(self.fixture).route(req)
        self.assertEqual((a.km_total, a.min_total, a.points), (b.km_total, b.min_total, b.points))
        self.assertFalse(a.synthetic)

    def test_access_legs_near_the_graph(self) -> None:
        off = LatLon(55.80, 37.50)  # an address in Moscow, ~9 km from the graph node
        r = self.ports.routing.route(RouteRequest((off, YAROSLAVL), False))
        self.assertFalse(r.synthetic)
        self.assertEqual(r.points[0], off)
        self.assertEqual(r.snapped[0], off)
        base = FakeRouting(self.fixture).route(RouteRequest((MOSCOW, YAROSLAVL), False)).km_total
        self.assertGreater(r.km_total, base - 15)
        r2 = self.ports.routing.route(RouteRequest((YAROSLAVL, off), False))
        self.assertEqual(r2.points[-1], off)
        self.assertEqual(r2.waypoint_idx[-1], len(r2.points) - 1)

    def test_synthetic_route_uses_the_model(self) -> None:
        r = self.ports.routing.route(RouteRequest((SPB, PERM), False))
        self.assertTrue(r.synthetic)
        h = haversine_km(SPB, PERM)
        self.assertAlmostEqual(r.km_total, road_model().road_km(h), places=6)
        self.assertEqual(len(r.cum_km), len(r.points))
        self.assertEqual(r.waypoint_idx, (0, len(r.points) - 1))

    def test_unreachable(self) -> None:
        with self.assertRaises(Unreachable) as e:
            self.ports.routing.route(RouteRequest((SPB, LatLon(74.0, 75.0)), False))
        self.assertEqual(e.exception.point_index, 1)
        with self.assertRaises(Unreachable):
            self.ports.routing.route(RouteRequest((SPB,), False))

    # ------------------------------------------------------------------ repositories
    def test_synthetic_roadside_only_off_the_graph(self) -> None:
        places = self.ports.places
        far = places.places_in_corridor(CorridorQuery((SPB, PERM), 15, frozenset({PlaceType.FUEL})))
        syn = [p for p in far if p.id.startswith("syn_f_")]
        self.assertGreater(len(syn), 10)
        got = places.get_places([syn[0].id, "nope"])
        self.assertEqual(list(got), [syn[0].id])
        near = places.places_in_corridor(
            CorridorQuery((MOSCOW, YAROSLAVL), 15, frozenset({PlaceType.FUEL, PlaceType.REST}))
        )
        self.assertFalse(any(p.id.startswith("syn_") for p in near))
        self.assertEqual(
            places.places_in_corridor(CorridorQuery((SPB,), 15, frozenset({PlaceType.FUEL}))), []
        )

    def test_towns_lodgings_and_near(self) -> None:
        places = self.ports.places
        towns = places.towns_in_corridor((MOSCOW, YAROSLAVL), 25)
        self.assertIn("t_rostov", [t.id for t in towns])
        lod = places.lodgings_of_towns(["Q900006", "none"])
        self.assertEqual((len(lod["Q900006"]), lod["none"]), (3, []))
        near = places.places_near(SPB, 2.0, frozenset({PlaceType.SIGHT}))
        self.assertIn("Q900107", [p.id for p in near])
        ds = [haversine_km(SPB, p.point) for p in near]
        self.assertEqual(ds, sorted(ds))

    def test_geocoding_and_regions(self) -> None:
        g = self.ports.geocoding
        self.assertEqual(g.suggest("санкт", None, 3)[0].name_ru, "Санкт-Петербург")
        self.assertEqual(g.suggest("  ", None, 3), [])
        self.assertEqual(g.suggest("Эрми", SPB, 3)[0].kind, "place")
        rev = g.reverse(LatLon(57.63, 39.87))
        assert rev is not None
        self.assertEqual(rev.name_ru, "Ярославль")
        self.assertIsNone(g.reverse(LatLon(70.0, 100.0)))
        self.assertEqual(self.ports.regions.locate(PERM).code, "RU-PER")
        self.assertEqual(self.ports.regions.locate(PERM).tz, "Asia/Yekaterinburg")
        self.assertEqual(self.ports.regions.locate(YAROSLAVL).code, "RU-YAR")


class GridAndModelTest(unittest.TestCase):
    def test_grid(self) -> None:
        g: GridIndex[str] = GridIndex(0.1)
        g.extend([(LatLon(55.0, 37.0), "a"), (LatLon(55.05, 37.0), "b"), (LatLon(56.0, 37.0), "c")])
        self.assertEqual(g.size, 3)
        self.assertEqual([x for _d, x in g.within(LatLon(55.0, 37.0), 10)], ["a", "b"])
        hit = g.nearest(LatLon(55.9, 37.0), 500)
        assert hit is not None
        self.assertEqual(hit[1], "c")
        self.assertIsNone(g.nearest(LatLon(70.0, 37.0), 50))
        self.assertEqual(
            sorted(x for _p, x in g.near_line((LatLon(55.0, 36.9), LatLon(55.0, 37.1)), 7)), ["a", "b"]
        )
        self.assertEqual(list(g.near_line((), 5)), [])
        self.assertEqual([x for _p, x in g.near_line((LatLon(56.0, 37.0),), 1)], ["c"])

    def test_road_model(self) -> None:
        m = RoadModel.from_dict(
            {
                "points": [
                    {"straightKm": 100, "ratio": 1.1, "speedKmh": 60},
                    {"straightKm": 300, "ratio": 1.3, "speedKmh": 80},
                ]
            }
        )
        self.assertAlmostEqual(m.ratio(50), 1.1)
        self.assertAlmostEqual(m.ratio(200), 1.2)
        self.assertAlmostEqual(m.ratio(900), 1.3)
        self.assertAlmostEqual(m.minutes(100), 110.0)
        with self.assertRaises(ValueError):
            RoadModel.from_dict({"points": []})

    def test_calibration_is_committed(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("cal", PLANNER_ROOT / "tools" / "calibrate_detour.py")
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.main(["--check"]), 0)
        err = road_model()
        self.assertGreater(err.ratio(700), err.ratio(60))


if __name__ == "__main__":
    unittest.main()
