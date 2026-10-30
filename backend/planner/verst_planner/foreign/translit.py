"""Cyrillic for names abroad written in a Latin alphabet (CEO 30.10, option «в»).

A place or town whose only label is Turkish, Azerbaijani or Uzbek (`nameLang` tr / az / uz) is shown in
Cyrillic by the usual Russian rendering of that language: the same name, never a translation
(«İhsangazi» → «Ихсангази», «Nərimanov parkı» → «Нариманов паркы», «Navroʻz bogʻi» → «Навруз боги»). A name
in English stays as it is: «Холи Тринити Чёрч» reads worse than the original. A description or extract with
no Cyrillic letter is dropped by `russian_or_none` (Wikidata gives «Museum in Yerevan», «Beyoğlu'nda müze»).
"""

# Latin and Cyrillic letters side by side are the point here.
# ruff: noqa: RUF001, RUF002
from __future__ import annotations

import re

LANGS = frozenset({"tr", "az", "uz"})
VOWELS = "aeıioöuüəâîû"
CYRILLIC = re.compile("[А-Яа-яЁё]")

# One letter (lower case) → Cyrillic, per language; digraphs and «y» before a vowel are handled in `_word`.
_COMMON = {
    "a": "а", "b": "б", "c": "дж", "ç": "ч", "d": "д", "e": "е", "f": "ф", "g": "г", "ğ": "г", "h": "х",
    "ı": "ы", "i": "и", "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", "ö": "ё", "p": "п",
    "r": "р", "s": "с", "ş": "ш", "t": "т", "u": "у", "ü": "ю", "v": "в", "y": "й", "z": "з", "â": "а",
    "î": "и", "û": "у", "w": "в", "x": "кс", "q": "к",
}  # fmt: skip
_TABLES = {
    "tr": _COMMON,
    "az": {**_COMMON, "ə": "а", "x": "х", "q": "г"},
    "uz": {**_COMMON, "c": "дж", "j": "дж", "x": "х", "q": "к", "ı": "и"},
}
# Initial vowels that Russian writes differently from the middle of a word (Eskişehir → Эскишехир).
_INITIAL = {"e": "э", "ö": "о", "ü": "у", "ə": "а"}
_IOTATED = {"a": "я", "e": "е", "u": "ю", "o": "йо", "ı": "йы", "i": "йи", "ü": "ю", "ö": "йо", "ə": "я"}
_UZ_DIGRAPHS = (("oʻ", "у"), ("o'", "у"), ("o‘", "у"), ("gʻ", "г"), ("g'", "г"), ("g‘", "г"),
                ("sh", "ш"), ("ch", "ч"), ("ng", "нг"), ("ts", "ц"))  # fmt: skip
_APOSTROPHES = "ʼʻ’‘'`"
# A label tagged tr / az / uz that is in fact English (Wikidata: «Tashkent City Park») stays as it is.
_ENGLISH = frozenset(
    {"the", "of", "city", "museum", "street", "square", "garden", "church", "cathedral", "monument", "house",
     "memorial", "center", "centre", "mosque", "tower", "bridge", "palace", "fortress", "castle", "lake"}
)  # fmt: skip


def _case(src: str, dst: str) -> str:
    return dst[:1].upper() + dst[1:] if src[:1].isupper() else dst


def _word(word: str, lang: str) -> str:
    table = _TABLES[lang]
    low = word.lower().replace("i̇", "i")  # «İ».lower() is «i» + a combining dot
    out: list[str] = []
    i = 0
    while i < len(low):
        ch = low[i]
        if lang == "uz":
            hit = next(((d, c) for d, c in _UZ_DIGRAPHS if low.startswith(d, i)), None)
            if hit is not None:
                out.append(hit[1])
                i += len(hit[0])
                continue
        if ch in _APOSTROPHES:
            i += 1
            continue
        nxt = low[i + 1] if i + 1 < len(low) else ""
        if ch == "y" and nxt in _IOTATED:
            prev = low[i - 1] if i > 0 else ""
            sign = "ь" if prev and prev.isalpha() and prev not in VOWELS + "y" else ""
            out.append(sign + _IOTATED[nxt])
            i += 2
            continue
        if i == 0 and ch in _INITIAL:
            out.append(_INITIAL[ch])
        elif ch in table:
            out.append(table[ch])
        else:
            out.append(ch)
        i += 1
    return _case(word, "".join(out))


def cyrillic(name: str, lang: str | None) -> str:
    """`name` in Cyrillic when its label language is tr / az / uz and it has no Cyrillic yet; else as is."""
    if lang not in LANGS or not name or CYRILLIC.search(name):
        return name
    assert lang is not None
    if _ENGLISH & {w.lower() for w in re.findall(r"[^\W\d_]+", name)}:
        return name
    out = re.sub(r"[^\W\d_]+(?:[ʼʻ’‘'`][^\W\d_]+)*", lambda m: _word(m.group(0), lang), name)
    return re.sub(r"(?<=[а-яё])[ʼʻ’‘`]", "", out, flags=re.IGNORECASE)


def russian_or_none(text: str | None) -> str | None:
    """A description or extract only when it is Russian (has a Cyrillic letter)."""
    return text if text and CYRILLIC.search(text) else None


__all__ = ["LANGS", "cyrillic", "russian_or_none"]
