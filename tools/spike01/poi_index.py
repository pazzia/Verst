"""Open place index (ADR-0021 §2.1 `open_index`, DATA-05 prototype): OSM POIs (+ Wikidata sitelinks) with a
grid for corridor search.

`build` reads `osmium export -f geojsonseq` output (any geometry; a way or relation is reduced to the mean of
its coordinates) and keeps named places of the kinds below. `Index.corridor` returns places within `radius_km`
of a route polyline with their position along it.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

# kind → (OSM key, values); first match wins, so specific kinds come first
KINDS: list[tuple[str, str, tuple[str, ...]]] = [
    ("museum", "tourism", ("museum", "gallery", "aquarium")),
    ("zoo", "tourism", ("zoo",)),
    ("theme_park", "tourism", ("theme_park",)),
    ("water_park", "leisure", ("water_park",)),
    ("viewpoint", "tourism", ("viewpoint",)),
    ("waterfall", "natural", ("waterfall",)),
    ("beach", "natural", ("beach",)),
    ("volcano", "natural", ("volcano", "peak")),
    ("cave", "natural", ("cave_entrance",)),
    ("hot_spring", "natural", ("hot_spring", "spring")),
    ("nature_reserve", "leisure", ("nature_reserve",)),
    ("park", "leisure", ("park", "garden")),
    ("castle", "historic", ("castle", "fort", "manor", "city_gate", "kremlin")),
    ("monastery", "historic", ("monastery",)),
    ("ruins", "historic", ("ruins", "archaeological_site")),
    ("monument", "historic", ("monument", "memorial")),
    ("temple", "amenity", ("place_of_worship",)),
    ("attraction", "tourism", ("attraction",)),
    ("food", "amenity", ("restaurant", "cafe", "fast_food", "food_court")),
    ("fuel", "amenity", ("fuel",)),
    ("lodging", "tourism", ("hotel", "guest_house", "motel", "hostel", "chalet")),
]
SIGHT_KINDS = {k for k, _, _ in KINDS} - {"food", "fuel", "lodging"}
CELL_DEG = 0.1


@dataclass
class Poi:
    id: str
    name: str
    kind: str
    lat: float
    lon: float
    wikidata: str | None = None
    sitelinks: int = 0
    hours: str | None = None
    dog: str | None = None  # OSM dog=yes|no|leashed|…; None = unknown (ADR-0019)
    fee: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


def classify(tags: dict[str, Any]) -> str | None:
    for kind, key, values in KINDS:
        if tags.get(key) in values:
            if kind == "temple" and not (tags.get("wikidata") or tags.get("tourism") == "attraction" or tags.get("historic")):
                return None  # an ordinary church or prayer house: not a sight unless notable (ADR-0015 §2)
            if kind == "park" and not tags.get("wikidata") and not tags.get("tourism"):
                return None  # unnamed-notability city greenery
            return kind
    return None


def centroid(geom: dict[str, Any]) -> tuple[float, float] | None:
    pts: list[list[float]] = []

    def walk(c: Any) -> None:
        if isinstance(c, list) and c and isinstance(c[0], (int, float)):
            pts.append(c)
        elif isinstance(c, list):
            for x in c:
                walk(x)

    walk(geom.get("coordinates"))
    if not pts:
        return None
    return sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts)


def build(lines: Iterable[str], lang: str) -> Iterator[Poi]:
    seen: set[str] = set()
    for line in lines:
        line = line.strip().lstrip("\x1e")
        if not line:
            continue
        ft = json.loads(line)
        tags = ft.get("properties") or {}
        name = tags.get(f"name:{lang}") or tags.get("name") or tags.get("name:en")
        if not name:
            continue
        kind = classify(tags)
        if kind is None:
            continue
        c = centroid(ft.get("geometry") or {})
        if c is None:
            continue
        pid = str(ft.get("id") or tags.get("@id") or f"{kind}:{c[0]:.5f},{c[1]:.5f}")
        if pid in seen:
            continue
        seen.add(pid)
        yield Poi(
            id=pid, name=name, kind=kind, lat=round(c[0], 6), lon=round(c[1], 6),
            wikidata=tags.get("wikidata"), hours=tags.get("opening_hours"), dog=tags.get("dog"), fee=tags.get("fee"),
        )


def save(pois: Iterable[Poi], path: Path) -> int:
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for p in pois:
            f.write(json.dumps(asdict(p), ensure_ascii=False) + "\n")
            n += 1
    return n


def load(path: Path) -> list[Poi]:
    with path.open(encoding="utf-8") as f:
        return [Poi(**json.loads(line)) for line in f if line.strip()]


# ------------------------------------------------------------------------------------------ geometry

def _xy(lat: float, lon: float, lat0: float) -> tuple[float, float]:
    k = 111.32
    return lon * k * math.cos(math.radians(lat0)), lat * k


@dataclass
class Hit:
    poi: Poi
    km_at: float  # position along the route
    lateral_km: float  # distance from the route


class Index:
    def __init__(self, pois: list[Poi]) -> None:
        self.pois = pois
        self.grid: dict[tuple[int, int], list[Poi]] = defaultdict(list)
        for p in pois:
            self.grid[(int(math.floor(p.lat / CELL_DEG)), int(math.floor(p.lon / CELL_DEG)))].append(p)

    def corridor(self, line: list[tuple[float, float]], radius_km: float, kinds: set[str] | None = None) -> list[Hit]:
        """Places within `radius_km` of the polyline `line` [(lat, lon)], each with its km along the line."""
        if len(line) < 2:
            return []
        lat0 = sum(p[0] for p in line) / len(line)
        xy = [_xy(a, b, lat0) for a, b in line]
        cum = [0.0]
        for (x1, y1), (x2, y2) in zip(xy, xy[1:]):
            cum.append(cum[-1] + math.hypot(x2 - x1, y2 - y1))
        pad = int(math.ceil(radius_km / (111.32 * CELL_DEG * math.cos(math.radians(abs(lat0)) or 1)))) + 1
        near: dict[tuple[int, int], list[int]] = defaultdict(list)  # cell → indices of segments near it
        for i, (a, b) in enumerate(zip(line, line[1:])):
            cs = {(int(math.floor(a[0] / CELL_DEG)), int(math.floor(a[1] / CELL_DEG))),
                  (int(math.floor(b[0] / CELL_DEG)), int(math.floor(b[1] / CELL_DEG)))}
            for ci, cj in cs:
                for di in range(-pad, pad + 1):
                    for dj in range(-pad, pad + 1):
                        lst = near[(ci + di, cj + dj)]
                        if not lst or lst[-1] != i:
                            lst.append(i)
        out: list[Hit] = []
        for cell, segs in near.items():
            for p in self.grid.get(cell, ()):
                if kinds is not None and p.kind not in kinds:
                    continue
                px, py = _xy(p.lat, p.lon, lat0)
                best = (float("inf"), 0.0)
                for i in segs:
                    (x1, y1), (x2, y2) = xy[i], xy[i + 1]
                    dx, dy = x2 - x1, y2 - y1
                    seg = dx * dx + dy * dy
                    t = 0.0 if seg == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg))
                    d = math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
                    if d < best[0]:
                        best = (d, cum[i] + t * math.sqrt(seg))
                if best[0] <= radius_km:
                    out.append(Hit(p, best[1], best[0]))
        out.sort(key=lambda h: h.km_at)
        return out


def simplify(points: list[tuple[float, float]], step_km: float = 1.0) -> list[tuple[float, float]]:
    """Keep a point every ~`step_km` (plus the last): enough for a corridor of several km."""
    if not points:
        return []
    out = [points[0]]
    acc = 0.0
    for a, b in zip(points, points[1:]):
        acc += math.hypot((b[0] - a[0]) * 111.32, (b[1] - a[1]) * 111.32 * math.cos(math.radians(a[0])))
        if acc >= step_km:
            out.append(b)
            acc = 0.0
    if out[-1] != points[-1]:
        out.append(points[-1])
    return out


def main() -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="geojsonseq (osmium export) → open place index (JSONL)")
    ap.add_argument("--in", dest="src", type=Path, required=True)
    ap.add_argument("--lang", default="ru")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    with args.src.open(encoding="utf-8") as f:
        n = save(build(f, args.lang), args.out)
    kinds: dict[str, int] = {}
    for p in load(args.out):
        kinds[p.kind] = kinds.get(p.kind, 0) + 1
    print(f"{n} places → {args.out}: {dict(sorted(kinds.items(), key=lambda kv: -kv[1]))}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
