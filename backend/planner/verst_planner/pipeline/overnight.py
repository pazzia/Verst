"""Stage 5: overnight choice with the fallback chain F1 → F2 → F3 → F4 [D-4] (A§6.5, SPEC §7.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from verst_planner.domain.enums import OvernightFallback, Tag, WarningCode
from verst_planner.domain.facts import rank_rating
from verst_planner.domain.model import (
    Candidate,
    NormalizedInput,
    OvernightChoice,
    PlanWarning,
    ScoredTown,
    TownCandidate,
)
from verst_planner.domain.rooms import room_plan
from verst_planner.explain import ru
from verst_planner.geo.distance import haversine_km
from verst_planner.geo.polyline import interpolate
from verst_planner.pipeline import Corridor, PlanContext, round_half_up
from verst_planner.pipeline.day_split import EPS, DaySplit, passes
from verst_planner.pipeline.timeline import Profile

PARKING_TAGS = frozenset({Tag.PARKING, Tag.PARKING_GUARDED})
HOTEL_CENTRE_KM = 2.0
EVENING_AFTER_ARRIVAL_MIN = 60
W_PRICE = 0.5  # ADR-0011 `lodging_cheap`: score points per 1 000 ₽ of the cheapest night


@dataclass(slots=True)
class OvernightResult:
    choices: list[OvernightChoice]
    warnings: list[PlanWarning] = field(default_factory=list)

    @property
    def n_days(self) -> int:
        return len(self.choices) + 1


def h_fit(passing: list[Candidate], ctx: PlanContext) -> float:
    s = ctx.cfg.overnight_score
    total = sum(1.0 if PARKING_TAGS & h.place.tags else s.h_no_parking_weight for h in passing)
    return min(float(s.h_cap), total)


def hotel_score(h: Candidate, tc: TownCandidate) -> float:
    p = h.place
    return (
        rank_rating(p)
        + (0.5 if Tag.PARKING_GUARDED in p.tags else 0.0)
        + (0.3 if haversine_km(p.point, tc.town.point) <= HOTEL_CENTRE_KM else 0.0)
        - (p.price_night_rub or 0) / 10000
    )


def night_cost(h: Candidate, inp: NormalizedInput, ctx: PlanContext) -> int:
    """Rooms x price of one night for the crew (family rooms when that lever is on, ADR-0011)."""
    rooms, price, _explicit = room_plan(h.place, inp.crew, ctx.knobs.family_rooms)
    return rooms * price


def rank_hotels(
    passing: list[Candidate],
    tc: TownCandidate,
    inp: NormalizedInput | None = None,
    ctx: PlanContext | None = None,
) -> list[Candidate]:
    if inp is not None and ctx is not None and ctx.knobs.lodging_cheap:
        # ADR-0011 lever 1: the cheapest night for this crew first, then the usual hotel score
        return sorted(passing, key=lambda h: (night_cost(h, inp, ctx), -hotel_score(h, tc), h.place.id))
    return sorted(passing, key=lambda h: (-hotel_score(h, tc), h.place.price_night_rub or 0, h.place.id))


def day_start_estimate(d: int, inp: NormalizedInput, ctx: PlanContext) -> datetime:
    """Start of day `d` before scheduling: day 1 = `start_at`, later days 09:00 on the following dates."""
    if d == 1:
        return inp.start_at
    zone = ZoneInfo(inp.tz)
    first = inp.start_at.astimezone(zone)
    day = (first + timedelta(days=d - 1)).replace(
        hour=ctx.cfg.day_start_next.hour, minute=ctx.cfg.day_start_next.minute, second=0, microsecond=0
    )
    return day


def anchor(tc: TownCandidate, ctx: PlanContext) -> bool:
    """Acceptance 2026-10-28 (K2): an «anchor town» of the open-data world — a city of at least
    `big_town_population` (Владимир, Нижний Новгород, Чебоксары, Тверь, Великий Новгород). It is searched
    within `corridor_km.town_big`, may end a day farther than the even split wants (up to the daily cap)
    and scores `w_big_town` more: a family should not sleep in Кстово, 20 km from Нижний."""
    s = ctx.cfg.overnight_score
    return bool(s.anchors) and tc.town.population >= s.big_town_population


@dataclass(slots=True)
class _Scorer:
    corridor: Corridor
    inp: NormalizedInput
    ctx: PlanContext
    profile: Profile

    def passing(self, tc: TownCandidate) -> list[Candidate]:
        return [h for h in tc.lodgings if passes(h, self.inp.crew, self.ctx)]

    def evening(self, tc: TownCandidate, eta: datetime) -> int:
        if tc.town.evening_walk:
            return 1
        tz = self.ctx.tz_of(tc.town.region_code, tc.town.point)
        at = (eta + timedelta(minutes=EVENING_AFTER_ARRIVAL_MIN)).astimezone(ZoneInfo(tz))
        for c in self.corridor.sights:
            if c.place.town_id == tc.town.id and Tag.EVENING in c.place.tags:
                hours = self.ctx.hours(c.place)
                if hours is None or hours.is_open(at):
                    return 1
        return 0

    def score(
        self, tc: TownCandidate, target: float, prev_km: float, day: int, with_h: bool = True
    ) -> ScoredTown:
        s = self.ctx.cfg.overnight_score
        passing = self.passing(tc)
        h = h_fit(passing, self.ctx) if with_h else 0.0
        q = tc.town.quality
        eta = day_start_estimate(day, self.inp, self.ctx) + timedelta(
            minutes=self.profile.drive(prev_km, tc.km_at)
            + self.ctx.cfg.overnight_eta_allowance_min.of(self.inp.mood)
        )
        e = self.evening(tc, eta)
        det = min(x.detour_min for x in passing) if passing else tc.detour_min
        total = (
            s.w_h * h + s.w_q * q + s.w_e * e - s.w_km * abs(tc.km_at - target) / 100 - s.w_detour * det / 15
        )
        if self.ctx.knobs.lodging_cheap and passing:
            total -= W_PRICE * min(night_cost(x, self.inp, self.ctx) for x in passing) / 1000
        if anchor(tc, self.ctx):
            total += s.w_big_town
        return ScoredTown(tc.town, tc.km_at, total, h, q, e, det)


def _choice(
    day: int,
    tc: TownCandidate,
    scorer: _Scorer,
    considered: list[ScoredTown],
    fallback: OvernightFallback,
    score: float,
    target: float,
    with_hotel: bool = True,
) -> OvernightChoice:
    ranked = rank_hotels(scorer.passing(tc), tc, scorer.inp, scorer.ctx) if with_hotel else []
    hotel = ranked[0] if ranked else None
    point = hotel.place.point if hotel else tc.town.point
    if hotel is not None:
        dkm, dmin = hotel.detour_km, hotel.detour_min
    else:
        dkm, dmin = 2.0 * tc.lateral_km * scorer.ctx.cfg.detour.winding, tc.detour_min
    return OvernightChoice(
        day=day,
        km_at=tc.km_at,
        town=tc.town,
        point=point,
        name_ru=tc.town.name_ru,
        hotel=hotel,
        hotel_options=ranked[:3],
        considered=considered,
        fallback=fallback,
        score=score,
        target_km=target,
        region_code=tc.town.region_code,
        detour_km=dkm,
        detour_min=dmin,
    )


# The farthest a passing hotel may be from the night stop, along the route, to be named as the nearest one
# (≈ 45 min of driving; ADR-0011 notes / dev-notes S3-QA). Farther → no substitute is named.
NEAREST_MAX_KM = 60.0


def _nearest_passing(
    corridor: Corridor, target: float, inp: NormalizedInput, ctx: PlanContext
) -> Candidate | None:
    pool = [h for h in corridor.lodgings if passes(h, inp.crew, ctx)]
    if not pool:
        return None
    return min(pool, key=lambda h: (abs(h.km_at - target), h.place.id))


def _no_lodging(ctx: PlanContext, choice: OvernightChoice, reason: str, corridor: Corridor) -> PlanWarning:
    """One sentence per night; the nearest passing hotel is the overnight stop's `note` only (S3-QA P1-06:
    the app shows the warning and the note as one plate, so the warning must not repeat it)."""
    text = ctx.templates.render(f"warning.{WarningCode.NO_LODGING.value}")
    detail = f"{reason}" + (f";nearest={choice.nearest.place.id}" if choice.nearest else "")
    return PlanWarning(WarningCode.NO_LODGING, choice.day, text, detail)


def _town_of(corridor: Corridor, h: Candidate) -> TownCandidate | None:
    for tc in corridor.towns:
        if any(x.place.id == h.place.id for x in tc.lodgings):
            return tc
    return None


def windows(
    prev: float, total: float, n_days: int, d: int, daily_km: int, ctx: PlanContext
) -> tuple[float, float, float, float, float]:
    """`(T, L, U, L2, U2)` for boundary `d` of an `n_days` split starting after `prev` (A§6.5)."""
    s = ctx.cfg.split
    seg = (total - prev) / (n_days - d + 1)
    target = prev + seg
    cap = total - (n_days - d) * s.hard_cap * daily_km
    lo = max(prev + s.window_lo * seg, cap)
    hi = prev + min(s.window_hi * seg, s.hard_cap * daily_km)
    lo2 = max(prev + s.widened_lo * seg, cap)
    hi2 = prev + min(s.widened_hi * seg, s.hard_cap * daily_km)
    return target, lo, hi, lo2, hi2


def _try_split(
    n_days: int, allow_f4: bool, corridor: Corridor, scorer: _Scorer
) -> tuple[list[OvernightChoice], list[PlanWarning]] | int:
    """The split, or the 1-based day whose boundary has no passing town (F1/F2 failed, F4 not allowed)."""
    inp, ctx = scorer.inp, scorer.ctx
    total = corridor.route.km_total
    prev = 0.0
    choices: list[OvernightChoice] = []
    warnings: list[PlanWarning] = []
    for d in range(1, n_days):
        target, lo, hi, lo2, hi2 = windows(prev, total, n_days, d, inp.daily_km, ctx)
        assert lo <= hi + 1e-6, f"split window empty: day {d} [{lo}, {hi}]"
        towns = [t for t in corridor.towns if t.km_at > prev + EPS]
        # K2: an anchor town may end the day later than the even split wants, up to the daily cap with the
        # drive into town (never earlier: an early big town would only push the km into the next days)
        cap_hi = prev + ctx.cfg.split.hard_cap * inp.daily_km
        f1 = [
            t
            for t in towns
            if (
                lo - EPS <= t.km_at <= hi + EPS
                or (anchor(t, ctx) and lo - EPS <= t.km_at and _into_town_km(t, ctx) <= cap_hi + EPS)
            )
            and scorer.passing(t)
        ]
        if f1:
            scored = [(t, scorer.score(t, target, prev, d)) for t in f1]
            tc, st = max(
                scored, key=lambda x: (round(x[1].score, 9), -abs(x[0].km_at - target), _neg(x[0].town.id))
            )
            choice = _choice(d, tc, scorer, [x[1] for x in scored], OvernightFallback.NONE, st.score, target)
        else:
            f2 = [t for t in towns if lo2 - EPS <= t.km_at <= hi2 + EPS and scorer.passing(t)]
            if f2:
                scored = [(t, scorer.score(t, target, prev, d)) for t in f2]
                tc, st = min(
                    scored, key=lambda x: (abs(x[0].km_at - target), -round(x[1].score, 9), x[0].town.id)
                )
                choice = _choice(
                    d, tc, scorer, [x[1] for x in scored], OvernightFallback.WIDENED, st.score, target
                )
                warnings.append(_no_lodging(ctx, choice, "widened", corridor))
            elif not allow_f4:
                return d
            else:
                f4 = [t for t in towns if lo - EPS <= t.km_at <= hi + EPS]
                nearest = _nearest_passing(corridor, target, inp, ctx)
                if f4:
                    scored = [(t, scorer.score(t, target, prev, d, with_h=False)) for t in f4]
                    tc, st = max(
                        scored,
                        key=lambda x: (round(x[1].score, 9), -abs(x[0].km_at - target), _neg(x[0].town.id)),
                    )
                    choice = _choice(
                        d,
                        tc,
                        scorer,
                        [x[1] for x in scored],
                        OvernightFallback.NO_HOTEL,
                        st.score,
                        target,
                        with_hotel=False,
                    )
                else:
                    km = min(max(target, lo), hi)
                    choice = _road_point(d, km, target, corridor, ctx)
                if nearest is not None and abs(nearest.km_at - choice.km_at) > NEAREST_MAX_KM:
                    nearest = None  # S3-QA P1-06: a hotel 320 km away is no substitute
                choice.nearest = nearest
                ntc = _town_of(corridor, nearest) if nearest else None
                choice.nearest_town = ntc.town if ntc else None
                warnings.append(_no_lodging(ctx, choice, "no_hotel", corridor))
        choice.day_start_km = prev
        choices.append(choice)
        prev = choice.km_at
    return choices, warnings


def _into_town_km(t: TownCandidate, ctx: PlanContext) -> float:
    """Route km at the town plus the drive into it (one way: the way back to the road is the next morning)."""
    return t.km_at + t.lateral_km * ctx.cfg.detour.winding


def _neg(s: str) -> tuple[int, ...]:
    """Key that makes `max` prefer the lexicographically smaller id."""
    return tuple(-ord(c) for c in s)


def _road_point(d: int, km: float, target: float, corridor: Corridor, ctx: PlanContext) -> OvernightChoice:
    point = interpolate(corridor.route, km)
    label = ctx.ports.geocoding.reverse(point)
    if label is not None:
        name = label.name_ru
    else:
        seg = corridor.index.nearest(point, 1.0)
        ref = corridor.index.road_ref_at(seg.seg_idx) if seg else None
        name = (
            ru.text("label.roadside_night", road_ref=ref, km=round_half_up(km))
            if ref
            else ru.text("label.roadside_night_noref", km=round_half_up(km))
        )
    region = ctx.region_at(point)
    return OvernightChoice(
        day=d,
        km_at=km,
        town=None,
        point=point,
        name_ru=name,
        hotel=None,
        hotel_options=[],
        considered=[],
        fallback=OvernightFallback.NO_HOTEL,
        score=0.0,
        target_km=target,
        region_code=region.code,
    )


def choose_overnights(
    split: DaySplit,
    corridor: Corridor,
    inp: NormalizedInput,
    ctx: PlanContext,
    profile: Profile | None = None,
) -> OvernightResult:
    prof = profile or ctx.profile_for(corridor.route)
    scorer = _Scorer(corridor, inp, ctx, prof)
    if split.fixed:
        return _from_template(split, scorer)
    n = split.n_days
    if n == 1:
        return OvernightResult([])
    first = _try_split(n, False, corridor, scorer)
    if not isinstance(first, int):
        return OvernightResult(*first)
    failed_day = first
    if n + 1 <= ctx.cfg.max_days:
        extra = _try_split(n + 1, False, corridor, scorer)
        if not isinstance(extra, int):
            choices, warnings = extra
            idx = min(failed_day, len(choices)) - 1
            choices[idx].fallback = OvernightFallback.EXTRA_DAY
            warnings.append(_no_lodging(ctx, choices[idx], "extra_day", corridor))
            return OvernightResult(choices, sorted(warnings, key=lambda w: w.day or 0))
    final = _try_split(n, True, corridor, scorer)
    assert not isinstance(final, int)
    return OvernightResult(*final)


def _from_template(split: DaySplit, scorer: _Scorer) -> OvernightResult:
    choices: list[OvernightChoice] = []
    warnings: list[PlanWarning] = []
    prev = 0.0
    for d, tc in enumerate(split.nights, start=1):
        st = scorer.score(tc, tc.km_at, prev, d)
        choice = _choice(d, tc, scorer, [st], OvernightFallback.TEMPLATE, st.score, tc.km_at)
        assert choice.hotel is not None  # `template_fits` requires a passing lodging (A§16.4)
        choice.day_start_km = prev
        choices.append(choice)
        prev = tc.km_at
    return OvernightResult(choices, warnings)
