"""Genitive and prepositional forms of town names with pymorphy3 (ADR-0012 §2). CI only:

    python3 tools/data/inflect.py RAW_DIR   # reads towns.json, writes forms.json {qid: {gen, prep}}

`forms(name, morph)` is pure given a morphology object with pymorphy3's `parse(word)` interface, so the
sandbox tests it with a stub. Rules: inflect every word that parses as a noun (Geox preferred) or an
adjective; keep prepositional phrases of hyphenated names («Ростов-на-Дону») and words that do not parse;
keep the capitalisation. `name_overrides.tsv` and the fixture forms win over this (build_catalogue).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

PREPOSITIONS = {"на", "в", "под", "над", "у", "при"}
# Run 2 oracle (46/48): «Сергиев Посад» → «Сергиеве Посаде» was wrong; the possessive first word of a
# two-word name («Сергиев», «Павлов») declines as a short adjective. «Пушкино» (kept unchanged, unlike
# «Иваново» → «Иванове») is an exception for name_overrides.tsv / the fixture, not a rule.
POSSESSIVE_ENDINGS = ("ов", "ев", "ёв", "ин", "ын")
POSSESSIVE = {"gent": "а", "loct": "ом"}
CASES = {"gen": "gent", "prep": "loct"}
WORD = re.compile(r"[А-Яа-яЁё]+")


def _keep_case(src: str, out: str) -> str:
    if src[:1].isupper():
        return out[:1].upper() + out[1:]
    return out


def _best(morph: Any, word: str) -> Any | None:
    parses = [p for p in morph.parse(word) if {"NOUN", "ADJF"} & set(str(p.tag).replace(",", " ").split())]
    if not parses:
        return None
    geox = [p for p in parses if "Geox" in str(p.tag)]
    return (geox or parses)[0]


def _inflect_word(morph: Any, word: str, case: str) -> str:
    p = _best(morph, word)
    if p is None:
        return word
    form = p.inflect({case})
    return _keep_case(word, form.word) if form is not None else word


def _inflect_part(morph: Any, part: str, case: str) -> str:
    return WORD.sub(lambda m: _inflect_word(morph, m.group(0), case), part)


def form(name: str, morph: Any, case: str) -> str:
    words = name.split(" ")
    out = []
    for n, word in enumerate(words):
        if n == 0 and len(words) > 1 and "-" not in word and word.lower().endswith(POSSESSIVE_ENDINGS):
            out.append(word + POSSESSIVE[case])
            continue
        pieces = word.split("-")
        keep_from = next((i for i, w in enumerate(pieces) if w.lower() in PREPOSITIONS), len(pieces))
        done = [_inflect_part(morph, w, case) if i < keep_from else w for i, w in enumerate(pieces)]
        out.append("-".join(done))
    return " ".join(out)


def forms(name: str, morph: Any) -> dict[str, str]:
    return {k: form(name, morph, case) for k, case in CASES.items()}


def main(argv: list[str]) -> int:
    import pymorphy3  # CI only (requirements of data.yml)

    raw = Path(argv[0])
    morph = pymorphy3.MorphAnalyzer(lang="ru")
    towns = json.loads((raw / "towns.json").read_text("utf-8"))
    out = {t["qid"]: forms(t["name"], morph) for t in towns}
    (raw / "forms.json").write_text(json.dumps(out, ensure_ascii=False), "utf-8")
    report = oracle(morph)
    report["pymorphy3"] = pymorphy3.__version__
    (raw / "forms_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
    print(f"forms: {len(out)} towns; fixture oracle {report['match']}/{report['total']}")
    return 0


def oracle(morph: Any) -> dict[str, Any]:
    """pymorphy3 vs the 48 hand-written fixture forms (the overrides fix the misses)."""
    root = Path(__file__).resolve().parents[2] / "fixtures" / "worlds"
    misses = []
    total = 0
    for w in ("central_russia_v1", "edge_cases_v1"):
        for t in json.loads((root / f"{w}.json").read_text("utf-8"))["towns"]:
            if not t.get("nameGenRu"):
                continue
            total += 1
            got = forms(t["nameRu"], morph)
            if (got["gen"], got["prep"]) != (t["nameGenRu"], t.get("namePrepRu")):
                misses.append(
                    {"name": t["nameRu"], "got": got, "want": [t["nameGenRu"], t.get("namePrepRu")]}
                )
    return {"total": total, "match": total - len(misses), "misses": misses}


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
