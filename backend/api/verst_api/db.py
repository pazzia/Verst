"""PostgreSQL access and the SQL-file migration runner (ADR-0020 §5).

Migrations are `migrations/NNNN_name.sql` with an optional `NNNN_name.down.sql`, applied in order, each in
its own transaction under an advisory lock (several workers may start at once). Applied versions are kept in
`api.schema_migration`. CLI: ``python -m verst_api.db up | down <version> | status``.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
LOCK_ID = 0x5645525354  # "VERST"
STATEMENT_TIMEOUT_MS = 3000  # architecture §10.8
_NAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    up: Path
    down: Path | None


def migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    out = []
    for p in sorted(directory.glob("*.sql")):
        m = _NAME.match(p.name)
        if m is None:
            continue  # *.down.sql
        down = p.with_name(f"{m.group(1)}_{m.group(2)}.down.sql")
        out.append(Migration(int(m.group(1)), m.group(2), p, down if down.exists() else None))
    versions = [m.version for m in out]
    if len(set(versions)) != len(versions):
        raise RuntimeError(f"duplicate migration versions in {directory}")
    return out


_BOOKKEEPING = """
CREATE SCHEMA IF NOT EXISTS api;
CREATE TABLE IF NOT EXISTS api.schema_migration (
  version     integer PRIMARY KEY,
  name        text NOT NULL,
  applied_at  timestamptz NOT NULL DEFAULT now()
);
"""


async def applied(conn: psycopg.AsyncConnection[TupleRow]) -> list[int]:
    if not await _has_table(conn):
        return []
    cur = await conn.execute("SELECT version FROM api.schema_migration ORDER BY version")
    return [int(r[0]) for r in await cur.fetchall()]


async def _has_table(conn: psycopg.AsyncConnection[TupleRow]) -> bool:
    cur = await conn.execute("SELECT to_regclass('api.schema_migration') IS NOT NULL")
    row = await cur.fetchone()
    return bool(row and row[0])


async def migrate_up(dsn: str, directory: Path = MIGRATIONS_DIR) -> list[int]:
    """Apply pending migrations; returns the versions applied now."""
    done: list[int] = []
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        await conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        try:
            await conn.execute(_BOOKKEEPING)
            have = set(await applied(conn))
            for m in migrations(directory):
                if m.version in have:
                    continue
                async with conn.transaction():
                    await conn.execute(m.up.read_text("utf-8"))
                    await conn.execute(
                        "INSERT INTO api.schema_migration (version, name) VALUES (%s, %s)",
                        (m.version, m.name),
                    )
                done.append(m.version)
        finally:
            await conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
    return done


async def migrate_down(dsn: str, to_version: int, directory: Path = MIGRATIONS_DIR) -> list[int]:
    """Revert applied migrations newer than `to_version` (0 = all), newest first."""
    done: list[int] = []
    by_version = {m.version: m for m in migrations(directory)}
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        await conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        try:
            for v in sorted(await applied(conn), reverse=True):
                if v <= to_version:
                    break
                m = by_version.get(v)
                if m is None or m.down is None:
                    raise RuntimeError(f"migration {v} has no down file")
                async with conn.transaction():
                    await conn.execute(m.down.read_text("utf-8"))
                    await conn.execute("DELETE FROM api.schema_migration WHERE version = %s", (v,))
                done.append(v)
        finally:
            await conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
    return done


async def _configure(conn: psycopg.AsyncConnection[TupleRow]) -> None:
    await conn.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
    await conn.commit()


def make_pool(dsn: str, max_size: int) -> AsyncConnectionPool:
    return AsyncConnectionPool(
        dsn, min_size=1, max_size=max_size, open=False, configure=_configure, timeout=5.0, name="verst-api"
    )


def main(argv: Sequence[str] | None = None) -> int:
    from verst_api.settings import Settings

    p = argparse.ArgumentParser(prog="python -m verst_api.db")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("up")
    d = sub.add_parser("down")
    d.add_argument("version", type=int, help="revert migrations newer than this version (0 = all)")
    sub.add_parser("status")
    args = p.parse_args(argv)
    dsn = Settings().database_url
    if args.cmd == "up":
        print("applied:", asyncio.run(migrate_up(dsn)) or "nothing")
    elif args.cmd == "down":
        print("reverted:", asyncio.run(migrate_down(dsn, args.version)) or "nothing")
    else:

        async def status() -> list[int]:
            async with await psycopg.AsyncConnection.connect(dsn) as conn:
                return await applied(conn)

        have = asyncio.run(status())
        for m in migrations():
            print(f"{m.version:04d} {m.name}: {'applied' if m.version in have else 'pending'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
