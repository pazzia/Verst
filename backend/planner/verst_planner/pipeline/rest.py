"""Stage 7: rest stops every R minutes of driving (A§6.8, SPEC §7.2 step 7)."""

from __future__ import annotations

import bisect
from dataclasses import dataclass

from verst_planner.domain.enums import PlaceType, StopKind, Tag
from verst_planner.domain.model import Candidate, DayPlan, NormalizedInput, PlannedStop
from verst_planner.explain import ru
from verst_planner.pipeline import Corridor, PlanContext
from verst_planner.pipeline.timeline import Profile, eta_if_inserted, insert_stop, local

MAX_REST_SIGHT_DWELL = 30
ROUND_DRIVE_MIN = 15


@dataclass(slots=True)
class DriveClock:
    """Cumulative driving minutes along one day (detours count as driving, dwell does not)."""

    kms: list[float]  # stop km
    t_arr: list[float]  # clock at arrival of each stop
    t_dep: list[float]  # clock when back on the route after each stop
    profile: Profile

    @classmethod
    def of(cls, day: DayPlan, profile: Profile) -> DriveClock:
        kms, arr, dep = [], [], []
        t = 0.0
        for i, s in enumerate(day.stops):
            if i > 0:
                t += profile.drive(day.stops[i - 1].km_at, s.km_at) + s.detour_min / 2
            kms.append(s.km_at)
            arr.append(t)
            t += s.detour_min / 2 if i > 0 else 0.0
            dep.append(t)
        return cls(kms, arr, dep, profile)

    def at(self, km: float) -> float:
        """Clock at route km `km` (between stops)."""
        i = max(0, bisect.bisect_right(self.kms, km) - 1)
        return self.t_dep[i] + self.profile.drive(self.kms[i], km)

    def km_of(self, t: float, lo_km: float, hi_km: float) -> float:
        """Route km where the clock reads `t`, searched between `lo_km` and `hi_km`."""
        i = max(0, bisect.bisect_right(self.kms, lo_km) - 1)
        while i + 1 < len(self.kms) and self.t_arr[i + 1] < t and self.kms[i + 1] < hi_km:
            i += 1
        km = self.profile.km_after_drive(self.kms[i], max(0.0, t - self.t_dep[i]))
        return max(lo_km, min(km, hi_km))


def rest_score(c: Candidate, inp: NormalizedInput) -> float:
    t = c.place.tags
    sight = c.place.type is PlaceType.SIGHT
    return (
        1.0 * (c.place.type is PlaceType.REST)
        + 2.0 * (Tag.PLAYGROUND in t and inp.crew.children > 0)
        + 1.5 * (Tag.WALK in t and inp.crew.dog)
        + 1.0 * (Tag.WC in t)
        + 0.5 * (Tag.VIEW in t)
        + 0.5 * c.place.rating_internal * sight
        - c.detour_min / 5
    )


def _who(inp: NormalizedInput) -> str | None:
    parts = []
    if inp.crew.children == 1:
        parts.append(ru.text("who.child"))
    elif inp.crew.children > 1:
        parts.append(ru.text("who.children"))
    if inp.crew.dog:
        parts.append(ru.text("who.dog"))
    return ru.text("who.join").join(parts) if parts else None


def _reason(inp: NormalizedInput, dwell: int, drove_min: float) -> tuple[str, dict[str, str | int | float]]:
    who = _who(inp)
    base: dict[str, str | int | float] = {"min": dwell, "min_word": ru.minutes_word(dwell)}
    if who:
        return "rest.who", {**base, "who": who}
    rounded = max(ROUND_DRIVE_MIN, round(drove_min / ROUND_DRIVE_MIN) * ROUND_DRIVE_MIN)
    return "rest.generic", {**base, "drive": ru.duration_genitive(int(rounded))}


def rest_pool(corridor: Corridor) -> list[Candidate]:
    """Rest areas, short sights and fuel stations with a cafe (A§6.8); also the REST alternatives pool."""
    pool = [*corridor.rest, *[c for c in corridor.fuel if Tag.CAFE_AT_FUEL in c.place.tags]]
    pool += [c for c in corridor.sights if (c.place.dwell_min or 60) <= MAX_REST_SIGHT_DWELL]
    return sorted(pool, key=lambda c: (c.km_at, c.place.id))


def make_rest_stop(c: Candidate, inp: NormalizedInput, ctx: PlanContext, drove_min: float) -> PlannedStop:
    dm = ctx.cfg.dwell_min
    if c.place.type is PlaceType.FUEL:
        kind, dwell, coffee = StopKind.FUEL, dm.coffee, True
    elif c.place.type is PlaceType.SIGHT:
        kind, dwell, coffee = (
            StopKind.SIGHT,
            max(c.place.dwell_min or dm.rest, ctx.cfg.rest.break_min_dwell),
            False,
        )
    else:
        kind, dwell, coffee = StopKind.REST, dm.rest, False
    key, params = _reason(inp, dwell, drove_min)
    return PlannedStop(
        kind=kind,
        km_at=c.km_at,
        name_ru=c.place.name_ru,
        point=c.place.point,
        place=c.place,
        detour_km=c.detour_km,
        detour_min=c.detour_min,
        dwell_min=dwell,
        auto=True,
        score=rest_score(c, inp),
        reason_key=key,
        reason_params=params,
        region_code=c.region_code,
        coffee=coffee,
    )


def _open_at_eta(day: DayPlan, stop: PlannedStop, ctx: PlanContext, profile: Profile) -> bool:
    if stop.place is None or stop.kind is not StopKind.SIGHT:
        return True
    hours = ctx.hours(stop.place)
    if hours is None:
        return True
    slot, _ = eta_if_inserted(day, stop, profile)
    assert slot.arrive is not None and slot.depart is not None
    tz = ctx.tz_of(stop.region_code, stop.point)
    return hours.covers(local(slot.arrive, tz), local(slot.depart, tz))


def _breaks(day: DayPlan, min_dwell: int) -> list[int]:
    return [i for i, s in enumerate(day.stops) if s.kind is StopKind.START or s.dwell_min >= min_dwell]


def plan_rests(days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext) -> None:
    profile = ctx.profile_for(corridor.route)
    rc = ctx.cfg.rest
    interval = float(ctx.cfg.rest_interval_min.of(inp.mood))
    used = {s.place.id for d in days for s in d.stops if s.place is not None}
    pool = rest_pool(corridor)
    for day in days:
        virtual: list[float] = []
        for _guard in range(200):
            clock = DriveClock.of(day, profile)
            # break positions on the clock: day start, stops with dwell ≥ 15 min, virtual breaks
            marks = sorted(
                [(clock.t_dep[i], day.stops[i].km_at) for i in _breaks(day, rc.break_min_dwell)]
                + [(clock.at(km), km) for km in virtual]
            )
            found = None
            for j, (t_b, km_b) in enumerate(marks):
                t_next = marks[j + 1][0] if j + 1 < len(marks) else clock.t_arr[-1]
                km_next = marks[j + 1][1] if j + 1 < len(marks) else day.km_end
                if t_next - t_b > interval + 1e-6:  # a break exactly at R is on time
                    found = (t_b, km_b, km_next)
                    break
            if found is None:
                break
            t_b, km_b, km_next = found
            x = clock.km_of(t_b + interval, km_b, km_next)
            if profile.drive(x, day.km_end) < rc.min_remaining_drive_min:
                break
            lo = clock.km_of(t_b + interval - rc.window_before_min, km_b, km_next)

            def free(c: Candidate, a: float, b: float, d: DayPlan = day) -> bool:
                eps = 1e-6  # x comes from an inverse profile lookup and carries float noise
                return (
                    a - eps <= c.km_at <= b + eps
                    and d.km_start < c.km_at < d.km_end
                    and c.place.id not in used
                )

            cands = [c for c in pool if free(c, lo, x)]
            if not cands:
                lo2 = clock.km_of(t_b + interval - rc.widen_before_min, km_b, km_next)
                hi2 = clock.km_of(t_b + interval + rc.widen_after_min, km_b, km_next)
                cands = [c for c in pool if free(c, lo2, hi2)]
            chosen = None
            for c in sorted(cands, key=lambda c: (-round(rest_score(c, inp), 9), -c.km_at, c.place.id)):
                stop = make_rest_stop(c, inp, ctx, clock.at(c.km_at) - t_b)
                if _open_at_eta(day, stop, ctx, profile):
                    chosen = stop
                    break
            if chosen is None:
                virtual.append(x)
                continue
            insert_stop(day, chosen)
            assert chosen.place is not None
            used.add(chosen.place.id)
