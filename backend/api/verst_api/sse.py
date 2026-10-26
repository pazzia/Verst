"""SSE progress for `POST /v1/plan` (ADR-0006, architecture §10.4, ADR-0020 §3).

The engine thread emits `StageEvent` / `StopEvent` through a sink that hands them to the event loop
(`call_soon_threadsafe`); the response generator turns them into `stage` / `stop` events, a `: ping` comment
every heartbeat, then `done` (data = exactly the JSON body of the non-SSE response) or `error`
(`{code, message, details}`). The plan is cancelled (engine `CancelToken`) when the client goes away or the
time limit passes; nothing is persisted by planning, so a cancelled plan leaves no trace."""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

from verst_planner.domain.errors import PlannerError
from verst_planner.events import CancelToken, PlanEvent, event_to_json

from verst_api.errors import ApiError, from_engine

log = logging.getLogger("verst_api.sse")

HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
RETRY_MS = 3000


class LoopSink:
    """`ProgressSink` called on the engine thread; queues the event JSON on the request's event loop."""

    def __init__(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue[tuple[str, Any]]) -> None:
        self.loop = loop
        self.queue = queue

    def emit(self, event: PlanEvent) -> None:
        self.put(("event", event_to_json(event)))

    def put(self, item: tuple[str, Any]) -> None:
        with contextlib.suppress(RuntimeError):  # the loop is closed: the client is long gone
            self.loop.call_soon_threadsafe(self.queue.put_nowait, item)


def frame(event: str | None, data: Any, event_id: int | None = None) -> str:
    lines = []
    if event is not None:
        lines.append(f"event: {event}")
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append("data: " + json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines) + "\n\n"


def error_payload(e: BaseException) -> dict[str, Any]:
    if isinstance(e, ApiError):
        err = e
    elif isinstance(e, PlannerError):
        err = from_engine(e)
    else:
        log.error("plan failed: %s", type(e).__name__, exc_info=e)
        err = ApiError("INTERNAL")
    payload: dict[str, Any] = err.body()["error"]
    return payload


async def stream(
    start: Callable[[LoopSink, CancelToken], concurrent.futures.Future[dict[str, Any]]],
    timeout_s: float,
    heartbeat_s: float,
    on_finish: Callable[[str], None],
) -> AsyncIterator[str]:
    """`start(sink, token)` submits the plan to the engine thread and returns its future."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
    sink = LoopSink(loop, queue)
    token = CancelToken()
    future = start(sink, token)
    future.add_done_callback(lambda _f: sink.put(("end", None)))
    deadline = loop.time() + timeout_s
    seq = 0
    outcome = "cancelled"
    try:
        yield f"retry: {RETRY_MS}\n\n"
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                token.cancel()
                outcome = "timeout"
                yield frame("error", ApiError("UPSTREAM", {"reason": "timeout"}).body()["error"])
                return
            try:
                kind, payload = await asyncio.wait_for(queue.get(), min(heartbeat_s, remaining))
            except TimeoutError:
                yield ": ping\n\n"
                continue
            if kind == "event":
                seq += 1
                name = payload.pop("event")
                yield frame(name, payload, seq)
                continue
            exc = future.exception()
            if exc is None:
                outcome = "done"
                yield frame("done", future.result(), seq + 1)
            else:
                outcome = "error"
                yield frame("error", error_payload(exc))
            return
    finally:
        if not future.done():
            token.cancel()  # client disconnected or timed out: stop at the engine's next checkpoint
        on_finish(outcome)
