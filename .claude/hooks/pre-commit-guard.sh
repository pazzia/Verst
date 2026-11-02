#!/usr/bin/env bash
# Claude Code PreToolUse hook (Bash): before a `git commit`, run the commit guard on everything that may be
# committed (staged, changed, untracked: `git add -A && git commit` stages in the same command).
# Exit 2 blocks the tool call and shows the reasons to the model; anything else lets it run.
root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cmd=$(python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("tool_input",{}).get("command",""))
except Exception: print("")' 2>/dev/null)
if printf '%s' "$cmd" | grep -Eq '(^|[;&|[:space:]])git([[:space:]]+-C[[:space:]]+[^[:space:]]+)?[[:space:]]+commit\b'; then
  python3 "$root/tools/hooks/guard_commit.py" --worktree || exit 2
fi
exit 0
