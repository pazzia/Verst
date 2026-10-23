"""Stage 7: breaks and rests, run after lunch and sights (A§16.2 replaces the rest part of A§6.8).

*Breaks* are the day start and every stop with `dwell_min ≥ break_min_dwell` (sights, lunch, coffee fuel
stops, rests, vias). `plan_rests` fills only the gaps between consecutive breaks whose driving time exceeds
`R = rest_interval_min[mood]`:

1. a range fuel stop in the window with a cafe becomes a coffee stop (no extra stop);
2. else the best admissible rest-pool candidate (detour ≤ `rest.max_detour_min`, at least
   `rest.min_gap_min` after the previous break) in `[R - 30, R]`, widened to `[max(G, R - 60), R + 15]`;
3. else a virtual break at the point where the clock reaches `R` (no stop).

A candidate is only inserted when every sight of the day stays open and the lunch stays in its window.
"""

from __future__ import annotations

import bisect
import dataclasses
from dataclasses import dataclass

from verst_planner.domain.enums import PlaceType, StopKind, Tag
from verst_planner.domain.model import Candidate, DayPlan, NormalizedInput, PlannedStop
from verst_planner.explain import ru
from verst_planner.explain.reasons import sight_reason
from verst_planner.pipeline import Corridor, PlanContext
from verst_planner.pipeline.checks import day_valid, lunch_out_of_window, over_budget, sights_still_open
from verst_planner.pipeline.timeline import Profile, eta_if_inserted, insert_stop, local, schedule_day

MAX_REST_SIGHT_DWELL = 30
ROUND_DRIVE_MIN = 15
EPS = 1e-6


@dataclass(slots=True)
class DriveClock:
    """Cumulative driving minutes along one day (detours count as driving, dwell does not).

    `t_arr[i]` is the clock on arrival at stop `i` (after the inbound half of its detour), `t_dep[i]` the
    clock when the car is back on the route (after the outbound half).
    """

    kms: list[float]
    t_arr: list[float]
    t_dep: list[float]
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
        """Clock at route km `km` (between stops, on the route)."""
        i = max(0, bisect.bisect_right(self.kms, km) - 1)
        return self.t_dep[i] + self.profile.drive(self.kms[i], km)

    def km_of(self, t: float, lo_km: float, hi_km: float) -> float:
        """Route km where the clock reads `t`, searched between `lo_km` and `hi_km`."""
        i = max(0, bisect.bisect_right(self.kms, lo_km) - 1)
        while i + 1 < len(self.kms) and self.t_arr[i + 1] < t and self.kms[i + 1] < hi_km:
            i += 1
        km = self.profile.km_after_drive(self.kms[i], max(0.0, t - self.t_dep[i]))
        return max(lo_km, min(km, hi_km))


def is_break(s: PlannedStop, min_dwell: int) -> bool:
    return s.kind is StopKind.START or (
        s.kind not in (StopKind.OVERNIGHT, StopKind.FINISH) and s.dwell_min >= min_dwell
    )


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


def rounded_drive(drove_min: float) -> int:
    """Driving since the previous break rounded to 15 min (at least 15) for `rest.generic`."""
    return int(max(ROUND_DRIVE_MIN, round(drove_min / ROUND_DRIVE_MIN) * ROUND_DRIVE_MIN))


def _reason(inp: NormalizedInput, dwell: int, drove_min: float) -> tuple[str, dict[str, str | int | float]]:
    who = _who(inp)
    base: dict[str, str | int | float] = {"min": dwell, "min_word": ru.minutes_word(dwell)}
    if who:
        return "rest.who", {**base, "who": who}
    return "rest.generic", {**base, "drive": ru.duration_genitive(rounded_drive(drove_min))}


def rest_pool(corridor: Corridor) -> list[Candidate]:
    """Rest areas, short sights and fuel stations with a cafe (A§6.8), sorted by km; also the REST
    alternatives pool."""
    pool = [*corridor.rest, *[c for c in corridor.fuel if Tag.CAFE_AT_FUEL in c.place.tags]]
    pool += [c for c in corridor.sights if (c.place.dwell_min or 60) <= MAX_REST_SIGHT_DWELL]
    return sorted(pool, key=lambda c: (c.km_at, c.place.id))


def make_rest_stop(c: Candidate, inp: NormalizedInput, ctx: PlanContext, drove_min: float) -> PlannedStop:
    """A rest-pool candidate as a stop: rest area (20 min), coffee at a fuel station (15 min, kind FUEL)
    or a short sight (its own dwell, at least a break, reason `sight.default`)."""
    dm = ctx.cfg.dwell_min
    if c.place.type is PlaceType.FUEL:
        kind, dwell, coffee = StopKind.FUEL, dm.coffee, True
        key, params = _reason(inp, dwell, drove_min)
    elif c.place.type is PlaceType.SIGHT:
        kind, dwell, coffee = (
            StopKind.SIGHT,
            max(c.place.dwell_min or dm.rest, ctx.cfg.rest.break_min_dwell),
            False,
        )
        key, params = sight_reason(dwell, inp.crew, c.place.source)
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
        pool="rest",
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


def _keeps_day_valid(day: DayPlan, stop: PlannedStop, ctx: PlanContext, profile: Profile) -> bool:
    i = insert_stop(day, stop)
    try:
        return day_valid(day, ctx, profile)
    finally:
        day.stops.pop(i)


@dataclass(slots=True)
class RestPool:
    """The rest pool sorted by km, sliced by bisect."""

    cands: list[Candidate]
    kms: list[float] = dataclasses.field(default_factory=list)

    def __post_init__(self) -> None:
        self.kms = [c.km_at for c in self.cands]

    def between(self, lo: float, hi: float) -> list[Candidate]:
        return self.cands[bisect.bisect_left(self.kms, lo) : bisect.bisect_right(self.kms, hi)]


@dataclass(slots=True)
class _Gap:
    i0: int  # index of the break stop b0 (-1 for a virtual break)
    t0: float  # clock at b0 (arrival)
    km0: float
    t1: float  # clock at b1 (arrival) or at the day end
    km1: float


def _first_long_gap(
    day: DayPlan, clock: DriveClock, virtual: list[float], r: float, min_dwell: int
) -> _Gap | None:
    marks = sorted(
        [(clock.t_arr[i], day.stops[i].km_at, i) for i, s in enumerate(day.stops) if is_break(s, min_dwell)]
        + [(clock.at(km), km, -1) for km in virtual]
    )
    for j, (t0, km0, i0) in enumerate(marks):
        t1 = marks[j + 1][0] if j + 1 < len(marks) else clock.t_arr[-1]
        km1 = marks[j + 1][1] if j + 1 < len(marks) else day.km_end
        if t1 - t0 > r + EPS:  # a break exactly R after the previous one is on time
            return _Gap(i0, t0, km0, t1, km1)
    return None


def _upgrade_fuel(
    day: DayPlan, gap: _Gap, clock: DriveClock, r: float, ctx: PlanContext, profile: Profile, strict: bool
) -> bool:
    """Step 1: a range fuel stop with a cafe inside the window becomes a coffee stop (15 min)."""
    lo, hi = (
        max(float(ctx.cfg.rest.min_gap_min), r - ctx.cfg.rest.widen_before_min),
        r + ctx.cfg.rest.widen_after_min,
    )
    best: tuple[float, int] | None = None
    for k, s in enumerate(day.stops):
        if not (gap.km0 <= s.km_at <= gap.km1) or k == gap.i0:
            continue
        if s.kind is not StopKind.FUEL or s.coffee or s.place is None or Tag.CAFE_AT_FUEL not in s.place.tags:
            continue
        d0 = clock.t_arr[k] - gap.t0
        if lo - EPS <= d0 <= hi + EPS and (best is None or abs(d0 - r) < best[0]):
            best = (abs(d0 - r), k)
    if best is None:
        return False
    k = best[1]
    old = day.stops[k]
    day.stops[k] = dataclasses.replace(old, coffee=True, dwell_min=ctx.cfg.dwell_min.fuel_coffee)
    if not strict or day_valid(day, ctx, profile):
        return True
    day.stops[k] = old
    return False


def plan_rests_day(
    day: DayPlan,
    pool: RestPool,
    used: set[str],
    inp: NormalizedInput,
    ctx: PlanContext,
    profile: Profile,
    strict: bool = True,
) -> list[PlannedStop]:
    """Fill the day's long gaps between breaks (mutates `day`); returns the inserted stops.

    `strict` (the real stage 7) only inserts a rest that keeps every sight open and the lunch in its
    window; `day_ok` plans its reserve copy with `strict=False`, so a lunch or sight that only fits
    without its rests is rejected (A§16.2).
    """
    rc = ctx.cfg.rest
    r = float(ctx.cfg.rest_interval_min.of(inp.mood))
    g = float(rc.min_gap_min)
    virtual: list[float] = []
    added: list[PlannedStop] = []
    taken = set(used)
    for _guard in range(200):
        clock = DriveClock.of(day, profile)
        gap = _first_long_gap(day, clock, virtual, r, rc.break_min_dwell)
        if gap is None:
            break
        x = clock.km_of(gap.t0 + r, gap.km0, gap.km1)
        if clock.t_arr[-1] - (gap.t0 + r) < rc.min_remaining_drive_min:
            break
        if _upgrade_fuel(day, gap, clock, r, ctx, profile, strict):
            continue
        need_after = min(g, gap.t1 - gap.t0 - r)

        def admissible(
            c: Candidate, gap: _Gap = gap, clock: DriveClock = clock, need_after: float = need_after
        ) -> float | None:
            """Driving since b0 when `c` is admissible, else None."""
            if c.place.id in taken or not (day.km_start < c.km_at < day.km_end):
                return None
            if c.detour_min > rc.max_detour_min:
                return None
            at = clock.at(c.km_at)
            d0 = at + c.detour_min / 2 - gap.t0
            if d0 < g - EPS or gap.t1 - at < need_after - EPS:
                return None
            return d0

        span = pool.between(gap.km0, gap.km1)
        scored = [(c, d0) for c in span if (d0 := admissible(c)) is not None]
        cands = [(c, d0) for c, d0 in scored if r - rc.window_before_min - EPS <= d0 <= r + EPS]
        if not cands:
            lo = max(g, r - rc.widen_before_min)
            cands = [(c, d0) for c, d0 in scored if lo - EPS <= d0 <= r + rc.widen_after_min + EPS]
        chosen = None
        for c, d0 in sorted(
            cands, key=lambda cd: (-round(rest_score(cd[0], inp), 9), abs(cd[1] - r), cd[0].place.id)
        ):
            stop = make_rest_stop(c, inp, ctx, d0)
            if _open_at_eta(day, stop, ctx, profile) and (
                not strict or _keeps_day_valid(day, stop, ctx, profile)
            ):
                chosen = stop
                break
        if chosen is None:
            virtual.append(x)
            continue
        insert_stop(day, chosen)
        assert chosen.place is not None
        taken.add(chosen.place.id)
        added.append(chosen)
    return added


def plan_rests(days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext) -> None:
    """Stage 7 over every day (runs after lunch and sights, A§16.2)."""
    profile = ctx.profile_for(corridor.route)
    used = {s.place.id for d in days for s in d.stops if s.place is not None}
    pool = RestPool(rest_pool(corridor))
    for day in days:
        for s in plan_rests_day(day, pool, used, inp, ctx, profile):
            assert s.place is not None
            used.add(s.place.id)


def day_ok(
    day: DayPlan,
    inp: NormalizedInput,
    ctx: PlanContext,
    profile: Profile,
    pool: RestPool,
    used: set[str],
) -> bool:
    """A§16.2: the day is feasible once its rests are planned (on a copy): optional content within the
    budget (`max(day_budget_min, mandatory + fixed)`, A§16.5), every sight open for its whole visit, the
    lunch in its window."""
    copy = DayPlan(day.day, day.km_start, day.km_end, day.start_at, list(day.stops), day.tz)
    plan_rests_day(copy, pool, used, inp, ctx, profile, strict=False)
    slots = schedule_day(copy, profile)
    if over_budget(copy, slots, profile, ctx.cfg.day_budget_min.of(inp.mood), with_fixed=True):
        return False
    return sights_still_open(copy, slots, ctx) and not lunch_out_of_window(copy, slots, ctx)


def remove_rests(day: DayPlan, ctx: PlanContext) -> None:
    """Undo stage 7 on a day: drop rest-pool stops and revert coffee upgrades of range fuel stops."""
    out = []
    for s in day.stops:
        if s.pool == "rest":
            continue
        if s.kind is StopKind.FUEL and s.coffee:
            s = dataclasses.replace(s, coffee=False, dwell_min=ctx.cfg.dwell_min.fuel)
        out.append(s)
    day.stops[:] = out
