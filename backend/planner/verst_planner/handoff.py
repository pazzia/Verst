"""Hand-off of a route to the navigator apps (ADR-0014): point selection and link strings.

Works on the JSON the app holds (a trip from `plan_to_json` or a `WalkRoute`), so it needs no world.

- Car (`mode = car`): one day, from `fromStopId` (exclusive) or the day start, to the day end. Kept kinds:
  sight, food, via, overnight, finish (the navigator handles fuel and rest live). The last point is the
  destination; the rest are vias, at most `MAX_VIAS`, chosen by priority (fixed stops, sights by `seq`
  order, food) when there are more, keeping the route order (`truncated = true`).
- Walk (`mode = walk`): start → stops → finish, at most `MAX_WALK_POINTS` per part; longer walks are split
  into consecutive parts that share their boundary point.

Links: `navigator` (car only), `maps` (Яндекс Карты app, `rtt=auto|pd`), `web` (browser). Coordinates with 6
decimals; `fromHere` lets the app start from the current position.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

MAX_VIAS = 8
MAX_WALK_POINTS = 10
CAR_KINDS = ("sight", "food", "via", "overnight", "finish")
PRIORITY = {"via": 0, "overnight": 0, "finish": 0, "sight": 1, "food": 2}


class HandoffError(ValueError):
    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.reason = reason


def _c(x: float) -> str:
    return f"{x:.6f}"


def _pt(lat: float, lon: float, name: str, role: str) -> dict[str, Any]:
    return {"lat": round(float(lat), 6), "lon": round(float(lon), 6), "nameRu": name, "role": role}


def rtext(points: list[dict[str, Any]], from_here: bool) -> str:
    coords = [f"{_c(p['lat'])},{_c(p['lon'])}" for p in points]
    return ("~" if from_here else "") + "~".join(coords)


def navigator_link(points: list[dict[str, Any]], from_here: bool) -> str:
    dest = points[-1]
    parts = [f"lat_to={_c(dest['lat'])}", f"lon_to={_c(dest['lon'])}"]
    vias = points[:-1]
    if not from_here:
        start, vias = points[0], points[1:-1]
        parts += [f"lat_from={_c(start['lat'])}", f"lon_from={_c(start['lon'])}"]
    for i, v in enumerate(vias):
        parts += [f"lat_via_{i}={_c(v['lat'])}", f"lon_via_{i}={_c(v['lon'])}"]
    return "yandexnavi://build_route_on_map?" + "&".join(parts)


def maps_links(points: list[dict[str, Any]], from_here: bool, rtt: str) -> dict[str, str]:
    q = quote(rtext(points, from_here), safe=",~.")
    return {
        "maps": f"yandexmaps://maps.yandex.ru/?rtext={q}&rtt={rtt}",
        "web": f"https://yandex.ru/maps/?rtext={q}&rtt={rtt}",
    }


def _pick_vias(cands: list[tuple[int, dict[str, Any]]]) -> tuple[list[dict[str, Any]], bool]:
    if len(cands) <= MAX_VIAS:
        return [p for _k, p in cands], False
    ranked = sorted(range(len(cands)), key=lambda i: (cands[i][0], i))[:MAX_VIAS]
    return [cands[i][1] for i in sorted(ranked)], True


def car(trip: dict[str, Any], day: int | None, from_stop_id: str | None, from_here: bool) -> dict[str, Any]:
    days = trip.get("daysList")
    if not isinstance(days, list) or not days:
        raise HandoffError("route", "no_days")
    if from_stop_id is not None:
        found = next((d for d in days for s in d.get("stops", []) if s.get("id") == from_stop_id), None)
        if found is None:
            raise HandoffError("fromStopId", "not_found")
        day_obj = found
    else:
        day_no = day or 1
        day_obj = next((d for d in days if d.get("day") == day_no), None)
        if day_obj is None:
            raise HandoffError("day", "not_found")
    stops = day_obj.get("stops", [])
    start_i = 0
    if from_stop_id is not None:
        start_i = next(i for i, s in enumerate(stops) if s.get("id") == from_stop_id)
    origin = stops[start_i]
    after = [s for s in stops[start_i + 1 :] if s.get("kind") in CAR_KINDS and s.get("lat") is not None]
    if not after:
        raise HandoffError("fromStopId", "nothing_after")
    dest = after[-1]
    cands = [
        (
            0 if s.get("fixed") else PRIORITY.get(str(s.get("kind")), 3),
            _pt(s["lat"], s["lon"], s.get("name", ""), "via"),
        )
        for s in after[:-1]
    ]
    vias, truncated = _pick_vias(cands)
    points = [_pt(dest["lat"], dest["lon"], dest.get("name", ""), "destination")]
    points = vias + points
    if not from_here:
        points = [_pt(origin["lat"], origin["lon"], origin.get("name", ""), "origin"), *points]
    links = {"navigator": navigator_link(points, from_here), **maps_links(points, from_here, "auto")}
    return {
        "mode": "car",
        "day": day_obj.get("day"),
        "parts": [{"index": 1, "points": points, "links": links}],
        "truncated": truncated,
    }


def walk(route: dict[str, Any], from_stop_id: str | None, from_here: bool) -> dict[str, Any]:
    stops = route.get("stops")
    if not isinstance(stops, list):
        raise HandoffError("route", "no_stops")
    seq: list[dict[str, Any]] = []
    start = route.get("start") or {}
    if start.get("lat") is not None:
        seq.append(_pt(start["lat"], start["lon"], start.get("label", ""), "origin"))
    seq += [_pt(s["lat"], s["lon"], s.get("nameRu", ""), "via") for s in stops]
    finish = route.get("finish") or {}
    if finish.get("lat") is not None:
        seq.append(_pt(finish["lat"], finish["lon"], finish.get("label", ""), "destination"))
    if from_stop_id is not None:
        idx = next((i for i, s in enumerate(stops) if s.get("id") == from_stop_id), None)
        if idx is None:
            raise HandoffError("fromStopId", "not_found")
        offset = 1 if start.get("lat") is not None else 0
        seq = seq[offset + idx :]
    if from_here and seq and seq[0]["role"] == "origin":
        seq = seq[1:]
    if len(seq) < (1 if from_here else 2):
        raise HandoffError("route", "too_few_points")
    parts: list[dict[str, Any]] = []
    i = 0
    first = True
    while True:
        cap = MAX_WALK_POINTS - (1 if first and from_here else 0)
        chunk = seq[i : i + cap]
        parts.append(
            {"index": len(parts) + 1, "points": chunk, "links": maps_links(chunk, from_here and first, "pd")}
        )
        if i + len(chunk) >= len(seq):
            break
        i += len(chunk) - 1  # consecutive parts share their boundary point
        first = False
    return {"mode": "walk", "day": None, "parts": parts, "truncated": False}


def handoff(route: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    mode = options.get("mode")
    from_here = options.get("fromHere", True)
    if not isinstance(from_here, bool):
        raise HandoffError("fromHere", "not_bool")
    from_stop = options.get("fromStopId")
    if from_stop is not None and not isinstance(from_stop, str):
        raise HandoffError("fromStopId", "not_string")
    if mode == "car":
        day = options.get("day")
        if day is not None and (isinstance(day, bool) or not isinstance(day, int)):
            raise HandoffError("day", "not_int")
        return car(route, day, from_stop, from_here)
    if mode == "walk":
        return walk(route, from_stop, from_here)
    raise HandoffError("mode", "unknown")
