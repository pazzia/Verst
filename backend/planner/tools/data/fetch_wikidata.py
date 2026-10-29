"""Fetch the towns and their POIs from the Wikidata Query Service (ADR-0012 §1). Runs in CI only.

    python3 tools/data/fetch_wikidata.py classes OUT_DIR [--country CC]  # check the class ids (class_check.json)
    python3 tools/data/fetch_wikidata.py country OUT_DIR --country CC    # country_check.json (abroad only)
    python3 tools/data/fetch_wikidata.py towns   OUT_DIR [--country CC]  # towns.json
    python3 tools/data/fetch_wikidata.py pois    OUT_DIR [--country CC]  # pois.json (needs towns.json)

`--country` (default RU, `countries.py`) picks the P17 values, the ISO 3166-2 prefix of the regions and the
label languages; for RU the queries are exactly the Russian ones of runs 1-7 (`tests/unit/test_abroad_data.py`).
Abroad, a name comes in Russian when Wikidata has one, else in the next language of `Country.label_langs`
(the local language when its script is Latin or Cyrillic, then English; never a machine translation), and the
row records the language (`nameLang`). The parsing helpers (`parse_point`, `towns_from_bindings`,
`pois_from_bindings`, `class_check`, `country_report`) are pure and tested in the sandbox on recorded responses.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from build_catalogue import ABROAD_CLASS_KIND, CLASS_IDS
from countries import RU, Country, get, keeps
from http_util import Pacer, request

WDQS = "https://query.wikidata.org/sparql"
TOWN_CLASSES = RU.town_classes  # город России; город федерального значения
COUNTRY = RU.qids[0]

# Expected English label keywords: the class ids above were written from memory (ADR-0012 §1), so the first
# step fails the run when a label does not match, and the report shows the actual labels.
EXPECT: dict[str, tuple[str, ...]] = {
    "Q7930989": ("city", "town"),
    "Q183342": ("federal",),
    "Q159": ("russia",),
    "Q263274": ("kremlin",),
    "Q57821": ("fortification", "fortress"),
    "Q23413": ("castle",),
    "Q44613": ("monastery",),
    "Q33506": ("museum",),
    "Q16970": ("church",),
    "Q2977": ("cathedral",),
    "Q4989906": ("monument",),
    "Q5003624": ("memorial",),
    "Q179700": ("statue",),
    "Q22698": ("park",),
    "Q1107656": ("garden",),
    "Q6017969": ("viewpoint", "scenic", "lookout"),
    "Q1851368": ("waterfront", "embankment", "promenade", "quay"),
    "Q174782": ("square",),
    "Q2319498": ("landmark",),
    "Q570116": ("tourist attraction", "attraction"),
}
# Abroad only (CEO 29.10): the sights of Central Asia, the Caucasus and Turkey that no Russian class covers. Ids
# written from memory like the ones above, so the classes step checks them too (and re-resolves by ru label).
EXPECT_ABROAD: dict[str, tuple[str, ...]] = {
    "Q32815": ("mosque",),
    "Q162875": ("mausoleum",),
    "Q132834": ("madrasa", "madrassa", "madrasah"),
    "Q839954": ("archaeological site",),
}
# Russian labels to re-resolve a class whose id fails the check (run 3: Q12035 is a spider, Q1501717 an HIV
# trial): the class with this ru label that has the most instances in Russia (`resolve_query`).
RU_LABEL: dict[str, str] = {
    "Q263274": "кремль",
    "Q57821": "фортификационное сооружение",
    "Q23413": "замок",
    "Q44613": "монастырь",
    "Q33506": "музей",
    "Q16970": "церковь",
    "Q2977": "собор",
    "Q4989906": "памятник",
    "Q5003624": "мемориал",
    "Q179700": "статуя",
    "Q22698": "парк",
    "Q1107656": "сад",
    "Q6017969": "смотровая площадка",
    "Q1851368": "набережная",
    "Q174782": "площадь",
    "Q2319498": "достопримечательность",
    "Q570116": "туристическая достопримечательность",
    "Q32815": "мечеть",
    "Q162875": "мавзолей",
    "Q132834": "медресе",
    "Q839954": "археологический памятник",
}
RADIUS_KM = ((1_000_000, 10.0), (100_000, 6.0), (20_000, 4.0), (0, 2.0))
CAPITALS = {"Москва": 15.0, "Санкт-Петербург": 15.0}
# Run 3 had 1 058 towns but no Екатеринбург, Челябинск or Владивосток (their P31 is a subclass of «город
# России», hence the subclasses in Q_SUBCLASSES); the towns step now fails when one of these is missing.
MUST_HAVE = (
    "Москва",
    "Санкт-Петербург",
    "Новосибирск",
    "Екатеринбург",
    "Казань",
    "Нижний Новгород",
    "Челябинск",
    "Красноярск",
    "Самара",
    "Уфа",
    "Ростов-на-Дону",
    "Омск",
    "Краснодар",
    "Воронеж",
    "Пермь",
    "Волгоград",
    "Владивосток",
    "Ярославль",
    "Калининград",
    "Иркутск",
    "Хабаровск",
    "Мурманск",
    "Суздаль",
    "Сочи",
)
POINT = re.compile(r"Point\(([-0-9.eE]+) ([-0-9.eE]+)\)")


def parse_point(wkt: str) -> tuple[float, float] | None:
    m = POINT.match(wkt.strip())
    if not m:
        return None
    lon, lat = float(m.group(1)), float(m.group(2))
    return lat, lon


def qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def val(b: dict[str, Any], key: str) -> str | None:
    v = b.get(key)
    return None if v is None else str(v["value"])


def commons_file(uri: str | None) -> str | None:
    """`http://commons.wikimedia.org/wiki/Special:FilePath/Foo%20bar.jpg` → `Foo bar.jpg`."""
    if not uri:
        return None
    from urllib.parse import unquote

    return unquote(uri.rsplit("/", 1)[-1]).replace("_", " ")


def lang(b: dict[str, Any], key: str) -> str | None:
    """The language tag of a label-service literal (`xml:lang`), or None (no label: the bare Q-id)."""
    v = b.get(key)
    return None if v is None else v.get("xml:lang")


def expect_for(country: Country) -> dict[str, tuple[str, ...]]:
    """The class ids (and abroad also the extra classes and the country ids) whose labels the classes step checks."""
    if not country.abroad:
        return EXPECT
    out = {k: v for k, v in EXPECT.items() if k != "Q159"}
    out.update(EXPECT_ABROAD)
    out[country.qids[0]] = country.expect
    return out


def class_check(bindings: list[dict[str, Any]], expect: dict[str, tuple[str, ...]] | None = None) -> dict[str, Any]:
    labels = {qid(val(b, "c") or ""): (val(b, "label") or "") for b in bindings}
    bad = {
        q: labels.get(q, "")
        for q, keys in (EXPECT if expect is None else expect).items()
        if not any(k in labels.get(q, "").lower() for k in keys)
    }
    return {"labels": labels, "mismatches": bad, "ok": not bad}


def pick_resolved(bindings: list[dict[str, Any]]) -> str | None:
    """The class with the most Russian instances among the label matches (ties: the smaller id)."""
    best: tuple[int, str] | None = None
    for b in bindings:
        q = qid(val(b, "c") or "")
        n = int(val(b, "n") or 0)
        if q and n > 0 and (best is None or (-n, q) < (-best[0], best[1])):
            best = (n, q)
    return best[1] if best else None


def resolve_classes(report: dict[str, Any], query: Any, country: Country = RU) -> dict[str, str]:
    """{wrong id: resolved id} for the mismatches that have a ru label; `query(sparql) -> bindings`."""
    out = {}
    for q in sorted(report["mismatches"]):
        label = RU_LABEL.get(q)
        if label is None:
            continue
        got = pick_resolved(query(Q_RESOLVE.format(label=label, country=country.qids[0])))
        if got is not None and got != q:
            out[q] = got
    return out


def towns_from_bindings(bindings: list[dict[str, Any]], country: Country = RU) -> list[dict[str, Any]]:
    """One row per town: latest population, a region of the country's ISO 3166-2 prefix, the first image; a
    label required. Abroad the row also keeps the label language (`nameLang`) and its P17 values (`countries`),
    the region is the smallest code seen (deterministic when a town reaches two coded regions), and the towns of
    a carved territory (Abkhazia) go to their own catalogue (`countries.keeps`)."""
    acc: dict[str, dict[str, Any]] = {}
    for b in bindings:
        q = qid(val(b, "town") or "")
        name = val(b, "townLabel") or ""
        pt = parse_point(val(b, "coord") or "")
        if not name or name == q or pt is None:
            continue
        row: dict[str, Any] = {
            "qid": q,
            "name": name,
            "lat": pt[0],
            "lon": pt[1],
            "population": 0,
            "_pdate": "",
            "regionIso": None,
            "regionName": None,
            "image": None,
        }
        if country.abroad:
            row.update(nameLang=lang(b, "townLabel"), countries=[])
        t = acc.setdefault(q, row)
        if country.abroad:
            c = qid(val(b, "country") or "") or country.qids[0]
            if c not in t["countries"]:
                t["countries"] = sorted([*t["countries"], c])
        pop = val(b, "pop")
        pdate = val(b, "popDate") or ""
        if pop is not None:
            try:
                n = int(float(pop))
            except ValueError:
                n = 0
            if pdate > t["_pdate"] or (pdate == t["_pdate"] and n > t["population"]):
                t["population"], t["_pdate"] = n, pdate
        iso = val(b, "iso")
        if (
            iso
            and iso.startswith(country.iso_prefix)
            and (t["regionIso"] is None or (country.abroad and iso < t["regionIso"]))
        ):
            t["regionIso"], t["regionName"] = iso, val(b, "regionLabel")
        img = commons_file(val(b, "image"))
        if img and (t["image"] is None or img < t["image"]):
            t["image"] = img
    out = []
    for t in acc.values():
        t.pop("_pdate")
        if country.abroad:
            if not keeps(country, t["regionIso"], t["countries"]):
                continue
            if country.carve is not None and country.inside:
                t["regionIso"] = country.carve[0]  # P17 Abkhazia without a GE-AB region: still Абхазия
            if t["regionIso"] in country.region_names:
                t["regionName"] = country.region_names[t["regionIso"]]
        out.append(t)
    return sorted(out, key=lambda t: t["qid"])


def pois_from_bindings(
    bindings: list[dict[str, Any]], town_qid: str, country: Country = RU
) -> list[dict[str, Any]]:
    acc: dict[str, dict[str, Any]] = {}
    for b in bindings:
        q = qid(val(b, "item") or "")
        name = val(b, "itemLabel") or ""
        pt = parse_point(val(b, "coord") or "")
        if not name or name == q or pt is None:
            continue
        p = acc.setdefault(
            q,
            {
                "qid": q,
                "name": name,
                "desc": val(b, "itemDescription"),
                "lat": pt[0],
                "lon": pt[1],
                "roots": [],
                "sitelinks": int(val(b, "sitelinks") or 0),
                "heritage": False,
                "image": None,
                "townQid": town_qid,
                **({"nameLang": lang(b, "itemLabel")} if country.abroad else {}),
            },
        )
        root = qid(val(b, "root") or "")
        if root and root not in p["roots"]:
            p["roots"].append(root)
        if val(b, "heritage"):
            p["heritage"] = True
        img = commons_file(val(b, "image"))
        if img and (p["image"] is None or img < p["image"]):
            p["image"] = img
    for p in acc.values():
        p["roots"].sort()
    return sorted(acc.values(), key=lambda p: p["qid"])


def missing_towns(towns: list[dict[str, Any]], must_have: tuple[str, ...] = MUST_HAVE) -> list[str]:
    """Must-have names (Russia) or Wikidata ids (abroad: the capitals of `country_check.json`) not in towns."""
    have = {t["name"] for t in towns} | {t["qid"] for t in towns}
    return [n for n in must_have if n not in have]


def radius_for(t: dict[str, Any]) -> float:
    if t["name"] in CAPITALS:
        return CAPITALS[t["name"]]
    return next(r for threshold, r in RADIUS_KM if (t.get("population") or 0) >= threshold)


# ------------------------------------------------------------------------------------------- queries

Q_CLASSES = """SELECT ?c ?label WHERE {{ VALUES ?c {{ {ids} }} ?c rdfs:label ?label . FILTER(LANG(?label) = "en") }}"""

Q_RESOLVE = """SELECT ?c (COUNT(DISTINCT ?i) AS ?n) WHERE {{
  ?c rdfs:label "{label}"@ru .
  ?i wdt:P31 ?c ; wdt:P17 wd:{country} .
}} GROUP BY ?c ORDER BY DESC(?n) LIMIT 5"""

# Run 6: `wdt:P31/wdt:P279*` inside the towns query timed out (504); the subclasses come first, then VALUES.
Q_SUBCLASSES = """SELECT DISTINCT ?c WHERE {{ VALUES ?root {{ {roots} }} ?c wdt:P279* ?root . }}"""

Q_TOWNS = """SELECT ?town ?townLabel ?coord ?pop ?popDate ?iso ?regionLabel ?image{country_var} WHERE {{
  VALUES ?cls {{ {classes} }}{country_values}
  ?town wdt:P31 ?cls; wdt:P17 {country}; wdt:P625 ?coord .
  FILTER NOT EXISTS {{ ?town wdt:P576 [] }}
  OPTIONAL {{ ?town p:P1082 ?ps . ?ps ps:P1082 ?pop . OPTIONAL {{ ?ps pq:P585 ?popDate }} }}
  OPTIONAL {{ ?town wdt:P131* ?region . ?region wdt:P300 ?iso . FILTER(STRSTARTS(?iso, "{prefix}")) }}
  OPTIONAL {{ ?town wdt:P18 ?image }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{langs}" . }}
}}"""

Q_POIS = """SELECT ?item ?itemLabel ?itemDescription ?coord ?root ?sitelinks ?image ?heritage WHERE {{
  SERVICE wikibase:around {{ ?item wdt:P625 ?coord .
    bd:serviceParam wikibase:center "Point({lon} {lat})"^^geo:wktLiteral; wikibase:radius "{radius}" . }}
  VALUES ?root {{ {roots} }}
  ?item wdt:P31/wdt:P279* ?root .
  ?item wikibase:sitelinks ?sitelinks .
  OPTIONAL {{ ?item wdt:P18 ?image }}
  OPTIONAL {{ ?item wdt:P1435 ?heritage }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{langs}" . }}
}}"""

# Abroad: the country's English label, capital, currency (ISO 4217 code) and time zones, and every item with an
# ISO 3166-2 code of the country's prefix with its time zone (P421) — the build checks region_tz_abroad.tsv
# against them (`tzCheck` in catalogue_meta).
Q_COUNTRY = """SELECT ?c ?cLabel ?capital ?curCode ?tzLabel WHERE {{
  VALUES ?c {{ {ids} }}
  OPTIONAL {{ ?c wdt:P36 ?capital }}
  OPTIONAL {{ ?c wdt:P38 ?cur . ?cur wdt:P498 ?curCode }}
  OPTIONAL {{ ?c wdt:P421 ?tz }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}"""

Q_REGIONS = """SELECT ?r ?iso ?rLabel ?tzLabel WHERE {{
  ?r wdt:P300 ?iso . FILTER(STRSTARTS(?iso, "{prefix}"))
  OPTIONAL {{ ?r wdt:P421 ?tz }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{langs}" . }}
}}"""


def towns_query(country: Country, classes: list[str]) -> str:
    """Q_TOWNS for a country (Russia: one P17 value, the query of runs 1-7; several: a VALUES ?country)."""
    multi = len(country.qids) > 1
    return Q_TOWNS.format(
        classes=" ".join(f"wd:{c}" for c in classes if c),
        country="?country" if multi else f"wd:{country.qids[0]}",
        country_var=" ?country" if multi else "",
        country_values=(
            "\n  VALUES ?country {{ {} }}".format(" ".join(f"wd:{q}" for q in country.qids)) if multi else ""
        ),
        prefix=country.iso_prefix,
        langs=country.label_langs,
    )


def country_report(country: Country, head: list[dict[str, Any]], regions: list[dict[str, Any]]) -> dict[str, Any]:
    """`country_check.json`: the label check of the country ids, the capitals (must-have towns), the currency
    codes vs `Country.currency`, the time zones, and the regions {ISO 3166-2 code: {name, tz: [labels]}}."""
    labels: dict[str, str] = {}
    capitals: set[str] = set()
    currencies: set[str] = set()
    tz: set[str] = set()
    for b in head:
        c = qid(val(b, "c") or "")
        labels[c] = val(b, "cLabel") or ""
        if c == country.qids[0] and val(b, "capital"):
            capitals.add(qid(val(b, "capital") or ""))
        if c == country.qids[0] and val(b, "curCode"):
            currencies.add(val(b, "curCode") or "")
        if c == country.qids[0] and val(b, "tzLabel"):
            tz.add(val(b, "tzLabel") or "")
    reg: dict[str, dict[str, Any]] = {}
    for b in regions:
        iso = val(b, "iso") or ""
        r = reg.setdefault(iso, {"qid": qid(val(b, "r") or ""), "name": val(b, "rLabel"), "tz": []})
        t = val(b, "tzLabel")
        if t and t not in r["tz"]:
            r["tz"] = sorted([*r["tz"], t])
    label_ok = any(k in labels.get(country.qids[0], "").lower() for k in country.expect)
    currency_ok = not currencies or country.currency in currencies
    return {
        "country": country.code,
        "labels": labels,
        "labelOk": label_ok,
        "capitals": sorted(capitals),
        "currencies": sorted(currencies),
        "currency": country.currency,
        "currencyOk": currency_ok,
        "tz": sorted(tz),
        "regions": dict(sorted(reg.items())),
        "ok": label_ok,  # a wrong country id fails the run; a currency mismatch is only reported
    }


def sparql(query: str, pacer: Any) -> list[dict[str, Any]]:
    doc = request(
        WDQS, pacer, data={"query": query, "format": "json"}, accept="application/sparql-results+json"
    )
    return list(doc["results"]["bindings"])


def parse_args(argv: list[str]) -> tuple[str, Path, Country]:
    """`CMD OUT_DIR [--country CC]` (the country flag anywhere after the command)."""
    args = list(argv)
    code = None
    if "--country" in args:
        i = args.index("--country")
        code = args[i + 1]
        del args[i : i + 2]
    return args[0], Path(args[1]), get(code)


def main(argv: list[str]) -> int:
    cmd, out, country = parse_args(argv)
    out.mkdir(parents=True, exist_ok=True)
    pacer = Pacer(1.0)
    if cmd == "classes":
        expect = expect_for(country)
        ids = " ".join(f"wd:{q}" for q in expect)
        report = class_check(sparql(Q_CLASSES.format(ids=ids), pacer), expect)
        resolved = resolve_classes(report, lambda q: sparql(q, pacer), country) if not report["ok"] else {}
        if resolved:
            labels = sparql(Q_CLASSES.format(ids=" ".join(f"wd:{q}" for q in resolved.values())), pacer)
            report["resolvedLabels"] = class_check(labels, {})["labels"]
        report["resolved"] = resolved
        report["unresolved"] = sorted(set(report["mismatches"]) - set(resolved))
        (out / "class_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
        (out / "classes_resolved.json").write_text(json.dumps(resolved, indent=1), "utf-8")
        print(json.dumps({"mismatches": report["mismatches"], "resolved": resolved}, ensure_ascii=False))
        # Green when every wrong id was re-resolved (the POIs use the resolved ids; copy them into CLASS_KIND
        # and EXPECT afterwards); the run fails at the end (data.yml) only for unresolved ids.
        return 0 if not report["unresolved"] else 2
    if cmd == "country":
        head = sparql(Q_COUNTRY.format(ids=" ".join(f"wd:{q}" for q in country.qids)), pacer)
        regions = sparql(Q_REGIONS.format(prefix=country.iso_prefix, langs=country.label_langs), pacer)
        report = country_report(country, head, regions)
        (out / "country_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
        print(json.dumps({k: report[k] for k in ("labels", "capitals", "currencies", "tz", "ok")}, ensure_ascii=False))
        return 0 if report["ok"] else 2
    if cmd == "towns":
        roots = country.town_classes
        subs = sparql(Q_SUBCLASSES.format(roots=" ".join(f"wd:{c}" for c in roots)), pacer)
        classes = sorted({qid(val(b, "c") or "") for b in subs} | set(roots))
        print(f"town classes: {len(classes)}", flush=True)
        towns = towns_from_bindings(sparql(towns_query(country, classes), pacer), country)
        (out / "towns.json").write_text(json.dumps(towns, ensure_ascii=False), "utf-8")
        must_have = MUST_HAVE
        if country.abroad:  # the capital(s) Wikidata names (P36), when the country step ran
            check = out / "country_check.json"
            must_have = tuple(json.loads(check.read_text("utf-8"))["capitals"]) if check.exists() else ()
        missing = missing_towns(towns, must_have)
        print(f"towns: {len(towns)}; missing must-have: {missing}")
        return 0 if not missing else 4
    if cmd == "pois":
        towns = json.loads((out / "towns.json").read_text("utf-8"))
        resolved_path = out / "classes_resolved.json"
        resolved = json.loads(resolved_path.read_text("utf-8")) if resolved_path.exists() else {}
        back = {new: old for old, new in resolved.items()}
        class_ids = CLASS_IDS + (tuple(q for q, _k in ABROAD_CLASS_KIND) if country.abroad else ())
        roots = " ".join(f"wd:{resolved.get(q, q)}" for q in class_ids)
        pois: list[dict[str, Any]] = []
        failed = []
        for i, t in enumerate(sorted(towns, key=lambda t: -(t.get("population") or 0))):
            q = Q_POIS.format(
                lat=t["lat"], lon=t["lon"], radius=radius_for(t), roots=roots, langs=country.label_langs
            )
            try:
                for p in pois_from_bindings(sparql(q, pacer), t["qid"], country):
                    p["roots"] = sorted({back.get(r, r) for r in p["roots"]})  # canonical CLASS_KIND ids
                    pois.append(p)
            except Exception as e:  # one town must not sink the run; reported in sources.json
                failed.append({"qid": t["qid"], "name": t["name"], "error": repr(e)[:200]})
            if i % 50 == 0:
                print(f"pois: {i}/{len(towns)} towns, {len(pois)} rows, {len(failed)} failed", flush=True)
        (out / "pois.json").write_text(json.dumps(pois, ensure_ascii=False), "utf-8")
        (out / "pois_failed.json").write_text(json.dumps(failed, ensure_ascii=False, indent=1), "utf-8")
        print(f"pois: {len(pois)} rows, {len(failed)} towns failed")
        return 0 if len(failed) <= len(towns) // 20 else 3
    raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
