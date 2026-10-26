"""Error mapping (architecture §10.6): one envelope, Russian messages, engine details preserved."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from verst_api.engine import Engine

MSK = {"lat": 55.7558, "lon": 37.6173}
YAR = {"lat": 57.6261, "lon": 39.8845}


def trip(**kw: Any) -> dict[str, Any]:
    return {"origin": MSK, "destination": YAR, "crew": {"adults": 2}, "dailyKm": 300} | kw


def error(r: Any) -> dict[str, Any]:
    body: dict[str, Any] = r.json()
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message", "details"}
    out: dict[str, Any] = body["error"]
    return out


@pytest.mark.parametrize(
    ("body", "field", "reason"),
    [
        (trip(dailyKm=123), "dailyKm", "out_of_range"),
        (trip(crew={"adults": 9}), "crew.adults", "out_of_range"),
        (trip(vias=[MSK, MSK, MSK, MSK]), "vias", "too_many"),
        (trip(startAt="2026-10-24T08:00+03:00"), "startAt", "must_be_local_without_offset"),
    ],
)
def test_engine_validation_errors(
    client: TestClient, auth: dict[str, str], body: dict[str, Any], field: str, reason: str
) -> None:
    r = client.post("/v1/trips/plan", json=body, headers=auth)
    assert r.status_code == 400
    e = error(r)
    assert e["code"] == "INVALID_INPUT" and e["message"] == "Проверьте параметры поездки"
    assert e["details"] == {"field": field, "reason": reason}


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"origin": MSK, "crew": {"adults": 2}}, "dailyKm"),
        (trip(dailyKm="300"), "dailyKm"),
        (trip(dailyKm=True), "dailyKm"),
        (trip(unknown=1), "unknown"),
        (trip(mood="fast"), "mood"),
        (trip(origin={"lat": 55.0}), "origin.lon"),
    ],
)
def test_request_validation_errors(
    client: TestClient, auth: dict[str, str], body: dict[str, Any], field: str
) -> None:
    r = client.post("/v1/trips/plan", json=body, headers=auth)
    assert r.status_code == 400
    e = error(r)
    assert e["code"] == "INVALID_INPUT" and e["details"]["field"] == field


def test_unreachable_and_too_short(client: TestClient, auth: dict[str, str]) -> None:
    r = client.post("/v1/trips/plan", json=trip(destination={"lat": 55.0, "lon": 150.0}), headers=auth)
    assert r.status_code == 404
    assert error(r) == {
        "code": "UNREACHABLE",
        "message": "Не нашли дорогу на машине до этой точки",
        "details": {"pointIndex": 1},
    }
    r = client.post("/v1/trips/plan", json=trip(destination={"lat": 55.7559, "lon": 37.6174}), headers=auth)
    assert r.status_code == 422
    e = error(r)
    assert e["code"] == "TOO_SHORT" and e["details"] == {"roadKm": 0.0}


def test_unknown_path_and_method(client: TestClient) -> None:
    r = client.get("/v1/nope")
    assert r.status_code == 404 and error(r)["code"] == "NOT_FOUND"
    r = client.get("/v1/trips/plan")
    assert r.status_code == 404 and error(r)["code"] == "NOT_FOUND"


def test_payload_too_large(make_client: Callable[..., TestClient]) -> None:
    client = make_client(max_body_bytes=10_000)
    r = client.post(
        "/v1/devices", content=b"{" + b" " * 20_000 + b"}", headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 413 and error(r)["code"] == "PAYLOAD_TOO_LARGE"
    assert r.headers["x-request-id"]


def test_payload_too_large_without_content_length(make_client: Callable[..., TestClient]) -> None:
    client = make_client(max_body_bytes=10_000)

    def chunks() -> Any:
        for _ in range(30):
            yield b" " * 1000

    r = client.post("/v1/devices", content=chunks(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and error(r)["code"] == "PAYLOAD_TOO_LARGE"


class Boom:
    def route(self, req: Any) -> Any:
        raise RuntimeError("boom with secret 55.751234")


def test_internal_errors_do_not_leak(make_client: Callable[..., TestClient], migrated: str) -> None:
    from conftest import register, settings_for

    engine = Engine(
        settings_for(migrated, routing="graphhopper", graphhopper_url="http://gh.test:8989"), Boom()
    )
    client = make_client(engine_override=engine, raise_server_exceptions=False)
    r = client.post("/v1/trips/plan", json=trip(), headers=register(client))
    assert r.status_code == 500
    assert error(r) == {
        "code": "INTERNAL",
        "message": "Что-то пошло не так, попробуйте ещё раз",
        "details": {},
    }
    assert "boom" not in r.text
