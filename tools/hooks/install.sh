#!/usr/bin/env bash
# Installs the commit guard as this clone's git pre-commit hook (once per clone).
set -euo pipefail
root=$(git rev-parse --show-toplevel)
hook="$root/.git/hooks/pre-commit"
printf '#!/bin/sh\nexec python3 "%s/tools/hooks/guard_commit.py"\n' "$root" > "$hook"
chmod +x "$hook"
echo "pre-commit guard installed: $hook"
