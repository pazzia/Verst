"""Build `catalogue_parks.json.gz` (CEO 29.10: parks for the walk «парки»; Фрязино had none) from `parks.json`
(`parks_from_extract.py`) and a built catalogue (its towns and POIs). Pure and stdlib only.

    python3 tools/data/build_parks.py RAW_DIR CATALOGUE_DIR [--out DIR] [--country CC] [--lock PATH]

A separate file next to the other catalogue files, so it ships on its own: the Russian catalogue in
`verst_planner/resources/` (APK) is not touched, and an engine that does not read the file sees no change. The
table is columnar like the others (`verst_planner.catalogue.PARK_COLS`):

- ``id`` ``osm_w123`` (the id an OSM POI of the same object has in `catalogue_pois`), ``name``, ``kind``
  (index into `PARK_KINDS`: park, garden), ``lat``/``lon`` (the area-weighted centre, degrees × 1e5),
  ``town`` (index into `catalogue_towns` of the same build), ``area`` (m²), ``poi`` (the `catalogue_pois` id of
  the same park — `osm_…` or the Wikidata `Q…` of its `wikidata` tag — or null), ``hours`` (OSM opening_hours
  that parse, or null); abroad also ``nameLang`` (ru / local / en, `build_catalogue.osm_name`).

The document also carries ``version`` (the catalogue it belongs to), ``townsSha256`` (the sha256 of that
build's `catalogue_towns.json.gz`: a loader must ignore the parks when it does not match), ``kinds`` and the
ODbL ``licence`` notice of OpenStreetMap. Per town: deny-listed names out, one row per name (the largest
area), the largest parks first, at most `park_cap(population)`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PLANNER = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLANNER))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_catalogue import (  # noqa: E402
    ODBL_URI,
    OSM_COPYRIGHT_URI,
    denied,
    denylist,
    load_json,
    norm,
    osm_name,
)
from countries import RU, Country, get  # noqa: E402
from enrich import tidy  # noqa: E402

from verst_planner.catalogue import (  # noqa: E402
    FILES,
    FORMAT_VERSION,
    PARK_COLS,
    PARK_KINDS,
    PARKS_FILE,
    POI_COLS,
    TOWN_COLS,
    decode_table,
    dump_gz,
    encode_table,
    load_gz,
    to_coord,
)

PARK_CAP_MIN, PARK_CAP_MAX, PARK_CAP_PEOPLE = 5, 60, 20_000


def park_cap(population: int) -> int:
    """5 parks for a town of up to 100 000 people, one more per 20 000, at most 60 (Москва, СПб)."""
    return max(PARK_CAP_MIN, min(PARK_CAP_MAX, population // PARK_CAP_PEOPLE))


def parks_licence(version: str) -> dict[str, Any]:
    return {
        "licence": "ODbL-1.0",
        "uri": ODBL_URI,
        "text": "© OpenStreetMap contributors",
        "source": OSM_COPYRIGHT_URI,
        "note": "Part of the Verst place catalogue (a Derivative Database of OpenStreetMap, ODbL 1.0); see "
        "catalogue_meta.licence of the same build.",
        "build": version,
    }


def build_parks(
    raw_parks: list[dict[str, Any]],
    towns_doc: dict[str, Any],
    pois_doc: dict[str, Any],
    deny: list[str],
    hours_ok: Any = None,
    country: Country = RU,
) -> list[dict[str, Any]]:
    """The park rows of one catalogue (towns and POIs of the same build), capped per town."""
    towns = decode_table(towns_doc, TOWN_COLS, "towns")
    town_pos = {t["id"]: i for i, t in enumerate(towns)}
    poi_ids = {str(p["id"]) for p in decode_table(pois_doc, POI_COLS[:1], "pois")}
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for p in raw_parks:
        tags = p.get("tags") or {}
        if p.get("townQid") not in town_pos or tags.get("leisure") not in PARK_KINDS:
            continue
        name, lang = (
            osm_name(tags, p.get("name")) if country.abroad else (p.get("name") or tags.get("name"), None)
        )
        name = tidy(str(name or "").strip()) or ""
        if not name or denied(name, deny):
            continue
        key = (p["townQid"], norm(name))
        old = best.get(key)
        if old is None or (p["area"], old["osm"]) > (old["area"], p["osm"]):
            best[key] = {**p, "_name": name, "_lang": lang}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for p in best.values():
        grouped.setdefault(p["townQid"], []).append(p)
    rows = []
    for qid in sorted(grouped, key=lambda q: town_pos[q]):
        lst = sorted(grouped[qid], key=lambda p: (-p["area"], p["osm"]))
        for p in lst[: park_cap(int(towns[town_pos[qid]]["pop"] or 0))]:
            tags = p.get("tags") or {}
            osm_id = f"osm_{p['osm']}"
            wd = tags.get("wikidata")
            hours = tags.get("opening_hours")
            if hours and hours_ok is not None and not hours_ok(hours):
                hours = None
            row = {
                "id": osm_id,
                "name": p["_name"],
                "kind": PARK_KINDS.index(tags["leisure"]),
                "lat": to_coord(p["lat"]),
                "lon": to_coord(p["lon"]),
                "town": town_pos[qid],
                "area": int(p["area"]),
                "poi": osm_id if osm_id in poi_ids else wd if wd in poi_ids else None,
                "hours": hours,
            }
            if country.abroad:
                row["nameLang"] = p["_lang"]
            rows.append(row)
    return rows


def parks_doc(raw: Path, cat_dir: Path, hours_ok: Any = None, country: Country = RU) -> dict[str, Any]:
    """The `catalogue_parks` document for the catalogue in `cat_dir` (its meta, towns and POIs)."""
    towns_bytes = (cat_dir / FILES["towns"]).read_bytes()
    meta = load_gz((cat_dir / FILES["meta"]).read_bytes(), "meta")
    rows = build_parks(
        load_json(raw / "parks.json", []),
        load_gz(towns_bytes, "towns"),
        load_gz((cat_dir / FILES["pois"]).read_bytes(), "pois"),
        denylist(),
        hours_ok,
        country,
    )
    cols = PARK_COLS + (("nameLang",) if country.abroad else ())
    doc = encode_table(rows, cols)
    assert doc["v"] == FORMAT_VERSION
    doc.update(
        {
            "version": meta["version"],
            "townsSha256": hashlib.sha256(towns_bytes).hexdigest(),
            "kinds": list(PARK_KINDS),
            "licence": parks_licence(meta["version"]),
        }
    )
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="build_parks")
    ap.add_argument("raw", type=Path)
    ap.add_argument("catalogue", type=Path, help="the directory of the built catalogue_*.json.gz")
    ap.add_argument("--out", type=Path, default=None, help="default: the catalogue directory")
    ap.add_argument("--country", default=None)
    ap.add_argument("--lock", type=Path, default=None, help="write the size and sha256 of the file here")
    args = ap.parse_args(argv)
    from verst_planner.domain.errors import OpeningHoursParseError
    from verst_planner.hours import parse

    def hours_ok(text: str) -> bool:
        try:
            parse(text)
        except OpeningHoursParseError:
            return False
        return True

    doc = parks_doc(args.raw, args.catalogue, hours_ok, get(args.country))
    data = dump_gz(doc)
    out = args.out or args.catalogue
    out.mkdir(parents=True, exist_ok=True)
    (out / PARKS_FILE).write_bytes(data)
    entry = {
        "version": doc["version"],
        "count": doc["n"],
        "townsSha256": doc["townsSha256"],
        "file": PARKS_FILE,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    if args.lock is not None:
        args.lock.write_text(json.dumps(entry, ensure_ascii=False, indent=1) + "\n", "utf-8")
    print(json.dumps(entry, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
