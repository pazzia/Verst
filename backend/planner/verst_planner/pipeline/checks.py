"""Day feasibility checks shared by stages 7-11 (A§6.8-6.10, A§16.2, A§16.5)."""

from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING

from verst_planner.domain.enums import Meal, StopKind
from verst_planner.domain.model import DayPlan, PlannedStop
from verst_planner.pipeline.timeline import Profile, Slot, day_duration_min, day_end, local, schedule_day

if TYPE_CHECKING:
    from verst_planner.pipeline import PlanContext

EPS = 1e-6


def in_window(t: datetime, window: tuple[time, time]) -> bool:
    """`t` is naive local; the window applies to its own calendar day."""
    return window[0] <= t.time() <= window[1]


def covers_lunch_window(day: DayPlan, slots: list[Slot], ctx: PlanContext) -> bool:
    """The day's driving schedule overlaps the lunch window (local to the day's start)."""
    lo, hi = ctx.cfg.lunch_window
    start = local(day.start_at, day.tz)
    end = local(day_end(slots), day.tz)
    w_lo = start.replace(hour=lo.hour, minute=lo.minute, second=0, microsecond=0)
    w_hi = start.replace(hour=hi.hour, minute=hi.minute, second=0, microsecond=0)
    return start < w_hi and end > w_lo


def sight_open(s: PlannedStop, slot: Slot, ctx: PlanContext) -> bool:
    """A sight stop is open for its whole visit (non-sights are always fine)."""
    if s.kind is not StopKind.SIGHT or s.place is None:
        return True
    hours = ctx.hours(s.place)
    if hours is None:
        return True
    assert slot.arrive is not None and slot.depart is not None
    tz = ctx.tz_of(s.region_code, s.point)
    return hours.covers(local(slot.arrive, tz), local(slot.depart, tz))


def closed_sights(day: DayPlan, slots: list[Slot], ctx: PlanContext) -> list[int]:
    """Indices of sights not open for their whole visit."""
    return [
        i for i, (s, slot) in enumerate(zip(day.stops, slots, strict=True)) if not sight_open(s, slot, ctx)
    ]


def sights_still_open(day: DayPlan, slots: list[Slot], ctx: PlanContext) -> bool:
    return not closed_sights(day, slots, ctx)


def lunch_out_of_window(day: DayPlan, slots: list[Slot], ctx: PlanContext) -> bool:
    return any(
        s.meal is Meal.LUNCH
        and slot.arrive is not None
        and not in_window(local(slot.arrive, ctx.tz_of(s.region_code, s.point)), ctx.cfg.lunch_window)
        for s, slot in zip(day.stops, slots, strict=True)
    )


def day_valid(day: DayPlan, ctx: PlanContext, profile: Profile) -> bool:
    """Every sight open for its whole visit and the lunch (if any) inside its window."""
    slots = schedule_day(day, profile)
    return sights_still_open(day, slots, ctx) and not lunch_out_of_window(day, slots, ctx)


def mandatory_min(day: DayPlan, profile: Profile, with_fixed: bool = False) -> float:
    """A§16.5: driving of the day plus detour and dwell of its `auto` stops (fuel, coffee, rests, lunch).

    `with_fixed` also counts fixed and user stops (template sights, vias): the time budget only limits
    optional content, so the stage-9/lunch feasibility check protects them too.
    """
    drive = profile.drive(day.km_start, day.km_end)
    return drive + sum(
        s.detour_min + s.dwell_min
        for s in day.stops
        if s.auto or (with_fixed and s.fixed and s.kind not in (StopKind.START, StopKind.OVERNIGHT))
    )


def budget_limit(day: DayPlan, profile: Profile, budget_min: int, with_fixed: bool = False) -> float:
    """The duration a day may reach: `max(day_budget_min[mood], mandatory_min)` (A§16.5)."""
    return max(float(budget_min), mandatory_min(day, profile, with_fixed))


def over_budget(
    day: DayPlan, slots: list[Slot], profile: Profile, budget_min: int, with_fixed: bool = False
) -> bool:
    return day_duration_min(day, slots) > budget_limit(day, profile, budget_min, with_fixed) + EPS
