"""Stage 6: fuel range walk (A§6.7, SPEC §7.2 step 6)."""

from __future__ import annotations

from dataclasses import dataclass

from verst_planner.domain.enums import StopKind, Tag, WarningCode
from verst_planner.domain.facts import Known, fuel_state
from verst_planner.domain.model import Candidate, DayPlan, NormalizedInput, PlannedStop, PlanWarning, Vehicle
from verst_planner.pipeline import Corridor, PlanContext, round_half_up
from verst_planner.pipeline.timeline import day_for_km, insert_stop

COINCIDE_KINDS = frozenset({StopKind.OVERNIGHT, StopKind.VIA, StopKind.SIGHT, StopKind.FOOD})
LAST_FILL_MARGIN_KM = 10.0


@dataclass(frozen=True, slots=True)
class FuelRange:
    full_km: float  # km on a full tank
    usable_km: float  # km until 20 % is left


def fuel_range(vehicle: Vehicle, ctx: PlanContext) -> FuelRange:
    full = vehicle.tank_l / vehicle.consumption_l_per_100km * 100.0
    return FuelRange(full, full * ctx.cfg.fuel.usable_frac)


def _all_stops(days: list[DayPlan]) -> list[PlannedStop]:
    return [s for d in days for s in d.stops]


def _coincide(c: Candidate, days: list[DayPlan], ctx: PlanContext) -> bool:
    lim = ctx.cfg.fuel.coincide_km
    return any(
        (s.kind in COINCIDE_KINDS or s.fixed)
        and s.kind not in (StopKind.START, StopKind.FINISH)
        and abs(s.km_at - c.km_at) <= lim
        for s in _all_stops(days)
    )


def fuel_score(c: Candidate, days: list[DayPlan], ctx: PlanContext) -> float:
    t = c.place.tags
    return (
        3.0 * _coincide(c, days, ctx)
        + 1.0 * (Tag.CAFE_AT_FUEL in t)
        + 1.0 * (Tag.H24 in t)
        + 0.5 * (Tag.WC in t)
        - c.detour_min / 5
    )


def _pick(
    cands: list[Candidate], days: list[DayPlan], ctx: PlanContext, inp: NormalizedInput, latest: bool = False
) -> Candidate:
    """The best station of the window; ADR-0019 E-4: one confirmed to sell the car's fuel ranks above any
    whose fuels are unknown (stations known not to sell it never reach the corridor)."""

    def key(c: Candidate) -> tuple[bool, float, float, str]:
        score = fuel_score(c, days, ctx) + (0.01 * c.km_at if latest else 0.0)
        unknown = fuel_state(c.place, inp.vehicle.fuel_type) is not Known.YES
        return (unknown, -round(score, 9), c.km_at, c.place.id)

    return min(cands, key=key)


def plan_fuel(
    days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext
) -> list[PlanWarning]:
    """Insert FUEL stops (mutates `days`); returns FUEL_GAP warnings."""
    fc = ctx.cfg.fuel
    rng = fuel_range(inp.vehicle, ctx)
    full = rng.full_km
    reserve = (1.0 - fc.usable_frac) * full
    total = corridor.route.km_total
    used = {s.place.id for s in _all_stops(days) if s.place is not None}
    overnights = sorted(
        (d.stops[-1] for d in days if d.stops[-1].kind is StopKind.OVERNIGHT), key=lambda s: s.km_at
    )
    warnings: list[PlanWarning] = []
    pos = 0.0
    remaining = full * fc.start_frac
    last_fill = 0.0
    inserted: list[PlannedStop] = []
    for _guard in range(1000):
        trigger = pos + remaining - reserve
        if trigger >= total - fc.skip_near_finish_frac * full:
            break
        evening = next((b for b in overnights if b.km_at < trigger <= b.km_at + fc.evening_next_day_km), None)

        def pool(lo: float, hi: float, after: float = pos) -> list[Candidate]:
            return [
                c for c in corridor.fuel if lo <= c.km_at <= hi and c.km_at > after and c.place.id not in used
            ]

        latest = False
        if evening is not None:
            cands = pool(max(pos, evening.km_at - fc.evening_window_km), evening.km_at)
            reason = "fuel.evening"
        else:
            cands = pool(trigger, trigger + fc.lookahead_km)
            reason = "fuel.range"
            if not cands:
                cands = pool(max(pos, trigger - fc.lookback_km), trigger)
                latest = True
                if not cands:
                    cands = pool(trigger, pos + remaining - LAST_FILL_MARGIN_KM)
                    latest = False
        if not cands:
            day = day_for_km(days, trigger)
            warnings.append(
                ctx.warning(WarningCode.FUEL_GAP, day.day, f"km={trigger:.1f}", km=round_half_up(trigger))
            )
            pos = trigger + fc.lookahead_km  # virtual refuel: the walk continues with a full tank
            remaining = full
            last_fill = pos
            continue
        best = _pick(cands, days, ctx, inp, latest)
        if reason == "fuel.range" and _coincide(best, days, ctx):
            reason = "fuel.coincide"
        params: dict[str, str | int | float] = {}
        if reason == "fuel.range":
            params["km"] = round_half_up(trigger - pos)
        litres = (best.km_at - last_fill + best.detour_km) * inp.vehicle.consumption_l_per_100km / 100.0
        stop = PlannedStop(
            kind=StopKind.FUEL,
            km_at=best.km_at,
            name_ru=best.place.name_ru,
            point=best.place.point,
            place=best.place,
            detour_km=best.detour_km,
            detour_min=best.detour_min,
            dwell_min=ctx.cfg.dwell_min.fuel,
            auto=True,
            score=fuel_score(best, days, ctx),
            reason_key=reason,
            reason_params=params,
            region_code=best.region_code,
            litres=litres,
            pool="fuel",
        )
        insert_stop(day_for_km(days, best.km_at), stop)
        inserted.append(stop)
        used.add(best.place.id)
        pos = best.km_at
        last_fill = best.km_at
        remaining = full
    if inserted and inp.round_trip:
        last = max(inserted, key=lambda s: s.km_at)
        if last.reason_key == "fuel.range":
            last.reason_key, last.reason_params = "fuel.last", {}
    return warnings
