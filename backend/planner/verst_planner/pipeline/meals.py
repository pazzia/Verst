"""Stage 8: lunch stops; dinner and breakfast are cost units only [D-5, D-6] (A§6.8, A§16.2)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from verst_planner.domain.enums import Meal, StopKind, Tag
from verst_planner.domain.model import Candidate, DayPlan, NormalizedInput, PlannedStop, Town, TownCandidate
from verst_planner.explain import ru
from verst_planner.pipeline import Corridor, PlanContext
from verst_planner.pipeline.checks import (
    covers_lunch_window,
    day_valid,
    in_window,
    lunch_out_of_window,
    sights_still_open,
)
from verst_planner.pipeline.timeline import Profile, eta_if_inserted, insert_stop, local, schedule_day

PARKING = frozenset({Tag.PARKING, Tag.PARKING_GUARDED})
NEAREST_TOWN_KM = 30.0
ECONOMY_W = 4.0  # ADR-0011 `food_economy`: score points per 1 000 ₽ of the average check
ECONOMY_UNKNOWN_CHECK = 700

DayCheck = Callable[[DayPlan], bool]


def lunch_score(c: Candidate, inp: NormalizedInput, eta_local: datetime, ctx: PlanContext) -> float:
    t = c.place.tags
    economy = (
        ECONOMY_W * (c.place.avg_check_rub or ECONOMY_UNKNOWN_CHECK) / 1000 if ctx.knobs.food_economy else 0.0
    )
    return (
        c.place.rating_internal
        + 2.0 * (Tag.KIDS_MENU in t and inp.crew.children > 0)
        + 1.0 * bool(PARKING & t)
        + 0.5 * (Tag.VIEW in t)
        + 0.5 * in_window(eta_local, ctx.cfg.lunch_sweet_spot)
        - c.detour_min / 5
        - economy
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
        pool="food",
    )


def lunch_candidates(
    day: DayPlan,
    corridor: Corridor,
    inp: NormalizedInput,
    ctx: PlanContext,
    profile: Profile,
    used: set[str],
    ok: DayCheck | None = None,
) -> list[tuple[float, PlannedStop]]:
    """Feasible lunch stops for `day` with their score: ETA in the window, open for the whole meal, every
    sight still open, and `ok(day with the lunch)` (the stage-9 budget check with rests, A§16.2)."""
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
        i = insert_stop(day, probe)
        try:
            fine = day_valid(day, ctx, profile) and (ok is None or ok(day))
        finally:
            day.stops.pop(i)
        if not fine:
            continue
        score = lunch_score(c, inp, arrive, ctx)
        probe.score = score
        out.append((score, probe))
    return out


def best_lunch(cands: list[tuple[float, PlannedStop]]) -> PlannedStop:
    return min(cands, key=lambda x: (-round(x[0], 9), x[1].km_at, x[1].place.id if x[1].place else ""))[1]


def needs_lunch(day: DayPlan, ctx: PlanContext, profile: Profile) -> bool:
    if any(s.meal is Meal.LUNCH for s in day.stops):
        return False
    return covers_lunch_window(day, schedule_day(day, profile), ctx)


def plan_meals(
    days: list[DayPlan],
    corridor: Corridor,
    inp: NormalizedInput,
    ctx: PlanContext,
    ok: DayCheck | None = None,
) -> None:
    """Stage 8: one lunch per day whose schedule overlaps the lunch window (best `lunch_score`)."""
    profile = ctx.profile_for(corridor.route)
    used = {s.place.id for d in days for s in d.stops if s.place is not None}
    for day in days:
        if not needs_lunch(day, ctx, profile):
            continue
        cands = lunch_candidates(day, corridor, inp, ctx, profile, used, ok)
        if not cands:
            continue
        best = best_lunch(cands)
        insert_stop(day, best)
        if best.place is not None:
            used.add(best.place.id)


__all__ = [
    "covers_lunch_window",
    "in_window",
    "lunch_candidates",
    "lunch_out_of_window",
    "lunch_score",
    "make_lunch_stop",
    "plan_meals",
    "sights_still_open",
]
