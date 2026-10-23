"""Stage 8: lunch stops; dinner and breakfast are cost units only [D-5, D-6] (A§6.8)."""

from __future__ import annotations

from datetime import datetime, time

from verst_planner.domain.enums import Meal, StopKind, Tag
from verst_planner.domain.model import Candidate, DayPlan, NormalizedInput, PlannedStop, Town, TownCandidate
from verst_planner.explain import ru
from verst_planner.pipeline import Corridor, PlanContext
from verst_planner.pipeline.timeline import (
    Profile,
    Slot,
    day_end,
    eta_if_inserted,
    insert_stop,
    local,
    schedule_day,
)

PARKING = frozenset({Tag.PARKING, Tag.PARKING_GUARDED})
NEAREST_TOWN_KM = 30.0


def in_window(t: datetime, window: tuple[time, time]) -> bool:
    """`t` is naive local; the lunch window applies to its own calendar day."""
    return window[0] <= t.time() <= window[1]


def covers_lunch_window(day: DayPlan, slots: list[Slot], ctx: PlanContext) -> bool:
    """The day's driving schedule overlaps the lunch window (local to the day's start)."""
    lo, hi = ctx.cfg.lunch_window
    start = local(day.start_at, day.tz)
    end = local(day_end(slots), day.tz)
    w_lo = start.replace(hour=lo.hour, minute=lo.minute, second=0, microsecond=0)
    w_hi = start.replace(hour=hi.hour, minute=hi.minute, second=0, microsecond=0)
    return start < w_hi and end > w_lo


def lunch_score(c: Candidate, inp: NormalizedInput, eta_local: datetime, ctx: PlanContext) -> float:
    t = c.place.tags
    return (
        c.place.rating_internal
        + 2.0 * (Tag.KIDS_MENU in t and inp.crew.children > 0)
        + 1.0 * bool(PARKING & t)
        + 0.5 * (Tag.VIEW in t)
        + 0.5 * in_window(eta_local, ctx.cfg.lunch_sweet_spot)
        - c.detour_min / 5
    )


def nearest_town(c: Candidate, towns: list[TownCandidate]) -> Town | None:
    if c.place.town_id:
        for tc in towns:
            if tc.town.id == c.place.town_id:
                return tc.town
    near = [tc for tc in towns if abs(tc.km_at - c.km_at) <= NEAREST_TOWN_KM]
    if not near:
        return None
    return min(near, key=lambda tc: (abs(tc.km_at - c.km_at), tc.town.id)).town


def make_lunch_stop(
    c: Candidate, inp: NormalizedInput, ctx: PlanContext, towns: list[TownCandidate], score: float
) -> PlannedStop:
    t = c.place.tags
    params: dict[str, str | int | float] = {}
    if Tag.KIDS_MENU in t and inp.crew.children > 0:
        key = "lunch.kids"
    elif PARKING & t:
        key = "lunch.parking"
    else:
        town = nearest_town(c, towns)
        key = "lunch.default"
        params["town_prep"] = ru.prepositional(town) if town else c.place.name_ru
    return PlannedStop(
        kind=StopKind.FOOD,
        km_at=c.km_at,
        name_ru=c.place.name_ru,
        point=c.place.point,
        place=c.place,
        detour_km=c.detour_km,
        detour_min=c.detour_min,
        dwell_min=ctx.cfg.dwell_min.lunch,
        auto=True,
        score=score,
        meal=Meal.LUNCH,
        reason_key=key,
        reason_params=params,
        region_code=c.region_code,
    )


def sights_still_open(day: DayPlan, slots: list[Slot], ctx: PlanContext) -> bool:
    for s, slot in zip(day.stops, slots, strict=True):
        if s.kind is StopKind.SIGHT and s.place is not None:
            hours = ctx.hours(s.place)
            if hours is None:
                continue
            assert slot.arrive is not None and slot.depart is not None
            tz = ctx.tz_of(s.region_code, s.point)
            if not hours.covers(local(slot.arrive, tz), local(slot.depart, tz)):
                return False
    return True


def lunch_candidates(
    day: DayPlan, corridor: Corridor, inp: NormalizedInput, ctx: PlanContext, profile: Profile, used: set[str]
) -> list[tuple[float, PlannedStop]]:
    """Feasible lunch stops for `day` with their score (ETA in the window, open for the whole meal)."""
    out: list[tuple[float, PlannedStop]] = []
    for c in corridor.food:
        if not (day.km_start < c.km_at < day.km_end) or c.place.id in used:
            continue
        probe = make_lunch_stop(c, inp, ctx, corridor.towns, 0.0)
        slot, _slots = eta_if_inserted(day, probe, profile)
        assert slot.arrive is not None and slot.depart is not None
        tz = ctx.tz_of(c.region_code, c.place.point)
        arrive, depart = local(slot.arrive, tz), local(slot.depart, tz)
        if not in_window(arrive, ctx.cfg.lunch_window):
            continue
        hours = ctx.hours(c.place)
        if hours is not None and not hours.covers(arrive, depart):
            continue
        if not sights_still_open_after(day, probe, ctx, profile):
            continue
        score = lunch_score(c, inp, arrive, ctx)
        probe.score = score
        out.append((score, probe))
    return out


def sights_still_open_after(day: DayPlan, probe: PlannedStop, ctx: PlanContext, profile: Profile) -> bool:
    i = insert_stop(day, probe)
    try:
        return sights_still_open(day, schedule_day(day, profile), ctx)
    finally:
        day.stops.pop(i)


def plan_meals(days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext) -> None:
    profile = ctx.profile_for(corridor.route)
    used = {s.place.id for d in days for s in d.stops if s.place is not None}
    for day in days:
        if any(s.meal is Meal.LUNCH for s in day.stops):
            continue
        if not covers_lunch_window(day, schedule_day(day, profile), ctx):
            continue
        cands = lunch_candidates(day, corridor, inp, ctx, profile, used)
        if not cands:
            continue
        _score, best = min(
            cands, key=lambda x: (-round(x[0], 9), x[1].km_at, x[1].place.id if x[1].place else "")
        )
        insert_stop(day, best)
        if best.place is not None:
            used.add(best.place.id)
