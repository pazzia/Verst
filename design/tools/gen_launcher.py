#!/usr/bin/env python3
"""BRAND-01 → BRAND-02 (CEO 31.10.2026): the launcher icon «Кемпер в лесу на закате».

The CEO's picture redrawn as vectors: a cream camper van with an over-cab alcove, whose wheels are orange map
pins, in front of a large pale sun in an orange dusk forest (dark trunks and branches at the edges, dark ground).
Writes into android/app/src/main/res/:
  mipmap-anydpi-v26/ic_launcher.xml, mipmap-anydpi-v26/ic_launcher_round.xml
  drawable/ic_launcher_background.xml   full-bleed scene: glow rings, sun, far and near trunks, branches, ground
  drawable/ic_launcher_foreground.xml   the camper with its pin wheels, inside the 66 dp safe zone
  drawable/ic_launcher_monochrome.xml   themed-icon layer (Android 13+): the camper silhouette, one colour
and design/brand/verst-icon.svg (the same composition as a plain SVG: store art, the landing, documents).
Replaces concept «В» «Солнце над трассой» (D-IR-22, 28.10).

Geometry: 108 x 108 dp viewport; launchers show about the centred 72 dp; safe zone = circle r 33 at 54, 54.
The van spans x 26.5…80, y 34…74.5. Checked by design/tools/check_icon.py (foreground + monochrome).

Usage: python3 design/tools/gen_launcher.py [--check]
"""
from __future__ import annotations

import difflib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES = os.path.join(ROOT, 'android', 'app', 'src', 'main', 'res')
BRAND = os.path.join(ROOT, 'design', 'brand')

# the CEO's picture (31.10): dusk orange, a pale sun, brown forest, cream van, orange-red pins
GLOW = ('#FFD9692F', '#FFE47A3A', '#FFEC8C47', '#FFF19F57')   # outer → inner rings of the sky
SUN = '#FFF6BE7E'
FAR_TREE, NEAR_TREE, GROUND = '#FFB0552E', '#FF4A1D15', '#FF3A1510'
OUTLINE, CREAM, PEACH, STRIPE = '#FF3B2824', '#FFEEDFC6', '#FFF2B98A', '#FFC86A38'
CHASSIS, PIN, PIN_DOT, WHITE = '#FFA39C95', '#FFD9573A', '#FFFFF4E4', '#FFFFFFFF'


def f(v: float) -> str:
    s = ('%.3f' % v).rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def rect(x: float, y: float, w: float, h: float) -> str:
    return 'M%s %sH%sV%sH%sZ' % (f(x), f(y), f(x + w), f(y + h), f(x))


def poly(*pts: tuple[float, float]) -> str:
    return 'M' + 'L'.join('%s %s' % (f(x), f(y)) for x, y in pts) + 'Z'


def rrect(x: float, y: float, w: float, h: float, r: float) -> str:
    """Rounded rectangle (circular arcs: VectorDrawable and check_icon.py both read A)."""
    return ('M%s %sH%sA%s %s 0 0 1 %s %sV%sA%s %s 0 0 1 %s %sH%sA%s %s 0 0 1 %s %sV%sA%s %s 0 0 1 %s %sZ'
            % (f(x + r), f(y), f(x + w - r), f(r), f(r), f(x + w), f(y + r), f(y + h - r), f(r), f(r),
               f(x + w - r), f(y + h), f(x + r), f(r), f(r), f(x), f(y + h - r), f(y + r), f(r), f(r),
               f(x + r), f(y)))


def circle(cx: float, cy: float, r: float) -> str:
    return 'M%s %sA%s %s 0 1 1 %s %sA%s %s 0 1 1 %s %sZ' % (
        f(cx - r), f(cy), f(r), f(r), f(cx + r), f(cy), f(r), f(r), f(cx - r), f(cy))


def pin(cx: float, cy: float, r: float, tip: float) -> str:
    """A map pin: the upper circle and a point at y = tip."""
    return 'M%s %sA%s %s 0 1 1 %s %sL%s %sZ' % (f(cx - r), f(cy), f(r), f(r), f(cx + r), f(cy), f(cx), f(tip))


def grow(d: list[float], k: float) -> list[float]:
    """x, y, w, h (, r) grown by k on every side (the dark outline under a cream shape)."""
    x, y, w, h, *r = d
    return [x - k, y - k, w + 2 * k, h + 2 * k, *[v + k for v in r]]


# --- the van (foreground) -------------------------------------------------------------------------------
LINE = 1.3                                         # outline width
BOX = [28.0, 38.0, 42.0, 23.0, 3.0]                # living box x, y, w, h, r
ALCOVE = [58.0, 37.0, 19.0, 9.5, 4.0]              # over-cab alcove
CAB = ((64.0, 46.0), (73.5, 46.0), (80.0, 54.5), (80.0, 61.0), (64.0, 61.0))
CAB_WINDOW = ((68.0, 48.0), (72.6, 48.0), (77.0, 54.0), (68.0, 54.0))
WHEELS = (38.0, 70.0)                              # pin centres x; circle centre y 63
PIN_R, PIN_TIP = 4.6, 72.5


def van() -> list[tuple[str, str]]:
    def outline_poly(pts: tuple[tuple[float, float], ...], k: float) -> str:
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        return poly(*[(x + (k if x > cx else -k), y + (k if y > cy else -k)) for x, y in pts])

    dark = (rrect(*grow(BOX, LINE)) + rrect(*grow(ALCOVE, LINE)) + outline_poly(CAB, LINE)
            + rect(34.0, 34.4, 18.0, 2.2) + rect(26.5, 48.0, 3.0, 12.5)          # roof rack, rear bumper
            + rect(28.0 - LINE, 59.5 - LINE, 53.0 + 2 * LINE, 4.0 + 2 * LINE))   # chassis outline
    cream = rrect(*BOX) + rrect(*ALCOVE) + poly(*CAB)
    windows_dark = (rrect(*grow([32.5, 43.5, 13.0, 7.0, 1.5], 1.0)) + rrect(*grow([61.5, 39.2, 9.0, 4.2, 1.5], 0.9))
                    + outline_poly(CAB_WINDOW, 1.0) + rrect(*grow([49.5, 43.0, 7.0, 17.0, 1.2], 1.0)))
    peach = rrect(32.5, 43.5, 13.0, 7.0, 1.5) + rrect(61.5, 39.2, 9.0, 4.2, 1.5) + poly(*CAB_WINDOW)
    door = rrect(49.5, 43.0, 7.0, 17.0, 1.2)
    door_window = rrect(51.0, 45.0, 4.0, 4.5, 0.8)
    stripes = rect(30.0, 40.6, 26.0, 0.9) + rect(30.0, 54.6, 18.5, 0.9) + rect(58.0, 54.6, 20.0, 0.9)
    chassis = rect(28.0, 59.5, 53.0, 4.0)
    pins_dark = ''.join(pin(x, 63.0, PIN_R + LINE, PIN_TIP + 1.8) for x in WHEELS)
    pins = ''.join(pin(x, 63.0, PIN_R, PIN_TIP) for x in WHEELS)
    dots = ''.join(circle(x, 63.0, 2.0) for x in WHEELS)
    return [(OUTLINE, dark), (CREAM, cream), (OUTLINE, windows_dark), (PEACH, peach), (CREAM, door),
            (OUTLINE, rrect(*grow([51.0, 45.0, 4.0, 4.5, 0.8], 0.8))), (PEACH, door_window),
            (STRIPE, stripes), (CHASSIS, chassis), (OUTLINE, pins_dark), (PIN, pins), (PIN_DOT, dots)]


def van_silhouette() -> str:
    """The themed layer: the van's outer shape and its pins, one colour."""
    return (rrect(*grow(BOX, LINE)) + rrect(*grow(ALCOVE, LINE)) + poly(*CAB) + rect(34.0, 34.4, 18.0, 2.2)
            + rect(26.5, 48.0, 3.0, 12.5) + rect(26.7, 58.2, 55.6, 6.6)
            + ''.join(pin(x, 63.0, PIN_R + LINE, PIN_TIP + 1.8) for x in WHEELS))


# --- the forest at dusk (background) ---------------------------------------------------------------------
def forest() -> list[tuple[str, str]]:
    glow = [(GLOW[0], rect(0, 0, 108, 108))] + [(c, circle(54, 46, r)) for c, r in zip(GLOW[1:], (58, 46, 36))]
    sun = [(SUN, circle(54, 44, 22))]
    # the launcher shows about x, y 18…90: the near trunks stand inside it, like the picture's
    far = poly((31, 0), (34, 0), (35, 72), (30, 72)) + poly((74, 0), (77, 0), (78, 72), (73, 72))
    near = (poly((13, 0), (24, 0), (25.5, 108), (11, 108)) + poly((84, 0), (95, 0), (97, 108), (82.5, 108))
            + poly((0, 0), (40, 0), (24, 14), (0, 24))            # canopy corners
            + poly((108, 0), (68, 0), (84, 14), (108, 24))
            + poly((24, 30), (38, 20), (39.5, 22.5), (24.5, 35))  # branches
            + poly((84, 30), (70, 20), (68.5, 22.5), (83.5, 35))
            + poly((24.5, 50), (30, 46), (31, 48.2), (25, 53.5)))
    ground = poly((0, 71), (30, 69), (78, 69), (108, 71), (108, 108), (0, 108))
    return glow + sun + [(FAR_TREE, far), (NEAR_TREE, near), (GROUND, ground)]


def layers() -> dict[str, list[tuple[str, str]]]:
    return {'background': forest(), 'foreground': van(), 'monochrome': [(WHITE, van_silhouette())]}


VEC_HEAD = ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<!-- GENERATED by design/tools/gen_launcher.py (BRAND-02). Do not edit. -->\n'
            '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
            '    android:width="108dp"\n    android:height="108dp"\n'
            '    android:viewportWidth="108"\n    android:viewportHeight="108">\n')


def path(color: str, d: str) -> str:
    return '    <path\n        android:fillColor="%s"\n        android:fillType="nonZero"\n        android:pathData="%s" />\n' % (color, d)


def vector(items: list[tuple[str, str]]) -> str:
    return VEC_HEAD + ''.join(path(c, d) for c, d in items) + '</vector>\n'


def svg() -> str:
    """The composed icon as a plain SVG (background then foreground), colours as #RRGGBB."""
    items = layers()['background'] + layers()['foreground']
    body = ''.join('  <path fill="#%s" d="%s"/>\n' % (c[3:], d) for c, d in items)
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<!-- GENERATED by design/tools/gen_launcher.py (BRAND-02). «Верста»: кемпер в лесу на закате. -->\n'
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108" width="1080" height="1080">\n'
            + body + '</svg>\n')


def outputs() -> dict[str, str]:
    lay = layers()
    adaptive = ('<?xml version="1.0" encoding="utf-8"?>\n'
                '<!-- GENERATED by design/tools/gen_launcher.py (BRAND-02). Do not edit. -->\n'
                '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
                '    <background android:drawable="@drawable/ic_launcher_background" />\n'
                '    <foreground android:drawable="@drawable/ic_launcher_foreground" />\n'
                '    <monochrome android:drawable="@drawable/ic_launcher_monochrome" />\n'
                '</adaptive-icon>\n')
    return {
        'mipmap-anydpi-v26/ic_launcher.xml': adaptive,
        'mipmap-anydpi-v26/ic_launcher_round.xml': adaptive,
        'drawable/ic_launcher_background.xml': vector(lay['background']),
        'drawable/ic_launcher_foreground.xml': vector(lay['foreground']),
        'drawable/ic_launcher_monochrome.xml': vector(lay['monochrome']),
        os.path.join('..', '..', '..', '..', '..', 'design', 'brand', 'verst-icon.svg'): svg(),
    }


def main() -> int:
    check = '--check' in sys.argv
    stale = False
    for rel, text in outputs().items():
        p = os.path.join(RES, rel)
        if check:
            old = open(p, encoding='utf-8').read() if os.path.exists(p) else ''
            if old != text:
                stale = True
                sys.stdout.writelines(difflib.unified_diff(old.splitlines(True), text.splitlines(True), rel + ' (committed)', rel + ' (generated)'))
        else:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'w', encoding='utf-8').write(text)
            print('wrote', os.path.relpath(p, ROOT))
    if check:
        print('gen_launcher --check: %s' % ('STALE' if stale else 'up to date'))
        return 1 if stale else 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
