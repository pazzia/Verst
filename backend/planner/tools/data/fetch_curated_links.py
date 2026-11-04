"""Wikidata candidates for the curated sights that have no photo (CEO 04.11, «картинок нет»). CI only:

    python3 tools/data/fetch_curated_links.py OUT_DIR      # writes OUT_DIR/curated_candidates.json

The fixture world's sights are matched to Wikidata items in `build_catalogue.py` by name within
`PLACE_MATCH_KM` of the fixture point; 64 of 101 found none (the fixture points are 1-6 km off and the names
differ: «Остров-град Свияжск» vs «Свияжск»). Their photos must not be guessed: this script only lists, for each
sight still without an image, the Wikidata items with a photo (P18) within `RADIUS_KM` of the fixture point,
ranked by name similarity then distance, with the Commons author and licence of each photo. A person reviews
the list and writes the chosen ids into `curated_wikidata.tsv`; nothing is linked automatically.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

from build_catalogue import fixture_points, fixture_worlds, similar, tokens  # noqa: E402
from fetch_commons_meta import API as COMMONS_API  # noqa: E402
from fetch_commons_meta import BATCH, credits_from_pages  # noqa: E402
from fetch_wikidata import WDQS, commons_file  # noqa: E402
from http_util import Pacer, request  # noqa: E402

RADIUS_KM = 10.0
KEEP = 8
"""Candidates kept per sight (the best by name, then the nearest)."""
META = HERE.parents[1] / "verst_planner" / "resources" / "catalogue_meta.json.gz"

Q_AROUND = """SELECT ?item ?itemLabel ?itemDescription ?image ?dist (GROUP_CONCAT(DISTINCT ?alt; SEPARATOR="|") AS ?alts)
       (SAMPLE(?clsLabel) AS ?cls) WHERE {{
  SERVICE wikibase:around {{
    ?item wdt:P625 ?coord . bd:serviceParam wikibase:center "Point({lon} {lat})"^^geo:wktLiteral .
    bd:serviceParam wikibase:radius "{radius}" . bd:serviceParam wikibase:distance ?dist .
  }}
  ?item wdt:P18 ?image .
  OPTIONAL {{ ?item rdfs:label ?itemLabel . FILTER(LANG(?itemLabel) = "ru") }}
  OPTIONAL {{ ?item schema:description ?itemDescription . FILTER(LANG(?itemDescription) = "ru") }}
  OPTIONAL {{ ?item skos:altLabel ?alt . FILTER(LANG(?alt) = "ru") }}
  OPTIONAL {{ ?item wdt:P31 ?c . ?c rdfs:label ?clsLabel . FILTER(LANG(?clsLabel) = "ru") }}
}} GROUP BY ?item ?itemLabel ?itemDescription ?image ?dist"""


def unlinked(meta: dict[str, Any]) -> list[dict[str, Any]]:
    """The fixture sights whose catalogue link is missing or has no image."""
    links = meta.get("links", {})
    out = []
    for world in fixture_worlds():
        _, pts = fixture_points(world)
        for p in world["places"]:
            if p["type"] != "sight" or (links.get(p["id"]) or {}).get("image"):
                continue
            lat, lon = pts[p["id"]]
            out.append({"id": p["id"], "name": p["nameRu"], "town": p.get("townId"), "lat": lat, "lon": lon})
    return out


def name_score(name: str, label: str, alts: list[str]) -> float:
    """1 = the same name (or one inside the other), else the best token overlap of the label and aliases."""
    best = 0.0
    for x in [label, *alts]:
        if not x:
            continue
        if similar(name, x):
            return 1.0
        a, b = tokens(name), tokens(x)
        if a and b:
            best = max(best, len(a & b) / len(a | b))
    return best


def rank(sight: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pure: the SPARQL rows of one sight → candidates, best name first, then nearest."""
    by_item: dict[str, dict[str, Any]] = {}
    for b in rows:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        label = b.get("itemLabel", {}).get("value", "")
        alts = [a for a in b.get("alts", {}).get("value", "").split("|") if a]
        c = {
            "qid": qid,
            "label": label,
            "description": b.get("itemDescription", {}).get("value"),
            "class": b.get("cls", {}).get("value"),
            "image": commons_file(b.get("image", {}).get("value")),
            "km": round(float(b.get("dist", {}).get("value", "nan")), 2),
            "nameScore": round(name_score(sight["name"], label, alts), 2),
        }
        old = by_item.get(qid)
        if old is None or c["km"] < old["km"]:
            by_item[qid] = c
    ranked = sorted(by_item.values(), key=lambda c: (-c["nameScore"], c["km"], c["qid"]))
    return ranked[:KEEP]


def main(argv: list[str]) -> int:
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    meta = json.loads(gzip.decompress(META.read_bytes()))
    sights = unlinked(meta)
    print(f"curated sights without a photo: {len(sights)}", flush=True)
    pacer = Pacer(2.0)
    for s in sights:
        q = Q_AROUND.format(lat=s["lat"], lon=s["lon"], radius=RADIUS_KM)
        doc = request(WDQS, pacer, data={"query": q, "format": "json"}, accept="application/sparql-results+json")
        s["candidates"] = rank(s, list(doc["results"]["bindings"]))
        top = s["candidates"][0] if s["candidates"] else None
        print(f"{s['id']}: {len(s['candidates'])} candidates; top {top and (top['qid'], top['label'], top['km'])}")
    files = sorted({c["image"] for s in sights for c in s["candidates"] if c["image"]})
    credits: dict[str, Any] = {}
    cpacer = Pacer(1.0)
    for i in range(0, len(files), BATCH):
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "imageinfo",
            "iiprop": "extmetadata",
            "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl|NonFree",
            "titles": "|".join("File:" + f for f in files[i : i + BATCH]),
        }
        doc = request(COMMONS_API, cpacer, data=params)
        normalized = {n["to"]: n["from"] for n in doc.get("query", {}).get("normalized", [])}
        for name, c in credits_from_pages(doc.get("query", {}).get("pages", [])).items():
            credits[normalized.get("File:" + name, "File:" + name)[len("File:") :]] = c
    for s in sights:
        for c in s["candidates"]:
            c["credit"] = credits.get(c["image"] or "")
    (out / "curated_candidates.json").write_text(json.dumps(sights, ensure_ascii=False, indent=1), "utf-8")
    print(f"written: {len(sights)} sights, {len(files)} photos, {len(credits)} credits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
