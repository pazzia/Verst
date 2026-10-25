# ruff: noqa: RUF001, RUF002 -- Cyrillic route letters and dash variants are data in this module.
"""GraphHopper `/route` JSON → `Route` (ADR-0017 §4). Pure functions, no I/O.

Response schema: https://github.com/graphhopper/graphhopper/blob/11.0/docs/web/api-doc.md ("Example JSON
output"; `details`: "The returned format for one detail segment is `[fromRef, toRef, value]`", refs index
`points`).
Shapes seen on a GraphHopper 11.0 server (fixtures in `tests/data/graphhopper/`):

- `points.coordinates`: `[[lon, lat], ...]` (`points_encoded: false`); a via point appears once.
- `details.distance` / `details.time`: one interval per edge, metres (float) / milliseconds (int); they sum to
  `paths[0].distance` / `paths[0].time`.
- `details.leg_distance`: one interval per leg; its boundaries are the waypoint indices.
- `details.road_class`: lower-case `RoadClass` names (`motorway`, `trunk`, ..., `residential`); a link has
  the class of its road (`motorway_link` → `motorway`).
- `details.toll`: `no` / `hgv` / `all` (`missing` before 11.0); `null` where unknown.
- `details.street_ref`: the OSM `ref`, several refs joined by ", " (`"М-10;Е105"` → `"М-10, Е105"`), or
  `null`.

GraphHopper drops the inner vertices of a straight edge (a 16 km motorway is one segment), while the engine's
stages were built on routes with a vertex at least every ~1 km (FakeRouting, HybridRouting). `to_route`
therefore inserts interpolated points so no segment is longer than `max_segment_km`.
"""

from __future__ import annotations

import itertools
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from verst_planner.domain.enums import RoadClass
from verst_planner.domain.errors import InvalidInput
from verst_planner.domain.model import LatLon, Route, RouteDetail
from verst_planner.geo.distance import haversine_km

DETAILS = ("road_class", "toll", "street_ref", "distance", "time", "leg_distance")
"""Path details requested on every call; `road_class` and `toll` must be in `graph.encoded_values`
(infra/routing/config.yml)."""

ROAD_CLASS = {
    "motorway": RoadClass.MOTORWAY,
    "trunk": RoadClass.TRUNK,
    "primary": RoadClass.PRIMARY,
    "secondary": RoadClass.SECONDARY,
}
"""Everything else (tertiary, residential, unclassified, service, track, ...) and `null` → OTHER."""

TOLL_VALUES = frozenset({"all"})
"""`all` = every vehicle pays. `hgv` (trucks only), `no`, `missing` and `null` are free for a car."""

# A§5.3.1: a federal/regional route number written with a Latin letter is normalised to the Cyrillic one.
_REF_LETTER = {"M": "М", "R": "Р", "P": "Р", "A": "А"}
_REF = re.compile(r"([MRPAМРА])\s*[-‐‑–—]?\s*(\d+)(.*)", re.IGNORECASE)


class MappingError(ValueError):
    """A 200 response without the shape this module needs; the adapter reports an upstream failure."""


@dataclass(frozen=True, slots=True)
class Leg:
    from_idx: int
    to_idx: int


def normalize_ref(raw: object) -> str | None:
    """`"M-10, Е105"` → `"М-10"`: the first ref, a Latin route letter replaced by the Cyrillic one."""
    if not isinstance(raw, str):
        return None
    first = re.split(r"[;,]", raw, maxsplit=1)[0].strip()
    if not first:
        return None
    m = _REF.fullmatch(first)
    if m is None:
        return first
    letter = m.group(1).upper()
    return f"{_REF_LETTER.get(letter, letter)}-{m.group(2)}{m.group(3).rstrip()}"


def road_class(raw: object) -> RoadClass:
    return ROAD_CLASS.get(raw, RoadClass.OTHER) if isinstance(raw, str) else RoadClass.OTHER


def is_toll(raw: object) -> bool:
    return isinstance(raw, str) and raw.lower() in TOLL_VALUES


# ---------------------------------------------------------------------------------------------- parsing


def _num(v: Any, what: str) -> float:
    if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
        raise MappingError(f"{what}: not a number")
    return float(v)


def _coords(raw: Any, what: str) -> list[LatLon]:
    if isinstance(raw, dict):
        raw = raw.get("coordinates")
    if not isinstance(raw, list):
        raise MappingError(f"{what}: expected GeoJSON coordinates (points_encoded=false)")
    out: list[LatLon] = []
    for c in raw:
        if not isinstance(c, list) or len(c) < 2:
            raise MappingError(f"{what}: bad coordinate")
        try:
            out.append(LatLon(_num(c[1], what), _num(c[0], what)))  # [lon, lat(, ele)]
        except InvalidInput as e:  # LatLon range check
            raise MappingError(f"{what}: {e}") from e
    return out


def _is_num(v: Any) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v) and v >= 0


def _intervals(
    details: dict[str, Any], key: str, n_points: int, numeric: bool = False
) -> list[tuple[int, int, Any]] | None:
    """`[[from, to, value], ...]` covering 0 .. n_points-1 without gaps (with `numeric`, every value a number
    >= 0), or None when absent or malformed: the caller then falls back to the path totals."""
    raw = details.get(key)
    if not isinstance(raw, list) or not raw:
        return None
    out: list[tuple[int, int, Any]] = []
    expect = 0
    for item in raw:
        if not isinstance(item, list) or len(item) != 3:
            return None
        lo, hi, value = item
        if not isinstance(lo, int) or not isinstance(hi, int) or lo != expect or hi < lo or hi >= n_points:
            return None
        if numeric and not _is_num(value):
            return None
        out.append((lo, hi, value))
        expect = hi
    return out if expect == n_points - 1 else None


def _scaled(
    seg: list[float], spans: list[tuple[int, int, Any]] | None, scale: float, total: float
) -> list[float]:
    """Per-segment amounts: each detail interval's value spread over its segments in proportion to `seg`
    (straight-line km); without a valid detail list, `total` spread over the whole route the same way."""
    if spans is None:
        spans = [(0, len(seg), total / scale)]
    out = [0.0] * len(seg)
    for lo, hi, value in spans:
        amount = float(value) * scale
        if hi == lo:
            continue
        weight = sum(seg[lo:hi])
        for i in range(lo, hi):
            out[i] = amount * (seg[i] / weight if weight > 0 else 1.0 / (hi - lo))
    return out


def _legs(details: dict[str, Any], n_points: int, n_waypoints: int) -> list[int] | None:
    spans = _intervals(details, "leg_distance", n_points, numeric=True)
    if spans is None or len(spans) != n_waypoints - 1:
        return None
    return [0] + [hi for _lo, hi, _v in spans]


def _nearest_forward(points: Sequence[LatLon], targets: Sequence[LatLon]) -> list[int]:
    """Waypoint indices without `leg_distance`: for each snapped waypoint, the nearest point at or after the
    previous waypoint's index (a route can pass a via point's location before it reaches it)."""
    out: list[int] = []
    start = 0
    for k, t in enumerate(targets):
        if k == 0:
            out.append(0)
            continue
        if k == len(targets) - 1:
            out.append(len(points) - 1)
            continue
        best = min(range(start, len(points)), key=lambda i: (haversine_km(points[i], t), i))
        out.append(best)
        start = best
    return out


def _densify(
    points: list[LatLon], seg_km: list[float], seg_min: list[float], max_segment_km: float
) -> tuple[list[LatLon], list[float], list[float], list[int]]:
    """Insert points so that no segment is longer than `max_segment_km` road km. Returns the new points,
    cumulative km and minutes, and the new index of every original point."""
    new_pts = [points[0]]
    cum_km = [0.0]
    cum_min = [0.0]
    index = [0]
    for i, (km, mins) in enumerate(zip(seg_km, seg_min, strict=True)):
        a, b = points[i], points[i + 1]
        n = max(1, math.ceil(km / max_segment_km - 1e-9))
        k0, m0 = cum_km[-1], cum_min[-1]
        for k in range(1, n + 1):
            f = k / n
            new_pts.append(b if k == n else LatLon(a.lat + (b.lat - a.lat) * f, a.lon + (b.lon - a.lon) * f))
            cum_km.append(k0 + km * f)
            cum_min.append(m0 + mins * f)
        index.append(len(new_pts) - 1)
    return new_pts, cum_km, cum_min, index


def _road_details(details: dict[str, Any], n_points: int, index: list[int]) -> tuple[RouteDetail, ...]:
    """One `RouteDetail` per run of equal (class, ref, toll), on the densified indices."""
    layers = {key: _intervals(details, key, n_points) or [(0, n_points - 1, None)] for key in DETAILS[:3]}
    bounds = {b for spans in layers.values() for lo, hi, _ in spans for b in (lo, hi)}
    cuts = sorted({0, n_points - 1} | bounds)

    def value_at(key: str, lo: int) -> Any:
        for a, b, v in layers[key]:
            if a <= lo < b:
                return v
        return None

    out: list[RouteDetail] = []
    for lo, hi in itertools.pairwise(cuts):
        cls = road_class(value_at("road_class", lo))
        ref = normalize_ref(value_at("street_ref", lo))
        toll = is_toll(value_at("toll", lo))
        if out and (out[-1].road_class, out[-1].road_ref, out[-1].toll) == (cls, ref, toll):
            last = out[-1]
            out[-1] = RouteDetail(last.from_idx, index[hi], cls, ref, toll)
        else:
            out.append(RouteDetail(index[lo], index[hi], cls, ref, toll))
    if not out:  # a single point: start and finish snapped to the same spot
        out.append(RouteDetail(0, index[-1], RoadClass.OTHER, None, False))
    return tuple(out)


def to_route(body: Any, n_waypoints: int, max_segment_km: float = 1.0) -> Route:
    """Map a 200 `/route` response for `n_waypoints` request points to a `Route` (not snap-checked)."""
    if not isinstance(body, dict) or not isinstance(body.get("paths"), list) or not body["paths"]:
        raise MappingError("no paths")
    path = body["paths"][0]
    if not isinstance(path, dict):
        raise MappingError("paths[0]: not an object")
    points = _coords(path.get("points"), "points")
    snapped = _coords(path.get("snapped_waypoints"), "snapped_waypoints")
    if not points:
        raise MappingError("points: empty")
    if len(snapped) != n_waypoints:
        raise MappingError(f"snapped_waypoints: {len(snapped)} for {n_waypoints} request points")
    details = path.get("details")
    if not isinstance(details, dict):
        details = {}
    n = len(points)
    total_m = _num(path.get("distance"), "distance")
    total_ms = _num(path.get("time"), "time")

    straight = [haversine_km(points[i], points[i + 1]) for i in range(n - 1)]
    seg_km = _scaled(straight, _intervals(details, "distance", n, numeric=True), 1 / 1000, total_m / 1000)
    seg_min = _scaled(seg_km, _intervals(details, "time", n, numeric=True), 1 / 60000, total_ms / 60000)
    wp = _legs(details, n, n_waypoints) or _nearest_forward(points, snapped)

    dense, cum_km, cum_min, index = _densify(points, seg_km, seg_min, max_segment_km)
    return Route(
        points=tuple(dense),
        cum_km=tuple(cum_km),
        cum_min=tuple(cum_min),
        details=_road_details(details, n, index),
        waypoint_idx=tuple(index[i] for i in wp),
        snapped=tuple(snapped),
        km_total=cum_km[-1],
        min_total=cum_min[-1],
        synthetic=False,
    )
