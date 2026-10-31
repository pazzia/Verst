#!/usr/bin/env python3
"""Fork camper-ui (CEO 31.10): overlay the camper paper palette (design/tokens-camper.json) onto design/DesignTokens.kt.

Every colour token of `DesignTokens.color` becomes a PLAIN value from tokens-camper.json "color" (no `Palette.day`
getter is left), so the day and the night theme both show the camper palette. The new group
`DesignTokens.color.camper` (tokens-camper.json "camper": page, paper, border, ink, orange, amber, green, ...) is
(re)written at the end of `object color`. Idempotent, and independent of whether apply_day_palette.py ran before:
the camper file must name every colour token (the run fails on a missing or an unknown one).

    python3 design/tools/apply_day_palette.py && python3 design/tools/apply_camper_palette.py && python3 tools/sync_design_tokens.py
    python3 -I design/tools/apply_camper_palette.py --check   # DesignTokens.kt current + WCAG pairs, exit 1 on failure
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KT = ROOT / "design/DesignTokens.kt"
CAMPER = ROOT / "design/tokens-camper.json"
GROUP_DOC = "/** Fork camper-ui (CEO 31.10): the «Кемпер-гид» paper palette of the Craft components (design/tokens-camper.json). */"

VAL = re.compile(r"^(?P<ind> *)val (?P<name>\w+): Color(?: = (?P<plain>.+)| get\(\) = .+)$")


def kcolor(leaf: dict) -> str:
    base = "Color(0xFF%s)" % leaf["value"][1:].upper()
    if "alpha" in leaf:
        s = "%g" % leaf["alpha"]
        if "." not in s and "e" not in s:
            s += ".0"
        return "%s.copy(alpha = %sf)" % (base, s)
    return base


def leaves(node: dict, p: tuple[str, ...] = ()):
    for k, v in node.items():
        if k.startswith("$"):
            continue
        if isinstance(v, dict) and "value" in v and isinstance(v["value"], str):
            yield p + (k,), v
        elif isinstance(v, dict):
            yield from leaves(v, p + (k,))


def load() -> tuple[dict[tuple[str, ...], dict], dict[str, dict]]:
    d = json.loads(CAMPER.read_text(encoding="utf-8"))
    return dict(leaves(d["color"])), d["camper"]


def render(text: str, colors: dict[tuple[str, ...], dict], camper: dict[str, dict]) -> tuple[str, set[tuple[str, ...]]]:
    lines = text.split("\n")
    out: list[str] = []
    stack: list[tuple[int, str]] = []
    in_color = False
    skip_until: int | None = None
    seen: set[tuple[str, ...]] = set()
    for line in lines:
        ind = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if skip_until is not None:
            if stripped == "}" and ind == skip_until:
                skip_until = None
            continue
        m_obj = re.match(r"^ *object (\w+) \{$", line)
        if m_obj:
            if in_color and m_obj.group(1) == "camper" and ind == 8:
                skip_until = ind  # drop the previous camper group; it is written again below
                if out and out[-1].strip() == GROUP_DOC:
                    out.pop()
                continue
            if m_obj.group(1) == "color" and ind == 4:
                in_color = True
            stack.append((ind, m_obj.group(1)))
            out.append(line)
            continue
        if stripped == "}" and stack and stack[-1][0] == ind:
            name = stack.pop()[1]
            if name == "color" and in_color:
                out.append(" " * 8 + GROUP_DOC)
                out.append(" " * 8 + "object camper {")
                for key, leaf in camper.items():
                    out.append(" " * 12 + "/** %s */" % leaf["use"])
                    out.append(" " * 12 + "val %s: Color = %s" % (key, kcolor(leaf)))
                out.append(" " * 8 + "}")
                in_color = False
            out.append(line)
            continue
        m = VAL.match(line) if in_color else None
        if m:
            path = tuple(n for _, n in stack if n not in ("DesignTokens", "color")) + (m.group("name"),)
            leaf = colors.get(path)
            if leaf is None:
                raise SystemExit("apply_camper_palette: %s has no camper value in %s" % (".".join(path), CAMPER.name))
            seen.add(path)
            out.append("%sval %s: Color = %s" % (m.group("ind"), m.group("name"), kcolor(leaf)))
            continue
        out.append(line)
    unknown = sorted(".".join(p) for p in set(colors) - seen)
    if unknown:
        raise SystemExit("apply_camper_palette: not colour tokens of DesignTokens.kt: %s" % ", ".join(unknown))
    return "\n".join(out), seen


# ---------------------------------------------------------------- WCAG 2.2 (same method as check_day_contrast.py)
def rgb(h: str) -> tuple[int, ...]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lum(h: str) -> float:
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    r, g, b = (x / 255 for x in rgb(h))
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a: str, b: str) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def over(fg: str, alpha: float, bg: str) -> str:
    f, b = rgb(fg), rgb(bg)
    return "#%02X%02X%02X" % tuple(round(alpha * x + (1 - alpha) * y) for x, y in zip(f, b))


# (class, fg, bg, where, threshold); a token with alpha is composited over the background (token@background)
PAIRS = [
    ("text.primary", "text.primary", "dash.base", "main text on the page", 7.0),
    ("text.primary", "text.primary", "dash.raised", "main text on paper", 7.0),
    ("text", "text.secondary", "dash.base", "secondary text", 4.5),
    ("text", "text.secondary", "dash.raised", "secondary text", 4.5),
    ("text", "text.muted", "dash.base", "labels, back links", 4.5),
    ("text", "text.muted", "dash.raised", "labels", 4.5),
    ("text", "text.muted", "camper.header", "labels on the header / wells", 4.5),
    ("text", "text.note", "dash.raised", "stop note", 4.5),
    ("disabled", "text.disabled", "dash.base", "disabled glyphs", 3.0),
    ("disabled", "text.disabled", "dash.raised", "disabled glyphs", 3.0),
    ("disabled", "text.disabled", "dash.controlAlt", "disabled key glyph", 3.0),
    ("disabled", "text.disabled", "dash.control", "disabled secondary button", 3.0),
    ("onLight", "text.onLight", "accent.yellow", "amber CTA plate text", 4.5),
    ("onLight", "text.onLight", "accent.yellowPressed", "pressed amber CTA", 4.5),
    ("onLight", "text.onLight", "sign.white", "city sign, selected chip", 4.5),
    ("onLight", "text.onLightMuted", "sign.white", "Waybill CTA label", 4.5),
    ("sign", "sign.blueText", "sign.blue", "small text on blue signs", 4.5),
    ("sign", "sign.white", "sign.blue", "names on blue signs", 4.5),
    ("sign", "sign.white", "sign.blueSelected", "selected row", 4.5),
    ("sign", "accent.yellow", "sign.blueSelected", "selected row text (amber on dark blue)", 4.5),
    ("sign", "accent.yellow", "sign.bluePressed", "selected + pressed row text", 4.5),
    ("sign", "sign.white", "sign.brown", "tourist sign", 4.5),
    ("sign", "sign.blueText", "sign.brown", "PresetPlate sub", 4.5),
    ("amber text", "accent.yellowText", "dash.base", "prices, links", 4.5),
    ("amber text", "accent.yellowText", "dash.raised", "prices on paper", 4.5),
    ("amber text", "accent.yellowText", "navi.field", "price in a field", 4.5),
    ("amber text", "accent.yellowText", "navi.screen", "on the navigator sheet", 4.5),
    ("amber text", "budget.tight", "dash.raised", "«Впритык»", 4.5),
    ("amber text", "budget.tight", "sign.white", "«Впритык» on the white CTA", 4.5),
    ("amber text", "stretch.text", "stretch.fill", "«РАЗМИНКА»", 4.5),
    ("controls", "text.primary", "dash.controlAlt", "key glyph, info chip", 4.5),
    ("controls", "text.primary", "dash.control", "secondary button, toast", 4.5),
    ("controls", "text.primary", "dash.face", "start label, MoodCard", 4.5),
    ("controls", "text.secondary", "dash.face", "MoodCard sub", 4.5),
    ("controls", "text.primary", "dash.well", "well value", 4.5),
    ("controls", "text.secondary", "dash.well", "well caption", 4.5),
    ("controls", "text.primary", "dash.pressed", "pressed row", 4.5),
    ("controls", "text.primary", "dash.outline", "filled-seat label", 4.5),
    ("controls", "text.seatEmpty", "dash.bench", "«свободно»", 4.5),
    ("controls", "text.secondary", "dash.bench", "«+ пёс»", 4.5),
    ("controls", "hours.unknown", "dash.control", "«часы не указаны»", 4.5),
    ("controls", "sign.white", "dash.odometerDrum", "odometer digits", 4.5),
    ("sky", "mirror.label", "sky.band1", "mirror caption, back link on sky", 4.5),
    ("sky", "mirror.label", "sky.band2", "back link on the lower band", 4.5),
    ("sky", "text.secondary", "sky.band1", "subtitle on sky", 4.5),
    ("sky", "text.primary", "sky.band1", "title on sky", 4.5),
    ("navigator", "navi.text", "navi.field", "field text", 4.5),
    ("navigator", "navi.text", "navi.screen", "distances", 4.5),
    ("navigator", "text.primary", "navi.listSelected", "selected suggestion", 4.5),
    ("navigator", "navi.hint", "navi.field", "placeholder", 4.5),
    ("navigator", "navi.hint", "navi.screen", "section labels", 4.5),
    ("navigator", "navi.label", "navi.screen", "secondary actions", 4.5),
    ("navigator", "navi.label", "navi.field", "«изменить»", 4.5),
    ("navigator", "navi.label", "navi.listSelected", "label on the selected row", 4.5),
    ("navigator", "navi.label", "dash.raised", "excursion link", 4.5),
    ("navigator", "navi.labelSecondary", "navi.field", "field captions", 4.5),
    ("navigator", "navi.labelSecondary", "navi.screen", "sub-lines", 4.5),
    ("navigator", "navi.labelSecondary", "navi.listSelected", "selected sub-line", 4.5),
    ("navigator", "sign.white", "navi.label", "badge «У» on navi.label", 4.5),
    ("status", "accent.redText", "dash.base", "red text", 4.5),
    ("status", "accent.redText", "dash.raised", "overspend", 4.5),
    ("status", "accent.redText", "dash.control", "«Нужен интернет»", 4.5),
    ("status", "accent.redText", "budget.overFill", "«Не помещается»", 4.5),
    ("status", "text.primary", "budget.overFill", "over-budget amount", 4.5),
    ("status", "hours.open", "hours.openFill@dash.raised", "«открыто» pill", 4.5),
    ("status", "hours.open", "dash.raised", "«открыто»", 4.5),
    ("status", "hours.closed", "hours.closedFill@dash.raised", "«закрыто» pill", 4.5),
    ("status", "kind.text", "kind.fill", "category tag", 4.5),
    ("status", "text.primary", "info.fill", "info plate", 4.5),
    ("status", "text.primary", "overlay.returnFlash@dash.raised", "row during the return flash", 4.5),
    ("paper", "paper.text", "paper.sheet", "printed text", 4.5),
    ("paper", "paper.label", "paper.sheet", "printed labels", 4.5),
    ("paper", "paper.ink", "paper.sheet", "handwriting", 4.5),
    ("paper", "paper.inkRed", "paper.sheet", "handwritten overspend", 4.5),
    ("photo", "photo.credit", "photo.scrim@#FFFFFF", "credit on a white photo", 4.5),
] + [("photo", "text.muted", "photo.%s" % k, "placeholder caption on %s" % k, 4.5)
     for k in ("mat", "phMuseum", "phChurch", "phPark", "phMonument", "phView", "phBar", "phCity")] + [
    # the Craft components
    ("craft", "camper.ink", "camper.page", "text on the page", 7.0),
    ("craft", "camper.ink", "camper.paper", "text on a card", 7.0),
    ("craft", "camper.ink", "camper.header", "header / tab bar text", 7.0),
    ("craft", "camper.inkSoft", "camper.paper", "secondary text on a card", 4.5),
    ("craft", "camper.inkMuted", "camper.paper", "muted text on a card", 4.5),
    ("craft", "camper.inkMuted", "camper.header", "inactive tab label", 4.5),
    ("craft", "camper.orangeText", "camper.header", "«КЕМПЕР-ГИД» under the logo", 4.5),
    ("craft", "camper.orangeText", "camper.paper", "orange overline on a card", 4.5),
    ("craft", "camper.greenText", "camper.paper", "green text on a card", 4.5),
    ("craft", "camper.ink", "camper.orange", "ink on an orange chip", 4.5),
    ("craft", "camper.onAmber", "camper.amber", "badge text", 4.5),
    ("craft", "camper.onOrange", "camper.green", "white on a green badge", 4.5),
    ("craft", "camper.onOrange", "camper.blue", "white on a blue badge", 4.5),
    ("craft", "camper.onOrange", "camper.stamp", "white on the stamp disc", 4.5),
    ("craft", "camper.onOrange", "camper.orange", "CraftButton label (mockup white; known deviation, see rules)", 2.8),
    ("ui 3:1", "camper.border", "camper.page", "card / field border", 3.0),
    ("ui 3:1", "camper.orange", "camper.paper", "active tile vs card", 2.5),
    ("ui 3:1", "dash.outline", "dash.raised", "outline button border", 3.0),
    ("ui 3:1", "dash.outline", "dash.base", "outline button border", 3.0),
    ("ui 3:1", "dash.outlineDashed", "dash.raised", "off-chip border", 3.0),
    ("ui 3:1", "dash.outlineDashed", "dash.bench", "empty-seat dashed border", 3.0),
    ("ui 3:1", "navi.fieldBorder", "navi.screen", "input border", 3.0),
    ("ui 3:1", "navi.fieldBorder", "navi.field", "input border", 3.0),
    ("ui 3:1", "navi.radio", "navi.screen", "unselected radio", 3.0),
    ("ui 3:1", "overlay.focus", "dash.base", "focus ring", 3.0),
    ("ui 3:1", "overlay.focus", "dash.raised", "focus ring", 3.0),
    ("ui 3:1", "accent.red", "dash.raised", "start ring, gauge E", 3.0),
    ("ui 3:1", "budget.overBorder", "dash.raised", "over-budget border", 3.0),
    ("ui 3:1", "stretch.border", "dash.raised", "«РАЗМИНКА» border", 3.0),
    ("ui 3:1", "kind.border", "dash.raised", "category tag border", 3.0),
    ("ui 3:1", "info.mark", "info.fill", "info check disc", 3.0),
    ("ui 3:1", "signal.green", "dash.raised", "turn signal", 3.0),
    ("ui 3:1", "sign.blue", "dash.raised", "blue sign edge", 3.0),
    ("ui 3:1", "sign.brown", "dash.raised", "tourist sign edge", 3.0),
]


def check(colors: dict[tuple[str, ...], dict], camper: dict[str, dict]) -> int:
    table = {".".join(p): v for p, v in colors.items()}
    table.update({"camper." + k: v for k, v in camper.items()})

    def resolve(ref: str, bg: str | None = None) -> str:
        if ref.startswith("#"):
            return ref
        if "@" in ref:
            tok, base = ref.split("@")
            return resolve(tok, resolve(base))
        v = table[ref]
        if "alpha" in v:
            if bg is None:
                raise SystemExit("%s has alpha; give a background with @" % ref)
            return over(v["value"], v["alpha"], bg)
        return v["value"]

    fails = 0
    print(f"{'class':<12} {'fg':<34} {'bg':<34} {'ratio':>6} {'need':>5}  result  where")
    for cls, fg, bg, where, need in PAIRS:
        bgh = resolve(bg)
        fgh = resolve(fg, bgh)
        r = ratio(fgh, bgh)
        ok = r >= need
        fails += 0 if ok else 1
        print(f"{cls:<12} {fg + ' ' + fgh:<34} {bg + ' ' + bgh:<34} {r:6.2f} {need:5.1f}  {'PASS' if ok else 'FAIL'}    {where}")
    print(f"{len(PAIRS)} pairs; {'ALL PASS' if fails == 0 else f'{fails} FAILURE(S)'}")
    return fails


def main() -> int:
    colors, camper = load()
    text = KT.read_text(encoding="utf-8")
    new, seen = render(text, colors, camper)
    if "--check" in sys.argv:
        fails = check(colors, camper)
        if new != text:
            print("apply_camper_palette --check: design/DesignTokens.kt is STALE (run without --check)")
            fails += 1
        else:
            print("apply_camper_palette --check: design/DesignTokens.kt up to date (%d colour tokens + %d camper)" % (len(seen), len(camper)))
        return 1 if fails else 0
    KT.write_text(new, encoding="utf-8")
    print("camper palette: %d colour tokens are plain camper values; color.camper has %d tokens" % (len(seen), len(camper)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
