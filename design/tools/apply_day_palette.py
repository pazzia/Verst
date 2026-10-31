#!/usr/bin/env python3
"""D-IR-20: overlay the day palette (design/tokens-day.json) onto design/DesignTokens.kt.

Every colour token with a different day value becomes a getter that reads `Palette.day` (set once per process from
the settings, see core-ui `Palette.kt`); tokens equal by day stay plain values. The proposed tokens of
`$meta.proposedTokens` (accent.yellowText) are added in both palettes. Idempotent: it starts from the plain values.

    python3 design/tools/apply_day_palette.py && python3 tools/sync_design_tokens.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KT = ROOT / "design/DesignTokens.kt"
DAY = ROOT / "design/tokens-day.json"

VAL = re.compile(r"^(?P<ind> *)val (?P<name>\w+): Color(?: = (?P<plain>.+)| get\(\) = if \(Palette\.day\) .+ else (?P<night>.+))$")


def kcolor(leaf: dict) -> str:
    base = "Color(0xFF%s)" % leaf["value"][1:].upper()
    if "alpha" in leaf:
        s = "%g" % leaf["alpha"]
        if "." not in s and "e" not in s:
            s += ".0"
        return "%s.copy(alpha = %sf)" % (base, s)
    return base


def day_leaves() -> dict[tuple[str, ...], dict]:
    d = json.loads(DAY.read_text(encoding="utf-8"))

    def walk(x: dict, p: tuple[str, ...]):
        for k, v in x.items():
            if k.startswith("$"):
                continue
            if isinstance(v, dict) and "value" in v and isinstance(v["value"], str):
                yield p + (k,), v
            elif isinstance(v, dict):
                yield from walk(v, p + (k,))

    out = dict(walk(d["color"], ()))
    for path, spec in d.get("$meta", {}).get("proposedTokens", {}).items():
        out[tuple(path.split("."))] = {"value": spec["day"], "_night": spec["night"], "use": spec.get("use", "")}
    return out


def main() -> None:
    day = day_leaves()
    lines = KT.read_text(encoding="utf-8").split("\n")
    out: list[str] = []
    stack: list[tuple[int, str]] = []
    in_color = False
    switched = 0
    seen: set[tuple[str, ...]] = set()
    for line in lines:
        stripped = line.strip()
        ind = len(line) - len(line.lstrip(" "))
        m_obj = re.match(r"^ *object (\w+) \{$", line)
        if m_obj:
            if m_obj.group(1) == "color" and ind == 4:
                in_color = True
            stack.append((ind, m_obj.group(1)))
            out.append(line)
            continue
        if stripped == "}" and stack and stack[-1][0] == ind:
            name = stack.pop()[1]
            if in_color and name != "color":
                group = tuple(n for _, n in stack if n not in ("DesignTokens", "color")) + (name,)
                # proposed tokens that belong to this group and are not in the file yet
                for path, leaf in day.items():
                    if "_night" in leaf and path[:-1] == group and path not in seen:
                        out.append(" " * (ind + 4) + "/** %s (D-IR-20 day palette: proposed token) */" % leaf["use"].split(". ")[0])
                        night = kcolor({"value": leaf["_night"]})
                        out.append(" " * (ind + 4) + "val %s: Color get() = if (Palette.day) %s else %s" % (path[-1], kcolor(leaf), night))
                        seen.add(path)
                        switched += 1
            if name == "color":
                in_color = False
            out.append(line)
            continue
        m = VAL.match(line) if in_color else None
        if m:
            path = tuple(n for _, n in stack if n not in ("DesignTokens", "color")) + (m.group("name"),)
            seen.add(path)
            night = m.group("plain") or m.group("night")
            leaf = day.get(path)
            if leaf is not None and "_night" not in leaf and kcolor(leaf) != night:
                out.append("%sval %s: Color get() = if (Palette.day) %s else %s" % (m.group("ind"), m.group("name"), kcolor(leaf), night))
                switched += 1
            elif leaf is not None and "_night" in leaf:
                out.append("%sval %s: Color get() = if (Palette.day) %s else %s" % (m.group("ind"), m.group("name"), kcolor(leaf), night))
                switched += 1
            else:
                out.append("%sval %s: Color = %s" % (m.group("ind"), m.group("name"), night))
            continue
        out.append(line)
    KT.write_text("\n".join(out), encoding="utf-8")
    print(f"day palette: {switched} colour tokens switch with Palette.day")


if __name__ == "__main__":
    main()
