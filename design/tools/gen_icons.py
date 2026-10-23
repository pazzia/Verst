#!/usr/bin/env python3
"""Generate design/icons/*.svg (DES-002): single-colour, stroke-free 24x24 icons.

Icons are authored as stroke centre-lines (the same path data as components.md §17,
taken from the approved canvases) and converted here to exact filled outlines:
every line segment becomes a rectangle, every circular arc an annular sector,
every vertex a round cap/join disc. All shapes are emitted with the same winding
(positive / clockwise on screen), so the default nonzero fill rule unions them;
ring holes are emitted with the opposite winding. Output = one <path> per file.

Run:  python3 design/tools/gen_icons.py      (writes design/icons/*.svg)
"""
from __future__ import annotations
import math, os, re

OUT = os.path.join(os.path.dirname(__file__), '..', 'icons')
FILL = '#141416'  # color.sign.black; tinted at use (ImageVector tint)

# ---------------------------------------------------------------- path parsing
TOK = re.compile(r'[MmLlHhVvCcAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?')

def parse(d):
    toks = TOK.findall(d); i = 0; cmd = None
    cur = (0.0, 0.0); start = cur; segs = []; pts_seen = []
    def num():
        nonlocal i; v = float(toks[i]); i += 1; return v
    while i < len(toks):
        if re.match(r'[A-Za-z]', toks[i]): cmd = toks[i]; i += 1
        c = cmd; rel = c.islower(); C = c.upper()
        ox, oy = cur if rel else (0.0, 0.0)
        if C == 'M':
            cur = (ox + num(), oy + num()); start = cur; pts_seen.append(cur)
            cmd = 'l' if rel else 'L'
        elif C == 'L':
            p = (ox + num(), oy + num()); segs.append(('L', cur, p)); cur = p
        elif C == 'H':
            x = num(); p = ((cur[0] + x) if rel else x, cur[1]); segs.append(('L', cur, p)); cur = p
        elif C == 'V':
            y = num(); p = (cur[0], (cur[1] + y) if rel else y); segs.append(('L', cur, p)); cur = p
        elif C == 'C':
            c1 = (ox + num(), oy + num()); c2 = (ox + num(), oy + num()); p = (ox + num(), oy + num())
            segs.append(('C', cur, c1, c2, p)); cur = p
        elif C == 'A':
            rx = num(); ry = num(); num(); large = int(num()); sweep = int(num()); p = (ox + num(), oy + num())
            assert abs(rx - ry) < 1e-9, 'only circular arcs'
            segs.append(('A', cur, p, rx, large, sweep)); cur = p
        elif C == 'Z':
            if cur != start: segs.append(('L', cur, start))
            cur = start
    return segs

# ---------------------------------------------------------------- geometry helpers
def f(v):
    s = ('%.3f' % v).rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s

def P(p): return f(p[0]) + ' ' + f(p[1])

def area(poly):
    return sum(poly[k][0] * poly[(k + 1) % len(poly)][1] - poly[(k + 1) % len(poly)][0] * poly[k][1] for k in range(len(poly))) / 2

def rect(p0, p1, h):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]; L = math.hypot(dx, dy)
    if L < 1e-9: return None
    nx, ny = -dy / L * h, dx / L * h
    poly = [(p0[0] + nx, p0[1] + ny), (p1[0] + nx, p1[1] + ny), (p1[0] - nx, p1[1] - ny), (p0[0] - nx, p0[1] - ny)]
    if area(poly) < 0: poly.reverse()
    return 'M' + 'L'.join(P(q) for q in poly) + 'Z'

def disc(c, r, positive=True):
    s = 1 if positive else 0
    a = (c[0] + r, c[1]); b = (c[0] - r, c[1])
    return 'M%sA%s %s 0 1 %d %sA%s %s 0 1 %d %sZ' % (P(a), f(r), f(r), s, P(b), f(r), f(r), s, P(a))

def arc_center(p0, p1, r, large, sweep):
    x1, y1 = p0; x2, y2 = p1
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    d2 = dx * dx + dy * dy
    r = max(r, math.sqrt(d2))
    k = math.sqrt(max(0.0, (r * r - d2) / d2)) if d2 else 0
    if large == sweep: k = -k
    cx = k * dy + (x1 + x2) / 2; cy = -k * dx + (y1 + y2) / 2
    return (cx, cy), r

def ang(c, p): return math.atan2(p[1] - c[1], p[0] - c[0])

def sector(c, r, a0, a1, sweep, h):
    """Annular sector of the stroke of a circular arc from a0 to a1 (sweep as SVG)."""
    # sweep 1 = increasing angle (clockwise on screen). Normalise so we always emit sweep 1.
    if sweep == 0: a0, a1 = a1, a0
    span = (a1 - a0) % (2 * math.pi)
    large = 1 if span > math.pi else 0
    ro, ri = r + h, r - h
    po0 = (c[0] + ro * math.cos(a0), c[1] + ro * math.sin(a0)); po1 = (c[0] + ro * math.cos(a1), c[1] + ro * math.sin(a1))
    pi1 = (c[0] + ri * math.cos(a1), c[1] + ri * math.sin(a1)); pi0 = (c[0] + ri * math.cos(a0), c[1] + ri * math.sin(a0))
    if ri <= 1e-6:
        return 'M%sA%s %s 0 %d 1 %sL%sZ' % (P(po0), f(ro), f(ro), large, P(po1), P(c))
    return 'M%sA%s %s 0 %d 1 %sL%sA%s %s 0 %d 0 %sZ' % (P(po0), f(ro), f(ro), large, P(po1), P(pi1), f(ri), f(ri), large, P(pi0))

def bez(p0, c1, c2, p1, t):
    u = 1 - t
    return (u**3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t**3 * p1[0],
            u**3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t**3 * p1[1])

def outline(d, width):
    h = width / 2; parts = []; nodes = []
    for s in parse(d):
        if s[0] == 'L':
            r_ = rect(s[1], s[2], h)
            if r_: parts.append(r_)
            nodes += [s[1], s[2]]
        elif s[0] == 'C':
            pts = [bez(s[1], s[2], s[3], s[4], k / 16) for k in range(17)]
            for a, b in zip(pts, pts[1:]):
                r_ = rect(a, b, h)
                if r_: parts.append(r_)
            nodes += pts
        elif s[0] == 'A':
            c, r = arc_center(s[1], s[2], s[3], s[4], s[5])
            parts.append(sector(c, r, ang(c, s[1]), ang(c, s[2]), s[5], h))
            nodes += [s[1], s[2]]
    seen = set()
    for n in nodes:
        k = (round(n[0], 3), round(n[1], 3))
        if k in seen: continue
        seen.add(k); parts.append(disc(n, h))
    return parts

def ring(c, r, width):
    h = width / 2
    return [disc(c, r + h, True), disc(c, r - h, False)]

def rrect(x, y, w, hgt, rt, rb, rot=0.0, pivot=None):
    """Filled rounded rect (top radius rt, bottom radius rb), optionally rotated (deg) about pivot."""
    # CSS clamps corner radii to half the side; do the same (the mockup ear is 9 wide with radius 5)
    rt = min(rt, w / 2, hgt / 2); rb = min(rb, w / 2, hgt / 2)
    seq = [('M', (x + rt, y)), ('L', (x + w - rt, y)), ('A', (x + w, y + rt), rt), ('L', (x + w, y + hgt - rb)),
           ('A', (x + w - rb, y + hgt), rb), ('L', (x + rb, y + hgt)), ('A', (x, y + hgt - rb), rb), ('L', (x, y + rt)), ('A', (x + rt, y), rt)]
    px, py = pivot if pivot else (x + w / 2, y + hgt / 2)
    t = math.radians(rot)
    def R(p):
        dx, dy = p[0] - px, p[1] - py
        return (px + dx * math.cos(t) - dy * math.sin(t), py + dx * math.sin(t) + dy * math.cos(t))
    out = ''
    for item in seq:
        if item[0] == 'M': out += 'M' + P(R(item[1]))
        elif item[0] == 'L': out += 'L' + P(R(item[1]))
        else:
            if item[2] > 0: out += 'A%s %s 0 0 1 %s' % (f(item[2]), f(item[2]), P(R(item[1])))
            else: out += 'L' + P(R(item[1]))
    return out + 'Z'   # clockwise on screen = positive

# ---------------------------------------------------------------- icon sources
ARROW_W = 3.0      # stroke.icon.sign
SERVICE_W = 2.2    # stroke.icon.pictogram
TOURIST_W = 2.0    # stroke.icon.thin

ICONS = {}
def stroke_icon(name, d, w, extra=()):
    ICONS[name] = outline(d, w) + list(extra)

# Arrows (components §17.1; up / upRight / down / downLeft verbatim from Wind.dc.html,
# right from the CTA arrows, left from the back links, downRight from Exit.dc.html, upLeft mirrored)
ARROWS = {
    'arrow-up': 'M12 20V4M5 11l7-7 7 7',
    'arrow-up-right': 'M7 17L17 7M9 7h8v8',
    'arrow-right': 'M4 12h16M13 5l7 7-7 7',
    'arrow-down-right': 'M7 7l10 10M17 9v8H9',
    'arrow-down': 'M12 4v16M5 13l7 7 7-7',
    'arrow-down-left': 'M17 7L7 17M15 17H7V9',
    'arrow-left': 'M20 12H4M11 5l-7 7 7 7',
    'arrow-up-left': 'M17 17L7 7M15 7H7v8',
}
for k, d in ARROWS.items(): stroke_icon(k, d, ARROW_W)

# Service pictograms (verbatim from Signs.dc.html)
stroke_icon('service-fuel', 'M4 20V5a1 1 0 0 1 1-1h7a1 1 0 0 1 1 1v15M3 20h11M5 9h7M13 8l3 2v7a1.5 1.5 0 0 0 3 0V9l-3-3', SERVICE_W)
stroke_icon('service-food', 'M7 3v8a2 2 0 0 0 2 2v8M5 3v5M9 3v5M16 21V3c2.5 1 4 3.5 4 7h-4', SERVICE_W)
stroke_icon('service-rest', 'M12 3l-5 8h3l-4 6h12l-4-6h3zM12 17v4', SERVICE_W)
stroke_icon('service-hotel', 'M3 18V8M3 14h18v4M21 14v-2a3 3 0 0 0-3-3h-7v5', SERVICE_W, ring((7, 11), 2, SERVICE_W))

# Tourist pictograms
stroke_icon('tourist-monastery', 'M12 2v3M10.5 3.5h3M8 21V12l4-4 4 4v9M5 21h14M10 21v-4a2 2 0 0 1 4 0v4', TOURIST_W)  # verbatim canvas
stroke_icon('tourist-kremlin', 'M3 21h18M9 21V10h6v11M9 10l3-6 3 6M12 4V2M5 21v-6h4M15 15h4v6M5 15v-2M7 15v-2M17 15v-2M19 15v-2M11 21v-3h2v3', TOURIST_W)
stroke_icon('tourist-museum', 'M3 21h18M4 10h16M12 3l9 5H3zM6 10v8M10 10v8M14 10v8M18 10v8M4 18h16', TOURIST_W)
stroke_icon('tourist-view', 'M3 19l6-9 4 5 3-4 5 8z', TOURIST_W, ring((17, 5.5), 2, TOURIST_W))
stroke_icon('tourist-walk', 'M12.5 8L10 14l3 3v4M10 14l-2.5 7M12.5 8l3 3.5H19M12.5 8L9 10l-1.5 3', TOURIST_W, [disc((13, 4.5), 2.2)])
stroke_icon('tourist-generic', 'M12 3l2 3v12h-4V6zM7 21h10M8.5 21v-3h7v3', TOURIST_W)

# Crew silhouettes (filled; proportions from the mirror silhouettes in Wind/Panel.dc.html)
def person(scale):
    # mockup adult box 26: head d12, gap 1, body 24 x 12 with top radius 10 -> scaled into 24 box
    k = 24 / 26 * scale; ox = 12 - 13 * k; oy = 24 - 26 * k
    head = disc((ox + 13 * k, oy + 6 * k), 6 * k)
    body = rrect(ox + 1 * k, oy + 13 * k, 24 * k, 13 * k, 10 * k, 0)
    return [head, body]
ICONS['crew-adult'] = person(1.0)
ICONS['crew-child'] = person(20 / 26)  # child silhouette is 20/26 of the adult (Wind.dc.html), bottom-aligned
# Dog (Panel.dc.html large mirror dog: body 32x26 radius 14/10, ears 9x14 radius 5 at +-18 deg), box 32 -> 24
k = 0.75
ICONS['crew-dog'] = [
    rrect(0, 6 * k, 32 * k, 26 * k, 14 * k, 10 * k),
    rrect(6 * k, 0, 9 * k, 14 * k, 5 * k, 5 * k, rot=-18),
    rrect(32 * k - 6 * k - 9 * k, 0, 9 * k, 14 * k, 5 * k, 5 * k, rot=18),
]

SOURCES = {k: v for k, v in list(ARROWS.items())}

def write():
    os.makedirs(OUT, exist_ok=True)
    for name, parts in sorted(ICONS.items()):
        d = ''.join(parts)
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
               '<path fill="%s" d="%s"/></svg>\n') % (FILL, d)
        open(os.path.join(OUT, name + '.svg'), 'w').write(svg)
    print('wrote %d icons to %s' % (len(ICONS), os.path.normpath(OUT)))

if __name__ == '__main__':
    write()
