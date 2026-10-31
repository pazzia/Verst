"""`FixedClock` (A§5.2). Golden tests use 2026-10-23T09:00:00+03:00."""

from __future__ import annotations

from datetime import UTC, datetime


class FixedClock:
    def __init__(self, dt: datetime) -> None:
        if dt.tzinfo is None:
            raise ValueError("FixedClock needs an aware datetime")
        self._dt = dt.astimezone(UTC)

    def now(self) -> datetime:
        return self._dt
