"""HTTP for the GraphHopper adapter: stdlib `urllib` only (ADR-0002: the planner has no dependencies)."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Protocol

READ_CHUNK = 64 * 1024
MAX_BODY_BYTES = 64 * 1024 * 1024
"""A 1 500 km route with path details is ~1-2 MB of JSON; anything near this cap is a misconfigured server."""


class TransportError(Exception):
    """No HTTP response. `connect` is True when the connection was refused before a request was sent, the only
    case the adapter retries (A§5.3.1: "1 retry on connect error only")."""

    def __init__(self, kind: str, connect: bool = False) -> None:
        super().__init__(kind)
        self.kind = kind
        self.connect = connect


class Transport(Protocol):
    def post_json(self, url: str, body: bytes, deadline: float) -> tuple[int, bytes]:
        """POST `body` as JSON; return (HTTP status, response bytes) for any status, including 4xx/5xx.
        `deadline` is a `time.monotonic()` value; raises `TransportError` when it passes or on a network
        error."""
        ...


class UrllibTransport:
    def __init__(self, user_agent: str = "VerstPlanner (+https://github.com/pazzia/verst)") -> None:
        self.user_agent = user_agent

    def post_json(self, url: str, body: bytes, deadline: float) -> tuple[int, bytes]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TransportError("timeout")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": self.user_agent,
            },
        )
        try:
            # `timeout` bounds the connect and every socket read; `_read` bounds the whole body by `deadline`.
            with urllib.request.urlopen(req, timeout=remaining) as resp:
                return resp.status, _read(resp, deadline)
        except urllib.error.HTTPError as e:
            try:
                return e.code, _read(e, deadline)
            finally:
                e.close()
        except urllib.error.URLError as e:
            reason = e.reason
            if isinstance(reason, TimeoutError):  # socket.timeout is TimeoutError since Python 3.10
                raise TransportError("timeout") from e
            refused = isinstance(reason, ConnectionRefusedError)
            raise TransportError(type(reason).__name__, connect=refused) from e
        except TimeoutError as e:
            raise TransportError("timeout") from e
        except OSError as e:  # reset / remote disconnect after the request was sent
            raise TransportError(type(e).__name__) from e


class _Readable(Protocol):
    def read(self, amt: int, /) -> bytes: ...


def _read(resp: _Readable, deadline: float) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = resp.read(READ_CHUNK)
        if not chunk:
            return b"".join(chunks)
        size += len(chunk)
        if size > MAX_BODY_BYTES:
            raise TransportError("body_too_large")
        if time.monotonic() > deadline:
            raise TransportError("timeout")
        chunks.append(chunk)
