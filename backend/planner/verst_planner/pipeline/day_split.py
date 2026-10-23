"""Stage 4: day split and the ready-route template fit rule [D-3] (A§6.4)."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from verst_planner.domain.errors import InvalidInput
from verst_planner.domain.model import NormalizedInput, ReadyRoute, Route, TownCandidate
from verst_planner.pipeline import Corridor, PlanContext

EPS = 1e-9


@dataclass(slots=True)
class DaySplit:
    n_days: int
    total_km: float
    fixed: bool  # True = template nights are used
    nights: list[TownCandidate]  # template night towns (fixed=True), in order


def n_days_for(total_km: float, daily_km: int) -> int:
    """`N = ceil(total / daily)`, at least 1 (with a tolerance for float noise)."""
    return max(1, math.ceil(total_km / daily_km - EPS))


def template_nights(template: ReadyRoute, corridor: Corridor) -> list[TownCandidate] | None:
    """The projection of each suggested night town, in order (first pass after the previous night)."""
    out: list[TownCandidate] = []
    prev = 0.0
    for town_id in template.suggested_nights:
        passes = [t for t in corridor.towns if t.town.id == town_id and t.km_at > prev + EPS]
        if not passes:
            return None
        pick = min(passes, key=lambda t: t.km_at)
        out.append(pick)
        prev = pick.km_at
    return out


def template_fits(template: ReadyRoute, corridor: Corridor, inp: NormalizedInput, ctx: PlanContext) -> bool:
    """[D-3]: every night town within 25 km of the route, every day ≤ 105 % of daily km and the number of
    days ≤ ceil(total / (90 % of daily km))."""
    nights = template_nights(template, corridor)
    if nights is None:
        return False
    if any(t.lateral_km > ctx.cfg.corridor_km.town for t in nights):
        return False
    total = corridor.route.km_total
    bounds = [0.0, *[t.km_at for t in nights], total]
    kms = [b - a for a, b in itertools.pairwise(bounds)]
    s = ctx.cfg.split
    return max(kms) <= s.template_hi * inp.daily_km + EPS and len(kms) <= math.ceil(
        total / (s.template_lo * inp.daily_km) - EPS
    )


def split_days(
    route: Route, corridor: Corridor, inp: NormalizedInput, template: ReadyRoute | None, ctx: PlanContext
) -> DaySplit:
    total = route.km_total
    n = n_days_for(total, inp.daily_km)
    if template is not None and template_fits(template, corridor, inp, ctx):
        nights = template_nights(template, corridor) or []
        return DaySplit(len(nights) + 1, total, True, nights)
    if n > ctx.cfg.max_days:
        raise InvalidInput("dailyKm", "too_many_days")
    return DaySplit(n, total, False, [])
