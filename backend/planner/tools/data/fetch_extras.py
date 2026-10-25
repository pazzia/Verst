"""Sprint 4 extra sources for the catalogue (ADR-0015 §2–§4). CI only (`.github/workflows/data-extras.yml`):

    python3 tools/data/fetch_extras.py classes   RAW        # class_tree.json: kind/exclude roots → subclasses
    python3 tools/data/fetch_extras.py wikidata  RAW        # wd_extra.json: P31, P1435 labels, ru wiki/voyage titles
    python3 tools/data/fetch_extras.py wikipedia RAW        # wiki.json: ru intro extract + page image per POI
    python3 tools/data/fetch_extras.py voyage    RAW DUMP   # voyage.json: Q-ids named in ru Wikivoyage listings
    python3 tools/data/fetch_extras.py osm       RAW SEQ    # osm_pois.json, parking.json from an osmium export
    python3 tools/data/fetch_extras.py geosearch RAW        # geosearch.json: Commons files near POIs without a photo

Every step reads the run-7 raw files (`towns.json`, `pois.json`) and adds one file. The parsing helpers are pure
and tested in the sandbox (`tests/unit/test_data_extras.py`).
"""

from __future__ import annotations

import bz2
import json
import re
import sys
import urllib.parse
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fetch_wikidata import pick_resolved, qid, sparql, val
from http_util import Pacer, request

WIKI_API = "https://ru.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Roots of the Sprint 4 kinds and of the hard excludes (ADR-0015 §2). The ids are written from memory, so —
# like ADR-0012's classes — the `classes` step checks the English labels and re-resolves a wrong id by its ru
# label (the class with the most instances in Russia).
ROOTS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    # id: (group, ru label, expected English keywords)
    "Q3914": ("exclude", "школа", ("school",)),
    "Q126807": ("exclude", "детский сад", ("kindergarten",)),
    "Q3918": ("exclude", "университет", ("university",)),
    "Q16917": ("exclude", "больница", ("hospital",)),
    "Q483110": ("exclude", "стадион", ("stadium",)),
    "Q1076486": ("exclude", "спортивное сооружение", ("sports venue", "sport")),
    "Q1021645": ("exclude", "офисное здание", ("office building",)),
    "Q16831714": ("exclude", "правительственное здание", ("government building",)),
    "Q40357": ("exclude", "тюрьма", ("prison",)),
    "Q83405": ("exclude", "фабрика", ("factory",)),
    "Q55488": ("exclude", "железнодорожная станция", ("railway station",)),
    "Q39614": ("exclude", "кладбище", ("cemetery",)),
    "Q11755880": ("exclude", "жилое здание", ("residential building",)),
    "Q3947": ("exclude", "дом", ("house",)),
    "Q486972": ("exclude", "населённый пункт", ("human settlement", "settlement")),
    "Q24398318": ("religious", "культовое сооружение", ("religious building",)),
    "Q16970": ("religious", "церковь", ("church building", "church")),
    "Q108325": ("religious", "часовня", ("chapel",)),
    "Q32815": ("religious", "мечеть", ("mosque",)),
    "Q24354": ("theatre", "театр", ("theatre", "theater")),
    "Q43501": ("zoo", "зоопарк", ("zoo",)),
    "Q179049": ("nature", "заповедник", ("nature reserve",)),
    "Q34038": ("nature", "водопад", ("waterfall",)),
    "Q23397": ("nature", "озеро", ("lake",)),
    "Q148319": ("interactive", "планетарий", ("planetarium",)),
    "Q588140": ("interactive", "научный музей", ("science museum",)),
    "Q194195": ("interactive", "парк развлечений", ("amusement park",)),
}
BATCH = 200


def batches(items: list[str], n: int) -> Iterator[list[str]]:
    for i in range(0, len(items), n):
        yield items[i : i + n]


# ------------------------------------------------------------------------------------------------- classes


Q_LABELS = """SELECT ?c ?label WHERE {{ VALUES ?c {{ {ids} }} ?c rdfs:label ?label . FILTER(LANG(?label) = "en") }}"""
Q_RESOLVE = """SELECT ?c (COUNT(DISTINCT ?i) AS ?n) WHERE {{
  ?c rdfs:label "{label}"@ru . ?i wdt:P31 ?c ; wdt:P17 wd:Q159 . }} GROUP BY ?c ORDER BY DESC(?n) LIMIT 5"""
Q_SUB = """SELECT DISTINCT ?c WHERE {{ ?c wdt:P279* wd:{root} . }}"""


def check_roots(bindings: list[dict[str, Any]]) -> dict[str, Any]:
    expect = {q: kw for q, (_g, _l, kw) in ROOTS.items()}
    labels = {qid(val(b, "c") or ""): (val(b, "label") or "") for b in bindings}
    bad = {
        q: labels.get(q, "")
        for q, kw in expect.items()
        if not any(k in labels.get(q, "").lower() for k in kw)
    }
    return {"labels": labels, "mismatches": bad, "ok": not bad}


def tree_doc(resolved: dict[str, str], subclasses: dict[str, list[str]]) -> dict[str, Any]:
    """{group: sorted class ids} over the (resolved) roots and all their subclasses."""
    groups: dict[str, set[str]] = {}
    for root, (group, _l, _k) in ROOTS.items():
        r = resolved.get(root, root)
        groups.setdefault(group, set()).update([r, *subclasses.get(r, [])])
    return {"resolved": resolved, "groups": {g: sorted(v) for g, v in sorted(groups.items())}}


def cmd_classes(raw: Path) -> int:
    pacer = Pacer(1.0)
    report = check_roots(sparql(Q_LABELS.format(ids=" ".join(f"wd:{q}" for q in ROOTS)), pacer))
    resolved: dict[str, str] = {}
    for q in sorted(report["mismatches"]):
        got = pick_resolved(sparql(Q_RESOLVE.format(label=ROOTS[q][1]), pacer))
        if got and got != q:
            resolved[q] = got
    subs: dict[str, list[str]] = {}
    for root in ROOTS:
        r = resolved.get(root, root)
        try:
            subs[r] = sorted({qid(val(b, "c") or "") for b in sparql(Q_SUB.format(root=r), pacer)} - {""})
        except Exception as e:  # a huge closure may time out: the root alone still counts
            print(f"classes: subclasses of {r} failed: {e!r}"[:200], flush=True)
            subs[r] = []
    doc = tree_doc(resolved, subs)
    doc["check"] = report
    (raw / "class_tree.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), "utf-8")
    print(
        f"classes: {sum(len(v) for v in doc['groups'].values())} ids; resolved {resolved}; "
        f"unresolved {sorted(set(report['mismatches']) - set(resolved))}"
    )
    return 0


# ------------------------------------------------------------------------------------------------ wikidata

Q_EXTRA = """SELECT ?item ?p31 ?hLabel ?ruTitle ?voyTitle WHERE {{
  VALUES ?item {{ {ids} }}
  OPTIONAL {{ ?item wdt:P31 ?p31 }}
  OPTIONAL {{ ?item wdt:P1435 ?h . ?h rdfs:label ?hLabel . FILTER(LANG(?hLabel) = "ru") }}
  OPTIONAL {{ ?w schema:about ?item ; schema:isPartOf <https://ru.wikipedia.org/> ; schema:name ?ruTitle }}
  OPTIONAL {{ ?v schema:about ?item ; schema:isPartOf <https://ru.wikivoyage.org/> ; schema:name ?voyTitle }}
}}"""


def extra_from_bindings(bindings: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for b in bindings:
        q = qid(val(b, "item") or "")
        if not q:
            continue
        rec = out.setdefault(q, {"p31": [], "heritage": [], "ruwiki": None, "ruvoyage": None})
        p = qid(val(b, "p31") or "")
        if p and p not in rec["p31"]:
            rec["p31"].append(p)
        h = val(b, "hLabel")
        if h and h not in rec["heritage"]:
            rec["heritage"].append(h)
        rec["ruwiki"] = rec["ruwiki"] or val(b, "ruTitle")
        rec["ruvoyage"] = rec["ruvoyage"] or val(b, "voyTitle")
    for rec in out.values():
        rec["p31"].sort()
        rec["heritage"].sort()
    return out


def cmd_wikidata(raw: Path) -> int:
    pois = json.loads((raw / "pois.json").read_text("utf-8"))
    ids = sorted({p["qid"] for p in pois})
    pacer = Pacer(1.0)
    out: dict[str, dict[str, Any]] = {}
    for i, chunk in enumerate(batches(ids, BATCH)):
        out.update(extra_from_bindings(sparql(Q_EXTRA.format(ids=" ".join(f"wd:{q}" for q in chunk)), pacer)))
        if i % 20 == 0:
            print(f"wikidata: {i * BATCH}/{len(ids)}", flush=True)
    (raw / "wd_extra.json").write_text(json.dumps(out, ensure_ascii=False), "utf-8")
    print(f"wikidata: {len(out)} items, {sum(1 for r in out.values() if r['ruwiki'])} with ru Wikipedia")
    return 0


# ----------------------------------------------------------------------------------------------- wikipedia

WIKI_BATCH = 20  # the extracts module returns intro extracts for at most 20 pages per request


def wiki_pages(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """{title: {extract, image}} from an action=query response (formatversion=2), following normalisation."""
    q = doc.get("query", {})
    back = {n["to"]: n["from"] for n in q.get("normalized", [])}
    back.update({r["to"]: back.get(r["from"], r["from"]) for r in q.get("redirects", [])})
    out = {}
    for p in q.get("pages", []):
        if p.get("missing") or "title" not in p:
            continue
        title = back.get(p["title"], p["title"])
        out[title] = {"extract": (p.get("extract") or "").strip() or None, "image": p.get("pageimage")}
    return out


def cmd_wikipedia(raw: Path) -> int:
    extra = json.loads((raw / "wd_extra.json").read_text("utf-8"))
    by_title = {r["ruwiki"]: q for q, r in extra.items() if r.get("ruwiki")}
    titles = sorted(by_title)
    pacer = Pacer(0.5)
    out: dict[str, dict[str, Any]] = {}
    for i, chunk in enumerate(batches(titles, WIKI_BATCH)):
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "redirects": "1",
            "prop": "extracts|pageimages",
            "exintro": "1",
            "explaintext": "1",
            "exsentences": "2",
            "exlimit": "max",
            "piprop": "name",
            "pilimit": "max",
            "titles": "|".join(chunk),
        }
        try:
            doc = request(WIKI_API, pacer, data=params)
        except Exception as e:  # reported, the run continues
            print(f"wikipedia: batch {i} failed: {e!r}"[:200], flush=True)
            continue
        for title, rec in wiki_pages(doc).items():
            if title in by_title:
                out[by_title[title]] = {"title": title, **rec}
        if i % 50 == 0:
            print(f"wikipedia: {i * WIKI_BATCH}/{len(titles)}", flush=True)
    (raw / "wiki.json").write_text(json.dumps(out, ensure_ascii=False), "utf-8")
    print(f"wikipedia: {len(out)} pages, {sum(1 for r in out.values() if r['extract'])} with an extract")
    return 0


# ------------------------------------------------------------------------------------------------- voyage

TEMPLATE = re.compile(r"\{\{\s*([^|{}]+?)\s*\|((?:[^{}]|\{\{[^{}]*\}\})*)\}\}", re.S)
PARAM = re.compile(r"\|\s*([\w-]+)\s*=\s*([^|]*)")


def listings(wikitext: str) -> Iterator[dict[str, str]]:
    """Every template call with a `wikidata=Q…` parameter (the listing templates of any Wikivoyage edition)."""
    for m in TEMPLATE.finditer(wikitext):
        params = {k.lower(): v.strip() for k, v in PARAM.findall("|" + m.group(2))}
        wd = params.get("wikidata", "")
        if re.fullmatch(r"Q\d+", wd):
            yield {"template": m.group(1).strip().lower(), **params}


def voyage_from_texts(texts: Iterable[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for text in texts:
        for li in listings(text):
            q = li["wikidata"]
            rec = out.setdefault(q, {"templates": [], "text": None, "hours": None, "price": None})
            t = li.get("type") or li["template"]
            if t not in rec["templates"]:
                rec["templates"].append(t)
            content = li.get("content") or li.get("описание") or li.get("description")
            if content and not rec["text"]:
                rec["text"] = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", content)[:300]
            rec["hours"] = rec["hours"] or li.get("hours") or li.get("часы")
            rec["price"] = rec["price"] or li.get("price") or li.get("цена")
    return out


def dump_texts(path: Path) -> Iterator[str]:
    """The <text> bodies of a pages-articles XML dump (.bz2), streamed."""
    buf: list[str] = []
    inside = False
    with bz2.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not inside and "<text" in line:
                inside = True
                line = line[line.index(">", line.index("<text")) + 1 :]
            if inside:
                if "</text>" in line:
                    buf.append(line[: line.index("</text>")])
                    yield "".join(buf)
                    buf, inside = [], False
                else:
                    buf.append(line)


def cmd_voyage(raw: Path, dump: Path) -> int:
    import html

    out = voyage_from_texts(html.unescape(t) for t in dump_texts(dump))
    (raw / "voyage.json").write_text(json.dumps(out, ensure_ascii=False), "utf-8")
    print(f"voyage: {len(out)} Q-ids in listings")
    return 0


# ---------------------------------------------------------------------------------------------------- osm

OSM_KEEP = (
    "name",
    "tourism",
    "leisure",
    "amenity",
    "natural",
    "historic",
    "museum",
    "zoo",
    "attraction",
    "wikidata",
    "opening_hours",
    "fee",
    "charge",
    "description",
    "image",
    "wikimedia_commons",
    "website",
    "parking",
    "capacity",
    "access",
)


def osm_from_features(lines: Iterable[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """GeoJSON-seq features → (POI candidates, paid parking points)."""
    from bars_from_extract import elements_from_features

    pois, parking = [], []
    for e in elements_from_features(lines, require_name=False):
        t = e["tags"]
        rec = {"osm": f"{e['type'][0]}{e['id']}", "lat": round(e["lat"], 6), "lon": round(e["lon"], 6)}
        if t.get("amenity") == "parking":
            if t.get("fee", "").lower() in ("yes", "да") or t.get("charge"):
                parking.append(
                    {**rec, "fee": t.get("fee"), "charge": t.get("charge"), "capacity": t.get("capacity")}
                )
            continue
        if not t.get("name") and t.get("leisure") != "playground":
            continue
        pois.append({**rec, "tags": {k: v for k, v in t.items() if k in OSM_KEEP}})
    return pois, parking


def cmd_osm(raw: Path, seq: Path) -> int:
    with seq.open(encoding="utf-8") as fh:
        pois, parking = osm_from_features(fh)
    (raw / "osm_pois.json").write_text(json.dumps(pois, ensure_ascii=False), "utf-8")
    (raw / "parking.json").write_text(json.dumps(parking, ensure_ascii=False), "utf-8")
    print(f"osm: {len(pois)} POI candidates, {len(parking)} paid parking places")
    return 0


# ---------------------------------------------------------------------------------------------- geosearch

GEO_RADIUS_M = 200
GEO_MAX = 6000


def geo_targets(pois: list[dict[str, Any]], osm: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """POIs without a photo, the most notable first (Wikidata sitelinks, then named OSM tourism objects)."""
    out = [
        {"id": p["qid"], "lat": p["lat"], "lon": p["lon"], "rank": int(p.get("sitelinks") or 0)}
        for p in pois
        if not p.get("image")
    ]
    out += [
        {"id": o["osm"], "lat": o["lat"], "lon": o["lon"], "rank": 0}
        for o in osm
        if o["tags"].get("name")
        and (o["tags"].get("tourism") or o["tags"].get("natural"))
        and not (o["tags"].get("image") or o["tags"].get("wikimedia_commons") or o["tags"].get("wikidata"))
    ]
    out.sort(key=lambda x: (-x["rank"], x["id"]))
    return out[:limit]


def cmd_geosearch(raw: Path) -> int:
    pois = json.loads((raw / "pois.json").read_text("utf-8"))
    osm = json.loads((raw / "osm_pois.json").read_text("utf-8")) if (raw / "osm_pois.json").exists() else []
    targets = geo_targets(pois, osm, GEO_MAX)
    pacer = Pacer(0.3)
    out: dict[str, list[str]] = {}
    for i, t in enumerate(targets):
        url = (
            COMMONS_API
            + "?"
            + urllib.parse.urlencode(
                {
                    "action": "query",
                    "format": "json",
                    "formatversion": "2",
                    "list": "geosearch",
                    "gscoord": f"{t['lat']}|{t['lon']}",
                    "gsradius": str(GEO_RADIUS_M),
                    "gsnamespace": "6",
                    "gslimit": "10",
                }
            )
        )
        try:
            doc = request(url, pacer)
        except Exception as e:  # reported, the run continues
            print(f"geosearch: {t['id']} failed: {e!r}"[:200], flush=True)
            continue
        files = [g["title"][len("File:") :] for g in doc.get("query", {}).get("geosearch", [])]
        if files:
            out[t["id"]] = files
        if i % 500 == 0:
            print(f"geosearch: {i}/{len(targets)}", flush=True)
            # written as it goes: a step timeout keeps what was found so far
            (raw / "geosearch.json").write_text(json.dumps(out, ensure_ascii=False), "utf-8")
    (raw / "geosearch.json").write_text(json.dumps(out, ensure_ascii=False), "utf-8")
    print(f"geosearch: {len(out)} of {len(targets)} POIs have nearby files")
    return 0


GEO_PER_POI = 3


def commons_name(v: str | None) -> str | None:
    """An OSM `wikimedia_commons`/`image` value → a Commons file name, if it is one."""
    if not v:
        return None
    v = urllib.parse.unquote(v.strip())
    for prefix in ("File:", "Файл:"):
        if v.startswith(prefix):
            return v[len(prefix) :].replace("_", " ")
    m = re.search(r"commons\.wikimedia\.org/wiki/(?:File|Файл):(.+)$", v)
    return m.group(1).replace("_", " ") if m else None


def candidate_files(raw: Path) -> list[str]:
    def load(name: str, default: Any) -> Any:
        p = raw / name
        return json.loads(p.read_text("utf-8")) if p.exists() else default

    names: set[str] = set()
    names |= {r["image"] for r in load("wiki.json", {}).values() if r.get("image")}
    for files in load("geosearch.json", {}).values():
        names |= set(files[:GEO_PER_POI])
    for o in load("osm_pois.json", []):
        for k in ("wikimedia_commons", "image"):
            n = commons_name(o["tags"].get(k))
            if n:
                names.add(n)
    return sorted(n.replace("_", " ") for n in names)


def cmd_candidates(raw: Path) -> int:
    files = candidate_files(raw)
    (raw / "candidates.json").write_text(json.dumps(files, ensure_ascii=False), "utf-8")
    print(f"candidates: {len(files)} photo files")
    return 0


def main(argv: list[str]) -> int:
    cmd, raw = argv[0], Path(argv[1])
    if cmd == "classes":
        return cmd_classes(raw)
    if cmd == "wikidata":
        return cmd_wikidata(raw)
    if cmd == "wikipedia":
        return cmd_wikipedia(raw)
    if cmd == "voyage":
        return cmd_voyage(raw, Path(argv[2]))
    if cmd == "osm":
        return cmd_osm(raw, Path(argv[2]))
    if cmd == "geosearch":
        return cmd_geosearch(raw)
    if cmd == "candidates":
        return cmd_candidates(raw)
    raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
