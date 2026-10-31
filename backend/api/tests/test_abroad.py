"""CEO 29.10 (trips abroad, server only): the plan endpoint plans into a neighbour country when the catalogues
abroad are on disk (`VERST_ABROAD_DIR`); without them it answers exactly as before."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import PLANNER, register, settings_for
from fastapi.testclient import TestClient

from verst_api.engine import Engine

MOSCOW = {"lat": 55.7558, "lon": 37.6173, "label": "Москва"}
TBILISI = {"lat": 41.7151, "lon": 44.8271, "label": "Тбилиси"}
BAKU = {"lat": 40.4093, "lon": 49.8671, "label": "Баку"}


def plan_body(destination: dict[str, Any]) -> dict[str, Any]:
    return {
        "origin": MOSCOW,
        "destination": destination,
        "crew": {"adults": 2, "children": 0, "dog": False},
        "dailyKm": 600,
    }


def _fixture_module() -> Any:
    """The planner's catalogue-abroad fixtures (`backend/planner/tests/abroad_fixture.py`), by path: both
    projects have a `tests` package."""
    spec = importlib.util.spec_from_file_location("abroad_fixture", PLANNER / "tests" / "abroad_fixture.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def abroad_client(
    migrated: str, engine: Engine, make_client: Callable[..., TestClient], tmp_path: Path
) -> Iterator[TestClient]:
    _fixture_module().write_abroad(tmp_path, ("GE", "AZ"))
    abroad = Engine(settings_for(migrated, abroad_dir=str(tmp_path)))
    abroad.load()
    assert abroad.abroad["countries"] == ["AZ", "GE"]
    try:
        yield make_client(engine_override=abroad)
    finally:
        engine.load()  # the session engine composes world_v1 again from its own settings (no data abroad)


def test_georgian_destination_is_planned_with_data_abroad(abroad_client: TestClient) -> None:
    auth = register(abroad_client)
    r = abroad_client.post("/v1/trips/plan", json=plan_body(TBILISI), headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == "plan"
    trip = body["trip"]
    assert trip["approxDistances"] is True
    stops = [s for d in trip["daysList"] for s in d["stops"]]
    border = [s for s in stops if s["kind"] == "border"]
    assert [b["border"]["crossingId"] for b in border] == ["verkhny_lars"]
    assert border[0]["border"]["unverified"] is True and border[0]["border"]["coordsApprox"] is True
    assert stops[-1]["kind"] == "finish" and stops[-1]["localTz"] == "Asia/Tbilisi"
    abroad = trip["abroad"]
    assert abroad["unverified"] is True and abroad["roubleTotalIncomplete"] is True
    ge = abroad["countries"][0]
    assert ge["code"] == "GE" and ge["fuel"]["currency"] == "GEL" and ge["fuel"]["amount"] is not None
    assert "ABROAD" in [w["code"] for w in trip["warnings"]]


def test_closed_border_is_a_clear_error(abroad_client: TestClient) -> None:
    auth = register(abroad_client)
    r = abroad_client.post("/v1/trips/plan", json=plan_body(BAKU), headers=auth)
    assert r.status_code == 400
    e = r.json()["error"]
    assert e["code"] == "INVALID_INPUT"
    assert e["details"] == {
        "field": "destination",
        "reason": "border_closed",
        "country": "AZ",
        "until": "2027-01-02T06:00:00+04:00",
    }
    assert "закрыта для легковых до 2 января 2027" in e["message"]


def test_georgian_destination_without_data_abroad(client: TestClient, auth: dict[str, str]) -> None:
    """No catalogues abroad: Tbilisi is inside the old Russia box and has no Russian town within 60 km, so it
    gets exactly what it got before (coordinator 29.10: no regression for Russia) — UNREACHABLE."""
    r = client.post("/v1/trips/plan", json=plan_body(TBILISI), headers=auth)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "UNREACHABLE"
    assert r.json()["error"]["details"] == {"pointIndex": 1}


def test_point_outside_the_box_is_unsupported(client: TestClient, auth: dict[str, str]) -> None:
    r = client.post("/v1/trips/plan", json=plan_body({"lat": 48.1, "lon": 11.6}), headers=auth)  # Munich
    assert r.status_code == 400
    e = r.json()["error"]
    assert e["details"] == {"field": "destination", "reason": "outside_supported"}
    assert e["message"].startswith("Туда пока не планируем")
