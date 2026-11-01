"""Restaurants, cafés, fast food and food courts from the Geofabrik OSM extract (CEO 2026-10-29). CI only:

    osmium tags-filter russia-latest.osm.pbf nwr/amenity=restaurant,cafe,fast_food,food_court -o food.osm.pbf
    osmium export food.osm.pbf -f geojsonseq --add-unique-id=type_id -o food.geojsonseq
    python3 tools/data/food_from_extract.py RAW_DIR food.geojsonseq [--abroad]   # writes RAW_DIR/food.json

The same path as the bars (`bars_from_extract.elements_from_features`, `fetch_overpass.assign` over every
catalogue town): named places only, each with the tags the catalogue uses (`KEEP`: kind, name, cuisine, opening
hours, the brand tags that mark a chain). `build_catalogue.py` caps them per town and writes
`catalogue_food.json.gz`. `food_from_features` is pure and tested in the sandbox. `--abroad` (CEO 29.10,
`data-abroad.yml`) also keeps `name:ru` and `name:en`: the builder names a place abroad in Russian first.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bars_from_extract import elements_from_features
from fetch_overpass import all_towns, assign, radius_all_m

FOOD_AMENITIES = frozenset({"restaurant", "cafe", "fast_food", "food_court"})
KEEP = ("amenity", "name", "cuisine", "opening_hours", "brand", "brand:wikidata", "brand:ru")
KEEP_ABROAD = ("name:ru", "name:en")


def food_from_features(lines: Iterable[str], abroad: bool = False) -> list[dict[str, Any]]:
    """Named food places (Overpass-shaped elements) with the `KEEP` tags only (the raw file stays small)."""
    keep = KEEP + KEEP_ABROAD if abroad else KEEP
    out = []
    for e in elements_from_features(lines):
        tags = e["tags"]
        if tags.get("amenity") not in FOOD_AMENITIES:
            continue
        out.append({**e, "tags": {k: tags[k] for k in keep if k in tags}})
    return out


def main(argv: list[str]) -> int:
    raw, seq = Path(argv[0]), Path(argv[1])
    towns = json.loads((raw / "towns.json").read_text("utf-8"))
    pick = all_towns(towns)
    with seq.open(encoding="utf-8") as fh:
        elements = food_from_features(fh, "--abroad" in argv[2:])
    food = assign(elements, pick, radius_all_m)
    (raw / "food.json").write_text(json.dumps(food, ensure_ascii=False), "utf-8")
    print(f"food: {len(food)} rows from {len(elements)} named features, {len(pick)} towns (extract)")
    return 0 if food else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
