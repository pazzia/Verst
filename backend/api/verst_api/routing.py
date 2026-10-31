"""Server routing (ADR-0017 §5, ADR-0020 §4): GraphHopper first; the engine's road model only when
GraphHopper is not configured (`VERST_ROUTING=road_model`) or, if `VERST_SYNTHETIC_FALLBACK=true`, when it is
down. A road-model route used as a fallback is always flagged `synthetic`, so the trip carries
`approxDistances: true`. `Unreachable` from GraphHopper is an answer, not a reason to use the *down*
fallback; but a point outside the graph's extract (CEO 31.10: the graph is one Geofabrik extract, the
catalogue covers more, e.g. towns the extract may leave out) goes to the world's own routing when `outside`
is set (`VERST_GRAPH_COVERAGE_FALLBACK`, on by default) — the same road model the phone uses, flagged
`synthetic`; if that routing refuses the point too, GraphHopper's `Unreachable` stands.

`route_to_json` is the wire shape of `POST /v1/route` (ADR-0020 §4.2), read by the phone's
`PrefetchedRouting`.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from verst_planner.domain.errors import Unreachable, UpstreamUnavailable
from verst_planner.domain.model import Route, RouteRequest
from verst_planner.ports import RoutingPort

from verst_api import metrics

log = logging.getLogger("verst_api.routing")

POINT_DECIMALS = 6  # ~0.1 m: the polyline as GraphHopper sends it, minus float noise
KM_DECIMALS = 3
MIN_DECIMALS = 2


class ServerRouting:
    """`RoutingPort` for server-side planning."""

    def __init__(
        self, primary: RoutingPort, fallback: RoutingPort | None, outside: RoutingPort | None = None
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.outside = outside

    def route(self, req: RouteRequest) -> Route:
        try:
            return self.primary.route(req)
        except Unreachable as e:
            if self.outside is None:
                raise
            try:
                r = self.outside.route(req)
            except Unreachable:
                raise e from None
            metrics.ROUTING_FALLBACK.inc()
            log.info("routing: point %s outside the graph, road model used (synthetic)", e.point_index)
            return dataclasses.replace(r, synthetic=True)
        except UpstreamUnavailable:
            if self.fallback is None:
                raise
            metrics.ROUTING_FALLBACK.inc()
            log.warning("routing: graphhopper unavailable, road model used (synthetic)")
            return dataclasses.replace(self.fallback.route(req), synthetic=True)


def route_to_json(r: Route) -> dict[str, Any]:
    """`Route` → JSON (camelCase; points as `[lat, lon]`). Exact points are returned to the device that asked
    for them and are neither stored nor logged (R-07)."""
    return {
        "points": [[round(p.lat, POINT_DECIMALS), round(p.lon, POINT_DECIMALS)] for p in r.points],
        "cumKm": [round(x, KM_DECIMALS) for x in r.cum_km],
        "cumMin": [round(x, MIN_DECIMALS) for x in r.cum_min],
        "details": [
            {
                "fromIdx": d.from_idx,
                "toIdx": d.to_idx,
                "roadClass": d.road_class.value,
                "roadRef": d.road_ref,
                "toll": d.toll,
            }
            for d in r.details
        ],
        "waypointIdx": list(r.waypoint_idx),
        "snapped": [[round(p.lat, POINT_DECIMALS), round(p.lon, POINT_DECIMALS)] for p in r.snapped],
        "kmTotal": round(r.km_total, KM_DECIMALS),
        "minTotal": round(r.min_total, MIN_DECIMALS),
        "synthetic": r.synthetic,
    }
