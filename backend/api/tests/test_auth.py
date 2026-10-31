"""ADR-0007 device auth: anonymous registration, opaque bearer tokens, only sha256(token) stored."""

from __future__ import annotations

import hashlib
from typing import Any

import psycopg
import pytest
from conftest import register
from fastapi.testclient import TestClient


def test_register_returns_a_token_and_stores_only_its_hash(
    client: TestClient, db: psycopg.Connection[Any]
) -> None:
    r = client.post("/v1/devices", json={"appVersion": "0.9.0", "locale": "ru-RU"})
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"deviceId", "token"} and len(body["token"]) == 43
    row = db.execute(
        "SELECT token_hash, app_version, locale FROM api.device WHERE id = %s", (body["deviceId"],)
    ).fetchone()
    assert row is not None
    assert bytes(row[0]) == hashlib.sha256(body["token"].encode()).digest()
    assert (row[1], row[2]) == ("0.9.0", "ru-RU")
    dump = str(db.execute("SELECT row_to_json(d) FROM api.device d").fetchall())
    assert body["token"] not in dump


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"appVersion": ""},
        {"appVersion": "1.0 beta"},
        {"appVersion": "x" * 33},
        {"appVersion": "1.0", "locale": "русский"},
        {"appVersion": "1.0", "imei": "123"},
    ],
)
def test_register_validation(client: TestClient, body: dict[str, Any]) -> None:
    r = client.post("/v1/devices", json=body)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_INPUT"


@pytest.mark.parametrize(
    "header",
    [None, "", "Bearer", "Bearer short", "Token " + "a" * 43, "Bearer " + "a" * 43, "bearer " + "a" * 43],
)
def test_protected_endpoints_need_a_valid_token(client: TestClient, header: str | None) -> None:
    headers = {} if header is None else {"Authorization": header}
    r = client.get("/v1/ready-routes", params={"lat": 55.75, "lon": 37.61}, headers=headers)
    assert r.status_code == 401
    assert r.json() == {
        "error": {"code": "UNAUTHORIZED", "message": "Перезапустите приложение", "details": {}}
    }


def test_revoked_token_is_rejected(client: TestClient, db: psycopg.Connection[Any]) -> None:
    auth = register(client)
    ok = client.get("/v1/ready-routes", params={"lat": 55.75, "lon": 37.61}, headers=auth)
    assert ok.status_code == 200
    db.execute("UPDATE api.device SET revoked_at = now()")
    r = client.get("/v1/ready-routes", params={"lat": 55.75, "lon": 37.61}, headers=auth)
    assert r.status_code == 401


def test_last_seen_is_refreshed_at_most_hourly(client: TestClient, db: psycopg.Connection[Any]) -> None:
    auth = register(client)
    db.execute("UPDATE api.device SET last_seen_at = now() - interval '30 minutes'")
    client.get("/v1/ready-routes", params={"lat": 55.75, "lon": 37.61}, headers=auth)
    fresh = db.execute("SELECT now() - last_seen_at > interval '29 minutes' FROM api.device").fetchone()
    assert fresh == (True,)
    db.execute("UPDATE api.device SET last_seen_at = now() - interval '2 hours'")
    client.get("/v1/ready-routes", params={"lat": 55.75, "lon": 37.61}, headers=auth)
    stale = db.execute("SELECT now() - last_seen_at < interval '1 minute' FROM api.device").fetchone()
    assert stale == (True,)


def test_public_endpoints_need_no_token(client: TestClient) -> None:
    assert client.get("/healthz").status_code == 200
    assert client.get("/s/abcdefgh").status_code == 404  # not found, not unauthorized
    assert client.get("/v1/shared/abcdefgh").json()["error"]["code"] == "NOT_FOUND"
