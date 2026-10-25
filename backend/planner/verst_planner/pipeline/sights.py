"""Stage 9: sights within the day's time budget and opening hours (A§6.9, SPEC §7.2 step 9), and stage 8b:
lunch for days that still have none after the sights (A§16.2).

Feasibility (`day_ok`) is evaluated on a copy of the day with its rests planned, so sights can never push
rests out of the budget (A§16.2); the budget rule is A§16.5 (`max(day_budget_min, mandatory_min)`).
"""

from __future__ import annotations

import math
import re

from verst_planner.domain.enums import Mood, Source, StopKind, Tag
from verst_planner.domain.model import Candidate, DayPlan, NormalizedInput, Place, PlannedStop, Town
from verst_planner.explain import ru
from verst_planner.explain.reasons import sight_reason
from verst_planner.geo.distance import haversine_km
from verst_planner.pipeline import Corridor, PlanContext
from verst_planner.pipeline.meals import best_lunch, lunch_candidates, needs_lunch, plan_meals
from verst_planner.pipeline.rest import RestPool, day_ok
from verst_planner.pipeline.timeline import Profile, insert_stop

NOTABLE = frozenset({Tag.KREMLIN, Tag.MONASTERY, Tag.MUSEUM, Tag.VIEW})

# ADR-0015 §2 — quality, transit and diversity rules for road-trip sights.
MIN_QUALITY = 0.40  # an open-data sight on the road
MIN_QUALITY_FAR = 0.55  # … with a detour over FAR_DETOUR_KM
FAR_DETOUR_KM = 10.0
BIG_CITY_POPULATION = 1_000_000
BIG_CITY_CENTRE_KM = 12.0  # no transit sight this close to a million-city centre
OWN_CITY_KM = 25.0  # a big city counts as the trip's own when an origin/destination/via is this close
SAME_SPOT_KM = 0.4  # two sights closer than this are one stop
RELIGIOUS = frozenset({"temple", "monastery", "church"})
RELIGIOUS_SHARE = 0.30  # of the trip's non-template sights
RELIGIOUS_NAME = re.compile(r"(?i)\b(" + "|".join(ru.words("sight.religious_name")) + ")")
TAG_CATEGORY = (
    (Tag.KREMLIN, "kremlin"),
    (Tag.MONASTERY, "monastery"),
    (Tag.MUSEUM, "museum"),
    (Tag.VIEW, "viewpoint"),
    (Tag.PLAYGROUND, "playground"),
    (Tag.WALK, "park"),
)


def category_of(p: Place) -> str:
    """The ADR-0015 kind of a sight: the catalogue's, else from the curated tags and name."""
    if p.category is not None:
        return p.category
    if RELIGIOUS_NAME.search(p.name_ru) and Tag.MONASTERY not in p.tags:
        return "temple"
    return next((cat for tag, cat in TAG_CATEGORY if tag in p.tags), "attraction")


def quality_ok(c: Candidate) -> bool:
    q = c.place.quality
    if q is None:
        return True
    return q >= (MIN_QUALITY_FAR if c.detour_km > FAR_DETOUR_KM else MIN_QUALITY)


def own_big_cities(inp: NormalizedInput, corridor: Corridor, days: list[DayPlan]) -> set[str]:
    """Million-cities the trip starts, ends, stops over or passes a via in: their centres are allowed."""
    pts = [inp.origin.point, *(v.point for v in inp.vias)]
    if inp.destination is not None:
        pts.append(inp.destination.point)
    nights = {s.town.id for d in days for s in d.stops if s.town is not None and s.kind is not StopKind.SIGHT}
    out = set()
    for tc in corridor.towns:
        t = tc.town
        if t.population >= BIG_CITY_POPULATION and (
            t.id in nights or any(haversine_km(t.point, p) <= OWN_CITY_KM for p in pts)
        ):
            out.add(t.id)
    return out


def big_city_centres(corridor: Corridor) -> list[Town]:
    return [tc.town for tc in corridor.towns if tc.town.population >= BIG_CITY_POPULATION]


def in_foreign_centre(c: Candidate, centres: list[Town], own: set[str]) -> bool:
    return any(
        t.id not in own and haversine_km(t.point, c.place.point) <= BIG_CITY_CENTRE_KM for t in centres
    )


def _day_sights(day: DayPlan) -> list[PlannedStop]:
    return [s for s in day.stops if s.kind is StopKind.SIGHT and s.place is not None]


def diversity_ok(day: DayPlan, c: Candidate, on: bool = True) -> bool:
    """≤ 1 religious place per 3 sights of the day, never two sights of the same kind in a row, and never a
    second sight within `SAME_SPOT_KM` of one already in the day.

    `on` is the `sights.diversity` config: on for the open-data world, off for the curated fixture worlds
    (G01-G13 keep their bytes)."""
    if not on:
        return True
    cat = category_of(c.place)
    sights = sorted([*_day_sights(day)], key=lambda s: s.km_at)
    if any(haversine_km(s.point, c.place.point) < SAME_SPOT_KM for s in sights):
        return False  # one stop covers both (Красная площадь and the Mausoleum on it)
    before = [s for s in sights if s.km_at <= c.km_at]
    after = [s for s in sights if s.km_at > c.km_at]
    for nb in before[-1:] + after[:1]:
        assert nb.place is not None
        if category_of(nb.place) == cat:
            return False
    if cat in RELIGIOUS:
        religious = sum(1 for s in sights if s.place is not None and category_of(s.place) in RELIGIOUS)
        if religious + 1 > math.ceil((len(sights) + 1) / 3):
            return False
    return True


def _religious(s: PlannedStop) -> bool:
    return s.place is not None and category_of(s.place) in RELIGIOUS


def trip_religious_repair(days: list[DayPlan]) -> None:
    """Drop the lowest-scored droppable religious sights until they are ≤ 30 % of non-template sights."""
    while True:
        rows = [(d, i) for d in days for i in droppable_sights(d)]
        if not rows:
            return
        rel = [(d, i) for d, i in rows if _religious(d.stops[i])]
        if len(rel) <= RELIGIOUS_SHARE * len(rows):
            return
        d, i = min(rel, key=lambda r: (r[0].stops[r[1]].score, -r[0].stops[r[1]].km_at))
        d.stops.pop(i)


def sight_score(c: Candidate, inp: NormalizedInput) -> float:
    t = c.place.tags
    return (
        c.place.rating_internal
        + 0.5 * bool(NOTABLE & t)
        + 0.5 * (c.place.source is Source.CURATED)
        + 0.5 * (Tag.WALK in t and inp.crew.dog)
        + 0.5 * (Tag.PLAYGROUND in t and inp.crew.children > 0)
        - c.detour_min / 15
    )


def is_paid(c: Candidate, inp: NormalizedInput) -> bool:
    """ADR-0011 `sights_free`: a ticket costs this crew money (`free_entry` / no price = free)."""
    p = c.place
    if Tag.FREE_ENTRY in p.tags or not p.ticket_adult_rub:
        return False
    child = p.ticket_child_rub if p.ticket_child_rub is not None else p.ticket_adult_rub
    return inp.crew.adults * p.ticket_adult_rub + inp.crew.children * child > 0


def make_sight_stop(c: Candidate, inp: NormalizedInput, ctx: PlanContext) -> PlannedStop:
    dwell = c.place.dwell_min or ctx.cfg.dwell_min.sight_default
    key, params = sight_reason(dwell, inp.crew, c.place.source)
    return PlannedStop(
        kind=StopKind.SIGHT,
        km_at=c.km_at,
        name_ru=c.place.name_ru,
        point=c.place.point,
        place=c.place,
        detour_km=c.detour_km,
        detour_min=c.detour_min,
        dwell_min=dwell,
        score=sight_score(c, inp),
        reason_key=key,
        reason_params=params,
        region_code=c.region_code,
        pool="sight",
    )


def _used(days: list[DayPlan]) -> set[str]:
    return {s.place.id for d in days for s in d.stops if s.place is not None}


def plan_sights(
    days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext, frozen: bool = False
) -> None:
    """Add sights by score while the day stays feasible; `frozen` (the re-run) keeps the current ones."""
    if frozen or inp.simplify or inp.mood is Mood.JUST_DRIVE:
        return
    profile = ctx.profile_for(corridor.route)
    max_n = ctx.cfg.sights.max_per_day.of(inp.mood)
    used = _used(days)
    rests = RestPool.of(corridor, inp.mood is Mood.FUN)
    centres = big_city_centres(corridor)
    own = own_big_cities(inp, corridor, days)
    for day in days:
        n = sum(1 for s in day.stops if s.kind is StopKind.SIGHT and s.fixed)
        pool = [
            c
            for c in corridor.sights
            if day.km_start < c.km_at < day.km_end
            and c.place.id not in used
            and sight_score(c, inp) >= ctx.cfg.sights.min_score
            and not (ctx.knobs.sights_free and is_paid(c, inp))
            and quality_ok(c)
            and not in_foreign_centre(c, centres, own)
        ]
        pool.sort(key=lambda c: (-round(sight_score(c, inp), 9), c.km_at, c.place.id))
        for c in pool:
            if n >= max_n:
                break
            if c.place.id in used or not diversity_ok(day, c, bool(ctx.cfg.sights.diversity)):
                continue
            stop = make_sight_stop(c, inp, ctx)
            i = insert_stop(day, stop)
            if day_ok(day, inp, ctx, profile, rests, used | {c.place.id}):
                n += 1
                used.add(c.place.id)
            else:
                day.stops.pop(i)
    if ctx.cfg.sights.diversity:
        trip_religious_repair(days)


def droppable_sights(day: DayPlan) -> list[int]:
    """Stage-9 sights (never fixed template sights, user vias or short sights used as rests)."""
    return [
        i for i, s in enumerate(day.stops) if s.kind is StopKind.SIGHT and s.pool == "sight" and not s.fixed
    ]


def lowest_sight(day: DayPlan) -> int:
    """The droppable sight with the lowest score (tie: the later one)."""
    return min(droppable_sights(day), key=lambda i: (day.stops[i].score, -day.stops[i].km_at))


def plan_lunches(days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext) -> None:
    """Stage 8 with the lunch probes checked by `day_ok` (rests reserved)."""
    profile = ctx.profile_for(corridor.route)
    rests = RestPool.of(corridor, inp.mood is Mood.FUN)
    used = _used(days)
    plan_meals(days, corridor, inp, ctx, ok=lambda d: day_ok(d, inp, ctx, profile, rests, used))


def lunch_after_sights_day(
    day: DayPlan,
    corridor: Corridor,
    inp: NormalizedInput,
    ctx: PlanContext,
    profile: Profile,
    used: set[str],
    rests: RestPool,
) -> None:
    """Stage 8b for one day: plan the lunch; if none fits, drop stage-9 sights (lowest score first, tie:
    later km) one at a time until a lunch fits (A§16.2). The drops are simulated on a copy first: when no
    lunch fits even with every droppable sight gone (no feasible food place on the day's corridor), the
    sights are kept and the day goes without a lunch stop (it is still costed, A§7.1)."""

    def cands(d: DayPlan) -> list[tuple[float, PlannedStop]]:
        if not needs_lunch(d, ctx, profile):
            return []
        return lunch_candidates(
            d, corridor, inp, ctx, profile, used, ok=lambda x: day_ok(x, inp, ctx, profile, rests, used)
        )

    if not needs_lunch(day, ctx, profile):
        return
    trial = DayPlan(day.day, day.km_start, day.km_end, day.start_at, list(day.stops), day.tz)
    dropped: list[PlannedStop] = []
    found = cands(trial)
    while not found and droppable_sights(trial) and needs_lunch(trial, ctx, profile):
        dropped.append(trial.stops.pop(lowest_sight(trial)))
        found = cands(trial)
    if not found:
        return
    day.stops[:] = trial.stops
    for s in dropped:
        if s.place is not None:
            used.discard(s.place.id)
    best = best_lunch(found)
    insert_stop(day, best)
    assert best.place is not None
    used.add(best.place.id)


def plan_lunch_after_sights(
    days: list[DayPlan], corridor: Corridor, inp: NormalizedInput, ctx: PlanContext
) -> None:
    """Stage 8b over every day still without a lunch that now overlaps the lunch window."""
    profile = ctx.profile_for(corridor.route)
    used = _used(days)
    rests = RestPool.of(corridor, inp.mood is Mood.FUN)
    for day in days:
        lunch_after_sights_day(day, corridor, inp, ctx, profile, used, rests)
