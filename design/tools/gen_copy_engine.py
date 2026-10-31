#!/usr/bin/env python3
"""Regenerate copy-ru.md §11 (reasons.ru.json) and §12 (strings.ru.json) from the engine resources.

The tables live between the markers `<!-- BEGIN engine tables -->` and `<!-- END engine tables -->` in
design/copy-ru.md. Each key gets its exact text, parameters, an example and the worst-case rendered length
(limit 140, DES-004), plus the Designer's review verdict from VERDICTS (default "OK").

Usage: python3 design/tools/gen_copy_engine.py [--check]   (--check: exit 1 if the deck is stale)
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DECK = os.path.join(ROOT, 'design', 'copy-ru.md')
RES = os.path.join(ROOT, 'backend', 'planner', 'verst_planner', 'resources')
BEGIN, END = '<!-- BEGIN engine tables (design/tools/gen_copy_engine.py) -->', '<!-- END engine tables -->'
LIMIT = 140
LONG_TOWN = 'Переславле-Залесском'
WORST = dict(shift='Не в %s, а на 120 км дальше' % LONG_TOWN, daily_km=900, other_prep=LONG_TOWN, dkm=120, dir='дальше',
             route='Нижний Новгород → Казань', km=120, min=20, min_word='минут', drive='полутора часов',
             who='ребёнку побегать, собаке погулять', town_prep=LONG_TOWN, dwell='Полтора часа', time='08:00',
             part_of_day='вечеру', n=4, days_word='дня', consumption='12,5', day=3, name='Ростовский кремль и музей-заповедник')
EXAMPLE = dict(shift='Не в Ростове Великом, а на 55 км дальше', daily_km=300, other_prep='Ростове Великом', dkm=55, dir='дальше',
               route='Золотое кольцо', km=40, min=20, min_word='минут', drive='двух часов', who='ребёнку побегать, собаке погулять',
               town_prep='Иванове', dwell='Полтора часа', time='08:00', part_of_day='вечеру', n=3, days_word='дня', consumption='8,0',
               day=2, name='Ипатьевский монастырь')
APPEND_CAP = ('overnight.shift.hotels', 'overnight.shift.quality', 'overnight.shift.evening')
WHERE = [('overnight.', 'Exit reason sentence (5.7 D7), Road-ahead hotel-row note'), ('crew_suffix.', 'suffix inside overnight.shift.hotels'),
         ('fuel.', 'Road-ahead fuel-row note'), ('rest.', 'Road-ahead rest-row note'), ('lunch.', 'Road-ahead lunch-row note'),
         ('sight.', 'Road-ahead sight-row note'), ('start.', 'Road-ahead start-row note'), ('finish.', 'Road-ahead finish-row note'),
         ('stage.', 'Drive step line (5.4 D5)'), ('hint.', 'Waybill over-budget hints (long form)'), ('warning.', 'Road-ahead plates / day lines, Drive warning step'),
         ('via.', 'Road-ahead via-row note'), ('alternatives.', 'Replace sheet D-6 body / note')]
VERDICTS = {
    'rest.generic': 'OK — R-2 resolved (`{min_word}`)',
    'rest.who': 'OK — R-2 resolved',
    'sight.default': 'OK — R-3 resolved (renderer capitalises the first letter)',
    'sight.dog_waits': 'OK — R-3 resolved',
    'stage.fuel': 'OK — R-4 resolved (`fmt_consumption`, «8,0»)',
    'warning.DAY_OVER_BUDGET': 'R-5: key says "budget", text is about time; rename to `DAY_TOO_LONG` at the next contract version',
    'overnight.shift.later': 'fragment — only used as `{shift}`', 'overnight.shift.earlier': 'fragment — only used as `{shift}`',
    'overnight.shift.limit': 'fragment — only used as `{shift}`', 'overnight.cap_ok': 'appended; starts with a space by design',
    'crew_suffix.none': 'empty by design', 'finish.home': 'OK; `part_of_day` gives «обеду / ужину / вечеру»',
    'alternatives.none': 'OK — the replace sheet shows this engine text (state `replace-none-note`); no UI duplicate',
    'warning.STOP_CLOSED': 'OK — shown as a day line on 5.5 (day-level warning)',
}
S_VERDICTS = {
    'cost.title.food': 'OK — R-1 resolved', 'cost.title.reserve': 'OK — R-1 resolved', 'cost.title.fuel': 'OK — R-1 resolved',
    'cost.reserve': 'OK — R-1 resolved', 'share.total': 'D-11 follows this format', 'cost.food.uniform': 'D-16: «3 чел. × 5 приёмов × 600»',
    'suggest.sub.city': 'OK — the Navigator suggestion sub-line comes from the engine; no UI duplicate',
    'suggest.sub.place': 'OK — as above', 'warning.nearest': 'used on Exit; Road ahead uses `note.nearest`',
    'cost.tickets.none': 'same text as `road_free`', 'cost.fuel.many': 'R-6: long, wraps to 2 lines on the Waybill (allowed)',
}


class Strict(dict):
    def __missing__(self, k):
        raise KeyError(k)


def esc(t: str) -> str:
    return t.replace('|', '\\|') if t else '(empty)'


def build() -> str:
    r = json.load(open(os.path.join(RES, 'reasons.ru.json'), encoding='utf-8'))
    s = json.load(open(os.path.join(RES, 'strings.ru.json'), encoding='utf-8'))
    WORST['crew_suffix'] = EXAMPLE['crew_suffix'] = r.get('crew_suffix.dog', '')
    rows, longest, over = [], 0, []
    for k, v in r.items():
        worst, ex = v.format_map(Strict(WORST)), v.format_map(Strict(EXAMPLE))
        if k in APPEND_CAP:
            worst += r['overnight.cap_ok'].format_map(Strict(WORST)); ex += r['overnight.cap_ok'].format_map(Strict(EXAMPLE))
        worst, ex = worst.strip(), ex.strip()
        worst, ex = worst[:1].upper() + worst[1:], ex[:1].upper() + ex[1:]
        longest = max(longest, len(worst))
        params = ', '.join(sorted(set(re.findall(r'\{(\w+)\}', v)))) or '—'
        where = next((w for p, w in WHERE if k.startswith(p)), 'engine text')
        if len(worst) > LIMIT:
            over.append(k)
        verdict = VERDICTS.get(k, 'OK') if len(worst) <= LIMIT else 'TOO LONG: over %d characters' % LIMIT
        rows.append('| `%s` | %s | %s | %s | %s | %d | %s |' % (k, esc(v), params, where, esc(ex), len(worst), verdict))
    out = [BEGIN, '', '## 11. Engine reason templates — `reasons.ru.json`', '',
           'Every key of `backend/planner/verst_planner/resources/reasons.ru.json` (%d keys), regenerated by `design/tools/gen_copy_engine.py`. '
           '"Example" renders the template with the Golden-Ring data (first letter capitalised, as the renderer does); "max" is the worst case '
           '(«%s», 120 km shift, 900 km/day, dog; the `overnight.shift.*` rows include the appended `overnight.cap_ok`). Limit %d characters; '
           'the longest rendered reason is %d characters%s.' % (len(r), LONG_TOWN, LIMIT, longest, ' — **all pass**' if not over else ' — %d OVER' % len(over)), '',
           '| Key | Template | Params | Where it shows | Example | max | Review |', '| --- | --- | --- | --- | --- | --- | --- |'] + rows
    out += ['', '## 12. Engine UI strings — `strings.ru.json`', '',
            'Shown to the user through cost formulas, labels, suggestion sub-lines, share text and notes; the app never duplicates them.', '',
            '| Key | Text | Review |', '| --- | --- | --- |']
    for k, v in s.items():
        val = ', '.join(v) if isinstance(v, list) else v
        out.append('| `%s` | %s | %s |' % (k, esc(val), S_VERDICTS.get(k, 'OK')))
    out += ['', END]
    return '\n'.join(out)


def main() -> int:
    deck = open(DECK, encoding='utf-8').read()
    if BEGIN not in deck:
        a, b = deck.index('## 11. Engine reason templates'), deck.index('## 13.')
        deck = deck[:a] + BEGIN + '\n' + END + '\n\n' + deck[b:]
    a, b = deck.index(BEGIN), deck.index(END) + len(END)
    new = deck[:a] + build() + deck[b:]
    if '--check' in sys.argv:
        stale = new != open(DECK, encoding='utf-8').read()
        print('gen_copy_engine --check: %s' % ('STALE (run gen_copy_engine.py)' if stale else 'up to date'))
        return 1 if stale else 0
    open(DECK, 'w', encoding='utf-8').write(new)
    print('copy-ru.md §11–12 regenerated')
    return 0


if __name__ == '__main__':
    sys.exit(main())
