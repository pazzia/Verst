"""Stage 9: sights within the day's time budget and opening hours (A§6.9, SPEC §7.2 step 9), and stage 8b:
lunch for days that still have none after the sights (A§16.2).

Feasibility (`day_ok`) is evaluated on a copy of the day with its rests planned, so sights can never push
rests out of the budget (A§16.2); the budget rule is A§16.5 (`max(day_budget_min, mandatory_min)`).
"""

from __future__ import annotations

from verst_planner.domain.enums import Mood, Source, StopKind, Tag
from verst_planner.domain.model import Candidate, DayPlan, NormalizedInput, PlannedStop
from verst_planner.explain.reasons import sight_reason
from verst_planner.pipeline import Corridor, PlanContext
from verst_planner.pipeline.meals import best_lunch, lunch_candidates, needs_lunch, plan_meals
from verst_planner.pipeline.rest import RestPool, day_ok
from verst_planner.pipeline.timeline import Profile, insert_stop

NOTABLE = frozenset({Tag.KREMLIN, Tag.MONASTERY, Tag.MUSEUM, Tag.VIEW})


def sight_score(c: Candidate, inp: NormalizedInput) -> float:
    t = c.place.tags
    return (
        c.place.rating_internal
        + 0.5 * bool(NOTABLE & t)
        + 0.5 * (c.place.source is Source.CURATED)
        + 0.5 * (Tag.WALK in t and inp.crew.dog)
        + 0.5 * (Tag.PLAYGROUND in t and inp.crew.children > 0)
        - c.detour_min / 15
    )


def make_sight_stop(c: Candidate, inp: NormalizedInput, ctx: PlanContext) -> PlannedStop:
    dwell = c.place.dwell_min or ctx.cfg.dwell_min.sight_default
    key, params = sight_reason(dwell, inp.crew, c.place.source)
    return PlannedStop(
        kind=StopKind.SIGHT,
        km_at=c.km_at,
        name_ru=c.place.name_ru,
        point=c.place.point,
        place=c.place,
        detour_km=c.detour_km,
        detour_min=c.detour_min,
        dwell_min=dwell,
        score=sight_score(c, inp),
        reason_key=key,
        reason_params=params,
        region_code=c.region_code,
        pool="sight",
    )


def _used(days: list[DayPlan]) -> set[str]:
    return {s.place.id for d in days for s in d.stops if s.place is not None}


def plan_sights(
    days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext, frozen: bool = False
) -> None:
    """Add sights by score while the day stays feasible; `frozen` (the re-run) keeps the current ones."""
    if frozen or inp.simplify or inp.mood is Mood.JUST_DRIVE:
        return
    profile = ctx.profile_for(corridor.route)
    max_n = ctx.cfg.sights.max_per_day.of(inp.mood)
    used = _used(days)
    rests = RestPool.of(corridor)
    for day in days:
        n = sum(1 for s in day.stops if s.kind is StopKind.SIGHT and s.fixed)
        pool = [
            c
            for c in corridor.sights
            if day.km_start < c.km_at < day.km_end
            and c.place.id not in used
            and sight_score(c, inp) >= ctx.cfg.sights.min_score
        ]
        pool.sort(key=lambda c: (-round(sight_score(c, inp), 9), c.km_at, c.place.id))
        for c in pool:
            if n >= max_n:
                break
            if c.place.id in used:
                continue
            stop = make_sight_stop(c, inp, ctx)
            i = insert_stop(day, stop)
            if day_ok(day, inp, ctx, profile, rests, used | {c.place.id}):
                n += 1
                used.add(c.place.id)
            else:
                day.stops.pop(i)


def droppable_sights(day: DayPlan) -> list[int]:
    """Stage-9 sights (never fixed template sights, user vias or short sights used as rests)."""
    return [
        i for i, s in enumerate(day.stops) if s.kind is StopKind.SIGHT and s.pool == "sight" and not s.fixed
    ]


def lowest_sight(day: DayPlan) -> int:
    """The droppable sight with the lowest score (tie: the later one)."""
    return min(droppable_sights(day), key=lambda i: (day.stops[i].score, -day.stops[i].km_at))


def plan_lunches(days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext) -> None:
    """Stage 8 with the lunch probes checked by `day_ok` (rests reserved)."""
    profile = ctx.profile_for(corridor.route)
    rests = RestPool.of(corridor)
    used = _used(days)
    plan_meals(days, corridor, inp, ctx, ok=lambda d: day_ok(d, inp, ctx, profile, rests, used))


def lunch_after_sights_day(
    day: DayPlan,
    corridor: Corridor,
    inp: NormalizedInput,
    ctx: PlanContext,
    profile: Profile,
    used: set[str],
    rests: RestPool,
) -> None:
    """Stage 8b for one day: plan the lunch; if none fits, drop stage-9 sights (lowest score first, tie:
    later km) one at a time until a lunch fits (A§16.2). The drops are simulated on a copy first: when no
    lunch fits even with every droppable sight gone (no feasible food place on the day's corridor), the
    sights are kept and the day goes without a lunch stop (it is still costed, A§7.1)."""

    def cands(d: DayPlan) -> list[tuple[float, PlannedStop]]:
        if not needs_lunch(d, ctx, profile):
            return []
        return lunch_candidates(
            d, corridor, inp, ctx, profile, used, ok=lambda x: day_ok(x, inp, ctx, profile, rests, used)
        )

    if not needs_lunch(day, ctx, profile):
        return
    trial = DayPlan(day.day, day.km_start, day.km_end, day.start_at, list(day.stops), day.tz)
    dropped: list[PlannedStop] = []
    found = cands(trial)
    while not found and droppable_sights(trial) and needs_lunch(trial, ctx, profile):
        dropped.append(trial.stops.pop(lowest_sight(trial)))
        found = cands(trial)
    if not found:
        return
    day.stops[:] = trial.stops
    for s in dropped:
        if s.place is not None:
            used.discard(s.place.id)
    best = best_lunch(found)
    insert_stop(day, best)
    assert best.place is not None
    used.add(best.place.id)


def plan_lunch_after_sights(
    days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext
) -> None:
    """Stage 8b over every day still without a lunch that now overlaps the lunch window."""
    profile = ctx.profile_for(corridor.route)
    used = _used(days)
    rests = RestPool.of(corridor)
    for day in days:
        lunch_after_sights_day(day, corridor, inp, ctx, profile, used, rests)
