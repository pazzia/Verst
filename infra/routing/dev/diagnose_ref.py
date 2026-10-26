"""Temporary ENG-01 diagnosis: why does the car profile not use a road (default М-12)?

Reads a GeoJSON-seq export of motorway/trunk ways (osmium export -f geojsonseq), summarises the tags of the ways
whose `ref` names the road, then asks the running GraphHopper for routes forced through a point on that road.
Usage: python3 diagnose_ref.py WAYS.geojsonseq http://127.0.0.1:8989 [REF]
"""

from __future__ import annotations

import collections
import json
import re
import sys
import urllib.request

MSK = (55.7558, 37.6173)
KZN = (55.7963, 49.1088)
KEYS = ("highway", "toll", "access", "motor_vehicle", "motorcar", "vehicle", "motorroad", "oneway", "maxspeed",
        "construction", "opening_date", "toll:hgv", "barrier")


def main() -> None:
    path, url = sys.argv[1], sys.argv[2]
    ref = sys.argv[3] if len(sys.argv) > 3 else "М-12"
    pat = re.compile(r"(^|;)\s*[МM]-?12\s*($|;)") if ref == "М-12" else re.compile(re.escape(ref))
    combos: collections.Counter[tuple] = collections.Counter()
    mids: list[tuple[float, float]] = []
    n = 0
    refs_seen: collections.Counter[str] = collections.Counter()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip().lstrip("\x1e")
            if not line:
                continue
            ft = json.loads(line)
            p = ft.get("properties", {})
            r = p.get("ref", "")
            if "12" in r:
                refs_seen[r] += 1
            if not pat.search(r):
                continue
            n += 1
            combos[tuple(f"{k}={p[k]}" for k in KEYS if k in p)] += 1
            coords = ft["geometry"]["coordinates"]
            lon, lat = coords[len(coords) // 2]
            mids.append((lat, lon))
    print(f"ways with ref {ref}: {n}")
    print("refs containing '12' (top 15):", refs_seen.most_common(15))
    for c, k in combos.most_common(25):
        print(f"{k:5d}  {' '.join(c)}")
    if not mids:
        return
    mids.sort(key=lambda p: p[1])
    probes = [mids[len(mids) // 4], mids[len(mids) // 2], mids[3 * len(mids) // 4]]
    for profile in ("car", "car_avoid_tolls"):
        route(url, profile, [MSK, KZN], "direct")
        for i, pr in enumerate(probes):
            route(url, profile, [MSK, pr, KZN], f"via probe {i} {pr[0]:.4f},{pr[1]:.4f}")
    for i, pr in enumerate(probes):
        route(url, "car", [pr, KZN], f"probe {i} -> Kazan")
        route(url, "car", [MSK, pr], f"Moscow -> probe {i}")


def route(url: str, profile: str, pts: list[tuple[float, float]], label: str) -> None:
    body = {"profile": profile, "points": [[lon, lat] for lat, lon in pts], "points_encoded": False,
            "details": ["street_ref", "toll", "road_class"], "instructions": False}
    req = urllib.request.Request(url + "/route", json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            d = json.load(resp)
    except Exception as e:  # noqa: BLE001 - diagnosis prints every failure
        msg = getattr(e, "read", lambda: b"")().decode(errors="replace")[:300]
        print(f"[{profile}] {label}: ERROR {e} {msg}")
        return
    p = d["paths"][0]
    coords = p["points"]["coordinates"]
    km = [0.0]
    import math
    for (lo1, la1), (lo2, la2) in zip(coords, coords[1:]):
        x = math.radians(lo2 - lo1) * math.cos(math.radians((la1 + la2) / 2))
        y = math.radians(la2 - la1)
        km.append(km[-1] + 6371.0 * math.hypot(x, y))
    by_ref: collections.Counter[str] = collections.Counter()
    for a, b, v in p["details"].get("street_ref", []):
        by_ref[str(v)] += km[b] - km[a]
    toll = sum(km[b] - km[a] for a, b, v in p["details"].get("toll", []) if v not in (None, "no", "NO", "MISSING"))
    tolls = collections.Counter(str(v) for _a, _b, v in p["details"].get("toll", []))
    top = ", ".join(f"{k} {v:.0f}" for k, v in by_ref.most_common(6))
    print(f"[{profile}] {label}: {p['distance']/1000:.1f} km, {p['time']/60000:.0f} min, toll-ish km {toll:.0f} "
          f"{dict(tolls)}; refs: {top}")


if __name__ == "__main__":
    main()
