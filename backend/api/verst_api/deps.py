"""Request dependencies: the app context, device authentication (ADR-0007) and rate limits (ADR-0020 §6)."""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, Request
from psycopg_pool import AsyncConnectionPool

from verst_api import store
from verst_api.engine import Engine
from verst_api.errors import ApiError
from verst_api.privacy import device_tag, ip_key
from verst_api.settings import Settings

HOUR = 3600
DAY = 86400
_BEARER = re.compile(r"Bearer ([A-Za-z0-9_-]{43})")


@dataclass(slots=True)
class Context:
    settings: Settings
    pool: AsyncConnectionPool
    engine: Engine


def context(request: Request) -> Context:
    ctx: Context = request.app.state.ctx
    return ctx


Ctx = Annotated[Context, Depends(context)]


async def current_device(request: Request, ctx: Ctx) -> store.Device:
    m = _BEARER.fullmatch(request.headers.get("authorization", ""))
    if m is None:
        raise ApiError("UNAUTHORIZED")
    device = await store.device_by_token(ctx.pool, m.group(1))
    if device is None:
        raise ApiError("UNAUTHORIZED")
    request.state.device_tag = device_tag(device.id)  # for the access log
    return device


CurrentDevice = Annotated[store.Device, Depends(current_device)]


def client_ip(request: Request) -> str:
    """The peer address; behind the proxy uvicorn rewrites it from X-Forwarded-For (`--proxy-headers`)."""
    return request.client.host if request.client else "unknown"


async def enforce(ctx: Context, bucket: str, subject: str, limit: int, window_s: int) -> None:
    """Fixed-window counter in PostgreSQL (shared by all workers); 429 RATE_LIMITED with Retry-After."""
    now = time.time()
    start = math.floor(now / window_s) * window_s
    hits = await store.hit(ctx.pool, f"{bucket}:{subject}", datetime.fromtimestamp(start, UTC))
    if hits > limit:
        retry = max(1, math.ceil(start + window_s - now))
        raise ApiError(
            "RATE_LIMITED", {"bucket": bucket, "limit": limit}, headers={"Retry-After": str(retry)}
        )


def device_limit(bucket: str, limit_field: str, window_s: int = HOUR) -> Any:
    """A dependency: authenticate, then count the request in the device's `bucket`. `limit_field` names the
    `Settings` field that holds the limit, so tests and the VM can tune it."""

    async def dep(ctx: Ctx, device: CurrentDevice) -> store.Device:
        await enforce(ctx, bucket, device.id, _limit(ctx.settings, limit_field), window_s)
        return device

    return Depends(dep)


def ip_limit(bucket: str, limit_field: str, window_s: int = HOUR) -> Any:
    """A dependency for unauthenticated endpoints: count the request per client IP (as an HMAC)."""

    async def dep(request: Request, ctx: Ctx) -> None:
        subject = ip_key(ctx.settings.rate_key_secret, client_ip(request))
        await enforce(ctx, bucket, subject, _limit(ctx.settings, limit_field), window_s)

    return Depends(dep)


def _limit(settings: Settings, field: str) -> int:
    value = getattr(settings, field)
    if not isinstance(value, int):
        raise TypeError(f"{field} is not a rate limit")
    return value
