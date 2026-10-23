"""Invariants applied to every golden plan (A§13.3). Each takes a `GoldenRun` and raises AssertionError."""

from __future__ import annotations

import itertools
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from verst_planner.adapters.fake import FakeWorld
from verst_planner.config import PlannerConfig
from verst_planner.cost.recompute import recompute
from verst_planner.domain import codec
from verst_planner.domain.enums import OvernightFallback, StopKind, Tag, WarningCode
from verst_planner.domain.model import CostOverrides, ReplaceableKinds, TripPlan
from verst_planner.events import PlanEvent, StageEvent, StopEvent
from verst_planner.hours import parse

LATIN = re.compile(r"[A-Za-z]")
ALT_WINDOW_MIN = 45
LUNCH = ("12:00", "14:30")


@dataclass
class GoldenRun:
    case: dict[str, Any]
    plan: TripPlan
    world: FakeWorld
    events: list[PlanEvent] = field(default_factory=list)
    replan: Callable[[], TripPlan] | None = None

    @property
    def json(self) -> dict[str, Any]:
        return codec.plan_to_json(self.plan, trip_id="trp_golden")


def _r(x: Decimal, step: int) -> int:
    return int((x / step).quantize(Decimal(1), ROUND_HALF_UP)) * step


def day_cap(run: GoldenRun) -> None:
    """Every non-template day: day.km ≤ 1.05 × dailyKm (US-06)."""
    if run.plan.overnight_reasons and all(
        r.fallback is OvernightFallback.TEMPLATE for r in run.plan.overnight_reasons
    ):
        return
    cap = 1.05 * run.plan.input.daily_km
    for d in run.plan.days_list:
        assert d.km <= cap + 1e-9, f"day {d.day}: {d.km} km > {cap}"


def dog_lodging(run: GoldenRun) -> None:
    """crew.dog ⇒ every selected hotel and every hotel option is dogs_allowed (US-05, SPEC §17)."""
    if not run.plan.input.crew.dog:
        return
    for d in run.plan.days_list:
        for s in d.stops:
            if s.kind is StopKind.OVERNIGHT:
                if s.selected_hotel_id is not None:
                    assert Tag.DOGS_ALLOWED in run.world.places[s.selected_hotel_id].tags, s.selected_hotel_id
                for h in s.hotel_options:
                    assert Tag.DOGS_ALLOWED in h.tags, h.place_id


def monotonic_time(run: GoldenRun) -> None:
    prev_end: datetime | None = None
    prev_tz: str | None = None
    from zoneinfo import ZoneInfo

    for d in run.plan.days_list:
        start = d.start_at.replace(tzinfo=ZoneInfo(d.tz))
        if prev_end is not None and prev_tz is not None:
            assert start > prev_end.replace(tzinfo=ZoneInfo(prev_tz)), (
                f"day {d.day} starts before the previous end"
            )
        times: list[tuple[datetime | None, datetime | None, str]] = [
            (s.arrive_at, s.depart_at, s.tz) for s in d.stops
        ]
        for (a1, d1, tz1), (a2, _d2, tz2) in itertools.pairwise(times):
            if a1 is not None and d1 is not None:
                assert a1 <= d1, f"day {d.day}: arrive after depart"
            assert d1 is not None and a2 is not None
            assert d1.replace(tzinfo=ZoneInfo(tz1)) <= a2.replace(tzinfo=ZoneInfo(tz2)), (
                f"day {d.day}: overlap"
            )
        prev_end, prev_tz = d.end_at, d.tz


def monotonic_km(run: GoldenRun) -> None:
    kms = [s.km_at for d in run.plan.days_list for s in d.stops]
    assert kms == sorted(kms), "kmAt decreases"
    assert all(s.km_from_prev >= 0 for d in run.plan.days_list for s in d.stops)
    assert sum(d.km for d in run.plan.days_list) == run.plan.km, "Σ day km ≠ trip km"


def hours_open(run: GoldenRun) -> None:
    for d in run.plan.days_list:
        for s in d.stops:
            if s.kind is StopKind.SIGHT and s.place_id:
                oh = run.world.places[s.place_id].opening_hours
                if oh:
                    assert s.arrive_at is not None and s.depart_at is not None
                    assert parse(oh).covers(s.arrive_at, s.depart_at), f"{s.name_ru} closed during the visit"


def lunch_window(run: GoldenRun) -> None:
    for d in run.plan.days_list:
        for s in d.stops:
            if s.kind is StopKind.FOOD:
                assert s.arrive_at is not None
                hhmm = s.arrive_at.strftime("%H:%M")
                assert LUNCH[0] <= hhmm <= LUNCH[1], f"lunch at {hhmm}"


def fuel_range(run: GoldenRun) -> None:
    """Simulated tank never below 0: fuel stops (and FUEL_GAP virtual refuels) refill to full."""
    v = run.plan.input.vehicle
    full = v.tank_l / v.consumption_l_per_100km * 100
    fills = [0.0] + [float(s.km_at) for d in run.plan.days_list for s in d.stops if s.kind is StopKind.FUEL]
    for w in run.plan.warnings:
        if w.code is WarningCode.FUEL_GAP:
            km = float(w.detail.split("=")[1])
            fills.append(km + 40)  # the walk continues as if refuelled after the look-ahead window
    fills = sorted(fills)
    total = float(run.plan.days_list[-1].stops[-1].km_at)
    for a, b in itertools.pairwise([*fills, total]):
        assert b - a <= full + 1, f"tank empty between km {a} and {b} (range {full:.0f})"


def unique_places(run: GoldenRun) -> None:
    ids = [
        s.place_id
        for d in run.plan.days_list
        for s in d.stops
        if s.place_id and s.kind is not StopKind.OVERNIGHT
    ]
    assert len(ids) == len(set(ids)), "a place is used twice"


def alternatives(run: GoldenRun) -> None:
    """A§16.6: ≤ 3 per stop, within ±45 min, unused places; each day patch covers the whole new day."""
    for d in run.plan.days_list:
        ids = [x.id for x in d.stops]
        for s in d.stops:
            assert len(s.alternatives) <= 3
            assert s.replaceable == (
                s.kind in ReplaceableKinds and s.kind is not StopKind.VIA and _not_fixed(s, run)
            )
            for a in s.alternatives:
                assert a.place_id != s.place_id
                assert s.arrive_at is not None and a.stop.arrive_at is not None
                assert abs((a.stop.arrive_at - s.arrive_at).total_seconds()) / 60 <= ALT_WINDOW_MIN
                order = [p.stop_id for p in a.day_patch]
                assert sorted(order) == sorted(ids), f"{a.id}: day patch does not cover the day"
                assert [p.seq for p in a.day_patch] == [x.seq for x in d.stops], f"{a.id}: seq"
                patched = next(p for p in a.day_patch if p.stop_id == s.id)
                assert patched.arrive_at == a.stop.arrive_at, f"{a.id}: patch ≠ rendered alternative"


def alternatives_note(run: GoldenRun) -> None:
    """A§16.6: a replaceable stop with fewer than two alternatives explains it; others carry no note."""
    from verst_planner.explain.templates import ReasonTemplates

    t = ReasonTemplates.default()
    for d in run.plan.days_list:
        for s in d.stops:
            if not s.replaceable:
                expected = None
            else:
                expected = {0: t.render("alternatives.none"), 1: t.render("alternatives.one")}.get(
                    len(s.alternatives)
                )
            assert s.alternatives_note_ru == expected, f"{s.id}: note {s.alternatives_note_ru!r}"


def alternatives_share(plan: TripPlan) -> tuple[int, int]:
    """(replaceable stops with ≥ 2 alternatives, replaceable stops)."""
    rep = [s for d in plan.days_list for s in d.stops if s.replaceable]
    return sum(1 for s in rep if len(s.alternatives) >= 2), len(rep)


def _not_fixed(s: Any, run: GoldenRun) -> bool:
    """Template `stop` sights are fixed (never replaceable)."""
    rr = run.world.ready_routes.get(run.plan.input.ready_route_id or "")
    return not (rr is not None and any(p.place_id == s.place_id for p in rr.points))


def cost_sum(run: GoldenRun) -> None:
    c = run.plan.cost
    assert len(c.lines) == 6
    assert all(line.rub % 10 == 0 for line in c.lines)
    assert c.total_rub % 100 == 0
    subtotal = sum(line.rub for line in c.lines[:5])
    assert subtotal == c.subtotal_rub
    reserve = c.lines[5].rub
    assert reserve == _r(Decimal(subtotal) * Decimal("0.10"), 10)
    assert c.total_rub == _r(Decimal(subtotal + (reserve if c.reserve_on else 0)), 100)
    people = run.plan.input.crew.adults + run.plan.input.crew.children
    assert c.per_person_rub == _r(Decimal(c.total_rub) / people, 100)
    if c.budget_rub is not None:
        assert c.remaining_rub == c.budget_rub - c.total_rub
        assert c.over_budget == (c.remaining_rub < 0)


def cost_recompute(run: GoldenRun) -> None:
    c = run.plan.cost
    offline = recompute(c.units, run.plan.input.crew, c.reserve_on, c.budget_rub, CostOverrides())
    assert offline == _without_hints(c), "server cost ≠ offline recompute"


def _without_hints(c: Any) -> Any:
    import dataclasses

    return dataclasses.replace(c, hints_ru=())


def reasons(run: GoldenRun) -> None:
    for r in run.plan.overnight_reasons:
        assert r.text, f"night {r.day}: empty reason"
        if r.fallback is not OvernightFallback.NO_HOTEL:
            assert r.candidates, f"night {r.day}: no candidates"
    for d in run.plan.days_list:
        for s in d.stops:
            if s.kind in (
                StopKind.FUEL,
                StopKind.REST,
                StopKind.FOOD,
                StopKind.SIGHT,
                StopKind.OVERNIGHT,
                StopKind.START,
                StopKind.FINISH,
            ):
                assert s.reason_ru, f"{s.id} {s.name_ru}: no reason"


def determinism(run: GoldenRun) -> None:
    assert run.replan is not None
    again = run.replan()
    a = json.dumps(codec.plan_to_json(run.plan, public=False), ensure_ascii=False, sort_keys=True)
    b = json.dumps(codec.plan_to_json(again, public=False), ensure_ascii=False, sort_keys=True)
    assert a == b, "planning twice gave different JSON"


def events(run: GoldenRun) -> None:
    ev = run.events
    assert ev, "no events"
    first = ev[0]
    assert isinstance(first, StageEvent) and first.key.value == "split", "first event is not stage split"
    progress = [e.progress for e in ev if isinstance(e, StageEvent)]
    assert progress == sorted(progress), "progress goes backwards"
    final = [(e.stop_id, e.kind) for e in ev if isinstance(e, StopEvent) and not e.provisional]
    stops = [(s.id, s.kind) for d in run.plan.days_list for s in d.stops]
    assert final == stops, "final stop events differ from the plan"


def russian_text(run: GoldenRun) -> None:
    p = run.plan
    texts: list[str] = [p.title_ru, *p.cost.hints_ru]
    texts += [w.message_ru for w in p.warnings]
    for r in p.overnight_reasons:
        texts += [r.text, r.town, *r.candidates]
    for line in p.cost.lines:
        texts += [line.title_ru, line.formula_ru]
        for b in line.breakdown:
            texts += [b.label_ru, b.formula_ru]
    for d in p.days_list:
        for s in d.stops:
            texts += [s.name_ru, s.reason_ru, s.note_ru or ""]
            for a in s.alternatives:
                texts += [a.name_ru, a.stop.reason_ru]
    for t in texts:
        assert not LATIN.search(t), f"Latin letters in {t!r}"


def _cfg(run: GoldenRun) -> PlannerConfig:
    return PlannerConfig.from_dict(run.case.get("config") or {})


def _drives(run: GoldenRun) -> list[tuple[Any, Any, float]]:
    """(rendered stop, stop state, driving minutes since the previous break) for every stop after START.

    Driving = arrival − departure of the previous break − dwell of the non-break stops in between, from the
    rendered (minute-rounded) times.
    """
    min_dwell = _cfg(run).rest.break_min_dwell
    out = []
    for d, ds in zip(run.plan.days_list, run.plan.engine_state.days, strict=True):
        prev = d.stops[0].depart_at
        between = 0
        for s, st in zip(d.stops[1:], ds.stops[1:], strict=True):
            assert s.arrive_at is not None and prev is not None
            drive = (s.arrive_at - prev).total_seconds() / 60 - between
            out.append((s, st, drive))
            if s.kind in (StopKind.OVERNIGHT, StopKind.FINISH):
                break
            if s.dwell_min >= min_dwell:
                prev, between = s.depart_at, 0
            else:
                between += s.dwell_min
    return out


def _rest_stage(s: Any, st: Any) -> bool:
    """Stops placed by stage 7: rest-pool stops and range fuel stops upgraded to coffee."""
    return bool(st.pool == "rest" or (s.kind is StopKind.FUEL and st.coffee))


def break_spacing(run: GoldenRun) -> None:
    """A§16.2: a stage-7 stop is at least `rest.min_gap_min` of driving after the previous break and has a
    detour of at most `rest.max_detour_min` (1 min tolerance for the minute rounding of rendered times)."""
    rc = _cfg(run).rest
    for s, st, drive in _drives(run):
        if _rest_stage(s, st):
            gap = f"{s.id} {s.name_ru}: {drive:.0f} min after the previous break"
            assert drive >= rc.min_gap_min - 1, gap
            if st.pool == "rest":
                assert st.detour_min <= rc.max_detour_min, f"{s.id}: detour {st.detour_min} min"


def rest_reason(run: GoldenRun) -> None:
    """`rest.generic` names the driving since the previous break, rounded to 15 min (A§16.2)."""
    from verst_planner.explain import ru
    from verst_planner.explain.templates import ReasonTemplates
    from verst_planner.pipeline.rest import rounded_drive

    t = ReasonTemplates.default()
    for s, st, drive in _drives(run):
        if st.reason_key != "rest.generic":
            continue
        params = dict(st.reason_params)
        ok = {
            t.render("rest.generic", **{**params, "drive": ru.duration_genitive(rounded_drive(x))})
            for x in (drive - 1, drive, drive + 1)
        }
        assert s.reason_ru in ok, f"{s.id}: {s.reason_ru!r} after {drive:.0f} min of driving"


def lunch_present(run: GoldenRun) -> None:
    """A§16.2 (D-18): every day whose schedule overlaps the lunch window has a lunch stop, unless the case
    names it in `expect.noLunchDays` (no feasible food place on that day's corridor, justified there)."""
    lo, hi = _cfg(run).lunch_window
    exempt = set(run.case["expect"].get("noLunchDays", []))
    for d in run.plan.days_list:
        w_lo = d.start_at.replace(hour=lo.hour, minute=lo.minute)
        w_hi = d.start_at.replace(hour=hi.hour, minute=hi.minute)
        overlaps = d.start_at < w_hi and d.end_at > w_lo
        has = any(s.kind is StopKind.FOOD for s in d.stops)
        if overlaps and d.day not in exempt:
            assert has, f"day {d.day} ({d.start_at:%H:%M}-{d.end_at:%H:%M}) has no lunch"


def formula_km(run: GoldenRun) -> None:
    """A§16.7: the fuel formula shows `TripPlan.km` (Σ day km); exact region km stay in the units."""
    from verst_planner.explain import ru

    fuel = run.plan.cost.lines[0]
    km = ru.fmt_km(run.plan.km)
    assert fuel.formula_ru.startswith(f"{km} км"), f"{fuel.formula_ru!r} ≠ {km} км"
    assert run.plan.cost.units.fuel.trip_km == run.plan.km


ALL: dict[str, Callable[[GoldenRun], None]] = {
    "day_cap": day_cap,
    "dog_lodging": dog_lodging,
    "monotonic_time": monotonic_time,
    "monotonic_km": monotonic_km,
    "hours_open": hours_open,
    "lunch_window": lunch_window,
    "fuel_range": fuel_range,
    "unique_places": unique_places,
    "alternatives": alternatives,
    "cost_sum": cost_sum,
    "cost_recompute": cost_recompute,
    "reasons": reasons,
    "determinism": determinism,
    "events": events,
    "russian_text": russian_text,
    "break_spacing": break_spacing,
    "rest_reason": rest_reason,
    "lunch_present": lunch_present,
    "alternatives_note": alternatives_note,
    "formula_km": formula_km,
}
