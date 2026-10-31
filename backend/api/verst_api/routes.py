"""The beta endpoints (ADR-0020 §2). Handlers validate, rate-limit, call the engine thread or the store, and
return the engine's JSON unchanged."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any

import anyio
from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from verst_planner import ENGINE_VERSION
from verst_planner.domain.errors import PlannerError
from verst_planner.events import NULL_SINK, CancelToken

from verst_api import links, metrics, share_page, sse, store
from verst_api.deps import DAY, Ctx, device_limit, ip_limit
from verst_api.engine import route_request
from verst_api.errors import ApiError, from_engine
from verst_api.privacy import log_point, mask_contacts, scrub_trip
from verst_api.routing import route_to_json
from verst_api.sanity import check_saved_trip, public_trip
from verst_api.schemas import (
    DeviceIn,
    DeviceOut,
    ErrorOut,
    FeedbackIn,
    FeedbackOut,
    HotelLinkQuery,
    LinkOut,
    PlanResult,
    ReadyRoutesOut,
    RouteIn,
    RouteOut,
    SavedTripOut,
    SaveTripIn,
    SharedTripOut,
    TripInputIn,
)
from verst_api.store import Device

log = logging.getLogger("verst_api.routes")
router = APIRouter()

SLUG = r"^[0-9a-hjkmnp-tv-z]{8}$"
TRIP_ID = r"^trp_[0-9a-hjkmnp-tv-z]{12}$"
ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorOut} for code in (400, 401, 404, 409, 413, 422, 429, 500, 503)
}

PlanDevice = Annotated[Device, device_limit("plan", "rate_plan_per_hour")]
RouteDevice = Annotated[Device, device_limit("route", "rate_route_per_hour")]
SaveDevice = Annotated[Device, device_limit("save", "rate_save_per_hour")]
FeedbackDevice = Annotated[Device, device_limit("feedback", "rate_feedback_per_day", DAY)]
AnyDevice = Annotated[Device, device_limit("default", "rate_default_per_hour")]
RegisterLimit = Annotated[None, ip_limit("register", "rate_register_per_hour_ip")]
PublicLimit = Annotated[None, ip_limit("public", "rate_public_per_hour_ip")]
Slug = Annotated[str, Path(pattern=SLUG)]


# ---------------------------------------------------------------------------------------------- devices


@router.post("/v1/devices", status_code=201, response_model=DeviceOut, responses=ERRORS)
async def register_device(body: DeviceIn, ctx: Ctx, _limit: RegisterLimit) -> DeviceOut:
    """ADR-0007: an anonymous device and its bearer token (shown once; the server keeps only its sha256)."""
    device_id, token = await store.create_device(ctx.pool, body.appVersion, body.locale)
    return DeviceOut(deviceId=device_id, token=token)


@router.delete("/v1/devices/me", status_code=204, responses=ERRORS)
async def forget_device(ctx: Ctx, device: AnyDevice) -> Response:
    """Security review M-2: consent withdrawn; the device, its saved trips and feedback are deleted."""
    await store.forget_device(ctx.pool, device.id)
    log.info("device forgotten")
    return Response(status_code=204)


@router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy_page(_limit: PublicLimit) -> HTMLResponse:
    """The privacy notice the app links to before «Строить на сервере» (security review B-1)."""
    return HTMLResponse(share_page.privacy(), headers=share_page.HEADERS)


# ---------------------------------------------------------------------------------------------- planning


@router.post(
    "/v1/trips/plan",
    response_model=PlanResult,
    responses={**ERRORS, 200: {"content": {"text/event-stream": {}}}},
)
async def plan_trip(body: TripInputIn, request: Request, ctx: Ctx, device: PlanDevice) -> Response:
    """Plan a trip with the server routing. `Accept: text/event-stream` streams progress (ADR-0006); the
    `done` event carries exactly the JSON body returned otherwise. Nothing is stored."""
    input_json = body.engine_json()
    log.info(
        "plan",
        extra={
            "origin": log_point(body.origin.lat, body.origin.lon),
            "destination": None
            if body.destination is None
            else log_point(body.destination.lat, body.destination.lon),
            "vias": len(body.vias or ()),
            "ready_route": body.readyRouteId,
            "sse": _wants_sse(request),
        },
    )
    engine = ctx.engine
    if _wants_sse(request):

        def start(sink: sse.LoopSink, token: CancelToken) -> Any:
            return engine.submit(lambda: engine.plan(input_json, sink, token))

        def finished(outcome: str) -> None:
            log.info("plan stream %s", outcome, extra={"outcome": outcome})

        return StreamingResponse(
            sse.stream(start, ctx.settings.plan_timeout_s, ctx.settings.sse_heartbeat_s, finished),
            media_type="text/event-stream; charset=utf-8",
            headers=sse.HEADERS,
        )
    token = CancelToken()
    future = engine.submit(lambda: engine.plan(input_json, NULL_SINK, token))
    try:
        result = await asyncio.wait_for(asyncio.wrap_future(future), ctx.settings.plan_timeout_s)
    except TimeoutError:
        token.cancel()
        raise ApiError("UPSTREAM", {"reason": "timeout"}) from None
    except PlannerError as e:
        raise from_engine(e) from e
    return JSONResponse(result)


def _wants_sse(request: Request) -> bool:
    return "text/event-stream" in request.headers.get("accept", "")


@router.post("/v1/route", response_model=RouteOut, responses=ERRORS)
async def route(body: RouteIn, ctx: Ctx, device: RouteDevice) -> Response:
    """ADR-0017 §5: the real road route for the phone's on-device plan (`PrefetchedRouting`). Never a
    road-model route: without GraphHopper the answer is 503 UPSTREAM and the phone applies its offline
    rule."""
    gh = ctx.engine.graphhopper
    if gh is None:
        metrics.ROUTE_REQUESTS.labels("not_configured").inc()
        raise ApiError("UPSTREAM", {"reason": "routing_not_configured"})
    req = route_request([(float(lat), float(lon)) for lat, lon in body.points], body.avoidTolls)
    try:
        r = await anyio.to_thread.run_sync(gh.route, req)
    except PlannerError as e:
        metrics.ROUTE_REQUESTS.labels(e.code.lower()).inc()
        raise from_engine(e) from e
    metrics.ROUTE_REQUESTS.labels("ok").inc()
    return JSONResponse(route_to_json(r))


@router.get("/v1/ready-routes", response_model=ReadyRoutesOut, responses=ERRORS)
async def ready_routes(
    ctx: Ctx,
    device: AnyDevice,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Response:
    """Ready routes whose hub town is within 50 km of the point (SPEC §7.6), as the phone lists them."""
    engine = ctx.engine
    items = await engine.call(lambda: engine.ready_routes(lat, lon, limit))
    return JSONResponse({"items": items})


# ---------------------------------------------------------------------------------------------- trips


@router.post("/v1/trips", status_code=201, response_model=SavedTripOut, responses=ERRORS)
async def save_trip(body: SaveTripIn, ctx: Ctx, device: SaveDevice) -> SavedTripOut:
    """Save a trip (planned here or on the phone) and get its share link. The server keeps only the
    privacy-reduced copy (R-07): towns instead of user points and labels, coordinates to 2 decimals."""
    raw = body.trip.model_dump(exclude_unset=True)
    check_saved_trip(raw)  # QA B-2: plausible units before anything is computed or stored
    engine = ctx.engine

    def reduce() -> tuple[dict[str, Any], str]:
        scrubbed = scrub_trip(raw, engine.town_of)
        # the cost lines and totals are the engine's, recomputed from the units, not the phone's numbers
        scrubbed["cost"] = engine.recompute_cost(scrubbed)
        return scrubbed, engine.share_text(scrubbed)  # share_text also validates the trip and its version

    scrubbed, text = await engine.call(reduce)
    start_town = str(scrubbed["input"]["origin"]["label"])
    try:
        saved = await store.save_trip(
            ctx.pool, device.id, scrubbed, text, start_town, ctx.settings.max_saved_trips
        )
    except store.LimitReached:
        raise ApiError("LIMIT_REACHED", {"limit": ctx.settings.max_saved_trips}) from None
    log.info("trip saved", extra={"km": saved.km, "days": saved.days, "synthetic": saved.synthetic})
    return SavedTripOut(
        tripId=saved.id,
        shareSlug=saved.share_slug,
        shareUrl=f"{ctx.settings.public_base_url.rstrip('/')}/s/{saved.share_slug}",
        title=saved.title,
        startTown=saved.start_town,
    )


@router.delete("/v1/trips/{trip_id}", status_code=204, responses=ERRORS)
async def delete_trip(
    ctx: Ctx, device: AnyDevice, trip_id: Annotated[str, Path(pattern=TRIP_ID)]
) -> Response:
    """Unshare: the stored copy and its link are deleted (owner only; 404 otherwise)."""
    if not await store.delete_trip(ctx.pool, device.id, trip_id):
        raise ApiError("NOT_FOUND")
    return Response(status_code=204)


@router.get("/v1/shared/{slug}", response_model=SharedTripOut, responses=ERRORS)
async def shared_trip(ctx: Ctx, _limit: PublicLimit, slug: Slug) -> SharedTripOut:
    """A shared trip for a recipient who has the app (the deep link of `/s/{slug}`)."""
    saved = await store.trip_by_slug(ctx.pool, slug)
    if saved is None:
        raise ApiError("NOT_FOUND")
    return SharedTripOut(
        title=saved.title,
        startTown=saved.start_town,
        km=saved.km,
        days=saved.days,
        approxDistances=saved.synthetic,
        shareText=saved.share_text,
        trip=public_trip(saved.trip),  # security B-3: no crew, budget, date, vehicle or engine state
    )


@router.get("/s/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def share_page_html(ctx: Ctx, _limit: PublicLimit, slug: Slug) -> HTMLResponse:
    saved = await store.trip_by_slug(ctx.pool, slug)
    if saved is None:
        return HTMLResponse(share_page.not_found(), status_code=404, headers=share_page.HEADERS)
    return HTMLResponse(share_page.render(saved), headers=share_page.HEADERS)


# ------------------------------------------------------------------------------------- feedback, links


@router.post("/v1/feedback", status_code=201, response_model=FeedbackOut, responses=ERRORS)
async def feedback(body: FeedbackIn, ctx: Ctx, device: FeedbackDevice) -> FeedbackOut:
    """A place or trip report for the curators (SPEC §9). Phone numbers and e-mails in the text are masked
    before storage, and the text is cleared after `VERST_FEEDBACK_TEXT_DAYS` (R-07 (в))."""
    if body.tripId is not None and not await store.owns_trip(ctx.pool, device.id, body.tripId):
        raise ApiError("NOT_FOUND")
    text = mask_contacts(body.text.strip()) if body.text and body.text.strip() else None
    fid = await store.add_feedback(ctx.pool, device, body.kind, body.placeId, body.tripId, text)
    log.info(
        "feedback", extra={"kind": body.kind, "has_place": body.placeId is not None, "has_text": bool(text)}
    )
    return FeedbackOut(id=fid)


@router.get("/v1/links/hotel", response_model=LinkOut, responses=ERRORS)
async def hotel_link(q: Annotated[HotelLinkQuery, Query()], ctx: Ctx, device: AnyDevice) -> LinkOut:
    """Partner link stub until LEG-02: a plain city search on Yandex Travel, `affiliate: false`."""
    engine = ctx.engine
    poi = await engine.call(lambda: engine.poi(q.placeId))
    if poi.get("kind") != "hotel":
        raise ApiError("INVALID_INPUT", {"field": "placeId", "reason": "not_a_hotel"})
    town = poi.get("townName") or poi.get("nameRu")
    url = links.hotel_search_url(str(town), q.checkin, q.nights, q.adults, q.childrenAges) if town else None
    return LinkOut(url=url, partner=links.PARTNER, affiliate=False)


# ---------------------------------------------------------------------------------------------- ops


@router.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
async def readyz(ctx: Ctx) -> Response:
    checks: dict[str, Any] = {
        "engine": ctx.engine.ready,
        "routing": ctx.engine.routing_mode,
        "catalogue": ctx.engine.catalogue_version,
    }
    try:
        await store.ping(ctx.pool)
        checks["db"] = True
    except Exception as e:  # any database failure means "not ready"
        log.warning("readyz: database %s", type(e).__name__)
        checks["db"] = False
    ok = bool(checks["engine"] and checks["db"])
    body = {"status": "ok" if ok else "unavailable", "engineVersion": ENGINE_VERSION, **checks}
    return JSONResponse(body, status_code=200 if ok else 503)


@router.get("/metrics", include_in_schema=False)
async def metrics_endpoint() -> Response:
    """Prometheus text; the proxy does not route it (private network only, infra/api/Caddyfile)."""
    return Response(metrics.render(), media_type=metrics.CONTENT_TYPE)
