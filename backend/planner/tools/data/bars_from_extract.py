"""Bars from a Geofabrik OSM extract instead of Overpass (ADR-0012 §1). CI only:

    osmium tags-filter russia-latest.osm.pbf nwr/amenity=bar,pub,biergarten nwr/craft=brewery -o bars.osm.pbf
    osmium export bars.osm.pbf -f geojsonseq --add-unique-id=type_id -o bars.geojsonseq
    python3 tools/data/bars_from_extract.py RAW_DIR bars.geojsonseq      # writes RAW_DIR/bars.json

Runs 1 and 2 lost 90+ min to Overpass (502/504 on the country-wide query on three mirrors, read timeouts per
town), so the extract is the primary source and `fetch_overpass.py` the fallback. Same output; the town
assignment is `fetch_overpass.assign` over every catalogue town (`all_towns`, `radius_all_m`, CEO 2026-10-29 —
the Overpass fallback keeps the bigger and touristic towns only). `elements_from_features` is pure and tested
in the sandbox; `food_from_extract.py` uses it too.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_overpass import all_towns, assign, radius_all_m

KINDS = {"n": "node", "w": "way", "r": "relation"}


def _coords(geom: dict[str, Any]) -> list[list[float]]:
    t, c = geom.get("type"), geom.get("coordinates")
    if t == "Point":
        return [c]
    if t == "LineString":
        return list(c)
    if t == "Polygon":
        return list(c[0])
    if t == "MultiPolygon":
        return [p for poly in c for p in poly[0]]
    if t == "MultiLineString":
        return [p for line in c for p in line]
    return []


def elements_from_features(lines: Iterable[str], require_name: bool = True) -> list[dict[str, Any]]:
    """GeoJSON-seq features (`id` = n123/w123/r123) → Overpass-shaped elements with a centre point."""
    out = []
    for raw in lines:
        line = raw.strip().lstrip("\x1e")
        if not line:
            continue
        f = json.loads(line)
        fid = str(f.get("id", ""))
        pts = _coords(f.get("geometry") or {})
        if not fid or fid[0] not in KINDS or not pts:
            continue
        lon = sum(p[0] for p in pts) / len(pts)
        lat = sum(p[1] for p in pts) / len(pts)
        tags = {k: v for k, v in (f.get("properties") or {}).items() if isinstance(v, str)}
        if require_name and not tags.get("name"):
            continue
        out.append({"type": KINDS[fid[0]], "id": int(fid[1:]), "lat": lat, "lon": lon, "tags": tags})
    return out


def main(argv: list[str]) -> int:
    raw, seq = Path(argv[0]), Path(argv[1])
    towns = json.loads((raw / "towns.json").read_text("utf-8"))
    pick = all_towns(towns)
    with seq.open(encoding="utf-8") as fh:
        elements = elements_from_features(fh)
    bars = assign(elements, pick, radius_all_m)
    (raw / "bars.json").write_text(json.dumps(bars, ensure_ascii=False), "utf-8")
    (raw / "bars_failed.json").write_text("[]", "utf-8")
    print(f"bars: {len(bars)} rows from {len(elements)} named features, {len(pick)} towns (extract)")
    return 0 if bars else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
