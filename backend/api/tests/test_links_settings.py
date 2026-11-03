"""Partner link stub (no affiliate link until LEG-02), configuration guards and small units (share page
wording, bridge error mapping, the migration CLI)."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from verst_api import links
from verst_api.db import main as db_main
from verst_api.errors import from_envelope
from verst_api.settings import Settings
from verst_api.share_page import days_word

HOTEL = "osm_n10175244917"  # a real OSM hotel in Ярославль (docs/contracts/v2/poi_details-hotel.json)
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


# ---- ENG-03: the Travelpayouts partner link (CEO 01.11)


def _tp_answer(url: str) -> dict[str, Any]:
    link = {"url": url, "code": "success", "partner_url": "https://tp.media/r?marker=1&u=x"}
    return {"result": {"links": [link]}}


def test_affiliate_wraps_with_sub_id_and_caches() -> None:
    calls: list[tuple[str, dict[str, str], dict[str, Any]]] = []

    def post(url: str, headers: dict[str, str], body: bytes, timeout: float) -> Any:
        payload = json.loads(body)
        calls.append((url, headers, payload))
        return _tp_answer(payload["links"][0]["url"])

    aff = links.AffiliateLinks(links.Travelpayouts("tok", "12345", "678"), post=post)
    target = "https://travel.yandex.ru/hotels/search/?text=X"
    assert aff.wrap(target, "t1_s2") == "https://tp.media/r?marker=1&u=x"
    assert aff.wrap(target, "t1_s2") == "https://tp.media/r?marker=1&u=x"  # cached
    assert len(calls) == 1
    url, headers, payload = calls[0]
    assert url == links.TP_LINKS_API and headers["X-Access-Token"] == "tok"
    links_in = [{"url": target, "sub_id": "t1_s2"}]
    assert payload == {"trs": 678, "marker": 12345, "shorten": False, "links": links_in}


@pytest.mark.parametrize(
    "answer",
    [
        RuntimeError("timeout"),
        {"result": {"links": [{"code": "error", "partner_url": "https://tp.media/r"}]}},
        {"result": {"links": []}},
        {"links": [{"partner_url": "http://insecure"}]},
        ["not", "a", "dict"],
    ],
)
def test_affiliate_failure_falls_back(answer: Any) -> None:
    def post(url: str, headers: dict[str, str], body: bytes, timeout: float) -> Any:
        if isinstance(answer, Exception):
            raise answer
        return answer

    aff = links.AffiliateLinks(links.Travelpayouts("tok", "1", "2"), post=post)
    assert aff.wrap("https://travel.yandex.ru/hotels/search/", "app") is None
    off = links.AffiliateLinks(None)
    assert off.wrap("https://x", "app") is None and not off.enabled


def test_sub_id_is_short_and_clean() -> None:
    assert links.sub_id("trip-1:a", "st_9") == "trip1a_st9"
    assert links.sub_id(None, None) == "app"
    assert len(links.sub_id("x" * 40, "y" * 40)) == links.SUB_ID_MAX


def test_hotel_link_affiliate_through_the_route(client: TestClient, auth: dict[str, str]) -> None:
    seen: list[dict[str, Any]] = []

    def post(url: str, headers: dict[str, str], body: bytes, timeout: float) -> Any:
        seen.append(json.loads(body))
        return _tp_answer("")

    aff = links.AffiliateLinks(links.Travelpayouts("tok", "1", "2"), post=post)
    client.app.state.ctx.affiliate = aff  # type: ignore[attr-defined]
    try:
        params = {"placeId": HOTEL, "checkin": "2026-11-07", "tripId": "trip7", "stopId": "d1_night"}
        body = client.get("/v1/links/hotel", params=params, headers=auth).json()
        expected = {"url": "https://tp.media/r?marker=1&u=x", "partner": "yandex_travel", "affiliate": True}
        assert body == expected
        assert seen[0]["links"][0]["sub_id"] == "trip7_d1night"
        assert seen[0]["links"][0]["url"].startswith("https://travel.yandex.ru/hotels/search/?text=")
    finally:
        client.app.state.ctx.affiliate = links.AffiliateLinks(None)  # type: ignore[attr-defined]


def test_partner_settings_all_or_none() -> None:
    with pytest.raises(ValidationError):
        Settings(tp_token="t", tp_marker="1")
    s = Settings(tp_token="tok-9f3e", tp_marker="1", tp_trs="2")
    cfg = links.travelpayouts(s)
    assert cfg is not None and cfg.token == "tok-9f3e" and cfg.marker == "1"
    assert "tok-9f3e" not in repr(s) and "tok-9f3e" not in str(s.model_dump())
    assert links.travelpayouts(Settings()) is None
