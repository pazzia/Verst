#!/usr/bin/env python3
"""DES-103 acceptance: the launcher foreground (and monochrome layer) fit the adaptive-icon safe zone.

Computes the exact bounds of every pathData in a 108 x 108 VectorDrawable (lines exactly, circular arcs by
dense sampling) and checks:
  1. bounding box width and height <= 66 / 108 of the viewport (the backlog criterion), centred box [21, 87];
  2. every point lies inside the 66 dp safe-zone circle (radius 33 around 54, 54), which is stricter.
Usage: python3 design/tools/check_icon.py [file.xml ...]   (default: foreground + monochrome)
"""
from __future__ import annotations

import math
import os
import re
import sys
import xml.dom.minidom

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT = [os.path.join(ROOT, 'android', 'app', 'src', 'main', 'res', 'drawable', n)
           for n in ('ic_launcher_foreground.xml', 'ic_launcher_monochrome.xml')]
VIEW, SAFE = 108.0, 66.0
TOK = re.compile(r'[MmLlHhVvAaZz]|-?(?:\d+\.?\d*|\.\d+)')


def arc_points(p0, p1, r, large, sweep, n=64):
    (x1, y1), (x2, y2) = p0, p1
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    d2 = dx * dx + dy * dy
    if d2 == 0:
        return []
    r = max(r, math.sqrt(d2))
    k = math.sqrt(max(0.0, (r * r - d2) / d2)) * (-1 if large == sweep else 1)
    cx, cy = k * dy + (x1 + x2) / 2, -k * dx + (y1 + y2) / 2
    a0, a1 = math.atan2(y1 - cy, x1 - cx), math.atan2(y2 - cy, x2 - cx)
    span = (a1 - a0) % (2 * math.pi) if sweep else -((a0 - a1) % (2 * math.pi))
    return [(cx + r * math.cos(a0 + span * t / n), cy + r * math.sin(a0 + span * t / n)) for t in range(n + 1)]


def points(d: str):
    toks = TOK.findall(d); i = 0; cur = (0.0, 0.0); start = cur; pts = []; cmd = None
    def num():
        nonlocal i; v = float(toks[i]); i += 1; return v
    while i < len(toks):
        if re.match(r'[A-Za-z]', toks[i]):
            cmd = toks[i]; i += 1
        rel = cmd.islower(); C = cmd.upper(); ox, oy = cur if rel else (0.0, 0.0)
        if C in 'ML':
            cur = (ox + num(), oy + num())
            if C == 'M': start = cur
            pts.append(cur)
        elif C == 'H':
            x = num(); cur = ((cur[0] + x) if rel else x, cur[1]); pts.append(cur)
        elif C == 'V':
            y = num(); cur = (cur[0], (cur[1] + y) if rel else y); pts.append(cur)
        elif C == 'A':
            rx = num(); num(); num(); la = int(num()); sw = int(num()); nxt = (ox + num(), oy + num())
            pts += arc_points(cur, nxt, rx, la, sw); cur = nxt
        elif C == 'Z':
            cur = start
    return pts


def check(path: str) -> bool:
    dom = xml.dom.minidom.parse(path)
    v = dom.documentElement
    assert float(v.getAttribute('android:viewportWidth')) == VIEW and float(v.getAttribute('android:viewportHeight')) == VIEW
    pts = [p for e in dom.getElementsByTagName('path') for p in points(e.getAttribute('android:pathData'))]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    rmax = max(math.hypot(x - 54, y - 54) for x, y in pts)
    lo, hi = (VIEW - SAFE) / 2, (VIEW + SAFE) / 2
    ok_box = w <= SAFE and h <= SAFE and min(xs) >= lo and max(xs) <= hi and min(ys) >= lo and max(ys) <= hi
    ok_circle = rmax <= SAFE / 2
    print('%s: bounds x %.2f..%.2f y %.2f..%.2f (%.2f x %.2f dp = %.3f x %.3f of the viewport, limit %.3f); '
          'max radius %.2f dp (limit 33) -> %s'
          % (os.path.basename(path), min(xs), max(xs), min(ys), max(ys), w, h, w / VIEW, h / VIEW, SAFE / VIEW, rmax,
             'PASS' if ok_box and ok_circle else 'FAIL'))
    return ok_box and ok_circle


if __name__ == '__main__':
    files = sys.argv[1:] or DEFAULT
    sys.exit(0 if all([check(f) for f in files]) else 1)
