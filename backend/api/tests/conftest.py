"""Test fixtures (ADR-0020 §9).

Repository and HTTP tests run against a real PostgreSQL 16, never SQLite: the store relies on
`jsonb`, `ON CONFLICT … RETURNING`, advisory locks, `make_interval`, CHECK regexes and
`gen_random_uuid()`, and a second dialect would test a database we do not ship. No PostGIS is needed
(the `api` schema has no geometry).

- CI: a `postgres:16` service; `VERST_TEST_DATABASE_URL` points at it.
- Locally: without that variable a throwaway cluster is started from the PostgreSQL binaries (`initdb`, as
  user `postgres` when run as root), on a Unix socket only, and removed afterwards.
- `VERST_TEST_REQUIRE_PG=1` (CI) turns "no PostgreSQL" into a failure instead of a skip.
"""

from __future__ import annotations

import asyncio
import glob
import os
import shutil
import socket
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from verst_api.db import migrate_down, migrate_up
from verst_api.engine import Engine
from verst_api.main import create_app
from verst_api.settings import Settings

PLANNER = Path(__file__).resolve().parents[2] / "planner"
CONTRACTS = Path(__file__).resolve().parents[3] / "docs" / "contracts" / "v2"
GH_DATA = PLANNER / "tests" / "data" / "graphhopper"


def _pg_bin() -> Path | None:
    found = shutil.which("initdb")
    if found:
        return Path(found).parent
    candidates = sorted(glob.glob("/usr/lib/postgresql/*/bin/initdb"), reverse=True)
    return Path(candidates[0]).parent if candidates else None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _as_postgres(cmd: list[str]) -> list[str]:
    return ["runuser", "-u", "postgres", "--", *cmd] if os.geteuid() == 0 else cmd


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    url = os.environ.get("VERST_TEST_DATABASE_URL")
    if url:
        yield url
        return
    pg = _pg_bin()
    if pg is None:
        if os.environ.get("VERST_TEST_REQUIRE_PG") == "1":
            pytest.fail(
                "PostgreSQL is required (VERST_TEST_REQUIRE_PG=1): "
                "set VERST_TEST_DATABASE_URL or install the server binaries"
            )
        pytest.skip("no PostgreSQL: set VERST_TEST_DATABASE_URL or install the server binaries")
    tmp = Path(tempfile.mkdtemp(prefix="verst-api-pg-"))
    data, sock = tmp / "data", tmp / "sock"
    sock.mkdir()
    if os.geteuid() == 0:
        shutil.chown(tmp, "postgres")
        shutil.chown(sock, "postgres")
    port = _free_port()
    subprocess.run(
        _as_postgres(
            [str(pg / "initdb"), "-D", str(data), "-U", "verst", "--auth=trust", "-E", "UTF8", "--no-sync"]
        ),
        check=True,
        capture_output=True,
    )
    opts = f"-c listen_addresses='' -c unix_socket_directories={sock} -p {port} -c fsync=off"
    subprocess.run(
        _as_postgres(
            [str(pg / "pg_ctl"), "-D", str(data), "-o", opts, "-l", str(tmp / "log"), "-w", "start"]
        ),
        check=True,
        capture_output=True,
    )
    try:
        with psycopg.connect(f"host={sock} port={port} user=verst dbname=postgres", autocommit=True) as conn:
            conn.execute("CREATE DATABASE verst_test")
        yield f"postgresql://verst@/verst_test?host={sock}&port={port}"
    finally:
        subprocess.run(
            _as_postgres([str(pg / "pg_ctl"), "-D", str(data), "-m", "immediate", "stop"]), check=False
        )
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="session")
def migrated(database_url: str) -> str:
    """A clean `api` schema at the latest version (a reused CI database is reverted first)."""
    if _has_schema(database_url):
        asyncio.run(migrate_down(database_url, 0))
    asyncio.run(migrate_up(database_url))
    return database_url


def _has_schema(url: str) -> bool:
    with psycopg.connect(url) as conn:
        row = conn.execute("SELECT to_regclass('api.schema_migration') IS NOT NULL").fetchone()
        return bool(row and row[0])


# The session engine plans with no catalogues abroad, whatever backend/planner/abroad holds (the CI data lands
# there since 30.10); tests that need them build a fixture folder (test_abroad.py).
NO_ABROAD_DIR = tempfile.mkdtemp(prefix="verst-no-abroad-")


def settings_for(url: str, **overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "abroad_dir": NO_ABROAD_DIR,
        "env": "test",
        "database_url": url,
        "clock": "golden",
        "routing": "road_model",
        "migrate_on_start": False,
        "public_base_url": "https://verst.test",
        "rate_key_secret": "test-secret-test-secret-test-secret",
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture(scope="session")
def engine(migrated: str) -> Engine:
    e = Engine(settings_for(migrated))
    e.load()
    return e


@pytest.fixture(scope="session")
def client(migrated: str, engine: Engine) -> Iterator[TestClient]:
    app = create_app(settings_for(migrated), engine=engine, log_setup=False)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_client(migrated: str, engine: Engine) -> Iterator[Callable[..., TestClient]]:
    """A client of an app with other settings (rate limits, routing); shares the loaded engine data."""
    opened: list[TestClient] = []

    def make(
        engine_override: Engine | None = None, raise_server_exceptions: bool = True, **overrides: Any
    ) -> TestClient:
        settings = settings_for(migrated, **overrides)
        app = create_app(settings, engine=engine_override or engine, log_setup=False)
        c = TestClient(app, raise_server_exceptions=raise_server_exceptions)
        c.__enter__()
        opened.append(c)
        return c

    yield make
    for c in opened:
        c.__exit__(None, None, None)


@pytest.fixture(autouse=True)
def clean_db(request: pytest.FixtureRequest) -> None:
    if "migrated" not in request.fixturenames:
        return
    url = request.getfixturevalue("migrated")
    with psycopg.connect(url) as conn:
        conn.execute("TRUNCATE api.rate_counter, api.feedback, api.trip, api.device")


@pytest.fixture
def db(migrated: str) -> Iterator[psycopg.Connection[Any]]:
    with psycopg.connect(migrated, autocommit=True) as conn:
        yield conn


def register(client: TestClient, version: str = "0.9.0-beta") -> dict[str, str]:
    r = client.post("/v1/devices", json={"appVersion": version, "locale": "ru-RU"})
    assert r.status_code == 201, r.text
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}", "X-App-Version": version}


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    return register(client)
