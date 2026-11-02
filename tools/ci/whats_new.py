#!/usr/bin/env python3
"""«Что нового» for release notes (CEO 02.11): the Russian `Тестерам:` trailer lines of the commits between the
previous release and this build (CLAUDE.md, «What's new»).

    python3 tools/ci/whats_new.py --since <sha>|"" [--head HEAD] [--notes-body FILE] [--max 25]

`--notes-body FILE` reads the previous release's notes and takes its commit from «Коммит: <sha>» or «Собрано из
коммита <sha>» (when `--since` is empty). Without a usable previous commit, the last 30 commits are read.
Prints Markdown: a «Что нового» heading and one bullet per change, newest first, duplicates dropped.
Standard library only.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

TRAILER = re.compile(r"^\s*Тестерам\s*:\s*(.+?)\s*$", re.MULTILINE)
PREV_SHA = re.compile(r"(?:Коммит:|Собрано из коммита)\s*([0-9a-f]{40})")
SEP = "\x1e"


def git(*args: str) -> tuple[int, str]:
    r = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    return r.returncode, r.stdout


def previous_commit(notes: str) -> str | None:
    m = PREV_SHA.search(notes)
    return m.group(1) if m else None


def bodies(since: str | None, head: str) -> list[str]:
    if since:
        code, _ = git("merge-base", "--is-ancestor", since, head)
        if code == 0:
            _, out = git("log", f"--format=%B{SEP}", f"{since}..{head}")
            return [b for b in out.split(SEP) if b.strip()]
    _, out = git("log", f"--format=%B{SEP}", "-n", "30", head)
    return [b for b in out.split(SEP) if b.strip()]


def items(texts: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for body in texts:
        for m in TRAILER.finditer(body):
            line = m.group(1).rstrip(".")
            key = line.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(line)
    return out[:limit]


def render(lines: list[str], had_range: bool) -> str:
    if not lines:
        note = "видимых изменений нет: внутренние исправления и проверки." if had_range else "список изменений не найден."
        return "**Что нового:** " + note
    return "**Что нового:**\n" + "\n".join(f"- {l}." for l in lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--notes-body", default="")
    ap.add_argument("--max", type=int, default=25)
    a = ap.parse_args(argv)
    since = a.since or None
    if not since and a.notes_body:
        try:
            with open(a.notes_body, encoding="utf-8") as f:
                since = previous_commit(f.read())
        except OSError:
            since = None
    print(render(items(bodies(since, a.head), a.max), since is not None))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
