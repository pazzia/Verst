#!/usr/bin/env python3
"""DES-105: reference renders of the design canvases -> design/reference/<screen>/<state>@390x844.png  (<screen> = screenshot folder id, e.g. 5.4-drive)

* Opens every docs/design-canvas/*.dc.html (template + `class Component` logic expanded in the page, the
  same way the canvas host does) and every design/states/*.dc.html in Chromium (Playwright) at a
  390 x 844 viewport, device scale factor 3 (1170 x 2532 px, = Robolectric xxhdpi).
* Google Fonts requests are intercepted: the CSS is replaced by @font-face rules that load
  android/core-ui/src/main/res/font/*.ttf (DES-100). Without those files the tool stops (exit 3): renders with
  substitute fonts are useless as comparison targets. `--provisional DIR --allow-fallback` renders with system
  fallbacks into DIR only, to test the pipeline before DES-100.
* Animations are frozen with the Web Animations API (`pause()` + `currentTime`). The time is t = 0 except for
  the canvases whose app state is defined after the entry animation (FRAME_MS below; screen files §6).
* The frame is cropped to the 390 x 844 screen (the Road-ahead canvas is 1980 tall: the reference is its top
  844 dp, i.e. scroll position 0; its footer is pinned in the app, so the footer area is masked in QA).

Usage:  python3 design/tools/render_refs.py                write design/reference/
        python3 design/tools/render_refs.py --check        re-render, compare: <= 0.1 % differing pixels per file
        python3 design/tools/render_refs.py --provisional /tmp/x --allow-fallback
"""
from __future__ import annotations

import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CANVAS = os.path.join(ROOT, 'docs', 'design-canvas')
STATES = os.path.join(ROOT, 'design', 'states')
OUT = os.path.join(ROOT, 'design', 'reference')
FONTS = os.path.join(ROOT, 'android', 'core-ui', 'src', 'main', 'res', 'font')
W, H, DPR = 390, 844, 3
MAX_DIFF = 0.001

# canvas file -> (screen, state name from architecture-android-mvp §8.2, frame time ms)
CANVAS_MAP = {
    'Wind.dc.html': ('5.1-windshield', 'default', 0),
    'Navi.dc.html': ('5.2-navigator', 'default-query-yaro', 0),
    'Panel.dc.html': ('5.3-instruments', 'default', 0),
    'Drive.dc.html': ('5.4-drive', 't1500', 1500),
    'Signs.dc.html': ('5.5-road-ahead', 'g02-top', 0),
    'Waybill.dc.html': ('5.6-waybill', 'reference', 1600),   # sheet slide 600 ms + stamp 1000 + 500 ms done
    'Exit.dc.html': ('5.7-exit', 'default', 2200),        # exit sign «near» entry done
}
STATE_RENAME = {'5.4-drive-error': 'error-internal'}  # canvas shows the UPSTREAM text used for INTERNAL (M§9)
FONT_FILES = [  # (css family, weight, res/font file)
    ('IBM Plex Sans Condensed', 400, 'ibm_plex_sans_condensed_regular.ttf'),
    ('IBM Plex Sans Condensed', 500, 'ibm_plex_sans_condensed_medium.ttf'),
    ('IBM Plex Sans Condensed', 600, 'ibm_plex_sans_condensed_semibold.ttf'),
    ('IBM Plex Sans Condensed', 700, 'ibm_plex_sans_condensed_bold.ttf'),
    ('IBM Plex Mono', 600, 'ibm_plex_mono_semibold.ttf'),
    ('Marck Script', 400, 'marck_script_regular.ttf'),
]
FALLBACK_CSS = """
@font-face{font-family:'IBM Plex Sans Condensed';src:local('DejaVu Sans Condensed');font-weight:400}
@font-face{font-family:'IBM Plex Sans Condensed';src:local('DejaVu Sans Condensed Bold');font-weight:500 700}
@font-face{font-family:'IBM Plex Mono';src:local('DejaVu Sans Mono')}
@font-face{font-family:'Marck Script';src:local('DejaVu Serif Condensed')}
"""

EXPAND_JS = r"""
(script) => {
  class DCLogic { constructor(p){ this.props = p || {}; this.state = {}; } setState(s){ Object.assign(this.state, s); } }
  const Component = (new Function('DCLogic', script + '\nreturn Component;'))(DCLogic);
  const vals = new Component({}).renderVals();
  const get = (scope, expr) => { expr = expr.trim(); if (expr === 'true') return true; if (expr === 'false') return false;
    let v = scope; for (const p of expr.split('.')) { if (v == null) return ''; v = v[p]; } return v; };
  const interp = (s, scope) => s.replace(/\{\{([^}]+)\}\}/g, (m, e) => { const v = get(scope, e); return typeof v === 'function' ? '' : (v == null ? '' : String(v)); });
  const walk = (node, scope) => {
    if (node.nodeType === 3) { node.textContent = interp(node.textContent, scope); return [node]; }
    if (node.nodeType !== 1) return [node];
    const tag = node.tagName.toLowerCase();
    if (tag === 'sc-for') { const list = get(scope, node.getAttribute('list').replace(/[{}]/g, '')) || []; const as = node.getAttribute('as'); const out = [];
      list.forEach(item => { const sc = Object.assign({}, scope, {[as]: item}); Array.from(node.childNodes).forEach(c => out.push(...walk(c.cloneNode(true), sc))); }); return out; }
    if (tag === 'sc-if') { const v = get(scope, node.getAttribute('value').replace(/[{}]/g, '')); if (!v || v === 'false') return [];
      const out = []; Array.from(node.childNodes).forEach(c => out.push(...walk(c.cloneNode(true), scope))); return out; }
    for (const a of Array.from(node.attributes)) { if (/^on/i.test(a.name)) { node.removeAttribute(a.name); continue; } if (a.value.includes('{{')) node.setAttribute(a.name, interp(a.value, scope)); }
    for (const k of Array.from(node.childNodes)) { const r = walk(k, scope); if (r.length !== 1 || r[0] !== k) { r.forEach(x => node.insertBefore(x, k)); node.removeChild(k); } }
    return [node];
  };
  const tpl = document.getElementById('tpl').content.cloneNode(true);
  const root = document.getElementById('root');
  Array.from(tpl.childNodes).forEach(c => walk(c, vals).forEach(x => root.appendChild(x)));
}
"""


def page_html(path: str) -> tuple[str, str]:
    h = open(path, encoding='utf-8').read()
    head = re.search(r'<helmet>(.*?)</helmet>', h, re.S).group(1)
    body = re.search(r'</helmet>(.*)</x-dc>', h, re.S).group(1)
    script = re.search(r'<script type="text/x-dc"[^>]*>(.*?)</script>', h, re.S).group(1)
    html = ('<!doctype html><html lang="ru"><head><meta charset="utf-8">%s</head><body style="margin:0">'
            '<div id="root"></div><template id="tpl">%s</template></body></html>' % (head, body))
    return html, script


def font_css(fallback: bool) -> str:
    if fallback:
        return FALLBACK_CSS
    return ''.join("@font-face{font-family:'%s';font-weight:%d;src:url('https://verst.local/font/%s') format('truetype')}\n" % f
                   for f in FONT_FILES)


def jobs():
    for name, (screen, state, t) in CANVAS_MAP.items():
        yield os.path.join(CANVAS, name), screen, state, t
    for path in sorted(glob.glob(os.path.join(STATES, '*.dc.html'))):
        base = os.path.basename(path)[:-len('.dc.html')]
        slug = re.match(r'\d\.\d-(windshield|navigator|instruments|drive|road-ahead|waybill|exit)-(.+)$', base)
        assert slug, 'unexpected state file name %s' % base
        screen = base[:base.index(slug.group(2)) - 1]  # e.g. 5.5-road-ahead (= screenshot folder, M§8.2)
        state = STATE_RENAME.get(base, slug.group(2))
        yield path, screen, state, 0


def render_all(fallback: bool) -> dict[str, bytes]:
    from playwright.sync_api import sync_playwright
    css = font_css(fallback)
    out: dict[str, bytes] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={'width': W, 'height': H}, device_scale_factor=DPR, locale='ru-RU')

        def route(r):
            url = r.request.url
            if 'fonts.googleapis.com' in url:
                return r.fulfill(status=200, content_type='text/css', body=css)
            if url.startswith('https://verst.local/font/'):
                return r.fulfill(status=200, content_type='font/ttf', body=open(os.path.join(FONTS, url.rsplit('/', 1)[1]), 'rb').read())
            if url.endswith('support.js'):
                return r.fulfill(status=200, content_type='application/javascript', body='')
            return r.abort()
        ctx.route(re.compile(r'^https?://.*'), route)
        page = ctx.new_page()
        for path, screen, state, t in jobs():
            html, script = page_html(path)
            page.set_content(html, wait_until='load')
            page.evaluate(EXPAND_JS, script)
            page.evaluate('document.fonts.ready')
            page.evaluate('(t) => { for (const a of document.getAnimations()) { a.pause(); a.currentTime = t; } }', t)
            page.wait_for_timeout(50)
            key = '%s/%s@%dx%d.png' % (screen, state, W, H)
            out[key] = page.screenshot(clip={'x': 0, 'y': 0, 'width': W, 'height': H})
        browser.close()
    return out


def diff_ratio(a: bytes, b: bytes) -> float:
    from PIL import Image, ImageChops
    ia, ib = Image.open(io.BytesIO(a)).convert('RGB'), Image.open(io.BytesIO(b)).convert('RGB')
    if ia.size != ib.size:
        return 1.0
    d = ImageChops.difference(ia, ib).convert('L').point(lambda v: 255 if v else 0)
    return d.histogram()[255] / (ia.size[0] * ia.size[1])


def main() -> int:
    args = sys.argv[1:]
    fallback = '--allow-fallback' in args
    provisional = args[args.index('--provisional') + 1] if '--provisional' in args else None
    missing = [f for _, _, f in FONT_FILES if not os.path.exists(os.path.join(FONTS, f))]
    if missing and not fallback:
        print('render_refs: fonts missing in %s (DES-100): %s' % (os.path.relpath(FONTS, ROOT), ', '.join(missing)))
        return 3
    if fallback and not provisional:
        print('render_refs: --allow-fallback only with --provisional DIR (never into design/reference)')
        return 2
    renders = render_all(fallback)
    if '--check' in args:
        bad = 0
        for key, png in sorted(renders.items()):
            ref = os.path.join(provisional or OUT, key)
            r = diff_ratio(open(ref, 'rb').read(), png) if os.path.exists(ref) else 1.0
            ok = r <= MAX_DIFF
            bad += not ok
            print('%-48s %.4f %%  %s' % (key, r * 100, 'OK' if ok else 'DIFFERS'))
        print('render_refs --check: %d files, %d over %.1f %%' % (len(renders), bad, MAX_DIFF * 100))
        return 1 if bad else 0
    base = provisional or OUT
    for key, png in renders.items():
        dst = os.path.join(base, key)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(png)
    print('wrote %d PNGs (%dx%d px) to %s%s' % (len(renders), W * DPR, H * DPR, base, ' [PROVISIONAL, fallback fonts]' if fallback else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
