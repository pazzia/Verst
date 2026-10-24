"""Stage picks of a golden plan and the margin between their two best scores (A§16.12 S2-01, DEV-113).

A golden pick must not depend on a tie-break: the winner's score must exceed the runner-up's by at least
`MIN_MARGIN`. `record_picks(case)` plans the case with the pick functions wrapped and returns one `Pick` per
stage decision that ended up in the final plan: lunch (`best_lunch`), range fuel (`fuel._pick`), rests
(`rest.rank_rests`), overnight town (F1 `_choice`) and hotel (`rank_hotels`).

Stage-9 sights are a greedy fill under feasibility checks; two of their decisions are rankings and are
recorded too (DEV-113 T1):

- `sight` — per day whose sight cap was reached: the last pool sight accepted vs the first one turned away by
  the cap (the next in pool order), so the cap does not cut between two equal scores;
- `sight_drop` — every `lowest_sight` pick (re-run drops and stage-8b drops): the dropped sight vs the
  next-lowest droppable one. These are kept even though the dropped sight is not in the final plan.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Any
from unittest import mock

from tests.golden.test_golden import run_case
from verst_planner import engine
from verst_planner.domain.enums import Mood, OvernightFallback, StopKind
from verst_planner.pipeline import fuel as fuel_stage
from verst_planner.pipeline import meals, overnight, rest, sights

MIN_MARGIN = 0.05


@dataclass(frozen=True, slots=True)
class Pick:
    stage: str
    place_id: str
    best: float
    second: float

    @property
    def margin(self) -> float:
        return round(self.best - self.second, 9)


def _top2(scores: list[float]) -> tuple[float, float] | None:
    if len(scores) < 2:
        return None
    a, b = sorted(scores, reverse=True)[:2]
    return a, b


def record_picks(case: dict[str, Any]) -> list[Pick]:
    raw: list[Pick] = []

    def add(stage: str, place_id: str | None, scores: list[float]) -> None:
        top = _top2(scores)
        if place_id is not None and top is not None:
            raw.append(Pick(stage, place_id, top[0], top[1]))

    real_best = meals.best_lunch

    def best_lunch(cands: list[Any]) -> Any:
        chosen = real_best(cands)
        add("lunch", chosen.place.id if chosen.place else None, [round(sc, 9) for sc, _s in cands])
        return chosen

    real_pick = fuel_stage._pick

    def pick(cands: list[Any], days: list[Any], ctx: Any, latest: bool = False) -> Any:
        chosen = real_pick(cands, days, ctx, latest)
        scores = [fuel_stage.fuel_score(c, days, ctx) + (0.01 * c.km_at if latest else 0.0) for c in cands]
        add("fuel", chosen.place.id, scores)
        return chosen

    real_rank = rest.rank_rests

    def rank_rests(cands: list[Any], inp: Any, r: float) -> list[Any]:
        ranked = real_rank(cands, inp, r)
        if ranked:
            add("rest", ranked[0][0].place.id, [rest.rest_score(c, inp) for c, _d in cands])
        return ranked

    real_choice = overnight._choice

    def choice(
        day: int, tc: Any, scorer: Any, considered: list[Any], fallback: Any, *a: Any, **k: Any
    ) -> Any:
        out = real_choice(day, tc, scorer, considered, fallback, *a, **k)
        if fallback is OvernightFallback.NONE:
            add("overnight", out.town.id if out.town else None, [st.score for st in considered])
        return out

    real_hotels = overnight.rank_hotels

    def rank_hotels(passing: list[Any], tc: Any) -> list[Any]:
        ranked = real_hotels(passing, tc)
        if ranked:
            add("hotel", ranked[0].place.id, [overnight.hotel_score(h, tc) for h in passing])
        return ranked

    drops: list[Pick] = []
    real_lowest = sights.lowest_sight

    def lowest_sight(day: Any) -> int:
        i = real_lowest(day)
        scores = sorted(round(day.stops[j].score, 9) for j in sights.droppable_sights(day))
        place = day.stops[i].place
        if len(scores) >= 2 and place is not None:
            drops.append(Pick("sight_drop", place.id, -scores[0], -scores[1]))
        return i

    real_sights = sights.plan_sights

    def plan_sights(days: list[Any], corridor: Any, inp: Any, ctx: Any, frozen: bool = False) -> None:
        used = sights._used(days)
        before = [{id(st) for st in d.stops} for d in days]
        real_sights(days, corridor, inp, ctx, frozen)
        if frozen or inp.simplify or inp.mood is Mood.JUST_DRIVE:
            return
        max_n = ctx.cfg.sights.max_per_day.of(inp.mood)
        for day, old in zip(days, before, strict=True):
            pool = [
                c
                for c in corridor.sights
                if day.km_start < c.km_at < day.km_end
                and c.place.id not in used
                and sights.sight_score(c, inp) >= ctx.cfg.sights.min_score
            ]
            pool.sort(key=lambda c: (-round(sights.sight_score(c, inp), 9), c.km_at, c.place.id))
            added = {st.place.id for st in day.stops if id(st) not in old and st.kind is StopKind.SIGHT}
            used |= added
            n = sum(1 for st in day.stops if st.kind is StopKind.SIGHT and (st.fixed or id(st) not in old))
            if n < max_n or not added:
                continue
            last = max(k for k, c in enumerate(pool) if c.place.id in added)
            if last + 1 < len(pool):
                a, b = pool[last], pool[last + 1]
                add("sight", a.place.id, [sights.sight_score(a, inp), sights.sight_score(b, inp)])

    patches: list[tuple[Any, str, Callable[..., Any]]] = [
        (meals, "best_lunch", best_lunch),
        (sights, "best_lunch", best_lunch),
        (fuel_stage, "_pick", pick),
        (rest, "rank_rests", rank_rests),
        (overnight, "_choice", choice),
        (overnight, "rank_hotels", rank_hotels),
        (sights, "lowest_sight", lowest_sight),
        (sights, "plan_sights", plan_sights),
        (engine, "plan_sights", plan_sights),
    ]
    with ExitStack() as stack:
        for module, name, fn in patches:
            stack.enter_context(mock.patch.object(module, name, fn))
        plan, *_ = run_case(case)
    final = {s.place_id for d in plan.days_list for s in d.stops if s.place_id}
    final |= {s.town_id for d in plan.days_list for s in d.stops if s.town_id}
    seen: dict[tuple[str, str], Pick] = {}
    for p in raw:
        if p.place_id in final:
            key = (p.stage, p.place_id)
            # the decision that placed it: keep the smallest margin seen for that pick (worst case)
            if key not in seen or p.margin < seen[key].margin:
                seen[key] = p
    for p in drops:
        key = (p.stage, p.place_id)
        if key not in seen or p.margin < seen[key].margin:
            seen[key] = p
    return sorted(seen.values(), key=lambda p: (p.stage, p.place_id))
