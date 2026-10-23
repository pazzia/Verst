"""Stage 10: schedule with the single re-run rule and the output rounding rules (A§6.10)."""

from __future__ import annotations

from dataclasses import dataclass, field

from verst_planner.domain.enums import StopKind, WarningCode
from verst_planner.domain.model import Alternative, DayPlan, NormalizedInput, PlanWarning
from verst_planner.pipeline import Corridor, PlanContext, round_half_up
from verst_planner.pipeline import fuel as fuel_stage
from verst_planner.pipeline import meals as meals_stage
from verst_planner.pipeline import rest as rest_stage
from verst_planner.pipeline import sights as sights_stage
from verst_planner.pipeline.meals import sights_still_open
from verst_planner.pipeline.sights import lunch_out_of_window
from verst_planner.pipeline.timeline import Profile, Slot, day_duration_min, refresh_day_starts, schedule_day


@dataclass(slots=True)
class ScheduledDay:
    plan: DayPlan
    slots: list[Slot]
    budget_min: int
    over_budget: bool = False
    ids: list[str] = field(default_factory=list)  # stop ids, set by `assign_ids`
    seq0: int = 1  # global `seq` of the first stop
    alternatives: dict[int, tuple[Alternative, ...]] = field(default_factory=dict)  # stage 11, by stop index

    @property
    def duration_min(self) -> float:
        return day_duration_min(self.plan, self.slots)


def _over(day: DayPlan, profile: Profile, budget: int) -> bool:
    return day_duration_min(day, schedule_day(day, profile)) > budget + 1e-6


def _hours_broken(day: DayPlan, profile: Profile, ctx: PlanContext) -> bool:
    return not sights_still_open(day, schedule_day(day, profile), ctx)


def _droppable(day: DayPlan) -> list[int]:
    return [i for i, s in enumerate(day.stops) if s.kind is StopKind.SIGHT and not s.fixed and not s.auto]


def schedule_with_rerun(
    days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext
) -> tuple[list[ScheduledDay], list[PlanWarning]]:
    """Schedule; if a day is over budget, breaks hours or misses the lunch window, drop the lowest-score
    sights of the bad days, remove every auto stop and re-run stages 6-9 once (sights frozen)."""
    profile = ctx.profile_for(corridor.route)
    budget = ctx.cfg.day_budget_min.of(inp.mood)
    bad = [
        d
        for d in days
        if _over(d, profile, budget)
        or _hours_broken(d, profile, ctx)
        or lunch_out_of_window(d, schedule_day(d, profile), ctx)
    ]
    if bad:
        for d in bad:
            while (_over(d, profile, budget) or _hours_broken(d, profile, ctx)) and _droppable(d):
                idx = min(_droppable(d), key=lambda i: (d.stops[i].score, -d.stops[i].km_at))
                d.stops.pop(idx)
        for d in days:
            d.stops[:] = [s for s in d.stops if not s.auto]
        refresh_day_starts(days, profile, ctx)
        ctx.rerun += 1
        ctx.fuel_warnings = fuel_stage.plan_fuel(days, corridor, inp, ctx)
        rest_stage.plan_rests(days, corridor, inp, ctx)
        meals_stage.plan_meals(days, corridor, inp, ctx)
        sights_stage.plan_sights(days, corridor, inp, ctx, frozen=True)
    if refresh_day_starts(days, profile, ctx):
        refresh_day_starts(days, profile, ctx)
    warnings: list[PlanWarning] = []
    out: list[ScheduledDay] = []
    for d in days:
        sd = ScheduledDay(d, schedule_day(d, profile), budget)
        if sd.duration_min > budget + 1e-6:
            sd.over_budget = True
            warnings.append(
                ctx.warning(
                    WarningCode.DAY_OVER_BUDGET, d.day, f"minutes={round_half_up(sd.duration_min)}", day=d.day
                )
            )
        out.append(sd)
    return out, warnings


# ------------------------------------------------------------------------------------------- rounding


def stop_km_from_prev(days: list[DayPlan]) -> list[list[int]]:
    """`km_from_prev` per stop: round-half-up of `km_at - prev.km_at + (prev.detour_km + s.detour_km) / 2`.

    The first stop of each day is 0. A stop's detour is driven half on the way in and half on the way out.
    """
    out: list[list[int]] = []
    for d in days:
        row = [0]
        for prev, s in zip(d.stops, d.stops[1:], strict=False):
            row.append(round_half_up(s.km_at - prev.km_at + (prev.detour_km + s.detour_km) / 2))
        out.append(row)
    return out


def day_km(day: DayPlan) -> int:
    """`round(km_end - km_start + Σ detour_km of its stops)`; the trip km is the sum of day km."""
    return round_half_up(day.km_end - day.km_start + sum(s.detour_km for s in day.stops))


def drive_minutes(slots: list[Slot]) -> int:
    return round_half_up(sum(s.drive_min for s in slots))


def assign_ids(sched: list[ScheduledDay]) -> None:
    """Stop ids `d{day}s{nn}` and the global `seq` (A§4.7)."""
    seq = 1
    for sd in sched:
        sd.ids = [f"d{sd.plan.day}s{i + 1:02d}" for i in range(len(sd.plan.stops))]
        sd.seq0 = seq
        seq += len(sd.plan.stops)
