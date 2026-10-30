import unittest
from datetime import UTC, date, datetime
from decimal import Decimal

from tests.helpers import UNIT_DATA
from verst_planner.adapters.fake import (
    FakeGeocoding,
    FakePlaceRepository,
    FakePriceRepository,
    FakeRegionLocator,
    FakeRouting,
    FakeTollRepository,
    FakeWorld,
    FixedClock,
    build_fakes,
)
from verst_planner.domain.enums import FuelType, PlaceType
from verst_planner.domain.errors import NotFound
from verst_planner.domain.model import LatLon, RouteRequest
from verst_planner.ports import (
    Clock,
    CorridorQuery,
    GeocodingPort,
    PlaceRepository,
    PriceRepository,
    RegionLocator,
    TollRepository,
)


class FakeReposTest(unittest.TestCase):
    def setUp(self) -> None:
        self.w = FakeWorld.load(UNIT_DATA / "mini_world.json")
        self.places: PlaceRepository = FakePlaceRepository(self.w)
        self.n = {k: v.point for k, v in self.w.nodes.items()}

    def test_corridor_query_radius(self) -> None:
        line = (self.n["N2"], self.n["N3"])
        ids = {
            p.id
            for p in self.places.places_in_corridor(CorridorQuery(line, 15.0, frozenset({PlaceType.SIGHT})))
        }
        self.assertIn("pl_sight_far", ids)  # 14.9 km
        self.assertNotIn("pl_sight_far2", ids)  # 15.1 km
        ids5 = {p.id for p in self.places.places_in_corridor(CorridorQuery(line, 5.0, frozenset(PlaceType)))}
        self.assertNotIn("pl_sight_far", ids5)
        self.assertIn("pl_rest_1", ids5)

    def test_status_live_only(self) -> None:
        line = (self.n["N0"], self.n["N1"], self.n["N2"])
        got = self.places.places_in_corridor(CorridorQuery(line, 15.0, frozenset({PlaceType.SIGHT})))
        self.assertNotIn("pl_draft_sight", {p.id for p in got})
        self.assertEqual(self.places.get_places(["pl_draft_sight", "nope"]).keys(), {"pl_draft_sight"})

    def test_types_filter_and_towns(self) -> None:
        line = (self.n["N0"], self.n["N1"], self.n["N2"], self.n["N3"])
        fuel = self.places.places_in_corridor(CorridorQuery(line, 15.0, frozenset({PlaceType.FUEL})))
        self.assertTrue(all(p.type is PlaceType.FUEL for p in fuel))
        towns = self.places.towns_in_corridor(line, 25.0)
        self.assertEqual([t.id for t in towns], ["t_alpha", "t_beta"])
        lodg = self.places.lodgings_of_towns(["t_beta", "t_gamma"])
        self.assertEqual([p.id for p in lodg["t_beta"]], ["pl_beta_hotel", "pl_beta_hotel_dog"])
        self.assertEqual(lodg["t_gamma"], [])
        self.assertEqual(set(self.places.get_towns(["t_beta", "x"])), {"t_beta"})
        rr = self.places.get_ready_route("rr_mini")
        assert rr is not None
        self.assertEqual(rr.hub_town_id, "t_alpha")
        self.assertIsNone(self.places.get_ready_route("nope"))
        self.assertEqual([r.id for r in self.places.ready_routes_near(self.n["N0"], 50, 10)], ["rr_mini"])
        self.assertEqual(self.places.ready_routes_near(self.n["N6"], 50, 10), [])

    def test_price_fallback_ru(self) -> None:
        prices: PriceRepository = FakePriceRepository(self.w)
        mos = prices.fuel_price("RU-MOS", FuelType.AI95)
        self.assertEqual((mos.price_rub, mos.as_of), (Decimal("61.20"), date(2026, 10, 1)))  # latest row
        sam = prices.fuel_price("RU-SAM", FuelType.AI95)
        self.assertEqual((sam.region_code, sam.price_rub), ("RU", Decimal("62.00")))
        self.assertEqual(prices.fuel_price("RU-MOS", FuelType.DT).region_code, "RU")
        self.assertEqual(prices.food_default_check(1_500_000), 900)
        self.assertEqual(prices.food_default_check(100_000), 700)
        self.assertEqual(prices.food_default_check(5_000), 550)
        self.assertEqual(prices.lodging_default_night(20_000), 4000)

    def test_price_missing_ru_raises(self) -> None:
        prices = FakePriceRepository(self.w)
        prices._latest = {}
        with self.assertRaises(NotFound):
            prices.fuel_price("RU-MOS", FuelType.AI95)

    def test_toll_hit_km_range(self) -> None:
        tolls: TollRepository = FakeTollRepository(self.w)
        routing = FakeRouting(self.w)
        paid = routing.route(RouteRequest((self.n["N0"], self.n["N5"]), False))
        hits = tolls.segments_on_route(paid)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].segment.id, "ts_m12")
        self.assertAlmostEqual(hits[0].km_from, 0.0, delta=0.2)
        self.assertAlmostEqual(hits[0].km_to, 52.0, delta=0.2)
        free = routing.route(RouteRequest((self.n["N0"], self.n["N5"]), True))
        self.assertEqual(tolls.segments_on_route(free), [])
        both_ways = routing.route(RouteRequest((self.n["N0"], self.n["N3"], self.n["N0"]), False))
        two = tolls.segments_on_route(both_ways)
        self.assertEqual(len(two), 2)
        self.assertAlmostEqual(two[1].km_from, 104 + 52, delta=0.3)
        self.assertAlmostEqual(two[1].km_to, 208, delta=0.3)

    def test_region_locator_and_geocoding(self) -> None:
        regions: RegionLocator = FakeRegionLocator(self.w)
        self.assertEqual(regions.locate(self.n["N5"]).tz, "Europe/Samara")
        self.assertEqual(regions.locate(self.n["N1"]).code, "RU-MOS")
        geo: GeocodingPort = FakeGeocoding(self.w)
        s = geo.suggest("бет", self.n["N0"], 5)
        self.assertEqual(s[0].name_ru, "Бета")
        self.assertEqual(s[0].kind, "city")
        self.assertTrue(any(x.kind == "place" for x in s))
        self.assertEqual(geo.suggest("ЁЛКА", None, 5)[0].name_ru, "Кафе Ёлка")
        self.assertEqual(geo.suggest("", None, 5), [])
        self.assertEqual(len(geo.suggest("а", None, 2)), 2)
        label = geo.reverse(LatLon(56.46, 38.01))
        assert label is not None
        self.assertEqual((label.name_ru, label.region_code), ("Бета", "RU-MOS"))
        self.assertIsNone(geo.reverse(LatLon(60.0, 50.0)))

    def test_clock_and_build(self) -> None:
        clock: Clock = FixedClock(datetime.fromisoformat("2026-10-23T09:00:00+03:00"))
        self.assertEqual(clock.now(), datetime(2026, 10, 23, 6, 0, tzinfo=UTC))
        with self.assertRaises(ValueError):
            FixedClock(datetime(2026, 10, 23, 9, 0))
        fakes = build_fakes(self.w)
        self.assertEqual(len(fakes), 7)
        self.assertEqual(fakes.clock.now().hour, 6)


if __name__ == "__main__":
    unittest.main()
