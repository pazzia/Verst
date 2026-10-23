import itertools
import unittest
from functools import cache

from tests.helpers import WORLDS
from verst_planner.adapters.fake import FakeRouting, FakeWorld
from verst_planner.domain.enums import PlaceType, Tag
from verst_planner.domain.errors import Unreachable
from verst_planner.domain.model import LatLon, RouteRequest
from verst_planner.geo.distance import haversine_km, point_segment_km

REQUIRED_REGIONS = [
    "RU",
    "RU-MOW",
    "RU-MOS",
    "RU-YAR",
    "RU-KOS",
    "RU-IVA",
    "RU-VLA",
    "RU-NIZ",
    "RU-CU",
    "RU-TA",
    "RU-TUL",
    "RU-RYA",
    "RU-LIP",
    "RU-TAM",
    "RU-VOR",
    "RU-VGG",
]
REQUIRED_TOWNS = [
    "Сергиев Посад",
    "Переславль-Залесский",
    "Ростов",
    "Ярославль",
    "Кострома",
    "Иваново",
    "Суздаль",
    "Владимир",
    "Нижний Новгород",
    "Чебоксары",
    "Казань",
    "Кашира",
    "Михайлов",
    "Мичуринск",
    "Тамбов",
    "Котовск",
    "Борисоглебск",
    "Волгоград",
    "Серпухов",
    "Тула",
]
REQUIRED_SIGHTS = ("Троице-Сергиева лавра", "Ростовский кремль", "Ипатьевский монастырь", "Золотые ворота")


@cache
def central() -> FakeWorld:
    return FakeWorld.load(WORLDS / "central_russia_v1.json")


@cache
def edge() -> FakeWorld:
    return FakeWorld.load(WORLDS / "edge_cases_v1.json")


def town(w: FakeWorld, name: str) -> LatLon:
    return next(t.point for t in w.towns.values() if t.name_ru == name)


class WorldsTest(unittest.TestCase):
    def test_both_worlds_load(self) -> None:
        self.assertEqual(central().id, "central_russia_v1")
        self.assertEqual(edge().id, "edge_cases_v1")
        for w in (central(), edge()):
            self.assertEqual(w.as_of.isoformat(), "2026-10-01")

    def test_edges_not_shorter_than_straight_line(self) -> None:
        for w in (central(), edge()):
            for e in w.edges:
                with self.subTest(world=w.id, edge=f"{e.a}-{e.b}"):
                    self.assertGreaterEqual(e.km, 0.95 * haversine_km(e.pa, e.pb))
                    self.assertTrue(60 <= e.speed_kmh <= 110)

    def test_central_minimum_counts(self) -> None:
        w = central()
        self.assertGreaterEqual(len(w.towns), 30)
        self.assertGreaterEqual(len(w.places), 150)
        names = {t.name_ru for t in w.towns.values()}
        for n in REQUIRED_TOWNS:
            self.assertIn(n, names)
        self.assertEqual(set(REQUIRED_REGIONS) - set(w.regions), set())
        for code in REQUIRED_REGIONS:
            for ft in ("ai92", "ai95", "dt"):
                with self.subTest(region=code, fuel=ft):
                    self.assertTrue(
                        any(p.region_code == code and p.fuel_type.value == ft for p in w.region_prices)
                    )
        sights = [p for p in w.places.values() if p.type is PlaceType.SIGHT]
        self.assertGreaterEqual(len(sights), 25)
        self.assertGreaterEqual(sum(1 for s in sights if s.opening_hours), 20)
        for n in REQUIRED_SIGHTS:
            self.assertIn(n, {s.name_ru for s in sights})
        food = [p for p in w.places.values() if p.type is PlaceType.FOOD]
        self.assertGreaterEqual(len(food), 15)
        self.assertTrue(any(Tag.KIDS_MENU in f.tags for f in food))
        fuel = [p for p in w.places.values() if p.type is PlaceType.FUEL]
        self.assertTrue(any(Tag.CAFE_AT_FUEL in f.tags for f in fuel))
        self.assertTrue(any(Tag.H24 in f.tags for f in fuel))
        yp = next(s for s in sights if s.name_ru == "Ясная Поляна")
        self.assertEqual(yp.opening_hours, "Tu-Su 09:00-17:00")
        self.assertEqual(set(w.ready_routes), {"rr_golden_ring", "rr_yaroslavl", "rr_tula_yasnaya"})
        gr = w.ready_routes["rr_golden_ring"]
        self.assertEqual((gr.km_sign, gr.suggested_nights), (745, ("t_yaroslavl", "t_suzdal")))
        self.assertEqual(w.ready_routes["rr_tula_yasnaya"].suggested_nights, ("t_tula",))
        for p in w.places.values():
            for v in (p.price_night_rub,):
                if v is not None:
                    self.assertTrue(2000 <= v <= 8000, p.id)
            if p.avg_check_rub is not None:
                self.assertTrue(500 <= p.avg_check_rub <= 1000, p.id)
            if p.ticket_adult_rub is not None:
                self.assertTrue(0 <= p.ticket_adult_rub <= 600, p.id)
        for rp in w.region_prices:
            if rp.fuel_type.value == "ai95":
                self.assertTrue(58 <= rp.price_rub <= 64)

    def test_lodging_rules_for_golden_trips(self) -> None:
        w = central()

        def lodgings(tid: str) -> list[frozenset[Tag]]:
            return [p.tags for p in w.places.values() if p.type is PlaceType.LODGING and p.town_id == tid]

        for tid in ("t_yaroslavl", "t_suzdal", "t_tambov", "t_nizhny", "t_tula", "t_rostov"):
            self.assertGreaterEqual(len(lodgings(tid)), 2, tid)
        for tid in ("t_yaroslavl", "t_tambov"):
            self.assertGreaterEqual(sum(Tag.DOGS_ALLOWED in t for t in lodgings(tid)), 2, tid)
        self.assertTrue(any({Tag.DOGS_ALLOWED, Tag.FAMILY_ROOM} <= t for t in lodgings("t_suzdal")))
        kot = lodgings("t_kotovsk")
        self.assertEqual(len(kot), 3)
        self.assertFalse(any(Tag.DOGS_ALLOWED in t for t in kot))

    def test_real_distances(self) -> None:
        w = central()
        r = FakeRouting(w)

        def km(a: str, b: str, avoid: bool = False) -> float:
            return r.route(RouteRequest((town(w, a), town(w, b)), avoid)).km_total

        self.assertTrue(255 <= km("Москва", "Ярославль") <= 275)
        m7 = r.route(RouteRequest((town(w, "Москва"), town(w, "Казань")), True))
        self.assertTrue(790 <= m7.km_total <= 840)
        self.assertEqual({d.road_ref for d in m7.details if d.road_ref}, {"М-7"})
        m12 = r.route(RouteRequest((town(w, "Москва"), town(w, "Казань")), False))
        self.assertEqual({d.road_ref for d in m12.details if d.road_ref}, {"М-12"})
        self.assertTrue(940 <= km("Москва", "Волгоград") <= 1010)
        self.assertTrue(175 <= km("Москва", "Тула") <= 195)
        # Golden Ring loop through all eight towns = 745 km (the sign value)
        ring = [
            "Москва",
            "Сергиев Посад",
            "Переславль-Залесский",
            "Ростов",
            "Ярославль",
            "Кострома",
            "Иваново",
            "Суздаль",
            "Владимир",
            "Москва",
        ]
        loop = r.route(RouteRequest(tuple(town(w, n) for n in ring), False)).km_total
        self.assertAlmostEqual(loop, 745, delta=1)

    def test_town_coordinates_are_real(self) -> None:
        w = central()
        real = {
            "Ярославль": (57.6261, 39.8845),
            "Тамбов": (52.7212, 41.4523),
            "Тула": (54.1931, 37.6173),
            "Суздаль": (56.4197, 40.4434),
            "Казань": (55.7963, 49.1088),
            "Волгоград": (48.7080, 44.5133),
        }
        for name, (lat, lon) in real.items():
            p = town(w, name)
            self.assertAlmostEqual(p.lat, lat, delta=0.01)
            self.assertAlmostEqual(p.lon, lon, delta=0.01)

    def test_edge_world_shapes(self) -> None:
        w = edge()
        self.assertEqual({r for r in w.regions}, {"RU", "RU-TST"})
        r = FakeRouting(w)
        # G05: Тестовск → Конечный ≈ 600 km, the only lodging is not dog-friendly
        g05 = r.route(RouteRequest((town(w, "Тестовск"), town(w, "Конечный")), False))
        self.assertAlmostEqual(g05.km_total, 600, delta=5)
        lodgings = [p for p in w.places.values() if p.type is PlaceType.LODGING]
        self.assertEqual([p.id for p in lodgings], ["pl_tst_hotel_nodog"])
        self.assertNotIn(Tag.DOGS_ALLOWED, lodgings[0].tags)
        # G09: the off-road node is 2.5 km from any edge
        off = town(w, "Глухово")
        self.assertAlmostEqual(min(point_segment_km(off, e.pa, e.pb) for e in w.edges), 2.5, delta=0.05)
        with self.assertRaises(Unreachable):
            r.route(RouteRequest((town(w, "Тестовск"), off), False))
        # G10: two nodes 12 km apart
        g10 = r.route(RouteRequest((town(w, "Тестовск"), town(w, "Ближний")), False))
        self.assertAlmostEqual(g10.km_total, 12, delta=0.5)
        # G11: ≥ 300 km without fuel on the north corridor
        g11 = r.route(RouteRequest((town(w, "Тестовск"), town(w, "Пустошь")), False))
        self.assertAlmostEqual(g11.km_total, 450, delta=5)
        north_fuel_km = sorted(
            (p.point.lat - 58.0) * 110.574
            for p in w.places.values()
            if p.type is PlaceType.FUEL and abs(p.point.lon - 50.0) < 0.01 and p.point.lat > 58.0
        )
        gaps = [b - a for a, b in itertools.pairwise(north_fuel_km)]
        self.assertGreaterEqual(max(gaps), 300)
        # G12: fixed long-dwell sights
        rr = w.ready_routes["rr_tst_marathon"]
        dwell = [w.places[p.place_id].dwell_min for p in rr.points if p.place_id]
        self.assertEqual(dwell, [240, 240])

    def test_generator_matches_committed_json(self) -> None:
        """A§16.10: `tools/gen_worlds.py` reproduces both committed worlds byte for byte."""
        from tests.contract.test_cost_recompute_contract import generated

        out = generated("gen_worlds.py")["GENERATED"]
        self.assertEqual(sorted(out), ["central_russia_v1", "edge_cases_v1"])
        for name, text in out.items():
            with self.subTest(world=name):
                self.assertEqual(text, (WORLDS / f"{name}.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
