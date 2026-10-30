"""Checks the day palette design/tokens-day.json against the night tokens design/tokens.json.

Usage: python3 -I design/tools/check_day_contrast.py
  (a) the set of colour leaf paths in tokens-day.json "color" equals the one in tokens.json "color";
      every day leaf has value #RRGGBB, use, from in {variant-b, derived, same-as-night}, and "alpha"
      only where the night leaf has one;
  (b) WCAG 2.2 contrast for every text / UI pair the day theme depends on, with PASS/FAIL.
Alpha colours are composited over their stated background before measuring.
Exit code 1 on any failure.
"""
import json, pathlib, re, sys

DESIGN = pathlib.Path(__file__).resolve().parents[1]
night = json.loads((DESIGN / "tokens.json").read_text(encoding="utf-8"))
day = json.loads((DESIGN / "tokens-day.json").read_text(encoding="utf-8"))


def leaves(node, prefix=""):
    out = {}
    for k, v in node.items():
        if isinstance(v, dict) and "value" in v and not isinstance(v["value"], dict):
            out[prefix + k] = v
        elif isinstance(v, dict):
            out.update(leaves(v, prefix + k + "."))
    return out


N, D = leaves(night["color"]), leaves(day["color"])
fails = 0

# ---------- (a) structure ----------
missing, extra = sorted(set(N) - set(D)), sorted(set(D) - set(N))
print(f"Leaves: night {len(N)}, day {len(D)}; missing {len(missing)}, extra {len(extra)}")
for p in missing:
    print("  MISSING", p)
for p in extra:
    print("  EXTRA  ", p)
fails += len(missing) + len(extra)
for p, v in D.items():
    problems = []
    if not re.fullmatch(r"#[0-9A-F]{6}", v.get("value", "")):
        problems.append("value is not #RRGGBB")
    if v.get("from") not in ("variant-b", "derived", "same-as-night"):
        problems.append("bad from")
    if not v.get("use"):
        problems.append("no use")
    if p in N and ("alpha" in v) != ("alpha" in N[p]):
        problems.append("alpha presence differs from night")
    if p in N and v.get("from") == "same-as-night" and (v["value"], v.get("alpha")) != (N[p]["value"], N[p].get("alpha")):
        problems.append("marked same-as-night but differs")
    for pr in problems:
        print(f"  LEAF {p}: {pr}")
        fails += 1
counts = {}
for v in D.values():
    counts[v.get("from")] = counts.get(v.get("from"), 0) + 1
print("from:", ", ".join(f"{k} {counts[k]}" for k in sorted(counts)))

# ---------- (b) contrast ----------
def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexs(c):
    return "#%02X%02X%02X" % tuple(round(x) for x in c)


def lum(h):
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (x / 255 for x in rgb(h))
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def over(fg_hex, alpha, bg_hex):
    f, b = rgb(fg_hex), rgb(bg_hex)
    return hexs(tuple(alpha * x + (1 - alpha) * y for x, y in zip(f, b)))


def resolve(ref, bg_hex=None):
    """Token path, literal #hex, or 'token@bgtoken' (composite the alpha token over a background)."""
    if ref.startswith("#"):
        return ref
    if "@" in ref:
        tok, base = ref.split("@")
        return resolve(tok, resolve(base))
    v = D[ref]
    if "alpha" in v:
        if bg_hex is None:
            raise ValueError(f"{ref} has alpha; give a background with @")
        return over(v["value"], v["alpha"], bg_hex)
    return v["value"]


PROPOSED_YELLOW_TEXT = day["$meta"]["proposedTokens"]["accent.yellowText"]["day"]

# (class, fg, bg, where, threshold)
PAIRS = [
    # text ramp on the dashboard
    ("text.primary", "text.primary", "dash.base", "main text, Windshield/Navigator/Drive/Exit", 7.0),
    ("text.primary", "text.primary", "dash.raised", "main text, Instruments/Road ahead/sheets", 7.0),
    ("text.secondary", "text.secondary", "dash.base", "secondary text", 4.5),
    ("text.secondary", "text.secondary", "dash.raised", "secondary text", 4.5),
    ("text.muted", "text.muted", "dash.base", "labels >= 11 sp, back links", 4.5),
    ("text.muted", "text.muted", "dash.raised", "labels >= 11 sp, Road ahead line 1", 4.5),
    ("text.note", "text.note", "dash.base", "note line", 4.5),
    ("text.note", "text.note", "dash.raised", "stop note, card description", 4.5),
    ("disabled", "text.disabled", "dash.base", "disabled glyphs", 3.0),
    ("disabled", "text.disabled", "dash.raised", "disabled glyphs", 3.0),
    ("disabled", "text.disabled", "dash.controlAlt", "disabled key glyph", 3.0),
    ("disabled", "text.disabled", "dash.control", "disabled secondary button text", 3.0),
    # text on light / yellow plates
    ("onLight", "text.onLight", "accent.yellow", "CTA plate text", 4.5),
    ("onLight", "text.onLight", "accent.yellowPressed", "pressed CTA plate text", 4.5),
    ("onLight", "text.onLight", "sign.white", "city sign, Waybill CTA, selected chip", 4.5),
    ("onLight", "text.onLightMuted", "sign.white", "Waybill CTA label, fit badge", 4.5),
    # signs (GOST, unchanged)
    ("sign text", "sign.blueText", "sign.blue", "small text on blue signs", 4.5),
    ("sign text", "sign.white", "sign.blue", "names on blue signs, HotelButton (proposed)", 4.5),
    ("sign text", "sign.white", "sign.blueSelected", "selected row (white parts)", 4.5),
    ("sign text", "sign.white", "sign.bluePressed", "pressed row text", 4.5),
    ("sign text", "accent.yellow", "sign.blueSelected", "selected row text (yellow on dark blue)", 4.5),
    ("sign text", "accent.yellow", "sign.bluePressed", "selected + pressed row text", 4.5),
    ("sign text", "sign.white", "sign.brown", "tourist sign, PresetPlate name", 4.5),
    ("sign text", "sign.blueText", "sign.brown", "PresetPlate sub (proposed repoint)", 4.5),
    ("sign text", "text.onLight", "sign.white", "pictogram plates (graphic)", 3.0),
    # yellow-as-text replaced by amber
    ("amber text", "budget.tight", "dash.base", "«Впритык»", 4.5),
    ("amber text", "budget.tight", "dash.raised", "«Впритык» on Road ahead", 4.5),
    ("amber text", "budget.tight", "sign.white", "«Впритык» on the white Waybill CTA", 4.5),
    ("amber text", "stretch.text", "stretch.fill", "«РАЗМИНКА» tag", 4.5),
    ("amber text", PROPOSED_YELLOW_TEXT, "dash.base", "proposed accent.yellowText", 4.5),
    ("amber text", PROPOSED_YELLOW_TEXT, "dash.raised", "proposed accent.yellowText: prices on Road ahead", 4.5),
    ("amber text", PROPOSED_YELLOW_TEXT, "navi.field", "proposed accent.yellowText: hotel price", 4.5),
    ("amber text", PROPOSED_YELLOW_TEXT, "navi.screen", "proposed accent.yellowText on navigator", 4.5),
    # text on controls and wells
    ("controls", "text.primary", "dash.controlAlt", "key glyph, info chip", 4.5),
    ("controls", "text.primary", "dash.control", "secondary button, report radio rows", 4.5),
    ("controls", "text.primary", "dash.face", "start label, MoodCard title", 4.5),
    ("controls", "text.secondary", "dash.face", "MoodCard sub", 4.5),
    ("controls", "text.primary", "dash.well", "well value, crew cell", 4.5),
    ("controls", "text.secondary", "dash.well", "well caption", 4.5),
    ("controls", "text.primary", "dash.pressed", "pressed row", 4.5),
    ("controls", "text.secondary", "dash.pressed", "pressed swap button", 4.5),
    ("controls", "text.primary", "dash.outline", "filled-seat label «взрослый»", 4.5),
    ("controls", "text.seatEmpty", "dash.bench", "«свободно» on the bench", 4.5),
    ("controls", "text.disabled", "dash.bench", "«нет мест» (disabled)", 3.0),
    ("controls", "text.secondary", "dash.bench", "«+ пёс» on the bench", 4.5),
    ("controls", "hours.unknown", "dash.control", "«часы не указаны» pill", 4.5),
    ("controls", "sign.white", "#1C1C1F", "odometer digits on the dark drum (proposed)", 4.5),
    # sky / mirror
    ("sky", "mirror.label", "sky.band1", "mirror caption, back link on sky", 4.5),
    ("sky", "mirror.label", "sky.band2", "back link on the lower band", 4.5),
    ("sky", "text.secondary", "sky.band1", "subtitle on sky", 4.5),
    ("sky", "text.primary", "sky.band1", "title on sky", 4.5),
    # navigator
    ("navigator", "navi.text", "navi.field", "field title, chip text", 4.5),
    ("navigator", "navi.text", "navi.screen", "distances, reason sentence", 4.5),
    ("navigator", "text.primary", "navi.listSelected", "selected suggestion name", 4.5),
    ("navigator", "navi.hint", "navi.field", "placeholder", 4.5),
    ("navigator", "navi.hint", "navi.screen", "section labels", 4.5),
    ("navigator", "navi.label", "navi.screen", "labels, secondary actions", 4.5),
    ("navigator", "navi.label", "navi.field", "«изменить»", 4.5),
    ("navigator", "navi.label", "navi.listSelected", "label on selected row", 4.5),
    ("navigator", "navi.labelSecondary", "navi.field", "field captions", 4.5),
    ("navigator", "navi.labelSecondary", "navi.screen", "sub-lines", 4.5),
    ("navigator", "navi.labelSecondary", "navi.list", "suggestion sub", 4.5),
    ("navigator", "navi.labelSecondary", "navi.listSelected", "selected suggestion sub", 4.5),
    ("navigator", "navi.label", "dash.raised", "excursion link on Road ahead", 4.5),
    ("navigator", "sign.white", "navi.label", "badge «У» letter on navi.label fill (proposed)", 4.5),
    # red / green / status text
    ("status", "accent.redText", "dash.base", "red text", 4.5),
    ("status", "accent.redText", "dash.raised", "overspend, breaks-budget", 4.5),
    ("status", "accent.redText", "dash.well", "gauge «E»", 4.5),
    ("status", "accent.redText", "dash.control", "BookCta offline «Нужен интернет»", 4.5),
    ("status", "accent.redText", "navi.screen", "offline plate", 4.5),
    ("status", "accent.redText", "budget.overFill", "«Не помещается» label", 4.5),
    ("status", "text.primary", "budget.overFill", "over-budget amount", 4.5),
    ("status", "hours.open", "hours.openFill@dash.raised", "«открыто» pill", 4.5),
    ("status", "hours.open", "dash.raised", "timed «открыто» without pill", 4.5),
    ("status", "hours.closed", "hours.closedFill@dash.raised", "«закрыто» pill", 4.5),
    ("status", "hours.closed", "dash.raised", "timed «закрыто» without pill", 4.5),
    ("status", "kind.text", "kind.fill", "category tag", 4.5),
    ("status", "text.primary", "info.fill", "info plate text", 4.5),
    ("status", "text.primary", "overlay.returnFlash@dash.raised", "row text during return flash", 4.5),
    # paper (Waybill)
    ("paper", "paper.text", "paper.sheet", "printed text", 4.5),
    ("paper", "paper.label", "paper.sheet", "printed small labels", 4.5),
    ("paper", "paper.ink", "paper.sheet", "handwriting", 4.5),
    ("paper", "paper.inkRed", "paper.sheet", "handwritten overspend", 4.5),
    ("paper", over(day["color"]["paper"]["stamp"]["value"], 0.85, day["color"]["paper"]["sheet"]["value"]), "paper.sheet", "stamp at 0.85 alpha", 4.5),
    # photos
    ("photo", "photo.credit", "photo.scrim@#FFFFFF", "credit over the scrim on a white photo (worst case)", 4.5),
    ("photo", "text.muted", "photo.mat", "placeholder caption", 4.5),
] + [("photo", "text.muted", f"photo.{k}", f"placeholder caption on {k}", 4.5)
     for k in ("phMuseum", "phChurch", "phPark", "phMonument", "phView", "phBar", "phCity")] + [
    # non-text boundaries and graphics (WCAG 1.4.11)
    ("ui 3:1", "dash.outline", "dash.raised", "outline button border", 3.0),
    ("ui 3:1", "dash.outline", "dash.base", "outline button border", 3.0),
    ("ui 3:1", "dash.outline", "dash.controlAlt", "key border (proposed) vs white key", 3.0),
    ("ui 3:1", "dash.outlineDashed", "dash.raised", "off-chip border", 3.0),
    ("ui 3:1", "dash.outlineDashed", "dash.bench", "empty-seat dashed border", 3.0),
    ("ui 3:1", "dash.outlineDashed", "dash.face", "filter chip border", 3.0),
    ("ui 3:1", "navi.fieldBorder", "navi.screen", "input border", 3.0),
    ("ui 3:1", "navi.fieldBorder", "navi.field", "input border (inside)", 3.0),
    ("ui 3:1", "navi.radio", "navi.screen", "unselected radio", 3.0),
    ("ui 3:1", "navi.radio", "navi.field", "unselected radio on field", 3.0),
    ("ui 3:1", "overlay.focus", "dash.base", "focus ring", 3.0),
    ("ui 3:1", "overlay.focus", "dash.raised", "focus ring", 3.0),
    ("ui 3:1", "overlay.focus", "navi.field", "focus ring on field", 3.0),
    ("ui 3:1", "text.onLight", "dash.base", "CTA plate 2 dp inner border vs dash", 3.0),
    ("ui 3:1", "accent.red", "dash.raised", "start ring, gauge E arc, breaks-budget dot", 3.0),
    ("ui 3:1", "accent.red", "dash.well", "gauge E arc", 3.0),
    ("ui 3:1", "budget.overBorder", "dash.raised", "over-budget plate border", 3.0),
    ("ui 3:1", "budget.tight", "sign.white", "TightDot on the white Waybill CTA", 3.0),
    ("ui 3:1", "stretch.border", "dash.raised", "«РАЗМИНКА» tag border", 3.0),
    ("ui 3:1", "kind.border", "dash.raised", "category tag border", 3.0),
    ("ui 3:1", "info.mark", "info.fill", "info plate check disc", 3.0),
    ("ui 3:1", "hours.open", "dash.raised", "«открыто» dot", 3.0),
    ("ui 3:1", "signal.green", "dash.base", "turn signal", 3.0),
    ("ui 3:1", "signal.green", "dash.raised", "turn signal", 3.0),
    ("ui 3:1", "sign.blue", "dash.raised", "blue sign plate edge on the dash", 3.0),
    ("ui 3:1", "sign.brown", "dash.raised", "tourist sign plate edge", 3.0),
]

print()
print(f"{'class':<14} {'fg':<34} {'bg':<34} {'ratio':>6} {'need':>5}  result  where")
mins = {}
for cls, fg, bg, where, need in PAIRS:
    bgh = resolve(bg)
    fgh = resolve(fg, bgh)
    r = ratio(fgh, bgh)
    ok = r >= need
    fails += 0 if ok else 1
    key = f"{cls} (>= {need:g})"
    mins[key] = min(mins.get(key, 99), r)
    fgl = fg if fg.startswith("#") else f"{fg} {fgh}"
    bgl = bg if bg.startswith("#") else f"{bg} {bgh}"
    print(f"{cls:<14} {fgl:<34} {bgl:<34} {r:6.2f} {need:5.1f}  {'PASS' if ok else 'FAIL'}    {where}")

print()
print("Minimum ratio per class:")
for k in sorted(mins):
    print(f"  {k:<26} {mins[k]:.2f}")
print()
print(f"{len(PAIRS)} pairs; {'ALL PASS' if fails == 0 else f'{fails} FAILURE(S)'}")
sys.exit(1 if fails else 0)
