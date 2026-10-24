#!/usr/bin/env python3
"""DES-101: design/copy-ru.md -> android/core-ui/src/main/res/values/{strings,plurals}.xml

Reads every table row `| `key` | text | notes |` of copy-ru.md §1–10 and §14 (the "Text" column is found
from each table's header) and the §9 plural table (one / few / many / other). Engine sections §11–13 are
skipped: the app never duplicates engine text.

Transformations (copy-ru.md §0):
  * {name} -> %n$s / %n$d, numbered by first appearance; integer counts get d (INT_NAMES)
  * typography: U+00A0 between a number/placeholder and a unit, after «≈» and «№»; U+202F in digit groups
  * XML escape (& < >), Android escape (\\ ' " and a leading @ or ?), a literal % becomes %% when the
    string has placeholders, otherwise the string gets formatted="false"
  * a text cell wrapped in straight double quotes keeps its leading/trailing spaces (emitted as "…")
  * «ёлочки», ё, U+202F, U+00A0 are written as real characters

Usage:  python3 design/tools/gen_strings.py          write the files
        python3 design/tools/gen_strings.py --check  exit 0 if current, 1 with a diff otherwise
"""
from __future__ import annotations

import difflib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DECK = os.path.join(ROOT, 'design', 'copy-ru.md')
RES = os.path.join(ROOT, 'android', 'core-ui', 'src', 'main', 'res', 'values')
OUT_STRINGS = os.path.join(RES, 'strings.xml')
OUT_PLURALS = os.path.join(RES, 'plurals.xml')

UI_SECTIONS = {1, 2, 3, 4, 5, 6, 7, 8, 10, 14, 15}
PLURAL_SECTION = 9
QUANTITIES = ('one', 'few', 'many', 'other')
INT_NAMES = {'n', 'k', 'd', 'a', 'c', 'h', 'm', 'min', 'nights', 'adults', 'children'}
UNITS = ('км', 'мин', 'м', 'ч', 'л', '₽')
KEY_RE = re.compile(r'[a-z][a-z0-9_]*')
NBSP, NNBSP = ' ', ' '
HEADER = ('<?xml version="1.0" encoding="utf-8"?>\n'
          '<!-- GENERATED from design/copy-ru.md by design/tools/gen_strings.py. Do not edit: change the deck and regenerate. -->\n')


class DeckError(Exception):
    pass


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip('|').split('|')]


def parse_deck(text: str):
    strings: list[tuple[str, str, str]] = []   # key, text, comment
    plurals: list[tuple[str, list[str]]] = []
    section = None
    header: list[str] | None = None
    for raw in text.split('\n'):
        m = re.match(r'## (\d+)\.', raw)
        if m:
            section = int(m.group(1)); header = None
            continue
        if not raw.startswith('|'):
            header = None
            continue
        row = cells(raw)
        if header is None:
            header = [c.lower() for c in row]
            continue
        if set(''.join(row)) <= set('-: '):
            continue
        if section not in UI_SECTIONS and section != PLURAL_SECTION:
            continue
        keys = re.findall(r'`([^`]+)`', row[0])
        if len(keys) != 1 or row[0] != '`%s`' % keys[0] or not KEY_RE.fullmatch(keys[0]):
            raise DeckError('§%s: key cell must be exactly one `key`: %r' % (section, raw[:90]))
        key = keys[0]
        if section == PLURAL_SECTION:
            idx = [header.index(q) for q in QUANTITIES]
            forms = [row[i] for i in idx]
            if len(row) != len(header) or any(not f for f in forms):
                raise DeckError('plural %s must have exactly 4 quantities' % key)
            plurals.append((key, forms))
            continue
        if 'text' not in header:
            raise DeckError('§%s table without a Text column: %r' % (section, header))
        t = row[header.index('text')]
        if '`' in t:
            raise DeckError('%s: text contains a code span, not copy: %r' % (key, t))
        note = row[header.index('notes')] if 'notes' in header and header.index('notes') < len(row) else ''
        refs = re.findall(r'\[plural: ([^\]]+)\]', note)
        comment = ' '.join('[plural: %s]' % r.replace('`', '') for r in refs)
        strings.append((key, t, comment))
    return strings, plurals


def typography(t: str) -> str:
    t = re.sub(r'(?<=\d) (?=\d{3}(?!\d))', NNBSP, t)
    t = re.sub(r'(?<=\d) (?=\d{3}(?!\d))', NNBSP, t)
    units = '|'.join(UNITS)
    t = re.sub(r'(?<=[\d}]) (?=(?:%s)(?![А-Яа-яЁёA-Za-z]))' % units, NBSP, t)
    t = t.replace('≈ ', '≈' + NBSP).replace('№ ', '№' + NBSP)
    return t


def placeholders(t: str) -> tuple[str, int]:
    order: dict[str, int] = {}

    def sub(m: re.Match) -> str:
        name = m.group(1)
        if name not in order:
            order[name] = len(order) + 1
        return '\x00%d$%s' % (order[name], 'd' if name in INT_NAMES else 's')
    out = re.sub(r'\{([A-Za-z_]+)\}', sub, t)
    if re.search(r'[{}]', out):
        raise DeckError('unbalanced placeholder in %r' % t)
    # «{n} {nights}» once produced «%3$d %4$d»: a count followed directly by another count is always a
    # deck error (the word after a count is a plural word: name it {<x>_word} or {days}, never an INT name)
    if re.search(r'\x00\d+\$d\s+\x00\d+\$d', out):
        raise DeckError('two integer placeholders in a row (count + count) in %r; '
                        'the plural word needs a non-integer name such as {nights_word}' % t)
    return out, len(order)


def android_escape(t: str, literal_quotes: bool, n_args: int) -> tuple[str, bool]:
    formatted_false = False
    t = t.replace('\\', '\\\\')
    if n_args:
        t = t.replace('%', '%%')
    elif '%' in t:
        formatted_false = True
    t = t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    t = t.replace("'", "\\'").replace('"', '\\"')
    t = t.replace('\x00', '%')  # placeholder marker -> %; literal % was doubled above
    if t[:1] in ('@', '?'):
        t = '\\' + t
    if literal_quotes:
        t = '"%s"' % t
    return t, formatted_false


def render(strings, plurals) -> tuple[str, str]:
    seen: dict[str, str] = {}
    for k, _, _ in strings:
        if k in seen:
            raise DeckError('duplicate key %s' % k)
        seen[k] = 'string'
    for k, _ in plurals:
        if k in seen:
            raise DeckError('duplicate key %s' % k)
        seen[k] = 'plural'
    plural_names = {k for k, _ in plurals}
    s_out = [HEADER, '<resources>\n']
    for key, text, comment in strings:
        for ref in re.findall(r'\[plural: ([^\]]+)\]', comment):
            for name in re.split(r',\s*', ref):
                if name not in plural_names:
                    raise DeckError('%s references unknown plural %s' % (key, name))
        literal = len(text) >= 2 and text[0] == '"' and text[-1] == '"'
        body = text[1:-1] if literal else text
        body = typography(body)
        body, n = placeholders(body)
        body, fmt_false = android_escape(body, literal, n)
        if comment:
            s_out.append('    <!-- %s -->\n' % comment)
        attr = ' formatted="false"' if fmt_false else ''
        s_out.append('    <string name="%s"%s>%s</string>\n' % (key, attr, body))
    s_out.append('</resources>\n')
    p_out = [HEADER, '<resources>\n']
    for key, forms in plurals:
        p_out.append('    <plurals name="%s">\n' % key)
        for q, f in zip(QUANTITIES, forms):
            body, _ = android_escape(typography(f), False, 0)
            p_out.append('        <item quantity="%s">%s</item>\n' % (q, body))
        p_out.append('    </plurals>\n')
    p_out.append('</resources>\n')
    s_xml, p_xml = ''.join(s_out), ''.join(p_out)
    if 'U+' in s_xml or 'U+' in p_xml:
        raise DeckError('a "U+" escape leaked into the output; write the real character in the deck')
    return s_xml, p_xml


def main() -> int:
    check = '--check' in sys.argv
    try:
        strings, plurals = parse_deck(open(DECK, encoding='utf-8').read())
        s_xml, p_xml = render(strings, plurals)
    except DeckError as e:
        print('gen_strings: ERROR %s' % e)
        return 2
    print('deck keys: %d strings + %d plurals = %d' % (len(strings), len(plurals), len(strings) + len(plurals)))
    outputs = ((OUT_STRINGS, s_xml), (OUT_PLURALS, p_xml))
    if check:
        stale = False
        for path, new in outputs:
            old = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
            if old != new:
                stale = True
                rel = os.path.relpath(path, ROOT)
                sys.stdout.writelines(difflib.unified_diff(old.splitlines(True), new.splitlines(True), rel + ' (committed)', rel + ' (generated)'))
        print('gen_strings --check: %s' % ('STALE' if stale else 'up to date'))
        return 1 if stale else 0
    os.makedirs(RES, exist_ok=True)
    for path, new in outputs:
        open(path, 'w', encoding='utf-8').write(new)
        print('wrote %s' % os.path.relpath(path, ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
