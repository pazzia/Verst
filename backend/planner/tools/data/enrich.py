"""Sprint 4 enrichment of the catalogue build (ADR-0015 §2–§4): quality score, hard excludes, kinds from the
Wikidata class tree, descriptions and photos from Wikipedia / Wikivoyage / OSM / Commons geosearch, OSM POIs,
opening hours, fees and paid parking. Pure functions over the raw files of `data-extras.yml`; every input is
optional (a missing file = that source contributes nothing), so the sandbox sample still builds.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ------------------------------------------------------------------------------------------------ inputs


@dataclass
class Extras:
    groups: dict[str, set[str]] = field(default_factory=dict)  # class_tree.json groups
    wd: dict[str, dict[str, Any]] = field(default_factory=dict)  # wd_extra.json
    wiki: dict[str, dict[str, Any]] = field(default_factory=dict)  # wiki.json
    voyage: dict[str, dict[str, Any]] = field(default_factory=dict)  # voyage.json
    osm: list[dict[str, Any]] = field(default_factory=list)  # osm_pois.json
    parking: list[dict[str, Any]] = field(default_factory=list)  # parking.json
    geosearch: dict[str, list[str]] = field(default_factory=dict)  # geosearch.json
    credits: dict[str, dict[str, Any]] = field(default_factory=dict)  # credits_extra.json
    photo_meta: dict[str, dict[str, Any]] = field(default_factory=dict)  # photo_meta_extra.json

    @classmethod
    def load(cls, raw: Path) -> Extras:
        def j(name: str, default: Any) -> Any:
            p = raw / name
            return json.loads(p.read_text("utf-8")) if p.exists() else default

        tree = j("class_tree.json", {})
        return cls(
            groups={g: set(v) for g, v in tree.get("groups", {}).items()},
            wd=j("wd_extra.json", {}),
            wiki=j("wiki.json", {}),
            voyage=j("voyage.json", {}),
            osm=j("osm_pois.json", []),
            parking=j("parking.json", []),
            geosearch=j("geosearch.json", {}),
            credits=j("credits_extra.json", {}),
            photo_meta=j("photo_meta_extra.json", {}),
        )


# ------------------------------------------------------------------------------------- excludes and kinds

NOT_A_SIGHT = re.compile(
    r"(?i)^(школа|гимназия|лицей|детский сад|здание|администрация|больница|поликлиника|стадион|"
    r"спорткомплекс|офис|бизнес-центр|жилой дом|дом (?:№|\d)|дом жилой|жилые дома|жилой комплекс|"
    # parts of an estate or a complex filed one by one: «Ограда с воротами …», «Главный дом (фундамент)»
    r"ограда|ворота|флигель|хозяйственн|служебн|конюш|амбар|каретн|погреб|сарай|людская|главный дом|корпус|"
    r"склад|гараж|котельная|магазин|банк$|банк \(|трансформатор|кафе|ресторан|пивная|клуб$|особняк$|"
    r"особняк,|казарма|административное здание)"
    r"|\b\d+\s*[А-Яа-я]?$"  # an address, not a name: «Амурская улица 201А», «2-я Московская улица 44»
)
RELIGIOUS_KINDS = frozenset({"church"})
KIND_FROM_GROUP = (
    ("theatre", "theatre"),
    ("zoo", "zoo"),
    ("nature", "nature"),
    ("interactive", "interactive"),
)
FEDERAL = re.compile(r"(?i)федерального")
REGIONAL = re.compile(r"(?i)регионального")


def heritage_level(r: dict[str, Any], wd: dict[str, Any]) -> float:
    labels = wd.get("heritage") or []
    if any(FEDERAL.search(x) for x in labels):
        return 1.0
    if any(REGIONAL.search(x) for x in labels):
        return 0.6
    return 0.3 if (labels or r.get("heritage")) else 0.0


def in_voyage(qid: str, ex: Extras) -> bool:
    return qid in ex.voyage or bool((ex.wd.get(qid) or {}).get("ruvoyage"))


def excluded(r: dict[str, Any], kind: str, ex: Extras, town_names: set[str]) -> str | None:
    """Why a Wikidata POI must not ship (ADR-0015 §2), or None."""
    name = str(r.get("name") or "")
    if name.strip().casefold() in town_names:
        return "town_name"  # «Можга», «Зелёный Город»: settlements filed as POIs
    if NOT_A_SIGHT.search(name):
        return "name"
    wd = ex.wd.get(r["qid"]) or {}
    p31 = set(wd.get("p31") or [])
    sitelinks = int(r.get("sitelinks") or 0)
    heritage = heritage_level(r, wd)
    voyage = in_voyage(r["qid"], ex)
    if p31 & ex.groups.get("exclude", set()) and not (voyage or (heritage >= 1.0 and sitelinks >= 10)):
        return "class"
    religious = kind in RELIGIOUS_KINDS or bool(p31 & ex.groups.get("religious", set()))
    if (
        religious
        and kind not in ("monastery", "kremlin")
        and heritage == 0.0
        and sitelinks < 3
        and not voyage
    ):
        return "ordinary_church"
    return None


def refine_kind(kind: str, r: dict[str, Any], ex: Extras) -> str:
    p31 = set((ex.wd.get(r["qid"]) or {}).get("p31") or [])
    for group, k in KIND_FROM_GROUP:
        if p31 & ex.groups.get(group, set()):
            return k
    return kind


# ------------------------------------------------------------------------------------------------ quality

CLASS_BONUS = {
    "kremlin": 1.0,
    "museum": 1.0,
    "zoo": 1.0,
    "theatre": 1.0,
    "park": 1.0,
    "nature": 1.0,
    "viewpoint": 1.0,
    "embankment": 1.0,
    "interactive": 1.0,
    "monastery": 0.6,
    "square": 0.6,
    "attraction": 0.4,
    "church": 0.3,
    "monument": 0.2,
    "playground": 0.3,
}
OSM_TOURISM = frozenset({"attraction", "museum", "viewpoint", "zoo", "theme_park", "gallery", "aquarium"})
OSM_LEISURE = frozenset({"park", "water_park", "nature_reserve"})


def quality(
    sitelinks: int, heritage: float, voyage: bool, osm_tourism: bool, photo: bool, desc: bool, kind: str
) -> float:
    """ADR-0015 §2: q = 0.30·S + 0.15·H + 0.15·V + 0.10·T + 0.10·P + 0.05·D + 0.15·C, in [0, 1]."""
    s = min(1.0, math.log10(1 + sitelinks) / math.log10(61))
    q = (
        0.30 * s
        + 0.15 * heritage
        + 0.15 * voyage
        + 0.10 * osm_tourism
        + 0.10 * photo
        + 0.05 * desc
        + 0.15 * CLASS_BONUS.get(kind, 0.3)
    )
    return round(min(1.0, q), 2)


def osm_is_tourism(tags: dict[str, str]) -> bool:
    return (
        tags.get("tourism") in OSM_TOURISM or tags.get("leisure") in OSM_LEISURE or bool(tags.get("natural"))
    )


# ------------------------------------------------------------------------------------------------- OSM join


class OsmIndex:
    """OSM objects by `wikidata=` tag and on a 0.01° grid (name + 150 m join)."""

    def __init__(self, osm: Iterable[dict[str, Any]]) -> None:
        self.by_qid: dict[str, dict[str, Any]] = {}
        self.grid: dict[tuple[int, int], list[dict[str, Any]]] = {}
        for o in osm:
            q = o["tags"].get("wikidata")
            if q:
                self.by_qid.setdefault(q, o)
            self.grid.setdefault(_cell(o["lat"], o["lon"]), []).append(o)

    def match(self, qid: str, name: str, lat: float, lon: float) -> dict[str, Any] | None:
        if qid in self.by_qid:
            return self.by_qid[qid]
        key = _norm(name)
        ci, cj = _cell(lat, lon)
        best = None
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for o in self.grid.get((ci + di, cj + dj), ()):
                    if _norm(o["tags"].get("name", "")) != key:
                        continue
                    d = _km(lat, lon, o["lat"], o["lon"])
                    if d <= 0.15 and (best is None or d < best[0]):
                        best = (d, o)
        return best[1] if best else None


def _cell(lat: float, lon: float) -> tuple[int, int]:
    return int(lat // 0.01), int(lon // 0.01)


def _norm(s: str) -> str:
    return re.sub(r"[^\w]+", " ", s.casefold().replace("ё", "е")).strip()


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 12742.0 * math.asin(min(1.0, math.sqrt(a)))


# --------------------------------------------------------------------------------------- texts and photos

EXTRACT_MAX = 200
SENTENCE = re.compile(r"^(.+?[.!?])(?:\s|$)")
WORD = re.compile(r"[A-Za-zА-Яа-яЁё]{4,}")


def first_sentence(text: str | None, limit: int = EXTRACT_MAX) -> str | None:
    if not text:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", "", text)).strip()  # drop (dates, transliterations)
    m = SENTENCE.match(t)
    out = m.group(1) if m else t
    if len(out) > limit:
        cut = out[:limit].rsplit(" ", 1)[0].rstrip(",;: ")
        out = cut + "…"
    return out or None


def extract_for(
    qid: str, osm: dict[str, Any] | None, desc: str | None, ex: Extras
) -> tuple[str | None, str | None]:
    """(text, source): ru Wikipedia intro → ru Wikivoyage listing → OSM description → Wikidata description."""
    w = ex.wiki.get(qid) or {}
    if w.get("extract"):
        return first_sentence(w["extract"]), "wikipedia"
    v = ex.voyage.get(qid) or {}
    if v.get("text"):
        return first_sentence(v["text"]), "wikivoyage"
    if osm and osm["tags"].get("description"):
        return first_sentence(osm["tags"]["description"]), "osm"
    if desc:
        return first_sentence(desc, 120), "wikidata"
    return None, None


def geosearch_pick(name: str, files: list[str], meta: dict[str, dict[str, Any]]) -> str | None:
    """A nearby Commons file that names the POI, a JPEG ≥ 800 px wide. The title must share the name's own
    words (two of them when the name has two or more; «Памятник Тарасу Шевченко» is not «улица Шевченко»)
    and its class word when the name has one («Памятник …» needs «памятник» in the title)."""
    bare = re.sub(r"\s*\([^()]*\)\s*$", "", name)  # «Аптекарский сад (Тюмень)»: the town is not the place
    stems = {_stem(w) for w in WORD.findall(bare)}
    generic = {_stem(w) for w in GENERIC_WORDS}
    own, cls = stems - generic, stems & generic
    if not own:
        return None
    need = min(2, len(own))
    for f in files[:3]:
        m = meta.get(f) or {}
        if m.get("mime") not in (None, "image/jpeg") or (m.get("w") or 800) < 800:
            continue
        title = {_stem(w) for w in WORD.findall(f)}
        if len(own & title) >= need and (not cls or cls & title):
            return f
    return None


# words that name a class, not the place: a nearby «Церковь …» photo may show another church
GENERIC_WORDS = frozenset(
    (
        "памятник",
        "церковь",
        "храм",
        "собор",
        "часовня",
        "музей",
        "парк",
        "сквер",
        "площадь",
        "улица",
        "дом",
        "усадьба",
        "монастырь",
        "мемориал",
        "здание",
        "имени",
        "святого",
        "святой",
        "успения",
        "троицы",
        "рождества",
        "покрова",
        "воскресения",
        "николая",
        "город",
        "славы",
        "советского",
        "союза",
        "героям",
        "герою",
        "воинам",
        "погибшим",
        "братская",
        "могила",
        "бывший",
        "бывшая",
        "башня",
        "фонтан",
        "стела",
        "бюст",
        "ограда",
        "воротами",
        "главный",
        "chapel",
        "church",
        "museum",
        "monument",
        "park",
    )
)


def _stem(w: str) -> str:
    """Crude Russian stem for title matching: «Ипатьевского» and «Ипатьевский» meet at «ипать»."""
    return w.casefold()[:5]


def card_level(photo: bool, extract_src: str | None, hours: bool) -> int:
    """ADR-0015 §3 card level: 4 photo + encyclopaedic text + hours; 3 photo + text; 2 photo or text; 1 name."""
    text = extract_src is not None
    if photo and extract_src in ("wikipedia", "wikivoyage") and hours:
        return 4
    if photo and text:
        return 3
    return 2 if (photo or text) else 1


# --------------------------------------------------------------------------------------------- OSM POIs

OSM_KIND = (
    (lambda t: t.get("tourism") == "zoo" or t.get("tourism") == "aquarium", "zoo"),
    (lambda t: t.get("amenity") == "theatre", "theatre"),
    (lambda t: t.get("tourism") == "theme_park" or t.get("museum") in ("children", "science"), "interactive"),
    (lambda t: t.get("tourism") in ("museum", "gallery"), "museum"),
    (lambda t: t.get("leisure") == "playground", "playground"),
    (lambda t: t.get("leisure") in ("nature_reserve",) or bool(t.get("natural")), "nature"),
    (lambda t: t.get("leisure") in ("park", "water_park"), "park"),
    (lambda t: t.get("tourism") == "viewpoint", "viewpoint"),
    (lambda t: t.get("historic") in ("castle", "fort"), "kremlin"),
    (lambda t: t.get("historic") in ("monument", "memorial"), "monument"),
    (lambda t: t.get("tourism") == "attraction" or bool(t.get("historic")), "attraction"),
)
OSM_RADIUS_KM = 8.0
PLAYGROUND_KM = 3.0
PLAYGROUNDS_PER_TOWN = 6
OSM_PER_TOWN = 25


def osm_kind(tags: dict[str, str]) -> str | None:
    return next((k for test, k in OSM_KIND if test(tags)), None)


CYRILLIC = re.compile(r"[а-яё]", re.I)
GENERIC_OSM_NAMES = frozenset(
    (
        "набережная",
        "парк",
        "сквер",
        "сад",
        "музей",
        "пляж",
        "озеро",
        "пруд",
        "родник",
        "источник",
        "поляна",
        "горка",
        "скала",
        "сопка",
        "пещера",
        "лес",
        "роща",
        "вид",
        "панорама",
        "смотровая площадка",
        "обзорная площадка",
        "детская площадка",
        "игровая площадка",
        "выставка",
        "водопад",
        "смотровая",
    )
)
NATURE_OK = frozenset(
    {"waterfall", "cave_entrance", "beach", "volcano", "geyser", "arch", "cliff", "hot_spring"}
)


def osm_name_ok(name: str, kind: str, tags: dict[str, str]) -> bool:
    """ADR-0015 §2 for OSM-only POIs: a Russian name that is a name (not «Набережная», «Учебный склон 1»,
    «马占山…»); nature only when it is a sight (waterfall, cave, beach, cliff…, a reserve, or a tourism tag)."""
    if kind == "playground" and name == "Детская площадка":
        return True
    if not CYRILLIC.search(name) or name.strip().casefold() in GENERIC_OSM_NAMES or name[-1:].isdigit():
        return False
    if kind == "nature":
        return (
            tags.get("natural") in NATURE_OK
            or tags.get("leisure") == "nature_reserve"
            or bool(tags.get("tourism"))
            or bool(tags.get("wikipedia"))
        )
    return True


__all__ = [
    "Extras",
    "OsmIndex",
    "card_level",
    "excluded",
    "extract_for",
    "first_sentence",
    "geosearch_pick",
    "heritage_level",
    "in_voyage",
    "osm_is_tourism",
    "osm_kind",
    "osm_name_ok",
    "quality",
    "refine_kind",
]
