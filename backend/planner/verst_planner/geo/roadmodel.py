"""The offline road model for points off the fixture graph (ADR-0012 §4).

`road_km(h)` = straight-line km x a ratio interpolated linearly between calibrated breakpoints (clamped);
`minutes(h)` uses the speed interpolated the same way. Calibration: `tools/calibrate_detour.py`.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RoadModel:
    xs: tuple[float, ...]
    ratios: tuple[float, ...]
    speeds: tuple[float, ...]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RoadModel:
        pts = sorted(d["points"], key=lambda p: float(p["straightKm"]))
        if not pts:
            raise ValueError("road model: no points")
        return cls(
            tuple(float(p["straightKm"]) for p in pts),
            tuple(float(p["ratio"]) for p in pts),
            tuple(float(p["speedKmh"]) for p in pts),
        )

    def _interp(self, ys: tuple[float, ...], h: float) -> float:
        xs = self.xs
        if h <= xs[0]:
            return ys[0]
        if h >= xs[-1]:
            return ys[-1]
        i = bisect.bisect_right(xs, h)
        x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
        return y0 + (y1 - y0) * (h - x0) / (x1 - x0)

    def ratio(self, straight_km: float) -> float:
        return self._interp(self.ratios, straight_km)

    def road_km(self, straight_km: float) -> float:
        return straight_km * self.ratio(straight_km)

    def speed_kmh(self, straight_km: float) -> float:
        return self._interp(self.speeds, straight_km)

    def minutes(self, straight_km: float) -> float:
        return self.road_km(straight_km) / self.speed_kmh(straight_km) * 60.0
