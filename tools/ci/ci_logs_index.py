#!/usr/bin/env python3
"""Maintain index.json, LATEST, README.md and retention on the ci-logs tree (called by publish_ci_logs.sh).

    ci_logs_index.py <tree> <run-name> <keep-runs> <keep-png-runs>

Run names are ``<run_id>-<attempt>``; ordering is numeric on (run_id, attempt), newest first.
``RUN_META_JSON`` (env, optional) is merged into the new run's index entry.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

README = """# ci-logs — Verst Android CI diagnostics (generated, do not edit)

Single orphan commit, force-pushed by `.github/workflows/android.yml` (job `ci-logs`).
Read from the sandbox without Actions log access:

    git fetch origin +ci-logs:refs/remotes/origin/ci-logs --depth=1
    git show origin/ci-logs:LATEST
    git show origin/ci-logs:runs/$(git show origin/ci-logs:LATEST)/summary.md
    mkdir -p /tmp/ci && git archive origin/ci-logs runs/<run> | tar -x -C /tmp/ci   # PNGs

Layout of runs/<run_id>-<attempt>/: summary.json/.md (whole run), errors.txt (all extracted errors),
planner/ (unittest.log, errors.txt), build/ e2e/ release/ (per-job diagnostics: logs/*.log.txt trimmed,
tests/, lint/, apk.json),
screenshots/<screen>/<state>@<w>x<h>.png (Robolectric), e2e/screens/*.png (emulator).
Retention: newest {keep} runs; PNGs only in the newest {keep_png} runs.
"""


def key(name: str) -> tuple[int, int]:
    run, _, attempt = name.partition("-")
    try:
        return int(run), int(attempt or 0)
    except ValueError:
        return 0, 0


def main() -> int:
    tree, run_name, keep, keep_png = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    runs_dir = tree / "runs"
    names = sorted((p.name for p in runs_dir.iterdir() if p.is_dir()), key=key, reverse=True)
    for old in names[keep:]:
        shutil.rmtree(runs_dir / old)
    names = names[:keep]
    for name in names[keep_png:]:
        for png in (runs_dir / name).rglob("*.png"):
            png.unlink()

    index_path = tree / "index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        index = {"schema": 1, "runs": []}
    entries = {e["name"]: e for e in index.get("runs", []) if e.get("name") in names}
    entry = {"name": run_name, "publishedAt": datetime.now(UTC).isoformat(timespec="seconds"),
             "sha": os.environ.get("GITHUB_SHA"), "ref": os.environ.get("GITHUB_REF"),
             "event": os.environ.get("GITHUB_EVENT_NAME")}
    meta = os.environ.get("RUN_META_JSON")
    if meta:
        try:
            entry.update(json.loads(meta))
        except json.JSONDecodeError:
            entry["metaError"] = meta[:500]
    entries[run_name] = entry
    index["runs"] = [entries[n] for n in names if n in entries]
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    newest = names[0] if names else run_name
    (tree / "LATEST").write_text(newest + "\n", encoding="utf-8")
    (tree / "README.md").write_text(README.format(keep=keep, keep_png=keep_png), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
