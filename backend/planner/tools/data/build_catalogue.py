"""Build the packaged catalogue (ADR-0012 §3) from the raw files the CI fetchers wrote.

A pure function of its inputs (stdlib only), so the sandbox tests it on recorded samples
(`tests/data/samples/raw/`). Inputs, all in one directory:

- ``towns.json``  ``[{qid, name, lat, lon, population, regionIso, regionName, image}]`` (fetch_wikidata towns)
- ``pois.json``   ``[{qid, name, desc, lat, lon, roots: [class qid…], sitelinks, heritage, image, townQid}]``
- ``bars.json``   ``[{osm: "n123", name, lat, lon, tags: {…}, townQid}]`` (fetch_overpass)
- ``credits.json`` ``{file name: {author, licence, url, free}}`` (fetch_commons_meta; optional)
- ``forms.json``  ``{qid: {gen, prep}}`` (inflect.py with pymorphy3; optional)
- ``sources.json`` free-form provenance written by the fetchers (optional)

plus the hand-maintained `region_tz.tsv` and `name_overrides.tsv` next to this file, the fixture worlds
(name forms and Wikidata links win) and `tests/brand_denylist.txt`.

Usage (from `backend/planner`): ``python3 tools/data/build_catalogue.py RAW_DIR [--out DIR] [--version V]``.
Writes ``catalogue_{meta,towns,pois,bars}.json.gz`` (default: `verst_planner/resources/`) and prints a
summary. `build(...)` returns the documents for tests.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from collections.abc import Iterable
from pathlib import Path
from typing import Any

PLANNER = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLANNER))

from verst_planner.catalogue import (  # noqa: E402
    BAR_COLS,
    BAR_KINDS,
    FILES,
    FORMAT_VERSION,
    POI_COLS,
    POI_KINDS,
    TOWN_COLS,
    dump_gz,
    encode_table,
    to_coord,
)

HERE = Path(__file__).resolve().parent
WORLDS = PLANNER / "fixtures" / "worlds"
DENYLIST = PLANNER / "tests" / "brand_denylist.txt"
RESOURCES = PLANNER / "verst_planner" / "resources"

# Wikidata class → POI kind, in priority order (a POI with several roots takes the first listed kind).
CLASS_KIND: tuple[tuple[str, str], ...] = (
    ("Q263274", "kremlin"),  # kremlin (run 6 re-resolved; Q12035 is a spider)
    ("Q57821", "kremlin"),  # fortification
    ("Q23413", "kremlin"),  # castle
    ("Q44613", "monastery"),  # monastery
    ("Q33506", "museum"),  # museum
    ("Q16970", "church"),  # church building
    ("Q2977", "church"),  # cathedral
    ("Q4989906", "monument"),  # monument
    ("Q5003624", "monument"),  # memorial
    ("Q179700", "monument"),  # statue
    ("Q22698", "park"),  # park
    ("Q1107656", "park"),  # garden
    ("Q6017969", "viewpoint"),  # scenic viewpoint
    ("Q1851368", "embankment"),  # waterfront «набережная» (run 6; Q1501717 is an HIV trial)
    ("Q174782", "square"),  # town square
    ("Q2319498", "attraction"),  # architectural landmark
    ("Q570116", "attraction"),  # tourist attraction
)
CLASS_IDS = tuple(q for q, _k in CLASS_KIND)

POI_CAP = ((1_000_000, 120), (100_000, 50))
POI_CAP_TOURIST = 40
POI_CAP_OTHER = 12
BAR_CAP = 60
TOURIST_TOP = 60
TOWN_MATCH_KM = 15.0
PLACE_MATCH_KM = 1.5
DESC_MAX = 120
AUTHOR_MAX = 60
BRANDED_TAGS = ("brand", "brand:wikidata", "brand:ru")
RYUMKA = re.compile(r"рюмочн", re.IGNORECASE)


# ------------------------------------------------------------------------------------------- helpers


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(min(1.0, math.sqrt(h)))


def norm(s: str) -> str:
    """Casefolded, yo→ye, punctuation-free name for matching."""
    s = unicodedata.normalize("NFC", s).casefold().replace("\u0451", "\u0435")
    return re.sub(r"[^\w\s-]", " ", s).strip()


def tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[\s-]+", norm(s)) if len(t) > 2}


def similar(a: str, b: str) -> bool:
    na, nb = norm(a), norm(b)
    if na == nb or na in nb or nb in na:
        return True
    ta, tb = tokens(a), tokens(b)
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= 0.5


def read_tsv(path: Path) -> list[list[str]]:
    rows = []
    for line in path.read_text("utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            rows.append(line.split("\t"))
    return rows


def denylist() -> list[str]:
    return [
        line.strip().casefold()
        for line in DENYLIST.read_text("utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def denied(name: str, deny: Iterable[str]) -> bool:
    low = name.casefold()
    return any(b in low for b in deny)


def load_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text("utf-8")) if path.exists() else default


def fixture_worlds() -> list[dict[str, Any]]:
    return [json.loads((WORLDS / f"{w}.json").read_text("utf-8")) for w in ("central_russia_v1",)]


def fixture_points(
    world: dict[str, Any],
) -> tuple[dict[str, tuple[float, float]], dict[str, tuple[float, float]]]:
    """Town and sight coordinates of a fixture world (anchors resolved with the engine's loader)."""
    from verst_planner.adapters.fake.world import FakeWorld
    from verst_planner.domain.enums import PlaceType

    w = FakeWorld.from_dict(world)
    towns = {t.id: (t.point.lat, t.point.lon) for t in w.towns.values()}
    sights = {p.id: (p.point.lat, p.point.lon) for p in w.places.values() if p.type is PlaceType.SIGHT}
    return towns, sights


# ------------------------------------------------------------------------------------------- build


# Run 7 took the subclasses of «город России» (547 classes) and with them villages, districts, historic
# centres and numbered military towns. A town needs ≥ 800 people and a plain town name.
MIN_TOWN_POPULATION = 800  # Чекалин, the smallest town, has ~900
MAX_TOWN_WORDS = 3
NOT_A_TOWN = re.compile(
    r"[()«»]|район|километр|-\d|^\d|^[a-zа-яё]|^(Деревня|Село|Посёлок|Поселок|Станица|Хутор|Курорт)\b"
)


def is_town(t: dict[str, Any]) -> bool:
    name = str(t.get("name") or "")
    return (
        int(t.get("population") or 0) >= MIN_TOWN_POPULATION
        and len(name.split()) <= MAX_TOWN_WORDS
        and NOT_A_TOWN.search(name) is None
    )


EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
URL = re.compile(r"(https?://|www\.)\S+", re.I)


def clean_author(author: str) -> str | None:
    """Commons «Artist» without markup, e-mail addresses (run 3: «…@yandex.ru») and URLs."""
    text = re.sub(r"<[^>]+>", "", author)
    text = URL.sub("", EMAIL.sub("", text))
    text = re.sub(r"\s+", " ", re.sub(r"\(\s*\)|\[\s*\]", "", text)).strip(" ,;:-–—")
    return text[:AUTHOR_MAX] or None


TRAILING_PAREN = re.compile(r"\s*\(([^()]*)\)$")


def poi_name(name: str, town: str) -> str:
    """«Площадь Свободы (Казань)» → «Площадь Свободы» in Казань (the Wikidata disambiguation suffix)."""
    m = TRAILING_PAREN.search(name)
    if m and norm(m.group(1)) == norm(town) and m.start() > 0:
        return name[: m.start()]
    return name


def poi_kind(roots: Iterable[str]) -> str | None:
    have = set(roots)
    for q, kind in CLASS_KIND:
        if q in have:
            return kind
    return None


def bar_kind(name: str, tags: dict[str, str]) -> str:
    if RYUMKA.search(name):
        return "ryumochnaya"
    if tags.get("craft") == "brewery" or tags.get("microbrewery") == "yes":
        return "craft"
    if tags.get("amenity") in ("pub", "biergarten"):
        return "pub"
    return "bar"


def poi_cap(population: int, tourist: bool) -> int:
    for threshold, cap in POI_CAP:
        if population >= threshold:
            return cap
    return POI_CAP_TOURIST if tourist else POI_CAP_OTHER


def build(
    raw_dir: Path, version: str = "dev", built_at: str = "", hours_ok: Any = None
) -> dict[str, dict[str, Any]]:
    """The four documents (`meta`, `towns`, `pois`, `bars`) from the raw directory."""
    deny = denylist()
    tz = {code: zone for code, zone in read_tsv(HERE / "region_tz.tsv")}
    overrides = {qid_or_name: (gen, prep) for qid_or_name, gen, prep in read_tsv(HERE / "name_overrides.tsv")}
    raw_towns = load_json(raw_dir / "towns.json", [])
    raw_pois = load_json(raw_dir / "pois.json", [])
    raw_bars = load_json(raw_dir / "bars.json", [])
    credits_in = load_json(raw_dir / "credits.json", {})
    forms = load_json(raw_dir / "forms.json", {})
    sources = load_json(raw_dir / "sources.json", {})

    # ---- towns: dedupe by qid (largest population wins), ISO 3166-2:RU regions only, real towns only
    region_fix = {name: code for name, code in read_tsv(HERE / "region_overrides.tsv")}
    by_qid: dict[str, dict[str, Any]] = {}
    region_names: dict[str, str] = {}
    for t in raw_towns:
        code = t.get("regionIso") or region_fix.get(t.get("name") or "")
        if code not in tz or not t.get("name") or not is_town(t):
            continue
        t = {**t, "regionIso": code}
        region_names.setdefault(code, t.get("regionName") or code)
        old = by_qid.get(t["qid"])
        if old is None or (t.get("population") or 0) > (old.get("population") or 0):
            by_qid[t["qid"]] = t
    towns = sorted(by_qid.values(), key=lambda t: (-(t.get("population") or 0), t["qid"]))

    # ---- fixture links and fixture name forms (they win over pymorphy3 and the override table)
    links: dict[str, dict[str, Any]] = {}
    fixture_forms: dict[str, tuple[str | None, str | None]] = {}
    for world in fixture_worlds():
        town_pts, sight_pts = fixture_points(world)
        for ft in world["towns"]:
            p = town_pts[ft["id"]]
            match = next(
                (
                    t
                    for t in towns
                    if norm(t["name"]) == norm(ft["nameRu"])
                    and haversine_km(p, (t["lat"], t["lon"])) <= TOWN_MATCH_KM
                ),
                None,
            )
            if match is not None:
                links[ft["id"]] = {"wikidata": match["qid"], "image": match.get("image")}
                fixture_forms[match["qid"]] = (ft.get("nameGenRu"), ft.get("namePrepRu"))
        # one-to-one: every candidate pair (fixture sight, POI) by distance, closest pairs first
        pairs = []
        for fp in world["places"]:
            if fp["type"] != "sight":
                continue
            p = sight_pts[fp["id"]]
            for r in raw_pois:
                d = haversine_km(p, (r["lat"], r["lon"]))
                if d <= PLACE_MATCH_KM and similar(fp["nameRu"], r["name"]):
                    pairs.append((d, fp["id"], r["qid"], r))
        taken: set[str] = set()
        for _d, fid, qid, r in sorted(pairs, key=lambda x: (x[0], x[1], x[2])):
            if fid in links or qid in taken:
                continue
            taken.add(qid)
            links[fid] = {"wikidata": qid, "image": r.get("image")}

    # ---- credits (only free files keep their image)
    credit_list: list[dict[str, Any]] = []
    credit_idx: dict[tuple[Any, ...], int] = {}

    def image_and_credit(file: str | None) -> tuple[str | None, int | None]:
        if not file:
            return None, None
        c = credits_in.get(file)
        if c is None:
            return file, None  # unknown credits: shown as «Фото: Wikimedia Commons»
        if not c.get("free", True):
            return None, None
        author = c.get("author")
        if author:
            author = clean_author(author)
        key = (author, c.get("licence"), c.get("url"))
        if key not in credit_idx:
            credit_idx[key] = len(credit_list)
            credit_list.append({"author": author, "licence": c.get("licence"), "url": c.get("url")})
        return file, credit_idx[key]

    regions_sorted = sorted({t["regionIso"] for t in towns})
    region_index = {c: i for i, c in enumerate(regions_sorted)}
    town_rows = []
    for t in towns:
        gen, prep = fixture_forms.get(t["qid"], (None, None))
        o = overrides.get(t["qid"]) or overrides.get(t["name"])
        f = forms.get(t["qid"], {})
        gen = gen or (o[0] if o else None) or f.get("gen")
        prep = prep or (o[1] if o else None) or f.get("prep")
        image, credit = image_and_credit(t.get("image"))
        town_rows.append(
            {
                "id": t["qid"],
                "name": t["name"],
                "gen": gen,
                "prep": prep,
                "lat": to_coord(t["lat"]),
                "lon": to_coord(t["lon"]),
                "pop": int(t.get("population") or 0),
                "region": region_index[t["regionIso"]],
                "image": image,
                "credit": credit,
            }
        )
    town_pos = {t["qid"]: i for i, t in enumerate(towns)}

    # ---- POIs: kind, nearest town among the towns that found it, deny-list, caps
    pois_by_qid: dict[str, dict[str, Any]] = {}
    for r in raw_pois:
        kind = poi_kind(r.get("roots", []))
        if kind is None or not r.get("name") or denied(r["name"], deny) or r.get("townQid") not in town_pos:
            continue
        town = towns[town_pos[r["townQid"]]]
        d = haversine_km((r["lat"], r["lon"]), (town["lat"], town["lon"]))
        old = pois_by_qid.get(r["qid"])
        if old is None or d < old["_d"] or (d == old["_d"] and r["townQid"] < old["townQid"]):
            pois_by_qid[r["qid"]] = {**r, "_kind": kind, "_d": d}
    sitelinks_by_town: dict[str, int] = {}
    for r in pois_by_qid.values():
        sitelinks_by_town[r["townQid"]] = sitelinks_by_town.get(r["townQid"], 0) + int(
            r.get("sitelinks") or 0
        )
    tourist = {q for q, _s in sorted(sitelinks_by_town.items(), key=lambda x: (-x[1], x[0]))[:TOURIST_TOP]}
    tourist |= {link["wikidata"] for fid, link in links.items() if fid.startswith("t_")}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for r in pois_by_qid.values():
        grouped.setdefault(r["townQid"], []).append(r)
    poi_rows = []
    for qid in sorted(grouped, key=lambda q: town_pos[q]):
        town = towns[town_pos[qid]]
        lst = sorted(
            grouped[qid],
            key=lambda r: (-int(r.get("sitelinks") or 0), -int(bool(r.get("heritage"))), r["qid"]),
        )
        for r in lst[: poi_cap(int(town.get("population") or 0), qid in tourist)]:
            image, credit = image_and_credit(r.get("image"))
            desc = r.get("desc")
            poi_rows.append(
                {
                    "id": r["qid"],
                    "name": poi_name(r["name"], town["name"]),
                    "desc": desc[:DESC_MAX] if desc else None,
                    "kind": POI_KINDS.index(r["_kind"]),
                    "lat": to_coord(r["lat"]),
                    "lon": to_coord(r["lon"]),
                    "town": town_pos[qid],
                    "sitelinks": int(r.get("sitelinks") or 0),
                    "heritage": 1 if r.get("heritage") else 0,
                    "image": image,
                    "credit": credit,
                }
            )

    # ---- bars: no chains, named, deny-list, caps (known hours and рюмочные first)
    bars_by_id: dict[str, dict[str, Any]] = {}
    for b in raw_bars:
        tags = b.get("tags") or {}
        name = b.get("name") or tags.get("name")
        if (
            not name
            or any(k in tags for k in BRANDED_TAGS)
            or denied(name, deny)
            or b.get("townQid") not in town_pos
        ):
            continue
        hours = tags.get("opening_hours")
        if hours and hours_ok is not None and not hours_ok(hours):
            hours = None
        bars_by_id.setdefault(b["osm"], {**b, "name": name, "_kind": bar_kind(name, tags), "_hours": hours})
    bars_grouped: dict[str, list[dict[str, Any]]] = {}
    for b in bars_by_id.values():
        bars_grouped.setdefault(b["townQid"], []).append(b)
    bar_rows = []
    for qid in sorted(bars_grouped, key=lambda q: town_pos[q]):
        lst = sorted(
            bars_grouped[qid], key=lambda b: (b["_hours"] is None, b["_kind"] != "ryumochnaya", b["osm"])
        )
        for b in lst[:BAR_CAP]:
            bar_rows.append(
                {
                    "id": b["osm"],
                    "name": b["name"],
                    "kind": BAR_KINDS.index(b["_kind"]),
                    "lat": to_coord(b["lat"]),
                    "lon": to_coord(b["lon"]),
                    "town": town_pos[qid],
                    "hours": b["_hours"],
                }
            )

    # links carry credit indices too
    meta_links = {}
    for fid in sorted(links):
        image, credit = image_and_credit(links[fid].get("image"))
        meta_links[fid] = {"wikidata": links[fid]["wikidata"], "image": image, "credit": credit}
    meta = {
        "v": FORMAT_VERSION,
        "version": version,
        "builtAt": built_at,
        "regions": [{"code": c, "nameRu": region_names[c], "tz": tz[c]} for c in regions_sorted],
        "poiKinds": list(POI_KINDS),
        "barKinds": list(BAR_KINDS),
        "credits": credit_list,
        "links": meta_links,
        "sources": sources,
    }
    return {
        "meta": meta,
        "towns": encode_table(town_rows, TOWN_COLS),
        "pois": encode_table(poi_rows, POI_COLS),
        "bars": encode_table(bar_rows, BAR_COLS),
    }


def write(docs: dict[str, dict[str, Any]], out: Path) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    sizes = {}
    for key, name in FILES.items():
        data = dump_gz(docs[key])
        (out / name).write_bytes(data)
        sizes[name] = len(data)
    return sizes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="build_catalogue")
    ap.add_argument("raw", type=Path)
    ap.add_argument("--out", type=Path, default=RESOURCES)
    ap.add_argument("--version", default="dev")
    ap.add_argument("--built-at", default="")
    args = ap.parse_args(argv)
    from verst_planner.domain.errors import OpeningHoursParseError
    from verst_planner.hours import parse

    def hours_ok(text: str) -> bool:
        try:
            parse(text)
        except OpeningHoursParseError:
            return False
        return True

    docs = build(args.raw, args.version, args.built_at, hours_ok)
    sizes = write(docs, args.out)
    summary = {
        "towns": docs["towns"]["n"],
        "pois": docs["pois"]["n"],
        "bars": docs["bars"]["n"],
        "links": len(docs["meta"]["links"]),
        "credits": len(docs["meta"]["credits"]),
        "bytes": sizes,
        "totalBytes": sum(sizes.values()),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
