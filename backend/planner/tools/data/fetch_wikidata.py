"""Fetch Russian towns and their POIs from the Wikidata Query Service (ADR-0012 §1). Runs in CI only.

    python3 tools/data/fetch_wikidata.py classes OUT_DIR   # check the class ids (class_check.json)
    python3 tools/data/fetch_wikidata.py towns   OUT_DIR   # towns.json
    python3 tools/data/fetch_wikidata.py pois    OUT_DIR   # pois.json (needs towns.json)

The parsing helpers (`parse_point`, `towns_from_bindings`, `pois_from_bindings`, `class_check`) are pure and
tested in the sandbox on recorded responses.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from build_catalogue import CLASS_IDS
from http_util import Pacer, request

WDQS = "https://query.wikidata.org/sparql"
TOWN_CLASSES = ("Q7930989", "Q183342")  # город России; город федерального значения
COUNTRY = "Q159"

# Expected English label keywords: the class ids above were written from memory (ADR-0012 §1), so the first
# step fails the run when a label does not match, and the report shows the actual labels.
EXPECT: dict[str, tuple[str, ...]] = {
    "Q7930989": ("city", "town"),
    "Q183342": ("federal",),
    "Q159": ("russia",),
    "Q12035": ("kremlin",),
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
    "Q1501717": ("embankment", "promenade", "quay"),
    "Q174782": ("square",),
    "Q2319498": ("landmark",),
    "Q570116": ("tourist attraction", "attraction"),
}
# Russian labels to re-resolve a class whose id fails the check (run 3: Q12035 is a spider, Q1501717 an HIV
# trial): the class with this ru label that has the most instances in Russia (`resolve_query`).
RU_LABEL: dict[str, str] = {
    "Q12035": "кремль",
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
    "Q1501717": "набережная",
    "Q174782": "площадь",
    "Q2319498": "достопримечательность",
    "Q570116": "туристическая достопримечательность",
}
RADIUS_KM = ((1_000_000, 10.0), (100_000, 6.0), (20_000, 4.0), (0, 2.0))
CAPITALS = {"Москва": 15.0, "Санкт-Петербург": 15.0}
# Run 3 had 1 058 towns but no Екатеринбург, Челябинск or Владивосток (their P31 is a subclass of «город
# России», hence `wdt:P31/wdt:P279*`); the towns step now fails when one of these is missing.
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


def class_check(bindings: list[dict[str, Any]]) -> dict[str, Any]:
    labels = {qid(val(b, "c") or ""): (val(b, "label") or "") for b in bindings}
    bad = {
        q: labels.get(q, "")
        for q, keys in EXPECT.items()
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


def resolve_classes(report: dict[str, Any], query: Any) -> dict[str, str]:
    """{wrong id: resolved id} for the mismatches that have a ru label; `query(sparql) -> bindings`."""
    out = {}
    for q in sorted(report["mismatches"]):
        label = RU_LABEL.get(q)
        if label is None:
            continue
        got = pick_resolved(query(Q_RESOLVE.format(label=label)))
        if got is not None and got != q:
            out[q] = got
    return out


def towns_from_bindings(bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per town: latest population, an RU-* region, the first image; ru label required."""
    acc: dict[str, dict[str, Any]] = {}
    for b in bindings:
        q = qid(val(b, "town") or "")
        name = val(b, "townLabel") or ""
        pt = parse_point(val(b, "coord") or "")
        if not name or name == q or pt is None:
            continue
        t = acc.setdefault(
            q,
            {
                "qid": q,
                "name": name,
                "lat": pt[0],
                "lon": pt[1],
                "population": 0,
                "_pdate": "",
                "regionIso": None,
                "regionName": None,
                "image": None,
            },
        )
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
        if iso and iso.startswith("RU-") and t["regionIso"] is None:
            t["regionIso"], t["regionName"] = iso, val(b, "regionLabel")
        img = commons_file(val(b, "image"))
        if img and (t["image"] is None or img < t["image"]):
            t["image"] = img
    out = []
    for t in acc.values():
        t.pop("_pdate")
        out.append(t)
    return sorted(out, key=lambda t: t["qid"])


def pois_from_bindings(bindings: list[dict[str, Any]], town_qid: str) -> list[dict[str, Any]]:
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


def missing_towns(towns: list[dict[str, Any]]) -> list[str]:
    names = {t["name"] for t in towns}
    return [n for n in MUST_HAVE if n not in names]


def radius_for(t: dict[str, Any]) -> float:
    if t["name"] in CAPITALS:
        return CAPITALS[t["name"]]
    return next(r for threshold, r in RADIUS_KM if (t.get("population") or 0) >= threshold)


# ------------------------------------------------------------------------------------------- queries

Q_CLASSES = """SELECT ?c ?label WHERE {{ VALUES ?c {{ {ids} }} ?c rdfs:label ?label . FILTER(LANG(?label) = "en") }}"""

Q_RESOLVE = """SELECT ?c (COUNT(DISTINCT ?i) AS ?n) WHERE {{
  ?c rdfs:label "{label}"@ru .
  ?i wdt:P31 ?c ; wdt:P17 wd:Q159 .
}} GROUP BY ?c ORDER BY DESC(?n) LIMIT 5"""

Q_TOWNS = """SELECT ?town ?townLabel ?coord ?pop ?popDate ?iso ?regionLabel ?image WHERE {{
  VALUES ?cls {{ {classes} }}
  ?town wdt:P31/wdt:P279* ?cls .
  ?town wdt:P17 wd:{country}; wdt:P625 ?coord .
  FILTER NOT EXISTS {{ ?town wdt:P576 [] }}
  OPTIONAL {{ ?town p:P1082 ?ps . ?ps ps:P1082 ?pop . OPTIONAL {{ ?ps pq:P585 ?popDate }} }}
  OPTIONAL {{ ?town wdt:P131* ?region . ?region wdt:P300 ?iso . FILTER(STRSTARTS(?iso, "RU-")) }}
  OPTIONAL {{ ?town wdt:P18 ?image }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "ru" . }}
}}"""

Q_POIS = """SELECT ?item ?itemLabel ?itemDescription ?coord ?root ?sitelinks ?image ?heritage WHERE {{
  SERVICE wikibase:around {{ ?item wdt:P625 ?coord .
    bd:serviceParam wikibase:center "Point({lon} {lat})"^^geo:wktLiteral; wikibase:radius "{radius}" . }}
  VALUES ?root {{ {roots} }}
  ?item wdt:P31/wdt:P279* ?root .
  ?item wikibase:sitelinks ?sitelinks .
  OPTIONAL {{ ?item wdt:P18 ?image }}
  OPTIONAL {{ ?item wdt:P1435 ?heritage }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "ru" . }}
}}"""


def sparql(query: str, pacer: Any) -> list[dict[str, Any]]:
    doc = request(
        WDQS, pacer, data={"query": query, "format": "json"}, accept="application/sparql-results+json"
    )
    return list(doc["results"]["bindings"])


def main(argv: list[str]) -> int:
    cmd, out = argv[0], Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    pacer = Pacer(1.0)
    if cmd == "classes":
        ids = " ".join(f"wd:{q}" for q in EXPECT)
        report = class_check(sparql(Q_CLASSES.format(ids=ids), pacer))
        resolved = resolve_classes(report, lambda q: sparql(q, pacer)) if not report["ok"] else {}
        if resolved:
            labels = sparql(Q_CLASSES.format(ids=" ".join(f"wd:{q}" for q in resolved.values())), pacer)
            report["resolvedLabels"] = class_check(labels)["labels"]
        report["resolved"] = resolved
        report["unresolved"] = sorted(set(report["mismatches"]) - set(resolved))
        (out / "class_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
        (out / "classes_resolved.json").write_text(json.dumps(resolved, indent=1), "utf-8")
        print(json.dumps({"mismatches": report["mismatches"], "resolved": resolved}, ensure_ascii=False))
        # Green when every wrong id was re-resolved (the POIs use the resolved ids; copy them into CLASS_KIND
        # and EXPECT afterwards); the run fails at the end (data.yml) only for unresolved ids.
        return 0 if not report["unresolved"] else 2
    if cmd == "towns":
        q = Q_TOWNS.format(classes=" ".join(f"wd:{c}" for c in TOWN_CLASSES), country=COUNTRY)
        towns = towns_from_bindings(sparql(q, pacer))
        (out / "towns.json").write_text(json.dumps(towns, ensure_ascii=False), "utf-8")
        missing = missing_towns(towns)
        print(f"towns: {len(towns)}; missing must-have: {missing}")
        return 0 if not missing else 4
    if cmd == "pois":
        towns = json.loads((out / "towns.json").read_text("utf-8"))
        resolved_path = out / "classes_resolved.json"
        resolved = json.loads(resolved_path.read_text("utf-8")) if resolved_path.exists() else {}
        back = {new: old for old, new in resolved.items()}
        roots = " ".join(f"wd:{resolved.get(q, q)}" for q in CLASS_IDS)
        pois: list[dict[str, Any]] = []
        failed = []
        for i, t in enumerate(sorted(towns, key=lambda t: -(t.get("population") or 0))):
            q = Q_POIS.format(lat=t["lat"], lon=t["lon"], radius=radius_for(t), roots=roots)
            try:
                for p in pois_from_bindings(sparql(q, pacer), t["qid"]):
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
