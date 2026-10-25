"""Stage 10: schedule with the single re-run rule and the output rounding rules (A§6.10)."""

from __future__ import annotations

from dataclasses import dataclass, field

from verst_planner.domain.enums import Meal, Mood, WarningCode
from verst_planner.domain.model import Alternative, DayPlan, NormalizedInput, PlanWarning
from verst_planner.pipeline import Corridor, PlanContext, round_half_up
from verst_planner.pipeline import fuel as fuel_stage
from verst_planner.pipeline import rest as rest_stage
from verst_planner.pipeline import sights as sights_stage
from verst_planner.pipeline.checks import closed_sights, lunch_out_of_window, over_budget
from verst_planner.pipeline.rest import RestPool, remove_rests
from verst_planner.pipeline.timeline import Profile, Slot, day_duration_min, refresh_day_starts, schedule_day

REPAIR_GUARD = 100


@dataclass(slots=True)
class ScheduledDay:
    plan: DayPlan
    slots: list[Slot]
    budget_min: int
    over_budget: bool = False
    ids: list[str] = field(default_factory=list)  # stop ids, set by `assign_ids`
    seq0: int = 1  # global `seq` of the first stop
    alternatives: dict[int, tuple[Alternative, ...]] = field(default_factory=dict)  # stage 11, by stop index
    alternatives_note: dict[int, str] = field(default_factory=dict)  # stage 11 shortfall notes, by index

    @property
    def duration_min(self) -> float:
        return day_duration_min(self.plan, self.slots)


def _over(day: DayPlan, profile: Profile, budget: int) -> bool:
    return over_budget(day, schedule_day(day, profile), profile, budget)


def _hours_broken(day: DayPlan, profile: Profile, ctx: PlanContext) -> bool:
    return bool(closed_sights(day, schedule_day(day, profile), ctx))


def run_stages(
    days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext, frozen: bool
) -> None:
    """Stages in execution order (A§16.2): 6 fuel → 8 lunch → 9 sights → 8b lunch → 7 rests."""
    ctx.fuel_warnings = fuel_stage.plan_fuel(days, corridor, inp, ctx)
    sights_stage.plan_lunches(days, corridor, inp, ctx)
    sights_stage.plan_sights(days, corridor, inp, ctx, frozen=frozen)
    sights_stage.plan_lunch_after_sights(days, corridor, inp, ctx)
    rest_stage.plan_rests(days, corridor, inp, ctx)


def schedule_with_rerun(
    days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext
) -> tuple[list[ScheduledDay], list[PlanWarning]]:
    """Schedule; if a day is over budget, breaks hours or misses the lunch window, drop the lowest-score
    sights of the bad days, remove every auto stop and re-run the stages once (sights frozen). Then the
    final repair (A§16.5) and the over-budget rule `duration > max(budget, mandatory_min)`."""
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
            while (
                _over(d, profile, budget) or _hours_broken(d, profile, ctx)
            ) and sights_stage.droppable_sights(d):
                d.stops.pop(sights_stage.lowest_sight(d))
        for d in days:
            d.stops[:] = [s for s in d.stops if not s.auto]
        refresh_day_starts(days, profile, ctx)
        ctx.rerun += 1
        run_stages(days, corridor, inp, ctx, frozen=True)
    warnings = final_repair(days, corridor, inp, ctx)
    if refresh_day_starts(days, profile, ctx):
        refresh_day_starts(days, profile, ctx)
    out: list[ScheduledDay] = []
    for d in days:
        sd = ScheduledDay(d, schedule_day(d, profile), budget)
        if over_budget(d, sd.slots, profile, budget):
            sd.over_budget = True
            warnings.append(
                ctx.warning(
                    WarningCode.DAY_OVER_BUDGET, d.day, f"minutes={round_half_up(sd.duration_min)}", day=d.day
                )
            )
        out.append(sd)
    return out, warnings


def final_repair(
    days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext
) -> list[PlanWarning]:
    """A§16.5, one pass per day in stop order: drop sights not open for their visit (`STOP_CLOSED` for a
    fixed one), re-plan a lunch that left its window (stage 8b, once), then re-plan the day's rests. Every
    change is followed by a fresh check, so `hours_open`, `lunch_window` and `break_spacing` hold."""
    profile = ctx.profile_for(corridor.route)
    pool = RestPool.of(corridor, inp.mood is Mood.FUN, bool(ctx.cfg.sights.diversity))
    warnings: list[PlanWarning] = []
    for day in days:
        lunch_replanned = False
        rests_fresh = False
        for _guard in range(REPAIR_GUARD):
            slots = schedule_day(day, profile)
            closed = closed_sights(day, slots, ctx)
            if closed:
                s = day.stops.pop(closed[0])
                if s.fixed:
                    detail = f"place={s.place.id}" if s.place is not None else "place="
                    warnings.append(ctx.warning(WarningCode.STOP_CLOSED, day.day, detail, name=s.name_ru))
                rests_fresh = False
                continue
            if lunch_out_of_window(day, slots, ctx):
                day.stops[:] = [s for s in day.stops if s.meal is not Meal.LUNCH]
                if not lunch_replanned:
                    lunch_replanned = True
                    used = {s.place.id for d in days for s in d.stops if s.place is not None}
                    sights_stage.lunch_after_sights_day(day, corridor, inp, ctx, profile, used, pool)
                rests_fresh = False
                continue
            if not rests_fresh:
                remove_rests(day, ctx)
                used = {s.place.id for d in days for s in d.stops if s.place is not None}
                rest_stage.plan_rests_day(day, pool, used, inp, ctx, profile)
                rests_fresh = True
                continue
            break
    return warnings


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
