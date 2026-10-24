#!/usr/bin/env python3
"""DES-106: sample CI screenshots against design/qa/<screen>.json (stdlib + PIL).

  python3 design/tools/qa_sample.py <screenshots_dir> <screen>   e.g. /tmp/ci/runs/R/screenshots 5.1-windshield
  python3 design/tools/qa_sample.py --self-test
  python3 design/tools/qa_sample.py --coverage                   checklist items not covered by any point
  python3 design/tools/qa_sample.py --write-theme                regenerate design/qa/theme.json from tokens.json

Screenshots: <dir>/<screen>/<state>@<size>.png at density 3 (dp x 3 = px), as architecture-android-mvp §8.2.

Point kinds (all coordinates in dp; "state" defaults to "default", "size" to "390x844"):
  colour   {"item","x","y","hex"[,"tol":1]}         exact match (tol 0), or ±tol per channel (alpha tokens)
  edge     {"item","kind":"edge","y"|"x", "seed", "match":[hex..], "expect":[start|null, end|null], "tol_dp"}
           scans the row y (or column x) and finds the run of pixels whose colour is in `match` (±match_tol)
           that contains `seed`; compares its first / one-past-last coordinate with `expect`
  present  {"item","kind":"present","region":[x,y,w,h],"hex","min_px"[,"tol"]}  colour occurs >= min_px times
  absent   {"item","kind":"absent","region":[...],"hex"[,"tol"]}               colour does not occur
  text     {"item","kind":"text","region":[x,y,w,h][,"min_px":40]}             region is not uniform (text drawn)
A colour sample must lie >= 2 px inside the element (enforced by the point authors, not by the tool).

Output: "PASS <screen> 0 failures" or one line per failure in the checklist format
        "[screen] [item id] expected <...> / actual <...> / <screenshot path>", exit 1.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import tempfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QA = os.path.join(ROOT, 'design', 'qa')
CHECKLIST = os.path.join(ROOT, 'design', 'visual-qa-checklist.md')
TOKENS = os.path.join(ROOT, 'design', 'tokens.json')
DENSITY = 3


def rgb(hexv: str) -> tuple[int, int, int]:
    h = hexv.lstrip('#')
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def hx(c) -> str:
    return '#%02X%02X%02X' % tuple(c[:3])


def close(a, b, tol: int) -> bool:
    return all(abs(int(x) - int(y)) <= tol for x, y in zip(a[:3], b[:3]))


class Shots:
    def __init__(self, base: str, screen: str):
        self.base, self.screen, self.cache = base, screen, {}

    # CI writes screenshots/<package dir>/ (windshield, navigator, …); accept both that and <screen id>/
    ALIASES = {'5.1-windshield': 'windshield', '5.2-navigator': 'navigator', '5.3-instruments': 'instruments',
               '5.4-drive': 'drive', '5.5-road-ahead': 'road', '5.6-waybill': 'waybill', '5.7-exit': 'exit'}

    def path(self, p: dict) -> str:
        name = '%s@%s.png' % (p.get('state', 'default'), p.get('size', '390x844'))
        own = os.path.join(self.base, self.screen, name)
        alias = os.path.join(self.base, self.ALIASES.get(self.screen, self.screen), name)
        return own if os.path.isdir(os.path.join(self.base, self.screen)) or not os.path.exists(alias) else alias

    def get(self, p: dict):
        path = self.path(p)
        if path not in self.cache:
            self.cache[path] = Image.open(path).convert('RGB') if os.path.exists(path) else None
        return self.cache[path], path


def px(v: float) -> int:
    return int(round(v * DENSITY))


def evaluate(p: dict, im) -> tuple[bool, str, str]:
    kind = p.get('kind', 'colour')
    W, H = im.size
    if kind == 'colour':
        x, y = px(p['x']), px(p['y'])
        if not (0 <= x < W and 0 <= y < H):
            return False, p['hex'], 'outside the image (%d,%d)' % (x, y)
        got = im.getpixel((x, y))
        return close(got, rgb(p['hex']), p.get('tol', 0)), '%s at (%s,%s)' % (p['hex'], p['x'], p['y']), hx(got)
    if kind == 'edge':
        cols = [rgb(h) for h in p['match']]; mt = p.get('match_tol', 0)
        ok_px = lambda c: any(close(c, m, mt) for m in cols)
        horiz = 'y' in p
        fixed = px(p['y'] if horiz else p['x'])
        n = W if horiz else H
        get = (lambda i: im.getpixel((i, fixed))) if horiz else (lambda i: im.getpixel((fixed, i)))
        seed = px(p['seed'])
        if not ok_px(get(seed)):
            return False, 'run of %s containing %s' % (p['match'], p['seed']), 'seed pixel is %s' % hx(get(seed))
        a = seed
        while a > 0 and ok_px(get(a - 1)):
            a -= 1
        b = seed
        while b < n - 1 and ok_px(get(b + 1)):
            b += 1
        start, end = a / DENSITY, (b + 1) / DENSITY
        tol = p.get('tol_dp', 1)
        exp = p['expect']
        ok = (exp[0] is None or abs(start - exp[0]) <= tol) and (exp[1] is None or abs(end - exp[1]) <= tol)
        return ok, '%s %s ±%s dp' % ('x' if horiz else 'y', exp, tol), '[%.2f, %.2f]' % (start, end)
    if kind in ('present', 'absent', 'text'):
        x, y, w, h = p['region']
        box = im.crop((px(x), px(y), px(x + w), px(y + h)))
        raw = box.tobytes()
        data = [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]
        if kind == 'text':
            counts: dict = {}
            for c in data:
                counts[c] = counts.get(c, 0) + 1
            dom = max(counts, key=counts.get)
            other = sum(v for c, v in counts.items() if not close(c, dom, 48))
            need = p.get('min_px', 40)
            return other >= need, 'text in %s (>= %d contrasting px)' % (p['region'], need), '%d px' % other
        target, tol = rgb(p['hex']), p.get('tol', 0)
        n = sum(1 for c in data if close(c, target, tol))
        if kind == 'present':
            return n >= p['min_px'], '%s >= %d px in %s' % (p['hex'], p['min_px'], p['region']), '%d px' % n
        return n == 0, 'no %s in %s' % (p['hex'], p['region']), '%d px' % n
    raise ValueError('unknown kind %r' % kind)


def run(base: str, screen: str) -> int:
    spec = json.load(open(os.path.join(QA, screen + '.json'), encoding='utf-8'))
    shots = Shots(base, screen)
    fails = []
    for p in spec['points']:
        im, path = shots.get(p)
        if im is None:
            fails.append('[%s] [%s] expected screenshot / actual missing / %s' % (screen, p['item'], path))
            continue
        ok, exp, act = evaluate(p, im)
        if not ok:
            fails.append('[%s] [%s] expected %s / actual %s / %s' % (screen, p['item'], exp, act, path))
    if fails:
        print('\n'.join(fails))
        print('FAIL %s %d failures (%d points)' % (screen, len(fails), len(spec['points'])))
        return 1
    print('PASS %s 0 failures (%d points)' % (screen, len(spec['points'])))
    return 0


# ------------------------------------------------------------------ theme (DEV-105 palette layout)
def color_leaves():
    t = json.load(open(TOKENS, encoding='utf-8'))
    out = []
    def walk(d, path):
        for k, v in d.items():
            if isinstance(v, dict) and isinstance(v.get('value'), str) and v['value'].startswith('#'):
                out.append(('.'.join(path + [k]), v['value'].upper(), float(v.get('alpha', 1.0))))
            elif isinstance(v, dict):
                walk(v, path + [k])
    walk(t['color'], ['color'])
    return out


PALETTE = {'columns': 6, 'cell_w': 65, 'cell_h': 60, 'swatch': [6, 4, 53, 30], 'background': '#141416',
           'label': 'token path under the swatch, 8 sp, color.text.secondary, 2 lines max (not sampled)'}


def composite(hexv: str, a: float, bg: str) -> str:
    f, b = rgb(hexv), rgb(bg)
    return hx(tuple(int(round(f[i] * a + b[i] * (1 - a))) for i in range(3)))


def write_theme() -> None:
    pts = []
    L = PALETTE
    for i, (path, hexv, a) in enumerate(color_leaves()):
        col, row = i % L['columns'], i // L['columns']
        sx, sy, sw, sh = L['swatch']
        x = col * L['cell_w'] + sx + sw / 2
        y = row * L['cell_h'] + sy + sh / 2
        p = {'item': path, 'state': 'palette', 'x': x, 'y': y, 'hex': hexv if a == 1 else composite(hexv, a, L['background'])}
        if a != 1:
            p['tol'] = 1
            p['alpha'] = a
        pts.append(p)
    doc = {'screen': 'theme',
           'notes': ('DEV-105 palette@390x844: one swatch per DesignTokens.color leaf in token order (tokens.json order), '
                     'laid out by `layout`: cell (col = i %% 6, row = i // 6) at (col * 65, row * 60) dp, swatch rect at '
                     '+(6, 4) size 53 x 30 dp, filled with the token colour (alpha tokens drawn over the page background %s). '
                     'Sample = swatch centre, exact; alpha tokens ±1. Generated by qa_sample.py --write-theme.') % L['background'],
           'layout': L, 'points': pts, 'justified': {}}
    json.dump(doc, open(os.path.join(QA, 'theme.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('wrote design/qa/theme.json (%d swatches)' % len(pts))


# ------------------------------------------------------------------ coverage
def checklist_items() -> list[str]:
    s = open(CHECKLIST, encoding='utf-8').read()
    a, b = s.index('## 2.'), s.index('## 9.')
    return re.findall(r'^\| ([A-Z]-\d\d) \|', s[a:b], re.M)


def coverage() -> int:
    covered, justified = set(), {}
    for f in glob.glob(os.path.join(QA, '*.json')):
        d = json.load(open(f, encoding='utf-8'))
        covered |= {p['item'] for p in d['points']}
        justified.update(d.get('justified', {}))
    items = checklist_items()
    missing = [i for i in items if i not in covered and i not in justified]
    sampled = [i for i in items if i in covered]
    print('checklist items: %d; sampled: %d; justified (not static-checkable): %d; uncovered: %d'
          % (len(items), len(sampled), len([i for i in items if i in justified and i not in covered]), len(missing)))
    if missing:
        print('uncovered:', ' '.join(missing))
    return 1 if missing else 0


# ------------------------------------------------------------------ self-test
def self_test() -> int:
    tmp = tempfile.mkdtemp(prefix='qa_selftest_')
    os.makedirs(os.path.join(tmp, 'shots', 'synthetic'))
    W, H = 390 * DENSITY, 844 * DENSITY

    def make(shift_px=0, colour_err=0):
        im = Image.new('RGB', (W, H), rgb('#2C3A33'))
        # a "road" run from x 100 dp to 290 dp at y 300..400 dp, with a white lane at the centre
        for yy in range(px(300), px(400)):
            for xx in range(px(100) + shift_px, px(290) + shift_px):
                im.putpixel((xx, yy), rgb('#3A3A3F'))
            for xx in range(px(193), px(197)):
                im.putpixel((xx, yy), rgb('#F4F4F0'))
        c = list(rgb('#1E4FA3')); c[2] = min(255, c[2] + colour_err)
        for yy in range(px(50), px(80)):
            for xx in range(px(50), px(120)):
                im.putpixel((xx, yy), tuple(c))
        return im

    spec = {'screen': 'synthetic', 'points': [
        {'item': 'T-01', 'x': 85, 'y': 65, 'hex': '#1E4FA3'},
        {'item': 'T-02', 'kind': 'edge', 'y': 350, 'seed': 150, 'match': ['#3A3A3F', '#F4F4F0'], 'expect': [100, 290], 'tol_dp': 0},
        {'item': 'T-03', 'kind': 'present', 'region': [190, 300, 10, 100], 'hex': '#F4F4F0', 'min_px': 100},
        {'item': 'T-04', 'kind': 'absent', 'region': [0, 500, 390, 100], 'hex': '#1E4FA3'},
    ]}
    global QA
    qa_saved = QA
    QA = tmp
    json.dump(spec, open(os.path.join(tmp, 'synthetic.json'), 'w'))
    results = []
    try:
        for label, shift, err, expect_pass in (('clean image', 0, 0, True), ('1 px edge shift', 1, 0, False), ('1-unit colour error', 0, 1, False)):
            make(shift, err).save(os.path.join(tmp, 'shots', 'synthetic', 'default@390x844.png'))
            rc = run(os.path.join(tmp, 'shots'), 'synthetic')
            ok = (rc == 0) == expect_pass
            results.append(ok)
            print('self-test %-20s -> %s (%s)' % (label, 'PASS' if rc == 0 else 'FAIL', 'as expected' if ok else 'WRONG'))
    finally:
        QA = qa_saved
    good = all(results)
    print('self-test: %s' % ('OK' if good else 'BROKEN'))
    return 0 if good else 1


def main(argv: list[str]) -> int:
    if '--self-test' in argv:
        return self_test()
    if '--coverage' in argv:
        return coverage()
    if '--write-theme' in argv:
        write_theme()
        return 0
    if len(argv) != 2:
        print(__doc__)
        return 2
    return run(argv[0], argv[1])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
