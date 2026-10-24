"""Calibrate the synthetic road model of `HybridRouting` on the fixture road graph (ADR-0012 §4).

For every pair of fixture towns at ≥ 15 km straight line, the fixture graph route gives road km and minutes.
Pairs are bucketed by straight-line distance `h`; each bucket contributes one breakpoint
`(median h, median road/straight ratio, median speed km/h)`. `HybridRouting` interpolates linearly between
the breakpoints and clamps outside them. The error of that model against the fixture routes (MAPE, p90, max)
is written into the same file so the documentation can quote it.

Usage (from `backend/planner`): ``python3 tools/calibrate_detour.py [--check]``. Writes
`verst_planner/resources/detour_model.json`; with ``--check`` it fails if the committed file differs.
"""

from __future__ import annotations

import itertools
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from verst_planner.adapters.fake import FakeWorld  # noqa: E402
from verst_planner.adapters.fake.routing import FakeRouting  # noqa: E402
from verst_planner.domain.errors import PlannerError  # noqa: E402
from verst_planner.domain.model import RouteRequest  # noqa: E402
from verst_planner.geo.distance import haversine_km  # noqa: E402
from verst_planner.geo.roadmodel import RoadModel  # noqa: E402

OUT = ROOT / "verst_planner" / "resources" / "detour_model.json"
BUCKETS = (15.0, 100.0, 300.0, 600.0, 10_000.0)
MIN_KM = 15.0


def pairs() -> list[tuple[float, float, float]]:
    world = FakeWorld.load(ROOT / "fixtures" / "worlds" / "central_russia_v1.json")
    routing = FakeRouting(world)
    out = []
    for a, b in itertools.combinations(sorted(world.towns.values(), key=lambda t: t.id), 2):
        h = haversine_km(a.point, b.point)
        if h < MIN_KM:
            continue
        try:
            r = routing.route(RouteRequest((a.point, b.point), False))
        except PlannerError:
            continue
        out.append((h, r.km_total, r.min_total))
    return out


def calibrate() -> dict[str, object]:
    rows = pairs()
    points = []
    for lo, hi in itertools.pairwise(BUCKETS):
        sel = [r for r in rows if lo <= r[0] < hi]
        if not sel:
            continue
        points.append(
            {
                "straightKm": round(statistics.median(r[0] for r in sel), 1),
                "ratio": round(statistics.median(r[1] / r[0] for r in sel), 3),
                "speedKmh": round(statistics.median(r[1] / (r[2] / 60.0) for r in sel), 1),
                "pairs": len(sel),
            }
        )
    model = RoadModel.from_dict({"points": points})
    errors = sorted(abs(model.road_km(h) - km) / km for h, km, _m in rows)
    time_errors = sorted(abs(model.minutes(h) - m) / m for h, _km, m in rows)
    return {
        "source": "fixtures/worlds/central_russia_v1.json town pairs (tools/calibrate_detour.py)",
        "points": points,
        "error": {
            "pairs": len(rows),
            "kmMapePct": round(100 * statistics.mean(errors), 1),
            "kmP90Pct": round(100 * errors[int(0.9 * (len(errors) - 1))], 1),
            "kmMaxPct": round(100 * errors[-1], 1),
            "minutesMapePct": round(100 * statistics.mean(time_errors), 1),
        },
        "note": "Sparse fixture graph (all corridors meet at Moscow): real roads are usually shorter.",
    }


def main(argv: list[str]) -> int:
    text = json.dumps(calibrate(), ensure_ascii=False, indent=1) + "\n"
    if "--check" in argv:
        return 0 if OUT.read_text("utf-8") == text else 1
    OUT.write_text(text, "utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
