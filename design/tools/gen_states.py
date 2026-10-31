#!/usr/bin/env python3
"""Generate design/states/*.dc.html (DES-006): canvases for the states SPEC §5 requires
but the approved v5 canvases do not show.

Every colour is a value from design/tokens.json (checked by check_states_tokens() below and by
`python3 design/tools/gen_states.py --check`). Structure, sizes and fonts follow the approved
canvases in docs/design-canvas/ and the redlines in design/screens/*.md, with the accepted
AA fixes (decisions.md) applied.

Run:  python3 design/tools/gen_states.py          (writes design/states/)
      python3 design/tools/gen_states.py --check  (token check only)
"""
from __future__ import annotations
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESIGN = os.path.dirname(HERE)
OUT = os.path.join(DESIGN, 'states')
CANVAS = '../../docs/design-canvas/'

FONTS = ('<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Condensed:wght@400;500;600;700'
         '&amp;family=IBM+Plex+Mono:wght@600&amp;family=Marck+Script&amp;display=swap" rel="stylesheet">')

BASE_CSS = """body{margin:0}
a{color:#FFD23F}
@keyframes rush{from{background-position:0 0}to{background-position:0 160px}}
.lane{background:repeating-linear-gradient(to bottom,#F4F4F0 0 70px,transparent 70px 160px);animation:rush .9s linear infinite}
.lane-slow{animation-duration:1.4s}
.lane-drive{animation-duration:.45s}
@keyframes post{0%{transform:translate(0,0) scale(.3);opacity:0}10%{opacity:1}100%{transform:translate(150px,260px) scale(2.2);opacity:1}}
.post{animation:post 2.6s cubic-bezier(.55,0,1,.45) infinite}
@keyframes postL{0%{transform:translate(0,0) scale(.3);opacity:0}10%{opacity:1}100%{transform:translate(-150px,260px) scale(2.2);opacity:1}}
.postL{animation:postL 2.6s cubic-bezier(.55,0,1,.45) 1.3s infinite both}
@keyframes ring{0%{box-shadow:0 0 0 0 rgba(216,64,43,.55)}100%{box-shadow:0 0 0 16px rgba(216,64,43,0)}}
.start{animation:ring 1.8s ease-out infinite}
@keyframes sway{0%,100%{transform:rotate(-1.5deg)}50%{transform:rotate(1.5deg)}}
.mirror{animation:sway 4s ease-in-out infinite;transform-origin:50% 0}
@keyframes shimmer{from{background-position:-90px 0}to{background-position:420px 0}}
.shim-sign{background-color:rgba(255,255,255,.10);background-image:linear-gradient(90deg,rgba(255,255,255,.10),rgba(255,255,255,.20),rgba(255,255,255,.10));background-size:90px 100%;background-repeat:no-repeat;animation:shimmer 1.2s linear infinite}
.shim-dash{background-color:#2A2A2E;background-image:linear-gradient(90deg,#2A2A2E,#3A3A42,#2A2A2E);background-size:90px 100%;background-repeat:no-repeat;animation:shimmer 1.2s linear infinite}
.shim-navi{background-color:#16222C;background-image:linear-gradient(90deg,#16222C,#1A2C3B,#16222C);background-size:90px 100%;background-repeat:no-repeat;animation:shimmer 1.2s linear infinite}
@keyframes pulseBorder{0%,100%{border-color:#FFD23F}50%{border-color:#16222C}}
.pulse2{animation:pulseBorder 1.2s ease-in-out 2}
@keyframes dots{0%,100%{opacity:.3}50%{opacity:1}}
.dot{animation:dots .9s ease-in-out infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.spin{animation:spin .9s linear infinite}
@keyframes blink{0%,55%{opacity:1}56%,100%{opacity:.15}}
.turn{animation:blink .9s steps(1) infinite}
@media (prefers-reduced-motion: reduce){*{animation:none!important}}
button:focus-visible,a:focus-visible{outline:2px solid #FFD23F;outline-offset:2px}"""

FONT_FAMILY = "font-family: 'IBM Plex Sans Condensed', sans-serif"

# ---------------------------------------------------------------- icons (UI strokes from components.md §17)
def svg(d, size, color, sw=2.0, fill='none', extra=''):
    stroke = '' if fill != 'none' else ' stroke="%s" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round"' % (color, sw)
    f = color if fill != 'none' else 'none'
    return ('<svg aria-hidden="true" width="%s" height="%s" viewBox="0 0 24 24" fill="%s"%s><path d="%s"></path>%s</svg>'
            % (size, size, f, stroke, d, extra))

UR = 'M7 17L17 7M9 7h8v8'; UP = 'M12 20V4M5 11l7-7 7 7'; DN = 'M12 4v16M5 13l7 7 7-7'; RIGHT = 'M4 12h16M13 5l7 7-7 7'
LEFT = 'M20 12H4M11 5l-7 7 7 7'
OFFLINE = 'M2 8.5a15 15 0 0 1 20 0M5.5 12a10 10 0 0 1 13 0M9 15.5a5 5 0 0 1 6 0M12 19h.01M3 3l18 18'
BOOKMARK = 'M6 3h12v18l-6-4-6 4z'; SHARE = 'M12 15V3M7 8l5-5 5 5M5 13v7h14v-7'; CLOCK_EXTRA = '<circle cx="12" cy="12" r="9"></circle>'
CHECK = 'M5 12.5l4.5 4.5L19 7'
CHURCH = 'M12 2v3M10.5 3.5h3M8 21V12l4-4 4 4v9M5 21h14M10 21v-4a2 2 0 0 1 4 0v4'
HOTEL = 'M3 18V8M3 14h18v4M21 14v-2a3 3 0 0 0-3-3h-7v5'
FOOD = 'M7 3v8a2 2 0 0 0 2 2v8M5 3v5M9 3v5M16 21V3c2.5 1 4 3.5 4 7h-4'
POWER = 'M12 3v8M6.3 6.6a8 8 0 1 0 11.4 0'
SEARCH_EXTRA = '<circle cx="11" cy="11" r="7"></circle>'
LOCATE = 'M3 11l18-8-8 18-2-8z'
PIN_EXTRA = '<circle cx="12" cy="9" r="2.5"></circle>'

def back_link(x, y, label, color='#8C8C93'):
    return ('<a href="#" style="position: absolute; left: %dpx; top: %dpx; min-height: 32px; display: flex; align-items: center; gap: 6px; '
            'font-size: 13px; color: %s; text-decoration: none; z-index: 4">%s%s</a>') % (x, y, color, svg(LEFT, 14, color, 2.5), label)

def offline_plate(color='#E6604A', label='НЕТ СЕТИ'):
    return ('<span style="display: inline-flex; align-items: center; gap: 4px; color: %s">%s%s</span>'
            % (color, svg(OFFLINE, 11, color, 2.4), label))

def warn_badge(size=16):
    return ('<span aria-hidden="true" style="width: %dpx; height: %dpx; border-radius: 50%%; background: #FFD23F; color: #141416; '
            'display: inline-flex; align-items: center; justify-content: center; font-weight: 700; font-size: 11px; flex-shrink: 0">!</span>' % (size, size))

def toast(text, action=None, bottom=96):
    act = ('<span style="font-weight: 600; color: #FFD23F; margin-left: auto; padding-left: 12px">%s</span>' % action) if action else ''
    return ('<div role="status" aria-live="polite" style="position: absolute; left: 18px; right: 18px; bottom: %dpx; min-height: 44px; '
            'box-sizing: border-box; padding: 10px 16px; border-radius: 10px; background: #232327; border: 1px solid #3A3A42; '
            'display: flex; align-items: center; font-size: 13px; color: #F4F4F0; z-index: 6">%s%s</div>') % (bottom, text, act)

# ---------------------------------------------------------------- scenes
def liner_pillars(h, liner=16, curve=14):
    return ('<div style="position: absolute; left: 0; right: 0; top: 0; height: %dpx; background: #0E0E10; border-radius: 0 0 50%% 50%% / 0 0 %dpx %dpx"></div>'
            '<div style="position: absolute; left: 0; top: 0; bottom: 0; width: 24px; background: #0E0E10; clip-path: polygon(0 0, 100%% 0, 40%% 100%%, 0 100%%)"></div>'
            '<div style="position: absolute; right: 0; top: 0; bottom: 0; width: 24px; background: #0E0E10; clip-path: polygon(0 0, 100%% 0, 100%% 100%%, 60%% 100%%)"></div>') % (liner, curve, curve)

def road(top, height, persp, w, length, deg, edge, lane, lane_cls='lane', asphalt='#3A3A3F', edgec='#F4F4F0'):
    return ('<div style="position: absolute; left: 0; right: 0; top: %dpx; height: %dpx; overflow: hidden; perspective: %dpx; perspective-origin: 50%% 0%%">'
            '<div style="position: absolute; left: 50%%; bottom: 0; width: %dpx; height: %dpx; margin-left: -%dpx; background: %s; border-left: %dpx solid %s; '
            'border-right: %dpx solid %s; box-sizing: border-box; transform-origin: 50%% 100%%; transform: rotateX(%ddeg)">'
            '<div class="%s" style="position: absolute; top: 0; bottom: 0; left: 50%%; width: %dpx; margin-left: -%gpx"></div></div></div>'
            ) % (top, height, persp, w, length, w // 2, asphalt, edge, edgec, edge, edgec, deg, lane_cls, lane, lane / 2)

def wind_scene(moving=True):
    posts = ('<div class="post" style="position: absolute; left: 236px; top: 302px; width: 6px; height: 18px; background: #F4F4F0; border-top: 5px solid #141416; box-sizing: border-box"></div>'
             '<div class="postL" style="position: absolute; left: 148px; top: 302px; width: 6px; height: 18px; background: #F4F4F0; border-top: 5px solid #141416; box-sizing: border-box"></div>') if moving else ''
    return ('<div aria-hidden="true" style="position: absolute; left: 0; right: 0; top: 0; height: 540px; overflow: hidden">'
            '<div style="position: absolute; left: 0; right: 0; top: 0; height: 110px; background: #2B2850"></div>'
            '<div style="position: absolute; left: 0; right: 0; top: 110px; height: 70px; background: #4E3768"></div>'
            '<div style="position: absolute; left: 0; right: 0; top: 180px; height: 55px; background: #8E4A6B"></div>'
            '<div style="position: absolute; left: 0; right: 0; top: 235px; height: 40px; background: #D9655A"></div>'
            '<div style="position: absolute; left: 0; right: 0; top: 275px; height: 25px; background: #F29A5E"></div>'
            '<div style="position: absolute; left: 236px; top: 266px; width: 68px; height: 68px; border-radius: 50%; background: #FFD99A"></div>'
            '<svg width="390" height="40" viewBox="0 0 390 40" style="position: absolute; left: 0; top: 272px"><path d="M0 28 L40 18 L80 24 L130 12 L170 22 L200 16 L250 26 L300 14 L350 24 L390 18 L390 40 L0 40 Z" fill="#3C3346"></path></svg>'
            '<div style="position: absolute; left: 0; right: 0; top: 300px; bottom: 0; background: #2C3A33"></div>'
            + road(300, 240, 210, 230, 1000, 76, 6, 8, 'lane' if moving else '') + posts +
            '<div style="position: absolute; left: 34px; top: 286px; width: 8px; height: 100px; background: #55565C"></div>'
            '<div style="position: absolute; right: 34px; top: 286px; width: 8px; height: 100px; background: #55565C"></div>'
            + liner_pillars(540) + '</div>')

def small_mirror(crew='2 взр · 1 реб · пёс', aria='2 взрослых, 1 ребёнок, собака', passengers=True):
    sil = lambda x, h, b, bw, bh, r: ('<span style="position: absolute; left: %dpx; bottom: 0; width: %dpx; height: %dpx; display: flex; flex-direction: column; align-items: center">'
                                      '<span style="width: %dpx; height: %dpx; border-radius: 50%%; background: #0D0D0F"></span>'
                                      '<span style="width: %dpx; height: %dpx; border-radius: %dpx %dpx 0 0; background: #0D0D0F; margin-top: 1px"></span></span>') % (x, bw + 2, h + bh + 1, h, h, bw, bh, r, r)
    head = ('<a href="%sPanel.dc.html" class="mirror" aria-label="Экипаж в зеркале: %s. Изменить" style="position: absolute; left: 120px; top: 8px; width: 150px; display: flex; flex-direction: column; align-items: center; text-decoration: none; z-index: 3">' % (CANVAS, aria))
    return (head +
            '<span aria-hidden="true" style="width: 8px; height: 10px; background: #2A2A2E"></span>'
            '<span aria-hidden="true" style="position: relative; width: 150px; height: 44px; border-radius: 22px; border: 3px solid #2A2A2E; background: #0D0D0F; overflow: hidden; box-sizing: border-box">'
            '<span style="position: absolute; left: 0; right: 0; top: 0; height: 20px; background: #4E3768"></span>'
            '<span style="position: absolute; left: 0; right: 0; top: 20px; height: 22px; background: #2C3A33"></span>'
            + ((sil(18, 12, 0, 24, 12, 10) + sil(60, 9, 0, 18, 10, 8) + sil(94, 12, 0, 24, 12, 10) +
            '<span style="position: absolute; right: 8px; bottom: 6px; width: 14px; height: 12px; border-radius: 6px 6px 4px 4px; background: #0D0D0F"></span>') if passengers else '') +
            ''
            '<span style="position: absolute; left: -20px; top: -10px; width: 60px; height: 70px; background: rgba(255,255,255,.08); transform: rotate(25deg)"></span></span>'
            '<span style="margin-top: 3px; font-size: 11px; font-weight: 600; color: #E9E2F2; text-shadow: 0 1px 2px #000000">' + crew + '</span></a>')

def overhead(header_left, header_right, body, footer=None):
    foot = ('<button type="button" style="display: block; width: 100%%; text-align: left; border: none; background: transparent; padding: 3px 6px 1px; '
            'font-family: inherit; font-size: 11px; color: #D6E0F5; cursor: pointer">%s</button>' % footer) if footer else ''
    return ('<div style="position: absolute; left: 20px; right: 20px; top: 84px; background: #1E4FA3; border-radius: 9px; padding: 4px; box-shadow: 0 8px 18px rgba(0,0,0,.35); z-index: 2">'
            '<div style="border: 2px solid #F4F4F0; border-radius: 6px; padding: 6px 6px 4px">'
            '<div style="display: flex; justify-content: space-between; align-items: center; padding: 0 6px 4px; font-size: 11px; font-weight: 600; letter-spacing: 0.08em; color: #D6E0F5">'
            '<span role="heading" aria-level="2">%s</span><span>%s</span></div>%s%s</div></div>') % (header_left, header_right, body, foot)

def sign_row(arrow, name, km, sel=False, meta=''):
    c = '#FFD23F' if sel else '#F4F4F0'; bg = '#163B7A' if sel else 'transparent'
    return ('<button type="button" aria-pressed="%s" aria-label="%s, %s километров%s" style="width: 100%%; min-height: 44px; display: flex; align-items: center; gap: 10px; padding: 0 6px; border: none; border-radius: 4px; '
            'cursor: pointer; font-family: inherit; color: %s; background: %s">%s'
            '<span style="flex: 1; min-width: 0; text-align: left; font-weight: 600; font-size: 18px; line-height: 1.1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">%s</span>'
            '<span style="font-weight: 600; font-size: 18px; font-variant-numeric: tabular-nums">%s</span></button>'
            ) % ('true' if sel else 'false', name, km, ('. ' + meta) if meta else '', c, bg, svg(arrow, 22, c, 3), name, km)

ROUTES = [(UR, 'Золотое кольцо', '745', '3 дня · 8 городов · по кругу'), (UP, 'Ярославль', '265', '2 дня · Ростов и Переславль по пути'),
          (UR, 'Суздаль · Владимир', '220', '2 дня · кремли и Золотые ворота'), (DN, 'Тула · Ясная Поляна', '200', '1–2 дня · кремль и усадьба Толстого')]

def dashboard(top, inner, curve=34):
    return ('<div style="position: absolute; left: 0; right: 0; top: %dpx; bottom: 0; background: #161618; border-radius: 50%% 50%% 0 0 / %dpx %dpx 0 0; box-shadow: 0 -2px 0 #232327">%s</div>'
            % (top, curve, curve, inner))

def wind_navi(header_left='НАВИГАТОР', field_sub='город, адрес или точка на карте — по всей России', hint='или выберите готовый маршрут на указателе ↑',
              city='МОСКВА', field_border='1px solid #2B3D4D', field_cls=''):
    return ('<a href="%sNavi.dc.html" aria-label="Навигатор. Куда угодно: %s" style="position: absolute; left: 18px; right: 18px; top: 22px; height: 134px; background: #0B1218; border: 6px solid #232327; border-radius: 16px; '
            'box-sizing: border-box; padding: 10px 12px; text-decoration: none; color: #F4F4F0; display: block">'
            '<span style="display: flex; justify-content: space-between; height: 14px; font-size: 11px; font-weight: 600; letter-spacing: 0.08em; color: #7FA6D9"><span style="display: flex; gap: 4px">%s</span><span></span></span>'
            '<span class="%s" style="margin-top: 14px; height: 48px; box-sizing: border-box; border-radius: 10px; background: #16222C; border: %s; display: flex; align-items: center; gap: 10px; padding: 0 12px">'
            '%s<span style="display: flex; flex-direction: column; min-width: 0"><span style="font-weight: 600; font-size: 16px">Куда угодно</span>'
            '<span style="font-size: 12px; color: #8FA4B8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis">%s</span></span></span>'
            '<span style="display: block; margin-top: 8px; font-size: 12px; color: #8FA4B8">%s</span></a>'
            '<button type="button" aria-label="Старт: %s. Определить по геопозиции" style="position: absolute; right: 24px; top: 22px; height: 44px; min-width: 100px; padding: 0 10px; border: none; background: transparent; '
            'display: flex; align-items: center; justify-content: flex-end; gap: 4px; font-family: inherit; font-size: 11px; font-weight: 600; letter-spacing: 0.08em; color: #7FA6D9; cursor: pointer">'
            '%sВЫ: %s</button>') % (CANVAS, field_sub, header_left, field_cls, field_border, svg('M20 20l-3.5-3.5', 18, '#FFD23F', 2.4, extra=SEARCH_EXTRA), field_sub, hint,
                                     city.capitalize(), svg(LOCATE, 11, '#7FA6D9', fill='#7FA6D9'), city)

def start_button(size='M', enabled=True, label='ПОЕХАЛИ', aria='Поехали'):
    outer, face, icon, fs = {'L': (100, 82, 20, 12), 'M': (92, 76, 18, 12), 'S': (86, 70, 16, 11)}[size]
    ring = '#D8402B' if enabled else '#55555E'; fg = '#F4F4F0' if enabled else '#6C6C74'
    return ('<a href="#" class="%s" aria-label="%s"%s style="width: %dpx; height: %dpx; border-radius: 50%%; background: #232327; display: flex; align-items: center; justify-content: center; text-decoration: none; flex-shrink: 0">'
            '<span style="width: %dpx; height: %dpx; border-radius: 50%%; border: 3px solid %s; background: #1C1C1F; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; box-sizing: border-box">'
            '%s<span style="font-weight: 700; font-size: %dpx; letter-spacing: 0.06em; color: %s">%s</span></span></a>'
            ) % ('start' if enabled else '', aria, '' if enabled else ' aria-disabled="true"', outer, outer, face, face, ring, svg(POWER, icon, fg, 2.4), fs, fg, label)

def caption(label, title, meta, extra='', title_size=22, meta_color='#B9B9C0'):
    return ('<div style="flex: 1; min-width: 0" aria-live="polite"><div style="font-size: 11px; font-weight: 600; letter-spacing: 0.08em; color: #8C8C93">%s</div>'
            '<div style="font-weight: 700; font-size: %dpx; line-height: 1.1">%s</div><div style="margin-top: 2px; font-size: 13px; color: %s">%s</div>%s</div>'
            ) % (label, title_size, title, meta_color, meta, extra)

def my_trips_plate(n=3):
    return ('<button type="button" aria-label="Мои поездки, %d сохранённые. Открыть список" style="margin-top: 8px; height: 36px; padding: 0 12px; border-radius: 8px; border: 1px solid #3A3A42; background: transparent; '
            'display: inline-flex; align-items: center; gap: 6px; font-family: inherit; font-weight: 600; font-size: 13px; color: #B9B9C0; cursor: pointer">%sМои поездки · %d</button>'
            ) % (n, svg(BOOKMARK, 16, '#B9B9C0', 2), n)

def wind_caption_row(cap, start):
    return '<div style="position: absolute; left: 22px; right: 20px; top: 176px; height: 92px; display: flex; align-items: center; gap: 14px">%s%s</div>' % (cap, start)

# ---------------------------------------------------------------- page wrapper
def page(title, note, body, height=844, root_bg='#141416', extra_css=''):
    return ('<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n<title>%s</title>\n<script src="./support.js"></script>\n</head>\n<body>\n'
            '<!-- DES-006 state canvas. %s Spec: design/screens/*.md; tokens: design/tokens.json; generated by design/tools/gen_states.py -->\n'
            '<x-dc>\n<helmet>\n%s\n<style>\n%s\n%s\n</style>\n</helmet>\n'
            '<div style="width: 390px; height: %dpx; position: relative; overflow: hidden; background: %s; color: #F4F4F0; %s">\n%s\n</div>\n</x-dc>\n'
            '<script type="text/x-dc" data-dc-script data-props=\'{"$preview":{"width":390,"height":%d}}\'>\n'
            'class Component extends DCLogic {\n  renderVals() { return {}; }\n}\n</script>\n</body>\n</html>\n'
            ) % (title, note, FONTS, BASE_CSS, extra_css, height, root_bg, FONT_FAMILY, body, height)

STATES = {}

# 1 ---------------------------------------------------------------- Windshield loading
def plate_row():
    return ('<div aria-hidden="true" style="min-height: 44px; display: flex; align-items: center; gap: 10px; padding: 0 6px">'
            '<span class="shim-sign" style="width: 22px; height: 22px; border-radius: 4px"></span>'
            '<span class="shim-sign" style="width: 145px; height: 14px; border-radius: 4px"></span><span style="flex: 1"></span>'
            '<span class="shim-sign" style="width: 30px; height: 14px; border-radius: 4px"></span></div>')
STATES['5.1-windshield-loading'] = page('Лобовое стекло · загрузка', 'Screen 5.1 §4.3 loading (≤ 2 s, never < 300 ms).',
    wind_scene() + small_mirror() +
    overhead('РЯДОМ С ВАМИ · ИЗ МОСКВЫ', 'КМ', '<div role="img" aria-label="Загружаем маршруты рядом">' + plate_row() * 4 + '</div>') +
    dashboard(520, wind_navi() + wind_caption_row(
        caption('ВЫБРАН МАРШРУТ', '<span class="shim-dash" style="display: block; width: 160px; height: 20px; margin: 2px 0; border-radius: 4px"></span>',
                '<span class="shim-dash" style="display: block; width: 120px; height: 12px; margin-top: 4px; border-radius: 4px"></span>'),
        start_button('M', False, aria='Поехали — маршрут ещё загружается'))))

# 2 ---------------------------------------------------------------- Windshield offline (cached routes)
rows_cached = ''.join(sign_row(a, n, k, i == 0, m) for i, (a, n, k, m) in enumerate(ROUTES))
STATES['5.1-windshield-offline-cached'] = page('Лобовое стекло · нет сети (кэш)', 'Screen 5.1 §4.5 offline with cached ready routes; saved trips present.',
    wind_scene() + small_mirror() +
    overhead('РЯДОМ С ВАМИ · ИЗ МОСКВЫ', offline_plate('#D6E0F5'), rows_cached, 'ещё 14 маршрутов в радиусе 300 км ↓') +
    dashboard(520, wind_navi(header_left='НАВИГАТОР · ' + offline_plate(), field_sub='без сети открываются только сохранённые поездки') + wind_caption_row(
        caption('ВЫБРАН МАРШРУТ', 'Золотое кольцо', '3 дня · 8 городов · по кругу', my_trips_plate()), start_button('M', True, aria='Поехали: Золотое кольцо'))))

# 3 ---------------------------------------------------------------- Windshield offline, nothing cached
def sign_message(text, size=15):
    return '<div role="status" style="padding: 10px 6px; font-weight: 700; font-size: %dpx; line-height: 1.3; color: #F4F4F0">%s</div>' % (size, text)
STATES['5.1-windshield-offline-empty'] = page('Лобовое стекло · нет сети (пусто)', 'Screen 5.1 §4.5 offline without cached routes; saved trips present.',
    wind_scene() + small_mirror() +
    overhead('РЯДОМ С ВАМИ · ИЗ МОСКВЫ', offline_plate('#D6E0F5'), sign_message('Нет сети — готовые маршруты появятся, когда будет интернет')) +
    dashboard(520, wind_navi(header_left='НАВИГАТОР · ' + offline_plate(), field_sub='без сети открываются только сохранённые поездки') + wind_caption_row(
        caption('НЕТ СЕТИ', 'Мои поездки работают', 'маршрут построим, когда появится сеть', my_trips_plate()),
        start_button('M', False, aria='Поехали — нужен интернет'))))

# 4 ---------------------------------------------------------------- Windshield no ready routes
STATES['5.1-windshield-no-routes'] = page('Лобовое стекло · нет маршрутов рядом', 'Screen 5.1 §4.7 no ready routes near the start (start outside the curated region).',
    wind_scene() + small_mirror('1 взр', '1 взрослый', passengers=False) +
    overhead('РЯДОМ С ВАМИ · ИЗ МУРМАНСКА', 'КМ', sign_message('Рядом пока нет готовых маршрутов', 18),
             'Наберите любой город в навигаторе ↓').replace('<button type="button" style="display: block', '<div style="display: block').replace('cursor: pointer">Наберите', '">Наберите').replace('навигаторе ↓</button>', 'навигаторе ↓</div>') +
    dashboard(520, wind_navi(city='МУРМАНСК', field_border='2px solid #FFD23F', field_cls='pulse2', hint='город, адрес или точка на карте — по всей России').replace(
        '<span style="display: block; margin-top: 8px; font-size: 12px; color: #8FA4B8">город, адрес или точка на карте — по всей России</span>',
        '<span style="display: block; margin-top: 8px; font-size: 12px; color: #8FA4B8">маршрут построим из любой точки России</span>') + wind_caption_row(
        caption('КУДА ЕДЕМ?', 'Выберите в навигаторе', 'город, адрес или точка на карте'), start_button('M', False, aria='Поехали — сначала выберите, куда'))))

# ---------------------------------------------------------------- Navigator frame
def navi_frame(query, list_html, after_html, cap_title, cap_meta, start_enabled, meta_color='#B9B9C0'):
    strip = ('<div aria-hidden="true" style="position: absolute; left: 0; right: 0; top: 0; height: 150px; overflow: hidden">'
             '<div style="position: absolute; left: 0; right: 0; top: 0; height: 46px; background: #2B2850"></div>'
             '<div style="position: absolute; left: 0; right: 0; top: 46px; height: 30px; background: #8E4A6B"></div>'
             '<div style="position: absolute; left: 0; right: 0; top: 76px; height: 18px; background: #D9655A"></div>'
             '<div style="position: absolute; left: 0; right: 0; top: 94px; height: 10px; background: #F29A5E"></div>'
             '<div style="position: absolute; left: 0; right: 0; top: 104px; bottom: 0; background: #2C3A33"></div>'
             + road(104, 46, 120, 160, 600, 80, 4, 6, 'lane lane-slow') +
             '<div style="position: absolute; left: 0; right: 0; top: 0; height: 14px; background: #0E0E10; border-radius: 0 0 50% 50% / 0 0 12px 12px"></div></div>')
    panel = ('<div style="position: absolute; left: 14px; right: 14px; top: 56px; bottom: 140px; background: #0B1218; border: 7px solid #232327; border-radius: 18px; padding: 12px; box-sizing: border-box; display: flex; flex-direction: column; gap: 10px; overflow: hidden">'
             '<div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: 600; letter-spacing: 0.08em; color: #7FA6D9"><span>НАВИГАТОР · ВСЯ РОССИЯ</span><span>GPS ●</span></div>'
             '<div style="display: flex; align-items: center; gap: 10px; min-height: 48px; padding: 0 12px; border-radius: 10px; background: #16222C; border: 1px solid #2B3D4D">'
             '<span aria-hidden="true" style="width: 12px; height: 12px; border-radius: 50%%; border: 3px solid #7FA6D9; box-sizing: border-box; flex-shrink: 0"></span>'
             '<span style="flex: 1; display: flex; flex-direction: column"><span style="font-size: 11px; color: #8FA4B8">ОТКУДА</span><span style="font-weight: 600; font-size: 16px">Москва · вы здесь</span></span>'
             '<button type="button" style="min-height: 36px; padding: 0 10px; border-radius: 8px; border: 1px solid #2B3D4D; background: transparent; color: #7FA6D9; font-family: inherit; font-weight: 600; font-size: 12px">изменить</button></div>'
             '<div style="display: flex; align-items: center; gap: 10px; min-height: 52px; padding: 0 12px; border-radius: 10px; background: #16222C; border: 2px solid #FFD23F">'
             '<span aria-hidden="true" style="width: 12px; height: 12px; border-radius: 3px; background: #FFD23F; flex-shrink: 0"></span>'
             '<span style="flex: 1; min-width: 0; display: flex; flex-direction: column"><label for="q" style="font-size: 11px; color: #8FA4B8">КУДА — город, адрес, место</label>'
             '<input id="q" type="text" value="%s" autocomplete="off" style="width: 100%%; background: transparent; border: none; color: #F4F4F0; font-family: inherit; font-weight: 600; font-size: 18px; padding: 0; min-height: 26px; outline: none; caret-color: #FFD23F"></span>'
             '<button type="button" aria-label="Очистить" style="width: 44px; height: 44px; margin-right: -12px; border: none; background: transparent; display: flex; align-items: center; justify-content: center">%s</button></div>'
             '%s%s</div>') % (query, svg('M6 6l12 12M18 6L6 18', 16, '#8FA4B8', 2), list_html, after_html)
    bottom = ('<div style="position: absolute; left: 22px; right: 20px; bottom: 26px; display: flex; align-items: center; gap: 14px">%s%s</div>'
              % (caption('МАРШРУТ', cap_title, cap_meta, title_size=20, meta_color=meta_color), start_button('S', start_enabled, aria='Поехали' if start_enabled else 'Поехали — сначала выберите, куда')))
    return strip + dashboard(132, back_link(20, 16, 'К лобовому') + panel + bottom, 30)

def dashed_buttons(map_highlight=False):
    mb = '2px dashed #FFD23F' if map_highlight else '1px dashed #3A5266'
    return ('<div style="display: flex; gap: 6px"><button type="button" style="flex: 1; min-height: 44px; border-radius: 10px; border: 1px dashed #3A5266; background: transparent; color: #FFD23F; font-family: inherit; font-weight: 600; font-size: 13px">+ заехать по пути</button>'
            '<button type="button" aria-label="Точка на карте, откроется карта" style="flex: 1; min-height: 44px; border-radius: 10px; border: %s; background: transparent; color: #7FA6D9; font-family: inherit; font-weight: 600; font-size: 13px">точка на карте</button></div>' % mb)

def info_block(title, text, icon=''):
    return ('<div role="status" style="padding: 12px; border-radius: 10px; background: #0F1A22; border: 1px solid #1E2E3A; display: flex; gap: 10px; align-items: flex-start">%s'
            '<span style="display: flex; flex-direction: column; gap: 2px"><span style="font-weight: 600; font-size: 15px; color: #F4F4F0">%s</span>'
            '<span style="font-size: 12px; line-height: 1.35; color: #8FA4B8">%s</span></span></div>') % (icon, title, text)

# 5 ---------------------------------------------------------------- Navigator no results
STATES['5.2-navigator-no-results'] = page('Навигатор · ничего не нашли', 'Screen 5.2 §3 "No results" (IME hidden for the canvas; with the IME open the caption row is hidden, 5.2 §1).',
    navi_frame('Суздальь', info_block('Ничего не нашли по запросу «Суздальь»', 'Попробуйте иначе или поставьте точку на карте'), dashed_buttons(True),
               'Москва → ?', 'выберите, куда ехать', False))

# 6 ---------------------------------------------------------------- Navigator outside Russia
def sugg_row(mark, badge, name, where, km, disabled=False):
    nc = '#6C6C74' if disabled else '#F4F4F0'; wc = '#768DA3' if disabled else '#8FA4B8'; bg = '#2A2A2E' if disabled else badge
    bc = '#6C6C74' if disabled else '#F4F4F0'
    right = '<span style="font-size: 12px; font-weight: 600; color: #768DA3; white-space: nowrap">не по России</span>' if disabled else '<span style="font-size: 13px; color: #B9C6D3; white-space: nowrap; font-variant-numeric: tabular-nums">%s</span>' % km
    return ('<li><button type="button"%s aria-label="%s, %s%s" style="width: 100%%; min-height: 52px; display: flex; align-items: center; gap: 10px; padding: 6px 12px; border: none; border-bottom: 1px solid #1E2E3A; '
            'font-family: inherit; color: %s; background: #0F1A22"><span aria-hidden="true" style="width: 26px; height: 26px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 12px; flex-shrink: 0; background: %s; color: %s">%s</span>'
            '<span style="flex: 1; min-width: 0; display: flex; flex-direction: column; text-align: left"><span style="font-weight: 600; font-size: 15px">%s</span><span style="font-size: 12px; color: %s">%s</span></span>%s</button></li>'
            ) % (' aria-disabled="true"' if disabled else '', name, where, ', маршрут только по России' if disabled else ', ' + km.replace('≈ ', 'примерно ').replace('км', 'километров'),
                 nc, bg, bc, mark, name, wc, where, right)
STATES['5.2-navigator-outside-russia'] = page('Навигатор · за пределами России', 'Screen 5.2 §3 "Outside Russia" (NEW row added to the state table; same copy as the map picker D-3).',
    navi_frame('Минск', '<ul role="listbox" aria-label="Подсказки" style="list-style: none; margin: 0; padding: 0; border-radius: 10px; overflow: hidden; border: 1px solid #1E2E3A">'
               + sugg_row('Г', '#1E4FA3', 'Минск', 'город · Беларусь', '', True)
               + sugg_row('М', '#6B3E26', 'Минское шоссе', 'трасса М-1 · Московская область', '≈ 40 км') + '</ul>'
               + info_block('Сюда маршрут не строим — только по России', 'Можно доехать до границы: выберите город в России, например Смоленск', svg(OFFLINE.split('M3 3')[0] and 'M12 8v5M12 16.5h.01', 18, '#FFD23F', 2.4, extra='<circle cx="12" cy="12" r="9"></circle>')),
               dashed_buttons(), 'Москва → ?', 'выберите город или место в России', False))

# ---------------------------------------------------------------- Drive frame
def drive_scene(speed='lane lane-drive', posts=True, signs=True):
    p = ('<div style="position: absolute; left: 212px; top: 300px; width: 6px; height: 18px; background: #F4F4F0; border-top: 5px solid #141416; box-sizing: border-box; animation: post 1.1s cubic-bezier(.6,0,1,.5) infinite"></div>'
         '<div style="position: absolute; left: 172px; top: 300px; width: 6px; height: 18px; background: #F4F4F0; border-top: 5px solid #141416; box-sizing: border-box; animation: postL 1.1s cubic-bezier(.6,0,1,.5) .55s infinite both"></div>') if posts else ''
    s = ('<div style="position: absolute; left: 195px; top: 250px; width: 150px; background: #1E4FA3; border-radius: 6px; padding: 3px; transform: translate(-50%, -50%) scale(.55); opacity: .9">'
         '<div style="border: 2px solid #F4F4F0; border-radius: 4px; padding: 6px 8px; display: flex; align-items: center; justify-content: space-between; gap: 8px">'
         '<span style="font-weight: 700; font-size: 15px; line-height: 1.05">Сергиев<br>Посад</span><span style="font-weight: 700; font-size: 18px">70</span></div></div>') if signs else ''
    return ('<div aria-hidden="true" style="position: absolute; left: 0; right: 0; top: 0; height: 560px; overflow: hidden">'
            '<div style="position: absolute; left: 0; right: 0; top: 0; height: 120px; background: #2B2850"></div>'
            '<div style="position: absolute; left: 0; right: 0; top: 120px; height: 70px; background: #4E3768"></div>'
            '<div style="position: absolute; left: 0; right: 0; top: 190px; height: 50px; background: #8E4A6B"></div>'
            '<div style="position: absolute; left: 0; right: 0; top: 240px; height: 36px; background: #D9655A"></div>'
            '<div style="position: absolute; left: 0; right: 0; top: 276px; height: 24px; background: #F29A5E"></div>'
            '<div style="position: absolute; left: 161px; top: 270px; width: 68px; height: 68px; border-radius: 50%; background: #FFD99A"></div>'
            '<div style="position: absolute; left: 0; right: 0; top: 300px; bottom: 0; background: #2C3A33"></div>'
            + road(300, 260, 210, 240, 1000, 76, 6, 8, speed) + p + s + liner_pillars(560) + '</div>')

def step(text, state='done'):
    if state == 'done':
        icon = svg(CHECK, 10, '#FFD23F', 2.4); col = '#F4F4F0'
    elif state == 'active':
        icon = '<span aria-hidden="true" style="width: 10px; height: 10px; border-radius: 50%; border: 2px solid #7FA6D9; box-sizing: border-box; flex-shrink: 0"></span>'; col = '#B9B9C0'
        text += '<span class="dot">…</span>'
    else:
        icon = warn_badge(12); col = '#F4F4F0'
    return '<li style="display: flex; gap: 8px; align-items: center; min-height: 18px; color: %s">%s<span>%s</span></li>' % (col, icon, text)

def drive_panel(header_left, header_right, bar_pct, body, bar_color='#FFD23F'):
    bar = ('<div aria-hidden="true" style="height: 4px; border-radius: 2px; background: #1E2E3A; overflow: hidden"><div style="width: %d%%; height: 100%%; background: %s"></div></div>' % (bar_pct, bar_color)) if bar_pct is not None else ''
    return ('<div style="position: absolute; left: 18px; right: 18px; top: 22px; height: 186px; background: #0B1218; border: 6px solid #232327; border-radius: 16px; box-sizing: border-box; padding: 12px 14px; display: flex; flex-direction: column; gap: 8px">'
            '<div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: 600; letter-spacing: 0.08em; color: #7FA6D9"><span role="heading" aria-level="2">%s</span><span>%s</span></div>%s%s</div>'
            ) % (header_left, header_right, bar, body)

def steps(*items):
    return '<ul aria-live="polite" style="list-style: none; margin: 2px 0 0; padding: 0; display: flex; flex-direction: column; gap: 6px; font-size: 14px">%s</ul>' % ''.join(items)

def cta_yellow(text, arrow=True, disabled=False):
    bg = '#232327' if disabled else '#FFD23F'; fg = '#6C6C74' if disabled else '#141416'
    return ('<a href="#"%s style="position: absolute; left: 18px; right: 18px; bottom: 26px; height: 58px; border-radius: 12px; background: %s; color: %s; display: flex; align-items: center; justify-content: space-between; padding: 0 18px; text-decoration: none; font-weight: 700; font-size: 17px">%s%s</a>'
            ) % (' aria-disabled="true"' if disabled else '', bg, fg, text, svg(RIGHT, 22, fg, 2.6) if arrow else '')

def message(text, sub=''):
    s = '<div style="font-size: 13px; line-height: 1.4; color: #B9C6D3">%s</div>' % sub if sub else ''
    return '<div role="alert" style="display: flex; flex-direction: column; gap: 6px; margin-top: 4px"><div style="font-size: 14px; line-height: 1.4; color: #F4F4F0">%s</div>%s</div>' % (text, s)

# 7 ---------------------------------------------------------------- Drive slow
STATES['5.4-drive-slow'] = page('Строим дорогу · дольше обычного', 'Screen 5.4 §4.2 slow: no `done` after 20 s.',
    drive_scene() + back_link(16, 18, 'Отменить', '#E9E2F2') +
    dashboard(540, drive_panel('СТРОИМ ДОРОГУ · 745 КМ', '3 ДНЯ', 40, steps(
        step('Делим кольцо на 3 дня по ≈ 250 км'), step('Ищем отели, куда пустят с собакой'),
        step('Сверяем, когда открыты кремли и музеи', 'active'), step('Строим дольше обычного…', 'active').replace('<span class="dot">…</span>', ''))) +
        '<div style="position: absolute; left: 18px; right: 18px; bottom: 26px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px">'
        '<button type="button" style="height: 58px; border-radius: 12px; border: 1px solid #3A3A42; background: #232327; color: #F4F4F0; font-family: inherit; font-weight: 600; font-size: 15px">Подождать</button>'
        '<button type="button" style="height: 58px; border-radius: 12px; border: none; background: #FFD23F; color: #141416; font-family: inherit; font-weight: 700; font-size: 17px">Упростить маршрут</button></div>'))

# 8 ---------------------------------------------------------------- Drive error
STATES['5.4-drive-error'] = page('Строим дорогу · ошибка', 'Screen 5.4 §4.4 error UPSTREAM (lane eased to idle speed; no new flying signs).',
    drive_scene('lane', posts=False, signs=False) + back_link(16, 18, 'Приборы', '#E9E2F2') +
    dashboard(540, drive_panel('НЕ ПОЛУЧИЛОСЬ', '', None, message('Сервис маршрутов временно недоступен', 'Параметры поездки сохранены — можно попробовать ещё раз.')) +
              cta_yellow('Попробовать ещё раз')))

# 9 ---------------------------------------------------------------- Drive offline
STATES['5.4-drive-offline'] = page('Строим дорогу · нет сети', 'Screen 5.4 §4.5 offline at send time.',
    drive_scene('lane', posts=False, signs=False) + back_link(16, 18, 'Приборы', '#E9E2F2') +
    dashboard(540, drive_panel(offline_plate(), '', None, message('Чтобы построить дорогу, нужен интернет.', 'Сохранённые поездки открываются без сети — на лобовом, в «Мои поездки».')) +
              cta_yellow('Попробовать ещё раз')))

# ---------------------------------------------------------------- Road ahead frame
def signs_header(title, km, saved=False):
    strip = ('<div aria-hidden="true" style="position: absolute; left: 0; right: 0; top: 0; height: 132px; overflow: hidden">'
            '<div style="position: absolute; left: 0; right: 0; top: 0; height: 50px; background: #2B2850"></div>'
            '<div style="position: absolute; left: 0; right: 0; top: 50px; height: 34px; background: #8E4A6B"></div>'
            '<div style="position: absolute; left: 0; right: 0; top: 84px; height: 26px; background: #D9655A"></div>'
            '<div style="position: absolute; left: 0; right: 0; top: 110px; height: 22px; background: #F29A5E"></div>'
            '<div style="position: absolute; left: 0; right: 0; top: 0; height: 14px; background: #0E0E10; border-radius: 0 0 50% 50% / 0 0 12px 12px"></div></div>')
    return strip + back_link(16, 18, 'Приборы', '#E9E2F2') + (
            '<button type="button" aria-label="%s" style="position: absolute; left: 290px; top: 12px; width: 44px; height: 44px; border: none; background: transparent; display: flex; align-items: center; justify-content: center; z-index: 4">%s</button>'
            '<button type="button" aria-label="Поделиться поездкой" style="position: absolute; left: 334px; top: 12px; width: 44px; height: 44px; border: none; background: transparent; display: flex; align-items: center; justify-content: center; z-index: 4">%s</button>'
            '<div role="heading" aria-level="1" aria-label="%s, %s километров" style="position: absolute; left: 20px; right: 20px; top: 56px; background: #1E4FA3; border-radius: 7px; padding: 3px; box-shadow: 0 6px 14px rgba(0,0,0,.35); z-index: 3">'
            '<div style="border: 2px solid #F4F4F0; border-radius: 5px; padding: 6px 10px; display: flex; justify-content: space-between; align-items: center">'
            '<span style="display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 20px">%s%s</span><span style="font-weight: 700; font-size: 20px">%s</span></div></div>'
            '<div style="position: absolute; left: 0; right: 0; top: 110px; height: 40px; background: #161618; border-radius: 50%% 50%% 0 0 / 30px 30px 0 0; z-index: 2"></div>'
            ) % ('Сохранено офлайн' if saved else 'Сохранить офлайн',
                 svg(BOOKMARK, 22, '#FFD23F', 2, fill='#FFD23F') if saved else svg(BOOKMARK, 22, '#E9E2F2', 2), svg(SHARE, 22, '#E9E2F2', 2),
                 title, km, svg(UR, 20, '#F4F4F0', 3), title, km)

def intro(chips):
    return ('<h1 style="margin: 0; font-weight: 700; font-size: 28px; line-height: 1.05">Дорога впереди</h1>'
            '<div style="margin-top: 6px; display: flex; flex-wrap: wrap; gap: 6px; font-size: 12px; font-weight: 600">%s</div>'
            '<p style="margin: 8px 0 0; font-size: 13px; color: #B9B9C0">Знаки по пути — как увидите их на трассе. Любой можно заменить.</p>'
            ) % ''.join('<span style="padding: 4px 9px; border-radius: 12px; background: #2A2A2E">%s</span>' % c for c in chips)

def status_plate(icon_html, text, link=None, border='#3A3A42', text_color='#B9B9C0'):
    l = '<a href="#" style="margin-left: auto; min-height: 44px; display: flex; align-items: center; padding-left: 8px; font-weight: 600; font-size: 13px; color: #FFD23F; text-decoration: none; white-space: nowrap">%s</a>' % link if link else ''
    return ('<div role="status" style="margin-top: 10px; padding: 10px 12px; border-radius: 10px; border: 1px solid %s; display: flex; align-items: center; gap: 10px; font-size: 13px; line-height: 1.4; color: %s">%s<span>%s</span>%s</div>'
            ) % (border, text_color, icon_html, text, l)

def day_warning(text):
    return ('<div role="status" style="margin: -4px 16px 6px 72px; display: flex; gap: 6px; align-items: flex-start; font-size: 12px; line-height: 1.35; color: #F4F4F0">%s<span>%s</span></div>' % (warn_badge(14), text))

def day_header(name, meta, link_disabled=False, first=True):
    link = ('<span aria-disabled="true" aria-label="Открыть день в навигаторе — нужен интернет" style="margin-left: auto; display: inline-flex; align-items: center; gap: 4px; font-size: 12px; font-weight: 600; color: #6C6C74; white-space: nowrap">' + svg(OFFLINE, 11, '#6C6C74', 2.4) + 'в навигатор</span>' if link_disabled
            else '<a href="#" style="margin-left: auto; font-size: 12px; font-weight: 600; color: #7FA6D9; text-decoration: none; white-space: nowrap">в навигатор ↗</a>')
    return ('<div role="heading" aria-level="2" style="margin: %s 16px 10px 72px; min-height: 19.5px; display: flex; align-items: baseline; gap: 8px">'
            '<span style="font-weight: 700; font-size: 15px; color: #FFD23F; white-space: nowrap">%s</span><span style="font-size: 12px; color: #8C8C93; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0">%s</span>%s</div>'
            ) % ('0' if first else '6px', name, meta, link)

def city_sign(text, warn=False):
    w = ('<span style="position: absolute; right: -4px; top: -8px">%s</span>' % warn_badge(16)) if warn else ''
    return ('<span style="position: relative; width: 64px; min-height: 40px; background: #F4F4F0; color: #141416; border: 3px solid #141416; outline: 2px solid #F4F4F0; border-radius: 4px; display: flex; align-items: center; justify-content: center; '
            'text-align: center; font-weight: 700; font-size: 11px; line-height: 1.05; padding: 3px 2px; box-sizing: border-box">%s%s</span>') % (text, w)

def tourist_sign():
    return ('<span style="width: 56px; height: 56px; background: #6B3E26; border-radius: 5px; padding: 3px; box-sizing: border-box; display: block"><span style="width: 100%%; height: 100%%; border: 2px solid #F4F4F0; border-radius: 3px; box-sizing: border-box; display: flex; align-items: center; justify-content: center">%s</span></span>'
            % svg(CHURCH, 30, '#F4F4F0', 2))

def service_sign(d, extra=''):
    return ('<span style="width: 50px; height: 62px; background: #1E4FA3; border-radius: 4px; padding: 5px; box-sizing: border-box; display: flex; flex-direction: column; align-items: center; gap: 4px">'
            '<span style="width: 40px; height: 40px; background: #F4F4F0; border-radius: 2px; display: flex; align-items: center; justify-content: center">%s</span>'
            '<span style="width: 22px; height: 3px; background: #F4F4F0; border-radius: 2px"></span></span>' % svg(d, 28, '#141416', 2.2, extra=extra))

def stop_row(sign, ahead, time, name, note, cost='', action='', aria=''):
    actions = ('<div style="display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-top: 2px"><span style="font-weight: 600; font-size: 13px; color: #FFD23F">%s</span>%s</div>' % (cost, action)) if (cost or action) else ''
    return ('<div role="group" aria-label="%s" style="display: grid; grid-template-columns: 72px 68px minmax(0, 1fr); align-items: start; padding: 8px 16px 12px 0">'
            '<div aria-hidden="true" style="position: relative; height: 100%%"><span style="position: absolute; left: 60px; top: 30px; width: 14px; height: 3px; background: #55565C"></span></div>'
            '<div aria-hidden="true" style="display: flex; justify-content: center">%s</div>'
            '<div style="min-width: 0; padding-left: 4px; display: flex; flex-direction: column; gap: 3px">'
            '<div style="display: flex; justify-content: space-between; gap: 8px; font-size: 12px; color: #8C8C93"><span>%s</span><span style="font-variant-numeric: tabular-nums">%s</span></div>'
            '<div style="font-weight: 700; font-size: 17px; line-height: 1.15">%s</div><div style="font-size: 13px; line-height: 1.4; color: #C4C4CA">%s</div>%s</div></div>'
            ) % (aria or '%s, %s, %s' % (ahead, time, name), sign, ahead, time, name, note, actions)

SWAP = lambda n: '<button type="button" aria-label="Заменить: %s" style="min-height: 36px; padding: 0 10px; border-radius: 8px; border: 1px solid #3A3A42; background: transparent; color: #B9B9C0; font-family: inherit; font-weight: 600; font-size: 12px">заменить</button>' % n
HOTEL_BTN = lambda town: '<a href="#" aria-label="Выбрать отель в %s" style="min-height: 36px; display: inline-flex; align-items: center; padding: 0 12px; border-radius: 8px; background: #1E4FA3; color: #F4F4F0; font-weight: 600; font-size: 13px; text-decoration: none">Выбрать отель →</a>' % town

def road_list(content, top):
    return ('<div style="position: absolute; left: 0; right: 0; top: %dpx; bottom: 0; overflow: hidden">'
            '<div aria-hidden="true" style="position: absolute; left: 14px; top: 0; bottom: 0; width: 46px; background: #3A3A3F; border-left: 3px solid #F4F4F0; border-right: 3px solid #F4F4F0; box-sizing: border-box">'
            '<div style="position: absolute; top: 0; bottom: 0; left: 50%%; width: 3px; margin-left: -1.5px; background: repeating-linear-gradient(to bottom,#F4F4F0 0 32px,transparent 32px 64px)"></div>'
            '<div style="position: absolute; left: 50%%; top: 120px; margin-left: 2px; width: 14px; height: 22px; border-radius: 5px 5px 3px 3px; background: #FFD23F; border: 2px solid #141416; box-sizing: border-box"></div></div>%s</div>'
            ) % (top, content)

def waybill_footer(label, amount, label_color='#55565C'):
    return ('<div aria-hidden="true" style="position: absolute; left: 0; right: 0; bottom: 88px; height: 24px; background: linear-gradient(to bottom, rgba(22,22,24,0), #161618); z-index: 4"></div>'
            '<div style="position: absolute; left: 0; right: 0; bottom: 0; height: 88px; background: #161618; z-index: 4"></div>'
            '<a href="%sWaybill.dc.html" style="position: absolute; left: 16px; right: 16px; bottom: 24px; height: 64px; border-radius: 12px; background: #F4F4F0; color: #141416; display: flex; align-items: center; justify-content: space-between; padding: 0 18px; text-decoration: none; z-index: 5">'
            '<span style="display: flex; flex-direction: column"><span style="font-size: 12px; font-weight: 600; color: %s">%s</span><span style="font-weight: 700; font-size: 22px">%s</span></span>%s</a>'
            ) % (CANVAS, label_color, label, amount, svg(RIGHT, 22, '#141416', 2.6))

# 10 ---------------------------------------------------------------- Road ahead NO_LODGING + over budget
STATES['5.5-road-ahead-no-lodging-over-budget'] = page('Дорога впереди · ночёвка не найдена, перерасход',
    'Screen 5.5 §4 NO_LODGING (overnight row without a hotel sign: city sign + warning badge, «ближайшая подходящая»), a day over its time budget (warning.DAY_OVER_BUDGET under the day header) and money over budget (red footer label). Scroll position 0; the footer is pinned.',
    signs_header('Ростов Великий', '200') +
    '<div style="position: absolute; left: 0; right: 0; top: 150px; padding: 0 20px">' + intro(['2 дня · 1 ночь', '2 взр · 1 реб · пёс', 'до 300 км в день']) +
    status_plate(warn_badge(16), 'Не нашли ночёвку с вашими условиями — показали ближайшую подходящую', border='#FFD23F', text_color='#F4F4F0') + '</div>' +
    road_list(day_header('День 1', '200 км · ≈ 3 ч за рулём') + day_warning('День 1 получился длинным — можно убрать остановку') +
        stop_row(city_sign('МОСКВА'), 'старт', '09:00', 'Москва', 'Выезд по Ярославскому шоссе, до пробок.') +
        stop_row(tourist_sign(), 'через 70 км', '10:15', 'Троице-Сергиева лавра', 'Сергиев Посад, полтора часа. Собака ждёт с одним из взрослых.', 'вход свободный', SWAP('Троице-Сергиева лавра')) +
        stop_row(city_sign('РОСТОВ ВЕЛИКИЙ', warn=True), 'через 130 км', '15:30', 'Ночёвка · Ростов Великий',
                 'Ближайшая подходящая: Усадьба на Неро, Ростов Великий, 6 км', '≈ 5 500 ₽', HOTEL_BTN('Ростове Великом'),
                 aria='Ночёвка: Ростов Великий, через 130 км, 15:30. Внимание: ближайшая подходящая — Усадьба на Неро, Ростов Великий, 6 километров'), 330) +
    waybill_footer('ПУТЕВОЙ ЛИСТ · ПЕРЕРАСХОД 2 300 ₽', '≈ 22 300 ₽', '#B3261E'),
    root_bg='#161618')

# 11 ---------------------------------------------------------------- Road ahead offline («Нужен интернет»)
STATES['5.5-road-ahead-offline'] = page('Дорога впереди · без сети', 'Screen 5.5 §4 offline: saved trip opened with no signal; the user tapped «в навигатор» → toast «Нужен интернет».',
    signs_header('Золотое кольцо', '745', saved=True) +
    '<div style="position: absolute; left: 0; right: 0; top: 150px; padding: 0 20px">' + intro(['3 дня · 2 ночи', '2 взр · 1 реб · пёс', 'до 300 км в день']) +
    status_plate(svg(OFFLINE, 16, '#E6604A', 2.2), 'Без сети: бронирование и навигатор недоступны') + '</div>' +
    road_list(day_header('День 1', '265 км · ≈ 4 ч за рулём', link_disabled=True) +
        stop_row(city_sign('МОСКВА'), 'старт', '08:00', 'Москва', 'Выезд по Ярославскому шоссе, до пробок.') +
        stop_row(tourist_sign(), 'через 70 км', '09:15', 'Троице-Сергиева лавра', 'Сергиев Посад, полтора часа. Собака ждёт с одним из взрослых.', 'вход свободный', SWAP('Троице-Сергиева лавра')) +
        stop_row(service_sign(FOOD), 'через 70 км', '12:00', 'Обед · Переславль-Залесский', 'Кафе у Плещеева озера, есть детское меню.', '≈ 1 800 ₽', SWAP('Обед · Переславль-Залесский'),
                 aria='Обед: Переславль-Залесский, через 70 км, 12:00'), 316) +
    toast('Нужен интернет, чтобы открыть навигатор', bottom=104) +
    waybill_footer('ПУТЕВОЙ ЛИСТ · СКОЛЬКО СТОИТ', '≈ 30 500 ₽'),
    root_bg='#161618')

# 12 ---------------------------------------------------------------- Waybill over budget
def hand(v, size=19, color='#1B3FA0'):
    return '<span style="font-family: \'Marck Script\', cursive; font-size: %dpx; color: %s; line-height: 1.2">%s</span>' % (size, color, v)

def cost_line(name, calc, total):
    return ('<button type="button" aria-expanded="false" style="width: 100%%; display: grid; grid-template-columns: minmax(0, 1fr) 70px; min-height: 44px; border: none; border-bottom: 1px solid #9FB0BE; background: transparent; padding: 0; font-family: inherit; color: #22313D; text-align: left">'
            '<span style="padding: 3px 6px; border-right: 1px solid #22313D; display: flex; flex-direction: column"><span style="font-weight: 600; font-size: 13px">%s</span>'
            '<span style="font-family: \'Marck Script\', cursive; font-size: 15px; color: #1B3FA0; line-height: 1.15">%s</span></span>'
            '<span style="padding: 3px 6px; text-align: right; align-self: center">%s</span></button>') % (name, calc, hand(total))

STATES['5.6-waybill-over-budget'] = page('Путевой лист · перерасход', 'Screen 5.6 §3 over budget: budget 20 000 ₽, total ≈ 30 500 ₽ (D-16 numbers), «Перерасход» in color.paper.inkRed + hint. Stamp at its final frame.',
    '<div style="position: absolute; inset: 0; box-sizing: border-box; padding: 14px 14px 20px; display: flex; flex-direction: column">'
    + back_link(14, 14, 'Дорога впереди').replace('position: absolute; left: 14px; top: 14px; ', 'position: relative; align-self: flex-start; ') +
    '<div style="position: relative; margin-top: 18px; background: #EEF2F4; color: #22313D; border-radius: 4px; padding: 26px 16px 14px; box-shadow: 0 10px 26px rgba(0,0,0,.5)">'
    '<div aria-hidden="true" style="position: absolute; left: 50%; top: -14px; width: 120px; margin-left: -60px; height: 30px; border-radius: 8px; background: #8C8C93; box-shadow: inset 0 -4px 0 #5D5D63"></div>'
    '<div style="display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 2px solid #22313D; padding-bottom: 6px"><div>'
    '<div style="font-size: 11px; letter-spacing: 0.08em; color: #53687C">ФОРМА ПОЕЗДКИ · ВЕРСТА</div><div style="font-weight: 700; font-size: 20px; line-height: 1.05">ПУТЕВОЙ ЛИСТ</div>'
    '<div style="font-size: 12px">легкового автомобиля</div></div><div style="text-align: right; font-size: 11px; color: #53687C">№ ' + hand('001', 20) + '</div></div>'
    '<div style="margin-top: 8px; display: grid; grid-template-columns: 92px minmax(0, 1fr); row-gap: 4px; align-items: baseline">'
    + ''.join('<span style="font-size: 11px; color: #53687C">%s</span><span style="border-bottom: 1px solid #9FB0BE">%s</span>' % (a, hand(b)) for a, b in
              [('Маршрут', 'Москва — Золотое кольцо — Москва'), ('Экипаж', '2 взр., 1 реб., собака'), ('Пробег, км', '745 за 3 дня')]) + '</div>'
    '<div style="margin-top: 10px; border: 1.5px solid #22313D">'
    '<div style="display: grid; grid-template-columns: minmax(0, 1fr) 70px; font-size: 11px; letter-spacing: 0.06em; color: #53687C; border-bottom: 1.5px solid #22313D">'
    '<span style="padding: 3px 6px; border-right: 1px solid #22313D">СТАТЬЯ И РАСЧЁТ</span><span style="padding: 3px 6px; text-align: right">₽</span></div>'
    + cost_line('Бензин АИ-95', '745 км × 8 л/100 × 62,40 ₽', '3 720') + cost_line('Платные дороги', 'нет платных участков', '0')
    + cost_line('Ночёвки', 'Ярославль + Суздаль, 2 × 6 000', '12 000') + cost_line('Питание', '3 чел. × 5 приёмов × 600', '9 000')
    + cost_line('Билеты', 'кремли и музеи на троих', '3 000') +
    '<button type="button" role="switch" aria-checked="true" style="width: 100%; display: grid; grid-template-columns: minmax(0, 1fr) 70px; border: none; border-bottom: 1.5px solid #22313D; background: transparent; padding: 0; font-family: inherit; color: #22313D; text-align: left; min-height: 44px">'
    '<span style="padding: 3px 6px; border-right: 1px solid #22313D; display: flex; align-items: center; gap: 8px"><span aria-hidden="true" style="width: 18px; height: 18px; border: 1.5px solid #22313D; display: flex; align-items: center; justify-content: center; box-sizing: border-box">'
    + svg('M5 13c1.5 1 3 2.6 4 4.5 2.5-5 6-9.5 10-12.5', 16, '#1B3FA0', 2) + '</span><span style="display: flex; flex-direction: column"><span style="font-weight: 600; font-size: 13px">Резерв 10%</span>'
    '<span style="font-size: 11px; color: #53687C">на пробки и «давай заедем»</span></span></span><span style="padding: 3px 6px; text-align: right; align-self: center">' + hand('2 770') + '</span></button>'
    '<div style="display: grid; grid-template-columns: minmax(0, 1fr) 100px; align-items: center"><span style="padding: 6px; font-weight: 700; font-size: 14px">ИТОГО</span>'
    '<span style="padding: 4px 6px; text-align: right">' + hand('≈ 30 500', 26) + '</span></div></div>'
    '<div style="margin-top: 8px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; font-size: 11px; color: #53687C">'
    '<span>Выдано<span style="display: block; border-bottom: 1px solid #9FB0BE">' + hand('20 000') + '</span></span>'
    '<span style="color: #B3261E; font-weight: 600">Перерасход<span style="display: block; border-bottom: 1px solid #9FB0BE; font-weight: 400">' + hand('10 500', 19, '#B3261E') + '</span></span></div>'
    '<div style="margin-top: 4px; padding-right: 100px; font-size: 11px; line-height: 1.3; color: #22313D">Дешевле: другая ночёвка, меньше музеев или «Просто доехать»</div>'
    '<div style="margin-top: 6px; padding-right: 100px; font-size: 11px; line-height: 1.3; color: #53687C">Пример расчёта: цены средние по трассе на октябрь 2026, точные — при бронировании.</div>'
    '<div aria-hidden="true" style="position: absolute; right: 12px; bottom: -30px; width: 88px; height: 88px; border-radius: 50%; border: 3px solid #5B3FA0; color: #5B3FA0; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; font-weight: 700; font-size: 10px; letter-spacing: 0.06em; line-height: 1.2; box-shadow: inset 0 0 0 3px #EEF2F4, inset 0 0 0 4px #5B3FA0; transform: rotate(-14deg); opacity: .85">ВЕРСТА<br><span style="font-size: 15px">В ПУТЬ</span>ГОТОВЫ</div>'
    '</div>'
    '<div style="margin-top: auto; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px">'
    '<button type="button" style="height: 56px; border-radius: 12px; border: 1px solid #3A3A42; background: #232327; color: #F4F4F0; font-family: inherit; font-weight: 600; font-size: 15px">Сохранить офлайн</button>'
    '<button type="button" style="height: 56px; border-radius: 12px; border: none; background: #FFD23F; color: #141416; font-family: inherit; font-weight: 700; font-size: 15px">Отправить экипажу</button></div></div>',
    root_bg='#161618')

# 13 ---------------------------------------------------------------- Exit offline
def hotel_opt(name, tags, price, sel):
    radio = ('width: 18px; height: 18px; border-radius: 50%%; flex-shrink: 0; box-sizing: border-box; border: 2px solid %s; box-shadow: %s'
             % ('#FFD23F' if sel else '#5A7893', 'inset 0 0 0 4px #0B1218, inset 0 0 0 9px #FFD23F' if sel else 'none'))
    return ('<button type="button" role="radio" aria-checked="%s" style="width: 100%%; min-height: 60px; display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-radius: 10px; font-family: inherit; color: #F4F4F0; background: %s; border: 1px solid %s">'
            '<span aria-hidden="true" style="%s"></span><span style="flex: 1; min-width: 0; display: flex; flex-direction: column; text-align: left"><span style="font-weight: 700; font-size: 15px">%s</span>'
            '<span style="font-size: 12px; color: #8FA4B8">%s</span></span><span style="font-weight: 700; font-size: 15px; color: #FFD23F; white-space: nowrap">%s</span></button>'
            ) % ('true' if sel else 'false', '#16222C' if sel else 'transparent', '#FFD23F' if sel else '#2B3D4D', radio, name, tags, price)

STATES['5.7-exit-offline'] = page('Съезд к ночёвке · без сети', 'Screen 5.7 §4 offline: hotels selectable, booking CTA in its offline variant («Нужен интернет»).',
    '<div aria-hidden="true" style="position: absolute; left: 0; right: 0; top: 0; height: 430px; overflow: hidden">'
    '<div style="position: absolute; left: 0; right: 0; top: 0; height: 150px; background: #121130"></div>'
    '<div style="position: absolute; left: 0; right: 0; top: 150px; height: 60px; background: #2B2850"></div>'
    '<div style="position: absolute; left: 0; right: 0; top: 210px; height: 30px; background: #4E3768"></div>'
    '<div style="position: absolute; left: 60px; top: 40px; width: 3px; height: 3px; border-radius: 50%; background: #F4F4F0"></div>'
    '<div style="position: absolute; left: 150px; top: 80px; width: 2px; height: 2px; border-radius: 50%; background: #F4F4F0"></div>'
    '<div style="position: absolute; left: 300px; top: 30px; width: 3px; height: 3px; border-radius: 50%; background: #F4F4F0"></div>'
    '<div style="position: absolute; left: 70px; top: 46px; width: 40px; height: 40px; border-radius: 50%; background: #F2E3B3; overflow: hidden"><span style="position: absolute; left: 12px; top: -6px; width: 40px; height: 40px; border-radius: 50%; background: #121130; display: block"></span></div>'
    '<div style="position: absolute; left: 0; right: 0; top: 240px; bottom: 0; background: #1A231F"></div>'
    + road(240, 190, 200, 230, 900, 76, 6, 8, 'lane', '#2E2E33', '#D9D9D2') +
    '<div style="position: absolute; left: 70px; right: 70px; top: 300px; bottom: 0; background: rgba(255,236,170,.10); clip-path: polygon(42% 0, 58% 0, 100% 100%, 0 100%)"></div>'
    '<div style="position: absolute; right: 70px; top: 196px; width: 6px; height: 100px; background: #55565C"></div>' + liner_pillars(430) + '</div>'
    '<div role="img" aria-label="Указатель: съезд на Ярославль, центр, гостиница через 800 метров" style="position: absolute; right: 30px; top: 92px; width: 190px; background: #1E4FA3; border-radius: 8px; padding: 4px; box-shadow: 0 8px 22px rgba(0,0,0,.5)">'
    '<div style="border: 2px solid #F4F4F0; border-radius: 5px; padding: 8px 10px; display: flex; flex-direction: column; gap: 6px"><div style="display: flex; align-items: center; justify-content: space-between; gap: 8px">'
    '<span style="font-weight: 700; font-size: 20px; line-height: 1.05">Ярославль<br><span style="font-size: 15px; font-weight: 600">центр</span></span>' + svg('M7 7l10 10M17 9v8H9', 30, '#F4F4F0', 3) + '</div>'
    '<div style="display: flex; align-items: center; gap: 8px"><span style="width: 34px; height: 34px; background: #F4F4F0; border-radius: 2px; display: flex; align-items: center; justify-content: center">'
    + svg(HOTEL, 24, '#141416', 2.2, extra='<circle cx="7" cy="11" r="2"></circle>') + '</span><span style="font-weight: 700; font-size: 18px">800 м</span></div></div></div>'
    + dashboard(410, back_link(20, 14, 'Дорога впереди') +
        '<div aria-hidden="true" class="turn" style="position: absolute; right: 24px; top: 20px; display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: #6FD18A">'
        + svg('M14 5l7 7-7 7v-4H3V9h11z', 18, '#6FD18A', fill='#6FD18A') + 'поворотник</div>'
        '<div style="position: absolute; left: 14px; right: 14px; top: 54px; bottom: 98px; background: #0B1218; border: 6px solid #232327; border-radius: 16px; box-sizing: border-box; padding: 12px; display: flex; flex-direction: column; gap: 8px">'
        '<div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: 600; letter-spacing: 0.08em; color: #7FA6D9"><span>НОЧЁВКА 1 ИЗ 2 · КМ 265 · 16:30</span>' + offline_plate() + '</div>'
        '<div role="heading" aria-level="2" style="font-weight: 700; font-size: 22px; line-height: 1.1">Ярославль</div>'
        '<div style="font-size: 13px; line-height: 1.4; color: #B9C6D3">Не в Ростове, а на 55 км дальше: тут больше отелей с собакой, а вечером можно дойти до Стрелки. Ваши 300 км в день не превышены.</div>'
        '<div role="radiogroup" aria-label="Где ночуем" style="display: flex; flex-direction: column; gap: 8px">'
        + hotel_opt('У Стрелки, в центре', 'можно с собакой · семейный номер · парковка', '≈ 6 000 ₽', True)
        + hotel_opt('У въезда с трассы', 'можно с собакой · охраняемая парковка', '≈ 4 500 ₽', False) + '</div></div>'
        '<a href="#" aria-disabled="true" aria-label="Забронировать ночь — нужен интернет" style="position: absolute; left: 14px; right: 14px; bottom: 24px; height: 60px; border-radius: 12px; background: #232327; color: #B9B9C0; display: flex; align-items: center; padding: 0 18px; text-decoration: none">'
        '<span style="display: flex; flex-direction: column"><span style="font-weight: 700; font-size: 18px; line-height: 1.1">Забронировать ночь</span>'
        '<span style="display: inline-flex; align-items: center; gap: 4px; font-size: 12px; font-weight: 500; color: #E6604A">' + svg(OFFLINE, 12, '#E6604A', 2.4) + 'Нужен интернет</span></span></a>'))

# ---------------------------------------------------------------- token check
def token_values():
    t = json.load(open(os.path.join(DESIGN, 'tokens.json')))
    hexes, alphas = set(), set()
    def walk(d):
        for k, v in d.items():
            if isinstance(v, dict):
                if isinstance(v.get('value'), str) and v['value'].startswith('#'):
                    hexes.add(v['value'].upper()); alphas.add((v['value'].upper(), float(v.get('alpha', 1))))
                if isinstance(v.get('color'), str):
                    alphas.add((v['color'].upper(), float(v.get('alpha', 1))))
                walk(v)
    walk(t)
    return hexes, alphas

def check_states_tokens(paths):
    hexes, alphas = token_values(); bad = []
    for p in paths:
        s = open(p).read()
        for h in re.findall(r'#[0-9A-Fa-f]{6}\b', s):
            if h.upper() not in hexes: bad.append((os.path.basename(p), h))
        for r, g, b, a in re.findall(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)', s):
            hx = '#%02X%02X%02X' % (int(r), int(g), int(b)); a = float(a)
            ok = hx in hexes and (a == 0 or (hx, a) in alphas or a == 1)
            if not ok: bad.append((os.path.basename(p), 'rgba(%s,%s,%s,%s)' % (r, g, b, a)))
    return bad

def main():
    if '--check' not in sys.argv:
        os.makedirs(OUT, exist_ok=True)
        for name, html in STATES.items():
            open(os.path.join(OUT, name + '.dc.html'), 'w').write(html)
        print('wrote %d state canvases to %s' % (len(STATES), os.path.normpath(OUT)))
    files = sorted(glob.glob(os.path.join(OUT, '*.dc.html')))
    bad = check_states_tokens(files)
    print('token check: %d files, %s' % (len(files), 'all colours are tokens' if not bad else 'NOT TOKENS: %s' % bad))
    return 1 if bad else 0

if __name__ == '__main__':
    sys.exit(main())
