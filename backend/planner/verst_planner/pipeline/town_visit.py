"""Stage 9c: an evening (or a morning) in the overnight town (acceptance 2026-10-28, traveller V1).

The plain stages leave the overnight town empty: a day that reaches Владимир at 14:14 had no stop in Владимир,
and Суздаль was only a hotel. A day that reaches its overnight town before `town_visit.arrive_before` gets up
to `evening_max` of the town's own sights before the hotel; a later arrival gets up to `morning_max` the next
morning before the departure (the departure may wait for the opening, ≤ 90 min, as stage 9 does).

The town's sights are its own catalogue places within `town_visit.radius_km` of its centre, fetched around the
town (an anchor town 30 km off the motorway is outside the road corridor). They pass the same admission
rules as every added sight (a dog crew, the «15-minute» rule, the `sights_free` lever). Each visit is costed
as a detour from the hotel, not from the motorway: the overnight stop already carries the drive into town.
Runs only with `town_visit.on` (the open-data world).
"""

from __future__ import annotations

from datetime import time

from verst_planner.domain.enums import PlaceType, RoadClass, StopKind
from verst_planner.domain.model import Candidate, DayPlan, NormalizedInput, Place, PlannedStop
from verst_planner.explain import ru
from verst_planner.geo.distance import haversine_km
from verst_planner.pipeline import Corridor, PlanContext, detour
from verst_planner.pipeline.rest import RestPool, day_ok
from verst_planner.pipeline.sights import (
    diversity_ok,
    dog_closed,
    lever_free_ok,
    make_sight_stop,
    minor_open_data,
    not_a_sight,
    open_score,
    with_later_start,
)
from verst_planner.pipeline.timeline import TOWN_POOL, Profile, insert_stop, local, schedule_day
from verst_planner.ports import CorridorQuery

SIGHTS = frozenset({PlaceType.SIGHT})


def _admitted(p: Place, inp: NormalizedInput, ctx: PlanContext) -> bool:
    if inp.crew.dog and dog_closed(p):
        return False
    if minor_open_data(p, ctx.cfg) or not_a_sight(p):
        return False
    return not (ctx.knobs.sights_free and not lever_free_ok(p, inp))


def town_candidates(
    centre_stop: PlannedStop, km_at: float, inp: NormalizedInput, ctx: PlanContext, used: set[str]
) -> list[Candidate]:
    """The overnight town's own sights as candidates at route km `km_at`, best first (quality, then the
    crew fit), with the detour from the hotel (or the town centre)."""
    town = centre_stop.town
    if town is None:
        return []
    q = CorridorQuery((town.point,), ctx.cfg.town_visit.radius_km, SIGHTS)
    base = centre_stop.place.point if centre_stop.place is not None else town.point
    out: list[Candidate] = []
    for p in ctx.ports.places.places_in_corridor(q):
        if p.id in used or p.type is not PlaceType.SIGHT or not _admitted(p, inp, ctx):
            continue
        lateral = haversine_km(base, p.point)
        dkm, dmin = detour(lateral, RoadClass.OTHER, ctx.cfg)
        out.append(Candidate(p, km_at, lateral, dkm, dmin, RoadClass.OTHER, p.region_code))
    out.sort(key=lambda c: (-open_score(c, inp, ctx.cfg), c.detour_min, c.place.id))
    return out


def _arrival_local_time(day: DayPlan, profile: Profile, ctx: PlanContext) -> time | None:
    end = day.stops[-1]
    arrive = schedule_day(day, profile)[-1].arrive
    if arrive is None:
        return None
    return local(arrive, ctx.tz_of(end.region_code, end.point)).time()


def _visit_stop(c: Candidate, key: str, inp: NormalizedInput, ctx: PlanContext) -> PlannedStop:
    stop = make_sight_stop(c, inp, ctx)
    stop.pool = TOWN_POOL
    stop.reason_key = key
    stop.reason_params = {"dwell": ru.duration_phrase(stop.dwell_min)}
    return stop


def _evening(
    day: DayPlan, inp: NormalizedInput, ctx: PlanContext, profile: Profile, rests: RestPool, used: set[str]
) -> int:
    end = day.stops[-1]
    added = 0
    for c in town_candidates(end, end.km_at, inp, ctx, used):
        if added >= ctx.cfg.town_visit.evening_max:
            break
        if not diversity_ok(day, c, bool(ctx.cfg.sights.diversity)):
            continue
        stop = _visit_stop(c, "town.evening", inp, ctx)
        i = insert_stop(day, stop)
        if day_ok(day, inp, ctx, profile, rests, used | {c.place.id}):
            used.add(c.place.id)
            added += 1
        else:
            day.stops.pop(i)
    return added


def _morning(
    day: DayPlan, inp: NormalizedInput, ctx: PlanContext, profile: Profile, rests: RestPool, used: set[str]
) -> int:
    start = day.stops[0]
    added = 0
    for c in town_candidates(start, start.km_at, inp, ctx, used):
        if added >= ctx.cfg.town_visit.morning_max:
            break
        if not diversity_ok(day, c, bool(ctx.cfg.sights.diversity)):
            continue
        stop = _visit_stop(c, "town.morning", inp, ctx)
        i = insert_stop(day, stop)
        if day_ok(day, inp, ctx, profile, rests, used | {c.place.id}) or with_later_start(
            day, stop, inp, ctx, profile, rests, used
        ):
            used.add(c.place.id)
            added += 1
        else:
            day.stops.pop(i)
    return added


def plan_town_visits(days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext) -> None:
    """Evening stops in each overnight town reached early, else a morning stop there the next day."""
    tv = ctx.cfg.town_visit
    if not tv.on or inp.simplify or len(days) < 2:
        return
    profile = ctx.profile_for(corridor.route)
    rests = RestPool.of(corridor, False, bool(ctx.cfg.sights.diversity))
    used = {s.place.id for d in days for s in d.stops if s.place is not None}
    for k, day in enumerate(days[:-1]):
        end = day.stops[-1]
        if end.kind is not StopKind.OVERNIGHT or end.town is None:
            continue
        arrive = _arrival_local_time(day, profile, ctx)
        if arrive is not None and arrive < tv.arrive_before and _evening(day, inp, ctx, profile, rests, used):
            continue
        _morning(days[k + 1], inp, ctx, profile, rests, used)
