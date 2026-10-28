"""Walk input, candidates, the orienteering solver and the `WalkRoute` JSON (ADR-0013).

Solver (deterministic; ≤ `POOL_MAX` candidates): greedy insertion by Δscore / Δminutes under every
constraint (time budget, opening hours over the whole visit, leg ≤ 2.5 km, group budget, preset caps), then
2-opt on the order (less walking), then single replacements that raise the score followed by more
insertions, until a full pass changes nothing or `MAX_MOVES` moves were made. Ties: lower Δminutes, then id.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from verst_planner.city.presets import (
    ADULT_PRESETS,
    BAR_DEFAULT_HOURS,
    BIG_MUSEUM_DWELL,
    BIG_MUSEUM_SITELINKS,
    DIVERSITY,
    DRINK_KINDS,
    DRINK_RUB,
    DURATIONS,
    DWELL,
    EAT_KINDS,
    HERITAGE_BONUS,
    INTERESTS,
    MAX_LEG_KM,
    MUSEUM_DWELL_CAP_MIN,
    MUSEUM_WALK_DWELL,
    PACES,
    PRESET_TABLE,
    PRESETS,
    UNLIMITED_MAX_STOPS,
    WALK_FACTOR,
    custom_weights,
)
from verst_planner.domain.errors import InvalidInput
from verst_planner.domain.model import LatLon
from verst_planner.events import NEVER, CancelToken
from verst_planner.geo.distance import haversine_km
from verst_planner.hours import OpeningHours
from verst_planner.hours import parse as parse_hours

MAX_MOVES = 200
FOOD_STOPS_MAX = 3  # CEO 2026-10-29: a walk with «Еда» eats at most three times …
FOOD_STOP_EVERY_MIN = 120  # … and with other interests at most once per two hours of walk


def food_stops_max(inp: WalkInput) -> int:
    if inp.interests == ("food",) or inp.duration_min is None:
        return FOOD_STOPS_MAX
    return max(1, min(FOOD_STOPS_MAX, inp.duration_min // FOOD_STOP_EVERY_MIN))
MAX_WAIT_MIN = 60
PAIR_POOL = 25  # pair insertion considers the 25 best candidates
WAIT_STEP_MIN = 5
# Daytime windows in the town's local time (ADR-0013 "Start time", spec 5.11 §9): a walk starts no earlier
# than the opening and ends by the closing hour; when that no longer fits today, at tomorrow's opening.
DAY_WINDOW = (9, 22)
MUSEUM_WINDOW = (10, 22)
DRINK_WINDOW = (18, 23)
RETURN_LEG_KM = 4.0


@dataclass(frozen=True, slots=True)
class WalkInput:
    start: LatLon
    label: str
    town_id: str | None
    preset: str
    duration_min: int | None  # None = «без ограничения» (ADR-0015 §6: no timetable)
    interests: tuple[str, ...]
    pace: str
    budget_rub: int | None
    return_to_start: bool
    start_at: datetime | None
    adults: int
    children: int
    adult_confirmed: bool
    exclude: frozenset[str]
    dog: bool = False
    widened: bool = False  # the interests gave < 2 places: other sights joined at 0.15
    no_data_ru: str | None = None  # CEO 2026-10-29: why — no catalogue data for an interest here (not «few»)


@dataclass(frozen=True, slots=True)
class Candidate:
    id: str
    name: str
    kind: str
    point: LatLon
    popularity: float
    heritage: bool
    hours: OpeningHours | None
    hours_verified: bool
    cost_rub: int
    dwell_min: int
    has_photo: bool
    weight: float
    long_visit: bool = False  # a big museum seen in ≤ 2 h: the stop says «только главное»
    hours_source: str = "default"  # "osm" | "curated" | "default" (ADR-0015 §6)
    price_known: bool = True  # False: a food place — OSM has no prices, the stop says so (ADR-0019 E-2)

    @property
    def base_score(self) -> float:
        return 100.0 * self.popularity * self.weight + (HERITAGE_BONUS if self.heritage else 0.0)


@dataclass(slots=True)
class Leg:
    walk_km: float
    walk_min: float
    arrive: float
    depart: float


@dataclass(slots=True)
class Evaluated:
    ok: bool
    total_min: float = 0.0
    walk_km: float = 0.0
    walk_min: float = 0.0
    cost: int = 0
    legs: list[Leg] = field(default_factory=list)
    back_km: float = 0.0
    back_min: float = 0.0
    wait_min: float = 0.0


def _bool(v: Any, name: str) -> bool:
    if not isinstance(v, bool):
        raise InvalidInput(name, "not_bool")
    return v


def _int(v: Any, name: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise InvalidInput(name, "not_int")
    return v


def parse_input(d: dict[str, Any], tz_now_local: datetime) -> WalkInput:
    """Validate the `city_route` input (ADR-0013 "Input"); `InvalidInput(field, reason)` on violations."""
    start = d.get("start")
    if not isinstance(start, dict):
        raise InvalidInput("start", "required")
    try:
        point = LatLon(float(start["lat"]), float(start["lon"]))
    except (KeyError, TypeError, ValueError):
        raise InvalidInput("start", "bad_point") from None
    preset = d.get("preset", "overview")
    if preset not in PRESETS:
        raise InvalidInput("preset", "unknown")
    raw_duration = d.get(
        "durationMin", PRESET_TABLE[preset].default_duration if preset in PRESET_TABLE else 240
    )
    duration: int | None = None
    if raw_duration is not None:  # null = «без ограничения»
        duration = _int(raw_duration, "durationMin")
        if duration not in DURATIONS:
            raise InvalidInput("durationMin", "out_of_range")
    interests = d.get("interests") or []
    if not isinstance(interests, list) or any(i not in INTERESTS for i in interests):
        raise InvalidInput("interests", "unknown")
    if preset == "custom" and not interests:
        raise InvalidInput("interests", "required")
    pace = d.get("pace") or (PRESET_TABLE[preset].default_pace if preset in PRESET_TABLE else "normal")
    if pace not in PACES:
        raise InvalidInput("pace", "unknown")
    budget = d.get("budgetRub")
    if budget is not None:
        budget = _int(budget, "budgetRub")
        if budget < 0:
            raise InvalidInput("budgetRub", "out_of_range")
    crew = d.get("crew", {})
    if crew is None:
        crew = {}
    if not isinstance(crew, dict):
        raise InvalidInput("crew", "not_object")
    adults = _int(crew.get("adults", 1), "crew.adults")
    children = _int(crew.get("children", 0), "crew.children")
    dog = _bool(crew.get("dog", False), "crew.dog")
    if not 1 <= adults <= 8 or not 0 <= children <= 7 or adults + children > 8:
        raise InvalidInput("crew", "out_of_range")
    confirmed = _bool(d.get("adultConfirmed", False), "adultConfirmed")
    alcohol = preset in ADULT_PRESETS or (preset == "custom" and "bars" in interests)
    if alcohol and not confirmed:  # 18+ by the user's age answer only; children get a warning, not a block
        raise InvalidInput("adultConfirmed", "required")
    start_at = d.get("startAt")
    when = None
    if start_at is not None:
        try:
            when = datetime.fromisoformat(str(start_at)).replace(tzinfo=None)
        except ValueError:
            raise InvalidInput("startAt", "bad_datetime") from None
        if not tz_now_local - timedelta(days=1) <= when <= tz_now_local + timedelta(days=365):
            raise InvalidInput("startAt", "out_of_range")
    exclude = d.get("exclude") or []
    if not isinstance(exclude, list) or not all(isinstance(x, str) for x in exclude):
        raise InvalidInput("exclude", "not_strings")
    town_id = d.get("townId")
    if town_id is not None and not isinstance(town_id, str):
        raise InvalidInput("townId", "not_string")
    return WalkInput(
        start=point,
        label=str(start.get("label") or ""),
        town_id=town_id,
        preset=preset,
        duration_min=duration,
        interests=tuple(interests),
        pace=pace,
        budget_rub=budget,
        return_to_start=_bool(d.get("returnToStart", True), "returnToStart"),
        start_at=when,
        adults=adults,
        children=children,
        adult_confirmed=confirmed,
        exclude=frozenset(exclude),
        dog=dog,
    )


def weights_for(inp: WalkInput) -> dict[str, float]:
    if inp.preset == "custom":
        return custom_weights(inp.interests, inp.widened)
    return dict(PRESET_TABLE[inp.preset].weights)


def caps_for(inp: WalkInput) -> dict[str, int]:
    caps = (
        {"museum": 4, "drinks": 5, "food": food_stops_max(inp)}
        if inp.preset == "custom"
        else dict(PRESET_TABLE[inp.preset].caps)
    )
    if inp.duration_min is None:
        caps["stops"] = UNLIMITED_MAX_STOPS
    return caps


def dwell_for(kind: str, sitelinks: int, inp: WalkInput) -> int:
    base = DWELL[kind]
    big = kind == "museum" and sitelinks >= BIG_MUSEUM_SITELINKS
    if big:
        base = BIG_MUSEUM_DWELL
    if kind == "museum" and inp.preset == "museums":
        if big:  # a fixed, round visit («за 1 ч 30 мин — только главное»), whatever the pace
            return min(MUSEUM_DWELL_CAP_MIN, BIG_MUSEUM_DWELL)
        return max(5, min(MUSEUM_DWELL_CAP_MIN, round(MUSEUM_WALK_DWELL * PACES[inp.pace][1])))
    if kind == "museum" and inp.preset == "overview":
        base = min(base, PRESET_TABLE["overview"].museum_dwell_cap or base)
    return max(5, round(base * PACES[inp.pace][1]))


def long_visit(kind: str, sitelinks: int) -> bool:
    return kind == "museum" and sitelinks >= BIG_MUSEUM_SITELINKS


def drink_cost(kind: str, adults: int) -> int:
    return DRINK_RUB.get(kind, 0) * adults if kind in DRINK_KINDS else 0


def bar_hours(raw: str | None) -> OpeningHours:
    return parse_hours(raw or BAR_DEFAULT_HOURS)


# ------------------------------------------------------------------------------------------- solver


class Solver:
    def __init__(
        self,
        cands: Sequence[Candidate],
        start: LatLon,
        finish: LatLon | None,
        budget_min: float,
        speed_kmh: float,
        start_dt: datetime,
        budget_rub: int | None,
        caps: dict[str, int],
        cancel: CancelToken = NEVER,
    ) -> None:
        self.c = list(cands)
        self.start = start
        self.finish = finish
        self.T = budget_min
        self.speed = speed_kmh
        self.start_dt = start_dt
        self.budget = budget_rub
        self.caps = caps
        self.cancel = cancel
        self.mixed = any(c.kind not in EAT_KINDS and c.weight > 0 for c in self.c)
        self._open_cache: dict[tuple[int, int], float | None] = {}
        n = len(self.c)
        self.d_start = [haversine_km(start, x.point) * WALK_FACTOR for x in self.c]
        self.d_fin = [haversine_km(x.point, finish) * WALK_FACTOR if finish else 0.0 for x in self.c]
        self.d = [
            [haversine_km(self.c[i].point, self.c[j].point) * WALK_FACTOR for j in range(n)] for i in range(n)
        ]

    def minutes(self, km: float) -> float:
        return km / self.speed * 60.0

    def caps_ok(self, seq: Sequence[int]) -> bool:
        return self._caps_ok(seq)

    def _caps_ok(self, seq: Sequence[int]) -> bool:
        museums = sum(1 for i in seq if self.c[i].kind == "museum")
        drinks = sum(1 for i in seq if self.c[i].kind in DRINK_KINDS)
        eats = sum(1 for i in seq if self.c[i].kind in EAT_KINDS)
        others = len(seq) - museums - drinks - eats
        if eats > 1 and self.mixed and any(
            self.c[a].kind in EAT_KINDS and self.c[b].kind in EAT_KINDS for a, b in itertools.pairwise(seq)
        ):
            return False  # CEO 2026-10-29: a walk with sights does not go from one café straight to the next
        return (
            len(seq) <= self.caps.get("stops", 99)
            and museums <= self.caps.get("museum", 99)
            and drinks <= self.caps.get("drinks", 99)
            and eats <= self.caps.get("food", 99)
            and others <= self.caps.get("others", 99)
        )

    def _open_from(self, i: int, arrive: float) -> float | None:
        """The earliest visit start ≥ `arrive` (waiting ≤ `MAX_WAIT_MIN`) whose whole dwell is open."""
        cand = self.c[i]
        if cand.hours is None or cand.hours.always:
            return arrive
        key = (i, round(arrive))
        if key in self._open_cache:
            return self._open_cache[key]
        found = None
        for wait in range(0, MAX_WAIT_MIN + 1, WAIT_STEP_MIN):
            a = self.start_dt + timedelta(minutes=arrive + wait)
            if cand.hours.covers(a, a + timedelta(minutes=cand.dwell_min)):
                found = arrive + wait
                break
        self._open_cache[key] = found
        return found

    def evaluate(self, seq: Sequence[int]) -> Evaluated:
        if not self._caps_ok(seq):
            return Evaluated(False)
        t = 0.0
        walk = 0.0
        wait = 0.0
        cost = 0
        legs: list[Leg] = []
        prev = -1
        for i in seq:
            km = self.d_start[i] if prev < 0 else self.d[prev][i]
            if km > MAX_LEG_KM:
                return Evaluated(False)
            wm = self.minutes(km)
            cand = self.c[i]
            arrive = self._open_from(i, t + wm)
            if arrive is None:
                return Evaluated(False)
            wait += arrive - (t + wm)
            depart = arrive + cand.dwell_min
            legs.append(Leg(km, wm, arrive, depart))
            walk += km
            cost += cand.cost_rub
            t = depart
            prev = i
        back_km = back_min = 0.0
        if self.finish is not None and seq:
            back_km = self.d_fin[prev]
            if back_km > RETURN_LEG_KM:
                return Evaluated(False)
            back_min = self.minutes(back_km)
            t += back_min
            walk += back_km
        if t > self.T + 1e-9:
            return Evaluated(False)
        if self.budget is not None and cost > self.budget:
            return Evaluated(False)
        walk_min = self.minutes(walk)
        return Evaluated(True, t, walk, walk_min, cost, legs, back_km, back_min, wait)

    def score(self, seq: Sequence[int]) -> float:
        by_kind: dict[str, list[float]] = {}
        for i in seq:
            by_kind.setdefault(self.c[i].kind, []).append(self.c[i].base_score)
        total = 0.0
        for scores in by_kind.values():
            for k, s in enumerate(sorted(scores, reverse=True)):
                total += s * (DIVERSITY ** max(0, k - 1))
        return total

    def _insert_pass(self, seq: list[int], by_ratio: bool = True) -> bool:
        """The best single insertion; on a round trip the reversed order is tried too (S4 walk-filters b3:
        [Памятник, Бюст, Бюст] cannot reach Гребнево, the same walk backwards can)."""
        if self.finish is not None and len(seq) > 1 and self.finish == self.start:
            rev = seq[::-1]
            a, b = list(seq), list(rev)
            ok_a, ok_b = self._insert_once(a, by_ratio), self._insert_once(b, by_ratio)
            if ok_a and ok_b:
                pick = a if self._better(a, b, by_ratio, seq) else b
            elif ok_a or ok_b:
                pick = a if ok_a else b
            else:
                return False
            seq[:] = pick
            return True
        return self._insert_once(seq, by_ratio)

    def _better(self, a: list[int], b: list[int], by_ratio: bool, base: list[int]) -> bool:
        ea, eb = self.evaluate(a), self.evaluate(b)
        sa, sb = self.score(a), self.score(b)
        if by_ratio:
            t0 = self.evaluate(base).total_min
            ra, rb = (
                (sa - self.score(base)) / max(1e-6, ea.total_min - t0),
                (sb - self.score(base)) / max(1e-6, eb.total_min - t0),
            )
            return (ra, -ea.total_min) >= (rb, -eb.total_min)
        return (sa, -ea.total_min) >= (sb, -eb.total_min)

    def _insert_once(self, seq: list[int], by_ratio: bool = True) -> bool:
        used = set(seq)
        base_ev = self.evaluate(seq)
        base_t = (base_ev.total_min - base_ev.wait_min) if seq else 0.0
        base_s = self.score(seq)
        best: tuple[float, float, str, int, int] | None = None
        for ci in range(len(self.c)):
            if ci in used or self.c[ci].weight <= 0:
                continue
            for pos in range(len(seq) + 1):
                if base_t + self._added(seq, pos, ci) > self.T + 1e-9:
                    continue  # a lower bound (waiting only adds) already exceeds the budget
                new = [*seq[:pos], ci, *seq[pos:]]
                ev = self.evaluate(new)
                if not ev.ok:
                    continue
                dt = max(1e-6, ev.total_min - base_t)
                ds = self.score(new) - base_s
                if ds <= 0:
                    continue
                key = (-ds / dt if by_ratio else -ds, dt, self.c[ci].id, pos, ci)
                if best is None or key < best:
                    best = key
        if best is None:
            return False
        seq.insert(best[3], best[4])
        return True

    def _insert_pair_pass(self, seq: list[int], by_ratio: bool = True) -> bool:
        """Insert two stops at once (S4 walk-filters bug b3): a cluster behind the 2.5 km leg cap (Гребнево
        from central Фрязино) is reachable only through a stepping stone, which one-at-a-time insertion never
        adds when the stepping stone alone is not worth it. Tried only when no single stop fits."""
        used = set(seq)
        base_ev = self.evaluate(seq)
        base_t = (base_ev.total_min - base_ev.wait_min) if seq else 0.0
        base_s = self.score(seq)
        pool = [ci for ci in range(len(self.c)) if ci not in used and self.c[ci].weight > 0]
        pool = sorted(pool, key=lambda ci: (-self.c[ci].base_score, self.c[ci].id))[:PAIR_POOL]
        best: tuple[float, float, str, str, int, int, int] | None = None
        for pos in range(len(seq) + 1):
            prev = seq[pos - 1] if pos > 0 else -1
            for ci in pool:
                if self._dist(prev, ci) > MAX_LEG_KM:
                    continue
                for cj in pool:
                    if cj == ci or self.d[ci][cj] > MAX_LEG_KM:
                        continue
                    new = [*seq[:pos], ci, cj, *seq[pos:]]
                    ev = self.evaluate(new)
                    if not ev.ok:
                        continue
                    dt = max(1e-6, ev.total_min - base_t)
                    ds = self.score(new) - base_s
                    if ds <= 0:
                        continue
                    key = (-ds / dt if by_ratio else -ds, dt, self.c[ci].id, self.c[cj].id, pos, ci, cj)
                    if best is None or key < best:
                        best = key
        if best is None:
            return False
        seq[best[4] : best[4]] = [best[5], best[6]]
        return True

    def _dist(self, a: int, b: int) -> float:
        """Walking km between sequence items; -1 stands for the start, -2 for the finish."""
        if a == -1:
            return self.d_start[b] if b >= 0 else 0.0
        if b == -2:
            return self.d_fin[a] if self.finish is not None else 0.0
        return self.d[a][b]

    def _added(self, seq: Sequence[int], pos: int, ci: int) -> float:
        """Travel + dwell minutes that inserting `ci` at `pos` adds, before any waiting."""
        prev = seq[pos - 1] if pos > 0 else -1
        if pos < len(seq):
            nxt = seq[pos]
            km = self._dist(prev, ci) + self._dist(ci, nxt) - self._dist(prev, nxt)
        else:
            km = self._dist(prev, ci) + (
                self._dist(ci, -2) - self._dist(prev, -2) if prev >= 0 else self._dist(ci, -2)
            )
        return self.minutes(km) + self.c[ci].dwell_min

    def _two_opt(self, seq: list[int]) -> bool:
        if len(seq) < 3:
            return False
        cur = self.evaluate(seq)
        for i in range(len(seq) - 1):
            for j in range(i + 1, len(seq)):
                new = seq[:i] + seq[i : j + 1][::-1] + seq[j + 1 :]
                ev = self.evaluate(new)
                if ev.ok and ev.walk_km < cur.walk_km - 1e-9:
                    seq[:] = new
                    return True
        return False

    def _replace(self, seq: list[int]) -> bool:
        used = set(seq)
        base = self.score(seq)
        ev = self.evaluate(seq)
        order = sorted(range(len(self.c)), key=lambda x: self.c[x].id)
        for k in range(len(seq)):
            rest = [*seq[:k], *seq[k + 1 :]]
            without = ev.total_min - ev.wait_min - self._added(rest, k, seq[k])
            for ci in order:
                if ci in used or self.c[ci].weight <= 0:
                    continue
                if without + self._added(rest, k, ci) > self.T + 1e-9:
                    continue
                new = [*seq[:k], ci, *seq[k + 1 :]]
                if self.score(new) > base + 1e-9 and self.evaluate(new).ok:
                    seq[:] = new
                    return True
        return False

    def _drop_and_refill(self, seq: list[int], by_ratio: bool) -> bool:
        """Remove one stop, refill greedily; keep the result if the score rose."""
        base = self.score(seq)
        for k in range(len(seq)):
            trial = [*seq[:k], *seq[k + 1 :]]
            banned = seq[k]
            while self._insert_pass_without(trial, banned, by_ratio):
                pass
            if self.score(trial) > base + 1e-9:
                seq[:] = trial
                return True
        return False

    def _insert_pass_without(self, seq: list[int], banned: int, by_ratio: bool) -> bool:
        w = self.c[banned].weight
        self.c[banned] = _with_weight(self.c[banned], 0.0)
        try:
            return self._insert_pass(seq, by_ratio)
        finally:
            self.c[banned] = _with_weight(self.c[banned], w)

    def _construct(self, by_ratio: bool) -> list[int]:
        seq: list[int] = []
        moves = 0
        while moves < MAX_MOVES:
            self.cancel.check()
            changed = False
            while moves < MAX_MOVES and (
                self._insert_pass(seq, by_ratio) or self._insert_pair_pass(seq, by_ratio)
            ):
                moves += 1
                changed = True
            while moves < MAX_MOVES and self._two_opt(seq):
                moves += 1
                changed = True
            if moves < MAX_MOVES and (self._replace(seq) or self._drop_and_refill(seq, by_ratio)):
                moves += 1
                changed = True
            if not changed:
                break
        return seq

    def solve(self) -> list[int]:
        """The better of two constructions (Δscore/Δmin and Δscore greedy), each improved locally."""
        best: tuple[float, float, list[str], list[int]] | None = None
        for by_ratio in (True, False):
            seq = self._construct(by_ratio)
            ev = self.evaluate(seq)
            key = (-self.score(seq), ev.total_min if ev.ok else 0.0, [self.c[i].id for i in seq], seq)
            if best is None or key[:3] < best[:3]:
                best = key
        assert best is not None
        return best[3]


def _with_weight(c: Candidate, w: float) -> Candidate:
    from dataclasses import replace

    return replace(c, weight=w)


def rounded_start(now_local: datetime) -> datetime:
    """Now rounded up to the next quarter hour (naive local time)."""
    base = now_local.replace(second=0, microsecond=0, tzinfo=None)
    return base + timedelta(minutes=(-base.minute) % 15)


def window(preset: str, interests: Sequence[str]) -> tuple[int, int]:
    """(opening hour, closing hour) of the walk's daytime window."""
    if preset in ADULT_PRESETS or "bars" in interests:
        return DRINK_WINDOW
    return MUSEUM_WINDOW if preset == "museums" else DAY_WINDOW


def planned_start(
    now_local: datetime, preset: str, interests: Sequence[str], duration_min: int
) -> tuple[datetime, bool]:
    """The start of a walk asked for now: (start, starts tomorrow).

    Now rounded up to 15 min if the walk still fits in today's window; before the opening → the opening
    today; after the latest start (closing minus duration) → the opening tomorrow. A walk longer than the
    window starts at the opening.
    """
    open_h, close_h = window(preset, interests)
    start = rounded_start(now_local)
    day = start.replace(hour=0, minute=0)
    opening = day + timedelta(hours=open_h)
    latest = max(opening, day + timedelta(hours=close_h, minutes=-duration_min))
    if start <= opening:
        return opening, False
    if start <= latest:
        return start, False
    return opening + timedelta(days=1), True


def hm(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def r1(x: float) -> float:
    return math.floor(x * 10 + 0.5) / 10


def polyline(points: Sequence[LatLon]) -> list[list[float]]:
    return [[round(p.lat, 6), round(p.lon, 6)] for p in points]
