"""Throughput of a GraphHopper server under parallel load, through `GraphHopperRouting` (server sizing).

    PYTHONPATH=backend/planner python3 infra/routing/load_test.py --url http://127.0.0.1:8989 --out OUT_DIR

Routes random pairs of real towns (the `central_russia_v1` fixture world) that lie inside the server's bbox,
`--threads` at a time, `--requests` in total after a warm-up, and writes OUT_DIR/load.json and a summary line
for $GITHUB_STEP_SUMMARY: requests per second, latency p50/p95/p99 and the number of unreachable pairs.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

from verst_planner.adapters.graphhopper import GraphHopperRouting, GraphHopperSettings
from verst_planner.domain.errors import Unreachable, UpstreamUnavailable
from verst_planner.domain.model import LatLon, RouteRequest

HERE = Path(__file__).resolve().parent
WORLD = HERE.parent.parent / "backend" / "planner" / "fixtures" / "worlds" / "central_russia_v1.json"


def towns_in(bbox: list[float]) -> list[LatLon]:
    w = json.loads(WORLD.read_text("utf-8"))
    nodes = {n["id"]: n for n in w["nodes"]}
    lon0, lat0, lon1, lat1 = bbox
    out = []
    for t in w["towns"]:
        n = nodes[t["node"]]
        lat, lon = float(n["lat"]), float(n["lon"])
        if lat0 <= lat <= lat1 and lon0 <= lon <= lon1:
            out.append(LatLon(lat, lon))
    return out


def pct(xs: list[float], p: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, round(p / 100 * (len(s) - 1)))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--requests", type=int, default=400)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    with urlopen(args.url.rstrip("/") + "/info", timeout=10) as r:
        bbox = json.load(r)["bbox"]
    towns = towns_in(bbox)
    rng = random.Random(1)
    pairs = [tuple(rng.sample(towns, 2)) for _ in range(args.requests + args.threads)]
    gh = GraphHopperRouting(GraphHopperSettings(args.url, timeout_s=10.0))

    def one(pair: tuple[LatLon, LatLon]) -> tuple[float, float | str]:
        t0 = time.perf_counter()
        km: float | str
        try:
            km = gh.route(RouteRequest(pair, False)).km_total
        except Unreachable:
            km = "unreachable"
        except UpstreamUnavailable:
            km = "error"  # timeout or 5xx: the server could not keep up
        return (time.perf_counter() - t0) * 1000, km

    with ThreadPoolExecutor(args.threads) as ex:
        list(ex.map(one, pairs[: args.threads]))  # warm-up: JIT, page cache
        t0 = time.perf_counter()
        res = list(ex.map(one, pairs[args.threads :]))
        wall = time.perf_counter() - t0
    ok = [ms for ms, km in res if isinstance(km, float)]
    kms = [km for _ms, km in res if isinstance(km, float)]
    report = {
        "label": args.label,
        "towns": len(towns),
        "requests": len(res),
        "threads": args.threads,
        "unreachable": sum(1 for _ms, km in res if km == "unreachable"),
        "errors": sum(1 for _ms, km in res if km == "error"),
        "requestsPerSecond": round(len(res) / wall, 1),
        "latencyMs": {f"p{q}": round(pct(ok, q)) for q in (50, 95, 99)} if ok else {},
        "meanKm": round(statistics.mean(kms)) if kms else None,
        "cpus": os.cpu_count(),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "load.json").write_text(json.dumps(report, indent=1) + "\n", "utf-8")
    lat = report["latencyMs"]
    assert isinstance(lat, dict)
    line = (
        f"load {args.label}: {report['requestsPerSecond']} routes/s with {args.threads} threads on "
        f"{report['cpus']} vCPU, p50/p95/p99 {lat.get('p50')}/{lat.get('p95')}/{lat.get('p99')} ms, "
        f"mean {report['meanKm']} km, unreachable {report['unreachable']}, errors {report['errors']}"
    )
    print(line)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(line + "\n\n")


if __name__ == "__main__":
    main()
