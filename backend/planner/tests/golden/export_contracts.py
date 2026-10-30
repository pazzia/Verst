"""Generate the cross-platform contracts from the golden trips (A§13.2, DEV-018).

Run from `backend/planner`: ``python3 -m tests.golden.export_contracts``. Writes
``docs/contracts/plan-response.example.json`` (G02) and ``docs/contracts/share-text/G01…G08.json``
(``{"plan": …, "text": …}``) used by the Kotlin `ShareTextBuilder` tests. Output is deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.golden.test_golden import CASES, load_case, run_case
from verst_planner.domain import codec
from verst_planner.explain.share import share_text

REPO = Path(__file__).resolve().parents[4]
CONTRACTS = REPO / "docs" / "contracts"
SHARE_CASES = ("G01", "G02", "G03", "G04", "G05", "G06", "G07", "G08")


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    for path in sorted(CASES.glob("G*.json")):
        case = load_case(path)
        if case["id"] not in SHARE_CASES:
            continue
        plan, _sink, _routing, _replan = run_case(case)
        public = codec.plan_to_json(plan, trip_id="trp_golden")
        if case["id"] == "G02":
            _write(CONTRACTS / "plan-response.example.json", public)
        _write(CONTRACTS / "share-text" / f"{case['id']}.json", {"plan": public, "text": share_text(plan)})
        print(f"{case['id']}: {plan.title_ru}")


if __name__ == "__main__":
    main()
