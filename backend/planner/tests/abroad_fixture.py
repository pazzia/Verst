"""CEO 29.10: tiny catalogues abroad in the CI format (`abroad/<cc>/catalogue_*.json.gz` with
`meta.country`), written to a temporary folder for the trips-abroad tests.

The real catalogues are built in CI (`bot/data-abroad-<N>`) and are not in the repository. These fixtures use
the same writer (`verst_planner.catalogue.encode_table` / `dump_gz`) and the same columns, with made-up
Wikidata-like ids (Q9xxxxx) and town coordinates of the real cities, so a route has realistic distances.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from verst_planner.catalogue import (
    BAR_COLS,
    FILES,
    FOOD_COLS,
    FOOD_KINDS,
    POI_COLS,
    POI_KINDS,
    TOWN_COLS,
    dump_gz,
    encode_table,
    to_coord,
)

# country: (currency, nameRu, tz, regions [(code, nameRu)], towns [(id, name, lat, lon, pop, region)],
#           pois [(id, name, kind, lat, lon, town, sitelinks)], food [(id, name, kind, lat, lon, town)])
COUNTRIES: dict[str, dict[str, Any]] = {
    "GE": {
        "currency": "GEL",
        "nameRu": "Грузия",
        "tz": "Asia/Tbilisi",
        "regions": [
            ("GE-TB", "Тбилиси"),
            ("GE-MM", "Мцхета-Мтианети"),
            ("GE-SK", "Шида-Картли"),
            ("GE-IM", "Имерети"),
            ("GE-AJ", "Аджария"),
        ],
        "towns": [
            ("Q9100001", "Тбилиси", 41.7151, 44.8271, 1_200_000, "GE-TB"),
            ("Q9100002", "Мцхета", 41.8458, 44.7208, 7_000, "GE-MM"),
            ("Q9100003", "Гори", 41.9842, 44.1158, 48_000, "GE-SK"),
            ("Q9100004", "Кутаиси", 42.2679, 42.6946, 140_000, "GE-IM"),
            ("Q9100005", "Батуми", 41.6168, 41.6367, 170_000, "GE-AJ"),
            ("Q9100006", "Душети", 42.0847, 44.6961, 6_000, "GE-MM"),
        ],
        "pois": [
            ("Q9200001", "Тестовый музей Тбилиси", "museum", 41.6955, 44.8008, "Q9100001", 60),
            ("Q9200002", "Тестовый собор", "church", 41.6970, 44.8090, "Q9100001", 40),
            ("Q9200003", "Тестовый монастырь Мцхеты", "monastery", 41.8420, 44.7210, "Q9100002", 80),
            ("Q9200004", "Тестовая крепость", "kremlin", 41.9860, 44.1100, "Q9100003", 30),
        ],
        "food": [
            ("osm_n9300001", "Тестовая хинкальная", "restaurant", 41.9830, 44.1120, "Q9100003"),
            ("osm_n9300002", "Test Cafe", "cafe", 41.7160, 44.8280, "Q9100001"),
        ],
    },
    "AZ": {
        "currency": "AZN",
        "nameRu": "Азербайджан",
        "tz": "Asia/Baku",
        "regions": [("AZ-BA", "Баку")],
        "towns": [("Q9110001", "Баку", 40.4093, 49.8671, 2_300_000, "AZ-BA")],
        "pois": [],
        "food": [],
    },
    "KZ": {
        "currency": "KZT",
        "nameRu": "Казахстан",
        "tz": "Asia/Almaty",
        "regions": [("KZ-ZAP", "Западно-Казахстанская область"), ("KZ-AKT", "Актюбинская область")],
        "towns": [
            ("Q9130001", "Уральск", 51.2333, 51.3667, 300_000, "KZ-ZAP"),
            ("Q9130002", "Актобе", 50.2839, 57.1670, 500_000, "KZ-AKT"),
        ],
        "pois": [],
        "food": [],
    },
    "BY": {
        "currency": "BYN",
        "nameRu": "Беларусь",
        "tz": "Europe/Minsk",
        "regions": [("BY-HM", "Минск"), ("BY-VI", "Витебская область")],
        "towns": [
            ("Q9120001", "Минск", 53.9023, 27.5619, 2_000_000, "BY-HM"),
            ("Q9120002", "Орша", 54.5153, 30.4053, 100_000, "BY-VI"),
        ],
        "pois": [("Q9220001", "Тестовая ратуша", "attraction", 53.9045, 27.5560, "Q9120001", 30)],
        "food": [],
    },
}


def write_country(root: Path, code: str) -> Path:
    c = COUNTRIES[code]
    folder = root / code.lower()
    folder.mkdir(parents=True, exist_ok=True)
    region_codes = [r[0] for r in c["regions"]]
    meta = {
        "v": 1,
        "version": "test-abroad",
        "builtAt": "2026-10-29",
        "licence": {"copy": "abroad/"},
        "country": {
            "code": code,
            "wikidata": "Q900000",
            "nameRu": c["nameRu"],
            "currency": c["currency"],
            "labelLangs": ["ru", "en"],
        },
        "regions": [{"code": r, "nameRu": n, "tz": c["tz"]} for r, n in c["regions"]],
        "poiKinds": list(POI_KINDS),
        "foodKinds": list(FOOD_KINDS),
        "credits": [],
        "links": {},
        "sources": {},
        "parking": {"lat": [], "lon": [], "rph": []},
    }
    town_ids = [t[0] for t in c["towns"]]
    towns = [
        {
            "id": tid,
            "name": name,
            "gen": None,
            "prep": None,
            "lat": to_coord(lat),
            "lon": to_coord(lon),
            "pop": pop,
            "region": region_codes.index(region),
            "image": None,
            "credit": None,
            "nameLang": "ru",
        }
        for tid, name, lat, lon, pop, region in c["towns"]
    ]
    pois = [
        {
            "id": pid,
            "name": name,
            "desc": None,
            "kind": POI_KINDS.index(kind),
            "lat": to_coord(lat),
            "lon": to_coord(lon),
            "town": town_ids.index(town),
            "sitelinks": sl,
            "heritage": False,
            "image": None,
            "credit": None,
            "quality": 70,
            "level": 2,
        }
        for pid, name, kind, lat, lon, town, sl in c["pois"]
    ]
    food = [
        {
            "id": fid,
            "name": name,
            "kind": FOOD_KINDS.index(kind),
            "lat": to_coord(lat),
            "lon": to_coord(lon),
            "town": town_ids.index(town),
            "hours": None,
            "cuisine": None,
        }
        for fid, name, kind, lat, lon, town in c["food"]
    ]
    docs = {
        "meta": meta,
        "towns": encode_table(towns, (*TOWN_COLS, "nameLang")),
        "pois": encode_table(pois, (*POI_COLS, "quality", "level")),
        "bars": encode_table([], BAR_COLS),
        "food": encode_table(food, FOOD_COLS),
    }
    for key, name in FILES.items():
        (folder / name).write_bytes(dump_gz(docs[key]))
    return folder


def write_abroad(root: Path, codes: tuple[str, ...] = ("GE", "AZ", "BY", "KZ")) -> Path:
    for code in codes:
        write_country(root, code)
    return root


__all__ = ["COUNTRIES", "write_abroad", "write_country"]
