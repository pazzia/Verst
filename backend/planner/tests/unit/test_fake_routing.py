import itertools
import unittest

from tests.helpers import UNIT_DATA
from verst_planner.adapters.fake import FakeRouting, FakeWorld
from verst_planner.adapters.fake.world import offset_local
from verst_planner.domain.enums import RoadClass
from verst_planner.domain.errors import Unreachable, UpstreamUnavailable
from verst_planner.domain.model import LatLon, RouteRequest
from verst_planner.ports import RoutingPort


class FakeRoutingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.w = FakeWorld.load(UNIT_DATA / "mini_world.json")
        self.r: RoutingPort = FakeRouting(self.w)
        self.n = {k: v.point for k, v in self.w.nodes.items()}

    def req(self, *names: str, avoid: bool = False) -> RouteRequest:
        return RouteRequest(tuple(self.n[x] for x in names), avoid)

    def test_route_km_equals_edge_sum(self) -> None:
        route = self.r.route(self.req("N0", "N3"))
        self.assertAlmostEqual(route.km_total, 52 + 52, places=6)  # motorway is faster
        self.assertAlmostEqual(route.min_total, 104 / 110 * 60, places=6)
        route = self.r.route(self.req("N0", "N5"))
        self.assertAlmostEqual(route.km_total, 52 + 52 + 32 + 32, places=6)
        self.assertEqual(route.waypoint_idx[0], 0)
        self.assertEqual(route.waypoint_idx[-1], len(route.points) - 1)
        self.assertEqual(route.cum_km[0], 0.0)

    def test_route_cum_monotonic(self) -> None:
        route = self.r.route(self.req("N0", "N6", "N0"))
        self.assertEqual(len(route.points), len(route.cum_km))
        self.assertEqual(len(route.points), len(route.cum_min))
        for a, b in itertools.pairwise(route.cum_km):
            self.assertGreater(b, a)
        for a, b in itertools.pairwise(route.cum_min):
            self.assertGreater(b, a)
        self.assertEqual(route.details[0].from_idx, 0)
        self.assertEqual(route.details[-1].to_idx, len(route.points) - 1)
        for d1, d2 in itertools.pairwise(route.details):
            self.assertEqual(d1.to_idx, d2.from_idx)
        self.assertEqual(len(route.waypoint_idx), 3)
        # each polyline step is about 1 km
        steps = [b - a for a, b in itertools.pairwise(route.cum_km)]
        self.assertLess(max(steps), 1.6)

    def test_avoid_tolls_takes_free_edge(self) -> None:
        free = self.r.route(self.req("N0", "N3", avoid=True))
        self.assertAlmostEqual(free.km_total, 24 + 30 + 53, places=6)
        self.assertFalse(any(d.toll for d in free.details))
        self.assertEqual({d.road_ref for d in free.details}, {"М-8"})
        paid = self.r.route(self.req("N0", "N3"))
        self.assertTrue(any(d.toll for d in paid.details))
        self.assertEqual(paid.details[0].road_class, RoadClass.MOTORWAY)

    def test_details_merged(self) -> None:
        free = self.r.route(self.req("N0", "N3", avoid=True))
        self.assertEqual(len(free.details), 1)  # three equal М-8 trunk edges merge

    def test_snap_to_edge_virtual_split(self) -> None:
        mid = offset_local(self.n["N1"], 0.3, 13.0)  # 13 km north of N1 on N1-N2, 0.3 km east
        route = self.r.route(RouteRequest((self.n["N0"], mid), False))
        self.assertAlmostEqual(route.km_total, 24 + 30 * (13.0 / 27.8), delta=0.3)
        self.assertLess(abs(route.snapped[1].lon - 38.0), 1e-9)

    def test_snap_over_2km_unreachable(self) -> None:
        off = offset_local(self.n["N1"], 3.0, 0.0)
        with self.assertRaises(Unreachable) as cm:
            self.r.route(RouteRequest((self.n["N0"], off), False))
        self.assertEqual(cm.exception.point_index, 1)
        self.assertIsNotNone(cm.exception.snap_km)

    def test_upstream_failure_injection(self) -> None:
        r = FakeRouting(self.w, fail_with=UpstreamUnavailable("graphhopper"))
        with self.assertRaises(UpstreamUnavailable) as cm:
            r.route(self.req("N0", "N3"))
        self.assertEqual(cm.exception.service, "graphhopper")
        self.assertEqual(r.calls, 1)

    def test_deterministic(self) -> None:
        a = self.r.route(self.req("N0", "N6", "N0"))
        b = FakeRouting(self.w).route(self.req("N0", "N6", "N0"))
        self.assertEqual(a, b)

    def test_same_point_twice(self) -> None:
        route = self.r.route(self.req("N0", "N0"))
        self.assertEqual(route.km_total, 0.0)
        p = LatLon(56.0, 38.0)
        self.assertEqual(route.snapped, (p, p))


if __name__ == "__main__":
    unittest.main()
