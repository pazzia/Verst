"""Initial bearing and its 8-sector name (A§6.12)."""

import math
from typing import Literal

from verst_planner.domain.model import LatLon

Bearing8 = Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
_SECTORS: tuple[Bearing8, ...] = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def initial_bearing_deg(a: LatLon, b: LatLon) -> float:
    """Initial great-circle bearing a→b in degrees [0, 360)."""
    phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
    dlmb = math.radians(b.lon - a.lon)
    x = math.sin(dlmb) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlmb)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def bearing8(a: LatLon, b: LatLon) -> Bearing8:
    """45-degree sector centred on N (N = [337.5, 22.5))."""
    return _SECTORS[int(((initial_bearing_deg(a, b) + 22.5) % 360.0) // 45.0)]
