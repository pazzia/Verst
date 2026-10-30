"""SSE bridge (ADR-0006, architecture §10.4): heartbeat, time limit and cancellation on client disconnect;
the engine thread runs in the request's context."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import threading
from typing import Any

from verst_planner.domain.enums import StageKey
from verst_planner.events import CancelToken, StageEvent

from verst_api import sse
from verst_api.engine import Engine
from verst_api.logs import request_id_var


class Plan:
    """A fake engine plan on its own thread: emits one stage event, then waits until released or cancelled."""

    def __init__(self) -> None:
        self.token: CancelToken | None = None
        self.release = threading.Event()
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def start(self, sink: sse.LoopSink, token: CancelToken) -> concurrent.futures.Future[dict[str, Any]]:
        self.token = token

        def run() -> dict[str, Any]:
            sink.emit(StageEvent(StageKey.SPLIT, "Прокладываем дорогу", 0.05))
            while not self.release.wait(0.01):
                token.check()
            return {"outcome": "plan"}

        return self.pool.submit(run)


def collect(gen: Any, n: int) -> list[str]:
    async def run() -> list[str]:
        out = []
        async for chunk in gen:
            out.append(chunk)
            if len(out) == n:
                await gen.aclose()  # the client goes away
                break
        return out

    return asyncio.run(run())


def test_disconnect_cancels_the_plan() -> None:
    plan = Plan()
    outcomes: list[str] = []
    chunks = collect(sse.stream(plan.start, 30, 5, outcomes.append), 2)
    assert chunks[0] == "retry: 3000\n\n"
    assert chunks[1].startswith("event: stage\nid: 1\ndata: ")
    assert json.loads(chunks[1].split("data: ", 1)[1]) == {
        "key": "split",
        "text": "Прокладываем дорогу",
        "progress": 0.05,
    }
    assert plan.token is not None and plan.token.is_cancelled()
    assert outcomes == ["cancelled"]
    plan.pool.shutdown(wait=True)


def test_heartbeat_then_done() -> None:
    plan = Plan()
    outcomes: list[str] = []

    async def run() -> list[str]:
        out = []
        async for chunk in sse.stream(plan.start, 30, 0.05, outcomes.append):
            out.append(chunk)
            if chunk == ": ping\n\n":
                plan.release.set()
        return out

    chunks = asyncio.run(run())
    assert ": ping\n\n" in chunks
    assert chunks[-1].startswith("event: done\nid: 2\ndata: ")
    assert json.loads(chunks[-1].split("data: ", 1)[1]) == {"outcome": "plan"}
    assert outcomes == ["done"]
    plan.pool.shutdown(wait=True)


def test_time_limit_is_an_error_event_and_cancels() -> None:
    plan = Plan()
    outcomes: list[str] = []

    async def run() -> list[str]:
        return [chunk async for chunk in sse.stream(plan.start, 0.2, 0.05, outcomes.append)]

    chunks = asyncio.run(run())
    assert chunks[-1].startswith("event: error\ndata: ")
    assert json.loads(chunks[-1].split("data: ", 1)[1]) == {
        "code": "UPSTREAM",
        "message": "Сервис маршрутов временно недоступен",
        "details": {"reason": "timeout"},
    }
    assert plan.token is not None and plan.token.is_cancelled()
    assert outcomes == ["timeout"]
    plan.pool.shutdown(wait=True)


def test_engine_thread_sees_the_request_id(engine: Engine) -> None:
    token = request_id_var.set("req-engine-ctx-1")
    try:
        assert engine.submit(request_id_var.get).result() == "req-engine-ctx-1"
    finally:
        request_id_var.reset(token)
    assert engine.submit(request_id_var.get).result() is None
