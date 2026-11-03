#!/usr/bin/env bash
# Claude Code SessionStart hook (startup, resume, clear, compact): the checkpoint first, so a new or compacted
# session picks up where the last one stopped (CLAUDE.md «Read first»). Prints only; never fails the session.
root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$root" 2>/dev/null || exit 0
echo "=== «Верста»: session context ==="
echo "Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null) · HEAD $(git log -1 --format='%h %s' 2>/dev/null | cut -c1-100)"
dirty=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
[ "$dirty" != "0" ] && echo "Uncommitted files: $dirty"
if [ -f docs/SESSION-STATE.md ]; then
  echo
  echo "--- docs/SESSION-STATE.md (checkpoint; update it at the end of every task) ---"
  head -n 80 docs/SESSION-STATE.md
fi
exit 0
