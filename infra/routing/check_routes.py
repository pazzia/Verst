"""ENG-01 integration check: real routes and real plans through `GraphHopperRouting` (ADR-0017 §6).

    PYTHONPATH=backend/planner python3 infra/routing/check_routes.py --url http://127.0.0.1:8989 --out OUT_DIR

For every route in references.json: route it through the adapter (1 warm-up + `--repeat` timed calls), compare
road km with the reference, check the expected road refs and toll km, and record the raw GraphHopper responses
(OUT_DIR/recordings/*.json, the same format as tests/data/graphhopper/). For every plan: run the full planner on
the `russia_v1` world with the adapter as routing and time it. Writes OUT_DIR/report.json and report.md (also
appended to $GITHUB_STEP_SUMMARY) and exits 1 if any gate fails:

- km within `tolerancePct` (3 %) of `yandexKm` when a human has confirmed it, else within
  `unconfirmedTolerancePct` of the published `referenceKm`;
- routing p95 <= `--route-budget-ms` (1 000 ms: a tenth of the plan budget), plan p95 <= 10 000 ms (SPEC §16);
- no route or plan is synthetic; the `expect` refs and toll limits hold.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from verst_planner.adapters.graphhopper import (
    GraphHopperRouting,
    GraphHopperSettings,
    UrllibTransport,
)
from verst_planner.domain.model import LatLon, Route, RouteRequest

HERE = Path(__file__).resolve().parent
PLANNER = HERE.parent.parent / "backend" / "planner"


class RecordingTransport(UrllibTransport):
    """Keeps every request and raw response so CI can publish them as fixtures."""

    def __init__(self) -> None:
        super().__init__()
        self.log: list[tuple[dict[str, Any], int, bytes]] = []

    def post_json(self, url: str, body: bytes, deadline: float) -> tuple[int, bytes]:
        status, raw = super().post_json(url, body, deadline)
        self.log.append((json.loads(body), status, raw))
        return status, raw


@dataclass
class Result:
    id: str
    ok: bool = True
    notes: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def fail(self, note: str) -> None:
        self.ok = False
        self.notes.append(note)


def p95(xs: list[float]) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, math.ceil(0.95 * len(s)) - 1)]


def toll_km(r: Route) -> float:
    return sum(r.cum_km[d.to_idx] - r.cum_km[d.from_idx] for d in r.details if d.toll)


def km_by_ref(r: Route) -> dict[str, float]:
    out: dict[str, float] = {}
    for d in r.details:
        if d.road_ref:
            out[d.road_ref] = (
                out.get(d.road_ref, 0.0) + r.cum_km[d.to_idx] - r.cum_km[d.from_idx]
            )
    return out


def check_route(
    spec: dict[str, Any],
    cfg: dict[str, Any],
    url: str,
    repeat: int,
    budget_ms: float,
    out: Path,
    meta: dict[str, Any],
) -> Result:
    res = Result(spec["id"])
    transport = RecordingTransport()
    gh = GraphHopperRouting(GraphHopperSettings(url), transport)
    req = RouteRequest(
        tuple(LatLon(a, b) for a, b in spec["points"]), bool(spec["avoidTolls"])
    )
    route = gh.route(req)  # warm-up (JIT, page cache); recorded
    times = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        gh.route(req)
        times.append((time.perf_counter() - t0) * 1000)
    request, status, raw = transport.log[0]
    rec = {
        "_meta": {**meta, "note": spec["titleRu"]},
        "request": request,
        "status": status,
        "body": json.loads(raw),
    }
    (out / "recordings").mkdir(parents=True, exist_ok=True)
    (out / "recordings" / f"{spec['id']}.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1) + "\n", "utf-8"
    )

    confirmed = spec.get("yandexKm") is not None
    ref = float(spec["yandexKm"] if confirmed else spec["referenceKm"])
    tol = float(cfg["tolerancePct"] if confirmed else cfg["unconfirmedTolerancePct"])
    dev = (route.km_total - ref) / ref * 100
    refs = km_by_ref(route)
    res.data = {
        "titleRu": spec["titleRu"],
        "km": round(route.km_total, 1),
        "min": round(route.min_total),
        "referenceKm": ref,
        "referenceKind": "yandex" if confirmed else "published",
        "deviationPct": round(dev, 2),
        "tolerancePct": tol,
        "tollKm": round(toll_km(route), 1),
        "points": len(route.points),
        "responseBytes": len(raw),
        "routeMsP50": round(statistics.median(times)),
        "routeMsP95": round(p95(times)),
        "topRefs": sorted(
            ((k, round(v)) for k, v in refs.items()), key=lambda kv: -kv[1]
        )[:6],
        "sources": spec["sources"],
    }
    if abs(dev) > tol:
        res.fail(f"km {route.km_total:.1f} vs {ref:.0f} ({dev:+.1f} % > ±{tol} %)")
    if not confirmed:
        res.notes.append(
            "UNCONFIRMED: fill yandexKm from Яндекс Карты to apply the 3 % gate"
        )
    if route.synthetic:
        res.fail("route is synthetic")
    if p95(times) > budget_ms:
        res.fail(f"routing p95 {p95(times):.0f} ms > {budget_ms:.0f} ms")
    expect = spec.get("expect", {})
    for want in expect.get("refsInclude", []):
        if refs.get(want, 0.0) < 1.0:
            res.fail(f"ref {want} not on the route")
    tk = toll_km(route)
    if "tollKmMax" in expect and tk > expect["tollKmMax"]:
        res.fail(f"toll km {tk:.1f} > {expect['tollKmMax']}")
    if "tollKmMin" in expect and tk < expect["tollKmMin"]:
        res.fail(f"toll km {tk:.1f} < {expect['tollKmMin']}")
    return res


def check_plans(
    specs: list[dict[str, Any]], url: str, repeat: int, budget_ms: float
) -> list[Result]:
    """Full plans on `russia_v1` (fixture world + packaged catalogue, as the app composes it in mobile.py) with
    GraphHopper as routing. The engine stays unchanged; only the routing port differs."""
    from verst_planner import mobile
    from verst_planner.adapters.catalogue import build_catalogue_ports, compose
    from verst_planner.adapters.fake import FakeWorld
    from verst_planner.catalogue import load_packaged
    from verst_planner.config import PlannerConfig
    from verst_planner.domain import codec
    from verst_planner.engine import Planner
    from verst_planner.explain.templates import ReasonTemplates

    base = FakeWorld.load(PLANNER / "fixtures" / "worlds" / "central_russia_v1.json")
    ports = build_catalogue_ports(compose(base, load_packaged()))
    gh = GraphHopperRouting(GraphHopperSettings(url))
    planner = Planner(
        routing=gh,
        places=ports.places,
        prices=ports.prices,
        tolls=ports.tolls,
        regions=ports.regions,
        geocoding=ports.geocoding,
        clock=ports.clock,
        config=PlannerConfig.from_dict(mobile.OPEN_DATA_CONFIG),
        templates=ReasonTemplates.default(),
        parking=ports.parking,
    )
    out = []
    for spec in specs:
        res = Result(spec["id"])
        trip = codec.input_from_json(spec["input"])
        times = []
        plan = None
        for _ in range(repeat + 1):  # the first run warms caches and is not timed
            t0 = time.perf_counter()
            plan = planner.plan(trip)
            times.append((time.perf_counter() - t0) * 1000)
        assert plan is not None
        body = codec.plan_to_json(plan)
        res.data = {
            "km": plan.km,
            "days": body.get("days"),
            "planMsP50": round(statistics.median(times[1:])),
            "planMsP95": round(p95(times[1:])),
            "approxDistances": bool(body.get("approxDistances")),
        }
        if body.get("approxDistances"):
            res.fail("plan is marked approxDistances (synthetic route)")
        if p95(times[1:]) > budget_ms:
            res.fail(f"plan p95 {p95(times[1:]):.0f} ms > {budget_ms:.0f} ms")
        out.append(res)
    return out


def report_md(routes: list[Result], plans: list[Result], meta: dict[str, Any]) -> str:
    lines = [
        f"## ENG-01 routing check ({meta.get('source', '')})",
        "",
        "| Trip | km | min | reference km | Δ % | gate | toll km | main refs | route ms p50/p95 | result |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: | --- |",
    ]
    for r in routes:
        d = r.data
        refs = ", ".join(f"{k} {v}" for k, v in d.get("topRefs", []))
        lines.append(
            f"| {d.get('titleRu', r.id)[:60]} | {d.get('km')} | {d.get('min')} | {d.get('referenceKm')} "
            f"({d.get('referenceKind')}) | {d.get('deviationPct')} | ±{d.get('tolerancePct')} | "
            f"{d.get('tollKm')} | {refs} | {d.get('routeMsP50')}/{d.get('routeMsP95')} | "
            f"{'OK' if r.ok else 'FAIL'} {'; '.join(r.notes)} |"
        )
    lines += [
        "",
        "| Plan | km | days | plan ms p50/p95 | result |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for r in plans:
        d = r.data
        lines.append(
            f"| {r.id} | {d.get('km')} | {d.get('days')} | {d.get('planMsP50')}/{d.get('planMsP95')} | "
            f"{'OK' if r.ok else 'FAIL'} {'; '.join(r.notes)} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--url",
        default=os.environ.get("VERST_GRAPHHOPPER_URL", "http://127.0.0.1:8989"),
    )
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--references", type=Path, default=HERE / "references.json")
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("--route-budget-ms", type=float, default=1000.0)
    ap.add_argument("--plan-budget-ms", type=float, default=10000.0)
    ap.add_argument(
        "--source",
        default="GraphHopper, unknown extract",
        help="recorded in every recording's _meta",
    )
    ap.add_argument("--skip-plans", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    cfg = json.loads(args.references.read_text("utf-8"))
    meta = {
        "source": args.source,
        "recordedBy": "infra/routing/check_routes.py (.github/workflows/routing.yml)",
        "schema": "https://github.com/graphhopper/graphhopper/blob/11.0/docs/web/api-doc.md",
    }
    args.out.mkdir(parents=True, exist_ok=True)
    routes = []
    for spec in cfg["routes"]:
        try:
            routes.append(
                check_route(
                    spec,
                    cfg,
                    args.url,
                    args.repeat,
                    args.route_budget_ms,
                    args.out,
                    meta,
                )
            )
        except Exception as e:  # noqa: BLE001 -- report every trip, then fail the run
            r = Result(spec["id"])
            r.fail(f"{type(e).__name__}: {e}")
            routes.append(r)
    plans: list[Result] = []
    if not args.skip_plans:
        try:
            plans = check_plans(
                cfg["plans"], args.url, args.repeat, args.plan_budget_ms
            )
        except Exception as e:  # noqa: BLE001 -- the report must still be written
            r = Result("plans")
            r.fail(f"{type(e).__name__}: {e}")
            plans = [r]

    report = {
        "meta": meta,
        "routes": [r.__dict__ for r in routes],
        "plans": [r.__dict__ for r in plans],
    }
    (args.out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1) + "\n", "utf-8"
    )
    md = report_md(routes, plans, meta)
    (args.out / "report.md").write_text(md, "utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(md)
    print(md)
    return 0 if all(r.ok for r in routes + plans) else 1


if __name__ == "__main__":
    sys.exit(main())
