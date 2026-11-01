"""Risk register R-07: stored trips and logs carry coordinates rounded to ~1 km, the share page names the
start town only, feedback text is masked and expires, no IP is stored."""

from __future__ import annotations

import io
import json
import logging
import re
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from conftest import register
from fastapi.testclient import TestClient

from verst_api import store
from verst_api.logs import JsonFormatter, configure
from verst_api.privacy import mask_contacts, round_coordinates, scrub_trip

HOME = {"lat": 55.751234, "lon": 37.618912, "label": "ул. Тверская, 7, кв. 12"}
DACHA = {"lat": 56.732911, "lon": 38.854321, "label": "дача Ивановых"}
YAR = {"lat": 57.626111, "lon": 39.884522, "label": "Ярославль, Советская площадь"}
SECRETS = ("Тверская", "кв. 12", "Ивановых", "Советская", "55.751234", "37.618912", "56.732911", "57.626111")
PLAN_INPUT = {"origin": HOME, "destination": YAR, "vias": [DACHA], "crew": {"adults": 2}, "dailyKm": 300}


@pytest.fixture
def log_lines() -> Iterator[io.StringIO]:
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    old_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    try:
        yield buf
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)


def plan(client: TestClient, auth: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    r = client.post("/v1/trips/plan", json=body, headers=auth)
    assert r.status_code == 200, r.text
    result: dict[str, Any] = r.json()
    return result


def coordinate_decimals(node: Any) -> list[int]:
    out: list[int] = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("lat", "lon") and isinstance(v, float):
                out.append(len(repr(v).split(".")[1]))
            else:
                out += coordinate_decimals(v)
    elif isinstance(node, list):
        for v in node:
            out += coordinate_decimals(v)
    return out


def test_saved_trip_holds_towns_and_rounded_coordinates(
    client: TestClient, auth: dict[str, str], db: psycopg.Connection[Any]
) -> None:
    trip = plan(client, auth, {**PLAN_INPUT, "roundTrip": True})["trip"]
    assert any(s in json.dumps(trip, ensure_ascii=False) for s in SECRETS)  # the phone gets its exact trip
    r = client.post("/v1/trips", json={"trip": trip}, headers=auth)
    assert r.status_code == 201, r.text
    saved = r.json()
    assert saved["startTown"] == "Москва" and saved["title"] == "Москва → Ярославль → Москва"
    assert re.fullmatch(r"https://verst\.test/s/[0-9a-hjkmnp-tv-z]{8}", saved["shareUrl"])
    row = db.execute("SELECT row_to_json(t)::text FROM api.trip t").fetchone()
    assert row is not None
    stored = row[0]
    for s in SECRETS:
        assert s not in stored, s
    stored_trip = json.loads(stored)["trip"]
    decimals = coordinate_decimals(stored_trip)
    assert decimals and max(decimals) <= 2
    assert stored_trip["input"]["origin"] == {
        "lat": 55.75,
        "lon": 37.62,
        "label": "Москва",
        "placeId": None,
        "townId": None,
    }
    assert stored_trip["input"]["vias"][0]["label"] == "Переславль-Залесский"
    assert stored_trip["id"] == saved["tripId"]


def test_share_page_and_shared_json_show_the_town_only(client: TestClient, auth: dict[str, str]) -> None:
    trip = plan(client, auth, PLAN_INPUT)["trip"]
    saved = client.post("/v1/trips", json={"trip": trip}, headers=auth).json()
    page = client.get(f"/s/{saved['shareSlug']}")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert page.headers["content-language"] == "ru"
    assert "noindex" in page.headers["x-robots-tag"]
    assert "default-src 'none'" in page.headers["content-security-policy"]
    html = page.text
    assert "Старт: Москва" in html and "Москва → Ярославль" in html
    for s in (*SECRETS, "55.75", "37.62"):
        assert s not in html, s
    shared = client.get(f"/v1/shared/{saved['shareSlug']}")
    assert shared.status_code == 200
    body = shared.json()
    assert body["startTown"] == "Москва" and body["shareText"].startswith("Москва → Ярославль")
    for s in SECRETS:
        assert s not in shared.text, s
    # security B-3: the plan and the cost, not who travels, with what budget, when, or the engine state
    public = body["trip"]
    assert "engineState" not in public and "units" not in public["cost"] and "budgetRub" not in public["cost"]
    assert set(public["input"]) <= {"origin", "destination"} and "crew" not in shared.text
    assert "2026-" not in json.dumps(public["daysList"])  # times of day only, not the date of the trip


def test_privacy_page_and_forgetting_the_device(client: TestClient, auth: dict[str, str]) -> None:
    page = client.get("/privacy")
    assert page.status_code == 200 and page.headers["content-type"].startswith("text/html")
    assert "Что уходит на сервер" in page.text and "Нидерландах" in page.text
    trip = plan(client, auth, PLAN_INPUT)["trip"]
    saved = client.post("/v1/trips", json={"trip": trip}, headers=auth).json()
    assert client.delete("/v1/devices/me", headers=auth).status_code == 204
    assert client.get(f"/v1/shared/{saved['shareSlug']}").status_code == 404  # the trips went with the device
    assert (
        client.post("/v1/trips/plan", json=PLAN_INPUT, headers=auth).status_code == 401
    )  # the token is dead


def test_saving_twice_returns_the_same_link_and_delete_unshares(
    client: TestClient, auth: dict[str, str]
) -> None:
    trip = plan(client, auth, PLAN_INPUT)["trip"]
    first = client.post("/v1/trips", json={"trip": trip}, headers=auth).json()
    second = client.post("/v1/trips", json={"trip": trip}, headers=auth).json()
    assert first == second
    other = {"Authorization": "Bearer " + "x" * 43}
    assert client.delete(f"/v1/trips/{first['tripId']}", headers=other).status_code == 401
    stranger = register(client)
    assert client.delete(f"/v1/trips/{first['tripId']}", headers=stranger).status_code == 404
    assert client.delete(f"/v1/trips/{first['tripId']}", headers=auth).status_code == 204
    assert client.get(f"/s/{first['shareSlug']}").status_code == 404


def test_logs_carry_request_ids_and_no_exact_coordinates(
    client: TestClient, auth: dict[str, str], log_lines: io.StringIO
) -> None:
    r = client.post("/v1/trips/plan", json=PLAN_INPUT, headers={**auth, "X-Request-Id": "test-req-0001"})
    assert r.status_code == 200 and r.headers["x-request-id"] == "test-req-0001"
    client.get("/v1/ready-routes", params={"lat": 55.751234, "lon": 37.618912}, headers=auth)
    trip = r.json()["trip"]
    client.post("/v1/trips", json={"trip": trip}, headers=auth)
    # the server's lines only: the test client (httpx2) logs its own request URLs, query strings included
    lines = [json.loads(x) for x in log_lines.getvalue().splitlines()]
    lines = [x for x in lines if not x["logger"].startswith(("httpx", "httpcore"))]
    assert {x["logger"] for x in lines} <= {"verst_api.access", "verst_api.routes", "verst_api.engine"}
    text = "\n".join(json.dumps(x, ensure_ascii=False) for x in lines)
    for s in (*SECRETS, "lat=", "?lat", auth["Authorization"][7:]):
        assert s not in text, s
    plan_line = next(x for x in lines if x["msg"] == "plan")
    assert plan_line["origin"] == [55.75, 37.62] and plan_line["destination"] == [57.63, 39.88]
    assert plan_line["request_id"] == "test-req-0001"
    access = [x for x in lines if x["logger"] == "verst_api.access"]
    routes = {x["route"] for x in access}
    assert {"/v1/trips/plan", "/v1/ready-routes", "/v1/trips"} <= routes
    for x in access:
        assert re.fullmatch(r"[0-9a-f]{8}", x["device"]) and x["app_version"] == "0.9.0-beta"
        assert isinstance(x["latency_ms"], float) and x["status"] in (200, 201)
    generated = client.get("/healthz").headers["x-request-id"]
    assert re.fullmatch(r"[0-9a-f]{32}", generated)


def test_log_formatter_rounds_coordinates_passed_as_extras() -> None:
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "point", None, None)
    record.lat, record.lon = 55.751234, 37.618912
    out = json.loads(JsonFormatter().format(record))
    assert (out["lat"], out["lon"]) == (55.75, 37.62)


def test_feedback_text_is_masked_and_expires(
    client: TestClient, auth: dict[str, str], db: psycopg.Connection[Any]
) -> None:
    text = "Закрыто. Звоните +7 (916) 123-45-67 или ivan.petrov@mail.ru, цена 1500 ₽"
    r = client.post(
        "/v1/feedback", json={"kind": "closed", "placeId": "Q4357088", "text": text}, headers=auth
    )
    assert r.status_code == 201
    row = db.execute("SELECT text, place_id, kind, app_version FROM api.feedback").fetchone()
    assert row == (
        "Закрыто. Звоните [телефон скрыт] или [почта скрыта], цена 1500 ₽",
        "Q4357088",
        "closed",
        "0.9.0-beta",
    )
    db.execute("UPDATE api.feedback SET created_at = now() - interval '181 days'")
    pool = client.app.state.ctx.pool  # type: ignore[attr-defined]
    done = client.portal.call(store.cleanup, pool, 180)  # type: ignore[union-attr]
    assert done["feedbackTexts"] == 1
    assert db.execute("SELECT text FROM api.feedback").fetchone() == (None,)


@pytest.mark.parametrize(
    ("raw", "masked"),
    [
        ("89161234567", "[телефон скрыт]"),
        ("тел 8-916-123-45-67!", "тел [телефон скрыт]!"),
        ("a@b.ru", "[почта скрыта]"),
        ("2 км до 12:30, 4 300 ₽", "2 км до 12:30, 4 300 ₽"),
        ("с 10 до 18", "с 10 до 18"),
    ],
)
def test_mask_contacts(raw: str, masked: str) -> None:
    assert mask_contacts(raw) == masked


def test_scrub_trip_unit() -> None:
    trip = {
        "title": "дом → Тула",
        "input": {"origin": {"lat": 55.1234, "lon": 37.5678, "label": "дом"}, "vias": []},
        "daysList": [
            {
                "stops": [
                    {
                        "kind": "start",
                        "name": "дом",
                        "lat": 55.1234,
                        "lon": 37.5678,
                        "placeId": None,
                        "townId": None,
                    },
                    {
                        "kind": "sight",
                        "name": "Музей",
                        "lat": 54.1111,
                        "lon": 37.2222,
                        "placeId": "Q1",
                        "townId": None,
                    },
                    {
                        "kind": "finish",
                        "name": "Тула",
                        "lat": 54.19,
                        "lon": 37.61,
                        "placeId": None,
                        "townId": "t_tula",
                    },
                ]
            }
        ],
    }
    out = scrub_trip(trip, lambda lat, lon: "Город")
    assert out["title"] == "Город → Тула"
    assert out["input"]["origin"] == {"lat": 55.12, "lon": 37.57, "label": "Город"}
    stops = out["daysList"][0]["stops"]
    assert [s["name"] for s in stops] == ["Город", "Музей", "Тула"]
    assert (stops[1]["lat"], stops[1]["lon"]) == (54.11, 37.22)
    assert trip["title"] == "дом → Тула"  # the input is not mutated
    assert round_coordinates({"lat": True, "x": [{"lon": 1.23456}]}) == {"lat": True, "x": [{"lon": 1.23}]}


def test_configure_silences_the_uvicorn_access_log() -> None:
    root = logging.getLogger()
    saved = (root.handlers[:], root.level)
    try:
        configure("INFO")
        assert logging.getLogger("uvicorn.access").disabled  # it would print raw paths with query strings
        assert isinstance(root.handlers[0].formatter, JsonFormatter)
    finally:
        root.handlers[:], level = saved
        root.setLevel(level)
        logging.getLogger("uvicorn.access").disabled = False
