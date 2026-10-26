"""`GraphHopperRouting`: `RoutingPort` over a self-hosted GraphHopper 11 server (ADR-0017, A§5.3.1).

One `POST {base_url}/route` per plan with the profile `car` or `car_avoid_tolls` (infra/routing/config.yml),
GeoJSON points and the path details of `mapping.DETAILS`.

- Budget: `timeout_s` (6 s, SPEC §10) for the whole call, including the one retry on a refused connection.
- Snapping: GraphHopper snaps up to ~2.5-3 km (`index.max_region_search: 8`); a waypoint snapped farther than
  `snap_max_km` (2 km, SPEC §7.2 step 1) raises `Unreachable(i, snap_km)`, as `FakeRouting` does.
- Errors: `PointNotFoundException` / `PointOutOfBoundsException` → `Unreachable(point_index)`;
  `ConnectionNotFoundException` → the legs are routed one by one to find the first unreachable point
  (`Unreachable(i + 1)`, the `FakeRouting` convention); timeouts, network errors, 5xx, any other 4xx (a
  configuration error: unknown profile or detail) and malformed bodies → `UpstreamUnavailable("graphhopper")`.
- Privacy (risk register R-07): logs carry coordinates rounded to 2 decimals (~1 km) and never the polyline;
  numbers in GraphHopper's error messages are rounded the same way before they are logged.
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from verst_planner.adapters.graphhopper.mapping import DETAILS, MappingError, to_route
from verst_planner.adapters.graphhopper.transport import Transport, TransportError, UrllibTransport
from verst_planner.domain.errors import Unreachable, UpstreamUnavailable
from verst_planner.domain.model import LatLon, Route, RouteRequest
from verst_planner.geo.distance import haversine_km

log = logging.getLogger("verst_planner.adapters.graphhopper")
log.addHandler(logging.NullHandler())  # library logger: the host (verst-api, check_routes.py) sets output

SERVICE = "graphhopper"
ENV_URL = "VERST_GRAPHHOPPER_URL"
ENV_TIMEOUT = "VERST_GRAPHHOPPER_TIMEOUT_S"
SNAP_PREVENTIONS = ("motorway", "tunnel", "bridge", "ferry")
"""Never start or end a trip on a motorway carriageway, in a tunnel, on a bridge or a ferry (upstream default
`tunnel, bridge, ferry` + `motorway`, A§5.3.1). Snapping only; the route itself may use them."""
RETRY_MIN_S = 0.5
"""A retry after a refused connection is attempted only if at least this much of the budget is left."""

_UNREACHABLE_POINT = {
    "com.graphhopper.util.exceptions.PointNotFoundException",
    "com.graphhopper.util.exceptions.PointOutOfBoundsException",
}
_NO_CONNECTION = "com.graphhopper.util.exceptions.ConnectionNotFoundException"
_NUMBER = re.compile(r"-?\d+\.\d+")


@dataclass(frozen=True, slots=True)
class GraphHopperSettings:
    base_url: str
    timeout_s: float = 6.0  # SPEC §10 "routing 6 s"
    profile: str = "car"
    profile_avoid_tolls: str = "car_avoid_tolls"
    snap_max_km: float = 2.0  # SPEC §7.2 step 1
    max_segment_km: float = 1.0  # mapping._densify

    def __post_init__(self) -> None:
        if not re.fullmatch(r"https?://[^\s/]+(/[^\s]*)?", self.base_url):
            raise ValueError(f"{ENV_URL}: expected http(s)://host[:port][/path], got {self.base_url!r}")
        if not (math.isfinite(self.timeout_s) and self.timeout_s > 0):
            raise ValueError("timeout_s must be > 0")
        if self.snap_max_km <= 0 or self.max_segment_km <= 0:
            raise ValueError("snap_max_km and max_segment_km must be > 0")

    @property
    def route_url(self) -> str:
        return self.base_url.rstrip("/") + "/route"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> GraphHopperSettings:
        """`VERST_GRAPHHOPPER_URL` (required), `VERST_GRAPHHOPPER_TIMEOUT_S` (default 6)."""
        url = env.get(ENV_URL, "").strip()
        if not url:
            raise ValueError(f"{ENV_URL} is not set")
        timeout = env.get(ENV_TIMEOUT, "").strip()
        return cls(base_url=url, timeout_s=float(timeout) if timeout else 6.0)


def rounded(p: LatLon) -> str:
    """A point for logs: 2 decimals (~1 km), the rounding the risk register R-07 asks for stored trips."""
    return f"{p.lat:.2f},{p.lon:.2f}"


def scrub(message: str) -> str:
    """GraphHopper error messages quote the request coordinates in full
    ("Cannot find point 1: 56.0501,37.145"); round every decimal number in them before logging."""
    return _NUMBER.sub(lambda m: f"{float(m.group()):.2f}", message)


def request_body(points: Sequence[LatLon], profile: str) -> dict[str, Any]:
    """The JSON body of `POST /route` (api-doc.md "HTTP POST": points are [lon, lat])."""
    return {
        "profile": profile,
        "points": [[p.lon, p.lat] for p in points],
        "snap_preventions": list(SNAP_PREVENTIONS),
        "points_encoded": False,
        "instructions": False,
        "calc_points": True,
        "details": list(DETAILS),
    }


class GraphHopperRouting:
    def __init__(self, settings: GraphHopperSettings, transport: Transport | None = None) -> None:
        self.settings = settings
        self.transport: Transport = transport or UrllibTransport()
        self.calls = 0

    @classmethod
    def from_env(cls, env: Mapping[str, str], transport: Transport | None = None) -> GraphHopperRouting:
        return cls(GraphHopperSettings.from_env(env), transport)

    # ------------------------------------------------------------------ RoutingPort
    def route(self, req: RouteRequest) -> Route:
        self.calls += 1
        if len(req.points) < 2:
            raise Unreachable(0, None)
        started = time.monotonic()
        deadline = started + self.settings.timeout_s
        profile = self.settings.profile_avoid_tolls if req.avoid_tolls else self.settings.profile
        where = f"{rounded(req.points[0])} -> {rounded(req.points[-1])}, {len(req.points)} points, {profile}"
        try:
            route = self._route(req.points, profile, deadline)
        except Unreachable as e:
            log.info("graphhopper: unreachable point %d (snap %s km): %s", e.point_index, e.snap_km, where)
            raise
        except UpstreamUnavailable:
            log.warning("graphhopper: upstream failure after %.0f ms: %s", _ms(started), where)
            raise
        log.info(
            "graphhopper: %.1f km, %.0f min, %d points in %.0f ms: %s",
            route.km_total,
            route.min_total,
            len(route.points),
            _ms(started),
            where,
        )
        return route

    # ------------------------------------------------------------------ internals
    def _route(self, points: Sequence[LatLon], profile: str, deadline: float) -> Route:
        status, payload = self._post(request_body(points, profile), deadline)
        if status == 200:
            try:
                route = to_route(payload, len(points), self.settings.max_segment_km)
            except MappingError as e:
                log.error("graphhopper: unexpected 200 body: %s", e)
                raise UpstreamUnavailable(SERVICE) from e
            self._check_snaps(points, route)
            return route
        if status == 400:
            kind, index = _error_kind(payload)
            if kind in _UNREACHABLE_POINT and index is not None and 0 <= index < len(points):
                raise Unreachable(index, None)
            if kind == _NO_CONNECTION:
                raise Unreachable(self._first_unreachable(points, profile, deadline), None)
        log.error("graphhopper: HTTP %d: %s", status, scrub(_message(payload))[:300])
        raise UpstreamUnavailable(SERVICE)

    def _post(self, body: dict[str, Any], deadline: float) -> tuple[int, Any]:
        data = json.dumps(body).encode("utf-8")
        for attempt in (1, 2):
            try:
                status, raw = self.transport.post_json(self.settings.route_url, data, deadline)
                break
            except TransportError as e:
                retry = e.connect and attempt == 1 and deadline - time.monotonic() >= RETRY_MIN_S
                log.warning("graphhopper: %s (attempt %d%s)", e.kind, attempt, ", retrying" if retry else "")
                if not retry:
                    raise UpstreamUnavailable(SERVICE) from e
        try:
            return status, json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            if status == 200:
                log.error("graphhopper: 200 with a body that is not JSON")
                raise UpstreamUnavailable(SERVICE) from None
            return status, None  # e.g. an HTML 502 page from a proxy

    def _check_snaps(self, points: Sequence[LatLon], route: Route) -> None:
        for i, (p, s) in enumerate(zip(points, route.snapped, strict=True)):
            d = haversine_km(p, s)
            if d > self.settings.snap_max_km:
                raise Unreachable(i, round(d, 3))

    def _first_unreachable(self, points: Sequence[LatLon], profile: str, deadline: float) -> int:
        """`ConnectionNotFoundException` does not say which leg failed; route the legs one by one."""
        if len(points) == 2:
            return 1
        for i in range(len(points) - 1):
            status, payload = self._post(request_body(points[i : i + 2], profile), deadline)
            if status == 200:
                continue
            kind, index = _error_kind(payload) if status == 400 else (None, None)
            if kind in _UNREACHABLE_POINT and index is not None:
                return i + index
            if kind == _NO_CONNECTION:
                return i + 1
            log.error("graphhopper: HTTP %d while locating the unreachable leg", status)
            raise UpstreamUnavailable(SERVICE)
        return len(points) - 1  # every leg alone is fine: report the finish, like a disconnected last leg


def _error_kind(payload: Any) -> tuple[str | None, int | None]:
    """(`hints[0].details`, `hints[0].point_index`) of an error body (api-doc.md "Error Output")."""
    if not isinstance(payload, dict):
        return None, None
    hints = payload.get("hints")
    if not isinstance(hints, list) or not hints or not isinstance(hints[0], dict):
        return None, None
    kind = hints[0].get("details")
    index = hints[0].get("point_index")
    return (
        kind if isinstance(kind, str) else None,
        index if isinstance(index, int) and not isinstance(index, bool) else None,
    )


def _message(payload: Any) -> str:
    if isinstance(payload, dict) and isinstance(payload.get("message"), str):
        return str(payload["message"])
    return "(no JSON message)"


def _ms(started: float) -> float:
    return (time.monotonic() - started) * 1000
