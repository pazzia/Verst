"""Real lodgings and roadside places from the Geofabrik OSM extract (CEO 02.11: «чтобы все кафешки,
достопримечательности и отели были настоящими, а не выдумкой для демо»). CI only for the extract part:

    osmium tags-filter russia-latest.osm.pbf nwr/tourism=hotel,motel,guest_house,hostel -o lodging.osm.pbf
    osmium export lodging.osm.pbf -f geojsonseq --add-unique-id=type_id -o lodging.geojsonseq
    osmium tags-filter russia-latest.osm.pbf nwr/amenity=fuel nwr/highway=rest_area,services -o roadside.osm.pbf
    osmium export roadside.osm.pbf -f geojsonseq --add-unique-id=type_id -o roadside.geojsonseq
    osmium tags-filter russia-latest.osm.pbf nwr/amenity=cafe,restaurant,fast_food -o food.osm.pbf
    osmium export food.osm.pbf -f geojsonseq --add-unique-id=type_id -o food.geojsonseq
    osmium tags-filter russia-latest.osm.pbf w/highway=motorway,trunk,primary -o roads.osm.pbf
    osmium export roads.osm.pbf -f geojsonseq --geometry-types=linestring -o roads.geojsonseq
    python3 tools/data/build_stops.py lodging.geojsonseq roadside.geojsonseq CATALOGUE_DIR \
        [--food food.geojsonseq --roads roads.geojsonseq] [--out DIR] [--lock F]

Writes `catalogue_lodging.json.gz` and `catalogue_roadside.json.gz` (`verst_planner.catalogue.LODGING_COLS`,
`ROADSIDE_COLS`) next to the built catalogue, plus a report of counts. The data is what OSM says, nothing is
added: no prices (OSM has none), no assumed amenities; a missing tag stays null (ADR-0019).

- **Lodging:** named `tourism=hotel|motel|guest_house|hostel` (not private, not disused), assigned to the nearest
  catalogue town whose lodging radius (`LODGING_RADIUS_FACTOR` × the walk radius, at least `LODGING_RADIUS_MIN_M`)
  covers it; others are counted, not kept (the planner books nights in towns). Deny-listed names are dropped.
- **Roadside:** every `amenity=fuel` and `highway=rest_area|services` of the country, named or not, with its
  real name or brand (CEO 03.11 «Добавляй настоящие имена заправок»; the demo rule P0-1 hid them before).
- **Roadside food (CEO 03.11):** named `amenity=cafe|restaurant|fast_food` outside every catalogue town's
  walk radius (the town ones are in `catalogue_food`) and within ~1 km of a motorway, trunk or primary road
  (`road_cells`: the road lines sampled every 200 m into 0.005° cells; a café counts when its cell or a
  neighbour holds a road sample). `wc` = OSM `toilets` as tagged, null when unknown.

Pure functions (`lodging_rows`, `roadside_rows`) are tested in the sandbox (tests/unit/test_build_stops.py).
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

PLANNER = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLANNER))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bars_from_extract import elements_from_features  # noqa: E402
from build_catalogue import ODBL_URI, OSM_COPYRIGHT_URI, denied, denylist  # noqa: E402
from enrich import tidy  # noqa: E402
from fetch_overpass import _km, assign, radius_all_m  # noqa: E402
from parks_from_extract import catalogue_towns  # noqa: E402

from verst_planner.catalogue import (  # noqa: E402
    FILES,
    FORMAT_VERSION,
    FUEL_BITS,
    LODGING_COLS,
    LODGING_FILE,
    LODGING_KINDS,
    ROADSIDE_COLS,
    ROADSIDE_FILE,
    ROADSIDE_FOOD_KINDS,
    ROADSIDE_KINDS,
    dump_gz,
    encode_table,
    load_gz,
    to_coord,
)

LODGING_RADIUS_FACTOR = 2
LODGING_RADIUS_MIN_M = 5_000
PRIVATE = frozenset({"private", "no"})
DISUSED_KEYS = ("disused:tourism", "abandoned:tourism", "disused:amenity", "abandoned:amenity")
FUEL_TAGS = {"ai92": "fuel:octane_92", "ai95": "fuel:octane_95", "dt": "fuel:diesel"}
MAX_PHONE, MAX_SITE, MAX_NAME = 32, 100, 80
ROAD_CELL = 0.005  # degrees: ~550 m of latitude, ~320 m of longitude at 55° N
ROAD_STEP_KM = 0.2
ROAD_NEAR = (1, 2)  # cells around a café that may hold a road sample (lat, lon): ~0.6–1.1 km


def _yes_no(v: str | None) -> int | None:
    """OSM yes/no-like values → 1 / 0, anything else (or missing) → None."""
    if v is None:
        return None
    v = v.strip().lower()
    if v in ("yes", "designated", "leashed", "outside", "inside", "customers"):
        return 1
    if v == "no":
        return 0
    return None


def _first(v: str | None, limit: int) -> str | None:
    """The first value of a `;`-list, trimmed; None when empty or longer than `limit`."""
    if not v:
        return None
    first = v.split(";")[0].strip()
    return first if first and len(first) <= limit else None


def _int(v: str | None, lo: int, hi: int) -> int | None:
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return None
    return n if lo <= n <= hi else None


def _usable(tags: dict[str, str]) -> bool:
    return tags.get("access") not in PRIVATE and not any(k in tags for k in DISUSED_KEYS)


def lodging_radius_m(t: dict[str, Any]) -> int:
    return max(LODGING_RADIUS_MIN_M, LODGING_RADIUS_FACTOR * radius_all_m(t))


def lodging_rows(
    lines: Iterable[str], towns: list[dict[str, Any]], deny: list[str], town_pos: dict[str, int]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """(rows, counts): named lodgings of catalogue towns; `counts` says what was dropped and why."""
    counts = {"features": 0, "kind": 0, "private": 0, "denied": 0, "noTown": 0, "kept": 0}
    elements = []
    for e in elements_from_features(lines):
        counts["features"] += 1
        tags = e["tags"]
        if tags.get("tourism") not in LODGING_KINDS:
            counts["kind"] += 1
            continue
        if not _usable(tags):
            counts["private"] += 1
            continue
        name = tidy(str(tags.get("name", "")).strip()) or ""
        if not name or len(name) > MAX_NAME or denied(name, deny):
            counts["denied"] += 1
            continue
        elements.append({**e, "tags": {**tags, "name": name}})
    assigned = assign(elements, towns, lodging_radius_m)
    counts["noTown"] = len(elements) - len(assigned)
    rows = []
    for r in sorted(assigned, key=lambda r: (town_pos[r["townQid"]], r["osm"])):
        tags = r["tags"]
        rows.append(
            {
                "id": f"osm_{r['osm']}",
                "name": tags["name"],
                "kind": LODGING_KINDS.index(tags["tourism"]),
                "lat": to_coord(r["lat"]),
                "lon": to_coord(r["lon"]),
                "town": town_pos[r["townQid"]],
                "stars": _int(tags.get("stars"), 1, 5),
                "rooms": _int(tags.get("rooms"), 1, 5000),
                "dog": _yes_no(tags.get("dog", tags.get("pets"))),
                "phone": _first(tags.get("phone") or tags.get("contact:phone"), MAX_PHONE),
                "site": _first(tags.get("website") or tags.get("contact:website"), MAX_SITE),
            }
        )
    counts["kept"] = len(rows)
    return rows, counts


def _roadside_kind(tags: dict[str, str]) -> str | None:
    if tags.get("amenity") == "fuel":
        return "fuel"
    hw = tags.get("highway")
    return hw if hw in ("rest_area", "services") else None


def _kind_code(e: dict[str, Any]) -> str:
    return {"node": "n", "way": "w", "relation": "r"}[e["type"]]


def roadside_rows(lines: Iterable[str]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """(rows, counts): every fuel station, rest area and services place, named or not, with its real name."""
    counts = {"features": 0, "kind": 0, "private": 0, "kept": 0}
    rows: list[dict[str, Any]] = []
    for e in elements_from_features(lines, require_name=False):
        counts["features"] += 1
        tags = e["tags"]
        kind = _roadside_kind(tags)
        if kind is None:
            counts["kind"] += 1
            continue
        if not _usable(tags):
            counts["private"] += 1
            continue
        name = tidy(str(tags.get("name") or tags.get("brand") or "").strip()) or None
        if name and len(name) > MAX_NAME:
            name = None
        yes = no = 0
        for key, bit in FUEL_BITS.items():
            v = _yes_no(tags.get(FUEL_TAGS[key]))
            yes |= bit if v == 1 else 0
            no |= bit if v == 0 else 0
        rows.append(
            {
                "id": f"osm_{_kind_code(e)}{e['id']}",
                "name": name,
                "kind": ROADSIDE_KINDS.index(kind),
                "lat": to_coord(e["lat"]),
                "lon": to_coord(e["lon"]),
                "hours": _first(tags.get("opening_hours"), 120),
                "fuel": yes or None,
                "nofuel": no or None,
                "wc": _yes_no(tags.get("toilets")),
                "cafe": _yes_no(tags.get("cafe")) if "cafe" in tags else (1 if tags.get("shop") == "cafe" else None),
            }
        )
    rows.sort(key=lambda r: r["id"])
    counts["kept"] = len(rows)
    return rows, counts


def _cell(lat: float, lon: float) -> tuple[int, int]:
    return math.floor(lat / ROAD_CELL), math.floor(lon / ROAD_CELL)


def road_cells(lines: Iterable[str]) -> set[tuple[int, int]]:
    """The 0.005° cells a main road passes through: every LineString sampled every `ROAD_STEP_KM`."""
    cells: set[tuple[int, int]] = set()
    for line in lines:
        line = line.strip().lstrip("\x1e")
        if not line:
            continue
        geom = json.loads(line).get("geometry") or {}
        parts = geom.get("coordinates") or []
        if geom.get("type") == "LineString":
            parts = [parts]
        elif geom.get("type") != "MultiLineString":
            continue
        for part in parts:
            for (lon1, lat1), (lon2, lat2) in itertools.pairwise(part):
                km = _km(lat1, lon1, lat2, lon2)
                n = max(1, math.ceil(km / ROAD_STEP_KM))
                for k in range(n + 1):
                    f = k / n
                    cells.add(_cell(lat1 + (lat2 - lat1) * f, lon1 + (lon2 - lon1) * f))
    return cells


def near_road(lat: float, lon: float, cells: set[tuple[int, int]]) -> bool:
    ci, cj = _cell(lat, lon)
    di_max, dj_max = ROAD_NEAR
    return any(
        (ci + di, cj + dj) in cells for di in range(-di_max, di_max + 1) for dj in range(-dj_max, dj_max + 1)
    )


def roadside_food_rows(
    lines: Iterable[str], towns: list[dict[str, Any]], cells: set[tuple[int, int]]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """(rows, counts): named cafés, restaurants and fast food outside the catalogue towns near a main road."""
    counts = {"features": 0, "kind": 0, "private": 0, "inTown": 0, "farFromRoad": 0, "kept": 0}
    elements = []
    for e in elements_from_features(lines):
        counts["features"] += 1
        tags = e["tags"]
        if tags.get("amenity") not in ROADSIDE_FOOD_KINDS:
            counts["kind"] += 1
            continue
        if not _usable(tags):
            counts["private"] += 1
            continue
        name = tidy(str(tags.get("name", "")).strip()) or ""
        if not name or len(name) > MAX_NAME:
            counts["kind"] += 1
            continue
        elements.append({**e, "tags": {**tags, "name": name}})
    in_town = {r["osm"] for r in assign(elements, towns, radius_all_m)}
    rows: list[dict[str, Any]] = []
    for e in elements:
        osm = f"{_kind_code(e)}{e['id']}"
        if osm in in_town:
            counts["inTown"] += 1
            continue
        if not near_road(e["lat"], e["lon"], cells):
            counts["farFromRoad"] += 1
            continue
        tags = e["tags"]
        rows.append(
            {
                "id": f"osm_{osm}",
                "name": tags["name"],
                "kind": ROADSIDE_KINDS.index(tags["amenity"]),
                "lat": to_coord(e["lat"]),
                "lon": to_coord(e["lon"]),
                "hours": _first(tags.get("opening_hours"), 120),
                "fuel": None,
                "nofuel": None,
                "wc": _yes_no(tags.get("toilets")),
                "cafe": None,
            }
        )
    rows.sort(key=lambda r: r["id"])
    counts["kept"] = len(rows)
    return rows, counts


def licence(version: str, what: str) -> dict[str, Any]:
    return {
        "licence": "ODbL-1.0",
        "uri": ODBL_URI,
        "text": "© OpenStreetMap contributors",
        "source": OSM_COPYRIGHT_URI,
        "note": f"{what}: part of the Verst place catalogue (a Derivative Database of OpenStreetMap, ODbL 1.0); "
        "see catalogue_meta.licence of the same build.",
        "build": version,
    }


def build(
    lodging_seq: Path,
    roadside_seq: Path,
    cat_dir: Path,
    hours_ok: Any = None,
    food_seq: Path | None = None,
    roads_seq: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """(lodging doc, roadside doc, report) for the catalogue in `cat_dir`; roadside food with both seqs."""
    towns_bytes = (cat_dir / FILES["towns"]).read_bytes()
    meta = load_gz((cat_dir / FILES["meta"]).read_bytes(), "meta")
    towns = catalogue_towns(cat_dir)
    town_pos = {t["qid"]: i for i, t in enumerate(towns)}
    deny = denylist()
    with lodging_seq.open(encoding="utf-8") as fh:
        lrows, lcounts = lodging_rows(fh, towns, deny, town_pos)
    with roadside_seq.open(encoding="utf-8") as fh:
        rrows, rcounts = roadside_rows(fh)
    fcounts: dict[str, int] = {}
    if food_seq is not None and roads_seq is not None:
        with roads_seq.open(encoding="utf-8") as fh:
            cells = road_cells(fh)
        with food_seq.open(encoding="utf-8") as fh:
            frows, fcounts = roadside_food_rows(fh, towns, cells)
        fcounts["roadCells"] = len(cells)
        rrows = sorted(rrows + frows, key=lambda r: r["id"])
    if hours_ok is not None:
        for r in rrows:
            if r["hours"] and not hours_ok(r["hours"]):
                r["hours"] = None
    sha = hashlib.sha256(towns_bytes).hexdigest()
    ldoc = encode_table(lrows, LODGING_COLS)
    ldoc.update({"version": meta["version"], "townsSha256": sha, "kinds": list(LODGING_KINDS),
                 "licence": licence(meta["version"], "lodging")})
    rdoc = encode_table(rrows, ROADSIDE_COLS)
    rdoc.update({"version": meta["version"], "kinds": list(ROADSIDE_KINDS), "fuelBits": FUEL_BITS,
                 "licence": licence(meta["version"], "roadside")})
    assert ldoc["v"] == rdoc["v"] == FORMAT_VERSION
    by_kind_l: dict[str, int] = {}
    for r in lrows:
        k = LODGING_KINDS[r["kind"]]
        by_kind_l[k] = by_kind_l.get(k, 0) + 1
    by_kind_r: dict[str, int] = {}
    for r in rrows:
        k = ROADSIDE_KINDS[r["kind"]]
        by_kind_r[k] = by_kind_r.get(k, 0) + 1
    report = {
        "version": meta["version"],
        "lodging": {**lcounts, "byKind": by_kind_l, "towns": len({r["town"] for r in lrows}),
                    "townsTotal": len(towns), "withPhone": sum(1 for r in lrows if r["phone"]),
                    "withSite": sum(1 for r in lrows if r["site"]), "dogKnown": sum(1 for r in lrows if r["dog"] is not None)},
        "roadsideFood": fcounts,
        "roadside": {**rcounts, "byKind": by_kind_r, "named": sum(1 for r in rrows if r["name"]),
                     "fuelKnown": sum(1 for r in rrows if r["fuel"] or r["nofuel"]),
                     "hoursKnown": sum(1 for r in rrows if r["hours"])},
    }
    return ldoc, rdoc, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="build_stops")
    ap.add_argument("lodging", type=Path, help="lodging.geojsonseq (osmium export)")
    ap.add_argument("roadside", type=Path, help="roadside.geojsonseq (osmium export)")
    ap.add_argument("catalogue", type=Path, help="the directory of the built catalogue_*.json.gz")
    ap.add_argument("--food", type=Path, default=None, help="food.geojsonseq (roadside cafés, with --roads)")
    ap.add_argument("--roads", type=Path, default=None, help="roads.geojsonseq (motorway, trunk, primary lines)")
    ap.add_argument("--out", type=Path, default=None, help="default: the catalogue directory")
    ap.add_argument("--lock", type=Path, default=None, help="write sizes, sha256 and the report here")
    args = ap.parse_args(argv)
    from verst_planner.domain.errors import OpeningHoursParseError
    from verst_planner.hours import parse

    def hours_ok(text: str) -> bool:
        try:
            parse(text)
        except OpeningHoursParseError:
            return False
        return True

    ldoc, rdoc, report = build(args.lodging, args.roadside, args.catalogue, hours_ok, args.food, args.roads)
    out = args.out or args.catalogue
    out.mkdir(parents=True, exist_ok=True)
    entry: dict[str, Any] = {"version": report["version"], "report": report, "files": {}}
    for name, doc in ((LODGING_FILE, ldoc), (ROADSIDE_FILE, rdoc)):
        data = dump_gz(doc)
        (out / name).write_bytes(data)
        entry["files"][name] = {"count": doc["n"], "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    entry["townsSha256"] = ldoc["townsSha256"]
    text = json.dumps(entry, ensure_ascii=False, indent=1) + "\n"
    if args.lock is not None:
        args.lock.write_text(text, "utf-8")
    print(text)
    return 0 if ldoc["n"] and rdoc["n"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
