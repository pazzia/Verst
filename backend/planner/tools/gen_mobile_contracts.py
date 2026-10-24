"""Writes the Kotlin `TripEditor` / `CostCalculator` contracts (DEV-112) from the golden trips.

- `docs/contracts/replace/<case>__<stopId>__<altId>.json`: for every alternative of every golden trip with a
  snapshot, `{"case", "stopId", "altId", "before": public trip, "after": public trip after replace_stop}`.
- `docs/contracts/patch/<case>__<kind>.json`: `{"case", "kind", "patch", "before", "after"}` for reserve off
  (`reserve_off`), budget «не важно» (`budget_none`) and a hotel choice for every night with ≥ 2 options
  (`hotel_<stopId>`, the first option that is not selected).

Run from `backend/planner`: ``python3 tools/gen_mobile_contracts.py``. With ``VERST_GEN_IN_MEMORY=1`` nothing
is written and `GENERATED` (relative path → text) holds the output (byte-for-byte test, A§16.10).
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.golden.test_golden import CASES, SNAPSHOTS, load_case, run_case, world  # noqa: E402
from tests.helpers import make_planner  # noqa: E402
from verst_planner.domain import codec  # noqa: E402
from verst_planner.domain.model import CostPatch  # noqa: E402

OUT = ROOT.parents[1] / "docs" / "contracts"
GENERATED = {}


def public(plan):
    return codec.plan_to_json(plan, trip_id="trp_golden")


def text(doc):
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n"


def emit(rel, doc):
    GENERATED[rel] = text(doc)


for path in sorted(CASES.glob("G*.json")):
    case = load_case(path)
    if not (SNAPSHOTS / f"{case['id']}_{case['slug']}.json").exists():
        continue
    cid = case["id"]
    plan, _sink, _routing, _replan = run_case(case)
    planner, _ = make_planner(case["world"])
    before = public(plan)
    for d in plan.days_list:
        for s in d.stops:
            for a in s.alternatives:
                after = public(planner.replace_stop(plan, s.id, a.id))
                emit(
                    f"replace/{cid}__{s.id}__{a.id}.json",
                    {"case": cid, "stopId": s.id, "altId": a.id, "before": before, "after": after},
                )
    patches = [("reserve_off", CostPatch(reserve_on=False), {"reserveOn": False})]
    patches.append(("budget_none", CostPatch(budget_rub=None), {"budget": None}))
    for d in plan.days_list:
        for s in d.stops:
            others = [h for h in s.hotel_options if h.place_id != s.selected_hotel_id]
            if len(s.hotel_options) >= 2 and others:
                hc = (s.id, others[0].place_id)
                patches.append(
                    (
                        f"hotel_{s.id}",
                        CostPatch(hotel_choice=hc),
                        {"hotelChoice": {"stopId": hc[0], "placeId": hc[1]}},
                    )
                )
    for kind, patch, patch_json in patches:
        after = public(planner.recompute_cost(plan, patch))
        emit(
            f"patch/{cid}__{kind}.json",
            {"case": cid, "kind": kind, "patch": patch_json, "before": before, "after": after},
        )

assert world  # the shared world cache of the golden runner is reused

if not os.environ.get("VERST_GEN_IN_MEMORY"):
    for sub in ("replace", "patch"):
        d = OUT / sub
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.json"):
            if f"{sub}/{old.name}" not in GENERATED:
                old.unlink()
    for rel, body in GENERATED.items():
        (OUT / rel).write_text(body, encoding="utf-8")
    n_replace = sum(1 for k in GENERATED if k.startswith("replace/"))
    print(f"{n_replace} replace, {len(GENERATED) - n_replace} patch contracts")
