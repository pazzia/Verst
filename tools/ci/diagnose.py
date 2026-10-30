#!/usr/bin/env python3
"""CI diagnostics for the Android workflow (docs/architecture-android-mvp.md §12).

Stdlib only. Every sub-command reads build outputs, writes plain-text/JSON files under ``--out``
(later published to the ``ci-logs`` branch) and prints at most ``--max-annotations`` GitHub
workflow commands (``::error file=…,line=…::…``) so the errors also appear as check-run
annotations readable through ``GET /repos/{o}/{r}/check-runs/{id}/annotations``.

Sub-commands
  gradle  --log F --step NAME     Kotlin/Java/AAPT/Gradle errors from a ``--console=plain`` log
  junit   --root DIR              failing test cases from ``**/build/test-results/**/*.xml``
  lint    --root DIR              Error/Fatal issues from ``**/build/reports/lint-results-*.xml``
  logcat  --log F                 Python tracebacks, fatal exceptions and Verst* tags from logcat
  instrument --log F              failures from ``am instrument -r`` raw output
  apk     --apk F [--warn-mb N --fail-mb N]   size, sha256, ABIs; exit 1 above the fail budget or when the
                                              APK packs the server-only catalogue abroad (CEO 29.10)
  steps   --json STR --job NAME   step outcomes from ``toJSON(steps)``
  summarize                       summary.md from everything written so far

All sub-commands append to ``<out>/summary.json`` (created on demand). Exit code is 0 unless
stated (diagnostics never fail a job by themselves, except ``apk`` over budget).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

WORKSPACE = Path(os.environ.get("GITHUB_WORKSPACE", os.getcwd())).resolve()

KOTLIN = re.compile(r"^(?P<sev>[ew]): (?:file://)?(?P<path>/[^:]+?\.kts?):(?P<line>\d+):(?P<col>\d+) (?P<msg>.*)$")
JAVAC = re.compile(r"^(?P<path>/\S+?\.java):(?P<line>\d+): (?P<sev>error|warning): (?P<msg>.*)$")
AAPT = re.compile(
    r"^(?:ERROR|error):\s*(?P<path>/\S+?\.(?:xml|png|9\.png|ttf|json))(?::(?P<line>\d+))?(?::\d+)?:?\s*(?P<msg>.*)$"
)
AAPT2 = re.compile(r"AAPT: error: (?P<msg>.*)$")
GRADLE_TEST_FAILED = re.compile(r"^(?P<cls>[\w.$]+) > (?P<test>.+) FAILED$")
CONTEXT_PATTERNS = re.compile(
    r"(\berror\b|\bFAILED\b|FAILURE:|What went wrong|Could not (?:find|resolve|get|determine)|"
    r"Exception|Caused by:|Chaquopy|python|Traceback|BUILD (?:FAILED|SUCCESSFUL)|e: |> Task .*FAILED)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------------------------- utils
def rel(path: str) -> str:
    """Absolute runner path → repo-relative path (annotations need repo-relative paths)."""
    p = Path(path)
    try:
        return str(p.resolve().relative_to(WORKSPACE))
    except (ValueError, OSError):
        return path.lstrip("/")


def esc_data(s: str) -> str:
    return s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def esc_prop(s: str) -> str:
    return esc_data(s).replace(":", "%3A").replace(",", "%2C")


def annotation(level: str, msg: str, file: str | None = None, line: int | None = None,
               col: int | None = None, title: str | None = None) -> str:
    props = []
    if file:
        props.append(f"file={esc_prop(file)}")
    if line:
        props.append(f"line={line}")
    if col:
        props.append(f"col={col}")
    if title:
        props.append(f"title={esc_prop(title)}")
    head = f"::{level} " + ",".join(props) if props else f"::{level}"
    return f"{head}::{esc_data(msg[:2000])}"


class Out:
    def __init__(self, root: str, max_annotations: int) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max = max_annotations
        self.emitted = 0

    def emit(self, level: str, msg: str, **kw: Any) -> None:
        if self.emitted < self.max:
            print(annotation(level, msg, **kw), flush=True)
            self.emitted += 1

    def write(self, name: str, text: str) -> Path:
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def append_errors(self, lines: list[str]) -> None:
        if not lines:
            return
        with (self.root / "errors.txt").open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def summary(self) -> dict[str, Any]:
        p = self.root / "summary.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return {"schema": 1, "run": os.environ.get("GITHUB_RUN_ID"), "sha": os.environ.get("GITHUB_SHA"),
                "ref": os.environ.get("GITHUB_REF"), "job": os.environ.get("GITHUB_JOB"), "sections": {}}

    def save_summary(self, data: dict[str, Any]) -> None:
        self.write("summary.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    def section(self, key: str, value: Any) -> None:
        s = self.summary()
        s["sections"][key] = value
        self.save_summary(s)


def trim_log(lines: list[str], tail: int = 400, context: int = 3, cap: int = 4000) -> str:
    keep: set[int] = set(range(max(0, len(lines) - tail), len(lines)))
    for i, line in enumerate(lines):
        if CONTEXT_PATTERNS.search(line):
            keep.update(range(max(0, i - context), min(len(lines), i + context + 1)))
    out: list[str] = []
    prev = -2
    for i in sorted(keep):
        if i != prev + 1:
            out.append(f"··· [{i - prev - 1} lines skipped] ···" if prev >= 0 else f"··· [{i} lines skipped] ···")
        out.append(lines[i])
        prev = i
    if len(out) > cap:
        out = out[:200] + [f"··· [{len(out) - cap} trimmed lines] ···"] + out[-(cap - 200):]
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------------------------- gradle
def cmd_gradle(a: argparse.Namespace, o: Out) -> int:
    path = Path(a.log)
    if not path.exists():
        o.section(f"gradle.{a.step}", {"log": "missing"})
        return 0
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    o.write(f"logs/{a.step}.log.txt", trim_log(lines))
    errors: list[str] = []
    seen: set[str] = set()

    def add(level: str, msg: str, file: str | None, line: int | None, col: int | None, title: str) -> None:
        key = f"{file}:{line}:{msg}"
        if key in seen:
            return
        seen.add(key)
        loc = f"{file}:{line}:{col or 0}" if file else "-"
        errors.append(f"[{a.step}] {title} {loc} {msg}")
        if level == "error":
            o.emit("error", msg, file=file, line=line, col=col, title=f"{title} ({a.step})")

    for line in lines:
        s = line.rstrip()
        if m := KOTLIN.match(s):
            if m["sev"] == "e":
                add("error", m["msg"], rel(m["path"]), int(m["line"]), int(m["col"]), "Kotlin")
        elif m := JAVAC.match(s):
            if m["sev"] == "error":
                add("error", m["msg"], rel(m["path"]), int(m["line"]), None, "Java")
        elif m := AAPT.match(s):
            add("error", m["msg"] or s, rel(m["path"]), int(m["line"]) if m["line"] else None, None, "Resources")
        elif m := AAPT2.search(s):
            add("error", m["msg"], None, None, None, "AAPT")
        elif m := GRADLE_TEST_FAILED.match(s):
            add("error", f"{m['cls']} > {m['test']}", None, None, None, "Test")

    # "* What went wrong:" blocks (dependency resolution, plugin errors, task failures)
    blocks: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == "* What went wrong:":
            j = i + 1
            block: list[str] = []
            while j < len(lines) and not lines[j].startswith("* Try:") and len(block) < 60:
                block.append(lines[j])
                j += 1
            text = "\n".join(b for b in block if b.strip())
            blocks.append(text)
            i = j
        else:
            i += 1
    for b in blocks:
        first = b.strip().splitlines()[0] if b.strip() else "Gradle failure"
        add("error", b.strip()[:1500], None, None, None, f"Gradle: {first[:80]}")

    failed = any("BUILD FAILED" in x for x in lines)
    o.append_errors(errors)
    o.section(f"gradle.{a.step}", {"buildFailed": failed, "errors": len(errors), "whatWentWrong": blocks[:5]})
    return 0


# ---------------------------------------------------------------------------------------------- junit
def _source_for(cls: str, root: Path) -> str | None:
    simple = cls.split(".")[-1].split("$")[0]
    for p in root.rglob(f"{simple}.kt"):
        if "/build/" not in str(p):
            return rel(str(p))
    return None


def cmd_junit(a: argparse.Namespace, o: Out) -> int:
    root = Path(a.root)
    total = failures = skipped = 0
    report: list[str] = []
    errors: list[str] = []
    for xml in sorted(root.glob("**/build/test-results/**/*.xml")):
        try:
            tree = ET.parse(xml)
        except ET.ParseError:
            continue
        for tc in tree.iter("testcase"):
            total += 1
            if tc.find("skipped") is not None:
                skipped += 1
            bad = tc.find("failure")
            if bad is None:
                bad = tc.find("error")
            if bad is None:
                continue
            failures += 1
            cls, name = tc.get("classname", "?"), tc.get("name", "?")
            msg = (bad.get("message") or "").strip()
            body = (bad.text or "").strip().splitlines()[:30]
            line_no = None
            simple = cls.split(".")[-1]
            for b in body:
                if m := re.search(rf"\({re.escape(simple)}\.kt:(\d+)\)", b):
                    line_no = int(m.group(1))
                    break
            src = _source_for(cls, root)
            report.append(f"## {cls} > {name}\n{msg}\n" + "\n".join(body) + "\n")
            errors.append(f"[test] {cls} > {name}: {msg[:300]}")
            o.emit("error", f"{name}: {msg[:900]}", file=src, line=line_no, title=f"Test failed: {simple}")
    o.write("tests/failures.txt", "\n".join(report) if report else "no failing tests\n")
    o.append_errors(errors)
    o.section("junit", {"tests": total, "failures": failures, "skipped": skipped})
    return 0


# ----------------------------------------------------------------------------------------------- lint
def cmd_lint(a: argparse.Namespace, o: Out) -> int:
    root = Path(a.root)
    out: list[str] = []
    counts: dict[str, int] = {}
    for xml in sorted(root.glob("**/build/reports/lint-results-*.xml")):
        try:
            tree = ET.parse(xml)
        except ET.ParseError:
            continue
        for issue in tree.iter("issue"):
            sev = issue.get("severity", "")
            counts[sev] = counts.get(sev, 0) + 1
            if sev not in ("Error", "Fatal"):
                continue
            loc = issue.find("location")
            file = rel(loc.get("file", "")) if loc is not None else None
            line = int(loc.get("line")) if loc is not None and loc.get("line") else None
            msg = f"[{issue.get('id')}] {issue.get('message')}"
            out.append(f"{sev} {file}:{line} {msg}")
            o.emit("error", msg, file=file, line=line, title="Android Lint")
    o.write("lint/lint-errors.txt", "\n".join(out) + "\n" if out else "no lint errors\n")
    o.append_errors([f"[lint] {x}" for x in out])
    o.section("lint", counts)
    return 0


# --------------------------------------------------------------------------------------------- logcat
LOGCAT_KEEP = re.compile(r"(Verst\w*|python\.std(?:out|err)|AndroidRuntime|FATAL|chaquopy|TestRunner)", re.I)


def cmd_logcat(a: argparse.Namespace, o: Out) -> int:
    path = Path(a.log)
    if not path.exists():
        o.section("logcat", {"log": "missing"})
        return 0
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    kept = [x for x in lines if LOGCAT_KEEP.search(x)]
    o.write("logcat-filtered.txt", "\n".join(kept[-5000:]) + "\n")
    tracebacks: list[str] = []
    cur: list[str] | None = None
    for x in kept:
        payload = x.split(": ", 1)[1] if ": " in x else x
        if "Traceback (most recent call last)" in payload or "FATAL EXCEPTION" in payload:
            if cur:
                tracebacks.append("\n".join(cur))
            cur = [payload]
        elif cur is not None:
            cur.append(payload)
            if len(cur) > 40 or re.match(r"^\w+(\.\w+)*(Error|Exception)\b", payload):
                tracebacks.append("\n".join(cur))
                cur = None
    if cur:
        tracebacks.append("\n".join(cur))
    for t in tracebacks[:5]:
        o.emit("error", t, title="Runtime exception on emulator")
    o.append_errors([f"[logcat] {t.splitlines()[-1]}" for t in tracebacks])
    o.write("tracebacks.txt", "\n\n".join(tracebacks) + "\n" if tracebacks else "none\n")
    o.section("logcat", {"lines": len(lines), "kept": len(kept), "tracebacks": len(tracebacks)})
    return 0


# ----------------------------------------------------------------------------------------- instrument
def cmd_instrument(a: argparse.Namespace, o: Out) -> int:
    path = Path(a.log)
    if not path.exists():
        o.section("instrument", {"log": "missing"})
        return 0
    text = path.read_text(encoding="utf-8", errors="replace")
    blocks = text.split("INSTRUMENTATION_STATUS_CODE:")
    results: list[dict[str, Any]] = []
    status: dict[str, str] = {}
    last_key: str | None = None
    for line in text.splitlines():
        if line.startswith("INSTRUMENTATION_STATUS: "):
            k, _, v = line[len("INSTRUMENTATION_STATUS: "):].partition("=")
            status[k] = v
            last_key = k
        elif not line.startswith("INSTRUMENTATION_") and last_key is not None:
            status[last_key] += "\n" + line  # multi-line values (stack traces)
        elif line.startswith("INSTRUMENTATION_STATUS_CODE: "):
            last_key = None
            code = int(line.split(":")[1].strip())
            if code in (0, -1, -2, -4) and "test" in status:
                results.append({"class": status.get("class"), "test": status.get("test"), "code": code,
                                "stack": status.get("stack", "")})
            status = {}
    passed = sum(1 for r in results if r["code"] == 0)
    failed = [r for r in results if r["code"] in (-1, -2)]
    for r in failed[:10]:
        o.emit("error", (r["stack"] or "failed")[:1500], title=f"Emulator test failed: {r['class']}.{r['test']}")
    crashed = "INSTRUMENTATION_RESULT: shortMsg=Process crashed" in text or "Process crashed" in text
    if crashed:
        o.emit("error", "Instrumentation process crashed; see e2e/tracebacks.txt in ci-logs", title="Emulator crash")
    o.write("instrument-failures.txt",
            "\n\n".join(f"{r['class']}.{r['test']}\n{r['stack']}" for r in failed) or "none\n")
    o.append_errors([f"[e2e] {r['class']}.{r['test']}" for r in failed])
    o.section("instrument", {"tests": len(results), "passed": passed, "failed": len(failed), "crashed": crashed,
                             "ok": ("OK (" in blocks[-1]) if blocks else False})
    return 0


# ------------------------------------------------------------------------------------------------ apk
# CEO 29.10: the catalogue of trips abroad (backend/planner/abroad/<cc>/catalogue_*.json.gz) is planned on the
# server only and must never ship in the APK. Chaquopy packs the Python code into archives inside the APK
# (assets/chaquopy/app.imy), so nested archives are searched too.
NESTED_ARCHIVES = (".imy", ".zip", ".jar")


def abroad_entries(z: zipfile.ZipFile, prefix: str = "", depth: int = 0) -> list[str]:
    """Entries of the APK (and of the archives in it) under a directory named `abroad`."""
    import io

    out = []
    for name in z.namelist():
        if "abroad" in name.split("/")[:-1]:
            out.append(prefix + name)
        if depth < 2 and name.endswith(NESTED_ARCHIVES):
            try:
                with zipfile.ZipFile(io.BytesIO(z.read(name))) as inner:
                    out += abroad_entries(inner, f"{prefix}{name}!/", depth + 1)
            except zipfile.BadZipFile:
                continue
    return out


def cmd_apk(a: argparse.Namespace, o: Out) -> int:
    apk = Path(a.apk)
    if not apk.exists():
        o.emit("error", f"APK not found: {a.apk}", title="APK")
        o.section("apk", {"missing": str(a.apk)})
        return 1
    data = apk.read_bytes()
    size = len(data)
    with zipfile.ZipFile(apk) as z:
        names = z.namelist()
        abis = sorted({n.split("/")[1] for n in names if n.startswith("lib/") and n.count("/") >= 2})
        by_top: dict[str, int] = {}
        for info in z.infolist():
            top = info.filename.split("/")[0] if "/" in info.filename else info.filename
            by_top[top] = by_top.get(top, 0) + info.compress_size
        abroad = abroad_entries(z)
    mb = size / 1_000_000
    info_d = {"file": apk.name, "bytes": size, "mb": round(mb, 2), "sha256": hashlib.sha256(data).hexdigest(),
              "abis": abis, "largestEntries": dict(sorted(by_top.items(), key=lambda kv: -kv[1])[:12]),
              "warnMb": a.warn_mb, "failMb": a.fail_mb, "abroadEntries": abroad[:20]}
    o.write("apk.json", json.dumps(info_d, indent=2) + "\n")
    o.section("apk", info_d)
    if abroad:
        o.emit("error", f"the APK packs the server-only catalogue abroad: {', '.join(abroad[:5])}",
               title="APK content")
        return 1
    if mb > a.fail_mb:
        o.emit("error", f"APK is {mb:.1f} MB, budget {a.fail_mb} MB", title="APK size budget")
        return 1
    if mb > a.warn_mb:
        print(annotation("warning", f"APK is {mb:.1f} MB (warn above {a.warn_mb} MB)", title="APK size"))
    return 0


# ---------------------------------------------------------------------------------------------- steps
def cmd_steps(a: argparse.Namespace, o: Out) -> int:
    try:
        steps = json.loads(a.json or "{}")
    except json.JSONDecodeError:
        steps = {}
    o.section(f"steps.{a.job}", {k: v.get("outcome") for k, v in steps.items()})
    return 0


# ------------------------------------------------------------------------------------------ summarize
def cmd_summarize(a: argparse.Namespace, o: Out) -> int:
    s = o.summary()
    lines = [f"# CI run {s.get('run')} · {s.get('job')} · {str(s.get('sha'))[:10]} · {s.get('ref')}", ""]
    for k, v in s["sections"].items():
        lines.append(f"## {k}")
        lines.append("```json")
        lines.append(json.dumps(v, ensure_ascii=False, indent=2)[:4000])
        lines.append("```")
    err = o.root / "errors.txt"
    if err.exists():
        lines += ["", "## First errors", "```", *err.read_text(encoding="utf-8").splitlines()[:80], "```"]
    o.write("summary.md", "\n".join(lines) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="diagnose.py")
    p.add_argument("--out", default="diag")
    p.add_argument("--max-annotations", type=int, default=10)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gradle")
    g.add_argument("--log", required=True)
    g.add_argument("--step", required=True)
    sub.add_parser("junit").add_argument("--root", required=True)
    sub.add_parser("lint").add_argument("--root", required=True)
    sub.add_parser("logcat").add_argument("--log", required=True)
    sub.add_parser("instrument").add_argument("--log", required=True)
    ap = sub.add_parser("apk")
    ap.add_argument("--apk", required=True)
    ap.add_argument("--warn-mb", type=float, default=45.0)
    ap.add_argument("--fail-mb", type=float, default=60.0)
    st = sub.add_parser("steps")
    st.add_argument("--json", default="{}")
    st.add_argument("--job", required=True)
    sub.add_parser("summarize")
    a = p.parse_args(argv)
    o = Out(a.out, a.max_annotations)
    handler = {"gradle": cmd_gradle, "junit": cmd_junit, "lint": cmd_lint, "logcat": cmd_logcat,
               "instrument": cmd_instrument, "apk": cmd_apk, "steps": cmd_steps, "summarize": cmd_summarize}
    return handler[a.cmd](a, o)


if __name__ == "__main__":
    sys.exit(main())
