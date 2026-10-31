"""Contract tests: the HTTP API answers with exactly the shapes of `docs/contracts/v2` (the phone's bridge
contract), so the app decodes server and on-device results with one set of decoders."""

from __future__ import annotations

import json
from typing import Any

import pytest
from conftest import CONTRACTS
from fastapi.testclient import TestClient
from verst_planner import mobile

from verst_api.engine import RUSSIA_WORLD, Engine
from verst_api.schemas import PlanNoFit, PlanOk, ReadyRoute, RouteOut, TripInputIn

PLAN_CASES = sorted(p.stem for p in CONTRACTS.glob("plan-*.json"))


def contract(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((CONTRACTS / f"{name}.json").read_text("utf-8"))
    return data


def test_every_plan_contract_is_covered() -> None:
    assert PLAN_CASES == ["plan-budget-fit", "plan-moscow-parking", "plan-no-fit", "plan-synthetic"]


def bridge_plan(engine: Engine, input_json: dict[str, Any]) -> dict[str, Any]:
    """What the phone's engine (`russia_v1`) returns for the same input (run on the engine thread: the bridge
    is single-threaded). The server plans in `world_v1`; a trip inside Russia must not change there."""
    text = engine.submit(
        lambda: mobile.plan(RUSSIA_WORLD, "contract-test", json.dumps(input_json), None)
    ).result()
    envelope = json.loads(text)
    assert envelope["ok"], envelope
    result: dict[str, Any] = envelope["result"]
    return result


@pytest.mark.parametrize("name", PLAN_CASES)
def test_plan_equals_the_bridge(client: TestClient, auth: dict[str, str], engine: Engine, name: str) -> None:
    """No forked serialiser: the server body is byte-for-byte the bridge's `plan` result for the input."""
    c = contract(name)
    assert c["request"]["function"] == "plan" and c["request"]["args"]["world"] == RUSSIA_WORLD
    r = client.post("/v1/trips/plan", json=c["request"]["args"]["input_json"], headers=auth)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/json"
    assert r.json() == bridge_plan(engine, c["request"]["args"]["input_json"])


@pytest.mark.parametrize("name", PLAN_CASES)
def test_plan_matches_committed_contract(
    client: TestClient, auth: dict[str, str], engine: Engine, name: str
) -> None:
    """Exactly the committed example. If the engine itself no longer produces it, the file is stale: the
    planner's own `test_mobile_v2` fails then, and this test says so instead of reporting an API defect."""
    c = contract(name)
    expected = c["response"]["result"]
    if bridge_plan(engine, c["request"]["args"]["input_json"]) != expected:
        pytest.skip(
            f"docs/contracts/v2/{name}.json is stale against the working-tree engine (gen_api_contracts.py)"
        )
    r = client.post("/v1/trips/plan", json=c["request"]["args"]["input_json"], headers=auth)
    assert r.json() == expected


@pytest.mark.parametrize("name", PLAN_CASES)
def test_models_accept_the_contract(name: str) -> None:
    c = contract(name)
    TripInputIn.model_validate(c["request"]["args"]["input_json"])
    result = c["response"]["result"]
    model = PlanOk if result["outcome"] == "plan" else PlanNoFit
    model.model_validate(result)


def test_plan_sse_streams_progress_then_the_same_body(
    client: TestClient, auth: dict[str, str], engine: Engine
) -> None:
    c = contract("plan-budget-fit")
    headers = {**auth, "Accept": "text/event-stream"}
    with client.stream(
        "POST", "/v1/trips/plan", json=c["request"]["args"]["input_json"], headers=headers
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        assert r.headers["cache-control"] == "no-cache" and r.headers["x-accel-buffering"] == "no"
        text = "".join(r.iter_text())
    assert text.startswith("retry: 3000\n\n")
    events = parse_sse(text)
    names = [e["event"] for e in events]
    assert names[0] == "stage" and names[-1] == "done"
    assert set(names) <= {"stage", "stop", "done"} and "stop" in names
    ids = [int(e["id"]) for e in events]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)
    first = events[0]["data"]
    assert set(first) == {"key", "text", "progress"} and first["progress"] == 0.05
    stop = next(e["data"] for e in events if e["event"] == "stop")
    assert set(stop) == {"day", "stop"} and {"id", "kind", "sign", "name", "kmAt", "provisional"} <= set(
        stop["stop"]
    )
    progress = [e["data"]["progress"] for e in events if e["event"] == "stage"]
    assert progress == sorted(progress)
    assert events[-1]["data"] == bridge_plan(engine, c["request"]["args"]["input_json"])


def test_plan_sse_error_event(client: TestClient, auth: dict[str, str]) -> None:
    body: dict[str, Any] = {
        "origin": {"lat": 55.75, "lon": 37.61},
        "destination": {"lat": 55.0, "lon": 150.0},
    }
    body |= {"crew": {"adults": 2}, "dailyKm": 300}
    headers = {**auth, "Accept": "text/event-stream"}
    with client.stream("POST", "/v1/trips/plan", json=body, headers=headers) as r:
        assert r.status_code == 200  # errors after the stream started are events (ADR-0006)
        events = parse_sse("".join(r.iter_text()))
    assert events[-1]["event"] == "error"
    assert events[-1]["data"]["code"] == "UNREACHABLE" and events[-1]["data"]["details"] == {"pointIndex": 1}


def test_ready_routes_match_the_bridge(client: TestClient, auth: dict[str, str]) -> None:
    r = client.get("/v1/ready-routes", params={"lat": 55.7558, "lon": 37.6173, "limit": 20}, headers=auth)
    assert r.status_code == 200
    items = r.json()["items"]
    expected = json.loads(mobile.ready_routes(RUSSIA_WORLD, 55.7558, 37.6173, 50, 20))["result"]
    assert items == expected and len(items) >= 3
    for item in items:
        ReadyRoute.model_validate(item)
    far = client.get("/v1/ready-routes", params={"lat": 43.1, "lon": 131.9}, headers=auth)
    assert far.status_code == 200 and far.json() == {"items": []}


def test_openapi_lists_the_beta_endpoints(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths) == {
        "/v1/devices",
        "/v1/devices/me",
        "/v1/trips/plan",
        "/v1/route",
        "/v1/ready-routes",
        "/v1/trips",
        "/v1/trips/{trip_id}",
        "/v1/shared/{slug}",
        "/v1/feedback",
        "/v1/links/hotel",
    }


def test_route_model_matches_the_wire_shape() -> None:
    RouteOut.model_validate(
        {
            "points": [[56.0, 37.0], [56.0, 37.3]],
            "cumKm": [0.0, 19.9],
            "cumMin": [0.0, 14.2],
            "details": [{"fromIdx": 0, "toIdx": 1, "roadClass": "motorway", "roadRef": "М-11", "toll": True}],
            "waypointIdx": [0, 1],
            "snapped": [[56.0, 37.0], [56.0, 37.3]],
            "kmTotal": 19.9,
            "minTotal": 14.2,
            "synthetic": False,
        }
    )


def parse_sse(text: str) -> list[dict[str, Any]]:
    events = []
    for block in text.split("\n\n"):
        fields: dict[str, Any] = {}
        for line in block.splitlines():
            if line.startswith(":") or not line:
                continue
            key, _, value = line.partition(": ")
            fields[key] = value
        if "data" in fields:
            fields["data"] = json.loads(fields["data"])
            events.append(fields)
    return events
