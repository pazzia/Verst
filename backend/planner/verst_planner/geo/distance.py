"""Great-circle and local planar distances (A§6.3)."""

import math

from verst_planner.domain.model import LatLon

EARTH_RADIUS_KM = 6371.0088
KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LON_EQUATOR = 111.320


def haversine_km(a: LatLon, b: LatLon) -> float:
    """Great-circle distance on the mean Earth sphere (R = 6371.0088 km)."""
    phi1 = math.radians(a.lat)
    phi2 = math.radians(b.lat)
    dphi = phi2 - phi1
    dlmb = math.radians(b.lon - a.lon)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


def local_xy(q: LatLon, origin: LatLon, cos_phi: float) -> tuple[float, float]:
    """Local equirectangular km coordinates of `q` relative to `origin` (A§6.3)."""
    return (q.lon - origin.lon) * KM_PER_DEG_LON_EQUATOR * cos_phi, (q.lat - origin.lat) * KM_PER_DEG_LAT


def project_on_segment(p: LatLon, a: LatLon, b: LatLon) -> tuple[float, float]:
    """Return `(t, d)`: clamped fraction of `p`'s projection along a→b and its distance in km."""
    cos_phi = math.cos(math.radians((a.lat + b.lat) / 2))
    px, py = local_xy(p, a, cos_phi)
    bx, by = local_xy(b, a, cos_phi)
    bb = bx * bx + by * by
    t = 0.0 if bb == 0.0 else max(0.0, min(1.0, (px * bx + py * by) / bb))
    return t, math.hypot(px - t * bx, py - t * by)


def point_segment_km(p: LatLon, a: LatLon, b: LatLon) -> float:
    """Distance in km from `p` to the segment a→b in the local equirectangular projection."""
    return project_on_segment(p, a, b)[1]
