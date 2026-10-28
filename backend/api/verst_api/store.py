"""Repository over the `api` schema (ADR-0020 §5). Every function takes the pool and runs one short
statement or transaction; no ORM. Privacy reduction happens before anything reaches this module."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

CROCKFORD = "0123456789abcdefghjkmnpqrstvwxyz"  # A§9.1 ids: Crockford base32, lower case


def crockford(n: int) -> str:
    return "".join(secrets.choice(CROCKFORD) for _ in range(n))


def new_token() -> str:
    """ADR-0007: 32 random bytes, base64url without padding (43 chars)."""
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def content_hash(trip: dict[str, Any]) -> bytes:
    return hashlib.sha256(json.dumps(trip, sort_keys=True, ensure_ascii=False).encode()).digest()


@dataclass(frozen=True, slots=True)
class Device:
    id: str
    app_version: str


@dataclass(frozen=True, slots=True)
class SavedTrip:
    id: str
    share_slug: str
    title: str
    start_town: str
    km: int
    days: int
    synthetic: bool
    trip: dict[str, Any]
    share_text: str
    created_at: datetime


# ---------------------------------------------------------------------------------------------- devices


async def create_device(pool: AsyncConnectionPool, app_version: str, locale: str) -> tuple[str, str]:
    token = new_token()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "INSERT INTO api.device (token_hash, app_version, locale) VALUES (%s, %s, %s) RETURNING id",
            (token_hash(token), app_version, locale),
        )
        row = await cur.fetchone()
    assert row is not None
    return str(row[0]), token


async def device_by_token(pool: AsyncConnectionPool, token: str) -> Device | None:
    """The live device of a token; `last_seen_at` is refreshed at most once an hour (A§10.8)."""
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT id, app_version, last_seen_at < now() - interval '1 hour' FROM api.device "
            "WHERE token_hash = %s AND revoked_at IS NULL",
            (token_hash(token),),
        )
        row = await cur.fetchone()
        if row is None:
            return None
        if row[2]:
            await conn.execute("UPDATE api.device SET last_seen_at = now() WHERE id = %s", (row[0],))
    return Device(str(row[0]), str(row[1]))


async def forget_device(pool: AsyncConnectionPool, device_id: str) -> None:
    """«Отвязать от сервера»: the device, its saved trips and its feedback go (ON DELETE CASCADE)."""
    async with pool.connection() as conn:
        await conn.execute("DELETE FROM api.device WHERE id = %s", (device_id,))


# ---------------------------------------------------------------------------------------------- rate limits


async def hit(pool: AsyncConnectionPool, key: str, window_start: datetime) -> int:
    """Count one request in the window; returns the hits so far, this one included."""
    async with pool.connection() as conn:
        cur = await conn.execute(
            "INSERT INTO api.rate_counter (key, window_start, hits) VALUES (%s, %s, 1) "
            "ON CONFLICT (key, window_start) DO UPDATE SET hits = api.rate_counter.hits + 1 RETURNING hits",
            (key, window_start),
        )
        row = await cur.fetchone()
    assert row is not None
    return int(row[0])


# ---------------------------------------------------------------------------------------------- trips


class LimitReached(Exception):
    pass


async def save_trip(
    pool: AsyncConnectionPool,
    device_id: str,
    trip: dict[str, Any],
    share_text: str,
    start_town: str,
    max_saved: int,
) -> SavedTrip:
    """Store a privacy-reduced trip; idempotent per (device, content). Raises `LimitReached`."""
    digest = content_hash(trip)
    async with pool.connection() as conn, conn.transaction():
        # serialise one device's saves so the limit check and the insert cannot interleave
        await conn.execute("SELECT 1 FROM api.device WHERE id = %s FOR UPDATE", (device_id,))
        existing = await _trip_where(conn, "device_id = %s AND content_hash = %s", (device_id, digest))
        if existing is not None:
            return existing
        cur = await conn.execute("SELECT count(*) FROM api.trip WHERE device_id = %s", (device_id,))
        row = await cur.fetchone()
        if row is not None and int(row[0]) >= max_saved:
            raise LimitReached()
        trip_id = "trp_" + crockford(12)
        slug = crockford(8)
        stored = {**trip, "id": trip_id}
        await conn.execute(
            "INSERT INTO api.trip (id, device_id, content_hash, share_slug, title, start_town, km, days, "
            "synthetic, engine_version, trip, share_text) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                trip_id,
                device_id,
                digest,
                slug,
                str(trip.get("title") or "")[:300] or start_town,
                start_town[:120],
                int(trip.get("km") or 0),
                max(1, int(trip.get("days") or 1)),
                bool(trip.get("approxDistances", False)),
                str(trip.get("engineVersion") or "")[:32],
                Jsonb(stored),
                share_text,
            ),
        )
        saved = await _trip_where(conn, "id = %s", (trip_id,))
    assert saved is not None
    return saved


_TRIP_COLS = "id, share_slug, title, start_town, km, days, synthetic, trip, share_text, created_at"


async def _trip_where(conn: Any, where: str, params: tuple[Any, ...]) -> SavedTrip | None:
    cur = await conn.execute(f"SELECT {_TRIP_COLS} FROM api.trip WHERE {where}", params)
    row = await cur.fetchone()
    return None if row is None else SavedTrip(*row)


async def trip_by_slug(pool: AsyncConnectionPool, slug: str) -> SavedTrip | None:
    async with pool.connection() as conn:
        return await _trip_where(conn, "share_slug = %s", (slug,))


async def delete_trip(pool: AsyncConnectionPool, device_id: str, trip_id: str) -> bool:
    async with pool.connection() as conn:
        cur = await conn.execute(
            "DELETE FROM api.trip WHERE id = %s AND device_id = %s", (trip_id, device_id)
        )
        return cur.rowcount == 1


async def owns_trip(pool: AsyncConnectionPool, device_id: str, trip_id: str) -> bool:
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM api.trip WHERE id = %s AND device_id = %s", (trip_id, device_id)
        )
        return await cur.fetchone() is not None


# ---------------------------------------------------------------------------------------------- feedback


async def add_feedback(
    pool: AsyncConnectionPool,
    device: Device,
    kind: str,
    place_id: str | None,
    trip_id: str | None,
    text: str | None,
) -> str:
    async with pool.connection() as conn:
        cur = await conn.execute(
            "INSERT INTO api.feedback (device_id, trip_id, place_id, kind, text, app_version) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (device.id, trip_id, place_id, kind, text, device.app_version),
        )
        row = await cur.fetchone()
    assert row is not None
    return str(row[0])


# ---------------------------------------------------------------------------------------------- housekeeping

CLEANUP_LOCK_ID = 0x5645525355


async def cleanup(pool: AsyncConnectionPool, feedback_text_days: int) -> dict[str, int]:
    """Retention (R-07): old rate counters are deleted, feedback text older than the limit is cleared.
    One worker at a time (advisory lock); a no-op returns zeros."""
    async with pool.connection() as conn:
        cur = await conn.execute("SELECT pg_try_advisory_lock(%s)", (CLEANUP_LOCK_ID,))
        row = await cur.fetchone()
        if not (row and row[0]):
            return {"rateCounters": 0, "feedbackTexts": 0}
        try:
            r1 = await conn.execute(
                "DELETE FROM api.rate_counter WHERE window_start < now() - interval '2 days'"
            )
            r2 = await conn.execute(
                "UPDATE api.feedback SET text = NULL "
                "WHERE text IS NOT NULL AND created_at < now() - make_interval(days => %s)",
                (feedback_text_days,),
            )
            return {"rateCounters": r1.rowcount, "feedbackTexts": r2.rowcount}
        finally:
            await conn.execute("SELECT pg_advisory_unlock(%s)", (CLEANUP_LOCK_ID,))


async def ping(pool: AsyncConnectionPool) -> None:
    async with pool.connection() as conn:
        await conn.execute("SELECT 1")


def is_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
    except ValueError:
        return False
    return True
