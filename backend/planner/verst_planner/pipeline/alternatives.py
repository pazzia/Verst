"""Stage 11: 2-3 alternatives per replaceable stop within ±45 min (A§6.11, SPEC §7.2 step 11)."""

from __future__ import annotations

import dataclasses
import itertools
from dataclasses import dataclass

from verst_planner.domain.enums import Meal, PlaceType, StopKind, Tag, WarningCode
from verst_planner.domain.model import (
    Alternative,
    AltUnits,
    Candidate,
    DayPlan,
    NormalizedInput,
    PlannedStop,
    ReplaceableKinds,
    TownCandidate,
)
from verst_planner.pipeline import Corridor, PlanContext, round_half_up
from verst_planner.pipeline.assemble import km_from_prev_row, render_stop
from verst_planner.pipeline.fuel import fuel_range, fuel_score
from verst_planner.pipeline.meals import in_window, lunch_score, make_lunch_stop, sights_still_open
from verst_planner.pipeline.rest import make_rest_stop, rest_pool, rest_score
from verst_planner.pipeline.schedule import ScheduledDay
from verst_planner.pipeline.sights import lunch_out_of_window, make_sight_stop, sight_score
from verst_planner.pipeline.timeline import (
    Profile,
    Slot,
    day_duration_min,
    day_end,
    insert_index,
    local,
    schedule_day,
)


@dataclass(slots=True)
class Pools:
    sights: list[Candidate]
    food: list[Candidate]
    fuel: list[Candidate]
    rest: list[Candidate]

    @classmethod
    def of(cls, corridor: Corridor) -> Pools:
        return cls(corridor.sights, corridor.food, corridor.fuel, rest_pool(corridor))


def family(s: PlannedStop) -> str | None:
    """Which stage pool a stop's alternatives come from (rest pool for stops inserted by stage 7)."""
    if s.kind not in ReplaceableKinds or s.fixed:
        return None
    if s.reason_key.startswith("rest."):
        return "rest"
    if s.kind is StopKind.FUEL:
        return "fuel"
    if s.kind is StopKind.FOOD:
        return "food"
    if s.kind is StopKind.SIGHT:
        return "sight"
    return "rest"


@dataclass(slots=True)
class _Probe:
    stop: PlannedStop
    stops: list[PlannedStop]
    slots: list[Slot]
    index: int
    score: float


def _replace(
    stops: list[PlannedStop], i: int, new: PlannedStop, day: DayPlan
) -> tuple[list[PlannedStop], int]:
    rest = [*stops[:i], *stops[i + 1 :]]
    tmp = DayPlan(day.day, day.km_start, day.km_end, day.start_at, rest, day.tz)
    j = insert_index(tmp, new)
    rest.insert(j, new)
    return rest, j


def _make(
    fam: str,
    c: Candidate,
    old: PlannedStop,
    inp: NormalizedInput,
    ctx: PlanContext,
    towns: list[TownCandidate],
) -> PlannedStop:
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
    )


def _covers(s: PlannedStop, slot: Slot, ctx: PlanContext) -> bool:
    if s.place is None:
        return True
    hours = ctx.hours(s.place)
    if hours is None:
        return True
    assert slot.arrive is not None and slot.depart is not None
    tz = ctx.tz_of(s.region_code, s.point)
    return hours.covers(local(slot.arrive, tz), local(slot.depart, tz))


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
) -> dict[int, tuple[Alternative, ...]]:
    """Alternatives of each replaceable stop of a day (`fills`: fuel stop km, None = no range check)."""
    day = sd.plan
    stops = day.stops
    slots = sd.slots
    window = ctx.cfg.alternatives.window_min
    limit = max(sd.budget_min, day_duration_min(day, slots))
    end0 = day_end(slots)
    full = fuel_range(inp.vehicle, ctx).full_km
    out: dict[int, tuple[Alternative, ...]] = {}
    for i, old in enumerate(stops):
        fam = family(old)
        if fam is None:
            continue
        old_slot = slots[i]
        assert old_slot.arrive is not None
        pool = {"rest": pools.rest, "sight": pools.sights, "food": pools.food, "fuel": pools.fuel}[fam]
        probes: list[_Probe] = []
        for c in pool:
            if c.place.id in used or not (day.km_start < c.km_at < day.km_end):
                continue
            if old.place is not None and c.place.type is not old.place.type:
                continue  # same kind: a coffee stop is replaced by a coffee stop, a rest area by a rest area
            new = _make(fam, c, old, inp, ctx, towns or [])
            new_stops, j = _replace(stops, i, new, day)
            if j != i:
                continue  # keep the neighbours: later stops then shift by exactly `shift_min`
            trial = DayPlan(day.day, day.km_start, day.km_end, day.start_at, new_stops, day.tz)
            new_slots = schedule_day(trial, profile)
            arrive = new_slots[j].arrive
            assert arrive is not None
            if abs((arrive - old_slot.arrive).total_seconds()) / 60 > window:
                continue
            if new.kind is StopKind.SIGHT and not _covers(new, new_slots[j], ctx):
                continue
            if new.meal is Meal.LUNCH:
                tz = ctx.tz_of(new.region_code, new.point)
                if not in_window(local(arrive, tz), ctx.cfg.lunch_window) or not _covers(
                    new, new_slots[j], ctx
                ):
                    continue
            if not sights_still_open(trial, new_slots, ctx) or lunch_out_of_window(trial, new_slots, ctx):
                continue
            if day_duration_min(trial, new_slots) > limit + 1e-6:
                continue
            if fills is not None and fam == "fuel":
                pts = sorted([0.0, *[f for f in fills if abs(f - old.km_at) > 1e-9], c.km_at, total_km])
                if any(b - a > full + 1e-6 for a, b in itertools.pairwise(pts)):
                    continue
            if fam == "rest":
                score = rest_score(c, inp)
            elif fam == "sight":
                score = sight_score(c, inp)
            elif fam == "food":
                score = lunch_score(c, inp, local(arrive, ctx.tz_of(c.region_code, c.place.point)), ctx)
            else:
                score = fuel_score(c, [trial], ctx)
            probes.append(_Probe(new, new_stops, new_slots, j, score))
        probes.sort(key=lambda p: (-round(p.score, 9), p.stop.km_at, p.stop.place.id if p.stop.place else ""))
        alts: list[Alternative] = []
        seen: set[str] = set()
        for p in probes:
            assert p.stop.place is not None
            if p.stop.place.id in seen:
                continue
            seen.add(p.stop.place.id)
            nxt = p.stops[p.index + 1]
            old_next = stops.index(nxt)
            arr_new, arr_old = p.slots[p.index + 1].arrive, slots[old_next].arrive
            assert arr_new is not None and arr_old is not None
            shift = round_half_up((arr_new - arr_old).total_seconds() / 60)
            delta = round_half_up((day_end(p.slots) - end0).total_seconds() / 60)
            row = km_from_prev_row(p.stops)
            rendered = render_stop(
                p.stop,
                p.slots[p.index],
                day.day,
                p.index,
                sd.seq0 + i,
                row[p.index],
                inp,
                ctx,
                sid=sd.ids[i] if sd.ids else None,
            )
            place = p.stop.place
            adult = place.ticket_adult_rub if place.type is PlaceType.SIGHT else None
            child = place.ticket_child_rub if place.type is PlaceType.SIGHT else None
            if place.type is PlaceType.SIGHT and Tag.FREE_ENTRY in place.tags:
                adult, child = 0, 0
            units = AltUnits(
                delta_km=round(p.stop.detour_km - old.detour_km, 3),
                region_code=p.stop.region_code,
                check_rub=place.avg_check_rub if place.type is PlaceType.FOOD else None,
                adult_rub=adult,
                child_rub=child,
                name_ru=place.name_ru,
                place_id=place.id,
            )
            alts.append(
                Alternative(
                    id=f"alt_{rendered.id}_{place.id}",
                    place_id=place.id,
                    name_ru=place.name_ru,
                    delta_min=delta,
                    delta_rub=ctx.stop_cost(p.stop, inp) - ctx.stop_cost(old, inp),
                    shift_min=shift,
                    stop=dataclasses.replace(rendered, alternatives=()),
                    units=units,
                )
            )
            if len(alts) == ctx.cfg.alternatives.max:
                break
        out[i] = tuple(alts)
    return out


def fuel_fills(sched: list[ScheduledDay], ctx: PlanContext) -> list[float] | None:
    """Fuel stop km over the whole trip; None when a FUEL_GAP made the range check meaningless."""
    if any(w.code is WarningCode.FUEL_GAP for w in ctx.fuel_warnings):
        return None
    return [s.km_at for sd in sched for s in sd.plan.stops if s.kind is StopKind.FUEL]


def build_alternatives(
    sched: list[ScheduledDay], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext
) -> None:
    """Fill `ScheduledDay.alternatives` for every day (ids must be assigned first)."""
    profile = ctx.profile_for(corridor.route)
    used = {s.place.id for sd in sched for s in sd.plan.stops if s.place is not None}
    pools = Pools.of(corridor)
    fills = fuel_fills(sched, ctx)
    for sd in sched:
        sd.alternatives = alternatives_for_day(
            sd, pools, used, inp, ctx, profile, fills, corridor.route.km_total, corridor.towns
        )
