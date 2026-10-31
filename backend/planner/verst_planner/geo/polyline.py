"""Polyline helpers: Douglas-Peucker simplification, interpolation and 1-km resampling (A§6.3, A§6.6)."""

import bisect
from collections.abc import Sequence

from verst_planner.domain.model import LatLon, Route
from verst_planner.geo.distance import point_segment_km


def douglas_peucker(points: Sequence[LatLon], cum_km: Sequence[float], tol_m: float) -> list[int]:
    """Indices of the vertices kept by Douglas-Peucker at tolerance `tol_m` metres (endpoints always kept).

    `cum_km` is accepted so callers keep the original along-route km of kept vertices; it is not used for
    the geometric test, which runs in local equirectangular metres per segment.
    """
    n = len(points)
    if len(cum_km) != n:
        raise ValueError("points and cum_km differ in length")
    if n <= 2:
        return list(range(n))
    tol_km = tol_m / 1000.0
    keep = [False] * n
    keep[0] = keep[n - 1] = True
    stack = [(0, n - 1)]
    while stack:
        lo, hi = stack.pop()
        if hi - lo < 2:
            continue
        a, b = points[lo], points[hi]
        best_i, best_d = -1, -1.0
        for i in range(lo + 1, hi):
            d = point_segment_km(points[i], a, b)
            if d > best_d:
                best_i, best_d = i, d
        if best_d > tol_km:
            keep[best_i] = True
            stack.append((lo, best_i))
            stack.append((best_i, hi))
    return [i for i in range(n) if keep[i]]


def _locate(cum: Sequence[float], km: float) -> tuple[int, float]:
    """Segment index `i` and fraction `f` such that km lies between cum[i] and cum[i+1]."""
    if km <= cum[0]:
        return 0, 0.0
    if km >= cum[-1]:
        return len(cum) - 2, 1.0
    i = bisect.bisect_right(cum, km) - 1
    span = cum[i + 1] - cum[i]
    return i, 0.0 if span == 0 else (km - cum[i]) / span


def interpolate(route: Route, km: float) -> LatLon:
    """The point at along-route distance `km` (clamped to the route)."""
    if len(route.points) == 1:
        return route.points[0]
    i, f = _locate(route.cum_km, km)
    a, b = route.points[i], route.points[i + 1]
    return LatLon(a.lat + (b.lat - a.lat) * f, a.lon + (b.lon - a.lon) * f)


def min_at(cum_km: Sequence[float], cum_min: Sequence[float], km: float) -> float:
    """Free-flow minutes at `km` by linear interpolation of the `(cum_km, cum_min)` profile."""
    if len(cum_km) == 1:
        return cum_min[0]
    i, f = _locate(cum_km, km)
    return cum_min[i] + (cum_min[i + 1] - cum_min[i]) * f


def resample(route: Route, step_km: float = 1.0) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """The route profile sampled every `step_km` (plus the exact end): `(km, minutes)` tuples."""
    if step_km <= 0:
        raise ValueError("step_km must be positive")
    total = route.cum_km[-1]
    kms: list[float] = []
    k = 0
    while k * step_km < total:
        kms.append(round(k * step_km, 6))
        k += 1
    kms.append(total)
    return tuple(kms), tuple(min_at(route.cum_km, route.cum_min, x) for x in kms)
