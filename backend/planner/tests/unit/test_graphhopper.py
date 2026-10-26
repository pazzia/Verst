"""ENG-01 / ADR-0017: `GraphHopperRouting` on responses recorded from a real GraphHopper 11.0 server.

The fixtures in `tests/data/graphhopper/` were recorded by `infra/routing/dev/record_fixtures.sh` from
GraphHopper 11.0 running on a synthetic mini map (`infra/routing/dev/make_mini_osm.py`): the server and the
response schema are real, the roads are made up. The CI workflow `.github/workflows/routing.yml` records the
same request shapes on the real Central + Volga extract (artifact `routing-recordings`).
"""

from __future__ import annotations

import http.server
import json
import logging
import socket
import threading
import time
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, ClassVar

from tests.test_layering import PKG, allowed, imports, module_name
from verst_planner.adapters.graphhopper import (
    DETAILS,
    GraphHopperRouting,
    GraphHopperSettings,
    TransportError,
    UrllibTransport,
    normalize_ref,
    request_body,
    to_route,
)
from verst_planner.adapters.graphhopper.mapping import MappingError
from verst_planner.domain.enums import RoadClass
from verst_planner.domain.errors import Unreachable, UpstreamUnavailable
from verst_planner.domain.model import LatLon, Route, RouteRequest
from verst_planner.geo.distance import haversine_km

DATA = Path(__file__).resolve().parent.parent / "data" / "graphhopper"
W, E, S = LatLon(56.0, 37.0), LatLon(56.0, 37.3), LatLon(55.95, 37.15)
ISLAND = LatLon(56.0501, 37.145)
LOGGER = "verst_planner.adapters.graphhopper"


def fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((DATA / f"{name}.json").read_text("utf-8"))
    return data


def points_of(body: dict[str, Any]) -> tuple[tuple[float, float], ...]:
    return tuple((float(lon), float(lat)) for lon, lat in body["points"])


class FixtureTransport:
    """Answers with the recorded fixture whose request equals the adapter's request, byte for byte as JSON."""

    def __init__(self, *names: str) -> None:
        self.fixtures = [fixture(n) for n in names]
        self.sent: list[dict[str, Any]] = []

    def post_json(self, url: str, body: bytes, deadline: float) -> tuple[int, bytes]:
        assert url == "http://gh.test:8989/route", url
        assert deadline > time.monotonic()
        req = json.loads(body)
        self.sent.append(req)
        for f in self.fixtures:
            if f["request"] == req:
                return int(f["status"]), json.dumps(f["body"], ensure_ascii=False).encode("utf-8")
        raise AssertionError(f"no fixture for {req}")


class ScriptedTransport:
    def __init__(self, *steps: tuple[int, bytes] | TransportError) -> None:
        self.steps = list(steps)
        self.calls = 0

    def post_json(self, url: str, body: bytes, deadline: float) -> tuple[int, bytes]:
        self.calls += 1
        step = self.steps.pop(0)
        if isinstance(step, TransportError):
            raise step
        return step


def router(transport: Any, **kw: Any) -> GraphHopperRouting:
    return GraphHopperRouting(GraphHopperSettings("http://gh.test:8989", **kw), transport)


def route_with(names: tuple[str, ...], *points: LatLon, avoid: bool = False) -> Route:
    return router(FixtureTransport(*names)).route(RouteRequest(points, avoid))


def ok_body(name: str = "route_toll") -> tuple[int, bytes]:
    return 200, json.dumps(fixture(name)["body"]).encode()


class RouteInvariants(unittest.TestCase):
    def assert_route(self, r: Route, n_waypoints: int) -> None:
        n = len(r.points)
        self.assertEqual((len(r.cum_km), len(r.cum_min)), (n, n))
        self.assertEqual((r.cum_km[0], r.cum_min[0]), (0.0, 0.0))
        self.assertTrue(all(b >= a for a, b in zip(r.cum_km, r.cum_km[1:], strict=False)))
        self.assertTrue(all(b >= a for a, b in zip(r.cum_min, r.cum_min[1:], strict=False)))
        self.assertTrue(all(b - a <= 1.0 + 1e-9 for a, b in zip(r.cum_km, r.cum_km[1:], strict=False)))
        self.assertEqual((r.km_total, r.min_total), (r.cum_km[-1], r.cum_min[-1]))
        self.assertEqual(r.details[0].from_idx, 0)
        self.assertEqual(r.details[-1].to_idx, n - 1)
        for a, b in zip(r.details, r.details[1:], strict=False):
            self.assertEqual(a.to_idx, b.from_idx)
            self.assertNotEqual((a.road_class, a.road_ref, a.toll), (b.road_class, b.road_ref, b.toll))
        self.assertEqual(len(r.waypoint_idx), n_waypoints)
        self.assertEqual((r.waypoint_idx[0], r.waypoint_idx[-1]), (0, n - 1))
        self.assertEqual(len(r.snapped), n_waypoints)
        self.assertFalse(r.synthetic)


class MappingTest(RouteInvariants):
    def test_toll_route_on_motorway(self) -> None:
        r = route_with(("route_toll",), W, E)
        self.assert_route(r, 2)
        body = fixture("route_toll")["body"]["paths"][0]
        self.assertAlmostEqual(r.km_total, body["distance"] / 1000, places=9)
        self.assertAlmostEqual(r.min_total, body["time"] / 60000, places=9)
        self.assertEqual(
            [(d.road_class, d.road_ref, d.toll) for d in r.details],
            [
                (RoadClass.OTHER, None, False),  # residential
                (RoadClass.MOTORWAY, None, False),  # motorway_link (class motorway, no ref, no toll)
                (RoadClass.MOTORWAY, "М-11", True),
                (RoadClass.MOTORWAY, None, False),
                (RoadClass.OTHER, None, False),  # tertiary
            ],
        )
        toll = r.details[2]
        self.assertAlmostEqual(r.cum_km[toll.to_idx] - r.cum_km[toll.from_idx], 16.162455, places=6)
        # GraphHopper sends the 16.2 km motorway as one segment; it is densified to 17 segments of <= 1 km
        self.assertEqual(toll.to_idx - toll.from_idx, 17)
        self.assertEqual(len(fixture("route_toll")["body"]["paths"][0]["points"]["coordinates"]), 6)

    def test_avoid_tolls_profile_and_ref_normalisation(self) -> None:
        r = route_with(("route_avoid_tolls",), W, E, avoid=True)
        self.assert_route(r, 2)
        self.assertFalse(any(d.toll for d in r.details))
        # "М-10, Е105" (two refs) and "M-10" (Latin M) are the same road: one detail
        self.assertEqual(
            [(d.road_class, d.road_ref) for d in r.details],
            [
                (RoadClass.OTHER, None),
                (RoadClass.SECONDARY, "46К-1150"),
                (RoadClass.TRUNK, "М-10"),
                (RoadClass.SECONDARY, None),
                (RoadClass.OTHER, None),
            ],
        )
        self.assertGreater(r.min_total, route_with(("route_toll",), W, E).min_total)

    def test_via_point_index_from_leg_distance(self) -> None:
        r = route_with(("route_via",), W, S, E)
        self.assert_route(r, 3)
        mid = r.waypoint_idx[1]
        self.assertEqual(r.points[mid], S)
        legs = fixture("route_via")["body"]["paths"][0]["details"]["leg_distance"]
        self.assertAlmostEqual(r.cum_km[mid], legs[0][2] / 1000, places=6)
        self.assertEqual(r.snapped, (W, S, E))

    def test_without_details_falls_back_to_totals(self) -> None:
        body = fixture("route_via")["body"]
        path = body["paths"][0]
        path["details"] = {}
        r = to_route(body, 3)
        self.assert_route(r, 3)
        self.assertAlmostEqual(r.km_total, path["distance"] / 1000, places=9)
        self.assertAlmostEqual(r.min_total, path["time"] / 60000, places=9)
        self.assertEqual(r.points[r.waypoint_idx[1]], S)  # nearest point after the start
        only = [(d.road_class, d.road_ref, d.toll) for d in r.details]
        self.assertEqual(only, [(RoadClass.OTHER, None, False)])

    def test_malformed_details_are_ignored_not_trusted(self) -> None:
        body = fixture("route_toll")["body"]
        details = body["paths"][0]["details"]
        details["distance"] = [[0, 2, 100.0]]  # does not cover the route
        details["time"] = [[0, 1, "fast"], [1, 5, 1]]  # not a number
        details["leg_distance"] = [[0, 9, 1.0]]  # beyond the last point
        details["road_class"] = "motorway"
        r = to_route(body, 2)
        self.assert_route(r, 2)
        self.assertAlmostEqual(r.km_total, body["paths"][0]["distance"] / 1000, places=9)

    def test_detail_values_that_are_not_numbers_fall_back_to_totals(self) -> None:
        for bad in (None, "7", True, -1.0, float("inf")):
            body = fixture("route_toll")["body"]
            body["paths"][0]["details"]["distance"] = [[0, 5, bad]]
            with self.subTest(bad=bad):
                want = body["paths"][0]["distance"] / 1000
                self.assertAlmostEqual(to_route(body, 2).km_total, want, places=9)

    def test_malformed_bodies(self) -> None:
        good = fixture("route_toll")["body"]
        cases: list[Any] = [
            [],
            {"paths": []},
            {"paths": ["x"]},
            {"paths": [{**good["paths"][0], "points": "encoded-polyline"}]},
            {"paths": [{**good["paths"][0], "points": {"coordinates": []}}]},
            {"paths": [{**good["paths"][0], "points": {"coordinates": [[37.0]]}}]},
            {"paths": [{**good["paths"][0], "points": {"coordinates": [[37.0, 95.0], [37.1, 56.0]]}}]},
            {"paths": [{**good["paths"][0], "distance": "far"}]},
            {"paths": [{**good["paths"][0], "time": float("nan")}]},
            {"paths": [{**good["paths"][0], "snapped_waypoints": {"coordinates": [[37.0, 56.0]]}}]},
        ]
        for body in cases:
            with self.subTest(body=str(body)[:80]), self.assertRaises(MappingError):
                to_route(body, 2)

    def test_single_point_route(self) -> None:
        body = {
            "paths": [
                {
                    "distance": 0.0,
                    "time": 0,
                    "points": {"coordinates": [[37.0, 56.0]]},
                    "snapped_waypoints": {"coordinates": [[37.0, 56.0], [37.0, 56.0]]},
                    "details": {},
                }
            ]
        }
        r = to_route(body, 2)
        self.assertEqual((r.points, r.waypoint_idx, r.km_total), ((W,), (0, 0), 0.0))
        self.assertEqual(len(r.details), 1)

    def test_deterministic(self) -> None:
        self.assertEqual(route_with(("route_via",), W, S, E), route_with(("route_via",), W, S, E))

    def test_normalize_ref(self) -> None:
        cases = {
            "М-11": "М-11",
            "M-11": "М-11",  # Latin M
            "m-11": "М-11",
            "М-10, Е105": "М-10",
            "М-10;Е105": "М-10",
            "R-132": "Р-132",
            "P-132": "Р-132",
            "A-108": "А-108",
            "M 8": "М-8",
            "М–8": "М-8",  # en dash
            "46К-1150": "46К-1150",
            "МКАД": "МКАД",
            "Е105": "Е105",
            "  ": None,
            "": None,
        }
        for raw, want in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_ref(raw), want)
        self.assertIsNone(normalize_ref(None))
        self.assertIsNone(normalize_ref(5))


class SnapTest(unittest.TestCase):
    def test_snap_within_2_km(self) -> None:
        far = LatLon(55.975, 37.10)
        r = route_with(("route_snap_far",), W, far)
        self.assertAlmostEqual(haversine_km(far, r.snapped[1]), 1.112, places=3)

    def test_snap_over_2_km_is_unreachable(self) -> None:
        too_far = LatLon(55.962, 37.10)
        with self.assertRaises(Unreachable) as cm:
            route_with(("route_snap_too_far",), W, too_far)
        self.assertEqual(cm.exception.point_index, 1)
        self.assertEqual(cm.exception.snap_km, round(haversine_km(too_far, LatLon(55.985, 37.10)), 3))
        self.assertGreater(cm.exception.snap_km or 0, 2.0)

    def test_snap_limit_is_configurable(self) -> None:
        t = FixtureTransport("route_snap_far")
        with self.assertRaises(Unreachable):
            router(t, snap_max_km=1.0).route(RouteRequest((W, LatLon(55.975, 37.10)), False))


class ErrorMappingTest(unittest.TestCase):
    def test_point_not_found_and_out_of_bounds(self) -> None:
        for name, point in (
            ("error_point_not_found", LatLon(56.05, 37.25)),
            ("error_out_of_bounds", LatLon(56.0, 38.5)),
        ):
            with self.subTest(name=name), self.assertRaises(Unreachable) as cm:
                route_with((name,), W, point)
            self.assertEqual((cm.exception.point_index, cm.exception.snap_km), (1, None))

    def test_no_connection_two_points(self) -> None:
        t = FixtureTransport("error_connection_not_found")
        with self.assertRaises(Unreachable) as cm:
            router(t).route(RouteRequest((W, ISLAND), False))
        self.assertEqual(cm.exception.point_index, 1)
        self.assertEqual(len(t.sent), 1)

    def test_no_connection_finds_the_failing_leg(self) -> None:
        t = FixtureTransport("error_connection_not_found_via", "leg_w_s", "leg_s_island")
        with self.assertRaises(Unreachable) as cm:
            router(t).route(RouteRequest((W, S, ISLAND), False))
        self.assertEqual(cm.exception.point_index, 2)
        self.assertEqual([len(b["points"]) for b in t.sent], [3, 2, 2])

    def test_failing_leg_variants(self) -> None:
        cnf = (400, json.dumps(fixture("error_connection_not_found")["body"]).encode())
        pnf = (400, json.dumps(fixture("error_point_not_found")["body"]).encode())
        three = RouteRequest((W, S, E), False)
        for steps, want in (
            ((cnf, ok_body("leg_w_s"), pnf), 2),  # leg 2's end cannot be snapped alone
            ((cnf, ok_body("leg_w_s"), ok_body("leg_w_s")), 2),  # every leg fine alone: the finish
        ):
            with self.subTest(want=want), self.assertRaises(Unreachable) as cm:
                router(ScriptedTransport(*steps)).route(three)
            self.assertEqual(cm.exception.point_index, want)
        with self.assertRaises(UpstreamUnavailable):
            router(ScriptedTransport(cnf, (503, b""))).route(three)

    def test_upstream_failures(self) -> None:
        cases: dict[str, tuple[int, bytes]] = {
            "unknown profile": (400, json.dumps(fixture("error_unknown_profile")["body"]).encode()),
            "400 without hints": (400, b'{"message": "bad"}'),
            "400 point index out of range": (
                400,
                b'{"message": "x", "hints": [{"details": '
                b'"com.graphhopper.util.exceptions.PointNotFoundException", "point_index": 7}]}',
            ),
            "500": (500, b'{"message": "NullPointerException"}'),
            "502 html": (502, b"<html>Bad Gateway</html>"),
            "200 not json": (200, b"<html>ok</html>"),
            "200 no paths": (200, b'{"paths": []}'),
            "200 not utf-8": (200, b"\xff\xfe"),
        }
        for name, step in cases.items():
            with self.subTest(name), self.assertRaises(UpstreamUnavailable) as cm:
                router(ScriptedTransport(step)).route(RouteRequest((W, E), False))
            self.assertEqual(cm.exception.service, "graphhopper")

    def test_fewer_than_two_points(self) -> None:
        t = ScriptedTransport()
        with self.assertRaises(Unreachable):
            router(t).route(RouteRequest((W,), False))
        self.assertEqual(t.calls, 0)


class RetryTest(unittest.TestCase):
    def test_one_retry_on_refused_connection(self) -> None:
        t = ScriptedTransport(TransportError("ConnectionRefusedError", connect=True), ok_body())
        self.assertAlmostEqual(router(t).route(RouteRequest((W, E), False)).km_total, 19.953951, places=6)
        self.assertEqual(t.calls, 2)

    def test_no_second_retry(self) -> None:
        refused = TransportError("ConnectionRefusedError", connect=True)
        t = ScriptedTransport(refused, TransportError("ConnectionRefusedError", connect=True))
        with self.assertRaises(UpstreamUnavailable):
            router(t).route(RouteRequest((W, E), False))
        self.assertEqual(t.calls, 2)

    def test_no_retry_on_timeout_or_reset(self) -> None:
        for err in (TransportError("timeout"), TransportError("ConnectionResetError")):
            t = ScriptedTransport(err, ok_body())
            with self.subTest(err.kind), self.assertRaises(UpstreamUnavailable):
                router(t).route(RouteRequest((W, E), False))
            self.assertEqual(t.calls, 1)

    def test_no_retry_when_budget_is_spent(self) -> None:
        t = ScriptedTransport(TransportError("ConnectionRefusedError", connect=True), ok_body())
        with self.assertRaises(UpstreamUnavailable):
            router(t, timeout_s=0.1).route(RouteRequest((W, E), False))
        self.assertEqual(t.calls, 1)


class RequestTest(unittest.TestCase):
    def test_body(self) -> None:
        body = request_body((W, S), "car")
        self.assertEqual(body["points"], [[37.0, 56.0], [37.15, 55.95]])  # [lon, lat]
        self.assertEqual(body["details"], list(DETAILS))
        self.assertEqual(body["snap_preventions"], ["motorway", "tunnel", "bridge", "ferry"])
        self.assertIs(body["points_encoded"], False)
        self.assertIs(body["instructions"], False)
        self.assertNotIn("custom_model", body)  # avoid tolls is a server-side CH profile (ADR-0017 §3)

    def test_profile_by_avoid_tolls(self) -> None:
        t = ScriptedTransport(ok_body(), ok_body())
        sent: list[str] = []
        orig = t.post_json

        def spy(url: str, body: bytes, deadline: float) -> tuple[int, bytes]:
            sent.append(json.loads(body)["profile"])
            return orig(url, body, deadline)

        t.post_json = spy  # type: ignore[method-assign]
        gh = router(t)
        gh.route(RouteRequest((W, E), False))
        gh.route(RouteRequest((W, E), True))
        self.assertEqual(sent, ["car", "car_avoid_tolls"])
        self.assertEqual(gh.calls, 2)

    def test_every_fixture_request_is_what_the_adapter_sends(self) -> None:
        for path in sorted(DATA.glob("*.json")):
            f = json.loads(path.read_text("utf-8"))
            with self.subTest(path.name):
                pts = [LatLon(lat, lon) for lon, lat in f["request"]["points"]]
                self.assertEqual(f["request"], request_body(pts, f["request"]["profile"]))
                self.assertIn("GraphHopper 11.0 server, synthetic mini map", f["_meta"]["source"])
                self.assertIn("routing.yml", f["_meta"]["replaceWith"])


class SettingsTest(unittest.TestCase):
    def test_from_env(self) -> None:
        s = GraphHopperSettings.from_env({"VERST_GRAPHHOPPER_URL": " http://10.0.0.5:8989/ "})
        self.assertEqual((s.route_url, s.timeout_s), ("http://10.0.0.5:8989/route", 6.0))
        s = GraphHopperSettings.from_env(
            {"VERST_GRAPHHOPPER_URL": "https://gh.internal/gh/", "VERST_GRAPHHOPPER_TIMEOUT_S": "2.5"}
        )
        self.assertEqual((s.route_url, s.timeout_s), ("https://gh.internal/gh/route", 2.5))
        self.assertIsInstance(
            GraphHopperRouting.from_env({"VERST_GRAPHHOPPER_URL": "http://gh:8989"}).transport,
            UrllibTransport,
        )

    def test_invalid(self) -> None:
        for env in (
            {},
            {"VERST_GRAPHHOPPER_URL": ""},
            {"VERST_GRAPHHOPPER_URL": "gh:8989"},
            {"VERST_GRAPHHOPPER_URL": "ftp://gh"},
            {"VERST_GRAPHHOPPER_URL": "http://gh", "VERST_GRAPHHOPPER_TIMEOUT_S": "0"},
            {"VERST_GRAPHHOPPER_URL": "http://gh", "VERST_GRAPHHOPPER_TIMEOUT_S": "nan"},
            {"VERST_GRAPHHOPPER_URL": "http://gh", "VERST_GRAPHHOPPER_TIMEOUT_S": "six"},
        ):
            with self.subTest(env=env), self.assertRaises(ValueError):
                GraphHopperSettings.from_env(env)
        with self.assertRaises(ValueError):
            GraphHopperSettings("http://gh", snap_max_km=0)


class PrivacyLogTest(unittest.TestCase):
    """Risk register R-07: coordinates in logs are rounded; GraphHopper's messages are scrubbed."""

    def test_logs_round_coordinates(self) -> None:
        exact = ("56.0501", "37.145", "55.962")  # the full-precision request coordinates
        with self.assertLogs(LOGGER, level="INFO") as cm:
            route_with(("route_via",), W, S, E)
            for names, pts in (
                (("route_snap_too_far",), (W, LatLon(55.962, 37.10))),
                (("error_point_not_found",), (W, LatLon(56.05, 37.25))),
                (("error_connection_not_found",), (W, ISLAND)),
            ):
                with self.assertRaises(Unreachable):
                    route_with(names, *pts)
            with self.assertRaises(UpstreamUnavailable):
                router(ScriptedTransport((500, b'{"message": "Cannot find point 1: 56.0501,37.145"}'))).route(
                    RouteRequest((W, ISLAND), False)
                )
        text = "\n".join(cm.output)
        for s in exact:
            self.assertNotIn(s, text)
        self.assertIn("56.00,37.00 -> 56.00,37.30, 3 points, car", text)
        self.assertIn("56.05,37.15", text)  # the scrubbed GraphHopper message


class _Handler(http.server.BaseHTTPRequestHandler):
    reply: ClassVar[tuple[int, bytes, float]] = (200, b"{}", 0.0)
    seen: ClassVar[list[tuple[str, str, str, bytes]]] = []

    def do_POST(self) -> None:  # http.server API name
        body = self.rfile.read(int(self.headers["Content-Length"]))
        type(self).seen.append((self.path, self.headers["Content-Type"], self.headers["User-Agent"], body))
        status, payload, delay = type(self).reply
        time.sleep(delay)
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format: str, *args: Any) -> None:
        pass


@contextmanager
def serve(status: int, payload: bytes, delay: float = 0.0) -> Iterator[str]:
    _Handler.reply = (status, payload, delay)
    _Handler.seen = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


class UrllibTransportTest(unittest.TestCase):
    """The real HTTP path against a local stdlib server."""

    def test_route_over_http(self) -> None:
        status, payload = ok_body()
        with serve(status, payload) as url:
            gh = GraphHopperRouting(GraphHopperSettings(url + "/"))
            r = gh.route(RouteRequest((W, E), False))
        self.assertEqual(r, route_with(("route_toll",), W, E))
        path, ctype, agent, body = _Handler.seen[0]
        self.assertEqual((path, ctype), ("/route", "application/json"))
        self.assertTrue(agent.startswith("VerstPlanner"))
        self.assertEqual(json.loads(body), request_body((W, E), "car"))

    def test_http_errors_are_returned_not_raised(self) -> None:
        payload = json.dumps(fixture("error_point_not_found")["body"]).encode()
        with serve(400, payload) as url:
            got = UrllibTransport().post_json(url + "/route", b"{}", time.monotonic() + 5)
            self.assertEqual(got, (400, payload))
        with serve(503, b"down") as url, self.assertRaises(UpstreamUnavailable):
            GraphHopperRouting(GraphHopperSettings(url)).route(RouteRequest((W, E), False))

    def test_timeout(self) -> None:
        with serve(200, ok_body()[1], delay=1.0) as url:
            gh = GraphHopperRouting(GraphHopperSettings(url, timeout_s=0.2))
            t0 = time.monotonic()
            with self.assertRaises(UpstreamUnavailable):
                gh.route(RouteRequest((W, E), False))
            self.assertLess(time.monotonic() - t0, 0.9)

    def test_deadline_passed(self) -> None:
        with self.assertRaises(TransportError) as cm:
            UrllibTransport().post_json("http://127.0.0.1:9/route", b"{}", time.monotonic() - 1)
        self.assertEqual(cm.exception.kind, "timeout")

    def test_refused_connection_is_retried_once(self) -> None:
        with socket.socket() as s:  # a port nobody listens on
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        with self.assertLogs(LOGGER, level="WARNING") as cm, self.assertRaises(UpstreamUnavailable):
            gh = GraphHopperRouting(GraphHopperSettings(f"http://127.0.0.1:{port}"))
            gh.route(RouteRequest((W, E), False))
        self.assertEqual(sum("ConnectionRefusedError" in line for line in cm.output), 2)


class LayeringTest(unittest.TestCase):
    """ADR-0017: the adapter imports stdlib + domain/geo/itself only, and no composition root uses it yet."""

    ALLOWED = (
        "verst_planner.domain",
        "verst_planner.geo",
        "verst_planner.ports",
        "verst_planner.adapters.graphhopper",
    )

    def test_adapter_imports(self) -> None:
        files = sorted((PKG / "adapters" / "graphhopper").glob("*.py"))
        self.assertEqual([f.name for f in files], ["__init__.py", "mapping.py", "routing.py", "transport.py"])
        for path in files:
            for line, name in imports(path):
                if name.startswith("verst_planner"):
                    with self.subTest(module=module_name(path), line=line):
                        self.assertTrue(allowed(name, self.ALLOWED), name)

    def test_not_wired_this_week(self) -> None:
        for path in sorted(PKG.rglob("*.py")):
            if "graphhopper" in path.parts:
                continue
            with self.subTest(module=module_name(path)):
                self.assertFalse(any("graphhopper" in name for _l, name in imports(path)))


if __name__ == "__main__":
    logging.basicConfig()
    unittest.main()
