#!/usr/bin/env bash
# Sandbox helper: status of the newest `android` workflow run for a commit, its annotations and its ci-logs.
#
#   tools/ci/ci_status.sh [<sha-or-branch>] [--wait]
#
# Prints: run id/number/conclusion, every job with failed steps, all check-run annotations, then
# runs/<run>-<attempt>/summary.md from the ci-logs branch. With --wait, polls every 30 s until the
# run completes (max 60 min). Exit code: 0 success, 1 failure, 2 not found / still running.
set -uo pipefail
REPO=${REPO:-pazzia/Verst}
REF=${1:-HEAD}
WAIT=${2:-}
SHA=$(git rev-parse "$REF" 2>/dev/null || echo "$REF")

find_run() {
  gh api "repos/$REPO/actions/runs?head_sha=$SHA&per_page=20" \
    --jq '[.workflow_runs[] | select(.name=="android")] | sort_by(.run_attempt) | last | select(.) | "\(.id) \(.run_attempt) \(.run_number) \(.status) \(.conclusion)"'
}

LINE=$(find_run)
if [ -z "$LINE" ]; then echo "no android run for $SHA"; exit 2; fi
read -r ID ATTEMPT NUM STATUS CONCL <<<"$LINE"
DEADLINE=$(( $(date +%s) + 3600 ))
while [ "$WAIT" = "--wait" ] && [ "$STATUS" != "completed" ] && [ "$(date +%s)" -lt "$DEADLINE" ]; do
  echo "run $NUM ($ID) $STATUS …"; sleep 30
  read -r ID ATTEMPT NUM STATUS CONCL <<<"$(find_run)"
done
echo "run $NUM id=$ID attempt=$ATTEMPT status=$STATUS conclusion=$CONCL sha=${SHA:0:12}"

gh api "repos/$REPO/actions/runs/$ID/attempts/$ATTEMPT/jobs" \
  --jq '.jobs[] | "\(.name): \(.conclusion // .status)  \([.steps[]? | select(.conclusion=="failure") | .name] | join(", "))"'

for JOB in $(gh api "repos/$REPO/actions/runs/$ID/attempts/$ATTEMPT/jobs" --jq '.jobs[].id'); do
  gh api "repos/$REPO/check-runs/$JOB/annotations" \
    --jq '.[] | "[\(.annotation_level)] \(.path):\(.start_line) \(.title // "")\n    \(.message | gsub("\n"; "\n    "))"' 2>/dev/null
done

if git fetch -q origin +ci-logs:refs/remotes/origin/ci-logs --depth=1 2>/dev/null; then
  git show "origin/ci-logs:runs/$ID-$ATTEMPT/summary.md" 2>/dev/null || echo "ci-logs: runs/$ID-$ATTEMPT not published (yet)"
else
  echo "ci-logs branch not found"
fi

[ "$STATUS" = "completed" ] || exit 2
[ "$CONCL" = "success" ] && exit 0 || exit 1
