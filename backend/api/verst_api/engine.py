"""The engine host (ADR-0020 §3): `verst_planner` as a library, on one dedicated thread per process.

`verst_planner.mobile` keeps module state (worlds, catalogue) and is documented as single-threaded ("every
call from one thread"), so every engine call of this process runs on `verst-engine`, a one-thread executor;
uvicorn workers (processes) give parallelism. Cancellation uses the engine's `CancelToken` from any thread.

The data is the same as the phone's: the `central_russia_v1` fixture world plus the packaged open-data
catalogue, composed as `russia_v1` by `mobile.load_catalogue()`. The server builds its own `Planner` over that
world's ports with the server routing (GraphHopper, ADR-0017) and renders results with the bridge's own
functions, so the JSON is byte-for-byte the shape of `docs/contracts/v2` (no forked serialiser).

Seams: the bridge has no public "plan with this routing" entry point yet, so three of its internal names are
used, resolved and checked once at start (`_seams`). The follow-up for the planner owner is in ADR-0020 §10.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from verst_planner import ENGINE_VERSION, mobile
from verst_planner.adapters.catalogue.world import WORLD_ID as CATALOGUE_WORLD
from verst_planner.adapters.fake import GOLDEN_CLOCK
from verst_planner.adapters.fake.clock import FixedClock
from verst_planner.adapters.graphhopper import GraphHopperRouting, GraphHopperSettings
from verst_planner.config import PlannerConfig
from verst_planner.domain import codec
from verst_planner.domain.errors import InvalidInput, PlanCancelled
from verst_planner.domain.model import LatLon, RouteRequest
from verst_planner.engine import Planner
from verst_planner.events import CancelToken, ProgressSink
from verst_planner.explain import ru
from verst_planner.explain.templates import ReasonTemplates
from verst_planner.fit import NoFit
from verst_planner.ports import Clock, RoutingPort

from verst_api import metrics
from verst_api.errors import ApiError, from_envelope
from verst_api.routing import ServerRouting
from verst_api.settings import Settings

log = logging.getLogger("verst_api.engine")

T = TypeVar("T")

BASE_WORLD = "central_russia_v1"
WORLD = CATALOGUE_WORLD  # "russia_v1": fixture world + packaged catalogue, the phone's data
PLANNER_ROOT = Path(mobile.__file__).resolve().parents[1]
WORLD_FILE = PLANNER_ROOT / "fixtures" / "worlds" / f"{BASE_WORLD}.json"
READY_ROUTE_RADIUS_KM = 50.0  # A§6.12 / SPEC §7.6: hub town within 50 km

_EXECUTOR: concurrent.futures.ThreadPoolExecutor | None = None


def executor() -> concurrent.futures.ThreadPoolExecutor:
    """The process-wide engine thread (the bridge's state is process-wide, so is its thread)."""
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="verst-engine")
    return _EXECUTOR


@dataclass(frozen=True, slots=True)
class _Seams:
    world: Any  # mobile._World of russia_v1
    trip_result: Callable[[Any, Any], dict[str, Any]]
    no_fit_result: Callable[[Any, Any], dict[str, Any]]


def _seams() -> _Seams:
    """The bridge internals this host relies on; fails at start (not mid-request) if a refactor moved them."""
    worlds = getattr(mobile, "_WORLDS", None)
    trip_result = getattr(mobile, "_trip_result", None)
    no_fit_result = getattr(mobile, "_no_fit_result", None)
    if not isinstance(worlds, dict) or not callable(trip_result) or not callable(no_fit_result):
        raise RuntimeError(
            "verst_planner.mobile changed: _WORLDS / _trip_result / _no_fit_result (ADR-0020 §10)"
        )
    w = worlds.get(WORLD)
    if w is None or not hasattr(w, "fakes") or not hasattr(w, "world"):
        raise RuntimeError(f"verst_planner.mobile: world {WORLD!r} is not loaded")
    return _Seams(w, trip_result, no_fit_result)


def _unwrap(envelope_text: str) -> Any:
    env = json.loads(envelope_text)
    if env.get("ok"):
        return env["result"]
    raise from_envelope(env.get("error") or {})


def make_clock(spec: str) -> Clock:
    if spec == "system":
        return mobile.SystemClock()
    if spec == "golden":
        return FixedClock(GOLDEN_CLOCK)
    return FixedClock(datetime.fromisoformat(spec))


def make_graphhopper(settings: Settings) -> GraphHopperRouting | None:
    if settings.routing != "graphhopper" or not settings.graphhopper_url:
        return None
    return GraphHopperRouting(
        GraphHopperSettings(base_url=settings.graphhopper_url, timeout_s=settings.graphhopper_timeout_s)
    )


class Engine:
    """Owns the server `Planner` and runs every engine call on the engine thread."""

    def __init__(self, settings: Settings, graphhopper: RoutingPort | None = None) -> None:
        self.settings = settings
        self.graphhopper = graphhopper if graphhopper is not None else make_graphhopper(settings)
        self.routing_mode = "graphhopper" if self.graphhopper is not None else "road_model"
        self._seams: _Seams | None = None
        self._planner: Planner | None = None
        self.catalogue_version: str | None = None

    # ------------------------------------------------------------------ lifecycle
    def load(self) -> None:
        """Load the worlds (once per process) and build the planner; blocks until done."""
        executor().submit(self._load).result()

    def _load(self) -> None:
        if WORLD not in _unwrap(mobile.selfcheck())["worlds"]:
            _unwrap(mobile.set_clock(self.settings.clock))
            _unwrap(mobile.load_world(WORLD_FILE.read_text("utf-8")))
            _unwrap(mobile.load_catalogue())
        check = _unwrap(mobile.selfcheck())  # also proves the time zones resolve (TZDATA_MISSING otherwise)
        self.catalogue_version = (check.get("catalogue") or {}).get("version")
        seams = _seams()
        ports = seams.world.fakes
        routing: RoutingPort = ports.routing
        if self.graphhopper is not None:
            routing = ServerRouting(
                self.graphhopper, ports.routing if self.settings.synthetic_fallback else None
            )
        self._planner = Planner(
            routing=routing,
            places=ports.places,
            prices=ports.prices,
            tolls=ports.tolls,
            regions=ports.regions,
            geocoding=ports.geocoding,
            clock=make_clock(self.settings.clock),
            config=PlannerConfig.from_dict(mobile.OPEN_DATA_CONFIG),
            templates=ReasonTemplates.default(),
            parking=getattr(ports, "parking", None),
        )
        self._seams = seams
        log.info("engine ready", extra={"engine_version": ENGINE_VERSION, "routing": self.routing_mode})

    @property
    def ready(self) -> bool:
        return self._planner is not None

    async def call(self, fn: Callable[[], T]) -> T:
        return await asyncio.wrap_future(self.submit(fn))

    def submit(self, fn: Callable[[], T]) -> concurrent.futures.Future[T]:
        """Run `fn` on the engine thread in a copy of the caller's context, so log lines written there (the
        engine, the GraphHopper adapter) carry the request id."""
        return executor().submit(contextvars.copy_context().run, fn)

    # ------------------------------------------------------------------ engine-thread functions
    def plan(self, input_json: dict[str, Any], sink: ProgressSink, token: CancelToken) -> dict[str, Any]:
        """The bridge's `plan` result (`outcome` plan | no_fit) for a trip input; raises `PlannerError`."""
        assert self._planner is not None and self._seams is not None
        token.check()  # cancelled while queued behind another plan
        try:
            trip_input = codec.input_from_json(input_json)
        except (KeyError, TypeError, ValueError) as e:
            raise InvalidInput("input", "bad_value") from e
        t0 = time.perf_counter()
        outcome = "error"
        try:
            plan = self._planner.plan(trip_input, sink, token)
            outcome = "plan"
            result = {"outcome": "plan", **self._seams.trip_result(plan, self._seams.world)}
            if plan.approx_distances:
                metrics.PLAN_SYNTHETIC.inc()
            return result
        except NoFit as nf:
            outcome = "no_fit"
            return self._seams.no_fit_result(nf, self._seams.world)
        except PlanCancelled:
            outcome = "cancelled"
            raise
        finally:
            metrics.PLAN_SECONDS.labels(outcome).observe(time.perf_counter() - t0)

    def ready_routes(self, lat: float, lon: float, limit: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = _unwrap(
            mobile.ready_routes(WORLD, lat, lon, READY_ROUTE_RADIUS_KM, limit)
        )
        return out

    def town_of(self, lat: float, lon: float) -> str:
        """The town a user point belongs to (R-07: shown instead of the point): the nearest catalogue town
        within 60 km (the bridge's `insideRussia` radius), else «Точка на карте»."""
        hit = _unwrap(mobile.geo_nearest(WORLD, lat, lon))
        town = hit.get("town")
        if town is None or not hit.get("insideRussia"):
            return ru.text("label.map_point")
        return str(town["name"])

    def share_text(self, trip: dict[str, Any]) -> str:
        """The share text of a private trip; validates it (engine version, shape) on the way."""
        return str(_unwrap(mobile.share_text(json.dumps(trip, ensure_ascii=False))))

    def poi(self, place_id: str) -> dict[str, Any]:
        out: dict[str, Any] = _unwrap(mobile.poi_details(WORLD, place_id))
        return out


def route_request(points: list[tuple[float, float]], avoid_tolls: bool) -> RouteRequest:
    try:
        return RouteRequest(tuple(LatLon(lat, lon) for lat, lon in points), avoid_tolls)
    except InvalidInput as e:
        raise ApiError("INVALID_INPUT", {"field": "points", "reason": e.reason}) from e
