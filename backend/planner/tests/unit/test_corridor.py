import unittest
from collections.abc import Sequence

from tests.helpers import line_north, make_ctx, make_place, make_route, make_town, trip
from verst_planner.adapters.fake.world import offset_local
from verst_planner.domain.enums import PlaceType, RoadClass, Tag
from verst_planner.domain.model import LatLon, Place, ReadyRoute, Route, RouteDetail, Town
from verst_planner.pipeline import detour
from verst_planner.pipeline.base_route import build_base_route
from verst_planner.pipeline.corridor import build_corridor, place_fixed
from verst_planner.pipeline.resolve import normalize_input, resolve_points
from verst_planner.ports import CorridorQuery


class StubPlaces:
    """Returns its places/towns regardless of the query (the corridor stage must do the filtering)."""

    def __init__(self, places: list[Place], towns: list[Town]) -> None:
        self.places = places
        self.towns = towns
        self.calls: dict[str, int] = {}

    def _c(self, n: str) -> None:
        self.calls[n] = self.calls.get(n, 0) + 1

    def places_in_corridor(self, q: CorridorQuery) -> list[Place]:
        self._c("places_in_corridor")
        return [p for p in self.places if p.type in q.types]

    def towns_in_corridor(self, line: tuple[LatLon, ...], radius_km: float) -> list[Town]:
        self._c("towns_in_corridor")
        return list(self.towns)

    def lodgings_of_towns(self, town_ids: Sequence[str]) -> dict[str, list[Place]]:
        self._c("lodgings_of_towns")
        return {
            t: [p for p in self.places if p.type is PlaceType.LODGING and p.town_id == t] for t in town_ids
        }

    def get_places(self, ids: Sequence[str]) -> dict[str, Place]:
        return {p.id: p for p in self.places if p.id in ids}

    def get_towns(self, ids: Sequence[str]) -> dict[str, Town]:
        return {t.id: t for t in self.towns if t.id in ids}

    def get_ready_route(self, route_id: str) -> ReadyRoute | None:
        return None

    def ready_routes_near(self, point: LatLon, hub_radius_km: float, limit: int) -> list[ReadyRoute]:
        return []


def two_class_route() -> Route:
    """100 km northbound: km 0-50 motorway, km 50-100 trunk."""
    base = make_route(line_north(56.0, 38.0, 100))
    return Route(
        base.points,
        base.cum_km,
        base.cum_min,
        (
            RouteDetail(0, 50, RoadClass.MOTORWAY, "М-12", False),
            RouteDetail(50, 100, RoadClass.TRUNK, "М-7", False),
        ),
        base.waypoint_idx,
        base.snapped,
        base.km_total,
        base.min_total,
    )


def at(route: Route, km: int, east_km: float) -> LatLon:
    return offset_local(route.points[km], east_km, 0.0)


class CorridorTest(unittest.TestCase):
    def build(self, places: list[Place], towns: list[Town] | None = None) -> tuple[object, StubPlaces]:
        ctx, _ = make_ctx()
        stub = StubPlaces(places, towns or [])
        ctx.ports.places = stub
        inp = normalize_input(trip(), ctx)
        return build_corridor(two_class_route(), inp, ctx), stub

    def test_motorway_fuel_5km(self) -> None:
        r = two_class_route()
        places = [
            make_place("f_mw_8", PlaceType.FUEL, *_ll(at(r, 25, 8.0))),
            make_place("f_mw_4", PlaceType.FUEL, *_ll(at(r, 30, 4.0))),
            make_place("f_tr_8", PlaceType.FUEL, *_ll(at(r, 75, 8.0))),
            make_place("r_mw_8", PlaceType.REST, *_ll(at(r, 20, -8.0))),
            make_place("s_mw_8", PlaceType.SIGHT, *_ll(at(r, 20, 8.0))),
        ]
        corridor, _ = self.build(places)
        self.assertEqual([c.place.id for c in corridor.fuel], ["f_mw_4", "f_tr_8"])
        self.assertEqual(corridor.rest, [])
        self.assertEqual([c.place.id for c in corridor.sights], ["s_mw_8"])  # 5 km rule is fuel/rest only
        self.assertEqual(corridor.fuel[1].road_class, RoadClass.TRUNK)
        self.assertAlmostEqual(corridor.fuel[1].km_at, 75, delta=0.3)

    def test_town_corridor_25km(self) -> None:
        r = two_class_route()
        near = make_town("t_near", *_ll(at(r, 60, 24.0)))
        far = make_town("t_far", *_ll(at(r, 60, 26.0)))
        hotel = make_place(
            "h1", PlaceType.LODGING, *_ll(at(r, 60, 23.0)), town_id="t_near", price_night_rub=4000
        )
        stray = make_place("h2", PlaceType.LODGING, *_ll(at(r, 62, 24.5)), price_night_rub=3000)
        corridor, _ = self.build([hotel, stray], [near, far])
        self.assertEqual([t.town.id for t in corridor.towns], ["t_near"])
        # own lodging by town_id, plus the stray one within 10 km of the centre
        self.assertEqual([c.place.id for c in corridor.towns[0].lodgings], ["h1", "h2"])
        self.assertEqual({c.place.id for c in corridor.lodgings}, {"h1", "h2"})

    def test_detour_formula(self) -> None:
        ctx, _ = make_ctx()
        km, minutes = detour(3.0, RoadClass.TRUNK, ctx.cfg)
        self.assertAlmostEqual(km, 7.8)
        self.assertEqual(minutes, 14)  # round(7.8 / 40 · 60) + 2
        self.assertEqual(detour(3.0, RoadClass.MOTORWAY, ctx.cfg)[1], 19)  # + 5 min motorway exit
        self.assertEqual(detour(0.29, RoadClass.TRUNK, ctx.cfg)[1], 0)  # on the road
        self.assertEqual(detour(0.3, RoadClass.TRUNK, ctx.cfg)[1], 3)  # 0.78 km → 1 min + 2

    def test_unparseable_hours_dropped(self) -> None:
        r = two_class_route()
        ok = make_place("s_ok", PlaceType.SIGHT, *_ll(at(r, 70, 1.0)), opening_hours="Mo-Su 10:00-18:00")
        bad = make_place("s_bad", PlaceType.SIGHT, *_ll(at(r, 72, 1.0)), opening_hours="sunrise-sunset")
        with self.assertLogs("verst_planner", level="WARNING") as logs:
            corridor, _ = self.build([ok, bad])
        self.assertEqual([c.place.id for c in corridor.sights], ["s_ok"])
        self.assertIn("hours_parse_error place=s_bad", logs.output[0])

    def test_round_trip_two_candidates(self) -> None:
        ctx, _ = make_ctx()
        inp = normalize_input(trip(round_trip=True), ctx)
        route = build_base_route(resolve_points(inp, ctx), inp, ctx)
        corridor = build_corridor(route, inp, ctx)
        lavra = [c for c in corridor.sights if c.place.id == "pl_sps_lavra"]
        self.assertEqual(len(lavra), 2)
        self.assertAlmostEqual(lavra[0].km_at, 72, delta=1)
        self.assertAlmostEqual(lavra[1].km_at, 526 - 72, delta=1)
        self.assertEqual(sum(1 for t in corridor.towns if t.town.id == "t_yaroslavl"), 1)

    def test_corridor_calls_ports_once(self) -> None:
        ctx, fakes = make_ctx()
        inp = normalize_input(trip(), ctx)
        route = build_base_route(resolve_points(inp, ctx), inp, ctx)
        corridor = build_corridor(route, inp, ctx)
        calls = fakes.places.calls
        self.assertEqual(calls.get("places_in_corridor"), 2)
        self.assertEqual(calls.get("towns_in_corridor"), 1)
        self.assertEqual(calls.get("lodgings_of_towns"), 1)
        self.assertTrue(corridor.fuel and corridor.rest and corridor.sights and corridor.food)
        yar = next(t for t in corridor.towns if t.town.id == "t_yaroslavl")
        self.assertAlmostEqual(yar.km_at, 263, delta=0.5)
        self.assertGreaterEqual(len(yar.lodgings), 4)
        for lst in (corridor.fuel, corridor.sights, corridor.towns):
            kms = [c.km_at for c in lst]
            self.assertEqual(kms, sorted(kms))
        self.assertGreaterEqual(sum(Tag.DOGS_ALLOWED in c.place.tags for c in yar.lodgings), 2)

    def test_place_fixed_golden_ring(self) -> None:
        ctx, _ = make_ctx()
        inp = normalize_input(trip(destination=None, ready_route_id="rr_golden_ring"), ctx)
        pts = resolve_points(inp, ctx)
        route = build_base_route(pts, inp, ctx)
        corridor = build_corridor(route, inp, ctx)
        fixed = place_fixed(pts, corridor, inp, ctx)
        names = [(s.kind.value, s.name_ru, round(s.km_at)) for s in fixed]
        # ready-route vias are routing waypoints only (A§16.3): just the lavra and the Ipatiev monastery
        self.assertEqual([k for k, _n, _km in names], ["sight", "sight"])
        lavra = next(s for s in fixed if s.place and s.place.id == "pl_sps_lavra")
        self.assertAlmostEqual(lavra.km_at, 72, delta=1.5)
        ipatiev = next(s for s in fixed if s.place and s.place.id == "pl_kos_ipatiev")
        self.assertTrue(263 < ipatiev.km_at <= 343)
        self.assertLess(ipatiev.detour_km, 2.0)  # on the Yaroslavl road, west of Kostroma


def _ll(p: LatLon) -> tuple[float, float]:
    return p.lat, p.lon


if __name__ == "__main__":
    unittest.main()
