"""Stage 9: sights within the day's time budget and opening hours (A§6.9, SPEC §7.2 step 9), and stage 8b:
lunch for days that still have none after the sights (A§16.2).

Feasibility (`day_ok`) is evaluated on a copy of the day with its rests planned, so sights can never push
rests out of the budget (A§16.2); the budget rule is A§16.5 (`max(day_budget_min, mandatory_min)`).
"""

from __future__ import annotations

import dataclasses
import itertools
import math
import re
from datetime import timedelta

from verst_planner.domain.enums import Meal, Mood, Source, StopKind, Tag
from verst_planner.domain.facts import confirmed_free, rank_rating
from verst_planner.domain.model import Candidate, DayPlan, NormalizedInput, Place, PlannedStop, Town
from verst_planner.explain import ru
from verst_planner.explain.reasons import sight_reason
from verst_planner.geo.distance import haversine_km
from verst_planner.pipeline import Corridor, PlanContext
from verst_planner.pipeline.meals import best_lunch, lunch_candidates, needs_lunch, plan_meals
from verst_planner.pipeline.rest import RestPool, day_ok
from verst_planner.pipeline.timeline import Profile, insert_stop, local, schedule_day

NOTABLE = frozenset({Tag.KREMLIN, Tag.MONASTERY, Tag.MUSEUM, Tag.VIEW})

# ADR-0015 §2 — quality, transit and diversity rules for road-trip sights.
MIN_QUALITY = 0.40  # an open-data sight on the road
MIN_QUALITY_FAR = 0.55  # … with a detour over FAR_DETOUR_KM
FAR_DETOUR_KM = 10.0
BIG_CITY_POPULATION = 1_000_000
MEGACITY_POPULATION = 4_000_000  # Москва, Санкт-Петербург: never a transit sight in the centre
BIG_CITY_CENTRE_KM = 12.0  # no transit sight this close to a million-city centre
OWN_CITY_KM = 25.0  # a big city counts as the trip's own when an origin/destination/via is this close
SAME_SPOT_KM = 0.4  # two sights closer than this are one stop
# Manager M8 (ADR-0015 §2 addendum): a tiered detour budget, so the motorways (M-12, M-4) that bypass the
# towns still get their quality sights. The detour counts inside the day limits like any stop time.
TOP_QUALITY, TOP_DETOUR_MIN = 0.70, 45  # at most TOP_PER_DAY such long detours a day
MID_QUALITY, MID_DETOUR_MIN = 0.55, 25
TOP_PER_DAY = 1
SAME_TOWN_KM = 2.0  # a café this close to a sight is «in its town» for the moved lunch
AFTER_SIGHT_KM = 0.01
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


def _words(key: str) -> re.Pattern[str]:
    return re.compile(r"(?i)(?:^|[\s«\"(-])(?:" + "|".join(map(re.escape, ru.words(key))) + ")")


# M9 name rules, first match wins: a heritage temple is «Храм», gates and monuments are «Памятник», a museum
# only when it is primarily one («Золотые ворота» are a monument, «Церковь Покрова на Нерли» a temple)
VIEW_START = re.compile(
    r"(?i)^(?:" + "|".join(map(re.escape, ru.words("sight.kind_words.viewpoint_start"))) + ")"
)
NAME_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (_words("sight.kind_words.museum"), "museum"),
    (_words("sight.kind_words.pavilion"), "attraction"),  # a pavilion called a temple is not one
    (_words("sight.kind_words.monastery"), "monastery"),
    (_words("sight.kind_words.temple"), "temple"),  # a cathedral inside a kremlin is a temple
    (_words("sight.kind_words.kremlin"), "kremlin"),
    (_words("sight.kind_words.monument"), "monument"),
    (_words("sight.kind_words.nature"), "nature"),
    (_words("sight.kind_words.embankment"), "embankment"),
    (_words("sight.kind_words.square"), "square"),
    (_words("sight.kind_words.park"), "park"),
)
STRONG_KINDS = frozenset({"playground", "zoo", "theatre", "interactive", "monastery"})
MUSEUM_DESC = _words("sight.kind_words.museum")


def kind_of(name: str, base: str, desc: str | None = None) -> str:
    """The category of a sight from its base kind (catalogue class or curated tags) and its name.

    Strong classes (playground, zoo, theatre, interactive, monastery) stay. Otherwise a view
    (a «Смотровая» by a cathedral) is a viewpoint, then the first name rule wins, then an open-data park
    or nature item described as a museum is a museum (Коломенское, a museum-reserve)."""
    base = POI_CATEGORY_OF.get(base, base)
    if base in STRONG_KINDS:
        return base
    if VIEW_START.search(name):
        return "viewpoint"
    for rx, kind in NAME_RULES:
        if rx.search(name):
            return kind
    if desc and base in ("nature", "park", "attraction") and MUSEUM_DESC.search(desc):
        return "museum"
    if base == "kremlin":  # a castle class without «кремль» in the name (Майендорф, Михайловский замок)
        return "attraction"
    return base


POI_CATEGORY_OF = {"church": "temple"}


NOT_A_SIGHT = _words("sight.not_a_sight")
NOT_A_SIGHT_UNLESS_Q = 0.60


def not_a_sight(p: Place) -> bool:
    """M9: a philharmonic, concert hall or house of culture is not a road-trip sight unless it is heritage
    AND of quality ≥ 0.60 (open-data places; curated ones were picked by hand)."""
    if p.quality is None or not NOT_A_SIGHT.search(p.name_ru):
        return False
    return not (p.heritage and p.quality >= NOT_A_SIGHT_UNLESS_Q)


def category_of(p: Place) -> str:
    """The ADR-0015 kind of a sight (M9: one rule for the card label and the diversity rules)."""
    if p.category is not None:
        base = p.category
        desc = p.description_ru if p.source is Source.OSM else None
    else:
        base = next((cat for tag, cat in TAG_CATEGORY if tag in p.tags), "attraction")
        desc = None
    return kind_of(p.name_ru, base, desc)


def effective_quality(p: Place) -> float:
    """Open-data quality, or a curated place's rating on the same 0..1 scale (3.6 → 0, 4.9 → 1)."""
    if p.quality is not None:
        return p.quality
    return max(0.0, min(1.0, (rank_rating(p) - 3.6) / 1.3))


def detour_ok(c: Candidate) -> bool:
    """The tiered detour budget (open-data world): q ≥ 0.70 up to 45 min, q ≥ 0.55 up to 25 min, else
    the plain rule (`quality_ok`: a detour of at most FAR_DETOUR_KM)."""
    if c.place.quality is not None and c.place.quality < MIN_QUALITY:
        return False
    q = effective_quality(c.place)
    if q >= TOP_QUALITY:
        return c.detour_min <= TOP_DETOUR_MIN
    if q >= MID_QUALITY:
        return c.detour_min <= MID_DETOUR_MIN
    return c.detour_km <= FAR_DETOUR_KM


def long_detour(c: Candidate | PlannedStop) -> bool:
    return c.detour_min > MID_DETOUR_MIN


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


def in_foreign_centre(c: Candidate, centres: list[Town], own: set[str], tiered: bool = False) -> bool:
    """A transit sight in a million-city centre the trip does not start, end or stay in. `tiered` (M8):
    a top-quality sight within the 45-minute budget is let in (Казанский кремль, Нижегородский кремль),
    except in the megacities (Москва, Санкт-Петербург), whose centre traffic the detour model cannot see."""
    for t in centres:
        if t.id in own or haversine_km(t.point, c.place.point) > BIG_CITY_CENTRE_KM:
            continue
        if not (tiered and t.population < MEGACITY_POPULATION and effective_quality(c.place) >= TOP_QUALITY):
            return True
    return False


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
    if cat in RELIGIOUS and not signature(c.place):
        counted = [s.place for s in sights if s.place is not None and not signature(s.place)]
        religious = sum(1 for p in counted if category_of(p) in RELIGIOUS)
        if religious + 1 > math.ceil((len(counted) + 1) / 3):
            return False
    return True


def signature(p: Place) -> bool:
    """A hand-curated kremlin or monastery (Троице-Сергиева лавра, Ипатьевский монастырь, the Суздаль and
    Ростов kremlins): the ring's signature sites count first and are exempt from the religious cap, which
    applies only to the added open-data sights."""
    return p.source is Source.CURATED and category_of(p) in SIGNATURE_KINDS


SIGNATURE_KINDS = frozenset({"kremlin", "monastery"})


def _religious(s: PlannedStop) -> bool:
    return s.place is not None and category_of(s.place) in RELIGIOUS


def _capped(d: DayPlan) -> list[int]:
    """The stage-9 sights the religious cap counts (signature sites are not)."""
    out = []
    for i in droppable_sights(d):
        p = d.stops[i].place
        if p is None or not signature(p):
            out.append(i)
    return out


def trip_religious_repair(days: list[DayPlan]) -> None:
    """Drop the lowest-scored droppable religious sights until they are ≤ 30 % of non-template sights."""
    while True:
        rows = [(d, i) for d in days for i in _capped(d)]
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
        rank_rating(c.place)
        + 0.5 * bool(NOTABLE & t)
        + 0.5 * (c.place.source is Source.CURATED)
        + 0.5 * (Tag.WALK in t and inp.crew.dog)
        + 0.5 * (Tag.PLAYGROUND in t and inp.crew.children > 0)
        - c.detour_min / 15
    )


def is_paid(c: Candidate, inp: NormalizedInput) -> bool:
    """ADR-0011 `sights_free`: a ticket costs this crew money. ADR-0019 E-2: an unknown price is not
    free, so the «бесплатные места» lever does not keep it (only `free_entry` or a 0 ₽ ticket are free)."""
    p = c.place
    if confirmed_free(p):
        return False
    if p.ticket_adult_rub is None:
        return True
    child = p.ticket_child_rub if p.ticket_child_rub is not None else p.ticket_adult_rub
    return inp.crew.adults * p.ticket_adult_rub + inp.crew.children * child > 0


def make_sight_stop(c: Candidate, inp: NormalizedInput, ctx: PlanContext) -> PlannedStop:
    dwell = c.place.dwell_min or ctx.cfg.dwell_min.sight_default
    key, params = sight_reason(dwell, inp.crew, c.place)
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
    rests = RestPool.of(corridor, inp.mood is Mood.FUN, bool(ctx.cfg.sights.diversity))
    centres = big_city_centres(corridor)
    own = own_big_cities(inp, corridor, days)
    open_data = bool(ctx.cfg.sights.diversity)
    # open data: secular sights first over the whole trip, then the religious ones while the trip share
    # stays ≤ RELIGIOUS_SHARE (a lone church on a sparse road would only be dropped by the repair)
    for religious in (False, True) if open_data else (None,):
        for day in days:
            n = sum(1 for s in day.stops if s.kind is StopKind.SIGHT and (s.fixed or s.pool == "sight"))
            pool = [
                c
                for c in corridor.sights
                if day.km_start < c.km_at < day.km_end
                and c.place.id not in used
                and sight_score(c, inp) >= ctx.cfg.sights.min_score
                and not (ctx.knobs.sights_free and is_paid(c, inp))
                and (detour_ok(c) and not not_a_sight(c.place) if open_data else quality_ok(c))
                and not in_foreign_centre(c, centres, own, open_data)
                and (
                    religious is None
                    or (category_of(c.place) in RELIGIOUS and not signature(c.place)) == religious
                )
            ]
            if open_data:  # quality first, so a 45-minute Владимир is tried before a nearby bust
                pool.sort(key=lambda c: (not signature(c.place), -_open_score(c, inp), c.km_at, c.place.id))
            else:
                pool.sort(key=lambda c: (-round(sight_score(c, inp), 9), c.km_at, c.place.id))
            for c in pool:
                if n >= max_n:
                    break
                if c.place.id in used or not diversity_ok(day, c, open_data):
                    continue
                if open_data and long_detour(c) and _long_today(day) >= TOP_PER_DAY:
                    continue
                if religious and not _religious_room(days):
                    break
                stop = make_sight_stop(c, inp, ctx)
                i = insert_stop(day, stop)
                if (
                    day_ok(day, inp, ctx, profile, rests, used | {c.place.id})
                    or (open_data and _with_moved_lunch(day, stop, corridor, inp, ctx, profile, rests, used))
                    or (open_data and _with_later_start(day, stop, inp, ctx, profile, rests, used))
                ):
                    n += 1
                    used.add(c.place.id)
                else:
                    day.stops.pop(i)
    if ctx.cfg.sights.diversity:
        trip_religious_repair(days)
        adjacent_kind_repair(days)


def adjacent_kind_repair(days: list[DayPlan]) -> None:
    """After the drops, two sights of one kind can become neighbours: drop the lower-scored droppable one
    (never a template sight)."""
    for d in days:
        while True:
            sights = sorted(
                (i for i, s in enumerate(d.stops) if s.kind is StopKind.SIGHT and s.place is not None),
                key=lambda i: d.stops[i].km_at,
            )
            pair = next(
                (
                    (a, b)
                    for a, b in itertools.pairwise(sights)
                    if category_of(d.stops[a].place) == category_of(d.stops[b].place)  # type: ignore[arg-type]
                    and (_droppable(d.stops[a]) or _droppable(d.stops[b]))
                ),
                None,
            )
            if pair is None:
                break
            cands = [i for i in pair if _droppable(d.stops[i])]
            d.stops.pop(min(cands, key=lambda i: (d.stops[i].score, -d.stops[i].km_at)))


def _droppable(s: PlannedStop) -> bool:
    return s.pool == "sight" and not s.fixed


def _with_moved_lunch(
    day: DayPlan,
    stop: PlannedStop,
    corridor: Corridor,
    inp: NormalizedInput,
    ctx: PlanContext,
    profile: Profile,
    rests: RestPool,
    used: set[str],
) -> bool:
    """Open-data world: a sight that only fails because it pushes the lunch out of its window gets the lunch
    moved (re-planned with the sight in the day). True = the day keeps both; False = `day` is unchanged."""
    lunch = next((k for k, s in enumerate(day.stops) if s.meal is Meal.LUNCH and not s.fixed), None)
    if lunch is None:
        return False
    trial = DayPlan(day.day, day.km_start, day.km_end, day.start_at, list(day.stops), day.tz)
    old = trial.stops.pop(lunch)
    free = used - {old.place.id} if old.place is not None else set(used)
    free.add(stop.place.id if stop.place is not None else "")
    found = lunch_candidates(
        trial, corridor, inp, ctx, profile, free, ok=lambda x: day_ok(x, inp, ctx, profile, rests, free)
    )
    if not found and stop.place is not None:
        # a café in the sight's own town, taken after the visit (in Rostov the café before the kremlin is
        # 3 min before the lunch window, after the kremlin it is in it)
        after = [
            dataclasses.replace(c, km_at=stop.km_at + AFTER_SIGHT_KM)
            for c in corridor.food
            if haversine_km(c.place.point, stop.place.point) <= SAME_TOWN_KM and c.km_at <= stop.km_at
        ]
        if after:
            found = lunch_candidates(
                trial,
                dataclasses.replace(corridor, food=after),
                inp,
                ctx,
                profile,
                free,
                ok=lambda x: day_ok(x, inp, ctx, profile, rests, free),
            )
    if not found:
        return False
    best = best_lunch(found)
    insert_stop(trial, best)
    day.stops[:] = trial.stops
    if old.place is not None:
        used.discard(old.place.id)
    if best.place is not None:
        used.add(best.place.id)
    return True


LATER_START_MAX_MIN = 90  # the morning in the overnight town: wait at most this long for an opening
NEAR_START_KM = 5.0


def _with_later_start(
    day: DayPlan,
    stop: PlannedStop,
    inp: NormalizedInput,
    ctx: PlanContext,
    profile: Profile,
    rests: RestPool,
    used: set[str],
) -> bool:
    """Open-data world: a sight in the overnight town that is still closed when the day starts (the
    Суздаль kremlin opens at 10:00, the day at 09:00) moves the departure to its opening (≤ 90 min).
    The day's duration does not grow, so the pace stays. True = kept; False = `day` is unchanged."""
    if day.day == 1 or stop.place is None or stop.km_at - day.km_start > NEAR_START_KM:
        return False
    hours = ctx.hours(stop.place)
    if hours is None:
        return False
    slots = schedule_day(day, profile)
    k = day.stops.index(stop)
    arrive = slots[k].arrive
    if arrive is None:
        return False
    tz = ctx.tz_of(stop.region_code, stop.point)
    at = local(arrive, tz)
    minute = at.hour * 60 + at.minute
    opens = [lo for lo, _hi in hours.day_intervals(at.weekday()) if lo > minute]
    if not opens or opens[0] - minute > LATER_START_MAX_MIN:
        return False
    old = day.start_at
    day.start_at = old + timedelta(minutes=opens[0] - minute)
    if day_ok(day, inp, ctx, profile, rests, used | {stop.place.id}):
        return True
    day.start_at = old
    return False


def _religious_room(days: list[DayPlan]) -> bool:
    """One more religious stage-9 sight keeps the trip within RELIGIOUS_SHARE."""
    rows = [d.stops[i] for d in days for i in _capped(d)]
    rel = sum(1 for s in rows if _religious(s))
    return rel + 1 <= RELIGIOUS_SHARE * (len(rows) + 1)


def _open_score(c: Candidate, inp: NormalizedInput) -> float:
    """Open-data ranking: quality dominates, the detour costs a little (45 min ≈ 0.15 of quality), the crew
    fit a little more (a walk for the dog, a playground for the child)."""
    t = c.place.tags
    crew = 0.05 * (Tag.WALK in t and inp.crew.dog) + 0.05 * (Tag.PLAYGROUND in t and inp.crew.children > 0)
    return round(effective_quality(c.place) - c.detour_min / 300 + crew, 9)


def _long_today(day: DayPlan) -> int:
    return sum(1 for s in day.stops if s.kind is StopKind.SIGHT and not s.fixed and long_detour(s))


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
    rests = RestPool.of(corridor, inp.mood is Mood.FUN, bool(ctx.cfg.sights.diversity))
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
    rests = RestPool.of(corridor, inp.mood is Mood.FUN, bool(ctx.cfg.sights.diversity))
    for day in days:
        lunch_after_sights_day(day, corridor, inp, ctx, profile, used, rests)
