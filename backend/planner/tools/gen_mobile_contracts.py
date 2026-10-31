"""Writes the Kotlin `TripEditor` / `CostCalculator` contracts (DEV-112) from the golden trips.

One gzip bundle per golden case with a snapshot; the trip before the edit is stored once per bundle:

- `docs/contracts/replace/<case>.json.gz` = `{"case", "before": public trip, "items": [{"stopId", "altId",
  "afterDay", "afterCost", "afterKm"}]}` — one item for every alternative of every stop. `afterDay` is the day
  (an element of `daysList`) that holds the stop after `replace_stop`, `afterCost` the new `cost`, `afterKm`
  the new trip `km`. The generator asserts that nothing else changes: `before` with that day, cost and km
  replaced equals the full trip `replace_stop` returns.
- `docs/contracts/patch/<case>.json.gz` = `{"case", "before", "items": [{"kind", "patch", "afterCost",
  "afterInput", "afterHotel"}]}` for reserve off (`reserve_off`), budget «не важно» (`budget_none`) and a hotel
  choice for every night with ≥ 2 options (`hotel_<stopId>`, the first option that is not selected).
  `afterHotel` is null or `{"stopId", "placeId", "selectedHotelId", "costRub", "tags"}` (the changed fields of
  that overnight stop). Asserted the same way: `before` + these parts == the trip `recompute_cost` returns.
- Both kinds carry `afterFlags` = `[{"stopId", "altId", "breaksBudget"}]` only when the edit re-flags an
  alternative elsewhere in the trip (ADR-0011 flags trip-wide; it happens when the edit moves the total
  across the budget tolerance, e.g. G13 after ADR-0019). The app takes those flags from the engine's answer.

The generator also asserts ≤ `MAX_ALTERNATIVES` (3) alternatives per stop and that `before` is the golden
snapshot. Files are compact JSON + newline, gzipped deterministically (`GzipFile(filename="", mtime=0)`,
level 9). Run from `backend/planner`: ``python3 tools/gen_mobile_contracts.py``. With
``VERST_GEN_IN_MEMORY=1`` nothing is written and `GENERATED` (relative path → uncompressed text) holds the
output (the test compares it with the decompressed committed files, A§16.10).
"""

import copy
import gzip
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.golden.test_golden import CASES, SNAPSHOTS, load_case, run_case, snapshot_text, world  # noqa: E402
from tests.helpers import make_planner  # noqa: E402
from verst_planner.domain import codec  # noqa: E402
from verst_planner.domain.model import CostPatch  # noqa: E402

OUT = ROOT.parents[1] / "docs" / "contracts"
GENERATED = {}
MAX_ALTERNATIVES = 3
HOTEL_FIELDS = ("placeId", "selectedHotelId", "costRub", "tags")


def public(plan):
    return codec.plan_to_json(plan, trip_id="trp_golden")


def text(doc):
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n"


def gz(body):
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, compresslevel=9, mtime=0) as f:
        f.write(body.encode("utf-8"))
    return buf.getvalue()


def day_index(trip, stop_id):
    return next(i for i, d in enumerate(trip["daysList"]) if any(s["id"] == stop_id for s in d["stops"]))


def flags(trip, skip_day):
    """`breaksBudget` of every alternative outside day index `skip_day`: {(stopId, altId): flag}."""
    return {
        (s["id"], a["id"]): bool(a.get("breaksBudget", False))
        for i, d in enumerate(trip["daysList"])
        if i != skip_day
        for s in d["stops"]
        for a in s["alternatives"]
    }


def changed_flags(before, after, skip_day=None):
    old, new = flags(before, skip_day), flags(after, skip_day)
    return [
        {"stopId": sid, "altId": aid, "breaksBudget": new[(sid, aid)]}
        for sid, aid in old
        if new[(sid, aid)] != old[(sid, aid)]
    ]


def apply_flags(out, item):
    """ADR-0011 re-flags `breaksBudget` trip-wide after an edit; `afterFlags` lists the flips (rare: only when
    the edit moves the total across the budget tolerance), so `before` + the parts still equals the trip."""
    for f in item.get("afterFlags", []):
        for d in out["daysList"]:
            for s in d["stops"]:
                for a in s["alternatives"] if s["id"] == f["stopId"] else ():
                    if a["id"] == f["altId"]:
                        a.pop("breaksBudget", None)
                        if f["breaksBudget"]:
                            a["breaksBudget"] = True
    return out


def apply_replace(before, item):
    out = copy.deepcopy(before)
    out["daysList"][day_index(before, item["stopId"])] = item["afterDay"]
    out["cost"] = item["afterCost"]
    out["km"] = item["afterKm"]
    return apply_flags(out, item)


def apply_patch(before, item):
    out = copy.deepcopy(before)
    out["cost"] = item["afterCost"]
    out["input"] = item["afterInput"]
    hotel = item["afterHotel"]
    if hotel is not None:
        stop = next(s for d in out["daysList"] for s in d["stops"] if s["id"] == hotel["stopId"])
        stop.update({k: hotel[k] for k in HOTEL_FIELDS})
    return apply_flags(out, item)


for path in sorted(CASES.glob("G*.json")):
    case = load_case(path)
    snap = SNAPSHOTS / f"{case['id']}_{case['slug']}.json"
    if not snap.exists():
        continue
    cid = case["id"]
    plan, _sink, _routing, _replan = run_case(case)
    planner, _ = make_planner(case["world"])
    assert snapshot_text(plan) == snap.read_text("utf-8"), cid
    before = public(plan)

    items = []
    for d in plan.days_list:
        for s in d.stops:
            assert len(s.alternatives) <= MAX_ALTERNATIVES, (cid, s.id, len(s.alternatives))
            for a in s.alternatives:
                after = public(planner.replace_stop(plan, s.id, a.id))
                item = {
                    "stopId": s.id,
                    "altId": a.id,
                    "afterDay": after["daysList"][day_index(before, s.id)],
                    "afterCost": after["cost"],
                    "afterKm": after["km"],
                }
                changed = changed_flags(before, after, day_index(before, s.id))
                if changed:  # only when the replace moves the total across the budget tolerance
                    item["afterFlags"] = changed
                assert apply_replace(before, item) == after, (cid, s.id, a.id, "other parts changed")
                items.append(item)
    GENERATED[f"replace/{cid}.json.gz"] = text({"case": cid, "before": before, "items": items})

    patches = [("reserve_off", CostPatch(reserve_on=False), {"reserveOn": False}, None)]
    patches.append(("budget_none", CostPatch(budget_rub=None), {"budget": None}, None))
    for d in plan.days_list:
        for s in d.stops:
            others = [h for h in s.hotel_options if h.place_id != s.selected_hotel_id]
            if len(s.hotel_options) >= 2 and others:
                hc = (s.id, others[0].place_id)
                patch_json = {"hotelChoice": {"stopId": hc[0], "placeId": hc[1]}}
                patches.append((f"hotel_{s.id}", CostPatch(hotel_choice=hc), patch_json, s.id))
    items = []
    for kind, patch, patch_json, stop_id in patches:
        after = public(planner.recompute_cost(plan, patch))
        hotel = None
        if stop_id is not None:
            stop = next(x for d in after["daysList"] for x in d["stops"] if x["id"] == stop_id)
            hotel = {"stopId": stop_id, **{k: stop[k] for k in HOTEL_FIELDS}}
        item = {
            "kind": kind,
            "patch": patch_json,
            "afterCost": after["cost"],
            "afterInput": after["input"],
            "afterHotel": hotel,
        }
        changed = changed_flags(before, after)
        if changed:
            item["afterFlags"] = changed
        assert apply_patch(before, item) == after, (cid, kind, "other parts changed")
        items.append(item)
    GENERATED[f"patch/{cid}.json.gz"] = text({"case": cid, "before": before, "items": items})

assert world  # the shared world cache of the golden runner is reused

if not os.environ.get("VERST_GEN_IN_MEMORY"):
    for sub in ("replace", "patch"):
        d = OUT / sub
        d.mkdir(parents=True, exist_ok=True)
        for old in d.iterdir():
            if f"{sub}/{old.name}" not in GENERATED:
                old.unlink()
    for rel, body in GENERATED.items():
        (OUT / rel).write_bytes(gz(body))
    n_items = {k: len(json.loads(v)["items"]) for k, v in GENERATED.items()}
    n_replace = sum(v for k, v in n_items.items() if k.startswith("replace/"))
    print(
        f"{len(GENERATED)} bundles: {n_replace} replace items, {sum(n_items.values()) - n_replace} patch items"
    )
