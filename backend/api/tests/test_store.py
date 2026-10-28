"""Repository and migrations against PostgreSQL 16 (conftest: CI service or a throwaway cluster)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import psycopg
import pytest
from conftest import CONTRACTS, register
from fastapi.testclient import TestClient

from verst_api.db import migrate_down, migrate_up, migrations


def test_migrations_up_down_up(migrated: str, db: psycopg.Connection[Any]) -> None:
    assert [m.version for m in migrations()] == [1]
    assert all(m.down is not None for m in migrations())
    assert asyncio.run(migrate_up(migrated)) == []  # idempotent
    assert asyncio.run(migrate_down(migrated, 0)) == [1]
    assert db.execute("SELECT to_regclass('api.trip')").fetchone() == (None,)
    assert asyncio.run(migrate_up(migrated)) == [1]
    tables = {r[0] for r in db.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'api'").fetchall()}
    assert tables == {"device", "trip", "feedback", "rate_counter", "schema_migration"}


def test_schema_has_no_place_for_exact_points_or_ips(db: psycopg.Connection[Any]) -> None:
    cols = db.execute(
        "SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'api'"
    ).fetchall()
    names = {c[1] for c in cols}
    assert not names & {
        "lat",
        "lon",
        "ip",
        "ip_address",
        "label",
        "token",
        "geom",
        "address",
        "phone",
        "email",
    }
    assert not any(c[2] in ("inet", "cidr", "USER-DEFINED") for c in cols)


def test_constraints_guard_the_data(db: psycopg.Connection[Any]) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("INSERT INTO api.device (token_hash, app_version) VALUES ('\\x00', '1.0')")
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("INSERT INTO api.feedback (device_id, kind) VALUES (gen_random_uuid(), 'spam')")


def saved_trip(client: TestClient, auth: dict[str, str], name: str = "plan-synthetic") -> dict[str, Any]:
    body = json.loads((CONTRACTS / f"{name}.json").read_text("utf-8"))["request"]["args"]["input_json"]
    trip = client.post("/v1/trips/plan", json=body, headers=auth).json()["trip"]
    r = client.post("/v1/trips", json={"trip": trip}, headers=auth)
    assert r.status_code == 201, r.text
    out: dict[str, Any] = r.json()
    return out


def test_saved_trip_limit(make_client: Callable[..., TestClient], db: psycopg.Connection[Any]) -> None:
    client = make_client(max_saved_trips=1)
    auth = register(client)
    saved_trip(client, auth, "plan-synthetic")
    body = json.loads((CONTRACTS / "plan-moscow-parking.json").read_text("utf-8"))["request"]["args"][
        "input_json"
    ]
    trip = client.post("/v1/trips/plan", json=body, headers=auth).json()["trip"]
    r = client.post("/v1/trips", json={"trip": trip}, headers=auth)
    assert r.status_code == 409
    assert r.json()["error"] == {
        "code": "LIMIT_REACHED",
        "message": "Можно сохранить до 50 поездок",
        "details": {"limit": 1},
    }
    row = db.execute("SELECT km, days, synthetic, start_town FROM api.trip").fetchone()
    assert row == (393, 1, True, "Екатеринбург")


def test_save_rejects_foreign_or_broken_trips(client: TestClient, auth: dict[str, str]) -> None:
    body = json.loads((CONTRACTS / "plan-synthetic.json").read_text("utf-8"))["request"]["args"]["input_json"]
    trip = client.post("/v1/trips/plan", json=body, headers=auth).json()["trip"]
    old = {**trip, "engineVersion": "99.0.0"}
    r = client.post("/v1/trips", json={"trip": old}, headers=auth)
    assert r.status_code == 400
    assert r.json()["error"]["details"] == {"field": "engineVersion", "reason": "incompatible"}
    no_state = {k: v for k, v in trip.items() if k != "engineState"}
    r = client.post("/v1/trips", json={"trip": no_state}, headers=auth)
    assert r.status_code == 400 and r.json()["error"]["details"]["field"] == "trip.engineState"
    broken = {**trip, "engineState": {"days": "x"}}
    assert client.post("/v1/trips", json={"trip": broken}, headers=auth).status_code == 400


def test_feedback_trip_must_be_own(
    client: TestClient, auth: dict[str, str], db: psycopg.Connection[Any]
) -> None:
    saved = saved_trip(client, auth)
    ok = client.post("/v1/feedback", json={"kind": "price", "tripId": saved["tripId"]}, headers=auth)
    assert ok.status_code == 201
    stranger = register(client)
    r = client.post("/v1/feedback", json={"kind": "price", "tripId": saved["tripId"]}, headers=stranger)
    assert r.status_code == 404
    bad = client.post("/v1/feedback", json={"kind": "spam"}, headers=auth)
    assert bad.status_code == 400 and bad.json()["error"]["details"]["field"] == "kind"
    assert db.execute("SELECT count(*), max(text) FROM api.feedback").fetchone() == (1, None)


def test_readyz_and_metrics(client: TestClient) -> None:
    r = client.get("/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["db"] is True and body["engine"] is True
    assert body["routing"] == "road_model" and body["catalogue"].startswith("wd-")
    m = client.get("/metrics")
    assert m.status_code == 200 and "verst_http_requests_total" in m.text
    assert 'route="/readyz"' in m.text


def test_save_rejects_implausible_numbers_and_recomputes_the_cost(
    client: TestClient, auth: dict[str, str]
) -> None:
    """Acceptance 28.10, QA B-2: nothing no plan can produce is stored, and the cost is the server's own."""
    body = json.loads((CONTRACTS / "plan-synthetic.json").read_text("utf-8"))["request"]["args"]["input_json"]
    trip = client.post("/v1/trips/plan", json=body, headers=auth).json()["trip"]
    units = trip["cost"]["units"]
    fuel = {**units["fuel"], "regions": [{**r, "priceRub": "999999999"} for r in units["fuel"]["regions"]]}
    cases = [
        ({**trip, "km": -5}, "trip.km"),
        ({**trip, "daysList": [], "days": 0}, "trip.daysList"),
        (
            {**trip, "cost": {**trip["cost"], "units": {**units, "fuel": fuel}}},
            "trip.cost.units.fuel.regions[0].priceRub",
        ),
    ]
    for forged, field in cases:
        r = client.post("/v1/trips", json={"trip": forged}, headers=auth)
        assert r.status_code == 400, (field, r.text)
        assert r.json()["error"]["details"]["field"] == field
    # forged totals are replaced by the engine's own, recomputed from the units
    forged_total = {**trip, "cost": {**trip["cost"], "totalRub": -5}}
    saved = client.post("/v1/trips", json={"trip": forged_total}, headers=auth).json()
    shared = client.get(f"/v1/shared/{saved['shareSlug']}").json()
    assert shared["trip"]["cost"]["totalRub"] == trip["cost"]["totalRub"]
