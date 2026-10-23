"""Assembly: stop ids, rendered stops/days, fuel region attribution, cost inputs and engine state.

Ids are `d{day}s{nn}` (nn from 01 within the day); `seq` is the global order from 1 (A§4.7).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime

from verst_planner.domain.enums import SIGN_BY_KIND, SignType, Source, StopKind, Tag
from verst_planner.domain.model import (
    Alternative,
    CandidateState,
    DayResult,
    DayState,
    EngineState,
    HotelOption,
    NormalizedInput,
    Place,
    PlannedStop,
    ReplaceableKinds,
    Route,
    ScheduledStop,
    StopState,
    TollHit,
)
from verst_planner.explain import ru
from verst_planner.explain.reasons import stop_reason
from verst_planner.geo.polyline import interpolate
from verst_planner.pipeline import Corridor, PlanContext, round_half_up
from verst_planner.pipeline.timeline import Profile, Slot, day_end, local_minute

REGION_STEP_KM = 10.0


def stop_id(day: int, idx: int) -> str:
    return f"d{day}s{idx + 1:02d}"


def sorted_tags(tags: frozenset[Tag]) -> tuple[Tag, ...]:
    order = {t: i for i, t in enumerate(Tag)}
    return tuple(sorted(tags, key=lambda t: order[t]))


def rooms(inp: NormalizedInput) -> int:
    return -(-inp.crew.adults // 2)


def hotel_option(p: Place, inp: NormalizedInput) -> HotelOption:
    price = p.price_night_rub or 0
    return HotelOption(
        p.id,
        p.name_ru,
        sorted_tags(p.tags),
        price,
        rooms(inp),
        rooms(inp) * price,
        p.source is not Source.OSM,
    )


@dataclass(slots=True)
class StopView:
    """Rendering context of one stop that the planned stop itself does not carry."""

    overnight_text: str = ""
    hotel_options: tuple[HotelOption, ...] = ()
    note: str | None = None
    alternatives: tuple[Alternative, ...] = ()
    alternatives_note: str | None = None


def render_stop(
    s: PlannedStop,
    slot: Slot,
    day_no: int,
    idx: int,
    seq: int,
    km_from_prev: int,
    inp: NormalizedInput,
    ctx: PlanContext,
    view: StopView | None = None,
    sid: str | None = None,
) -> ScheduledStop:
    v = view or StopView()
    tz = ctx.tz_of(s.region_code, s.point)
    arrive = local_minute(slot.arrive, tz) if slot.arrive is not None else None
    depart = local_minute(slot.depart, tz) if slot.depart is not None else None
    if s.kind is StopKind.OVERNIGHT:
        sign = SignType.HOTEL if s.place is not None else SignType.CITY
        reason = v.overnight_text
    else:
        sign = SIGN_BY_KIND[s.kind]
        when = depart if s.kind is StopKind.START else arrive
        reason = stop_reason(s, inp, ctx.cfg, ctx.templates, when, inp.round_trip)
    note = v.note
    if note is None and s.place is not None and s.place.source is Source.OSM:
        note = ru.text("note.unverified")
    town_id = s.town.id if s.town is not None else (s.place.town_id if s.place is not None else None)
    return ScheduledStop(
        id=sid or stop_id(day_no, idx),
        seq=seq,
        day=day_no,
        kind=s.kind,
        sign=sign,
        place_id=s.place.id if s.place is not None else None,
        town_id=town_id,
        name_ru=s.name_ru,
        note_ru=note,
        point=s.point,
        arrive_at=arrive,
        depart_at=depart,
        tz=tz,
        km_from_prev=km_from_prev,
        km_at=round_half_up(s.km_at),
        dwell_min=s.dwell_min,
        tags=sorted_tags(s.place.tags) if s.place is not None else (),
        cost_rub=ctx.stop_cost(s, inp),
        verified=s.place is None or s.place.source is not Source.OSM,
        reason_ru=reason,
        replaceable=s.kind in ReplaceableKinds and not s.fixed and s.place is not None,
        alternatives=v.alternatives,
        hotel_options=v.hotel_options,
        selected_hotel_id=s.place.id if s.kind is StopKind.OVERNIGHT and s.place is not None else None,
        alternatives_note_ru=v.alternatives_note,
    )


def km_from_prev_row(stops: list[PlannedStop]) -> list[int]:
    row = [0]
    for prev, s in itertools.pairwise(stops):
        row.append(round_half_up(s.km_at - prev.km_at + (prev.detour_km + s.detour_km) / 2))
    return row


def render_day(
    plan_stops: list[PlannedStop],
    slots: list[Slot],
    day_no: int,
    km_start: float,
    km_end: float,
    start_at: datetime,
    tz: str,
    over_budget: bool,
    seq0: int,
    inp: NormalizedInput,
    ctx: PlanContext,
    views: dict[int, StopView],
    ids: list[str] | None = None,
) -> DayResult:
    row = km_from_prev_row(plan_stops)
    stops = tuple(
        render_stop(s, slot, day_no, i, seq0 + i, row[i], inp, ctx, views.get(i), ids[i] if ids else None)
        for i, (s, slot) in enumerate(zip(plan_stops, slots, strict=True))
    )
    km = round_half_up(km_end - km_start + sum(s.detour_km for s in plan_stops))
    return DayResult(
        day=day_no,
        km=km,
        drive_min=round_half_up(sum(x.drive_min for x in slots)),
        tz=tz,
        start_at=local_minute(start_at, tz),
        end_at=local_minute(day_end(slots), tz),
        stops=stops,
        over_budget=over_budget,
    )


# ----------------------------------------------------------------------------------- region attribution


def region_km(route: Route, stops: list[PlannedStop], ctx: PlanContext) -> list[tuple[str, float]]:
    """A§7.1: 10-km buckets assigned to the region at their midpoint, plus each stop's detour km."""
    out: dict[str, float] = {}
    total = route.km_total
    k = 0.0
    while k < total - 1e-9:
        length = min(REGION_STEP_KM, total - k)
        code = ctx.region_at(interpolate(route, k + length / 2)).code
        out[code] = out.get(code, 0.0) + length
        k += REGION_STEP_KM
    for s in stops:
        if s.detour_km > 0:
            code = s.region_code or ctx.region_at(s.point).code
            out[code] = out.get(code, 0.0) + s.detour_km
    return [(code, round(km, 3)) for code, km in out.items()]


@dataclass(slots=True)
class Sched:
    """Minimal view of a scheduled day for assembly and costing (decoupled from `schedule.ScheduledDay`)."""

    day: int
    km_start: float
    km_end: float
    start_at: datetime
    tz: str
    stops: list[PlannedStop]
    slots: list[Slot]
    ids: list[str] = field(default_factory=list)
    budget_min: int = 0


# ----------------------------------------------------------------------------------- engine state


def engine_state(
    profile: Profile,
    region_kms: list[tuple[str, float]],
    toll_hits: list[TollHit],
    days: list[Sched],
    corridor: Corridor,
    ctx: PlanContext,
) -> EngineState:
    states = []
    for d in days:
        states.append(
            DayState(
                day=d.day,
                km_start=d.km_start,
                km_end=d.km_end,
                start_at=d.start_at,
                tz=d.tz,
                budget_min=d.budget_min,
                stops=tuple(stop_state(s, sid) for s, sid in zip(d.stops, d.ids, strict=True)),
            )
        )
    cands = tuple(
        CandidateState(
            c.place.id, c.km_at, c.lateral_km, c.detour_km, c.detour_min, c.road_class, c.region_code
        )
        for lst in (corridor.sights, corridor.food, corridor.fuel, corridor.rest)
        for c in lst
    )
    return EngineState(
        profile_km=profile.km,
        profile_min=profile.minutes,
        region_km=tuple(region_kms),
        toll_hits=tuple(toll_hits),
        drive_time_factor=profile.factor,
        days=tuple(states),
        candidates=cands,
        rerun=ctx.rerun,
        town_kms=tuple((t.town.id, t.km_at) for t in corridor.towns),
    )


def stop_state(s: PlannedStop, sid: str) -> StopState:
    return StopState(
        stop_id=sid,
        kind=s.kind,
        km_at=s.km_at,
        detour_km=s.detour_km,
        detour_min=s.detour_min,
        dwell_min=s.dwell_min,
        fixed=s.fixed,
        auto=s.auto,
        score=s.score,
        place_id=s.place.id if s.place is not None else None,
        region_code=s.region_code,
        reason_key=s.reason_key,
        reason_params=tuple(s.reason_params.items()),
        meal=s.meal,
        litres=round(s.litres, 3),
        coffee=s.coffee,
        pool=s.pool,
    )


def title(labels: tuple[str, ...], inp: NormalizedInput, template_title: str | None) -> str:
    if template_title:
        return template_title
    origin = labels[0]
    dest = labels[-2] if inp.round_trip and len(labels) >= 3 else labels[-1]
    key = "label.round_title" if inp.round_trip else "label.trip_title"
    return ru.text(key, origin=origin, destination=dest)
