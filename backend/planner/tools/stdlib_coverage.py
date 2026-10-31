"""Line coverage of `verst_planner` without coverage.py (A§13.5).

Runs the unittest suite under `sys.settrace` and compares executed lines with executable lines: every
`ast` statement except `if TYPE_CHECKING:` blocks, `...` bodies (Protocols), docstrings and statements on a
line marked ``# pragma: no cover`` (a marked compound statement excludes its whole block). A compound
statement counts as executed when any line of its header (decorators through the line before its body) ran.

Usage (from `backend/planner`): ``python3 tools/stdlib_coverage.py [--fail-under 85]``. Exits 1 when the
total is below `--fail-under` or a test fails.
"""

from __future__ import annotations

import argparse
import ast
import io
import sys
import threading
import unittest
from collections.abc import Iterator
from pathlib import Path
from types import FrameType
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "verst_planner"
PRAGMA = "pragma: no cover"


def _is_docstring(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _is_ellipsis(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and node.value.value is Ellipsis
    )


def _is_type_checking(node: ast.stmt) -> bool:
    if not isinstance(node, ast.If):
        return False
    t = node.test
    return (isinstance(t, ast.Name) and t.id == "TYPE_CHECKING") or (
        isinstance(t, ast.Attribute) and t.attr == "TYPE_CHECKING"
    )


def _children(node: ast.AST) -> list[ast.stmt]:
    out: list[ast.stmt] = []
    for field in ("body", "orelse", "finalbody", "handlers", "cases"):
        for child in getattr(node, field, []) or []:
            if isinstance(child, ast.stmt):
                out.append(child)
            else:  # ExceptHandler / match_case hold statements in .body
                out.extend(c for c in getattr(child, "body", []) if isinstance(c, ast.stmt))
    return out


def _head(node: ast.stmt) -> range:
    start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    kids = _children(node)
    if kids:
        end = min(k.lineno for k in kids) - 1
        return range(start, max(start, end) + 1)
    return range(start, (node.end_lineno or node.lineno) + 1)


def executable(path: Path) -> dict[int, range]:
    """First line of each executable statement → the lines whose execution proves it ran."""
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    out: dict[int, range] = {}

    def marked(node: ast.stmt) -> bool:
        return PRAGMA in lines[node.lineno - 1]

    def visit(stmts: list[ast.stmt]) -> None:
        for i, node in enumerate(stmts):
            if marked(node) or _is_type_checking(node) or _is_ellipsis(node):
                continue
            if i == 0 and _is_docstring(node):
                continue
            if not isinstance(node, ast.Try):  # `try:` itself emits no line event
                out[node.lineno] = _head(node)
            visit(_children(node))

    visit(tree.body)
    return out


class Tracer:
    def __init__(self) -> None:
        self.hits: dict[str, set[int]] = {}
        self.prefix = str(PKG) + "/"

    def _local(self, frame: FrameType, event: str, arg: Any) -> Any:
        if event == "line":
            self.hits.setdefault(frame.f_code.co_filename, set()).add(frame.f_lineno)
        return self._local

    def __call__(self, frame: FrameType, event: str, arg: Any) -> Any:
        if event == "call" and frame.f_code.co_filename.startswith(self.prefix):
            self.hits.setdefault(frame.f_code.co_filename, set()).add(frame.f_lineno)
            return self._local
        return None

    def start(self) -> None:
        threading.settrace(self)
        sys.settrace(self)

    def stop(self) -> None:
        sys.settrace(None)
        threading.settrace(None)


def run_tests(quiet: bool) -> unittest.TestResult:
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT), top_level_dir=str(ROOT))
    stream: Any = io.StringIO() if quiet else sys.stderr
    return unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)


def files() -> Iterator[Path]:
    yield from sorted(PKG.rglob("*.py"))


def report(tracer: Tracer) -> tuple[list[tuple[str, int, int]], int, int]:
    rows = []
    total = missed = 0
    for path in files():
        stmts = executable(path)
        hit = tracer.hits.get(str(path), set())
        miss = sum(1 for span in stmts.values() if not any(line in hit for line in span))
        rows.append((str(path.relative_to(ROOT)), len(stmts), miss))
        total += len(stmts)
        missed += miss
    return rows, total, missed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fail-under", type=float, default=0.0)
    parser.add_argument("--verbose-tests", action="store_true")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    for name in [m for m in sys.modules if m == "verst_planner" or m.startswith("verst_planner.")]:
        del sys.modules[name]
    tracer = Tracer()
    tracer.start()
    try:
        result = run_tests(quiet=not args.verbose_tests)
    finally:
        tracer.stop()
    rows, total, missed = report(tracer)
    width = max(len(r[0]) for r in rows)
    print(f"{'Name':<{width}}  {'Stmts':>6}  {'Miss':>6}  {'Cover':>6}")
    print("-" * (width + 24))
    for name, stmts, miss in rows:
        pct = 100.0 * (stmts - miss) / stmts if stmts else 100.0
        print(f"{name:<{width}}  {stmts:>6}  {miss:>6}  {pct:>5.1f}%")
    print("-" * (width + 24))
    pct_total = 100.0 * (total - missed) / total if total else 100.0
    print(f"{'TOTAL':<{width}}  {total:>6}  {missed:>6}  {pct_total:>5.1f}%")
    print(f"tests: {result.testsRun} run, {len(result.failures)} failures, {len(result.errors)} errors")
    if not result.wasSuccessful():
        print("FAIL: the test suite did not pass")
        return 1
    if pct_total < args.fail_under:
        print(f"FAIL: total coverage {pct_total:.1f}% is below --fail-under {args.fail_under:.1f}%")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
