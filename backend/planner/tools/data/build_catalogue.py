"""Build the packaged catalogue (ADR-0012 §3) from the raw files the CI fetchers wrote.

A pure function of its inputs (stdlib only), so the sandbox tests it on recorded samples
(`tests/data/samples/raw/`). Inputs, all in one directory:

- ``towns.json``  ``[{qid, name, lat, lon, population, regionIso, regionName, image}]`` (fetch_wikidata towns)
- ``pois.json``   ``[{qid, name, desc, lat, lon, roots: [class qid…], sitelinks, heritage, image, townQid}]``
- ``bars.json``   ``[{osm: "n123", name, lat, lon, tags: {…}, townQid}]`` (bars_from_extract / fetch_overpass)
- ``food.json``   ``[{osm: "n123", name, lat, lon, tags: {…}, townQid}]`` (food_from_extract; optional — without it
  `catalogue_food` has no rows and the walk says there is no food data yet)
- ``credits.json`` ``{file name: {author, licence, url, free}}`` (fetch_commons_meta; optional)
- ``forms.json``  ``{qid: {gen, prep}}`` (inflect.py with pymorphy3; optional)
- ``sources.json`` free-form provenance written by the fetchers (optional)

plus the hand-maintained `region_tz.tsv` and `name_overrides.tsv` next to this file, the fixture worlds
(name forms and Wikidata links win) and `tests/brand_denylist.txt`.

Usage (from `backend/planner`): ``python3 tools/data/build_catalogue.py RAW_DIR [--out DIR] [--version V]``.
Writes ``catalogue_{meta,towns,pois,bars,food}.json.gz`` (default: `verst_planner/resources/`) and prints a
summary. `build(...)` returns the documents for tests. `meta.licence` carries the ODbL 1.0 notice of the
whole catalogue (`licence_block`); Commons files that are GFDL-only are not used (`gfdl_only`).
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
sys.path.insert(0, str(Path(__file__).resolve().parent))  # enrich, fetch_extras

from enrich import (  # noqa: E402
    OSM_PER_TOWN,
    OSM_RADIUS_KM,
    PLAYGROUND_KM,
    PLAYGROUNDS_PER_TOWN,
    Extras,
    OsmIndex,
    card_level,
    excluded,
    extract_for,
    geosearch_pick,
    heritage_level,
    in_voyage,
    osm_is_tourism,
    osm_kind,
    osm_name_ok,
    quality,
    refine_kind,
    tidy,
)

from verst_planner.catalogue import (  # noqa: E402
    BAR_COLS,
    BAR_KINDS,
    COORD_SCALE,
    FILES,
    FOOD_COLS,
    FOOD_KINDS,
    FORMAT_VERSION,
    POI_COLS,
    POI_KINDS,
    POI_OPT_COLS,
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
# CEO 2026-10-29: a per-town bar cap that grows with the town (СПб and Москва have hundreds of bars; 60 left
# 4 рюмочные and no beer bar in СПб) — the specialised kinds are kept first, generic bars fill the rest
BAR_CAP_MIN, BAR_CAP_MAX, BAR_CAP_PEOPLE = 60, 400, 12_500
# CEO 2026-10-29: restaurants, cafés and fast food (OSM), capped per town by population (APK size: ~1 MB)
FOOD_CAP_MIN, FOOD_CAP_MAX, FOOD_CAP_PEOPLE = 15, 600, 2_500
CUISINE_MAX = 40
TOURIST_TOP = 60
TOWN_MATCH_KM = 15.0
PLACE_MATCH_KM = 1.5
DESC_MAX = 120
BRANDED_TAGS = ("brand", "brand:wikidata", "brand:ru")
# CEO 2026-10-29: «По рюмочным» = places for strong spirits and shots, «Пивной» = beer places. A name word
# beginning (not preceded by a letter) decides; OSM tags too where they exist. Run 7 (5 382 bars) has no
# drink:vodka / bar=* values beyond «bar=yes»; it has craft_beer=yes (91), craft=brewery (56), brewery=* (90),
# microbrewery=yes (52), drink:beer (22).
_WORD = r"(?<![^\W\d_])"
RYUMKA = re.compile(
    _WORD + r"(?:рюмоч|рюмк|стопк|стопоч|налив(?:оч|к|айк)|настоеч|настойк|водоч|водк|самогон|чарк"
    r"|шот(?:-|\s)?бар|шоты\b|shots?\b|shot\s?bar)",
    re.IGNORECASE,
)
CRAFT_NAME = re.compile(
    _WORD + r"(?:крафт|craft|brew|пивовар|пивоварн|tap(?:room|house|\b)|тап(?:рум|хаус)\b)", re.IGNORECASE
)
BEER_NAME = re.compile(
    _WORD + r"(?:пив|beer|bier|эль\b|ale\b|ales\b|паб\b|pub\b|пинт|pint|хмел|солод|ipa\b)", re.IGNORECASE
)
YES = ("yes", "only", "draught")
CRAFT_YES = (*YES, "served")


# ------------------------------------------------------------------------------------------- licence

# ODbL package (CEO D-IR-07; docs/legal/risk-register.md R-01, R-09, R-10; lawyer brief appendix B). The whole
# catalogue is a Derivative Database of OpenStreetMap and is licensed under ODbL 1.0 as a database (ODbL 4.4);
# the contents keep their sources' licences. `meta.licence` is the notice the database carries (ODbL 4.2) and
# names the free copy (ODbL 4.6). The same URIs are in the app's `assets/licenses/data.txt` and
# `data/catalogue/README.md` (`tests/unit/test_data_licence.py` keeps them in step).
ODBL_URI = "https://opendatacommons.org/licenses/odbl/1-0/"
OSM_COPYRIGHT_URI = "https://www.openstreetmap.org/copyright"
CC0_URI = "https://creativecommons.org/publicdomain/zero/1.0/"
CC_BY_SA_4_URI = "https://creativecommons.org/licenses/by-sa/4.0/"
CATALOGUE_COPY_URI = "https://github.com/pazzia/Verst/tree/main/data/catalogue"
LICENCE_NOTICE = (
    "Verst place catalogue (catalogue_*.json.gz). Contains information from OpenStreetMap "
    f"({OSM_COPYRIGHT_URI}), which is made available here under the Open Database License (ODbL) 1.0: "
    f"{ODBL_URI}. © OpenStreetMap contributors. This catalogue is a Derivative Database of OpenStreetMap "
    "and is licensed under ODbL 1.0. Wikidata content: CC0 1.0. Wikipedia / Wikivoyage extracts: "
    "CC BY-SA 4.0, abridged. Photos: Wikimedia Commons, licence per file (see credits). "
    f"A free machine-readable copy: {CATALOGUE_COPY_URI}"
)


def licence_block(version: str) -> dict[str, Any]:
    """`meta.licence`: ODbL 1.0 for the database as a whole, the attributions per source (which parts of the
    catalogue each one fed), the source and licence URIs, the free copy and the build id (= `meta.version`)."""
    return {
        "database": {
            "licence": "ODbL-1.0",
            "name": "Open Database License (ODbL) 1.0",
            "uri": ODBL_URI,
            "scope": "the catalogue as a whole: catalogue_meta, catalogue_towns, catalogue_pois, catalogue_bars, "
            "catalogue_food",
            "derivativeOf": "OpenStreetMap",
        },
        "notice": LICENCE_NOTICE,
        "attribution": [
            {
                "source": "OpenStreetMap",
                "text": "© OpenStreetMap contributors",
                "licence": "ODbL-1.0",
                "licenceUri": ODBL_URI,
                "uri": OSM_COPYRIGHT_URI,
                "parts": [
                    "bars",
                    "food (restaurants, cafés, fast food, food courts)",
                    "pois with an osm_* id",
                    "pois.hours, pois.fee, pois.website",
                    "pois.extract where extractSrc = osm",
                    "pois.image where imageSrc = osm (the file named by the OSM tag)",
                    "meta.parking",
                ],
            },
            {
                "source": "Wikidata",
                "text": "Wikidata",
                "licence": "CC0-1.0",
                "licenceUri": CC0_URI,
                "uri": "https://www.wikidata.org/wiki/Wikidata:Licensing",
                "parts": [
                    "towns",
                    "pois with a Q* id",
                    "pois.desc, pois.extract where extractSrc = wikidata",
                    "meta.regions, meta.links",
                ],
            },
            {
                "source": "Wikipedia (ru)",
                "text": "Wikipedia contributors (the article's history)",
                "licence": "CC-BY-SA-4.0",
                "licenceUri": CC_BY_SA_4_URI,
                "uri": "https://ru.wikipedia.org/",
                "abridged": True,
                "parts": ["pois.extract where extractSrc = wikipedia (the first sentence of the article)"],
            },
            {
                "source": "Wikivoyage (ru)",
                "text": "Wikivoyage contributors (the article's history)",
                "licence": "CC-BY-SA-4.0",
                "licenceUri": CC_BY_SA_4_URI,
                "uri": "https://ru.wikivoyage.org/",
                "abridged": True,
                "parts": ["pois.extract where extractSrc = wikivoyage (the first sentence of the listing)"],
            },
            {
                "source": "Wikimedia Commons",
                "text": "the author named in meta.credits",
                "licence": "per file (meta.credits); GFDL-only files are not used",
                "licenceUri": None,
                "uri": "https://commons.wikimedia.org/",
                "parts": ["towns.image, pois.image, meta.links.image (file names only)", "meta.credits"],
            },
        ],
        "copy": CATALOGUE_COPY_URI,
        "build": version,
    }


GFDL = re.compile(r"(?:gfdl|gnu free documentation licen[cs]e)\b", re.I)
LICENCE_SEP = re.compile(r"\s*(?:[,;|/+]|\bor\b|\band\b|\bили\b)\s*", re.I)


def gfdl_only(licence: str | None) -> bool:
    """R-10: a Commons file whose only licence is the GFDL (any version). The GFDL wants its full text with every
    copy, which a photo credit cannot carry, so the builder does not use the file. A file that also offers
    another licence («GFDL, CC BY-SA 3.0») stays: the credit then names that licence."""
    parts = [p for p in LICENCE_SEP.split((licence or "").strip()) if p]
    return bool(parts) and all(GFDL.match(p) for p in parts)


# ------------------------------------------------------------------------------------------- helpers

MISPLACED_KM = 40.0
PAREN_TOWN = re.compile(r"\(([^()]+)\)\s*$")


def misplaced(r: dict[str, Any], by_name: dict[str, list[tuple[float, float]]]) -> bool:
    """«Памятник Чернышевскому (Москва)» at Сергиев Посад: the name's own town disagrees with the
    coordinates by more than `MISPLACED_KM` (a Wikidata coordinate error) — do not ship it."""
    m = PAREN_TOWN.search(str(r.get("name") or ""))
    if m is None:
        return False
    pts = by_name.get(m.group(1).strip().casefold())
    if not pts:
        return False
    return min(haversine_km((r["lat"], r["lon"]), p) for p in pts) > MISPLACED_KM


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
    """Substring match on purpose (HYG-01): a pre-filter stricter than the release gates' word-start match
    (`tests/unit/test_brands.py`), so whatever the builder keeps also passes the gates."""
    low = name.casefold()
    return any(b in low for b in deny)


GENERIC_PLAYGROUND = "Детская площадка"
VO = re.compile(r"^[ВвФф][бвгджзйклмнпрстфхцчшщ]")  # «во Владимире», «во Пскове» — not «в Вологде»


def playground_name(name: str, town: dict[str, Any]) -> str:
    """M9: never a bare «Детская площадка» — «Детская площадка в Клину» (the town's prepositional form)."""
    if name != GENERIC_PLAYGROUND:
        return name
    prep = town.get("prep")
    if not prep or prep == town["name"]:  # no prepositional form known: «Детская площадка, Благовещенск»
        return f"{name}, {town['name']}"
    return f"{name} {'во' if VO.match(prep) else 'в'} {prep}"


def website(tags: dict[str, str], deny: Iterable[str]) -> str | None:
    """The OSM `website` when it is a plain http(s) link of ≤ 100 chars and no deny-listed brand (a map
    service redirect such as link.2gis.ru is not the place's site)."""
    url = str(tags.get("website") or "").strip()
    if not url.startswith(("http://", "https://")) or len(url) > 100 or denied(url, deny):
        return None
    return url


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


# Release S3: Commons «Artist» fields are free text («This photography was created by Artem Topchiy (user
# Art-top)», «… Original uploader was … at ru.wikipedia», «Own work», camera coordinates). The card shows a
# short name only; anything that does not reduce to one is dropped (the card then says «Wikimedia Commons»).
AUTHOR_MAX = 40
AUTHOR_MAX_WORDS = 4
AT_EMAIL = re.compile(r"\S+\s*\[at\]\s*\S+", re.I)
CUT_AT = re.compile(
    r"\s*(?:,\s*)?(?:\boriginal uploader\b|\buploaded\b|\bcamera location\b|\bother photos\b|\bplease\b"
    r"|\bwith permission\b|\+?\s*\bmodified by\b|\bchanges by\b|\bderivative work\b|\blicen[cs]ed?\b"
    r"|\bcc[ -]by\b|\bpublic domain\b|,?\s*автор памятника|,?\s*скульптор\b|,?\s*архитектор\w*\b"
    r"|\barchitects?\b|\bfor\b|\bfrom\b|\bat \w+ wikipedia\b|\bat [a-z]{2}\.wiki\w*|\bс викисклада\b"
    r"|\bиспользуя\b|\d{1,2}:\d{2}\b).*$",
    re.I,
)
SEP = r"(?:\s*(?:\bby\b|:|-)\s*|\s+)"
LEAD = re.compile(
    r"^(?:this (?:photo(?:graph)?y?|image|picture) (?:was|is) (?:taken|created|made|shot) by\s+"
    r"|(?:photo(?:graph)?y?|photographer|image|picture|author|creator|автор(?: фото)?|фото(?:граф)?)"
    + SEP
    + r"|(?:(?:russian|english) wikipedia )?(?:[a-z]{2,3}:)?(?:user|uzer|участник|creator)\s*[:\s]\s*)+",
    re.I,
)
NO_AUTHOR = re.compile(
    r"^(?:own work|собственная работа|(?:unknown(?: photographer| author)?\s*)+|неизвестен|неизвестный автор"
    r"|anonymous|see below|see description|wikimedia commons|(?:made|taken) by the uploader|the uploader|(?:this|it) is\b.*)\.?$",
    re.I,
)
UPLOADER_ONLY = re.compile(
    r"^(?:(?:the )?original uploader was (.+?) at \S+|no machine-readable author provided\.?\s*(.+?)~\w+)",
    re.I,
)
PARENS = re.compile(r"\s*[(\[][^()\[\]]*[)\]]|\s*[(\[][^()\[\]]*$")


def clean_author(author: str) -> str | None:
    """A short name from a Commons «Artist» field, or None (no markup, URLs, e-mails, sentences, licences)."""
    import html

    text = html.unescape(re.sub(r"<[^>]+>", " ", author))
    text = URL.sub(" ", EMAIL.sub(" ", AT_EMAIL.sub(" ", text)))
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^\S+\.(?:jpe?g|png|tiff?|gif|svg|webp)\s*:\s*", "", text, flags=re.I)  # «X.jpg: Name»
    text = text.lstrip(" .,;:")
    m = UPLOADER_ONLY.match(text)
    if m:  # «The original uploader was Digr at Russian Wikipedia.» → «Digr»
        text = m.group(1) or m.group(2)
    text = CUT_AT.sub("", text)
    # the first sentence: a full stop after a word of 4+ letters followed by a capitalised word
    text = re.split(r"(?<=[^\W\d_]{3})\.\s+(?=[A-ZА-ЯЁ])", text, maxsplit=1)[0]
    text = PARENS.sub("", text)
    text = LEAD.sub("", text.strip()).replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip(" ,;:-–—/.+«»\"'")
    if not text or NO_AUTHOR.match(text):
        return None
    if len(text) > AUTHOR_MAX or len(text.split()) > AUTHOR_MAX_WORDS:
        first = re.split(r"\s*[;,/]\s*", text)[0].strip(" .")
        text = LEAD.sub("", first)
    if not text or NO_AUTHOR.match(text) or len(text) > AUTHOR_MAX or len(text.split()) > AUTHOR_MAX_WORDS:
        return None
    if not re.search(r"[^\W\d_]{2}", text):  # «???», «1987»
        return None
    if re.search(r"(?:^|\s)[A-ZА-ЯЁ]$", text):  # «Чурилов Д. А» → «Чурилов Д. А.»
        text += "."
    return text


# S3-FINAL P1-04 (5.9 §3): an area photo is one photograph of a street, square or embankment, never a collage,
# montage, map, flag, coat of arms, diagram or a very wide panorama, and at least 800 px wide.
AREA_MIN_WIDTH = 800
AREA_MAX_ASPECT = 2.5
AREA_MIMES = ("image/jpeg", "image/tiff", "image/webp")
NOT_AREA = re.compile(
    r"collage|montage|коллаж|монтаж|mosaic|composite|\bmaps?\b|\bkarta\b|карта|схема|\bplan\b|\bflags?\b|флаг"
    r"|coats? of arms|\bcoa\b|герб|emblem|эмблем|\blogos?\b|логотип|diagram|диаграмм|\bseals?\b|locator|location map"
    r"|\bstamps?\b|марк[аи] почт|postage|banknote|coin|монет|\bsvg\b|\.svg$|\.png$|\.gif$",
    re.I,
)

# A category says what the file IS («Montages of Ufa», «Flags of …», «Coats of arms of …»), not what is in it
# («Photographs of flags of Russia in …», «Flag tower (Peter & Paul Fortress)» stay allowed).
CAT_NOT_AREA = re.compile(
    r"collage|montage|коллаж|монтаж|^(?:flags?|coats? of arms|maps?|logos?|diagrams?|locator maps?|seals?"
    r"|emblems?|gerbs?)(?:\s+(?:of|in)\b|$)",
    re.I,
)


def area_ok(file: str, meta: dict[str, Any] | None) -> bool:
    """May this Commons file be shown as «Фото района»? File name, categories, MIME type and size decide."""
    if NOT_AREA.search(file.replace("_", " ")):
        return False
    if meta is None:
        return True  # no Commons metadata (sandbox sample): the file name rule only
    if any(CAT_NOT_AREA.search(c) for c in meta.get("cats") or []):
        return False
    mime, w, h = meta.get("mime"), meta.get("w"), meta.get("h")
    if mime is not None and mime not in AREA_MIMES:
        return False
    if w is not None and w < AREA_MIN_WIDTH:
        return False
    return not (w and h and w / h > AREA_MAX_ASPECT)


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
    """ryumochnaya (strong spirits, shots) > craft (brewery, craft beer, tap room) > pub (beer) > bar."""
    if (
        RYUMKA.search(name)
        or tags.get("bar") in ("ryumochnaya", "shot_bar", "shots")
        or tags.get("drink:vodka") == "only"
    ):
        return "ryumochnaya"
    if (
        tags.get("craft") == "brewery"
        or tags.get("microbrewery") == "yes"
        or tags.get("craft_beer") in CRAFT_YES
        or tags.get("drink:craft_beer") in CRAFT_YES
        or CRAFT_NAME.search(name)
    ):
        return "craft"
    if (
        tags.get("amenity") in ("pub", "biergarten")
        or tags.get("drink:beer") in YES
        or tags.get("brewery", "no") != "no"  # the breweries whose beer is on tap («various»)
        or BEER_NAME.search(name)
    ):
        return "pub"
    return "bar"


def bar_cap(population: int) -> int:
    return max(BAR_CAP_MIN, min(BAR_CAP_MAX, population // BAR_CAP_PEOPLE))


def food_cap(population: int) -> int:
    return max(FOOD_CAP_MIN, min(FOOD_CAP_MAX, population // FOOD_CAP_PEOPLE))


FOOD_ORDER = {k: i for i, k in enumerate(("restaurant", "cafe", "food_court", "fast_food"))}


def cuisine(tags: dict[str, str]) -> str | None:
    """OSM `cuisine` («russian;georgian»): lower case, at most CUISINE_MAX characters, whole values only."""
    out: list[str] = []
    for v in str(tags.get("cuisine") or "").lower().split(";"):
        v = v.strip()
        if v and v not in out and len(";".join([*out, v])) <= CUISINE_MAX:
            out.append(v)
    return ";".join(out) or None


def food_rows(
    raw_food: list[dict[str, Any]], town_pos: dict[str, int], towns: list[dict[str, Any]], deny: list[str],
    hours_ok: Any,
) -> list[dict[str, Any]]:
    """Restaurants, cafés, fast food, food courts (CEO 2026-10-29): named, not deny-listed, one row per OSM
    object, capped per town by population. Over the cap, chain fast food goes first, then other chains
    (`brand*` tags), then places without opening hours."""
    by_id: dict[str, dict[str, Any]] = {}
    for f in raw_food:
        tags = f.get("tags") or {}
        name = str(f.get("name") or tags.get("name") or "").strip()
        kind = tags.get("amenity")
        if not name or kind not in FOOD_KINDS or denied(name, deny) or f.get("townQid") not in town_pos:
            continue
        hours = tags.get("opening_hours")
        if hours and hours_ok is not None and not hours_ok(hours):
            hours = None
        chain = any(k in tags for k in BRANDED_TAGS)
        by_id.setdefault(f["osm"], {**f, "name": name, "_kind": kind, "_hours": hours, "_chain": chain})
    grouped: dict[str, list[dict[str, Any]]] = {}
    for f in by_id.values():
        grouped.setdefault(f["townQid"], []).append(f)
    rows = []
    for qid in sorted(grouped, key=lambda q: town_pos[q]):
        lst = sorted(
            grouped[qid],
            key=lambda f: (
                f["_chain"] and f["_kind"] == "fast_food",
                f["_chain"],
                f["_hours"] is None,
                FOOD_ORDER[f["_kind"]],
                f["osm"],
            ),
        )
        for f in lst[: food_cap(int(towns[town_pos[qid]].get("population") or 0))]:
            rows.append(
                {
                    "id": f["osm"],
                    "name": tidy(f["name"]) or f["name"],
                    "kind": FOOD_KINDS.index(f["_kind"]),
                    "lat": to_coord(f["lat"]),
                    "lon": to_coord(f["lon"]),
                    "town": town_pos[qid],
                    "hours": f["_hours"],
                    "cuisine": cuisine(f.get("tags") or {}),
                }
            )
    return rows


def poi_cap(population: int, tourist: bool) -> int:
    for threshold, cap in POI_CAP:
        if population >= threshold:
            return cap
    return POI_CAP_TOURIST if tourist else POI_CAP_OTHER


def build(
    raw_dir: Path, version: str = "dev", built_at: str = "", hours_ok: Any = None
) -> dict[str, dict[str, Any]]:
    """The documents (`meta`, `towns`, `pois`, `bars`, `food`) from the raw directory."""
    deny = denylist()
    tz = {code: zone for code, zone in read_tsv(HERE / "region_tz.tsv")}
    overrides = {qid_or_name: (gen, prep) for qid_or_name, gen, prep in read_tsv(HERE / "name_overrides.tsv")}
    raw_towns = load_json(raw_dir / "towns.json", [])
    raw_pois = load_json(raw_dir / "pois.json", [])
    raw_bars = load_json(raw_dir / "bars.json", [])
    raw_food = load_json(raw_dir / "food.json", [])
    credits_in = load_json(raw_dir / "credits.json", {})
    forms = load_json(raw_dir / "forms.json", {})
    sources = load_json(raw_dir / "sources.json", {})
    ex = Extras.load(raw_dir)  # Sprint 4 extras (data-extras.yml); empty when absent
    credits_in = {**credits_in, **ex.credits}

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

    # ---- credits (only free files keep their image; GFDL-only files are dropped too, R-10)
    credit_list: list[dict[str, Any]] = []
    credit_idx: dict[tuple[Any, ...], int] = {}

    def image_and_credit(file: str | None) -> tuple[str | None, int | None]:
        if not file:
            return None, None
        c = credits_in.get(file)
        if c is None:
            return file, None  # unknown credits: shown as «Фото: Wikimedia Commons»
        if not c.get("free", True) or gfdl_only(c.get("licence")):
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

    # ---- POIs: kind, nearest town among the towns that found it, deny-list, ADR-0015 §2 excludes, caps
    town_names = {str(t["name"]).strip().casefold() for t in towns}
    by_name: dict[str, list[tuple[float, float]]] = {}
    for t in towns:
        by_name.setdefault(str(t["name"]).strip().casefold(), []).append((t["lat"], t["lon"]))
    osm_ix = OsmIndex(ex.osm)
    all_meta = {**load_json(raw_dir / "photo_meta.json", {}), **ex.photo_meta}
    stats: dict[str, int] = {}
    pois_by_qid: dict[str, dict[str, Any]] = {}
    for r in raw_pois:
        kind = poi_kind(r.get("roots", []))
        if kind is None or not r.get("name") or denied(r["name"], deny) or r.get("townQid") not in town_pos:
            continue
        kind = refine_kind(kind, r, ex)
        why = excluded(r, kind, ex, town_names)
        if why is not None:
            stats[why] = stats.get(why, 0) + 1
            continue
        town = towns[town_pos[r["townQid"]]]
        d = haversine_km((r["lat"], r["lon"]), (town["lat"], town["lon"]))
        if misplaced(r, by_name):
            stats["misplaced"] = stats.get("misplaced", 0) + 1
            continue
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

    def enriched(r: dict[str, Any], town: dict[str, Any]) -> dict[str, Any]:
        osm = osm_ix.match(r["qid"], r["name"], r["lat"], r["lon"])
        tags = osm["tags"] if osm else {}
        image, credit = image_and_credit(r.get("image"))
        src = "p18" if image else None
        for cand, s_ in (
            ((ex.wiki.get(r["qid"]) or {}).get("image"), "wikipedia"),
            (commons_tag(tags), "osm"),
            (geosearch_pick(r["name"], ex.geosearch.get(r["qid"], []), all_meta), "geosearch"),
        ):
            if image is None and cand and cand in credits_in:
                image, credit = image_and_credit(cand)
                src = s_ if image else None
        extract, extract_src = extract_for(r["qid"], osm, r.get("desc"), ex)
        if extract and denied(extract, deny):
            extract, extract_src = None, None
        hours = tags.get("opening_hours")
        if hours and hours_ok is not None and not hours_ok(hours):
            hours = None
        fee = {"yes": 1, "no": 0}.get(str(tags.get("fee", "")).lower())
        q = quality(
            int(r.get("sitelinks") or 0),
            heritage_level(r, ex.wd.get(r["qid"]) or {}),
            in_voyage(r["qid"], ex),
            osm is not None and osm_is_tourism(tags),
            image is not None,
            extract is not None,
            r["_kind"],
        )
        desc = r.get("desc")
        return {
            "id": r["qid"],
            "name": tidy(poi_name(r["name"], town["name"])),
            "desc": tidy(desc[:DESC_MAX]) if desc else None,
            "kind": POI_KINDS.index(r["_kind"]),
            "lat": to_coord(r["lat"]),
            "lon": to_coord(r["lon"]),
            "town": town_pos[r["townQid"]],
            "sitelinks": int(r.get("sitelinks") or 0),
            "heritage": 1 if r.get("heritage") else 0,
            "image": image,
            "credit": credit,
            "quality": round(q * 100),
            "extract": extract,
            "extractSrc": extract_src,
            "hours": hours,
            "fee": fee,
            "website": website(tags, deny),
            "level": card_level(image is not None, extract_src, hours is not None),
            "imageSrc": src,
        }

    poi_rows = []
    for qid in sorted(grouped, key=lambda q: town_pos[q]):
        town = towns[town_pos[qid]]
        rows = [enriched(r, town) for r in grouped[qid]]
        rows = [x for x in rows if x["quality"] >= MIN_SHIP_QUALITY * 100]
        rows.sort(key=lambda x: (-x["quality"], -x["sitelinks"], x["id"]))
        poi_rows.extend(rows[: poi_cap(int(town.get("population") or 0), qid in tourist)])
    shipped = {x["id"] for x in poi_rows}
    poi_rows.extend(
        osm_rows(
            ex,
            towns,
            town_pos,
            shipped,
            {r["qid"] for r in raw_pois},
            image_and_credit,
            all_meta,
            hours_ok,
            deny,
        )
    )
    stats["shipped"] = len(poi_rows)

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
            bars_grouped[qid], key=lambda b: (b["_kind"] == "bar", b["_hours"] is None, b["_kind"], b["osm"])
        )
        for b in lst[: bar_cap(int(towns[town_pos[qid]].get("population") or 0))]:
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
    # area photos (5.9 §3): the files that may NOT stand for a town's area on a hotel card
    photo_meta = load_json(raw_dir / "photo_meta.json", {})
    used = {r["image"] for r in town_rows + poi_rows if r.get("image")} | {
        v["image"] for v in meta_links.values() if v.get("image")
    }
    area_block = sorted(f for f in used if not area_ok(f, photo_meta.get(f)))
    meta = {
        "v": FORMAT_VERSION,
        "version": version,
        "builtAt": built_at,
        "licence": licence_block(version),
        "regions": [{"code": c, "nameRu": region_names[c], "tz": tz[c]} for c in regions_sorted],
        "poiKinds": list(POI_KINDS),
        "barKinds": list(BAR_KINDS),
        "foodKinds": list(FOOD_KINDS),
        "credits": credit_list,
        "links": meta_links,
        "areaBlock": area_block,
        "areaChecked": bool(photo_meta),
        "sources": sources,
        "parking": parking_meta(ex.parking, poi_rows),
        "buildStats": stats,
    }
    return {
        "meta": meta,
        "towns": encode_table(town_rows, TOWN_COLS),
        "pois": encode_table(poi_rows, POI_COLS + POI_OPT_COLS),
        "bars": encode_table(bar_rows, BAR_COLS),
        "food": encode_table(food_rows(raw_food, town_pos, towns, deny, hours_ok), FOOD_COLS),
    }


MIN_SHIP_QUALITY = 0.25  # ADR-0015 §2: below the walk threshold a POI is not shipped
# M9: an OSM-only POI needs a photo or a text on top of its tourism tag (a bare «Паровоз», «Свиное рыло»
# at 0.25 is not worth a stop) — and the catalogue loads faster with ~40 % fewer rows
MIN_SHIP_QUALITY_OSM = 0.30
PARKING_NEAR_KM = 1.5


def commons_tag(tags: dict[str, str]) -> str | None:
    from fetch_extras import commons_name

    return commons_name(tags.get("wikimedia_commons")) or commons_name(tags.get("image"))


def osm_rows(
    ex: Extras,
    towns: list[dict[str, Any]],
    town_pos: dict[str, int],
    shipped: set[str],
    wikidata_ids: set[str],
    image_and_credit: Any,
    meta: dict[str, dict[str, Any]],
    hours_ok: Any,
    deny: list[str],
) -> list[dict[str, Any]]:
    """OSM-only POIs (ADR-0015 §2 kinds: nature, parks, zoos, theatres, interactive, playgrounds, viewpoints,
    attractions): the nearest town within OSM_RADIUS_KM (playgrounds within PLAYGROUND_KM), capped per town."""
    grid: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for t in towns:
        grid.setdefault((int(t["lat"] // 0.5), int(t["lon"] // 0.5)), []).append(t)
    per_town: dict[str, list[dict[str, Any]]] = {}
    for o in ex.osm:
        tags = o["tags"]
        if tags.get("wikidata") in wikidata_ids or tags.get("wikidata") in shipped:
            continue
        kind = osm_kind(tags)
        if kind is None:
            continue
        name = tags.get("name") or ("Детская площадка" if kind == "playground" else None)
        if not name or denied(name, deny) or not osm_name_ok(name, kind, tags):
            continue
        reach = PLAYGROUND_KM if kind == "playground" else OSM_RADIUS_KM
        ci, cj = int(o["lat"] // 0.5), int(o["lon"] // 0.5)
        best = None
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for t in grid.get((ci + di, cj + dj), ()):
                    d = haversine_km((o["lat"], o["lon"]), (t["lat"], t["lon"]))
                    if d <= reach and (best is None or d < best[0]):
                        best = (d, t)
        if best is None:
            continue
        per_town.setdefault(best[1]["qid"], []).append({**o, "_kind": kind, "_name": name, "_d": best[0]})
    out = []
    for qid in sorted(per_town, key=lambda q: town_pos[q]):
        lst = per_town[qid]
        # named playgrounds first («Сказка» before a bare «Детская площадка»), then the nearest to the town
        play = sorted(
            [x for x in lst if x["_kind"] == "playground"],
            key=lambda x: (x["_name"] == "Детская площадка", x["_d"], x["osm"]),
        )
        named = [x for x in lst if x["_kind"] != "playground"]
        rows = []
        for x in named + play[:PLAYGROUNDS_PER_TOWN]:
            tags = x["tags"]
            cand = commons_tag(tags) or geosearch_pick(x["_name"], ex.geosearch.get(x["osm"], []), meta)
            image, credit = image_and_credit(cand) if cand else (None, None)
            extract, src = extract_for(x["osm"], x, None, ex)
            if extract and denied(extract, deny):
                extract, src = None, None
            hours = tags.get("opening_hours")
            if hours and hours_ok is not None and not hours_ok(hours):
                hours = None
            q = quality(
                0,
                0.0,
                False,
                osm_is_tourism(tags) or x["_kind"] == "playground",
                image is not None,
                extract is not None,
                x["_kind"],
            )
            rows.append(
                {
                    "id": f"osm_{x['osm']}",
                    "name": playground_name(tidy(x["_name"]) or "", towns[town_pos[qid]]),
                    "desc": None,
                    "kind": POI_KINDS.index(x["_kind"]),
                    "lat": to_coord(x["lat"]),
                    "lon": to_coord(x["lon"]),
                    "town": town_pos[qid],
                    "sitelinks": 0,
                    "heritage": 0,
                    "image": image,
                    "credit": credit,
                    "quality": round(q * 100),
                    "extract": extract,
                    "extractSrc": src,
                    "hours": hours,
                    "fee": {"yes": 1, "no": 0}.get(str(tags.get("fee", "")).lower()),
                    "website": website(tags, deny),
                    "level": card_level(image is not None, src, hours is not None),
                    "imageSrc": ("osm" if commons_tag(tags) else "geosearch") if image else None,
                }
            )
        rows = [
            r
            for r in rows
            if r["kind"] == POI_KINDS.index("playground") or r["quality"] >= MIN_SHIP_QUALITY_OSM * 100
        ]
        rows.sort(key=lambda r: (-r["quality"], r["id"]))
        out.extend(rows[: OSM_PER_TOWN + PLAYGROUNDS_PER_TOWN])
    return out


def parking_meta(parking: list[dict[str, Any]], pois: list[dict[str, Any]]) -> dict[str, list[Any]]:
    """Paid OSM parking within PARKING_NEAR_KM of a shipped POI (ADR-0015 §4), with ₽/h from `charge`."""
    from verst_planner.parking import charge_per_hour

    cells = {(int(p["lat"] / COORD_SCALE // 0.02), int(p["lon"] / COORD_SCALE // 0.02)) for p in pois}
    lat, lon, rph = [], [], []
    for x in sorted(parking, key=lambda x: x["osm"]):
        c = (int(x["lat"] // 0.02), int(x["lon"] // 0.02))
        if not any((c[0] + a, c[1] + b) in cells for a in (-1, 0, 1) for b in (-1, 0, 1)):
            continue
        lat.append(to_coord(x["lat"]))
        lon.append(to_coord(x["lon"]))
        rph.append(charge_per_hour(x.get("charge")))
    return {"lat": lat, "lon": lon, "rph": rph}


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
        "food": docs["food"]["n"],
        "links": len(docs["meta"]["links"]),
        "credits": len(docs["meta"]["credits"]),
        "bytes": sizes,
        "totalBytes": sum(sizes.values()),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
