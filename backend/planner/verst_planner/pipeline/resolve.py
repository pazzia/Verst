"""Stages 0-1: normalize the input and resolve the ordered waypoints (A§6.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from verst_planner.domain.enums import Mood, StopKind
from verst_planner.domain.errors import InvalidInput, NotFound
from verst_planner.domain.model import (
    LatLon,
    NormalizedInput,
    PlannedStop,
    PointInput,
    ReadyRoute,
    TripInput,
)
from verst_planner.explain import ru
from verst_planner.pipeline import PlanContext

MAX_VIAS = 3
MAX_PEOPLE = 8  # Manager decision OI-07: adults + children ≤ 8 seats incl. the driver
BUDGET_MIN, BUDGET_MAX = 1_000, 10_000_000
SATURDAY = 5


def in_russia(p: LatLon) -> bool:
    """Russia bounding box of A§6.2 (incl. Chukotka across the antimeridian)."""
    return 41.0 <= p.lat <= 82.0 and (19.0 <= p.lon <= 180.0 or -180.0 <= p.lon <= -168.0)


def _check_point(p: PointInput | None, name: str) -> None:
    if p is not None and not in_russia(p.point):
        raise InvalidInput(name, "outside_russia")


def next_saturday(now_local: datetime) -> datetime:
    """The next Saturday strictly after today (local date)."""
    days = (SATURDAY - now_local.weekday()) % 7 or 7
    return (now_local + timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)


def get_template(raw: TripInput, ctx: PlanContext) -> ReadyRoute | None:
    if raw.ready_route_id is None:
        return None
    if ctx.ready_route is None or ctx.ready_route.id != raw.ready_route_id:
        rr = ctx.ports.places.get_ready_route(raw.ready_route_id)
        if rr is None:
            raise NotFound("ready_route", raw.ready_route_id)
        ctx.ready_route = rr
    return ctx.ready_route


def normalize_input(raw: TripInput, ctx: PlanContext) -> NormalizedInput:
    """Stage 0: validate (`InvalidInput(field, reason)`) and resolve every default."""
    cfg = ctx.cfg
    _check_point(raw.origin, "origin")
    _check_point(raw.destination, "destination")
    for i, v in enumerate(raw.vias):
        _check_point(v, f"vias[{i}]")
    if not (150 <= raw.daily_km <= 900 and raw.daily_km % 50 == 0):
        raise InvalidInput("dailyKm", "out_of_range")
    if raw.crew.adults + raw.crew.children > MAX_PEOPLE:
        raise InvalidInput("crew", "too_many_people")
    if len(raw.vias) > MAX_VIAS:
        raise InvalidInput("vias", "too_many")
    if raw.destination is None and raw.ready_route_id is None:
        raise InvalidInput("destination", "required")
    if raw.destination is not None and raw.ready_route_id is not None:
        raise InvalidInput("destination", "conflicts_with_ready_route")
    if raw.vias and raw.ready_route_id is not None:
        raise InvalidInput("vias", "conflicts_with_ready_route")
    if raw.budget_rub is not None and not BUDGET_MIN <= raw.budget_rub <= BUDGET_MAX:
        raise InvalidInput("budget", "out_of_range")
    template = get_template(raw, ctx)

    tz = ctx.region_at(raw.origin.point).tz
    zone = ZoneInfo(tz)
    now = ctx.clock.now()
    if raw.start_at is None:
        day = next_saturday(now.astimezone(zone))
        start = day.replace(hour=cfg.day_start_first.hour, minute=cfg.day_start_first.minute)
    else:
        start = raw.start_at.replace(tzinfo=zone)
        if not now - timedelta(days=1) <= start <= now + timedelta(days=365):
            raise InvalidInput("startAt", "out_of_range")
    if raw.round_trip is not None:
        round_trip = raw.round_trip
    else:
        round_trip = template.round_trip if template is not None else False
    mood = raw.mood if raw.mood is not None else (Mood.CALM if raw.crew.children > 0 else Mood.MORE_STOPS)
    return NormalizedInput(
        origin=raw.origin,
        destination=raw.destination,
        vias=raw.vias,
        ready_route_id=raw.ready_route_id,
        round_trip=round_trip,
        crew=raw.crew,
        daily_km=raw.daily_km,
        budget_rub=raw.budget_rub,
        vehicle=raw.vehicle,
        start_at=start,
        mood=mood,
        avoid_tolls=raw.avoid_tolls,
        reserve_on=raw.reserve_on,
        simplify=raw.simplify,
        tz=tz,
    )


@dataclass(slots=True)
class Waypoint:
    point: LatLon
    label: str
    town_id: str | None = None
    place_id: str | None = None


@dataclass(slots=True)
class ResolvedPoints:
    """Ordered waypoints (origin, vias, destination [, origin]) and template fixed stops.

    `fixed_stops` are the template `stop` points as fixed SIGHT stops; `fixed_after[i]` is the index of the
    waypoint they follow (their km is assigned by projection after routing, A§6.2).
    """

    points: tuple[LatLon, ...]
    labels: tuple[str, ...]
    fixed_stops: list[PlannedStop]
    template: ReadyRoute | None
    waypoints: list[Waypoint] = field(default_factory=list)
    fixed_after: list[int] = field(default_factory=list)


def _label(p: PointInput, ctx: PlanContext) -> str:
    if p.label:
        return p.label
    found = ctx.ports.geocoding.reverse(p.point)
    return found.name_ru if found is not None else ru.text("label.map_point")


def resolve_points(inp: NormalizedInput, ctx: PlanContext) -> ResolvedPoints:
    """Stage 1: origin, vias (or the template's via towns), destination, plus origin again on round trips."""
    template = ctx.ready_route if inp.ready_route_id is not None else None
    wps: list[Waypoint] = [
        Waypoint(inp.origin.point, _label(inp.origin, ctx), inp.origin.town_id, inp.origin.place_id)
    ]
    fixed: list[PlannedStop] = []
    fixed_after: list[int] = []
    if template is not None:
        town_ids = [p.town_id for p in template.points if p.role == "via" and p.town_id]
        place_ids = [p.place_id for p in template.points if p.role == "stop" and p.place_id]
        towns = ctx.ports.places.get_towns(town_ids)
        places = ctx.ports.places.get_places(place_ids)
        for p in template.points:
            if p.role == "via" and p.town_id is not None:
                t = towns.get(p.town_id)
                if t is None:
                    raise NotFound("town", p.town_id)
                wps.append(Waypoint(t.point, t.name_ru, t.id))
            elif p.role == "stop" and p.place_id is not None:
                pl = places.get(p.place_id)
                if pl is None:
                    raise NotFound("place", p.place_id)
                fixed.append(
                    PlannedStop(
                        kind=StopKind.SIGHT,
                        km_at=-1.0,
                        name_ru=pl.name_ru,
                        point=pl.point,
                        place=pl,
                        dwell_min=pl.dwell_min or ctx.cfg.dwell_min.sight_default,
                        fixed=True,
                        reason_key="sight.default",
                        region_code=pl.region_code,
                    )
                )
                fixed_after.append(len(wps) - 1)
    else:
        for v in inp.vias:
            wps.append(Waypoint(v.point, _label(v, ctx), v.town_id, v.place_id))
        assert inp.destination is not None
        d = inp.destination
        wps.append(Waypoint(d.point, _label(d, ctx), d.town_id, d.place_id))
    if inp.round_trip:
        wps.append(Waypoint(wps[0].point, wps[0].label, wps[0].town_id, wps[0].place_id))
    return ResolvedPoints(
        points=tuple(w.point for w in wps),
        labels=tuple(w.label for w in wps),
        fixed_stops=fixed,
        template=template,
        waypoints=wps,
        fixed_after=fixed_after,
    )
