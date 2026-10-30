"""The Geofabrik extract of a country, found by its ISO 3166-1 code in Geofabrik's own index (CEO 29.10: the
extract paths differ — europe/belarus, asia/kazakhstan, europe/georgia or asia/georgia… — so none is guessed).
CI only (`data-abroad.yml`):

    curl -fsSL -o index.json https://download.geofabrik.de/index-v1-nogeom.json
    python3 tools/data/geofabrik_url.py index.json GE      # prints https://download.geofabrik.de/…/georgia-latest.osm.pbf

`pbf_url` is pure and tested in the sandbox: among the index features whose `iso3166-1:alpha2` lists the code,
the one whose parent is not itself a match (the country, not its sub-regions); exit 2 when none or several.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

INDEX_URL = "https://download.geofabrik.de/index-v1-nogeom.json"


def pbf_url(index: dict[str, Any], iso: str) -> str:
    props = [f.get("properties") or {} for f in index.get("features", [])]
    matches = [p for p in props if iso.upper() in (p.get("iso3166-1:alpha2") or [])]
    ids = {p.get("id") for p in matches}
    top = [p for p in matches if p.get("parent") not in ids]
    if len(top) != 1:
        raise LookupError(f"{iso}: {len(top)} top-level Geofabrik extracts: {[p.get('id') for p in top]}")
    return str(top[0]["urls"]["pbf"])


def main(argv: list[str]) -> int:
    index = json.loads(Path(argv[0]).read_text("utf-8"))
    try:
        print(pbf_url(index, argv[1]))
    except LookupError as e:
        print(e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
