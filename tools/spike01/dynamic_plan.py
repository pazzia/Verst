"""SPIKE-01 (ADR-0021 §5): plan a trip dynamically from the open place index through providers chosen per request.

    PYTHONPATH=backend/planner:tools/spike01 python3 tools/spike01/dynamic_plan.py \
        --cases tools/spike01/cases.json --index RU=ru.jsonl --index ID=bali.jsonl --out OUT

Pipeline per case:
1. route the skeleton (selector → routing provider);
2. place search in the corridor (selector → `open_index`; commercial providers are simulated only);
3. Wikidata sitelinks for the candidates;
4. constraints and scoring by the profile (v1);
5. choosing stops per day (density, detour, spacing, the religious cap);
6. re-routing through the stops;
7. a cost simulation: what the commercial calls would cost if a vendor were licensed, for the hybrid pipeline
   (gaps + shortlist enrichment) and for "vendor only".
Writes OUT/report.md, OUT/report.json; with `--baseline` also plans the Russian cases with today's engine.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import poi_index
import wikidata
from poi_index import Hit, Index, Poi
from selector import ProviderSelector

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

INTERESTS: dict[str, dict[str, float]] = {
    "history": {"museum": 1, "castle": 1, "ruins": 1, "monument": 0.6, "monastery": 0.8, "attraction": 0.5},
    "religion": {"temple": 1, "monastery": 1},
    "nature": {"waterfall": 1, "volcano": 1, "cave": 1, "hot_spring": 1, "nature_reserve": 1, "park": 0.6, "beach": 0.5},
    "views": {"viewpoint": 1, "volcano": 0.7},
    "kids": {"zoo": 1, "theme_park": 1, "water_park": 1, "park": 0.5, "museum": 0.3, "beach": 0.5},
    "beach": {"beach": 1},
}
RELIGIOUS = {"temple", "monastery"}
DETOUR_KM = {"relaxed": 5.0, "comfort": 10.0, "active": 20.0}
DWELL_MIN = {"museum": 90, "zoo": 120, "theme_park": 180, "water_park": 180, "castle": 75, "monastery": 60,
             "temple": 45, "waterfall": 60, "volcano": 120, "beach": 90, "park": 60, "nature_reserve": 90}


def notability(p: Poi) -> float:
    if p.sitelinks:
        return min(1.0, math.log10(1 + p.sitelinks) / math.log10(61))
    return 0.15 if p.wikidata else 0.05


def score(p: Poi, profile: dict[str, Any]) -> float:
    weights = profile.get("interests", {})
    interest = max((w * INTERESTS.get(i, {}).get(p.kind, 0.0) for i, w in weights.items()), default=0.0)
    if p.kind == "attraction":
        interest = max(interest, 0.4)
    s = interest * (0.4 + 0.6 * notability(p))
    if p.hours:
        s += 0.05
    if profile.get("crew", {}).get("children") and p.kind in INTERESTS["kids"]:
        s += 0.1
    return round(s, 4)


def allowed(p: Poi, profile: dict[str, Any]) -> tuple[bool, str | None]:
    """Constraints. Unknown is never "allowed by default" (ADR-0019): it passes, flagged «не проверено»."""
    pets = profile.get("crew", {}).get("pets")
    if pets and p.kind in poi_index.SIGHT_KINDS:
        if p.dog == "no":
            return False, "dogs not allowed"
        if p.dog is None:
            return True, "dog policy not verified"
    if p.kind == "monument" and p.sitelinks < 3:
        return False, "minor monument"
    return True, None


def choose(hits: list[Hit], profile: dict[str, Any], km_total: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    days = max(1, math.ceil(km_total / float(profile["dailyKm"])))
    per_day = km_total / days
    density = int(profile.get("density", 3))
    detour = DETOUR_KM[profile.get("level", "comfort")]
    spacing = max(10.0, per_day / (density * 2))
    religion_heavy = profile.get("interests", {}).get("religion", 0) >= 0.8
    chosen: list[dict[str, Any]] = []
    stats = {"days": days, "perDayKm": round(per_day, 1), "gapDays": 0, "excluded": {}}
    for d in range(days):
        lo, hi = d * per_day, (d + 1) * per_day
        pool = []
        for h in hits:
            if not (lo <= h.km_at < hi) or h.lateral_km > detour or h.poi.kind not in poi_index.SIGHT_KINDS:
                continue
            ok, note = allowed(h.poi, profile)
            if not ok:
                stats["excluded"][note] = stats["excluded"].get(note, 0) + 1
                continue
            sc = score(h.poi, profile)
            if sc > 0.15:
                pool.append((sc, h, note))
        pool.sort(key=lambda t: -t[0])
        picked: list[tuple[float, Hit, str | None]] = []
        rel_cap = density if religion_heavy else max(1, math.ceil(density / 3))
        for distinct in (True, False):  # first one stop per kind a day (ADR-0015 §2 diversity), then fill up
            for sc, h, note in pool:
                if len(picked) >= density:
                    break
                if any(q is h for _, q, _ in picked) or any(abs(h.km_at - q.km_at) < spacing for _, q, _ in picked):
                    continue
                if distinct and any(q.poi.kind == h.poi.kind for _, q, _ in picked):
                    continue
                if h.poi.kind in RELIGIOUS and sum(1 for _, q, _ in picked if q.poi.kind in RELIGIOUS) >= rel_cap:
                    continue
                picked.append((sc, h, note))
        if len(picked) < density:
            stats["gapDays"] += 1
        for sc, h, note in sorted(picked, key=lambda t: t[1].km_at):
            chosen.append({
                "day": d + 1, "kmAt": round(h.km_at), "lateralKm": round(h.lateral_km, 1), "name": h.poi.name,
                "kind": h.poi.kind, "score": sc, "sitelinks": h.poi.sitelinks, "wikidata": h.poi.wikidata,
                "hoursKnown": bool(h.poi.hours), "dog": h.poi.dog, "note": note, "id": h.poi.id,
                "lat": h.poi.lat, "lon": h.poi.lon, "dwellMin": DWELL_MIN.get(h.poi.kind, 45),
            })
    return chosen, stats


def service_gaps(hits: list[Hit], km_total: float, day_ends: list[float]) -> dict[str, int]:
    """Food: 100-km buckets with no named food place within 3 km. Lodging: day ends with < 3 lodgings within
    25 km along and 10 km across."""
    buckets = max(1, math.ceil(km_total / 100))
    food = [0] * buckets
    for h in hits:
        if h.poi.kind == "food" and h.lateral_km <= 3:
            food[min(buckets - 1, int(h.km_at // 100))] += 1
    lodging_gaps = 0
    for end in day_ends:
        n = sum(1 for h in hits if h.poi.kind == "lodging" and abs(h.km_at - end) <= 25 and h.lateral_km <= 10)
        lodging_gaps += n < 3
    return {"foodBuckets": buckets, "foodGaps": sum(1 for x in food if x == 0), "lodgingGaps": lodging_gaps}


def cost_sim(sel: ProviderSelector, country: str, km_total: float, days: int, chosen: list[dict[str, Any]],
             gaps: dict[str, int], gap_days: int) -> dict[str, Any]:
    vendor = sel.would_pick_if_licensed("place_search", country)
    if vendor is None:
        return {"vendor": None}
    hybrid_search = gaps["foodGaps"] + gaps["lodgingGaps"] + 2 * gap_days
    hybrid_details = sum(1 for c in chosen if not c["hoursKnown"]) + 5 * max(0, days - 1)
    only_search = math.ceil(km_total / 20) * 3  # 10-km circles every 20 km x (sights, food, lodging)
    only_details = len(chosen) + 5 * max(0, days - 1) + 10
    rub = lambda m, n: round(sel.call_cost_rub(vendor, m, n), 1)  # noqa: E731
    return {
        "vendor": vendor["id"], "licencePerYearRub": vendor["cost"].get("licencePerYear"),
        "hybrid": {"search": hybrid_search, "details": hybrid_details,
                   "rub": round(rub("search", hybrid_search) + rub("details", hybrid_details), 1)},
        "vendorOnly": {"search": only_search, "details": only_details,
                       "rub": round(rub("search", only_search) + rub("details", only_details), 1)},
    }


def run_case(case: dict[str, Any], index: Index, sel: ProviderSelector, wd_cache: dict[str, int]) -> dict[str, Any]:
    from verst_planner.adapters.graphhopper import GraphHopperRouting, GraphHopperSettings
    from verst_planner.domain.errors import Unreachable
    from verst_planner.domain.model import LatLon, RouteRequest

    country = case["country"]
    profile = case["profile"]
    t: dict[str, float] = {}
    decisions = {cap: [asdict(c) for c in sel.chain(cap, country)] for cap in ("routing", "place_search", "place_details")}
    routing = sel.pick("routing", country)
    gh = GraphHopperRouting(GraphHopperSettings(sel.env[sel.key_name(sel.provider(routing.provider), country)], timeout_s=20))
    pts = [LatLon(*p) for p in case["points"]]

    t0 = time.perf_counter()
    base = gh.route(RouteRequest(tuple(pts), bool(profile.get("avoidTolls"))))
    t["routeMs"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    line = poi_index.simplify([(p.lat, p.lon) for p in base.points])
    radius = max(DETOUR_KM.values()) + 5
    hits = index.corridor(line, radius)
    t["corridorMs"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    need = {h.poi.wikidata for h in hits if h.poi.wikidata and h.poi.wikidata not in wd_cache}
    got, failed = wikidata.sitelinks(need) if need else ({}, 0)
    wd_cache.update(got)
    for h in hits:
        if h.poi.wikidata:
            h.poi.sitelinks = wd_cache.get(h.poi.wikidata, 0)
    t["wikidataMs"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    chosen, stats = choose(hits, profile, base.km_total)
    t["chooseMs"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    via = [LatLon(c["lat"], c["lon"]) for c in chosen]
    fixed = [LatLon(*p) for p in case["points"]]
    # keep the case's own vias (e.g. Убуд) in order: insert chosen stops between them by position along the route
    seq = [fixed[0]] + sorted(via + fixed[1:-1], key=lambda p: _km_along(line, (p.lat, p.lon))) + [fixed[-1]]
    dropped: list[str] = []
    try:
        final = gh.route(RouteRequest(tuple(seq), bool(profile.get("avoidTolls"))))
    except Unreachable:
        # a stop off the road network (a summit, an island): drop the stops a car cannot reach, keep the rest
        keep = []
        for c in chosen:
            here = LatLon(c["lat"], c["lon"])
            try:
                gh.route(RouteRequest((here, fixed[-1]), False))
                keep.append(c)
            except Unreachable:
                dropped.append(c["name"])
        chosen[:] = keep
        via = [LatLon(c["lat"], c["lon"]) for c in chosen]
        seq = [fixed[0]] + sorted(via + fixed[1:-1], key=lambda p: _km_along(line, (p.lat, p.lon))) + [fixed[-1]]
        final = gh.route(RouteRequest(tuple(seq), bool(profile.get("avoidTolls"))))
    t["rerouteMs"] = (time.perf_counter() - t0) * 1000

    per_day = base.km_total / stats["days"]
    gaps = service_gaps(hits, base.km_total, [per_day * (d + 1) for d in range(stats["days"] - 1)])
    kinds: dict[str, int] = {}
    for h in hits:
        kinds[h.poi.kind] = kinds.get(h.poi.kind, 0) + 1
    sights = [c for c in chosen]
    return {
        "id": case["id"], "title": case["title"], "country": country, "profile": profile,
        "providers": decisions,
        "baseKm": round(base.km_total, 1), "baseMin": round(base.min_total),
        "finalKm": round(final.km_total, 1), "finalMin": round(final.min_total),
        "detourKm": round(final.km_total - base.km_total, 1),
        "dwellMin": sum(c["dwellMin"] for c in sights),
        "candidates": len(hits), "candidatesByKind": dict(sorted(kinds.items(), key=lambda kv: -kv[1])),
        "wikidataFailed": failed, "droppedUnreachable": dropped,
        "stops": chosen, "selection": stats, "serviceGaps": gaps,
        "hoursKnownShare": round(sum(c["hoursKnown"] for c in chosen) / len(chosen), 2) if chosen else None,
        "notableShare": round(sum(c["sitelinks"] >= 5 for c in chosen) / len(chosen), 2) if chosen else None,
        "cost": cost_sim(sel, country, base.km_total, stats["days"], chosen, gaps, stats["gapDays"]),
        "timingsMs": {k: round(v) for k, v in t.items()},
        "serverPlanMs": round(t["routeMs"] + t["corridorMs"] + t["chooseMs"] + t["rerouteMs"]),
    }


def _km_along(line: list[tuple[float, float]], p: tuple[float, float]) -> float:
    best, at, acc = float("inf"), 0.0, 0.0
    for a, b in zip(line, line[1:]):
        d = math.hypot((p[0] - a[0]) * 111.32, (p[1] - a[1]) * 111.32 * math.cos(math.radians(a[0])))
        if d < best:
            best, at = d, acc
        acc += math.hypot((b[0] - a[0]) * 111.32, (b[1] - a[1]) * 111.32 * math.cos(math.radians(a[0])))
    return at


def baseline(case: dict[str, Any], url: str) -> dict[str, Any]:
    """Today's engine on `russia_v1` with GraphHopper (as infra/routing/check_routes.py): its sight stops."""
    from verst_planner import mobile
    from verst_planner.adapters.catalogue import build_catalogue_ports, compose
    from verst_planner.adapters.fake import FakeWorld
    from verst_planner.adapters.graphhopper import GraphHopperRouting, GraphHopperSettings
    from verst_planner.catalogue import load_packaged
    from verst_planner.config import PlannerConfig
    from verst_planner.domain import codec
    from verst_planner.engine import Planner
    from verst_planner.explain.templates import ReasonTemplates

    planner_dir = REPO / "backend" / "planner"
    world = FakeWorld.load(planner_dir / "fixtures" / "worlds" / "central_russia_v1.json")
    ports = build_catalogue_ports(compose(world, load_packaged()))
    planner = Planner(
        routing=GraphHopperRouting(GraphHopperSettings(url, timeout_s=20)), places=ports.places, prices=ports.prices,
        tolls=ports.tolls, regions=ports.regions, geocoding=ports.geocoding, clock=ports.clock,
        config=PlannerConfig.from_dict(mobile.OPEN_DATA_CONFIG), templates=ReasonTemplates.default(),
        parking=ports.parking,
    )
    p = case["profile"]
    a, b = case["points"][0], case["points"][-1]
    inp = {
        "origin": {"lat": a[0], "lon": a[1], "label": "A"}, "destination": {"lat": b[0], "lon": b[1], "label": "B"},
        "crew": {"adults": p["crew"]["adults"], "children": len(p["crew"].get("children") or []),
                 "dog": bool(p["crew"].get("pets"))},
        "dailyKm": p["dailyKm"], "startAt": "2026-11-07T08:00",
    }
    t0 = time.perf_counter()
    plan = codec.plan_to_json(planner.plan(codec.input_from_json(inp)))
    ms = (time.perf_counter() - t0) * 1000
    stops = [
        {"day": s["day"], "kmAt": s.get("kmAt"), "name": s["name"], "tags": s.get("tags", []), "verified": s.get("verified")}
        for d in plan["daysList"] for s in d["stops"] if s.get("kind") == "sight"
    ]
    return {"km": plan["km"], "days": plan["days"], "planMs": round(ms), "stops": stops}


def report_md(results: list[dict[str, Any]]) -> str:
    out = ["# SPIKE-01: dynamic planning prototype", ""]
    out.append("| Case | km (base → with stops) | days | candidates | stops | notable ≥ 5 sitelinks | hours known "
               "| server plan ms | commercial cost, hybrid / vendor only |")
    out.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for r in results:
        c = r["cost"]
        cost = "—" if not c.get("vendor") else f"{c['hybrid']['rub']} ₽ / {c['vendorOnly']['rub']} ₽ ({c['vendor']}" + (
            f"; + licence {c['licencePerYearRub']} ₽/yr)" if c.get("licencePerYearRub") else ")")
        out.append(
            f"| {r['title']} | {r['baseKm']} → {r['finalKm']} | {r['selection']['days']} | {r['candidates']} "
            f"| {len(r['stops'])} | {r['notableShare']} | {r['hoursKnownShare']} | {r['serverPlanMs']} | {cost} |"
        )
    for r in results:
        out += ["", f"## {r['title']}", ""]
        out.append(f"Providers chosen: routing `{r['providers']['routing'][0]['provider']}`; place search "
                   + ", ".join(f"`{c['provider']}` ({c['reason']})" for c in r["providers"]["place_search"]))
        out.append("")
        out.append(f"Timings, ms: {r['timingsMs']} · Wikidata failures: {r['wikidataFailed']} · "
                   f"detour {r['detourKm']} km · dwell {r['dwellMin']} min · gaps {r['serviceGaps']} · "
                   f"selection {r['selection']}")
        out.append("")
        out.append(f"Candidates by kind: {r['candidatesByKind']}")
        out += ["", "| Day | km | Stop | Kind | Sitelinks | Hours | Dog | Note | Rating 1–5 (A) | Rating 1–5 (B) |",
                "| ---: | ---: | --- | --- | ---: | --- | --- | --- | --- | --- |"]
        for s in r["stops"]:
            out.append(f"| {s['day']} | {s['kmAt']} | {s['name']} | {s['kind']} | {s['sitelinks']} | "
                       f"{'yes' if s['hoursKnown'] else 'не проверено'} | {s['dog'] or '—'} | {s['note'] or ''} |  |  |")
        if r.get("baseline"):
            b = r["baseline"]
            out += ["", f"**Today's engine** (packaged catalogue, same crew): {b['km']} km, {b['days']} days, "
                        f"{b['planMs']} ms, {len(b['stops'])} sights", "",
                    "| Day | km | Sight | Tags | Rating 1–5 (A) | Rating 1–5 (B) |", "| ---: | ---: | --- | --- | --- | --- |"]
            for s in b["stops"]:
                out.append(f"| {s['day']} | {s['kmAt']} | {s['name']} | {', '.join(s['tags'][:4])} |  |  |")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=Path, default=HERE / "cases.json")
    ap.add_argument("--providers", type=Path, default=HERE / "providers.json")
    ap.add_argument("--index", action="append", default=[], help="COUNTRY=path.jsonl")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--baseline", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    sel = ProviderSelector.load(args.providers)
    indexes = {k: Index(poi_index.load(Path(v))) for k, v in (s.split("=", 1) for s in args.index)}
    wd_cache: dict[str, int] = {}
    results = []
    for case in json.loads(args.cases.read_text(encoding="utf-8"))["cases"]:
        if case["country"] not in indexes:
            continue
        r = run_case(case, indexes[case["country"]], sel, wd_cache)
        if args.baseline and case["country"] == "RU":
            r["baseline"] = baseline(case, os.environ["SPIKE_GH_URL_RU"])
        results.append(r)
        print(f"{case['id']}: {r['baseKm']} km, {len(r['stops'])} stops, {r['serverPlanMs']} ms, cost {r['cost']}")
    (args.out / "report.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    md = report_md(results)
    (args.out / "report.md").write_text(md, encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
