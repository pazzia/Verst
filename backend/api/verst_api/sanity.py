"""What a saved trip may claim, and what a shared link shows (acceptance 28.10: QA B-2, security B-3).

A saved trip comes from the phone, so the server does not take its numbers on trust: the units the cost
is computed from must be plausible (`check_saved_trip`), and the cost lines and totals are recomputed from
them by the engine before storage (`routes.save_trip`). A shared link is read by anyone who has it, so it
shows the plan and the cost, never who travels, with what budget, when exactly, or the engine's internals
(`public_trip`).
"""

from __future__ import annotations

from typing import Any

from verst_api.errors import ApiError

# Plausible bounds of what the engine ever produces (Russia, a family car, SPEC §7). Wide on purpose: they
# catch forged or corrupted trips, not unusual ones.
MAX_DAYS = 30
MAX_KM = 15_000
FUEL_PRICE_RUB = (20.0, 300.0)  # per litre
CONSUMPTION_L = (2.0, 40.0)  # per 100 km
MAX_TOLL_RUB = 50_000  # one toll unit
MAX_NIGHT_RUB = 300_000  # one room-night
MAX_CHECK_RUB = 20_000  # one meal check
MAX_TICKET_RUB = 50_000

# A shared trip keeps these keys; everything else (input with crew, budget and start time, engineState, …) is
# the owner's.
PUBLIC_TRIP_KEYS = (
    "title",
    "km",
    "days",
    "nights",
    "roundTrip",
    "daysList",
    "approxDistances",
    "engineVersion",
)
PUBLIC_COST_KEYS = ("lines", "reserveOn", "subtotalRub", "totalRub", "pricesAsOf")
PUBLIC_DAY_KEYS = ("day", "km", "driveMin", "tz", "stops")
TIME_KEYS = ("arriveAt", "departAt", "startAt", "endAt")


def _bad(field: str, reason: str = "out_of_range") -> ApiError:
    return ApiError("INVALID_INPUT", {"field": f"trip.{field}", "reason": reason})


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int | float):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    return None


def _within(v: Any, lo: float, hi: float, field: str) -> None:
    n = _num(v)
    if n is None or not lo <= n <= hi:
        raise _bad(field)


def check_saved_trip(trip: dict[str, Any]) -> None:
    """Raises INVALID_INPUT (`trip.<field>`, `out_of_range`) when the trip claims what no plan can."""
    days = trip.get("daysList")
    if not isinstance(days, list) or not days:
        raise _bad("daysList", "empty")
    _within(trip.get("days"), 1, MAX_DAYS, "days")
    if trip.get("days") != len(days):
        raise _bad("days", "mismatch")
    _within(trip.get("km"), 1, MAX_KM, "km")
    for i, d in enumerate(days):
        if not isinstance(d, dict):
            raise _bad(f"daysList[{i}]", "not_an_object")
        _within(d.get("km"), 0, MAX_KM, f"daysList[{i}].km")
    cost = trip.get("cost")
    units = cost.get("units") if isinstance(cost, dict) else None
    if not isinstance(units, dict):
        raise _bad("cost.units", "missing")
    fuel = units.get("fuel")
    if isinstance(fuel, dict):
        _within(fuel.get("consumption"), *CONSUMPTION_L, "cost.units.fuel.consumption")
        for i, r in enumerate(fuel.get("regions") or []):
            _within(r.get("priceRub"), *FUEL_PRICE_RUB, f"cost.units.fuel.regions[{i}].priceRub")
            _within(r.get("km"), 0, MAX_KM, f"cost.units.fuel.regions[{i}].km")
    for i, t in enumerate(units.get("tolls") or []):
        _within(t.get("rub"), 0, MAX_TOLL_RUB, f"cost.units.tolls[{i}].rub")
    for i, n in enumerate(units.get("nights") or []):
        _within(n.get("priceNightRub"), 0, MAX_NIGHT_RUB, f"cost.units.nights[{i}].priceNightRub")
        for j, o in enumerate(n.get("options") or []):
            _within(
                o.get("priceNightRub"), 0, MAX_NIGHT_RUB, f"cost.units.nights[{i}].options[{j}].priceNightRub"
            )
    for i, m in enumerate(units.get("meals") or []):
        _within(m.get("checkRub"), 0, MAX_CHECK_RUB, f"cost.units.meals[{i}].checkRub")
    for i, t in enumerate(units.get("tickets") or []):
        _within(t.get("adultRub"), 0, MAX_TICKET_RUB, f"cost.units.tickets[{i}].adultRub")
        _within(t.get("childRub"), 0, MAX_TICKET_RUB, f"cost.units.tickets[{i}].childRub")


def public_trip(trip: dict[str, Any]) -> dict[str, Any]:
    """The part of a stored trip a link recipient sees: days, stops and the cost lines; no crew, budget, start
    time, vehicle or engine state."""
    out = {k: trip[k] for k in PUBLIC_TRIP_KEYS if k in trip}
    out["daysList"] = [
        _times_of_day({k: d[k] for k in PUBLIC_DAY_KEYS if k in d})
        for d in trip.get("daysList") or []
        if isinstance(d, dict)
    ]
    cost = trip.get("cost")
    if isinstance(cost, dict):
        out["cost"] = {k: cost[k] for k in PUBLIC_COST_KEYS if k in cost}
    inp = trip.get("input")
    if isinstance(inp, dict):
        # towns only (the stored copy is already scrubbed to towns, R-07)
        out["input"] = {
            k: {"label": inp[k].get("label")}
            for k in ("origin", "destination")
            if isinstance(inp.get(k), dict)
        }
    return out


def _times_of_day(node: Any) -> Any:
    """`arriveAt` / `departAt` (also inside alternatives) as times of day only (`…T08:31` → `08:31`): the
    date of the trip stays private."""
    if isinstance(node, list):
        return [_times_of_day(v) for v in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for k, v in node.items():
        if k in TIME_KEYS and isinstance(v, str) and "T" in v:
            out[k] = v.split("T", 1)[1][:5]
        else:
            out[k] = _times_of_day(v)
    return out
