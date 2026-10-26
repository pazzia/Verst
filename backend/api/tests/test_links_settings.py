"""Partner link stub (no affiliate link until LEG-02), configuration guards and small units (share page
wording, bridge error mapping, the migration CLI)."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from verst_api.db import main as db_main
from verst_api.errors import from_envelope
from verst_api.settings import Settings
from verst_api.share_page import days_word

HOTEL = "pl_yar_hotel_strelka"  # docs/contracts/v2/poi_details-hotel.json
SIGHT = "Q4357088"  # docs/contracts/v2/poi_details-sight.json


def test_hotel_link_is_a_plain_search(client: TestClient, auth: dict[str, str]) -> None:
    params: dict[str, Any] = {"placeId": HOTEL, "checkin": "2026-11-07", "nights": 2, "adults": 2}
    r = client.get("/v1/links/hotel", params={**params, "childrenAges": [5, 9]}, headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["partner"] == "yandex_travel" and body["affiliate"] is False
    url = urlparse(body["url"])
    assert (url.scheme, url.netloc, url.path) == ("https", "travel.yandex.ru", "/hotels/search/")
    assert parse_qs(url.query) == {
        "text": ["Ярославль"],
        "checkinDate": ["2026-11-07"],
        "checkoutDate": ["2026-11-09"],
        "adults": ["2"],
        "childrenAges": ["5,9"],
    }
    for marker in ("tp.media", "marker", "sub_id", "campaign"):
        assert marker not in body["url"]


def test_hotel_link_errors(client: TestClient, auth: dict[str, str]) -> None:
    r = client.get("/v1/links/hotel", params={"placeId": SIGHT, "checkin": "2026-11-07"}, headers=auth)
    assert r.status_code == 400 and r.json()["error"]["details"] == {
        "field": "placeId",
        "reason": "not_a_hotel",
    }
    r = client.get("/v1/links/hotel", params={"placeId": "nope", "checkin": "2026-11-07"}, headers=auth)
    assert r.status_code == 404
    r = client.get("/v1/links/hotel", params={"placeId": HOTEL, "checkin": "07.11.2026"}, headers=auth)
    assert r.status_code == 400 and r.json()["error"]["details"]["field"] == "checkin"


@pytest.mark.parametrize(
    "kw",
    [
        {"env": "prod", "public_base_url": "https://verst.app"},
        {"env": "prod", "rate_key_secret": "x" * 40, "public_base_url": "http://verst.app"},
        {
            "env": "prod",
            "rate_key_secret": "x" * 40,
            "public_base_url": "https://verst.app",
            "clock": "golden",
        },
        {"routing": "graphhopper"},
    ],
)
def test_settings_refuse_unsafe_configs(kw: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Settings(**kw)


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERST_ENV", "prod")
    monkeypatch.setenv("VERST_RATE_KEY_SECRET", "s" * 48)
    monkeypatch.setenv("VERST_PUBLIC_BASE_URL", "https://verst.example")
    monkeypatch.setenv("VERST_ROUTING", "graphhopper")
    monkeypatch.setenv("VERST_GRAPHHOPPER_URL", "http://10.0.0.5:8989")
    monkeypatch.setenv("VERST_RATE_PLAN_PER_HOUR", "12")
    s = Settings()
    assert (s.env, s.routing, s.rate_plan_per_hour, s.synthetic_fallback) == (
        "prod",
        "graphhopper",
        12,
        False,
    )


@pytest.mark.parametrize(
    ("n", "word"),
    [(1, "день"), (2, "дня"), (4, "дня"), (5, "дней"), (11, "дней"), (12, "дней"), (21, "день")],
)
def test_share_page_days_word(n: int, word: str) -> None:
    assert days_word(n) == word


@pytest.mark.parametrize(
    ("error", "status", "code", "details"),
    [
        ({"code": "UNREACHABLE", "pointIndex": 2}, 404, "UNREACHABLE", {"pointIndex": 2}),
        ({"code": "TOO_SHORT", "roadKm": 1.5}, 422, "TOO_SHORT", {"roadKm": 1.5}),
        ({"code": "UPSTREAM"}, 503, "UPSTREAM", {}),
        ({"code": "NOT_FOUND", "message": "place x not found"}, 404, "NOT_FOUND", {}),
        ({"code": "TZDATA_MISSING", "message": "Europe/Moscow"}, 500, "INTERNAL", {}),
        (
            {"code": "INVALID_INPUT", "field": "lat", "reason": "out_of_range"},
            400,
            "INVALID_INPUT",
            {"field": "lat", "reason": "out_of_range"},
        ),
    ],
)
def test_bridge_errors_map_to_http(
    error: dict[str, Any], status: int, code: str, details: dict[str, Any]
) -> None:
    e = from_envelope(error)
    assert (e.status, e.code, e.details) == (status, code, details)


def test_migration_cli_status(
    migrated: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("VERST_DATABASE_URL", migrated)
    assert db_main(["status"]) == 0
    assert capsys.readouterr().out == "0001 api_beta: applied\n"
    assert db_main(["up"]) == 0
    assert capsys.readouterr().out == "applied: nothing\n"
