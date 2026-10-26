"""Pure ASGI middleware (works with streaming responses): request id, access log line, HTTP metrics and the
request body limit (ADR-0020 §8).

The access line carries method, route template (never the raw path or the query string: they hold ids and
coordinates), status, latency, the device tag (8 hex chars of a hash) and the app version."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from verst_api import metrics
from verst_api.errors import ApiError
from verst_api.logs import request_id_var

log = logging.getLogger("verst_api.access")
_RID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_APP_VERSION = re.compile(r"^[0-9A-Za-z.+_-]{1,32}$")


def _header(scope: Scope, name: bytes) -> str | None:
    for k, v in scope.get("headers") or []:
        if k == name:
            return str(v.decode("latin-1"))
    return None


class RequestContext:
    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = _header(scope, b"x-request-id")
        rid = incoming if incoming and _RID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(rid)
        started = time.perf_counter()
        status = 500
        limit = self.max_body_bytes

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
                headers = list(message.get("headers") or [])
                headers.append((b"x-request-id", rid.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            replay = await _read_body(receive, limit)
            if replay is None:
                await _send_error(send_wrapper, ApiError("PAYLOAD_TOO_LARGE", {"maxBytes": limit}))
            else:
                await self.app(scope, replay, send_wrapper)
        finally:
            elapsed = time.perf_counter() - started
            route = scope.get("route")
            template = getattr(route, "path", None) or "unmatched"
            method = str(scope.get("method", ""))
            metrics.HTTP_REQUESTS.labels(template, method, str(status)).inc()
            metrics.HTTP_SECONDS.labels(template).observe(elapsed)
            state: dict[str, Any] = scope.get("state") or {}
            version = _header(scope, b"x-app-version")
            log.info(
                "%s %s %d",
                method,
                template,
                status,
                extra={
                    "method": method,
                    "route": template,
                    "status": status,
                    "latency_ms": round(elapsed * 1000, 1),
                    "device": state.get("device_tag"),
                    "app_version": version if version and _APP_VERSION.match(version) else None,
                },
            )
            request_id_var.reset(token)


async def _read_body(receive: Receive, limit: int) -> Receive | None:
    """Read the request body up to `limit` bytes (chunked or not) before the app sees it; None if larger.
    The app then receives the buffered body, and later messages (disconnect) from the client as usual."""
    chunks: list[bytes] = []
    size = 0
    while True:
        message = await receive()
        if message["type"] != "http.request":
            pending: list[Message] = [message]
            break
        body = message.get("body", b"")
        size += len(body)
        if size > limit:
            return None
        chunks.append(body)
        if not message.get("more_body", False):
            pending = []
            break
    first: list[Message] = [{"type": "http.request", "body": b"".join(chunks), "more_body": False}, *pending]

    async def replay() -> Message:
        return first.pop(0) if first else await receive()

    return replay


async def _send_error(send: Send, err: ApiError) -> None:
    body = json.dumps(err.body(), ensure_ascii=False).encode()
    await send(
        {
            "type": "http.response.start",
            "status": err.status,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})
