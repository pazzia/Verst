"""Grid index over a simplified route polyline for `kmAt` projection (A§6.3)."""

import bisect
import math
from typing import NamedTuple

from verst_planner.domain.enums import RoadClass
from verst_planner.domain.model import LatLon, Route
from verst_planner.geo.distance import project_on_segment
from verst_planner.geo.polyline import douglas_peucker

SIMPLIFY_TOL_M = 30.0
_BBOX_PAD_DEG = 0.0005
_KM_PER_CELL_LAT = 5.5


class Projection(NamedTuple):
    km_at: float
    lateral_km: float
    seg_idx: int  # index of the segment's start vertex in the original (dense) polyline
    road_class: RoadClass


class PolylineIndex:
    def __init__(self, route: Route, cell_deg: float = 0.05) -> None:
        self.route = route
        self.cell_deg = cell_deg
        kept = douglas_peucker(route.points, route.cum_km, SIMPLIFY_TOL_M)
        self.kept: tuple[int, ...] = tuple(kept)
        self._cells: dict[tuple[int, int], list[int]] = {}
        for s in range(len(kept) - 1):
            a, b = route.points[kept[s]], route.points[kept[s + 1]]
            lat_lo = math.floor((min(a.lat, b.lat) - _BBOX_PAD_DEG) / cell_deg)
            lat_hi = math.floor((max(a.lat, b.lat) + _BBOX_PAD_DEG) / cell_deg)
            lon_lo = math.floor((min(a.lon, b.lon) - _BBOX_PAD_DEG) / cell_deg)
            lon_hi = math.floor((max(a.lon, b.lon) + _BBOX_PAD_DEG) / cell_deg)
            for ci in range(lat_lo, lat_hi + 1):
                for cj in range(lon_lo, lon_hi + 1):
                    self._cells.setdefault((ci, cj), []).append(s)
        self._detail_starts = [d.from_idx for d in route.details]

    @property
    def segment_count(self) -> int:
        return len(self.kept) - 1

    def simplified_points(self) -> tuple[LatLon, ...]:
        return tuple(self.route.points[i] for i in self.kept)

    def road_class_at(self, poly_idx: int) -> RoadClass:
        """Road class of the `RouteDetail` covering polyline index `poly_idx`."""
        if not self.route.details:
            return RoadClass.OTHER
        i = max(0, bisect.bisect_right(self._detail_starts, poly_idx) - 1)
        return self.route.details[i].road_class

    def road_ref_at(self, poly_idx: int) -> str | None:
        if not self.route.details:
            return None
        i = max(0, bisect.bisect_right(self._detail_starts, poly_idx) - 1)
        return self.route.details[i].road_ref

    def project_segment(self, p: LatLon, s: int) -> tuple[float, float]:
        """`(km_at, lateral_km)` of `p` projected on simplified segment `s`."""
        i0, i1 = self.kept[s], self.kept[s + 1]
        t, d = project_on_segment(p, self.route.points[i0], self.route.points[i1])
        cum = self.route.cum_km
        return cum[i0] + t * (cum[i1] - cum[i0]), d

    def _seg_for_km(self, s: int, km_at: float) -> int:
        """Dense polyline segment index containing `km_at` within simplified segment `s`."""
        i0, i1 = self.kept[s], self.kept[s + 1]
        cum = self.route.cum_km
        j = bisect.bisect_right(cum, km_at, i0, i1) - 1
        return max(i0, min(j, i1 - 1))

    def _hits(self, p: LatLon, max_km: float) -> list[tuple[float, float, int]]:
        """Raw `(km_at, lateral_km, simplified segment)` hits within `max_km`, sorted by km."""
        if self.segment_count < 1:
            return []
        rings_lat = math.ceil(max_km / _KM_PER_CELL_LAT)
        cos_lat = max(0.01, math.cos(math.radians(p.lat)))
        rings_lon = math.ceil(max_km / (_KM_PER_CELL_LAT * cos_lat))
        ci0 = math.floor(p.lat / self.cell_deg)
        cj0 = math.floor(p.lon / self.cell_deg)
        segs: set[int] = set()
        for ci in range(ci0 - rings_lat, ci0 + rings_lat + 1):
            for cj in range(cj0 - rings_lon, cj0 + rings_lon + 1):
                cell = self._cells.get((ci, cj))
                if cell:
                    segs.update(cell)
        hits: list[tuple[float, float, int]] = []
        for s in sorted(segs):
            km_at, d = self.project_segment(p, s)
            if d <= max_km:
                hits.append((km_at, d, s))
        hits.sort()
        return hits

    def project_all(self, p: LatLon, max_km: float) -> list[Projection]:
        """One projection per pass of the route within `max_km` of `p`, sorted by `km_at`."""
        hits = self._hits(p, max_km)
        if not hits:
            return []
        gap = 2 * max_km + 5
        passes: list[list[tuple[float, float, int]]] = [[hits[0]]]
        for h in hits[1:]:
            if h[0] - passes[-1][-1][0] > gap:
                passes.append([h])
            else:
                passes[-1].append(h)
        out: list[Projection] = []
        for group in passes:
            km_at, d, s = min(group, key=lambda h: (h[1], h[0]))
            dense = self._seg_for_km(s, km_at)
            out.append(Projection(km_at, d, dense, self.road_class_at(dense)))
        return out

    def nearest_in_range(self, p: LatLon, max_km: float, lo_km: float, hi_km: float) -> Projection | None:
        """Closest projection whose `km_at` lies in [lo_km, hi_km] (no pass grouping)."""
        hits = [h for h in self._hits(p, max_km) if lo_km <= h[0] <= hi_km]
        if not hits:
            return None
        km_at, d, s = min(hits, key=lambda h: (h[1], h[0]))
        dense = self._seg_for_km(s, km_at)
        return Projection(km_at, d, dense, self.road_class_at(dense))

    def nearest(self, p: LatLon, max_km: float) -> Projection | None:
        projections = self.project_all(p, max_km)
        if not projections:
            return None
        return min(projections, key=lambda q: (q.lateral_km, q.km_at))
