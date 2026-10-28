"""ADR-0011: fit a plan to the budget (stage 12b), or say that it does not fit.

The ladder re-plans with one more lever per step, cheapest change first:

    S0 plain → S1 + cheaper hotels & family rooms → S2 + economy food → S3 + free sights
    → S4 + fewer nights (free trips with ≥ 2 days) → S5 + the ready route's shorter variant

The first step with `total ≤ budget` wins (`fits`); otherwise the earliest step within the tolerance
(`small_overrun`, ≤ 5 % and ≤ 3 000 ₽); otherwise `NoFit` with the cheapest step as the minimum and 2-3
options that are each verified by a plan of their own (at most `MAX_OPTION_PLANS` extra plans).

The module knows nothing about adapters: the engine passes a `FitEnv` (plan with knobs, variants, routes of
the hub, towns towards the destination).
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from verst_planner.domain.enums import WarningCode
from verst_planner.domain.errors import PlannerError
from verst_planner.domain.model import (
    Alternative,
    BudgetFit,
    BudgetLever,
    CostOverrides,
    DayResult,
    FitKnobs,
    PointInput,
    ReadyRoute,
    TripInput,
    TripPlan,
)

TOLERANCE_FRAC = 0.05
TOLERANCE_MAX_RUB = 3000
DAILY_KM_STEP = 50
FEWER_NIGHTS_FACTOR = 1.3
DAILY_KM_MAX = 900
MAX_OPTION_PLANS = 8
MAX_OPTIONS = 3
CLOSER_TOWNS = 5
NNBSP = chr(0x202F)  # thousands separator of the Russian copy

LEVER_KNOBS: dict[str, FitKnobs] = {
    "lodging_cheap": FitKnobs(lodging_cheap=True, family_rooms=True),
    "food_economy": FitKnobs(lodging_cheap=True, family_rooms=True, food_economy=True),
    "sights_free": FitKnobs(lodging_cheap=True, family_rooms=True, food_economy=True, sights_free=True),
}
FRUGAL = LEVER_KNOBS["sights_free"]


def allowed_rub(budget: int) -> int:
    """`budget + min(round(5 %), 3 000)` (Manager decision D1)."""
    return budget + min(math.floor(budget * TOLERANCE_FRAC + 0.5), TOLERANCE_MAX_RUB)


class FitEnv(Protocol):
    def plan(self, raw: TripInput, knobs: FitKnobs) -> TripPlan: ...

    def variants(self, ready_route_id: str) -> list[ReadyRoute]: ...

    def hub_routes(self, ready_route_id: str) -> list[ReadyRoute]: ...

    def towns_towards(self, raw: TripInput, plan: TripPlan, limit: int) -> list[PointInput]: ...

    def check_cancel(self) -> None: ...

    def text(self, key: str, **params: str | int) -> str: ...

    def recompute_total(self, plan: TripPlan, overrides: CostOverrides) -> int: ...


@dataclass(slots=True)
class Step:
    plan: TripPlan
    levers: tuple[str, ...]
    raw: TripInput
    variant_of: str | None = None

    @property
    def total(self) -> int:
        return self.plan.cost.total_rub


@dataclass(slots=True)
class FitOption:
    kind: str  # raise_budget | shorten | cheaper_route
    total_rub: int | None = None
    budget_rub: int | None = None
    days: int | None = None
    daily_km: int | None = None
    ready_route_id: str | None = None
    destination: PointInput | None = None
    title_ru: str | None = None
    fits: bool = True


class NoFit(PlannerError):
    """Not an error for the app: the distinct «не помещается в бюджет» outcome (ADR-0011)."""

    code = "NO_FIT"

    def __init__(
        self,
        budget_rub: int,
        allowed: int,
        minimum: TripPlan,
        levers: tuple[BudgetLever, ...],
        options: list[FitOption],
        text_ru: str,
    ) -> None:
        super().__init__(f"budget {budget_rub}: minimum {minimum.cost.total_rub}")
        self.budget_rub = budget_rub
        self.allowed = allowed
        self.minimum = minimum
        self.levers = levers
        self.options = options
        self.text_ru = text_ru


def _over_budget_days(p: TripPlan) -> int:
    return sum(1 for w in p.warnings if w.code is WarningCode.DAY_OVER_BUDGET)


def _savings(steps: list[Step], upto: int) -> tuple[BudgetLever, ...]:
    """The levers applied up to step `upto` with what each saved; a lever that saved nothing is omitted.
    `fewer_nights` carries the raised daily km (V2)."""
    out = []
    for k in range(1, upto + 1):
        saved = steps[k - 1].total - steps[k].total
        if saved > 0:
            code = steps[k].levers[-1]
            raised = steps[k].raw.daily_km if code == "fewer_nights" else None
            out.append(BudgetLever(code, saved, raised))
    return tuple(out)


def _lever_text(x: BudgetLever, user_daily_km: int, env: FitEnv) -> str:
    """The lever's words in the fit text. `fewer_nights` says the norm it raised (acceptance 2026-10-28,
    traveller V2: «300 км в день» must not silently become 350)."""
    if x.code == "fewer_nights" and x.daily_km is not None and x.daily_km != user_daily_km:
        return env.text("fit.lever.fewer_nights_raised", daily_from=user_daily_km, daily_to=x.daily_km)
    return env.text(f"fit.lever.{x.code}")


def _fewer_nights_raw(raw: TripInput, plan: TripPlan, factor: float, cap: int) -> TripInput | None:
    if raw.ready_route_id is not None or plan.days < 2:
        return None
    limit = min(cap, int(raw.daily_km * factor) // DAILY_KM_STEP * DAILY_KM_STEP)
    need = math.ceil(plan.km / (plan.days - 1) * 1.02 / DAILY_KM_STEP) * DAILY_KM_STEP
    daily = max(need, raw.daily_km + DAILY_KM_STEP)
    if daily > limit:
        return None
    return dataclasses.replace(raw, daily_km=daily)


def _try(env: FitEnv, raw: TripInput, knobs: FitKnobs) -> TripPlan | None:
    env.check_cancel()
    try:
        return env.plan(raw, knobs)
    except PlannerError:
        return None


def fit(raw: TripInput, s0: TripPlan, env: FitEnv) -> TripPlan:
    """The fitted plan (with `budget_fit`), or raise `NoFit`. A plan within budget is returned unchanged."""
    budget = raw.budget_rub
    if budget is None:
        return s0
    allowed = allowed_rub(budget)
    if s0.cost.total_rub <= budget:
        return flag_alternatives(s0, allowed, env)
    steps = [Step(s0, (), raw)]
    for lever, knobs in LEVER_KNOBS.items():
        p = _try(env, raw, knobs)
        if p is None:
            break
        steps.append(Step(p, (*steps[-1].levers, lever), raw))
        if p.cost.total_rub <= budget:
            return _fitted(steps, len(steps) - 1, "fits", budget, allowed, env)
    last = steps[-1]
    fewer = _fewer_nights_raw(raw, last.plan, FEWER_NIGHTS_FACTOR, DAILY_KM_MAX)
    if fewer is not None:
        # ADR-0011 defines this lever as a higher daily km (≤ 1.3x, never a new DAY_OVER_BUDGET), so it stays;
        # the raise is said, not hidden (acceptance 2026-10-28, traveller V2): the fit text names the new
        # norm, the lever carries it (`dailyKm`), `input.dailyKm` echoes the norm the trip is planned with
        # (the days and the chips agree) and the overnight reasons say the norm was raised (`norm_from_km`)
        p = _try(env, fewer, dataclasses.replace(FRUGAL, norm_from_km=raw.daily_km))
        if p is not None and p.days < last.plan.days and _over_budget_days(p) <= _over_budget_days(last.plan):
            steps.append(Step(p, (*last.levers, "fewer_nights"), fewer))
            if p.cost.total_rub <= budget:
                return _fitted(steps, len(steps) - 1, "fits", budget, allowed, env)
    if raw.ready_route_id is not None:
        for v in env.variants(raw.ready_route_id):
            vraw = dataclasses.replace(raw, ready_route_id=v.id)
            p = _try(env, vraw, FRUGAL)
            if p is not None:
                steps.append(Step(p, (*steps[-1].levers, "variant"), vraw, raw.ready_route_id))
                if p.cost.total_rub <= budget:
                    return _fitted(steps, len(steps) - 1, "fits", budget, allowed, env)
                break
    within = next((k for k in range(1, len(steps)) if steps[k].total <= allowed), None)
    if within is not None:
        return _fitted(steps, within, "small_overrun", budget, allowed, env)
    cheapest = min(range(len(steps)), key=lambda k: (steps[k].total, k))
    raise _no_fit(steps, cheapest, budget, allowed, env)


def _fitted(steps: list[Step], k: int, status: str, budget: int, allowed: int, env: FitEnv) -> TripPlan:
    s = steps[k]
    levers = _savings(steps, k)
    names = ", ".join(_lever_text(x, steps[0].raw.daily_km, env) for x in levers)
    text = env.text(f"fit.{status}", levers=names, budget=_rub(budget), total=_rub(s.total))
    bf = BudgetFit(status, budget, allowed, steps[0].total, s.total, levers, text, s.variant_of)
    plan = dataclasses.replace(s.plan, budget_fit=bf)
    return flag_alternatives(plan, allowed, env)


def _rub(x: int) -> str:
    return f"{x:,}".replace(",", NNBSP)


def flag_alternatives(plan: TripPlan, allowed: int, env: FitEnv) -> TripPlan:
    """ADR-0011: mark the alternatives whose replace would push the total past the tolerance."""
    days: list[DayResult] = []
    changed = False
    for d in plan.days_list:
        stops = []
        for st in d.stops:
            alts: list[Alternative] = []
            for a in st.alternatives:
                total = env.recompute_total(plan, CostOverrides(replaced={st.id: a.units}))
                flag = total > allowed
                changed = changed or flag != a.breaks_budget
                alts.append(dataclasses.replace(a, breaks_budget=flag))
            stops.append(dataclasses.replace(st, alternatives=tuple(alts)))
        days.append(dataclasses.replace(d, stops=tuple(stops)))
    return dataclasses.replace(plan, days_list=tuple(days)) if changed else plan


def _no_fit(steps: list[Step], k: int, budget: int, allowed: int, env: FitEnv) -> NoFit:
    """The minimum and up to 3 options: shorten, a cheaper route, raise the budget. Shorten and the cheaper
    route are re-planned; when none fits the tolerance, the cheapest candidate cheaper than the minimum is
    still offered with `fits = false` (a concrete number, not a promise)."""
    s = steps[k]
    levers = _savings(steps, k)
    options: list[FitOption] = []
    budget_left = MAX_OPTION_PLANS
    raw = steps[0].raw

    def attempt(r: TripInput) -> TripPlan | None:
        nonlocal budget_left
        if budget_left <= 0:
            return None
        budget_left -= 1
        return _try(env, r, FRUGAL)

    def best_of(cands: list[tuple[TripPlan, FitOption]]) -> FitOption | None:
        fitting = [o for p, o in cands if p.cost.total_rub <= allowed]
        if fitting:
            return fitting[0]
        cheaper = [(p.cost.total_rub, i, o) for i, (p, o) in enumerate(cands) if p.cost.total_rub < s.total]
        if not cheaper:
            return None
        return dataclasses.replace(min(cheaper, key=lambda x: (x[0], x[1]))[2], fits=False)

    # shorten: the ready route's variant (if not used yet) or more km per day for a free trip
    shorten: list[tuple[TripPlan, FitOption]] = []
    if raw.ready_route_id is not None and s.variant_of is None:
        for v in env.variants(raw.ready_route_id):
            p = attempt(dataclasses.replace(raw, ready_route_id=v.id))
            if p is not None:
                shorten.append((p, FitOption("shorten", p.cost.total_rub, days=p.days, ready_route_id=v.id)))
                shorten[-1][1].title_ru = v.title_ru
    elif raw.ready_route_id is None:
        longer = _fewer_nights_raw(s.raw, s.plan, DAILY_KM_MAX / max(1, s.raw.daily_km), DAILY_KM_MAX)
        if longer is not None:
            p = attempt(longer)
            if p is not None and p.days < s.plan.days:
                shorten.append(
                    (p, FitOption("shorten", p.cost.total_rub, days=p.days, daily_km=longer.daily_km))
                )
    # cheaper_route: another ready route of the hub, or a closer town in the same direction
    cheaper: list[tuple[TripPlan, FitOption]] = []
    if raw.ready_route_id is not None:
        for r in env.hub_routes(raw.ready_route_id):
            p = attempt(dataclasses.replace(raw, ready_route_id=r.id))
            if p is not None:
                cheaper.append(
                    (p, FitOption("cheaper_route", p.cost.total_rub, days=p.days, ready_route_id=r.id))
                )
                cheaper[-1][1].title_ru = r.title_ru
                if p.cost.total_rub <= allowed:
                    break
    else:
        for town in env.towns_towards(raw, s.plan, CLOSER_TOWNS):
            p = attempt(dataclasses.replace(raw, destination=town))
            if p is not None:
                cheaper.append(
                    (p, FitOption("cheaper_route", p.cost.total_rub, days=p.days, destination=town))
                )
                cheaper[-1][1].title_ru = p.title_ru
                if p.cost.total_rub <= allowed:
                    break
    for found in (best_of(shorten), best_of(cheaper)):
        if found is not None:
            options.append(found)
    options.append(FitOption("raise_budget", budget_rub=math.ceil(s.total / 1000) * 1000))
    text = env.text("fit.no_fit", budget=_rub(budget), total=_rub(s.total))
    minimum = dataclasses.replace(s.plan, budget_fit=None)
    return NoFit(budget, allowed, minimum, levers, options[:MAX_OPTIONS], text)


Planner = Callable[[TripInput, FitKnobs], TripPlan]

__all__ = ["FitEnv", "FitOption", "NoFit", "allowed_rub", "fit", "flag_alternatives"]
