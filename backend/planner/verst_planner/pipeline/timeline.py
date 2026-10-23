"""Timeline primitives (A§6.6): route profile, driving minutes, day schedule, day plans."""

from __future__ import annotations

import bisect
import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from verst_planner.domain.enums import StopKind
from verst_planner.domain.model import DayPlan, NormalizedInput, OvernightChoice, PlannedStop, Route
from verst_planner.geo.polyline import resample

if TYPE_CHECKING:
    from verst_planner.pipeline import PlanContext
    from verst_planner.pipeline.resolve import ResolvedPoints


@dataclass(frozen=True, slots=True)
class Profile:
    """`(km, minutes)` route profile resampled every 1 km (the same profile `EngineState` persists)."""

    km: tuple[float, ...]
    minutes: tuple[float, ...]
    factor: float

    @classmethod
    def from_route(cls, route: Route, factor: float) -> Profile:
        km, minutes = resample(route, 1.0)
        return cls(km, minutes, factor)

    def min_at(self, km: float) -> float:
        """Free-flow minutes at `km` (linear interpolation, clamped)."""
        return _interp(self.km, self.minutes, km)

    def km_at_min(self, minutes: float) -> float:
        """Inverse of `min_at` (free-flow minutes → km)."""
        return _interp(self.minutes, self.km, minutes)

    def drive(self, a: float, b: float) -> float:
        """Driving minutes between two km positions, x the drive-time factor [D-10]."""
        return (self.min_at(b) - self.min_at(a)) * self.factor

    def km_after_drive(self, start_km: float, drive_min: float) -> float:
        """The km reached after `drive_min` driving minutes from `start_km`."""
        return self.km_at_min(self.min_at(start_km) + drive_min / self.factor)


def _interp(xs: Sequence[float], ys: Sequence[float], x: float) -> float:
    if len(xs) == 1 or x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect.bisect_right(xs, x) - 1
    span = xs[i + 1] - xs[i]
    f = 0.0 if span == 0 else (x - xs[i]) / span
    return ys[i] + (ys[i + 1] - ys[i]) * f


# ---------------------------------------------------------------------------------------------- schedule


@dataclass(frozen=True, slots=True)
class Slot:
    arrive: datetime | None  # aware; None for START
    depart: datetime | None  # aware; None for OVERNIGHT / FINISH
    drive_min: float  # driving minutes from the previous stop, incl. both detour halves


def schedule_day(day: DayPlan, profile: Profile) -> list[Slot]:
    """A§6.6: arrival/departure of every stop of `day` (stops ordered by km, START first)."""
    t = day.start_at
    pos = day.km_start
    prev_half = 0.0
    out: list[Slot] = []
    for s in day.stops:
        if s.kind is StopKind.START:
            out.append(Slot(None, t, 0.0))
            pos = s.km_at
            continue
        leg = profile.drive(pos, s.km_at) + s.detour_min / 2
        t = t + timedelta(minutes=leg)
        arrive = t
        depart = (
            None if s.kind in (StopKind.OVERNIGHT, StopKind.FINISH) else t + timedelta(minutes=s.dwell_min)
        )
        out.append(Slot(arrive, depart, leg + prev_half))
        t = (depart or t) + timedelta(minutes=s.detour_min / 2)
        prev_half = s.detour_min / 2
        pos = s.km_at
    return out


def day_end(slots: list[Slot]) -> datetime:
    last = slots[-1]
    end = last.arrive if last.arrive is not None else last.depart
    assert end is not None
    return end


def day_duration_min(day: DayPlan, slots: list[Slot]) -> float:
    return (day_end(slots) - day.start_at).total_seconds() / 60.0


def insert_index(day: DayPlan, stop: PlannedStop) -> int:
    """Position that keeps stops ordered by km (after equal-km stops), before the final anchor."""
    i = len(day.stops) - 1
    while i > 1 and day.stops[i - 1].km_at > stop.km_at:
        i -= 1
    return i


def insert_stop(day: DayPlan, stop: PlannedStop) -> int:
    i = insert_index(day, stop)
    day.stops.insert(i, stop)
    return i


def eta_if_inserted(day: DayPlan, stop: PlannedStop, profile: Profile) -> tuple[Slot, list[Slot]]:
    """The candidate's slot (and the whole day's slots) when tentatively inserted (A§6.6)."""
    i = insert_stop(day, stop)
    try:
        slots = schedule_day(day, profile)
    finally:
        day.stops.pop(i)
    return slots[i], slots


def local(dt: datetime, tz: str) -> datetime:
    """Aware instant → naive local wall time in `tz`."""
    return dt.astimezone(ZoneInfo(tz)).replace(tzinfo=None)


def local_minute(dt: datetime, tz: str) -> datetime:
    """Naive local wall time rounded half-up to the minute (output rendering, A§6.10)."""
    loc = local(dt, tz)
    base = loc.replace(second=0, microsecond=0)
    return base + timedelta(minutes=1) if loc - base >= timedelta(seconds=30) else base


def next_day_start(prev_arrival: datetime, tz: str, start: time) -> datetime:
    """`day_start_next` local to `tz` on the calendar day after the previous arrival."""
    zone = ZoneInfo(tz)
    arr = prev_arrival.astimezone(zone)
    nxt = (arr + timedelta(days=1)).date()
    return datetime(nxt.year, nxt.month, nxt.day, start.hour, start.minute, tzinfo=zone)


# ---------------------------------------------------------------------------------------------- day plans


def _overnight_stop(c: OvernightChoice) -> PlannedStop:
    return PlannedStop(
        kind=StopKind.OVERNIGHT,
        km_at=c.km_at,
        name_ru=c.name_ru,
        point=c.point,
        place=c.hotel.place if c.hotel else None,
        town=c.town,
        detour_km=c.detour_km,
        detour_min=c.detour_min,
        fixed=True,
        score=c.score,
        region_code=c.region_code,
    )


def build_day_plans(
    route: Route,
    overnights: list[OvernightChoice],
    fixed: list[PlannedStop],
    inp: NormalizedInput,
    ctx: PlanContext,
    pts: ResolvedPoints,
    profile: Profile,
) -> list[DayPlan]:
    """Days between consecutive overnights with START / fixed stops / OVERNIGHT or FINISH anchors."""
    total = route.km_total
    bounds = [0.0, *[c.km_at for c in overnights], total]
    first, last = pts.waypoints[0], pts.waypoints[-1]
    towns = ctx.ports.places.get_towns([t for t in (first.town_id, last.town_id) if t])
    days: list[DayPlan] = []
    start_at = inp.start_at
    for d in range(1, len(bounds)):
        km_start, km_end = bounds[d - 1], bounds[d]
        if d == 1:
            town = towns.get(first.town_id) if first.town_id else None
            start = PlannedStop(
                StopKind.START,
                0.0,
                first.label,
                first.point,
                town=town,
                fixed=True,
                region_code=ctx.region_at(first.point).code,
            )
        else:
            prev = overnights[d - 2]
            start = PlannedStop(
                StopKind.START,
                km_start,
                prev.name_ru,
                prev.point,
                town=prev.town,
                fixed=True,
                region_code=prev.region_code,
            )
        if d < len(bounds) - 1:
            end = _overnight_stop(overnights[d - 1])
        else:
            town = towns.get(last.town_id) if last.town_id else None
            end = PlannedStop(
                StopKind.FINISH,
                total,
                last.label,
                last.point,
                town=town,
                fixed=True,
                region_code=ctx.region_at(last.point).code,
            )
        middle = [
            s
            for s in fixed
            if km_start < s.km_at <= km_end + 1e-9
            and not (s.kind is StopKind.VIA and end.kind is StopKind.OVERNIGHT and _same_place(s, end))
        ]
        middle.sort(key=lambda s: s.km_at)
        tz = ctx.tz_of(start.region_code, start.point)
        day = DayPlan(d, km_start, km_end, start_at, [start, *middle, end], tz)
        days.append(day)
        if d < len(bounds) - 1:
            slots = schedule_day(day, profile)
            nxt_tz = ctx.tz_of(end.region_code, end.point)
            start_at = next_day_start(day_end(slots), nxt_tz, ctx.cfg.day_start_next)
    return days


def _same_place(via: PlannedStop, end: PlannedStop) -> bool:
    if via.town is not None and end.town is not None:
        return via.town.id == end.town.id
    return abs(via.km_at - end.km_at) < 0.5


def refresh_day_starts(days: list[DayPlan], profile: Profile, ctx: PlanContext) -> bool:
    """Re-derive day `d > 1` starts from the final previous arrival; True if any start changed."""
    changed = False
    for prev, day in itertools.pairwise(days):
        slots = schedule_day(prev, profile)
        end = prev.stops[-1]
        want = next_day_start(day_end(slots), ctx.tz_of(end.region_code, end.point), ctx.cfg.day_start_next)
        if want != day.start_at:
            day.start_at = want
            changed = True
    return changed


def day_for_km(days: list[DayPlan], km: float) -> DayPlan:
    """The day whose km range contains `km` (a boundary km belongs to the earlier day)."""
    for d in days:
        if km <= d.km_end + 1e-9:
            return d
    return days[-1]
