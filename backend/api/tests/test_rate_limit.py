"""ADR-0020 §6 rate limits: fixed windows in PostgreSQL, per device (plan, route, save, feedback, default)
and per client IP as an HMAC (registration, public share pages)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import psycopg
from conftest import register
from fastapi.testclient import TestClient

PLAN: dict[str, Any] = {"origin": {"lat": 55.75, "lon": 37.61}, "destination": {"lat": 55.0, "lon": 150.0}}
PLAN |= {"crew": {"adults": 2}, "dailyKm": 300}  # fails fast (UNREACHABLE) but still counts


def test_plan_limit_per_device(make_client: Callable[..., TestClient]) -> None:
    client = make_client(rate_plan_per_hour=2)
    a, b = register(client), register(client)
    codes = [client.post("/v1/trips/plan", json=PLAN, headers=a).status_code for _ in range(3)]
    assert codes == [404, 404, 429]
    r = client.post("/v1/trips/plan", json=PLAN, headers=a)
    assert r.status_code == 429
    body = r.json()["error"]
    assert body["code"] == "RATE_LIMITED" and body["details"] == {"bucket": "plan", "limit": 2}
    assert body["message"] == "Слишком много запросов, подождите минуту"
    assert 1 <= int(r.headers["retry-after"]) <= 3600
    assert (
        client.post("/v1/trips/plan", json=PLAN, headers=b).status_code == 404
    )  # another device is not limited
    ready = client.get("/v1/ready-routes", params={"lat": 55.75, "lon": 37.61}, headers=a)
    assert ready.status_code == 200  # another bucket


def test_feedback_limit_is_daily(make_client: Callable[..., TestClient]) -> None:
    client = make_client(rate_feedback_per_day=1)
    auth = register(client)
    assert client.post("/v1/feedback", json={"kind": "other"}, headers=auth).status_code == 201
    r = client.post("/v1/feedback", json={"kind": "other"}, headers=auth)
    assert r.status_code == 429 and int(r.headers["retry-after"]) <= 86400


def test_registration_limit_per_ip_stores_no_ip(
    make_client: Callable[..., TestClient], db: psycopg.Connection[Any]
) -> None:
    client = make_client(rate_register_per_hour_ip=2)
    codes = [client.post("/v1/devices", json={"appVersion": "1.0"}).status_code for _ in range(3)]
    assert codes == [201, 201, 429]
    keys = [k for (k,) in db.execute("SELECT key FROM api.rate_counter").fetchall()]
    assert keys and all(k.startswith("register:") and len(k) == len("register:") + 16 for k in keys)
    assert not any("testclient" in k or "127.0.0.1" in k for k in keys)


def test_public_share_page_limit(make_client: Callable[..., TestClient]) -> None:
    client = make_client(rate_public_per_hour_ip=1)
    assert client.get("/s/abcdefgh").status_code == 404
    assert client.get("/s/abcdefgh").status_code == 429
    assert client.get("/v1/shared/abcdefgh").status_code == 429  # the same bucket


def test_unauthenticated_requests_do_not_count(
    make_client: Callable[..., TestClient], db: psycopg.Connection[Any]
) -> None:
    client = make_client()
    assert client.post("/v1/trips/plan", json=PLAN).status_code == 401
    assert db.execute("SELECT count(*) FROM api.rate_counter").fetchone() == (0,)
