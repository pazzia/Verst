"""WCAG 2.2 contrast ratios for every text/background (and key UI boundary) pair used in variants A, B, C.

Usage: python3 -I design/variants-ir/tools/contrast.py [--md]
Reads design/variants-ir/tokens-day.json (B) and the night values from design/tokens.json (A, C).
Alpha colours are composited over their stated background before measuring.
"""
import json, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
night = json.loads((ROOT / "design/tokens.json").read_text())
day = json.loads((ROOT / "design/variants-ir/tokens-day.json").read_text())


def tok(tree, path):
    node = tree
    for p in path.split("."):
        node = node[p]
    return node["value"] if isinstance(node, dict) else node


def lum(hexv):
    h = hexv.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# (theme, fg token, bg token, size/role, required)
# required: 4.5 normal text, 3.0 large text (>= 18.66 px bold / 24 px) or non-text UI boundary (WCAG 1.4.11)
NIGHT = [
    ("text.primary", "dash.base", "основной текст на приборной панели", 4.5),
    ("text.secondary", "dash.base", "вторичный текст 14–15 sp", 4.5),
    ("text.secondary", "dash.raised", "вторичный текст на «Приборах»", 4.5),
    ("text.muted", "dash.raised", "подписи 14 sp (C, подзаголовки разделов)", 4.5),
    ("text.primary", "dash.controlAlt", "цифра степпера / текст чипа", 4.5),
    ("accent.yellow", "chip.selectedFill", "выбранный чип: текст", 4.5),
    ("text.onLight", "accent.yellow", "главная кнопка «Построить маршрут»", 4.5),
    ("sign.white", "sign.blue", "название на синем указателе", 4.5),
    ("sign.blueText", "sign.blue", "строка смысла на указателе 14 sp", 4.5),
    ("accent.yellow", "sign.blueSelected", "нажатая строка указателя", 4.5),
    ("text.onLight", "sign.white", "поле «Куда едем?» (A)", 4.5),
    ("text.onLightMuted", "sign.white", "подсказка в поле (A)", 4.5),
    ("navi.label", "navi.screen", "«из Москвы» на экране навигатора (A)", 4.5),
    ("navi.label", "dash.base", "«из Москвы» рядом с заголовком (C)", 4.5),
    ("sign.white", "sign.blue", "стрелка на табличке-иконке списка (C, 1.4.11)", 3.0),
    ("mirror.label", "sky.band1", "подпись экипажа под зеркалом", 4.5),
    ("mirror.label", "sky.band2", "кнопка «Назад» на небе (Приборы)", 4.5),
    ("text.primary", "dash.well", "значение в колодце прибора", 4.5),
    ("text.secondary", "dash.well", "подпись в колодце прибора", 4.5),
    ("accent.yellow", "dash.raised", "рамка выбранного чипа (граница)", 3.0),
    ("chip.border", "dash.raised", "рамка невыбранного чипа и клавиш (граница, новый токен)", 3.0),
    ("chip.border", "dash.base", "контур ссылки «По городу пешком» (граница)", 3.0),
    ("accent.yellow", "dash.raised", "кольцо фокуса", 3.0),
]
DAY = [
    ("text.primary", "dash.base", "основной текст на панели", 4.5),
    ("text.secondary", "dash.base", "вторичный текст на панели", 4.5),
    ("text.primary", "dash.raised", "основной текст на «Приборах»", 4.5),
    ("text.secondary", "dash.raised", "вторичный текст на «Приборах»", 4.5),
    ("text.muted", "dash.raised", "подписи разделов 14 sp", 4.5),
    ("text.muted", "dash.base", "строка «Демо-версия» на панели", 4.5),
    ("text.primary", "key.fill", "цифра степпера / текст чипа", 4.5),
    ("chip.selectedText", "chip.selectedFill", "выбранный чип: текст", 4.5),
    ("text.onCta", "cta.fill", "главная кнопка", 4.5),
    ("sign.white", "sign.blue", "название на указателе", 4.5),
    ("sign.blueText", "sign.blue", "строка смысла на указателе", 4.5),
    ("accent.yellowOnSign", "sign.blueSelected", "нажатая строка указателя", 4.5),
    ("navi.text", "navi.field", "поле «Куда едем?»", 4.5),
    ("navi.hint", "navi.field", "подсказка в поле", 4.5),
    ("navi.label", "navi.screen", "«из Москвы» на экране навигатора", 4.5),
    ("mirror.label", "sky.band1", "подпись экипажа под зеркалом", 4.5),
    ("text.primary", "sky.band1", "кнопка «Назад» и заголовок на небе", 4.5),
    ("text.secondary", "sky.band2", "подзаголовок на небе (Приборы)", 4.5),
    ("text.primary", "well.fill", "значение в колодце прибора", 4.5),
    ("text.secondary", "well.fill", "подпись в колодце прибора", 4.5),
    ("link", "dash.base", "текстовая ссылка (токен на будущее; в макетах не использован)", 4.5),
    ("key.border", "dash.base", "контур кнопки «По городу пешком»", 3.0),
    ("text.secondary", "sky.band1", "подзаголовок «из Москвы · 761 км» на небе (Приборы)", 4.5),
    ("navi.fieldBorder", "navi.screen", "граница поля (1.4.11)", 3.0),
    ("chip.selectedBorder", "dash.raised", "рамка выбранного чипа", 3.0),
    ("key.border", "dash.raised", "граница кнопок и чипов", 3.0),
    ("cta.border", "dash.base", "контур главной кнопки на светлой панели", 3.0),
    ("focus", "dash.raised", "кольцо фокуса", 3.0),
    ("focus", "dash.base", "кольцо фокуса на панели", 3.0),
]
# New night tokens proposed by the variants (README §6); not in design/tokens.json yet.
EXTRA_NIGHT = {"chip.selectedFill": "#1F1F17", "chip.border": "#707078"}


def nv(path):
    if path in EXTRA_NIGHT:
        return EXTRA_NIGHT[path]
    return tok(night["color"], path)


def dv(path):
    return tok(day["color"], path)


rows = []
for fg, bg, role, req in NIGHT:
    rows.append(("A, C (ночь)", fg, nv(fg), bg, nv(bg), role, req))
for fg, bg, role, req in DAY:
    rows.append(("B (день)", fg, dv(fg), bg, dv(bg), role, req))

md = "--md" in sys.argv
fails = 0
if md:
    print("| Тема | Цвет | Фон | Где | Нужно | Есть |")
    print("| --- | --- | --- | --- | --- | --- |")
for theme, fg, fgv, bg, bgv, role, req in rows:
    r = ratio(fgv, bgv)
    ok = r >= req
    fails += not ok
    if md:
        print(f"| {theme} | `{fg}` {fgv} | `{bg}` {bgv} | {role} | {req:.1f} | **{r:.2f}**{'' if ok else ' ✗'} |")
    else:
        print(f"{'OK ' if ok else 'FAIL'} {theme:12} {r:5.2f} (≥{req}) {fg} {fgv} on {bg} {bgv} — {role}")
if not md:
    print(f"\n{len(rows)} pairs, {fails} below AA")
sys.exit(1 if fails else 0)
