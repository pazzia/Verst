"""Stage 7: breaks and rests, run after lunch and sights (A§16.2 replaces the rest part of A§6.8).

*Breaks* are the day start and every stop with `dwell_min ≥ break_min_dwell` (sights, lunch, coffee fuel
stops, rests, vias). `plan_rests` fills only the gaps between consecutive breaks whose driving time exceeds
`R = rest_interval_min[mood]`:

1. a range fuel stop in the window with a cafe becomes a coffee stop (no extra stop);
2. else the best admissible rest-pool candidate (detour ≤ `rest.max_detour_min`, at least
   `rest.min_gap_min` after the previous break) in `[R - 30, R]`, widened to `[max(G, R - 60), R + 15]`;
3. else an extended window: detour ≤ `rest.extended_detour_min` (15), driving since the previous break in
   `[max(45, R - 60), R + 30]` (A§16.11.1);
4. else a roadside break (`label.roadside_break`, 15 min, no place) where the clock reaches `R`.

A candidate is only inserted when every sight of the day stays open and the lunch stays in its window.
"""

from __future__ import annotations

import bisect
import dataclasses
from dataclasses import dataclass

from verst_planner.domain.enums import Mood, PlaceType, StopKind, Tag
from verst_planner.domain.facts import rank_rating
from verst_planner.domain.model import Candidate, DayPlan, LatLon, NormalizedInput, Place, PlannedStop, Route
from verst_planner.explain import ru
from verst_planner.explain.reasons import sight_reason
from verst_planner.geo.distance import haversine_km
from verst_planner.geo.polyline import interpolate
from verst_planner.pipeline import Corridor, PlanContext
from verst_planner.pipeline.checks import day_valid, lunch_out_of_window, over_budget, sights_still_open
from verst_planner.pipeline.timeline import (
    Profile,
    detour_halves,
    eta_if_inserted,
    insert_stop,
    local,
    schedule_day,
)

MAX_REST_SIGHT_DWELL = 30
# ADR-0015 §5 «Весело и познавательно»: interesting stops in the rest slots, within a 15-min detour,
# 30-45 min, chosen for the crew; a dog never gets an indoor-only place as its walk.
FUN_DETOUR_MIN = 15
FUN_DETOUR_FALLBACK_MIN = 30  # M8: when nothing interesting is within 15 min of the rest window
FUN_DWELL = (30, 45)
FUN_BONUS = 5.0  # above a rest area with a playground, WC and a walk (5.5) for a fitting stop
FUN_PREFER: dict[str, frozenset[str]] = {
    # acceptance 2026-10-28 (K1 d): the copy promises a child «площадки, зоопарки и интерактивные музеи»;
    # an art museum is no longer a child's fun stop by default (it still fits the adults)
    "child": frozenset({"playground", "interactive", "zoo", "park", "nature"}),
    "dog": frozenset({"park", "nature", "embankment", "viewpoint"}),
    # CEO 2026-10-29: «весело» for adults is also the playful places — attractions, interactive museums, zoos
    "adults": frozenset(
        {
            "museum",
            "viewpoint",
            "kremlin",
            "nature",
            "square",
            "park",
            "embankment",
            "attraction",
            "interactive",
            "zoo",
        }
    ),
}
FUN_FIT = 1.5  # `fun_affinity` of a kind the crew's «Весело» copy promises (0.5 + 1.0)
INDOOR = frozenset({"museum", "theatre", "interactive"})
KID_FUN_KINDS = frozenset({"zoo", "playground", "interactive", "park"})  # = sights.KID_KINDS
KID_FUN_EXTRA = 0.5
EXTENDED_MIN_DRIVE = 45  # A§16.11.1 step 3: driving since b0 in [max(45, R - 60), R + 30]
EXTENDED_AFTER = 30
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
        halves = detour_halves(day.stops)
        for i, s in enumerate(day.stops):
            if i > 0:
                t += profile.drive(day.stops[i - 1].km_at, s.km_at) + halves[i][0]
            kms.append(s.km_at)
            arr.append(t)
            t += halves[i][1] if i > 0 else 0.0
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


def fun_group(inp: NormalizedInput) -> str:
    if inp.crew.children > 0:
        return "child"
    return "dog" if inp.crew.dog else "adults"


def fun_affinity(c: Candidate, inp: NormalizedInput) -> float:
    """How well an interesting stop suits the crew (0..1.5; negative = unsuitable)."""
    if c.place.type is not PlaceType.SIGHT:
        return 0.0
    from verst_planner.pipeline.sights import category_of

    cat = category_of(c.place)
    if inp.crew.dog and cat in INDOOR:
        return -1.0
    if cat == "playground" and inp.crew.children == 0:
        return -1.0  # a playground is for a child (and dogs are not let in)
    score = 0.5 + (1.0 if cat in FUN_PREFER[fun_group(inp)] else 0.0)
    if inp.crew.children > 0 and cat in KID_FUN_KINDS:
        score += KID_FUN_EXTRA  # K1 d: a playground, zoo or science centre before a lake or a viewpoint
    if inp.crew.children > 0 and cat in ("temple", "monastery", "church"):
        score -= 0.5
    return score


FUN_MIN_QUALITY = 0.30  # M9: a bare «Паровоз» is not a fun stop; a playground (named by its town) is


def is_fun(c: Candidate, inp: NormalizedInput) -> bool:
    return (
        inp.mood is Mood.FUN
        and c.place.type is PlaceType.SIGHT
        and fun_affinity(c, inp) > 0
        and _fun_quality_ok(c.place)
    )


def _fun_quality_ok(p: Place) -> bool:
    from verst_planner.pipeline.sights import category_of

    return p.quality is None or p.quality >= FUN_MIN_QUALITY or category_of(p) == "playground"


def fun_for(p: Place, inp: NormalizedInput) -> tuple[str, ...]:
    """ADR-0015 §5 `funFor`: the crew groups the stop suits (the stop's own group first when none does)."""
    from verst_planner.pipeline.sights import category_of

    cat = category_of(p)
    groups = []
    if inp.crew.children > 0 and cat in FUN_PREFER["child"]:
        groups.append("child")
    if inp.crew.dog and cat in FUN_PREFER["dog"] and cat not in INDOOR:
        groups.append("dog")
    if cat in FUN_PREFER["adults"] and not (inp.crew.dog and cat in INDOOR):
        groups.append("adults")
    return tuple(groups) or (fun_group(inp),)


def rest_score(c: Candidate, inp: NormalizedInput) -> float:
    t = c.place.tags
    sight = c.place.type is PlaceType.SIGHT
    fun = FUN_BONUS * fun_affinity(c, inp) if inp.mood is Mood.FUN and sight else 0.0
    return fun + (
        1.0 * (c.place.type is PlaceType.REST)
        + 2.0 * (Tag.PLAYGROUND in t and inp.crew.children > 0)
        + 1.5 * (Tag.WALK in t and inp.crew.dog)
        + 1.0 * (Tag.WC in t)
        + 0.5 * (Tag.VIEW in t)
        + 0.5 * rank_rating(c.place) * sight
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


def rest_pool(
    corridor: Corridor, fun: bool = False, secular: bool = False, sights: bool = True
) -> list[Candidate]:
    """Rest areas, short sights and fuel stations with a cafe (A§6.8), sorted by km; also the REST
    alternatives pool. `fun` («Весело и познавательно») adds every sight within the fun detour. `secular`
    (the open-data world, ADR-0015 §2): no church as a break — the religious share is the sights' budget.
    `sights` False («Только доехать», CEO 2026-10-29): rest areas and cafés at fuel stations only."""
    from verst_planner.pipeline.sights import RELIGIOUS, category_of, not_a_sight

    pool = [*corridor.rest, *[c for c in corridor.fuel if Tag.CAFE_AT_FUEL in c.place.tags]]
    pool += [
        c
        for c in corridor.sights
        if sights
        and (
            (c.place.dwell_min or 60) <= MAX_REST_SIGHT_DWELL
            or (fun and c.detour_min <= FUN_DETOUR_FALLBACK_MIN)
        )
        and not (
            secular
            and (category_of(c.place) in RELIGIOUS or not _fun_quality_ok(c.place) or not_a_sight(c.place))
        )
    ]
    return sorted(pool, key=lambda c: (c.km_at, c.place.id))


def make_rest_stop(c: Candidate, inp: NormalizedInput, ctx: PlanContext, drove_min: float) -> PlannedStop:
    """A rest-pool candidate as a stop: rest area (20 min), coffee at a fuel station (15 min, kind FUEL)
    or a short sight (its own dwell, at least a break, reason `sight.default`)."""
    dm = ctx.cfg.dwell_min
    rest_min = ctx.cfg.rest_dwell_min.of(inp.mood)
    if c.place.type is PlaceType.FUEL:
        kind, dwell, coffee = StopKind.FUEL, dm.coffee, True
        key, params = _reason(inp, dwell, drove_min)
    elif is_fun(c, inp):
        kind, dwell, coffee = (
            StopKind.SIGHT,
            min(FUN_DWELL[1], max(FUN_DWELL[0], c.place.dwell_min or 30)),
            False,
        )
        key, params = f"rest.fun.{fun_group(inp)}", {"min": dwell, "min_word": ru.minutes_word(dwell)}
    elif c.place.type is PlaceType.SIGHT:
        kind, dwell, coffee = (
            StopKind.SIGHT,
            max(c.place.dwell_min or rest_min, ctx.cfg.rest.break_min_dwell),
            False,
        )
        key, params = sight_reason(dwell, inp.crew, c.place)
    else:
        kind, dwell, coffee = StopKind.REST, rest_min, False
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
    route: Route | None = None  # for the position of a roadside break
    kms: list[float] = dataclasses.field(default_factory=list)

    def __post_init__(self) -> None:
        self.kms = [c.km_at for c in self.cands]

    @classmethod
    def of(
        cls, corridor: Corridor, fun: bool = False, secular: bool = False, sights: bool = True
    ) -> RestPool:
        return cls(rest_pool(corridor, fun, secular, sights), corridor.route)

    @classmethod
    def for_trip(cls, corridor: Corridor, inp: NormalizedInput, ctx: PlanContext) -> RestPool:
        """The trip's rest pool: fun stops for «Весело», no sights for «Только доехать»."""
        return cls.of(
            corridor, inp.mood is Mood.FUN, bool(ctx.cfg.sights.diversity), inp.mood is not Mood.JUST_DRIVE
        )

    def between(self, lo: float, hi: float) -> list[Candidate]:
        return self.cands[bisect.bisect_left(self.kms, lo) : bisect.bisect_right(self.kms, hi)]


@dataclass(slots=True)
class _Gap:
    i0: int  # index of the break stop b0
    t0: float  # clock at b0 (arrival)
    km0: float
    t1: float  # clock at b1 (arrival) or at the day end
    km1: float


def _first_long_gap(
    day: DayPlan, clock: DriveClock, r: float, min_dwell: int, accepted: set[tuple[int, int]]
) -> _Gap | None:
    """The first gap between consecutive breaks longer than R, skipping gaps closed by a break this stage
    placed after R (widened/extended windows end at R + 15 / R + 30, `accepted` holds those pairs)."""
    marks = [
        (clock.t_arr[i], day.stops[i].km_at, i) for i, s in enumerate(day.stops) if is_break(s, min_dwell)
    ]
    for j, (t0, km0, i0) in enumerate(marks):
        t1 = marks[j + 1][0] if j + 1 < len(marks) else clock.t_arr[-1]
        km1 = marks[j + 1][1] if j + 1 < len(marks) else day.km_end
        if j + 1 < len(marks) and (id(day.stops[i0]), id(day.stops[marks[j + 1][2]])) in accepted:
            continue
        if t1 - t0 > r + EPS:  # a break exactly R after the previous one is on time
            return _Gap(i0, t0, km0, t1, km1)
    return None


def _upgrade_fuel(
    day: DayPlan, gap: _Gap, clock: DriveClock, r: float, ctx: PlanContext, profile: Profile, strict: bool
) -> PlannedStop | None:
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
        return None
    k = best[1]
    old = day.stops[k]
    day.stops[k] = dataclasses.replace(old, coffee=True, dwell_min=ctx.cfg.dwell_min.fuel_coffee)
    if not strict or day_valid(day, ctx, profile):
        return day.stops[k]
    day.stops[k] = old
    return None


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
    added: list[PlannedStop] = []
    taken = set(used)
    accepted: set[tuple[int, int]] = set()
    # ADR-0015 §5: «подходящей площадки рядом нет» once a day; later breaks say only «Перерыв 15 минут»
    roadside_done = any(s.reason_key == "rest.roadside" for s in day.stops)
    last_roadside: float | None = None
    for _guard in range(200):
        clock = DriveClock.of(day, profile)
        gap = _first_long_gap(day, clock, r, rc.break_min_dwell, accepted)
        if gap is None:
            break
        x = clock.km_of(gap.t0 + r, gap.km0, gap.km1)
        if clock.t_arr[-1] - (gap.t0 + r) < rc.min_remaining_drive_min:
            break
        b0 = day.stops[gap.i0]
        coffee = _upgrade_fuel(day, gap, clock, r, ctx, profile, strict)
        if coffee is not None:
            accepted.add((id(b0), id(coffee)))
            continue
        need_after = min(g, gap.t1 - gap.t0 - r)

        def drive_since(c: Candidate, gap: _Gap = gap, clock: DriveClock = clock) -> float | None:
            """Driving since b0 at arrival for an unused candidate inside the day, else None."""
            if c.place.id in taken or not (day.km_start < c.km_at < day.km_end):
                return None
            if c.place.type is PlaceType.SIGHT and not sight_break_ok(c.place, day, inp, ctx):
                return None
            return clock.at(c.km_at) + c.detour_min / 2 - gap.t0

        def admissible(
            c: Candidate,
            d0: float,
            gap: _Gap = gap,
            clock: DriveClock = clock,
            need_after: float = need_after,
            fun_limit: int = FUN_DETOUR_MIN,
        ) -> bool:
            limit = fun_limit if is_fun(c, inp) else rc.max_detour_min
            if c.detour_min > limit or d0 < g - EPS:
                return False
            if inp.crew.children == 0 and c.place.quality is not None and Tag.PLAYGROUND in c.place.tags:
                return False  # M9: an open-data playground is a break only for a child
            if c.place.type is PlaceType.SIGHT and ctx.cfg.sights.diversity:
                from verst_planner.pipeline.sights import diversity_ok

                if not diversity_ok(day, c):  # a sight as a break follows the same kind rules
                    return False
            return gap.t1 - clock.at(c.km_at) >= need_after - EPS

        span = [(c, d0) for c in pool.between(gap.km0, gap.km1) if (d0 := drive_since(c)) is not None]
        scored = [(c, d0) for c, d0 in span if admissible(c, d0)]
        windows = [
            [(c, d0) for c, d0 in scored if r - rc.window_before_min - EPS <= d0 <= r + EPS],
            [
                (c, d0)
                for c, d0 in scored
                if max(g, r - rc.widen_before_min) - EPS <= d0 <= r + rc.widen_after_min + EPS
            ],
            # step 3 (A§16.11.1): extended window and detour
            [
                (c, d0)
                for c, d0 in span
                if c.detour_min <= rc.extended_detour_min
                and max(float(EXTENDED_MIN_DRIVE), r - rc.widen_before_min) - EPS
                <= d0
                <= r + EXTENDED_AFTER + EPS
            ],
        ]
        if inp.mood is Mood.FUN:
            # ADR-0015 §5: an interesting stop in the widened window beats a plain rest area in the narrow one
            # (`rest_score` carries the fun bonus); the extended window stays the last resort
            near = _union(windows[0], windows[1])
            if not any(is_fun(c, inp) for c, _d in near):  # M8: nothing within 15 min → up to 30 min
                wide = [
                    (c, d0)
                    for c, d0 in span
                    if is_fun(c, inp)
                    and admissible(c, d0, fun_limit=FUN_DETOUR_FALLBACK_MIN)
                    and max(g, r - rc.widen_before_min) - EPS <= d0 <= r + rc.widen_after_min + EPS
                ]
                near = _union(near, wide)
            windows = [near, windows[2]]
        chosen = None
        for cands in windows:
            for c, d0 in rank_rests(cands, inp, r):
                stop = make_rest_stop(c, inp, ctx, d0)
                if _open_at_eta(day, stop, ctx, profile) and (
                    not strict or _keeps_day_valid(day, stop, ctx, profile)
                ):
                    chosen = stop
                    break
            if chosen is not None:
                break
        if chosen is None:  # step 4: a roadside break at x, never a gap left unfilled
            if last_roadside is not None and abs(last_roadside - x) < 0.01:
                break  # the break did not shorten the gap (x inside a long detour): one is enough
            chosen = roadside_break(x, pool, ctx, again=roadside_done)
            roadside_done = True
            last_roadside = x
        insert_stop(day, chosen)
        accepted.add((id(b0), id(chosen)))
        if chosen.place is not None:
            taken.add(chosen.place.id)
        added.append(chosen)
    return added


def _union(
    a: list[tuple[Candidate, float]], b: list[tuple[Candidate, float]]
) -> list[tuple[Candidate, float]]:
    seen = {id(c) for c, _d in a}
    return a + [(c, d) for c, d in b if id(c) not in seen]


def rank_rests(
    cands: list[tuple[Candidate, float]], inp: NormalizedInput, r: float
) -> list[tuple[Candidate, float]]:
    """Rest candidates (with driving since the break) by `rest_score` desc, tie: closer to R, then id."""
    return sorted(cands, key=lambda cd: (-round(rest_score(cd[0], inp), 9), abs(cd[1] - r), cd[0].place.id))


def roadside_break(km: float, pool: RestPool, ctx: PlanContext, again: bool = False) -> PlannedStop:
    """A§16.11.1 step 4: a 15-min stop on the road where no place fits (`label.roadside_break`); `again`
    (a second one that day) drops the «площадки рядом нет» sentence (ADR-0015 §5)."""
    assert pool.route is not None
    point = interpolate(pool.route, km)
    name = roadside_name(km, point, pool.route, ctx) if ctx.cfg.sights.diversity else None
    return PlannedStop(
        kind=StopKind.REST,
        km_at=km,
        name_ru=name or ru.text("label.roadside_break"),
        point=point,
        dwell_min=ctx.cfg.rest.break_min_dwell,
        auto=True,
        reason_key="rest.roadside_again" if again else "rest.roadside",
        region_code=ctx.region_at(point).code,
        pool="rest",
    )


ROADSIDE_TOWN_KM = 15.0


def roadside_name(
    km: float, point: LatLon, route: Route | None, ctx: PlanContext, base: str | None = None
) -> str:
    """M9 (spec 5.5 §10.4): never a bare roadside label (`base`: a synthetic rest area or fuel station name,
    else the break label) — the nearest corridor town within ROADSIDE_TOWN_KM (`label.place_near`), else
    the road and its km (`label.place_road`), else the km (`label.place_km`)."""
    base = base or ru.text("label.roadside_break")
    near = [
        (haversine_km(t.town.point, point), t.town.id, t.town)
        for t in ctx.corridor_towns
        if haversine_km(t.town.point, point) <= ROADSIDE_TOWN_KM
    ]
    if near:
        town = min(near)[2]
        return ru.text("label.place_near", base=base, town=ru.genitive(town))
    ref = _road_ref_at(route, km) if route is not None else None
    if ref:
        return ru.text("label.place_road", base=base, road=ref, km=round(km))
    return ru.text("label.place_km", base=base, km=round(km))


def _road_ref_at(route: Route, km: float) -> str | None:
    i = bisect.bisect_left(route.cum_km, km)
    for d in route.details:
        if d.from_idx <= i <= d.to_idx and d.road_ref:
            return d.road_ref
    return None


def sight_break_ok(p: Place, day: DayPlan, inp: NormalizedInput, ctx: PlanContext) -> bool:
    """A sight as a break follows the stage-9 day rules (acceptance 2026-10-28 K1): not an open-data sight
    on the way out of or into the overnight town, and under the `sights_free` lever only a curated free
    place or an open public space."""
    from verst_planner.pipeline.sights import lever_free_ok, near_day_ends

    if near_day_ends(p, day, inp, ctx.cfg):
        return False
    return not (ctx.knobs.sights_free and not lever_free_ok(p, inp))


def plan_rests(days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext) -> None:
    """Stage 7 over every day (runs after lunch and sights, A§16.2)."""
    profile = ctx.profile_for(corridor.route)
    used = {s.place.id for d in days for s in d.stops if s.place is not None}
    pool = RestPool.for_trip(corridor, inp, ctx)
    for day in days:
        for s in plan_rests_day(day, pool, used, inp, ctx, profile):
            if s.place is not None:
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
