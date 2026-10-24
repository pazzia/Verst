"""A uniform lat/lon grid for "items near a point / near a line" queries (ADR-0012 §3).

Buckets are `cell_deg` degrees on both axes. Queries return candidates from every bucket that a km radius can
reach, so callers still filter by exact distance. Insertion order is kept inside a bucket and results are
sorted by the caller's key, so queries are deterministic.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Iterator

from verst_planner.domain.model import LatLon
from verst_planner.geo.distance import KM_PER_DEG_LAT, KM_PER_DEG_LON_EQUATOR, haversine_km


class GridIndex[T]:
    def __init__(self, cell_deg: float = 0.1) -> None:
        self.cell = cell_deg
        self._cells: dict[tuple[int, int], list[tuple[LatLon, T]]] = {}
        self.size = 0

    def _key(self, p: LatLon) -> tuple[int, int]:
        return math.floor(p.lat / self.cell), math.floor(p.lon / self.cell)

    def add(self, p: LatLon, item: T) -> None:
        self._cells.setdefault(self._key(p), []).append((p, item))
        self.size += 1

    def extend(self, items: Iterable[tuple[LatLon, T]]) -> None:
        for p, item in items:
            self.add(p, item)

    def _span(self, p: LatLon, radius_km: float) -> tuple[int, int, int, int]:
        dlat = radius_km / KM_PER_DEG_LAT
        cos_phi = max(0.05, math.cos(math.radians(min(89.0, abs(p.lat) + dlat))))
        dlon = radius_km / (KM_PER_DEG_LON_EQUATOR * cos_phi)
        return (
            math.floor((p.lat - dlat) / self.cell),
            math.floor((p.lat + dlat) / self.cell),
            math.floor((p.lon - dlon) / self.cell),
            math.floor((p.lon + dlon) / self.cell),
        )

    def candidates(self, p: LatLon, radius_km: float) -> Iterator[tuple[LatLon, T]]:
        """Every item in the buckets a circle of `radius_km` around `p` touches (a superset)."""
        lat0, lat1, lon0, lon1 = self._span(p, radius_km)
        for i in range(lat0, lat1 + 1):
            for j in range(lon0, lon1 + 1):
                yield from self._cells.get((i, j), ())

    def within(self, p: LatLon, radius_km: float) -> list[tuple[float, T]]:
        """`(distance_km, item)` for every item within `radius_km` of `p`, nearest first (stable)."""
        out = [(haversine_km(p, q), item) for q, item in self.candidates(p, radius_km)]
        return sorted(((d, item) for d, item in out if d <= radius_km), key=lambda x: x[0])

    def nearest(self, p: LatLon, max_km: float) -> tuple[float, T] | None:
        """The nearest item within `max_km` (search radius grows by doubling), or None."""
        r = min(max_km, max(5.0, self.cell * KM_PER_DEG_LAT))
        while True:
            hits = self.within(p, r)
            if hits:
                return hits[0]
            if r >= max_km:
                return None
            r = min(max_km, r * 2)

    def near_line(self, line: tuple[LatLon, ...], radius_km: float) -> Iterator[tuple[LatLon, T]]:
        """A superset of the items within `radius_km` of the polyline (each item once, bucket order)."""
        if not line:
            return
        seen: set[tuple[int, int]] = set()
        pairs = list(itertools.pairwise(line)) if len(line) > 1 else [(line[0], line[0])]
        for a, b in pairs:
            steps = max(1, math.ceil(haversine_km(a, b) / max(radius_km, 1.0)))
            for k in range(steps + 1):
                f = k / steps
                q = LatLon(a.lat + (b.lat - a.lat) * f, a.lon + (b.lon - a.lon) * f)
                lat0, lat1, lon0, lon1 = self._span(q, radius_km * 1.5)
                for i in range(lat0, lat1 + 1):
                    for j in range(lon0, lon1 + 1):
                        if (i, j) in seen:
                            continue
                        seen.add((i, j))
                        yield from self._cells.get((i, j), ())
