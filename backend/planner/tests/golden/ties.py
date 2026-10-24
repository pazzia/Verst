"""Stage picks of a golden plan and the margin between their two best scores (A§16.12 S2-01, DEV-113).

A golden pick must not depend on a tie-break: the winner's score must exceed the runner-up's by at least
`MIN_MARGIN`. `record_picks(case)` plans the case with the pick functions wrapped and returns one `Pick` per
stage decision that ended up in the final plan: lunch (`best_lunch`), range fuel (`fuel._pick`), rests
(`rest.rank_rests`), overnight town (F1 `_choice`) and hotel (`rank_hotels`). Stage-9 sights are a greedy
fill under feasibility checks, not an argmax, and are not recorded.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Any
from unittest import mock

from tests.golden.test_golden import run_case
from verst_planner.domain.enums import OvernightFallback
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

    patches: list[tuple[Any, str, Callable[..., Any]]] = [
        (meals, "best_lunch", best_lunch),
        (sights, "best_lunch", best_lunch),
        (fuel_stage, "_pick", pick),
        (rest, "rank_rests", rank_rests),
        (overnight, "_choice", choice),
        (overnight, "rank_hotels", rank_hotels),
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
    return sorted(seen.values(), key=lambda p: (p.stage, p.place_id))
