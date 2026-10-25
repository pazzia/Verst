"""Stage 3: corridor candidates with `kmAt`, lateral distance and detour (A§6.3)."""

from __future__ import annotations

from verst_planner.domain.enums import PlaceType, RoadClass, StopKind
from verst_planner.domain.errors import OpeningHoursParseError
from verst_planner.domain.model import Candidate, NormalizedInput, Place, PlannedStop, Route, TownCandidate
from verst_planner.geo.distance import haversine_km
from verst_planner.geo.index import PolylineIndex
from verst_planner.geo.polyline import douglas_peucker
from verst_planner.hours import parse
from verst_planner.pipeline import Corridor, PlanContext, detour, log
from verst_planner.pipeline.resolve import ResolvedPoints
from verst_planner.ports import CorridorQuery

PREFILTER_TOL_M = 200.0
FIXED_SEARCH_KM = 50.0
FIXED_SLACK_KM = 2.0


def _hours_ok(p: Place) -> bool:
    if p.opening_hours is None:
        return True
    try:
        parse(p.opening_hours)
    except OpeningHoursParseError:
        log.warning("hours_parse_error place=%s hours=%r", p.id, p.opening_hours)
        return False
    return True


def _candidates(
    p: Place, index: PolylineIndex, radius: float, motorway_radius: float | None, ctx: PlanContext
) -> list[Candidate]:
    out: list[Candidate] = []
    for proj in index.project_all(p.point, radius):
        limit = (
            motorway_radius
            if motorway_radius is not None and proj.road_class is RoadClass.MOTORWAY
            else radius
        )
        if proj.lateral_km > limit:
            continue
        dkm, dmin = detour(proj.lateral_km, proj.road_class, ctx.cfg)
        out.append(Candidate(p, proj.km_at, proj.lateral_km, dkm, dmin, proj.road_class, p.region_code))
    return out


def _sort(cands: list[Candidate]) -> list[Candidate]:
    return sorted(cands, key=lambda c: (c.km_at, c.place.id))


# Real catalogue (Sprint 3): the Золотое кольцо corridor held ~1 260 candidates and the trip's engineState
# grew from 30 KB to 240 KB. Per 10 km of route only the best sights and food places are kept (by rating,
# then detour); the fixture worlds never reach these caps, so G01-G13 are unchanged.
THIN_BUCKET_KM = 10.0
THIN_CAP = {PlaceType.SIGHT: 10, PlaceType.FOOD: 8}  # fixture maximum: 8 and 6


def _thin(cands: list[Candidate], cap: int | None) -> list[Candidate]:
    if cap is None:
        return cands
    by: dict[int, list[Candidate]] = {}
    for c in cands:
        by.setdefault(int(c.km_at // THIN_BUCKET_KM), []).append(c)
    out: list[Candidate] = []
    for lst in by.values():
        lst.sort(key=lambda c: (-c.place.rating_internal, c.detour_min, c.place.id, c.km_at))
        out.extend(lst[:cap])
    return out


def build_corridor(route: Route, inp: NormalizedInput, ctx: PlanContext) -> Corridor:
    cfg = ctx.cfg
    ck = cfg.corridor_km
    index = PolylineIndex(route)
    kept = douglas_peucker(route.points, route.cum_km, PREFILTER_TOL_M)
    line = tuple(route.points[i] for i in kept)
    places_port = ctx.ports.places
    radius = max(ck.sight, ck.food, ck.fuel, ck.rest)
    stop_types = frozenset({PlaceType.SIGHT, PlaceType.FOOD, PlaceType.FUEL, PlaceType.REST})
    roadside = places_port.places_in_corridor(CorridorQuery(line, radius, stop_types))
    towns = places_port.towns_in_corridor(line, ck.town)
    town_lodgings = places_port.lodgings_of_towns([t.id for t in towns])
    free_lodgings = places_port.places_in_corridor(
        CorridorQuery(line, ck.town, frozenset({PlaceType.LODGING}))
    )

    radius_by_type = {
        PlaceType.SIGHT: ck.sight,
        PlaceType.FOOD: ck.food,
        PlaceType.FUEL: ck.fuel,
        PlaceType.REST: ck.rest,
    }
    motorway = {PlaceType.FUEL: ck.fuel_motorway, PlaceType.REST: ck.rest_motorway}
    buckets: dict[PlaceType, list[Candidate]] = {t: [] for t in stop_types}
    for p in roadside:
        if p.type not in stop_types or not _hours_ok(p):
            continue
        buckets[p.type].extend(_candidates(p, index, radius_by_type[p.type], motorway.get(p.type), ctx))

    lodging_places: dict[str, Place] = {}
    for lst in town_lodgings.values():
        for p in lst:
            lodging_places[p.id] = p
    for p in free_lodgings:
        lodging_places.setdefault(p.id, p)
    lodging_radius = ck.town + ck.lodging_from_town
    lodgings: list[Candidate] = []
    for pid in sorted(lodging_places):
        lodgings.extend(_candidates(lodging_places[pid], index, lodging_radius, None, ctx))

    town_cands: list[TownCandidate] = []
    for t in towns:
        for proj in index.project_all(t.point, ck.town):
            _dkm, dmin = detour(proj.lateral_km, proj.road_class, cfg)
            own: dict[str, Candidate] = {}
            for c in lodgings:
                belongs = (
                    c.place.town_id == t.id or haversine_km(c.place.point, t.point) <= ck.lodging_from_town
                )
                if not belongs:
                    continue
                best = own.get(c.place.id)
                if best is None or abs(c.km_at - proj.km_at) < abs(best.km_at - proj.km_at):
                    own[c.place.id] = c
            town_cands.append(
                TownCandidate(t, proj.km_at, proj.lateral_km, dmin, [own[k] for k in sorted(own)])
            )
    town_cands.sort(key=lambda tc: (tc.km_at, tc.town.id))
    return Corridor(
        route=route,
        index=index,
        sights=_sort(_thin(buckets[PlaceType.SIGHT], THIN_CAP.get(PlaceType.SIGHT))),
        food=_sort(_thin(buckets[PlaceType.FOOD], THIN_CAP.get(PlaceType.FOOD))),
        fuel=_sort(buckets[PlaceType.FUEL]),
        rest=_sort(buckets[PlaceType.REST]),
        lodgings=_sort(lodgings),
        towns=town_cands,
    )


def place_fixed(
    pts: ResolvedPoints, corridor: Corridor, inp: NormalizedInput, ctx: PlanContext
) -> list[PlannedStop]:
    """User VIA stops at their waypoint km and template sights at their projection between waypoints.

    The first and last waypoints (origin, destination/origin) are the START and FINISH anchors, not here.
    Ready-route `via` points are routing waypoints only and produce no stop (A§16.3, D-21).
    """
    route = corridor.route
    wp_km = [route.cum_km[i] for i in route.waypoint_idx]
    town_ids = [w.town_id for w in pts.waypoints if w.town_id]
    towns = ctx.ports.places.get_towns(town_ids) if town_ids else {}
    out: list[PlannedStop] = []
    user_vias = range(1, len(pts.waypoints) - 1) if pts.template is None else range(0)
    for i in user_vias:
        w = pts.waypoints[i]
        town = towns.get(w.town_id) if w.town_id else None
        out.append(
            PlannedStop(
                kind=StopKind.VIA,
                km_at=wp_km[i],
                name_ru=w.label,
                point=w.point,
                town=town,
                dwell_min=ctx.cfg.dwell_min.via,
                fixed=True,
                reason_key="via.user",
                region_code=town.region_code if town else ctx.region_at(w.point).code,
            )
        )
    for stop, after in zip(pts.fixed_stops, pts.fixed_after, strict=True):
        lo = wp_km[after] - FIXED_SLACK_KM
        hi = wp_km[after + 1] + FIXED_SLACK_KM if after + 1 < len(wp_km) else route.km_total
        inside = corridor.index.nearest_in_range(stop.point, FIXED_SEARCH_KM, lo, hi)
        fallback = corridor.index.nearest(stop.point, FIXED_SEARCH_KM)
        best = inside or fallback
        if best is None:
            proj_km, lateral, road_class = (
                wp_km[after],
                haversine_km(stop.point, pts.waypoints[after].point),
                RoadClass.OTHER,
            )
        else:
            proj_km, lateral, road_class = best.km_at, best.lateral_km, best.road_class
        dkm, dmin = detour(lateral, road_class, ctx.cfg)
        stop.km_at = proj_km
        stop.detour_km = dkm
        stop.detour_min = dmin
        out.append(stop)
    out.sort(key=lambda s: s.km_at)
    return out
