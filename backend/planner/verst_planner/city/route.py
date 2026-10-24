"""Assemble a `WalkRoute` (ADR-0013 "Output") from the input, the candidates and the solver's order."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from verst_planner.city.presets import ADULT_PRESETS, DRINK_KINDS, DWELL, MEAL_RUB, PACES
from verst_planner.city.walk import Candidate, Solver, WalkInput, caps_for, hm, polyline, r1
from verst_planner.domain.errors import PlannerError
from verst_planner.domain.model import LatLon
from verst_planner.events import NEVER, CancelToken
from verst_planner.explain import ru

MEAL_MIN_DURATION = 240
SHORTER_MIN = 30  # spec 5.11 §9: a walk ≥ 30 min shorter than asked says why
BUDGET_BOUND = 0.8  # spent ≥ 80 % of a set budget → the budget, not the places, cut the walk


class NotEnoughPois(PlannerError):
    code = "NOT_ENOUGH_POIS"

    def __init__(self, preset: str) -> None:
        super().__init__(f"not enough places for preset {preset!r}")
        self.field = "preset"


@dataclass(frozen=True, slots=True)
class WalkTown:
    id: str
    name: str
    prep: str
    tz: str


def _meal(inp: WalkInput) -> bool:
    return inp.preset == "custom" and "food" in inp.interests and inp.duration_min >= MEAL_MIN_DURATION


def build_walk(
    inp: WalkInput,
    cands: Sequence[Candidate],
    town: WalkTown,
    start_dt: datetime,
    engine_version: str,
    route_id: str,
    cancel: CancelToken = NEVER,
    starts_tomorrow: bool = False,
) -> dict[str, Any]:
    speed = PACES[inp.pace][0]
    meal = _meal(inp)
    meal_min = round(DWELL["meal"] * PACES[inp.pace][1]) if meal else 0
    meal_rub = MEAL_RUB * (inp.adults + inp.children) if meal else 0
    finish = inp.start if inp.return_to_start else None
    budget = None if inp.budget_rub is None else inp.budget_rub - meal_rub
    solver = Solver(
        cands, inp.start, finish, inp.duration_min - meal_min, speed, start_dt, budget, caps_for(inp), cancel
    )
    order = solver.solve()
    if len(order) < 2:
        raise NotEnoughPois(inp.preset)
    ev = solver.evaluate(order)
    stops: list[dict[str, Any]] = []
    shift = 0.0
    meal_after = None
    if meal:
        half = inp.duration_min / 2
        meal_after = min(range(len(order)), key=lambda k: (abs(ev.legs[k].depart - half), k))
    tickets = drinks = 0
    verified_all = True
    for k, ci in enumerate(order):
        c = cands[ci]
        leg = ev.legs[k]
        arrive = start_dt + timedelta(minutes=leg.arrive + shift)
        depart = start_dt + timedelta(minutes=leg.depart + shift)
        if c.kind in DRINK_KINDS:
            drinks += c.cost_rub
        else:
            tickets += c.cost_rub
        verified_all = verified_all and c.hours_verified
        stops.append(
            {
                "id": f"w{len(stops) + 1:02d}",
                "poiId": c.id,
                "kind": c.kind,
                "nameRu": c.name,
                "lat": round(c.point.lat, 6),
                "lon": round(c.point.lon, 6),
                "arriveAt": hm(arrive),
                "departAt": hm(depart),
                "dwellMin": c.dwell_min,
                "walkKmFromPrev": r1(leg.walk_km),
                "walkMinFromPrev": round(leg.walk_min),
                "costRub": c.cost_rub,
                "hoursVerified": c.hours_verified,
                "noteRu": None if c.hours_verified else ru.text("walk.note.hours"),
                "hasPhoto": c.has_photo,
                "tappable": True,
            }
        )
        if meal_after == k:
            meal_start = depart
            shift += meal_min
            stops.append(
                {
                    "id": f"w{len(stops) + 1:02d}",
                    "poiId": None,
                    "kind": "meal",
                    "nameRu": ru.text("walk.meal"),
                    "lat": round(c.point.lat, 6),
                    "lon": round(c.point.lon, 6),
                    "arriveAt": hm(meal_start),
                    "departAt": hm(meal_start + timedelta(minutes=meal_min)),
                    "dwellMin": meal_min,
                    "walkKmFromPrev": 0.0,
                    "walkMinFromPrev": 0,
                    "costRub": meal_rub,
                    "hoursVerified": True,
                    "noteRu": None,
                    "hasPhoto": False,
                    "tappable": False,
                }
            )
    end = start_dt + timedelta(minutes=ev.total_min + shift)
    pts: list[LatLon] = [inp.start, *(cands[ci].point for ci in order)] + ([inp.start] if finish else [])
    lines: list[dict[str, Any]] = [{"key": "tickets", "rub": tickets}]
    if drinks:
        lines.append({"key": "drinks", "rub": drinks})
    if meal_rub:
        lines.append({"key": "food", "rub": meal_rub})
    warnings = []
    if not verified_all:
        warnings.append({"code": "HOURS_UNVERIFIED", "messageRu": ru.text("walk.warning.hours")})
    alcohol = inp.preset in ADULT_PRESETS or any(cands[ci].kind in DRINK_KINDS for ci in order)
    duration = round(ev.total_min + shift)
    total_rub = tickets + drinks + meal_rub
    shorter = _shorter(inp, duration, total_rub)
    if shorter is not None:
        warnings.append({"code": "SHORTER_THAN_ASKED", "messageRu": shorter["messageRu"]})
    start_obj = {
        "lat": round(inp.start.lat, 6),
        "lon": round(inp.start.lon, 6),
        "label": inp.label or town.name,
    }
    return {
        "kind": "walk",
        "engineVersion": engine_version,
        "id": route_id,
        "titleRu": ru.text(f"walk.title.{inp.preset}", town=town.name),
        "townId": town.id,
        "townName": town.name,
        "townPrep": town.prep,
        "preset": inp.preset,
        "startAt": hm(start_dt),
        "startsTomorrow": starts_tomorrow,
        "startNoteRu": ru.text("walk.tomorrow", time=start_dt.strftime("%H:%M")) if starts_tomorrow else None,
        "endAt": hm(end),
        "tz": town.tz,
        "walkKm": r1(ev.walk_km),
        "walkMin": round(ev.walk_min),
        "durationMin": duration,
        "requestedDurationMin": inp.duration_min,
        "shorter": shorter,
        "returnToStart": inp.return_to_start,
        "start": start_obj,
        "finish": start_obj if finish else {**start_obj, **_last(stops)},
        "stops": stops,
        "cost": {"totalRub": total_rub, "lines": lines, "budgetRub": inp.budget_rub},
        "warnings": warnings,
        "responsibleNoteRu": ru.text("walk.responsible") if alcohol else None,
        "polyline": polyline(pts),
        "approxDistances": True,
        "input": _input_echo(inp, start_dt),
    }


def _quarter(minutes: int) -> int:
    return max(15, (minutes + 7) // 15 * 15)


def _shorter(inp: WalkInput, duration: int, total_rub: int) -> dict[str, Any] | None:
    """Why the walk is ≥ 30 min shorter than asked (P1-2), or None."""
    if inp.duration_min - duration < SHORTER_MIN:
        return None
    reason = (
        "budget" if inp.budget_rub is not None and total_rub >= BUDGET_BOUND * inp.budget_rub else "places"
    )
    actual, requested = ru.fmt_duration(_quarter(duration)), ru.fmt_duration(inp.duration_min)
    return {
        "reason": reason,
        "requestedMin": inp.duration_min,
        "actualMin": duration,
        "messageRu": ru.text(f"walk.shorter.{reason}", actual=actual, requested=requested),
    }


def _last(stops: list[dict[str, Any]]) -> dict[str, Any]:
    s = stops[-1]
    return {"lat": s["lat"], "lon": s["lon"], "label": s["nameRu"]}


def _input_echo(inp: WalkInput, start_dt: datetime) -> dict[str, Any]:
    return {
        "start": {"lat": inp.start.lat, "lon": inp.start.lon, "label": inp.label},
        "townId": inp.town_id,
        "preset": inp.preset,
        "durationMin": inp.duration_min,
        "interests": list(inp.interests),
        "pace": inp.pace,
        "budgetRub": inp.budget_rub,
        "returnToStart": inp.return_to_start,
        "startAt": hm(start_dt),
        "crew": {"adults": inp.adults, "children": inp.children},
        "adultConfirmed": inp.adult_confirmed,
        "exclude": sorted(inp.exclude),
    }


__all__ = ["NotEnoughPois", "WalkTown", "build_walk"]
