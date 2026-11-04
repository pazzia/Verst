# ci-logs — Verst Android CI diagnostics (generated, do not edit)

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
Retention: newest 30 runs; PNGs only in the newest 3 runs.
