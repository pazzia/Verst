"""Parks and gardens from a Geofabrik OSM extract (CEO 29.10: Фрязино has no park in the catalogue). CI only:

    osmium tags-filter X-latest.osm.pbf wr/leisure=park,garden -o parks.osm.pbf
    osmium export parks.osm.pbf -f geojsonseq --add-unique-id=type_id -o parks.geojsonseq
    python3 tools/data/parks_from_extract.py RAW_DIR parks.geojsonseq [--catalogue DIR]  # writes RAW_DIR/parks.json

A park is an OSM area (closed way or multipolygon relation) tagged `leisure=park` or `leisure=garden`, with a
name and at least `MIN_AREA_M2`; private ones (`access=private|no`, `garden:type=residential|private`) are left
out. Each row keeps its area in m² (outer rings minus holes, on a local equirectangular projection) and its
area-weighted centroid, and is assigned to the nearest catalogue town like the bars and food places
(`fetch_overpass.assign` over every town, `radius_all_m`). `build_parks.py` caps them per town and writes
`catalogue_parks.json.gz`. `--catalogue DIR` takes the towns from a built `catalogue_towns.json.gz` instead of
`RAW_DIR/towns.json` (the Russian parks of `data-abroad.yml` are built against the shipped catalogue).
`parks_from_features` is pure and tested in the sandbox.
"""

from __future__ import annotations

import itertools
import json
import math
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bars_from_extract import KINDS
from fetch_overpass import all_towns, assign, radius_all_m

PARK_LEISURE = frozenset({"park", "garden"})
MIN_AREA_M2 = 3_000
PRIVATE_ACCESS = frozenset({"private", "no"})
PRIVATE_GARDEN = frozenset({"residential", "private"})
KEEP = ("leisure", "name", "name:ru", "name:en", "wikidata", "opening_hours", "access", "garden:type", "fee")
EARTH_R_M = 6_371_008.8

Ring = list[list[float]]


def _polygons(geom: dict[str, Any]) -> list[list[Ring]]:
    """[[outer, hole, …], …] of a Polygon or MultiPolygon; nothing for points and lines (no area)."""
    t, c = geom.get("type"), geom.get("coordinates")
    if t == "Polygon" and c:
        return [c]
    if t == "MultiPolygon" and c:
        return [p for p in c if p]
    return []


def _ring_area_centroid(ring: Ring, lat0: float) -> tuple[float, float, float]:
    """Signed area (m²) and centroid (lon, lat in degrees) of one ring (shoelace on a local projection)."""
    kx = math.radians(1) * EARTH_R_M * math.cos(math.radians(lat0))
    ky = math.radians(1) * EARTH_R_M
    pts = [(p[0] * kx, p[1] * ky) for p in ring]
    if len(pts) > 1 and pts[0] != pts[-1]:
        pts.append(pts[0])
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in itertools.pairwise(pts):
        cross = x1 * y2 - x2 * y1
        a += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    a /= 2
    if a == 0:
        return 0.0, 0.0, 0.0
    return a, cx / (6 * a) / kx, cy / (6 * a) / ky


def area_and_centre(geom: dict[str, Any]) -> tuple[float, float, float] | None:
    """(area m², lat, lon) of a (multi)polygon: outer rings minus holes; None without an area."""
    polys = _polygons(geom)
    rings = [r for poly in polys for r in poly if len(r) >= 3]
    if not rings:
        return None
    lat0 = sum(p[1] for r in rings for p in r) / sum(len(r) for r in rings)
    total = sx = sy = 0.0
    for poly in polys:
        for i, ring in enumerate(poly):
            if len(ring) < 3:
                continue
            a, lon, lat = _ring_area_centroid(ring, lat0)
            a = abs(a) if i == 0 else -abs(a)  # the first ring is the outer one, the others are holes
            total += a
            sx += a * lon
            sy += a * lat
    if total <= 0:
        return None
    return total, sy / total, sx / total


def osm_object(fid: str) -> tuple[str, int] | None:
    """The OSM object of an `osmium export --add-unique-id=type_id` feature id: `n1`/`w2`/`r3` as they are, and
    an area `a<id>` back to its way (`a246` → way 123: area id = 2 × way id) or relation (`a91` → relation 45:
    2 × relation id + 1). Run 1 of data-abroad.yml (29.10) found no park at all: osmium writes every park
    polygon with an `a…` id (the `w…` feature of a closed way is its LineString, which has no area)."""
    if len(fid) < 2 or not fid[1:].isdigit():
        return None
    n = int(fid[1:])
    if fid[0] == "a":
        return ("relation", (n - 1) // 2) if n % 2 else ("way", n // 2)
    return (KINDS[fid[0]], n) if fid[0] in KINDS else None


def parks_from_features(lines: Iterable[str], min_area: float = MIN_AREA_M2) -> list[dict[str, Any]]:
    """Named public parks and gardens with an area (Overpass-shaped elements + `area`), the `KEEP` tags only."""
    out = []
    for raw in lines:
        line = raw.strip().lstrip("\x1e")
        if not line:
            continue
        f = json.loads(line)
        obj = osm_object(str(f.get("id", "")))
        if obj is None:
            continue
        tags = {k: v for k, v in (f.get("properties") or {}).items() if isinstance(v, str)}
        if (
            tags.get("leisure") not in PARK_LEISURE
            or not tags.get("name", "").strip()
            or tags.get("access") in PRIVATE_ACCESS
            or tags.get("garden:type") in PRIVATE_GARDEN
        ):
            continue
        got = area_and_centre(f.get("geometry") or {})
        if got is None or got[0] < min_area:
            continue
        area, lat, lon = got
        out.append(
            {
                "type": obj[0],
                "id": obj[1],
                "lat": lat,
                "lon": lon,
                "area": round(area),
                "tags": {k: tags[k] for k in KEEP if k in tags},
            }
        )
    seen: set[tuple[str, int]] = set()
    unique = []
    for e in out:
        if (e["type"], e["id"]) not in seen:
            seen.add((e["type"], e["id"]))
            unique.append(e)
    return unique


def assign_parks(elements: list[dict[str, Any]], towns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parks → rows of the nearest catalogue town whose radius covers the park's centre (others dropped)."""
    areas = {f"{e['type'][0]}{e['id']}": e["area"] for e in elements}
    return [{**r, "area": areas[r["osm"]]} for r in assign(elements, all_towns(towns), radius_all_m)]


def catalogue_towns(cat_dir: Path) -> list[dict[str, Any]]:
    """The towns of a built catalogue in the raw `towns.json` shape that `assign` reads."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from verst_planner.catalogue import COORD_SCALE, FILES, TOWN_COLS, decode_table, load_gz

    doc = load_gz((cat_dir / FILES["towns"]).read_bytes(), "towns")
    return [
        {
            "qid": t["id"],
            "name": t["name"],
            "lat": t["lat"] / COORD_SCALE,
            "lon": t["lon"] / COORD_SCALE,
            "population": int(t["pop"] or 0),
        }
        for t in decode_table(doc, TOWN_COLS, "towns")
    ]


def main(argv: list[str]) -> int:
    raw, seq = Path(argv[0]), Path(argv[1])
    if "--catalogue" in argv:
        towns = catalogue_towns(Path(argv[argv.index("--catalogue") + 1]))
    else:
        towns = json.loads((raw / "towns.json").read_text("utf-8"))
    with seq.open(encoding="utf-8") as fh:
        elements = parks_from_features(fh)
    parks = assign_parks(elements, towns)
    (raw / "parks.json").write_text(json.dumps(parks, ensure_ascii=False), "utf-8")
    print(
        f"parks: {len(parks)} rows from {len(elements)} named parks and gardens, {len(towns)} towns (extract)"
    )
    return 0 if parks else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
