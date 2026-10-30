"""ADR-0017 §5 / ADR-0020 §4: `POST /v1/route` from GraphHopper (recorded real responses, no network) and
server planning with GraphHopper first and the road model only as a flagged fallback."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

import pytest
from conftest import GH_DATA, register, settings_for
from fastapi.testclient import TestClient
from verst_planner import mobile
from verst_planner.adapters.graphhopper import GraphHopperRouting, GraphHopperSettings
from verst_planner.domain.errors import Unreachable, UpstreamUnavailable
from verst_planner.domain.model import LatLon, Route, RouteRequest

from verst_api.engine import WORLD, Engine
from verst_api.routing import ServerRouting, route_to_json
from verst_api.schemas import RouteOut

GH_URL = "http://gh.test:8989"
MSK = {"lat": 55.7558, "lon": 37.6173}
YAR = {"lat": 57.6261, "lon": 39.8845}
PLAN = {"origin": MSK, "destination": YAR, "crew": {"adults": 2}, "dailyKm": 300}


class FixtureTransport:
    """Replays `backend/planner/tests/data/graphhopper/*.json` (real GraphHopper 11 responses,
    ADR-0017 §6)."""

    def __init__(self, *names: str) -> None:
        self.fixtures = [json.loads((GH_DATA / f"{n}.json").read_text("utf-8")) for n in names]

    def post_json(self, url: str, body: bytes, deadline: float) -> tuple[int, bytes]:
        assert url == GH_URL + "/route"
        req = json.loads(body)
        for f in self.fixtures:
            if f["request"] == req:
                return int(f["status"]), json.dumps(f["body"]).encode()
        raise AssertionError(f"no fixture for {req}")


def gh(*names: str) -> GraphHopperRouting:
    return GraphHopperRouting(GraphHopperSettings(GH_URL), FixtureTransport(*names))


def gh_engine(migrated: str, routing: Any, **kw: Any) -> Engine:
    return Engine(settings_for(migrated, routing="graphhopper", graphhopper_url=GH_URL, **kw), routing)


def points(name: str) -> list[list[float]]:
    req = json.loads((GH_DATA / f"{name}.json").read_text("utf-8"))["request"]
    return [[lat, lon] for lon, lat in req["points"]]


def test_route_returns_the_graphhopper_route(make_client: Callable[..., TestClient], migrated: str) -> None:
    client = make_client(engine_override=gh_engine(migrated, gh("route_toll")))
    auth = register(client)
    r = client.post("/v1/route", json={"points": points("route_toll"), "avoidTolls": False}, headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    RouteOut.model_validate(body)
    expected = gh("route_toll").route(
        RouteRequest(tuple(LatLon(a, b) for a, b in points("route_toll")), False)
    )
    assert body == route_to_json(expected)
    assert body["synthetic"] is False and any(d["toll"] for d in body["details"])
    assert body["cumKm"][-1] == body["kmTotal"] and len(body["points"]) == len(body["cumKm"])


def test_route_avoid_tolls_profile(make_client: Callable[..., TestClient], migrated: str) -> None:
    client = make_client(engine_override=gh_engine(migrated, gh("route_avoid_tolls")))
    auth = register(client)
    r = client.post(
        "/v1/route", json={"points": points("route_avoid_tolls"), "avoidTolls": True}, headers=auth
    )
    assert r.status_code == 200 and not any(d["toll"] for d in r.json()["details"])


def test_route_unreachable_point(make_client: Callable[..., TestClient], migrated: str) -> None:
    client = make_client(engine_override=gh_engine(migrated, gh("error_point_not_found")))
    r = client.post("/v1/route", json={"points": points("error_point_not_found")}, headers=register(client))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "UNREACHABLE" and "pointIndex" in r.json()["error"]["details"]


def test_route_without_graphhopper_is_unavailable_not_synthetic(
    client: TestClient, auth: dict[str, str]
) -> None:
    r = client.post("/v1/route", json={"points": [[55.75, 37.61], [57.62, 39.88]]}, headers=auth)
    assert r.status_code == 503
    assert r.json()["error"] == {
        "code": "UPSTREAM",
        "message": "Сервис маршрутов временно недоступен",
        "details": {"reason": "routing_not_configured"},
    }


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"points": [[55.75, 37.61]]}, "points"),
        ({"points": [[55.75, 37.61], [56.0, 38.0]], "avoidTolls": "yes"}, "avoidTolls"),
        ({"points": [[95.0, 37.61], [55.0, 37.0]]}, "points"),
    ],
)
def test_route_validation(
    make_client: Callable[..., TestClient], migrated: str, body: dict[str, Any], field: str
) -> None:
    client = make_client(engine_override=gh_engine(migrated, gh()))  # never reached: no fixture needed
    r = client.post("/v1/route", json=body, headers=register(client))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_INPUT" and r.json()["error"]["details"]["field"] == field


# ------------------------------------------------------------------------------------- server planning


class RealLike:
    """Stands in for GraphHopper in a full plan: the road model's geometry, reported as a real route."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.calls = 0

    def route(self, req: RouteRequest) -> Route:
        self.calls += 1
        r: Route = self.inner.route(req)
        return Route(
            r.points, r.cum_km, r.cum_min, r.details, r.waypoint_idx, r.snapped, r.km_total, r.min_total
        )


class Down:
    def __init__(self, delay_s: float = 0.0) -> None:
        self.delay_s = delay_s

    def route(self, req: RouteRequest) -> Route:
        time.sleep(self.delay_s)
        raise UpstreamUnavailable("graphhopper")


def road_model() -> Any:
    """The engine's road model (`HybridRouting`) of the loaded `russia_v1` world (test-only access)."""
    return mobile._WORLDS[WORLD].fakes.routing


def test_server_plan_uses_graphhopper(make_client: Callable[..., TestClient], migrated: str) -> None:
    # Екатеринбург → Тюмень is synthetic on the road model (docs/contracts/v2/plan-synthetic.json);
    # through the primary routing it is a "real" route, so the trip must not carry approxDistances.
    primary = RealLike(road_model())
    client = make_client(engine_override=gh_engine(migrated, primary))
    body = {
        **PLAN,
        "origin": {"lat": 56.8389, "lon": 60.6057},
        "destination": {"lat": 57.153, "lon": 65.5343},
    }
    r = client.post("/v1/trips/plan", json=body, headers=register(client))
    assert r.status_code == 200, r.text
    assert primary.calls >= 1
    assert "approxDistances" not in r.json()["trip"]


def test_graphhopper_down_is_503_without_fallback(
    make_client: Callable[..., TestClient], migrated: str
) -> None:
    client = make_client(engine_override=gh_engine(migrated, Down()))
    r = client.post("/v1/trips/plan", json=PLAN, headers=register(client))
    assert r.status_code == 503
    assert r.json()["error"]["details"] == {"service": "graphhopper"}


def test_graphhopper_down_with_fallback_is_flagged_synthetic(
    make_client: Callable[..., TestClient], migrated: str
) -> None:
    client = make_client(engine_override=gh_engine(migrated, Down(), synthetic_fallback=True))
    r = client.post("/v1/trips/plan", json=PLAN, headers=register(client))
    assert r.status_code == 200
    assert r.json()["trip"]["approxDistances"] is True
    metrics = client.get("/metrics").text
    assert "verst_routing_fallback_total" in metrics and "verst_plan_synthetic_total" in metrics


def test_plan_timeout_is_503(make_client: Callable[..., TestClient], migrated: str) -> None:
    client = make_client(engine_override=gh_engine(migrated, Down(delay_s=0.6)), plan_timeout_s=0.2)
    r = client.post("/v1/trips/plan", json=PLAN, headers=register(client))
    assert r.status_code == 503 and r.json()["error"]["details"] == {"reason": "timeout"}


def test_server_routing_unit() -> None:
    class Fallback:
        def route(self, req: RouteRequest) -> Route:
            p = req.points
            return Route(p, (0.0, 1.0), (0.0, 1.0), (), (0, 1), p, 1.0, 1.0)

    class Fails:
        def __init__(self, exc: Exception) -> None:
            self.exc = exc

        def route(self, req: RouteRequest) -> Route:
            raise self.exc

    req = RouteRequest((LatLon(55, 37), LatLon(56, 38)), False)
    assert ServerRouting(Fails(UpstreamUnavailable("graphhopper")), Fallback()).route(req).synthetic is True
    with pytest.raises(UpstreamUnavailable):
        ServerRouting(Fails(UpstreamUnavailable("graphhopper")), None).route(req)
    with pytest.raises(Unreachable):  # an answer, never a reason to fall back
        ServerRouting(Fails(Unreachable(1)), Fallback()).route(req)
