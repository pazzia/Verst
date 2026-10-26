"""Error envelope and mapping (architecture §10.6, ADR-0020 §3):
`{"error": {"code": "…", "message": "<ru>", "details": {…}}}`. Engine errors keep the details the app already
handles on the phone (`field`/`reason`, `pointIndex`, `roadKm`)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from verst_planner.domain.errors import (
    InvalidInput,
    NotFound,
    PlanCancelled,
    PlannerError,
    TooShort,
    Unreachable,
    UpstreamUnavailable,
)

log = logging.getLogger("verst_api.errors")

MESSAGES_RU: dict[str, str] = {
    "INVALID_INPUT": "Проверьте параметры поездки",
    "UNAUTHORIZED": "Перезапустите приложение",
    "NOT_FOUND": "Не нашли поездку",
    "UNREACHABLE": "Не нашли дорогу на машине до этой точки",
    "LIMIT_REACHED": "Можно сохранить до 50 поездок",
    "TOO_SHORT": "Слишком близко для поездки на машине",
    "PAYLOAD_TOO_LARGE": "Слишком большой запрос",
    "RATE_LIMITED": "Слишком много запросов, подождите минуту",
    "UPSTREAM": "Сервис маршрутов временно недоступен",
    "INTERNAL": "Что-то пошло не так, попробуйте ещё раз",
}
STATUS: dict[str, int] = {
    "INVALID_INPUT": 400,
    "UNAUTHORIZED": 401,
    "NOT_FOUND": 404,
    "UNREACHABLE": 404,
    "LIMIT_REACHED": 409,
    "PAYLOAD_TOO_LARGE": 413,
    "TOO_SHORT": 422,
    "RATE_LIMITED": 429,
    "UPSTREAM": 503,
    "INTERNAL": 500,
}


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        message: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.status = STATUS[code]
        self.details = details or {}
        self.headers = headers or {}
        self.message = message or MESSAGES_RU[code]

    def body(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


def from_engine(e: PlannerError) -> ApiError:
    """A planner exception → the HTTP error (the same codes the phone's bridge reports, §10.6)."""
    if isinstance(e, InvalidInput):
        return ApiError("INVALID_INPUT", {"field": e.field, "reason": e.reason})
    if isinstance(e, Unreachable):
        return ApiError("UNREACHABLE", {"pointIndex": e.point_index})
    if isinstance(e, TooShort):
        return ApiError("TOO_SHORT", {"roadKm": e.road_km})
    if isinstance(e, UpstreamUnavailable):
        return ApiError("UPSTREAM", {"service": e.service})
    if isinstance(e, NotFound):
        return ApiError("NOT_FOUND", {"entity": e.entity})
    if isinstance(e, PlanCancelled):
        return ApiError("UPSTREAM", {"reason": "timeout"})
    return ApiError("INTERNAL")


def from_envelope(error: dict[str, Any]) -> ApiError:
    """An error from a `verst_planner.mobile` envelope (`{"code", "field", "reason", "pointIndex", …}`)."""
    code = str(error.get("code"))
    if code == "INVALID_INPUT":
        return ApiError("INVALID_INPUT", {"field": error.get("field"), "reason": error.get("reason")})
    if code == "TRIP_INCOMPATIBLE":
        return ApiError("INVALID_INPUT", {"field": "engineVersion", "reason": "incompatible"})
    if code == "NOT_FOUND":
        return ApiError("NOT_FOUND")
    if code in ("UNREACHABLE", "TOO_SHORT", "UPSTREAM"):
        key = {"UNREACHABLE": "pointIndex", "TOO_SHORT": "roadKm", "UPSTREAM": "service"}[code]
        return ApiError(code, {key: error.get(key)} if error.get(key) is not None else {})
    log.error(
        "engine error %s",
        code,
        extra={"engine_code": code, "engine_message": str(error.get("message"))[:300]},
    )
    return ApiError("INTERNAL")


def _validation_details(exc: RequestValidationError) -> dict[str, Any]:
    first = exc.errors()[0] if exc.errors() else {}
    loc = [str(x) for x in first.get("loc", ()) if x not in ("body", "query", "path", "header")]
    return {"field": ".".join(loc) or None, "reason": first.get("type")}


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(exc.body(), status_code=exc.status, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        err = ApiError("INVALID_INPUT", _validation_details(exc))
        return JSONResponse(err.body(), status_code=err.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {401: "UNAUTHORIZED", 404: "NOT_FOUND", 405: "NOT_FOUND", 413: "PAYLOAD_TOO_LARGE"}.get(
            exc.status_code, "INVALID_INPUT" if exc.status_code < 500 else "INTERNAL"
        )
        err = ApiError(code)
        return JSONResponse(err.body(), status_code=err.status)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled %s", type(exc).__name__, exc_info=exc)
        err = ApiError("INTERNAL")
        return JSONResponse(err.body(), status_code=err.status)
