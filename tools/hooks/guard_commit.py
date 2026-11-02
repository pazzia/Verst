#!/usr/bin/env python3
"""Commit guard (CEO 02.11, CLAUDE.md «Never commit …»): blocks a commit that would add a secret, broken JSON or
out-of-sync generated files. Runs as a git pre-commit hook (`tools/hooks/install.sh`) and as the Claude Code
PreToolUse hook on `git commit` (`.claude/hooks/pre-commit-guard.sh`).

    python3 tools/hooks/guard_commit.py              # staged files (git pre-commit)
    python3 tools/hooks/guard_commit.py --worktree   # staged + changed + untracked (before `git add -A && git commit`)

Exit 0 = fine, 1 = blocked (the reasons on stderr). Standard library only.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Files that must never be committed (the server .env, signing material, local SDK paths).
FORBIDDEN_NAME = re.compile(
    r"(^|/)(\.env(\.[^/]*)?|local\.properties|google-services\.json)$|\.(jks|keystore|p12|pfx|pem|key)$"
)
ALLOWED_NAME = re.compile(r"(^|/)\.env\.example$")

# Secret values in added lines. An empty value (`VERST_TP_TOKEN=`) or a placeholder is fine.
SECRET_LINE = [
    (re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----"), "a private key"),
    (re.compile(r"\b(VERST_TP_TOKEN|POSTGRES_PASSWORD|VERST_RATE_KEY_SECRET|VERST_SIGNING_[A-Z_]*PASSWORD)"
                r"\s*[=:]\s*['\"]?(?!\$|<|CHANGE|[А-ЯЁ]|\s|$|['\"]?\s*#)[^\s'\"#]{6,}"), "a server secret"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "a GitHub token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"), "a GitHub token"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"), "an Anthropic key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "an AWS key"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "a Google API key"),
]
TEXT_SUFFIXES = {".py", ".kt", ".kts", ".md", ".yml", ".yaml", ".json", ".sh", ".txt", ".xml", ".toml", ".cfg",
                 ".ini", ".properties", ".env", ".conf", ".example", ".sql", ".html", ".js", ".ts", ""}
MAX_JSON_BYTES = 30_000_000


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=False).stdout


def changed_files(worktree: bool) -> list[str]:
    names = set(git("diff", "--cached", "--name-only", "--diff-filter=ACMR").split())
    if worktree:
        names |= set(git("diff", "--name-only", "--diff-filter=ACMR").split())
        names |= set(git("ls-files", "--others", "--exclude-standard").split())
    return sorted(n for n in names if (ROOT / n).is_file())


def added_lines(path: str, worktree: bool) -> list[str]:
    """The lines this commit adds to [path] (the whole file when it is new or untracked)."""
    tracked = bool(git("ls-files", "--", path).strip())
    if not tracked:
        try:
            return (ROOT / path).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
    diff = git("diff", "--cached", "-U0", "--", path)
    if worktree:
        diff += git("diff", "-U0", "--", path)
    return [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]


def run(cmd: list[str]) -> tuple[bool, str]:
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    return r.returncode == 0, (r.stdout + r.stderr).strip()[-1500:]


def check(worktree: bool) -> list[str]:
    files = changed_files(worktree)
    problems: list[str] = []
    for f in files:
        if FORBIDDEN_NAME.search(f) and not ALLOWED_NAME.search(f):
            problems.append(f"{f}: this file must never be committed (secrets / signing / local settings)")
            continue
        p = ROOT / f
        if p.suffix in TEXT_SUFFIXES or p.name.startswith(".env"):
            for n, line in enumerate(added_lines(f, worktree), 1):
                for rx, what in SECRET_LINE:
                    if rx.search(line):
                        problems.append(f"{f}: added line looks like {what}: {line.strip()[:80]}…")
                        break
        if p.suffix == ".json" and p.stat().st_size <= MAX_JSON_BYTES:
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except (ValueError, UnicodeDecodeError) as e:
                problems.append(f"{f}: invalid JSON ({e})")

    def touched(*prefixes: str) -> bool:
        return any(f.startswith(prefixes) for f in files)

    if touched("design/copy-ru.md", "android/core-ui/src/main/res/values/strings.xml",
               "android/core-ui/src/main/res/values/plurals.xml", "design/tools/gen_strings.py"):
        ok, out = run([sys.executable, "design/tools/gen_strings.py", "--check"])
        if not ok:
            problems.append("strings are out of sync with design/copy-ru.md: run python3 design/tools/gen_strings.py\n" + out)
    if touched("design/tokens", "design/DesignTokens.kt", "design/tools/apply_",
               "android/core-ui/src/main/kotlin/app/verst/core/ui/theme/DesignTokens.kt"):
        ok, out = run([sys.executable, "-I", "design/tools/apply_camper_palette.py", "--check"])
        if not ok:
            problems.append("colour tokens are stale or fail contrast: regenerate (CLAUDE.md «Colours»)\n" + out[-600:])
        a = ROOT / "design/DesignTokens.kt"
        b = ROOT / "android/core-ui/src/main/kotlin/app/verst/core/ui/theme/DesignTokens.kt"
        if a.is_file() and b.is_file() and a.read_bytes() != b.read_bytes():
            problems.append("design/DesignTokens.kt differs from the core-ui copy: run python3 tools/sync_design_tokens.py")
    return problems


def main(argv: list[str]) -> int:
    problems = check("--worktree" in argv)
    if not problems:
        return 0
    print("Commit blocked by tools/hooks/guard_commit.py:", file=sys.stderr)
    for p in problems:
        print(" - " + p, file=sys.stderr)
    print("Fix these, or unstage the file. A real secret belongs in .env on the server or in GitHub Secrets.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
