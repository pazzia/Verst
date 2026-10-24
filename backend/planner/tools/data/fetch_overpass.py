"""Fetch bars, pubs, breweries and рюмочные from OSM Overpass for the bigger and the touristic towns
(ADR-0012 §1). Runs in CI only: ``python3 tools/data/fetch_overpass.py OUT_DIR`` (needs towns.json and
pois.json). `towns_to_query` and `bars_from_elements` are pure and tested in the sandbox.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from http_util import Pacer, request

OVERPASS = "https://overpass-api.de/api/interpreter"
MIN_POPULATION = 100_000
TOURIST_TOP = 60
RADIUS_M = ((1_000_000, 9000), (300_000, 6000), (0, 4000))

QUERY = """[out:json][timeout:90];
(
  nwr["amenity"~"^(bar|pub|biergarten)$"]["name"](around:{r},{lat},{lon});
  nwr["craft"="brewery"]["name"](around:{r},{lat},{lon});
  nwr["name"~"рюмочн",i](around:{r},{lat},{lon});
);
out center tags;"""


def towns_to_query(towns: list[dict[str, Any]], pois: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Towns ≥ 100 000 people plus the top towns by POI sitelinks, biggest first."""
    by_town: dict[str, int] = {}
    for p in pois:
        by_town[p["townQid"]] = by_town.get(p["townQid"], 0) + int(p.get("sitelinks") or 0)
    tourist = {q for q, _s in sorted(by_town.items(), key=lambda x: (-x[1], x[0]))[:TOURIST_TOP]}
    pick = [t for t in towns if (t.get("population") or 0) >= MIN_POPULATION or t["qid"] in tourist]
    return sorted(pick, key=lambda t: (-(t.get("population") or 0), t["qid"]))


def radius_m(t: dict[str, Any]) -> int:
    return next(r for threshold, r in RADIUS_M if (t.get("population") or 0) >= threshold)


def bars_from_elements(elements: list[dict[str, Any]], town_qid: str) -> list[dict[str, Any]]:
    out = []
    for e in elements:
        tags = e.get("tags") or {}
        if "lat" in e:
            lat, lon = e["lat"], e["lon"]
        elif "center" in e:
            lat, lon = e["center"]["lat"], e["center"]["lon"]
        else:
            continue
        kind = {"node": "n", "way": "w", "relation": "r"}.get(e.get("type", ""), "x")
        out.append(
            {
                "osm": f"{kind}{e['id']}",
                "name": tags.get("name"),
                "lat": lat,
                "lon": lon,
                "tags": tags,
                "townQid": town_qid,
            }
        )
    return sorted(out, key=lambda b: b["osm"])


def main(argv: list[str]) -> int:
    out = Path(argv[0])
    towns = json.loads((out / "towns.json").read_text("utf-8"))
    pois = json.loads((out / "pois.json").read_text("utf-8"))
    pacer = Pacer(2.0)
    bars: list[dict[str, Any]] = []
    failed = []
    pick = towns_to_query(towns, pois)
    for i, t in enumerate(pick):
        q = QUERY.format(r=radius_m(t), lat=t["lat"], lon=t["lon"])
        try:
            doc = request(OVERPASS, pacer, data={"data": q}, timeout=180)
            bars += bars_from_elements(doc.get("elements", []), t["qid"])
        except Exception as e:  # reported, the run continues
            failed.append({"qid": t["qid"], "name": t["name"], "error": repr(e)[:200]})
        if i % 20 == 0:
            print(f"bars: {i}/{len(pick)} towns, {len(bars)} rows, {len(failed)} failed", flush=True)
    (out / "bars.json").write_text(json.dumps(bars, ensure_ascii=False), "utf-8")
    (out / "bars_failed.json").write_text(json.dumps(failed, ensure_ascii=False, indent=1), "utf-8")
    print(f"bars: {len(bars)} rows from {len(pick)} towns, {len(failed)} failed")
    return 0 if len(failed) <= len(pick) // 10 else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
