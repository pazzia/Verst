"""Stage 11: up to 3 alternatives per replaceable stop within ±45 min (A§16.6 replaces A§6.11, D-19).

For a replaceable stop `s` the candidates come from the stage pool of `s` (rest pool for stage-7 stops,
food for the lunch, fuel for range fuel stops, sights for stage-9 sights). Each candidate replaces `s` at
its own km position (the order of the day may change); nothing else is re-planned. A candidate is kept
when it arrives within ±45 min of `s`, every sight of the new day is open for its visit, the lunch is in
its window, the day is not longer than `max(budget, current duration)` and (for range fuel stops) no gap
between fills exceeds the full-tank range. Each alternative carries the whole new day (`day_patch`), so a
replace is applied offline verbatim, and its `AltUnits` for the offline cost recompute.
"""

from __future__ import annotations

import dataclasses
import itertools
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from verst_planner.domain.enums import Meal, StopKind, Tag, WarningCode
from verst_planner.domain.model import (
    Alternative,
    AltUnits,
    Candidate,
    DayPlan,
    NormalizedInput,
    Place,
    PlannedStop,
    ReplaceableKinds,
    StopTime,
    TownCandidate,
)
from verst_planner.pipeline import Corridor, PlanContext, round_half_up
from verst_planner.pipeline.assemble import km_from_prev_row, render_stop
from verst_planner.pipeline.checks import in_window, lunch_out_of_window, sights_still_open
from verst_planner.pipeline.fuel import fuel_range, fuel_score
from verst_planner.pipeline.meals import lunch_score, make_lunch_stop
from verst_planner.pipeline.rest import DriveClock, is_break, make_rest_stop, rest_pool, rest_score
from verst_planner.pipeline.schedule import ScheduledDay
from verst_planner.pipeline.sights import make_sight_stop, sight_score
from verst_planner.pipeline.timeline import (
    Profile,
    Slot,
    day_duration_min,
    day_end,
    insert_index,
    local,
    local_minute,
    schedule_day,
)

POOLS = ("rest", "fuel", "food", "sight")
CLUSTER_KM = 2.0
"""A candidate this close to the replaced stop (same town) takes its slot in the day (dev-notes R-05)."""


@dataclass(slots=True)
class Pools:
    sights: list[Candidate]
    food: list[Candidate]
    fuel: list[Candidate]
    rest: list[Candidate]

    @classmethod
    def of(cls, corridor: Corridor) -> Pools:
        return cls(corridor.sights, corridor.food, corridor.fuel, rest_pool(corridor))

    def get(self, fam: str) -> list[Candidate]:
        return {"rest": self.rest, "sight": self.sights, "food": self.food, "fuel": self.fuel}[fam]


def family(s: PlannedStop) -> str | None:
    """Which stage pool a stop's alternatives come from (None: not replaceable)."""
    if s.kind not in ReplaceableKinds or s.fixed:
        return None
    if s.pool in POOLS:
        return s.pool
    return {StopKind.FUEL: "fuel", StopKind.FOOD: "food", StopKind.SIGHT: "sight"}.get(s.kind, "rest")


@dataclass(slots=True)
class Trial:
    """The day with stop `i` replaced by a candidate (`index` = the candidate's new position)."""

    stop: PlannedStop
    plan: DayPlan
    slots: list[Slot]
    index: int


def _drive_since_break(day: DayPlan, i: int, profile: Profile, min_dwell: int) -> float:
    clock = DriveClock.of(day, profile)
    b = max(k for k in range(i) if is_break(day.stops[k], min_dwell))
    return clock.t_arr[i] - clock.t_arr[b]


def make_alternative_stop(
    fam: str,
    c: Candidate,
    old: PlannedStop,
    inp: NormalizedInput,
    ctx: PlanContext,
    towns: list[TownCandidate],
) -> PlannedStop:
    """The candidate as a stop of the same stage as `old` (a rest-pool place keeps its own kind)."""
    if fam == "rest":
        return make_rest_stop(c, inp, ctx, float(ctx.cfg.rest_interval_min.of(inp.mood)))
    if fam == "sight":
        return make_sight_stop(c, inp, ctx)
    if fam == "food":
        return make_lunch_stop(c, inp, ctx, towns, 0.0)
    coffee = old.coffee and Tag.CAFE_AT_FUEL in c.place.tags
    litres = max(
        0.0,
        old.litres
        + (c.km_at - old.km_at + c.detour_km - old.detour_km) * inp.vehicle.consumption_l_per_100km / 100,
    )
    return PlannedStop(
        kind=StopKind.FUEL,
        km_at=c.km_at,
        name_ru=c.place.name_ru,
        point=c.place.point,
        place=c.place,
        detour_km=c.detour_km,
        detour_min=c.detour_min,
        dwell_min=ctx.cfg.dwell_min.fuel_coffee if coffee else ctx.cfg.dwell_min.fuel,
        auto=True,
        reason_key=old.reason_key,
        reason_params=dict(old.reason_params),
        region_code=c.region_code,
        litres=litres,
        coffee=coffee,
        pool="fuel",
    )


def trial_day(
    day: DayPlan,
    i: int,
    c: Candidate,
    inp: NormalizedInput,
    ctx: PlanContext,
    profile: Profile,
    towns: list[TownCandidate],
) -> Trial:
    """Replace stop `i` by `c` at its km position and schedule (also used by `Planner.replace_stop`)."""
    old = day.stops[i]
    fam = family(old) or "rest"
    new = make_alternative_stop(fam, c, old, inp, ctx, towns)
    rest = [*day.stops[:i], *day.stops[i + 1 :]]
    plan = DayPlan(day.day, day.km_start, day.km_end, day.start_at, rest, day.tz)
    if abs(c.km_at - old.km_at) <= CLUSTER_KM:
        # same town cluster: take the replaced stop's slot (km clamped to the neighbours, ≤ 2 km)
        j = i
        new.km_at = min(max(c.km_at, rest[i - 1].km_at), rest[i].km_at)
    else:
        j = insert_index(plan, new)
    rest.insert(j, new)
    if new.reason_key == "rest.generic":  # name the driving since the previous break at the new position
        drove = _drive_since_break(plan, j, profile, ctx.cfg.rest.break_min_dwell)
        km = new.km_at
        new = make_rest_stop(c, inp, ctx, drove)
        new.km_at = km
        rest[j] = new
    return Trial(new, plan, schedule_day(plan, profile), j)


def _covers(s: PlannedStop, slot: Slot, ctx: PlanContext) -> bool:
    if s.place is None:
        return True
    hours = ctx.hours(s.place)
    if hours is None:
        return True
    assert slot.arrive is not None and slot.depart is not None
    tz = ctx.tz_of(s.region_code, s.point)
    return hours.covers(local(slot.arrive, tz), local(slot.depart, tz))


def day_patch(trial: Trial, ids: list[str], i: int, seq0: int, ctx: PlanContext) -> tuple[StopTime, ...]:
    """Every stop of the new day in its new order; the alternative carries the replaced stop's id."""
    order = [*ids[:i], *ids[i + 1 :]]
    order.insert(trial.index, ids[i])
    row = km_from_prev_row(trial.plan.stops)
    out = []
    for k, (s, slot, sid) in enumerate(zip(trial.plan.stops, trial.slots, order, strict=True)):
        tz = ctx.tz_of(s.region_code, s.point)
        out.append(
            StopTime(
                sid,
                seq0 + k,
                None if slot.arrive is None else local_minute(slot.arrive, tz),
                None if slot.depart is None else local_minute(slot.depart, tz),
                row[k],
            )
        )
    return tuple(out)


def _shift(trial: Trial, old_slots: list[Slot], old_stops: list[PlannedStop]) -> int:
    """Display shift: the arrival change of the first stop after the replaced one in the new order."""
    if trial.index + 1 >= len(trial.plan.stops):
        return 0
    nxt = trial.plan.stops[trial.index + 1]
    k = next(n for n, s in enumerate(old_stops) if s is nxt)
    new_arr, old_arr = trial.slots[trial.index + 1].arrive, old_slots[k].arrive
    assert new_arr is not None and old_arr is not None
    return round_half_up((new_arr - old_arr).total_seconds() / 60)


def ticket_prices(p: Place) -> tuple[int, int]:
    """(adult, child) ticket as costed (A§7.1): `free_entry` or no price → 0, child falls back to adult."""
    if Tag.FREE_ENTRY in p.tags or p.ticket_adult_rub is None:
        return 0, 0
    adult = p.ticket_adult_rub
    return adult, p.ticket_child_rub if p.ticket_child_rub is not None else adult


def food_people(inp: NormalizedInput, ctx: PlanContext) -> Decimal:
    """`adults + Σ child weight` (0.5 under 7) as in the food line [D-14]."""
    crew = inp.crew
    w = ctx.cfg.cost.child_food_weight_under7
    ages = (
        crew.child_ages if crew.child_ages is not None else (ctx.cfg.cost.assumed_child_age,) * crew.children
    )
    return Decimal(crew.adults) + sum((w if a < 7 else Decimal(1) for a in ages), Decimal(0))


def lunch_check(s: PlannedStop, ctx: PlanContext) -> int:
    """A lunch stop's check: its `avg_check_rub`, else the food-line default near it (A§16.7)."""
    if s.place is not None and s.place.avg_check_rub is not None:
        return s.place.avg_check_rub
    return ctx.default_check_at(s.km_at)


def _exact_cost(s: PlannedStop, inp: NormalizedInput, ctx: PlanContext) -> Decimal:
    """Unrounded per-stop cost for `delta_rub`: tickets, the lunch for the crew; fuel stops 0 (A§16.6)."""
    if s.place is None or s.kind is StopKind.FUEL:
        return Decimal(0)
    if s.kind is StopKind.SIGHT:
        adult, child = ticket_prices(s.place)
        return Decimal(inp.crew.adults * adult + inp.crew.children * child)
    if s.meal is Meal.LUNCH:
        return food_people(inp, ctx) * lunch_check(s, ctx)
    return Decimal(0)


def _round10(x: Decimal) -> int:
    return int((x / 10).quantize(Decimal(1), ROUND_HALF_UP)) * 10


def alt_units(new: PlannedStop, old: PlannedStop, inp: NormalizedInput, ctx: PlanContext) -> AltUnits:
    """What the offline recompute needs to cost the replace (A§7.4, A§16.6)."""
    place = new.place
    assert place is not None
    adult: int | None = None
    child: int | None = None
    if new.kind is StopKind.SIGHT:
        adult, child = ticket_prices(place)
    info = ctx.region_info(new.region_code) or ctx.region_at(new.point)
    return AltUnits(
        delta_km=round(new.detour_km - old.detour_km, 3),
        region_code=new.region_code,
        check_rub=lunch_check(new, ctx) if new.meal is Meal.LUNCH else None,
        adult_rub=adult,
        child_rub=child,
        name_ru=place.name_ru,
        place_id=place.id,
        price_rub=ctx.ports.prices.fuel_price(new.region_code, inp.vehicle.fuel_type).price_rub,
        region_name_ru=info.name_ru,
    )


def delta_rub(
    new: PlannedStop, old: PlannedStop, units: AltUnits, inp: NormalizedInput, ctx: PlanContext
) -> int:
    """`round_to(Δ stop cost excl. fuel stops + Δ detour_km x consumption / 100 x price(region of c), 10)`."""
    cons = Decimal(repr(inp.vehicle.consumption_l_per_100km))
    price = units.price_rub if units.price_rub is not None else Decimal(0)
    fuel = Decimal(repr(units.delta_km)) * cons / 100 * price
    return _round10(_exact_cost(new, inp, ctx) - _exact_cost(old, inp, ctx) + fuel)


def _score(fam: str, c: Candidate, trial: Trial, inp: NormalizedInput, ctx: PlanContext) -> float:
    if fam == "rest":
        return rest_score(c, inp)
    if fam == "sight":
        return sight_score(c, inp)
    if fam == "food":
        arrive = trial.slots[trial.index].arrive
        assert arrive is not None
        return lunch_score(c, inp, local(arrive, ctx.tz_of(c.region_code, c.place.point)), ctx)
    return fuel_score(c, [trial.plan], ctx)


def alternatives_for_day(
    sd: ScheduledDay,
    pools: Pools,
    used: set[str],
    inp: NormalizedInput,
    ctx: PlanContext,
    profile: Profile,
    fills: list[float] | None,
    total_km: float,
    towns: list[TownCandidate] | None = None,
) -> tuple[dict[int, tuple[Alternative, ...]], dict[int, str]]:
    """Alternatives (and shortfall notes) of each replaceable stop of a day.

    `fills`: km of the range fuel stops of the trip (None = no range check, e.g. after a FUEL_GAP).
    """
    day = sd.plan
    stops = day.stops
    slots = sd.slots
    window = ctx.cfg.alternatives.window_min
    limit = max(sd.budget_min, day_duration_min(day, slots))
    end0 = day_end(slots)
    full = fuel_range(inp.vehicle, ctx).full_km
    ids = sd.ids or [f"s{k}" for k in range(len(stops))]
    out: dict[int, tuple[Alternative, ...]] = {}
    notes: dict[int, str] = {}
    for i, old in enumerate(stops):
        fam = family(old)
        if fam is None:
            continue
        old_slot = slots[i]
        assert old_slot.arrive is not None
        reach = window + old.dwell_min + old.detour_min + 1
        probes: list[tuple[float, Trial]] = []
        for c in pools.get(fam):
            if c.place.id in used or not (day.km_start < c.km_at < day.km_end):
                continue
            if profile.drive(min(c.km_at, old.km_at), max(c.km_at, old.km_at)) > reach:
                continue
            if fam == "sight" and sight_score(c, inp) < ctx.cfg.sights.min_score:
                continue
            trial = trial_day(day, i, c, inp, ctx, profile, towns or [])
            new = trial.stop
            arrive = trial.slots[trial.index].arrive
            assert arrive is not None
            if abs((arrive - old_slot.arrive).total_seconds()) / 60 > window:
                continue
            if new.kind in (StopKind.SIGHT, StopKind.FOOD) and not _covers(
                new, trial.slots[trial.index], ctx
            ):
                continue
            if new.meal is Meal.LUNCH:
                tz = ctx.tz_of(new.region_code, new.point)
                if not in_window(local(arrive, tz), ctx.cfg.lunch_window):
                    continue
            if not sights_still_open(trial.plan, trial.slots, ctx) or lunch_out_of_window(
                trial.plan, trial.slots, ctx
            ):
                continue
            if day_duration_min(trial.plan, trial.slots) > limit + 1e-6:
                continue
            if fills is not None and fam == "fuel":
                pts = sorted([0.0, *[f for f in fills if abs(f - old.km_at) > 1e-9], c.km_at, total_km])
                if any(b - a > full + 1e-6 for a, b in itertools.pairwise(pts)):
                    continue
            probes.append((_score(fam, c, trial, inp, ctx), trial))
        probes.sort(
            key=lambda p: (-round(p[0], 9), p[1].stop.km_at, p[1].stop.place.id if p[1].stop.place else "")
        )
        alts: list[Alternative] = []
        seen: set[str] = set()
        for _score_value, t in probes:
            place = t.stop.place
            assert place is not None
            if place.id in seen:
                continue
            seen.add(place.id)
            row = km_from_prev_row(t.plan.stops)
            rendered = render_stop(
                t.stop,
                t.slots[t.index],
                day.day,
                t.index,
                sd.seq0 + t.index,
                row[t.index],
                inp,
                ctx,
                sid=ids[i],
            )
            units = alt_units(t.stop, old, inp, ctx)
            alts.append(
                Alternative(
                    id=f"alt_{rendered.id}_{place.id}",
                    place_id=place.id,
                    name_ru=place.name_ru,
                    delta_min=round_half_up((day_end(t.slots) - end0).total_seconds() / 60),
                    delta_rub=delta_rub(t.stop, old, units, inp, ctx),
                    shift_min=_shift(t, slots, stops),
                    stop=dataclasses.replace(rendered, alternatives=()),
                    units=units,
                    day_patch=day_patch(t, ids, i, sd.seq0, ctx),
                )
            )
            if len(alts) == ctx.cfg.alternatives.max:
                break
        out[i] = tuple(alts)
        if len(alts) < 2:
            notes[i] = ctx.templates.render("alternatives.one" if alts else "alternatives.none")
    return out, notes


def fuel_fills(sched: list[ScheduledDay], ctx: PlanContext) -> list[float] | None:
    """Range fuel stop km over the whole trip; None when a FUEL_GAP made the range check meaningless."""
    if any(w.code is WarningCode.FUEL_GAP for w in ctx.fuel_warnings):
        return None
    return [s.km_at for sd in sched for s in sd.plan.stops if s.kind is StopKind.FUEL and s.pool == "fuel"]


def build_alternatives(
    sched: list[ScheduledDay], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext
) -> None:
    """Fill `ScheduledDay.alternatives` / `.alternatives_note` for every day (ids must be assigned first)."""
    profile = ctx.profile_for(corridor.route)
    used = {s.place.id for sd in sched for s in sd.plan.stops if s.place is not None}
    pools = Pools.of(corridor)
    fills = fuel_fills(sched, ctx)
    for sd in sched:
        sd.alternatives, sd.alternatives_note = alternatives_for_day(
            sd, pools, used, inp, ctx, profile, fills, corridor.route.km_total, corridor.towns
        )
