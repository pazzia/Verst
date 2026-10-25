"""Fetch bars, pubs, breweries and рюмочные from OSM Overpass for the bigger and the touristic towns
(ADR-0012 §1). Runs in CI only: ``python3 tools/data/fetch_overpass.py OUT_DIR`` (needs towns.json and
pois.json). `towns_to_query`, `bars_from_elements` and `assign` are pure and tested in the sandbox.

Strategy (run 1 spent > 90 min on ~250 per-town queries): one country-wide query (area RU) tried on several
public mirrors, then each bar is assigned to the nearest picked town whose radius covers it. Only when every
mirror fails does it fall back to per-town queries, capped at PER_TOWN_BUDGET_S in total.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from http_util import Pacer, request

OVERPASS = "https://overpass-api.de/api/interpreter"
MIRRORS = (
    OVERPASS,
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
PER_TOWN_BUDGET_S = 45 * 60
MIN_POPULATION = 100_000
TOURIST_TOP = 60
RADIUS_M = ((1_000_000, 9000), (300_000, 6000), (0, 4000))

QUERY = """[out:json][timeout:90];
(
  nwr["amenity"~"^(bar|pub|biergarten)$"]["name"](around:{r},{lat},{lon});
  nwr["craft"="brewery"]["name"](around:{r},{lat},{lon});
);
out center tags;"""

QUERY_ALL = """[out:json][timeout:1200][maxsize:1073741824];
area["ISO3166-1"="RU"][admin_level=2]->.ru;
(
  nwr["amenity"~"^(bar|pub|biergarten)$"]["name"](area.ru);
  nwr["craft"="brewery"]["name"](area.ru);
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


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 12742.0 * math.asin(min(1.0, math.sqrt(a)))


def assign(elements: list[dict[str, Any]], towns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Country-wide elements → bars of the nearest picked town whose radius covers them (others dropped)."""
    cell = 0.2  # degrees; the largest radius is 9 km < 0.2° of latitude
    grid: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for t in towns:
        grid.setdefault((int(t["lat"] // cell), int(t["lon"] // cell)), []).append(t)
    out = []
    for b in bars_from_elements(elements, ""):
        ci, cj = int(b["lat"] // cell), int(b["lon"] // cell)
        best: tuple[float, str] | None = None
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for t in grid.get((ci + di, cj + dj), ()):
                    d = _km(b["lat"], b["lon"], t["lat"], t["lon"])
                    if d * 1000 <= radius_m(t) and (best is None or (d, t["qid"]) < best):
                        best = (d, t["qid"])
        if best is not None:
            out.append({**b, "townQid": best[1]})
    return out


def _country_wide() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors = []
    for url in MIRRORS:
        try:
            doc = request(url, Pacer(1.0), data={"data": QUERY_ALL}, timeout=1500, retries=2)
            return list(doc.get("elements", [])), errors
        except Exception as e:  # next mirror
            errors.append({"mirror": url, "error": repr(e)[:200]})
            print(f"bars: country-wide query failed on {url}: {e!r}"[:300], flush=True)
    return [], errors


def main(argv: list[str]) -> int:
    out = Path(argv[0])
    towns = json.loads((out / "towns.json").read_text("utf-8"))
    pois = json.loads((out / "pois.json").read_text("utf-8"))
    pick = towns_to_query(towns, pois)
    elements, mirror_errors = _country_wide()
    if elements:
        bars = assign(elements, pick)
        (out / "bars.json").write_text(json.dumps(bars, ensure_ascii=False), "utf-8")
        (out / "bars_failed.json").write_text(
            json.dumps(mirror_errors, ensure_ascii=False, indent=1), "utf-8"
        )
        print(f"bars: {len(bars)} rows from {len(elements)} elements, {len(pick)} towns (country-wide)")
        return 0
    pacer = Pacer(2.0)
    bars: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = list(mirror_errors)
    deadline = time.monotonic() + PER_TOWN_BUDGET_S
    for i, t in enumerate(pick):
        if time.monotonic() > deadline:
            failed.append({"qid": t["qid"], "name": t["name"], "error": "per-town time budget spent"})
            continue
        q = QUERY.format(r=radius_m(t), lat=t["lat"], lon=t["lon"])
        try:
            doc = request(MIRRORS[i % len(MIRRORS)], pacer, data={"data": q}, timeout=90, retries=2)
            bars += bars_from_elements(doc.get("elements", []), t["qid"])
        except Exception as e:  # reported, the run continues
            failed.append({"qid": t["qid"], "name": t["name"], "error": repr(e)[:200]})
        if i % 20 == 0:
            print(f"bars: {i}/{len(pick)} towns, {len(bars)} rows, {len(failed)} failed", flush=True)
    (out / "bars.json").write_text(json.dumps(bars, ensure_ascii=False), "utf-8")
    (out / "bars_failed.json").write_text(json.dumps(failed, ensure_ascii=False, indent=1), "utf-8")
    print(f"bars: {len(bars)} rows from {len(pick)} towns, {len(failed)} failed")
    return 0 if len(failed) - len(mirror_errors) <= len(pick) // 10 else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
