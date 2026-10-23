"""Stage 9: sights within the day's time budget and opening hours (A§6.9, SPEC §7.2 step 9)."""

from __future__ import annotations

from verst_planner.domain.enums import Meal, Mood, Source, StopKind, Tag
from verst_planner.domain.model import Candidate, DayPlan, NormalizedInput, PlannedStop
from verst_planner.explain import ru
from verst_planner.pipeline import Corridor, PlanContext
from verst_planner.pipeline.meals import in_window, sights_still_open
from verst_planner.pipeline.timeline import Profile, Slot, day_duration_min, insert_stop, local, schedule_day

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


def sight_reason(
    dwell: int, inp: NormalizedInput, source: Source
) -> tuple[str, dict[str, str | int | float]]:
    if source is Source.OSM:
        return "sight.osm", {}
    key = "sight.dog_waits" if inp.crew.dog else "sight.default"
    return key, {"dwell": ru.duration_phrase(dwell)}


def make_sight_stop(c: Candidate, inp: NormalizedInput, ctx: PlanContext) -> PlannedStop:
    dwell = c.place.dwell_min or ctx.cfg.dwell_min.sight_default
    key, params = sight_reason(dwell, inp, c.place.source)
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
    )


def day_ok(
    day: DayPlan, inp: NormalizedInput, ctx: PlanContext, profile: Profile, budget: int | None = None
) -> bool:
    """Within the time budget, every sight open for its whole visit, lunch (if any) in its window."""
    slots = schedule_day(day, profile)
    limit = budget if budget is not None else ctx.cfg.day_budget_min.of(inp.mood)
    if day_duration_min(day, slots) > limit + 1e-6:
        return False
    if not sights_still_open(day, slots, ctx):
        return False
    return not lunch_out_of_window(day, slots, ctx)


def lunch_out_of_window(day: DayPlan, slots: list[Slot], ctx: PlanContext) -> bool:
    return any(
        s.meal is Meal.LUNCH
        and slot.arrive is not None
        and not in_window(local(slot.arrive, ctx.tz_of(s.region_code, s.point)), ctx.cfg.lunch_window)
        for s, slot in zip(day.stops, slots, strict=True)
    )


def plan_sights(
    days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext, frozen: bool = False
) -> None:
    """Add sights by score while the day stays feasible; `frozen` (the re-run) keeps the current ones."""
    if frozen or inp.simplify or inp.mood is Mood.JUST_DRIVE:
        return
    profile = ctx.profile_for(corridor.route)
    max_n = ctx.cfg.sights.max_per_day.of(inp.mood)
    used = {s.place.id for d in days for s in d.stops if s.place is not None}
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
            if day_ok(day, inp, ctx, profile):
                n += 1
                used.add(c.place.id)
            else:
                day.stops.pop(i)
