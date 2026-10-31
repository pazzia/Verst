#!/usr/bin/env bash
# Publish one CI run's diagnostics to the `ci-logs` branch (docs/architecture-android-mvp.md §12.3).
#
#   publish_ci_logs.sh <run-name> <source-dir>
#
# The branch is a single orphan commit, force-pushed with a lease, so it never grows history:
#   README.md · index.json (newest first, ≤ KEEP_RUNS) · LATEST · runs/<run-name>/…
# PNG files are kept only for the newest KEEP_PNG_RUNS runs. Concurrent publishers are safe:
# a lost lease re-fetches and retries (5 attempts).
#
# Env: GITHUB_TOKEN, GITHUB_REPOSITORY (required unless CI_LOGS_REMOTE is set, used by tests); KEEP_RUNS (30), KEEP_PNG_RUNS (3),
#      CI_LOGS_BRANCH (ci-logs), RUN_META_JSON (optional JSON merged into the index entry).
set -euo pipefail

RUN_NAME=${1:?run name}
SRC=$(cd "${2:?source dir}" && pwd)
BRANCH=${CI_LOGS_BRANCH:-ci-logs}
KEEP_RUNS=${KEEP_RUNS:-30}
KEEP_PNG_RUNS=${KEEP_PNG_RUNS:-3}
REMOTE=${CI_LOGS_REMOTE:-"https://x-access-token:${GITHUB_TOKEN:?}@github.com/${GITHUB_REPOSITORY:?}.git"}
HERE=$(cd "$(dirname "$0")" && pwd)

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
git -C "$WORK" init -q
git -C "$WORK" config user.name "verst-ci"
git -C "$WORK" config user.email "verst-ci@users.noreply.github.com"

for attempt in 1 2 3 4 5; do
  TREE="$WORK/tree"
  rm -rf "$TREE" && mkdir -p "$TREE"
  OLD=""
  if git -C "$WORK" fetch -q --depth=1 "$REMOTE" "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH" 2>/dev/null; then
    OLD=$(git -C "$WORK" rev-parse "refs/remotes/origin/$BRANCH")
    git -C "$WORK" archive "$OLD" | tar -x -C "$TREE"
  fi

  rm -rf "$TREE/runs/$RUN_NAME"
  mkdir -p "$TREE/runs/$RUN_NAME"
  cp -R "$SRC/." "$TREE/runs/$RUN_NAME/"

  python3 "$HERE/ci_logs_index.py" "$TREE" "$RUN_NAME" "$KEEP_RUNS" "$KEEP_PNG_RUNS"

  export GIT_INDEX_FILE="$WORK/index"
  rm -f "$GIT_INDEX_FILE"
  git -C "$WORK" --work-tree="$TREE" add -A .
  TREE_SHA=$(git -C "$WORK" write-tree)
  unset GIT_INDEX_FILE
  COMMIT=$(git -C "$WORK" commit-tree "$TREE_SHA" -m "ci-logs: $RUN_NAME (${GITHUB_SHA:-local})")

  if git -C "$WORK" push -q --force-with-lease="refs/heads/$BRANCH:$OLD" "$REMOTE" "$COMMIT:refs/heads/$BRANCH"; then
    echo "published runs/$RUN_NAME to $BRANCH as $COMMIT (attempt $attempt)"
    exit 0
  fi
  echo "lease lost or push failed (attempt $attempt), retrying" >&2
  sleep $(( attempt * 3 + RANDOM % 5 ))
done
echo "::warning title=ci-logs::could not publish runs/$RUN_NAME after 5 attempts"
exit 1
