"""Progress events, sinks and cancellation (A§5.1, A§8.3). The planner never knows about HTTP."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Protocol

from verst_planner.domain.enums import SignType, StageKey, StopKind
from verst_planner.domain.errors import PlanCancelled


@dataclass(frozen=True, slots=True)
class StageEvent:
    key: StageKey
    text_ru: str
    progress: float  # 0..1


@dataclass(frozen=True, slots=True)
class StopEvent:
    day: int
    stop_id: str
    kind: StopKind
    sign: SignType
    name_ru: str
    km_at: int
    provisional: bool


PlanEvent = StageEvent | StopEvent


class ProgressSink(Protocol):
    def emit(self, event: PlanEvent) -> None: ...


class _NullSink:
    def emit(self, event: PlanEvent) -> None:
        return None


NULL_SINK: ProgressSink = _NullSink()


class ListSink:
    """Collects events in order (tests, CLI)."""

    def __init__(self) -> None:
        self.events: list[PlanEvent] = []
        self._lock = threading.Lock()

    def emit(self, event: PlanEvent) -> None:
        with self._lock:
            self.events.append(event)


class CancelToken:
    """Wraps `threading.Event`; `check()` raises `PlanCancelled` once `cancel()` was called."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        if self._event.is_set():
            raise PlanCancelled()


class _NeverToken(CancelToken):
    def cancel(self) -> None:
        raise RuntimeError("NEVER cannot be cancelled")


NEVER: CancelToken = _NeverToken()


def event_to_json(e: PlanEvent) -> dict[str, object]:
    """SSE `data` payloads of A§10.4 (`stage` and `stop`)."""
    if isinstance(e, StageEvent):
        return {"event": "stage", "key": e.key.value, "text": e.text_ru, "progress": e.progress}
    return {
        "event": "stop",
        "day": e.day,
        "stop": {
            "id": e.stop_id,
            "kind": e.kind.value,
            "sign": e.sign.value,
            "name": e.name_ru,
            "kmAt": e.km_at,
            "provisional": e.provisional,
        },
    }
