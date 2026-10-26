"""Structured JSON logs (ADR-0020 §8): one JSON object per line on stdout, with the request id of the request
being served. Fields are whitelisted by the call sites; nothing logs query strings, bodies, tokens, labels or
exact coordinates (R-07: points are logged through `privacy.log_point`)."""

from __future__ import annotations

import json
import logging
import sys
import traceback
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from verst_api.privacy import round_coordinates

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_STD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid is not None:
            out["request_id"] = rid
        extra = {k: v for k, v in vars(record).items() if k not in _STD_ATTRS and not k.startswith("_")}
        out.update(round_coordinates(extra))  # a `lat`/`lon` passed as an extra is rounded as well
        if record.exc_info:
            out["exc"] = "".join(traceback.format_exception(*record.exc_info))[-4000:]
        return json.dumps(out, ensure_ascii=False, default=str)


def configure(level: str) -> None:
    """Route every logger (ours, uvicorn's error log, the GraphHopper adapter's) to one JSON stream. Uvicorn's
    access log is disabled in the container command: it would print query strings (coordinates)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers[:] = []
        lg.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
