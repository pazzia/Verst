"""Stage 2: base route with snap re-check, too-short check and the tolls warning (A§6.2)."""

from __future__ import annotations

from verst_planner.domain.enums import WarningCode
from verst_planner.domain.errors import TooShort, Unreachable
from verst_planner.domain.model import NormalizedInput, PlanWarning, Route, RouteRequest
from verst_planner.geo.distance import haversine_km
from verst_planner.pipeline import PlanContext
from verst_planner.pipeline.resolve import ResolvedPoints


def build_base_route(pts: ResolvedPoints, inp: NormalizedInput, ctx: PlanContext) -> Route:
    route = ctx.ports.routing.route(RouteRequest(pts.points, inp.avoid_tolls))
    for i, (p, s) in enumerate(zip(pts.points, route.snapped, strict=True)):
        d = haversine_km(p, s)
        if d > ctx.cfg.snap_max_km:
            raise Unreachable(i, round(d, 3))
    limit = ctx.cfg.too_short_km * (2 if inp.round_trip else 1)
    if route.km_total < limit:
        raise TooShort(route.km_total)
    return route


def toll_warnings(route: Route, inp: NormalizedInput, ctx: PlanContext) -> list[PlanWarning]:
    """[D-13] `avoidTolls` but the route still has toll details → TOLLS_UNAVOIDABLE (tolls are costed)."""
    if inp.avoid_tolls and any(d.toll for d in route.details):
        return [ctx.warning(WarningCode.TOLLS_UNAVOIDABLE, None, "toll_detail_on_route")]
    return []
