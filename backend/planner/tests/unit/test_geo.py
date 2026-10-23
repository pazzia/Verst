import itertools
import math
import random
import unittest

from tests.helpers import line_north, make_route
from verst_planner.domain.enums import RoadClass
from verst_planner.domain.model import LatLon, Route, RouteDetail
from verst_planner.geo.bearing import bearing8, initial_bearing_deg
from verst_planner.geo.distance import haversine_km, point_segment_km
from verst_planner.geo.index import PolylineIndex
from verst_planner.geo.polyline import douglas_peucker, interpolate, resample

MOSCOW = LatLon(55.7558, 37.6173)
YAROSLAVL = LatLon(57.6261, 39.8845)
TULA = LatLon(54.1931, 37.6173)
TVER = LatLon(56.8587, 35.9176)
VLADIMIR = LatLon(56.1290, 40.4066)


def east_of(p: LatLon, km: float) -> LatLon:
    return LatLon(p.lat, p.lon + km / (111.195 * math.cos(math.radians(p.lat))))


class DistanceTest(unittest.TestCase):
    def test_haversine_moscow_yaroslavl(self) -> None:
        self.assertAlmostEqual(haversine_km(MOSCOW, YAROSLAVL), 249.8, delta=0.5)

    def test_haversine_symmetric_zero(self) -> None:
        self.assertEqual(haversine_km(MOSCOW, MOSCOW), 0.0)
        self.assertAlmostEqual(haversine_km(MOSCOW, TULA), haversine_km(TULA, MOSCOW), places=9)

    def test_point_segment(self) -> None:
        a, b = LatLon(56.0, 38.0), LatLon(56.5, 38.0)
        mid = LatLon(56.25, 38.0)
        self.assertAlmostEqual(point_segment_km(east_of(mid, 2.0), a, b), 2.0, delta=0.01)
        # beyond the end: distance to the endpoint
        beyond = LatLon(56.5 + 1 / 111.195, 38.0)
        self.assertAlmostEqual(point_segment_km(beyond, a, b), 1.0, delta=0.01)
        # degenerate segment = distance to the point (equirectangular vs sphere differ by < 1 %)
        self.assertAlmostEqual(point_segment_km(beyond, a, a), haversine_km(beyond, a), delta=0.01 * 56.6)


class PolylineTest(unittest.TestCase):
    def test_dp_keeps_endpoints_and_corners(self) -> None:
        leg1 = line_north(56.0, 38.0, 50)
        corner = leg1[-1]
        leg2 = [east_of(corner, k) for k in range(1, 51)]
        pts = leg1 + leg2
        cum = [float(i) for i in range(len(pts))]
        kept = douglas_peucker(pts, cum, 30.0)
        self.assertEqual(kept, [0, 50, len(pts) - 1])
        # a 100 m bump survives at 30 m tolerance, a 10 m one does not
        bumped = list(leg1)
        bumped[25] = east_of(bumped[25], 0.1)
        self.assertIn(25, douglas_peucker(bumped, [float(i) for i in range(len(bumped))], 30.0))
        bumped[25] = east_of(leg1[25], 0.01)
        self.assertEqual(douglas_peucker(bumped, [float(i) for i in range(len(bumped))], 30.0), [0, 50])

    def test_dp_small_inputs(self) -> None:
        self.assertEqual(douglas_peucker([MOSCOW], [0.0], 30), [0])
        self.assertEqual(douglas_peucker([MOSCOW, TULA], [0.0, 1.0], 30), [0, 1])
        with self.assertRaises(ValueError):
            douglas_peucker([MOSCOW, TULA], [0.0], 30)

    def test_interpolate_and_resample(self) -> None:
        route = make_route(line_north(56.0, 38.0, 10), speed_kmh=60)
        p = interpolate(route, 5.0)
        self.assertAlmostEqual(haversine_km(p, route.points[0]), 5.0, delta=0.001)
        self.assertEqual(interpolate(route, -3.0), route.points[0])
        self.assertEqual(interpolate(route, 99.0), route.points[-1])
        km, mins = resample(route, 1.0)
        self.assertEqual(len(km), len(mins))
        self.assertEqual(km[0], 0.0)
        self.assertAlmostEqual(km[-1], route.km_total)
        self.assertAlmostEqual(mins[3], 3.0, delta=0.01)
        self.assertTrue(all(b > a for a, b in itertools.pairwise(km)))
        with self.assertRaises(ValueError):
            resample(route, 0)


class IndexTest(unittest.TestCase):
    def test_project_on_straight_line(self) -> None:
        route = make_route(line_north(56.0, 38.0, 100))
        idx = PolylineIndex(route)
        mid = interpolate(route, 50.0)
        res = idx.project_all(east_of(mid, 3.0), 15.0)
        self.assertEqual(len(res), 1)
        self.assertAlmostEqual(res[0].km_at, 50.0, delta=0.2)
        self.assertAlmostEqual(res[0].lateral_km, 3.0, delta=0.05)
        self.assertEqual(res[0].road_class, RoadClass.TRUNK)

    def test_project_beyond_radius(self) -> None:
        route = make_route(line_north(56.0, 38.0, 100))
        idx = PolylineIndex(route)
        self.assertEqual(idx.project_all(east_of(interpolate(route, 50.0), 16.0), 15.0), [])
        self.assertIsNone(idx.nearest(east_of(interpolate(route, 50.0), 16.0), 15.0))

    def test_round_trip_two_passes(self) -> None:
        out = line_north(56.0, 38.0, 100)
        pts = out + list(reversed(out[:-1]))
        cum = [float(i) for i in range(len(pts))]
        route = make_route(pts, cum_km=cum)
        idx = PolylineIndex(route)
        res = idx.project_all(east_of(out[30], 1.0), 15.0)
        self.assertEqual(len(res), 2)
        self.assertAlmostEqual(res[0].km_at, 30.0, delta=0.5)
        self.assertAlmostEqual(res[1].km_at, 170.0, delta=0.5)
        for r in res:
            self.assertAlmostEqual(r.lateral_km, 1.0, delta=0.05)

    def test_nearest_in_range_splits_close_passes(self) -> None:
        # out 0→20 km and back: the two passes 10 km apart merge in project_all at 15 km radius
        out = line_north(56.0, 38.0, 20)
        pts = out + list(reversed(out[:-1]))
        route = make_route(pts, cum_km=[float(i) for i in range(len(pts))])
        idx = PolylineIndex(route)
        p = east_of(out[15], 1.0)
        self.assertEqual(len(idx.project_all(p, 15.0)), 1)
        back = idx.nearest_in_range(p, 15.0, 20.0, 40.0)
        there = idx.nearest_in_range(p, 15.0, 0.0, 20.0)
        assert back is not None and there is not None
        self.assertAlmostEqual(there.km_at, 15.0, delta=0.3)
        self.assertAlmostEqual(back.km_at, 25.0, delta=0.3)
        self.assertIsNone(idx.nearest_in_range(p, 15.0, 41.0, 50.0))

    def test_road_class_by_detail(self) -> None:
        pts = line_north(56.0, 38.0, 20)
        base = make_route(pts)
        route = Route(
            points=base.points,
            cum_km=base.cum_km,
            cum_min=base.cum_min,
            details=(
                RouteDetail(0, 10, RoadClass.MOTORWAY, "М-12", True),
                RouteDetail(10, 20, RoadClass.PRIMARY, "Р-132", False),
            ),
            waypoint_idx=base.waypoint_idx,
            snapped=base.snapped,
            km_total=base.km_total,
            min_total=base.min_total,
        )
        idx = PolylineIndex(route)
        self.assertEqual(idx.project_all(east_of(pts[4], 1.0), 5)[0].road_class, RoadClass.MOTORWAY)
        self.assertEqual(idx.project_all(east_of(pts[15], 1.0), 5)[0].road_class, RoadClass.PRIMARY)
        self.assertEqual(idx.road_ref_at(15), "Р-132")

    def test_index_matches_bruteforce(self) -> None:
        rng = random.Random(42)
        pts = [LatLon(55.0 + i * 0.01, 37.0 + (0.03 if i % 2 else 0.0)) for i in range(300)]
        route = make_route(pts)
        idx = PolylineIndex(route)
        self.assertEqual(len(idx.kept), 300)  # every zig-zag corner is kept
        for _ in range(500):
            p = LatLon(rng.uniform(54.95, 58.05), rng.uniform(36.85, 37.18))
            best = idx.nearest(p, 15.0)
            brute = min(
                (idx.project_segment(p, s) for s in range(idx.segment_count)),
                key=lambda kd: (kd[1], kd[0]),
            )
            if brute[1] > 15.0:
                self.assertIsNone(best)
                continue
            assert best is not None
            self.assertAlmostEqual(best.lateral_km, brute[1], delta=1e-6)


class BearingTest(unittest.TestCase):
    def test_bearing8(self) -> None:
        self.assertEqual(bearing8(MOSCOW, YAROSLAVL), "NE")
        self.assertEqual(bearing8(MOSCOW, TULA), "S")
        self.assertEqual(bearing8(MOSCOW, TVER), "NW")
        self.assertEqual(bearing8(MOSCOW, VLADIMIR), "E")
        self.assertAlmostEqual(initial_bearing_deg(MOSCOW, YAROSLAVL), 33, delta=3)
        self.assertAlmostEqual(initial_bearing_deg(MOSCOW, VLADIMIR), 75, delta=3)
        self.assertAlmostEqual(initial_bearing_deg(MOSCOW, TVER), 320, delta=3)
        self.assertAlmostEqual(initial_bearing_deg(MOSCOW, TULA), 180, delta=0.01)

    def test_sector_edges(self) -> None:
        a = LatLon(0.0, 0.0)
        self.assertEqual(bearing8(a, LatLon(1.0, 0.0)), "N")
        self.assertEqual(bearing8(a, LatLon(0.0, 1.0)), "E")
        self.assertEqual(bearing8(a, LatLon(0.0, -1.0)), "W")
        self.assertEqual(bearing8(a, LatLon(-1.0, -1.0)), "SW")


if __name__ == "__main__":
    unittest.main()
