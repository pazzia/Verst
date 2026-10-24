#!/usr/bin/env python3
"""Merge per-job diagnostics into one run directory for the ci-logs branch.

    combine_run.py <run-dir>

Expects <run-dir>/{build,e2e,release}/summary.json (any may be missing) and env:
  NEEDS_JSON   toJSON(needs) of the ci-logs job (job results)
  GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT, GITHUB_RUN_NUMBER, GITHUB_SHA, GITHUB_REF, GITHUB_EVENT_NAME
  HEAD_COMMIT_MESSAGE (optional)
Writes <run-dir>/summary.json, summary.md, errors.txt and prints RUN_META_JSON for the index.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

JOBS = ("build", "e2e", "release")


def main() -> int:
    run = Path(sys.argv[1])
    try:
        needs = json.loads(os.environ.get("NEEDS_JSON") or "{}")
    except json.JSONDecodeError:
        needs = {}
    results = {j: (needs.get(j) or {}).get("result", "absent") for j in JOBS}
    jobs: dict[str, object] = {}
    errors: list[str] = []
    for j in JOBS:
        p = run / j / "summary.json"
        if p.exists():
            jobs[j] = json.loads(p.read_text(encoding="utf-8")).get("sections", {})
        e = run / j / "errors.txt"
        if e.exists():
            errors += e.read_text(encoding="utf-8").splitlines()
    pngs = sorted(str(p.relative_to(run)) for p in run.rglob("*.png"))
    conclusion = "success" if results["build"] == "success" and results["e2e"] in ("success", "skipped") else (
        "failure" if "failure" in results.values() else "incomplete")
    summary = {
        "schema": 1,
        "run": {"id": os.environ.get("GITHUB_RUN_ID"), "attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
                "number": os.environ.get("GITHUB_RUN_NUMBER"), "sha": os.environ.get("GITHUB_SHA"),
                "ref": os.environ.get("GITHUB_REF"), "event": os.environ.get("GITHUB_EVENT_NAME"),
                "commitMessage": (os.environ.get("HEAD_COMMIT_MESSAGE") or "").splitlines()[:1]},
        "conclusion": conclusion,
        "jobs": results,
        "details": jobs,
        "errorCount": len(errors),
        "screenshots": pngs,
    }
    (run / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run / "errors.txt").write_text("\n".join(errors) + ("\n" if errors else "no errors extracted\n"),
                                    encoding="utf-8")
    md = [f"# Run {summary['run']['number']} ({summary['run']['id']}-{summary['run']['attempt']}) — {conclusion}",
          "", f"sha `{str(summary['run']['sha'])[:12]}` · {summary['run']['ref']} · {summary['run']['event']}", "",
          "| job | result |", "| --- | --- |", *[f"| {j} | {r} |" for j, r in results.items()], ""]
    apk = (jobs.get("build") or {}).get("apk") if isinstance(jobs.get("build"), dict) else None
    if isinstance(apk, dict):
        md.append(f"APK: {apk.get('mb')} MB · ABIs {apk.get('abis')} · sha256 {str(apk.get('sha256'))[:16]}…")
    md += ["", f"Screenshots: {len(pngs)}", "", "## Errors (first 60)", "```", *errors[:60], "```"]
    (run / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"conclusion": conclusion, "jobs": results, "number": summary["run"]["number"],
                      "errors": len(errors), "screenshots": len(pngs)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
