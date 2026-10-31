"""Generator for backend/planner/fixtures/worlds/*.json (DEV-008).

All coordinates, edge lengths, prices and places are hand-chosen here; the script only lays out
regularly spaced roadside POIs (fuel, rest, cafes) along the hand-made chains and writes the JSON.
"""

import itertools
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/worlds/ (HYG-02), also under runpy

OUT = Path(__file__).resolve().parent.parent / "fixtures" / "worlds"
AS_OF = "2026-10-01"
VERIFIED = "2026-09-15"


def hav(a, b):
    r = 6371.0088
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = p2 - p1
    dl = math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


# =====================================================================================================
# central_russia_v1
# =====================================================================================================

from worlds import extras, food, lodgings, sights  # noqa: E402
from worlds.central_russia_geo import CHAINS, EDGES, NAME_GEN, NODES, REGIONS, TOWNS  # noqa: E402

EDGE_KM = {frozenset((a, b)): km for a, b, km, *_ in EDGES}
EDGE_REF = {frozenset((a, b)): ref for a, b, _k, _s, _c, ref, _t in EDGES}


def chain_anchor(chain, km, lateral):
    """Edge anchor at cumulative `km` along a chain (direction of the chain)."""
    nodes = CHAINS[chain]
    acc = 0.0
    for a, b in itertools.pairwise(nodes):
        e = EDGE_KM[frozenset((a, b))]
        if km <= acc + e:
            return {"edge": [a, b], "km": round(km - acc, 3), "lateralKm": lateral}
        acc += e
    raise ValueError(f"{chain}: km {km} beyond {acc}")


def chain_len(chain):
    nodes = CHAINS[chain]
    return sum(EDGE_KM[frozenset((a, b))] for a, b in itertools.pairwise(nodes))


def ref_at(chain, km):
    a = chain_anchor(chain, km, 0)
    return EDGE_REF[frozenset(a["edge"])]


places = []


def add(pid, ptype, name, anchor, **kw):
    d = {"id": pid, "type": ptype, "nameRu": name, "anchor": anchor}
    d.update(kw)
    d.setdefault("tags", [])
    d.setdefault("rating", 4.0)
    d.setdefault("source", "curated")
    d.setdefault("verifiedAt", VERIFIED)
    places.append(d)


def node(n, dx=0.0, dy=0.0):
    return {"node": n, "dxKm": dx, "dyKm": dy}


# hand-placed places (tools/worlds/*.py), in their original order
lodgings.apply(add, node)
sights.apply(add, node, chain_anchor)
food.apply(add, node)
extras.apply(add, node)

# ------------------------------------------------------------------ roadside POIs laid out along chains
# Release review P0-1: no real brand anywhere in the mock build — fuel stops are neutral «АЗС, <road>, <km> км».
FUEL_LABEL = "АЗС"


def roadside(
    chain,
    fuel_every,
    rest_every,
    cafe_every,
    fuel_offset,
    rest_offset,
    cafe_offset,
    code,
    cafe_at_fuel=True,
    rest_playground=False,
    lateral=0.3,
    skip_fuel=(),
    extra_fuel=(),
):
    length = chain_len(chain)
    i = 0
    km = fuel_offset
    kms = []
    while km < length - 5:
        if not any(lo <= km <= hi for lo, hi in skip_fuel):
            kms.append(km)
        km += fuel_every
    kms.extend(extra_fuel)
    for km in sorted(kms):
        tags = ["24h"] if i % 2 == 0 else ["wc"]
        if cafe_at_fuel and i % 3 == 1:
            tags.append("cafe_at_fuel")
        if i % 4 == 0:
            tags.append("wc")
        add(
            f"pl_{code}_fuel_{int(km):03d}",
            "fuel",
            f"{FUEL_LABEL}, {ref_at(chain, km)}, {int(km)} км",
            chain_anchor(chain, km, lateral if i % 2 == 0 else -lateral),
            tags=sorted(set(tags)),
            rating=round(3.6 + (i % 5) * 0.2, 1),
        )
        i += 1
    j = 0
    km = rest_offset
    while km < length - 5:
        tags = ["wc"]
        if rest_playground or j % 2 == 0:
            tags.append("playground")
        if j % 2 == 1:
            tags.append("walk")
        if j % 3 == 2:
            tags.append("view")
        add(
            f"pl_{code}_rest_{int(km):03d}",
            "rest",
            f"Площадка отдыха, {ref_at(chain, km)}, {int(km)} км",
            chain_anchor(chain, km, -lateral if j % 2 == 0 else lateral),
            tags=sorted(set(tags)),
            rating=round(3.5 + (j % 4) * 0.2, 1),
        )
        j += 1
        km += rest_every
    k = 0
    km = cafe_offset
    names = ["Придорожное", "У дороги", "Привал", "Обжорка", "Домашняя кухня", "Блинная", "Ямщик"]
    while cafe_every and km < length - 5:
        tags = ["parking"]
        if k % 2 == 0:
            tags.append("kids_menu")
        add(
            f"pl_{code}_cafe_{int(km):03d}",
            "food",
            f"Кафе «{names[k % len(names)]}», {ref_at(chain, km)}",
            chain_anchor(chain, km, lateral),
            tags=sorted(set(tags)),
            avgCheckRub=500 + (k % 4) * 100,
            rating=round(3.8 + (k % 4) * 0.15, 2),
            openingHours="Mo-Su 08:00-22:00" if k % 3 else "24/7",
        )
        k += 1
        km += cafe_every


roadside("M8", 32, 45, 0, 22, 40, 0, "m8")
roadside("GR", 38, 45, 60, 25, 30, 40, "gr")
roadside("M7W", 35, 45, 70, 30, 35, 60, "m7w")
roadside("M7E", 40, 45, 55, 20, 30, 25, "m7e")
roadside("M12", 45, 50, 60, 40, 30, 55, "m12", lateral=0.4)
# М-4/Р-22: no coffee at fuel on the Moscow–Tambov stretch (family trips pick playgrounds), rest every 35 km;
# the Tambov approach (G03 evening window 427–467) has the station at km 457.
roadside(
    "M4R22",
    40,
    35,
    50,
    25,
    20,
    45,
    "r22",
    cafe_at_fuel=False,
    rest_playground=True,
    skip_fuel=[(405, 470)],
    extra_fuel=[457],
)
roadside("M2", 35, 40, 0, 20, 30, 0, "m2")

# ------------------------------------------------------------------ region prices
PRICES = {
    "RU": ("61.50", "57.00", "70.50"),
    "RU-MOW": ("62.50", "57.90", "71.20"),
    "RU-MOS": ("61.80", "57.30", "70.80"),
    "RU-YAR": ("61.90", "57.40", "70.60"),
    "RU-KOS": ("62.20", "57.70", "70.90"),
    "RU-IVA": ("61.60", "57.10", "70.40"),
    "RU-VLA": ("61.40", "56.90", "70.30"),
    "RU-NIZ": ("60.90", "56.40", "69.80"),
    "RU-CU": ("59.80", "55.60", "68.90"),
    "RU-TA": ("58.90", "54.90", "67.80"),
    "RU-TUL": ("61.70", "57.20", "70.70"),
    "RU-RYA": ("61.20", "56.80", "70.10"),
    "RU-LIP": ("60.80", "56.30", "69.60"),
    "RU-TAM": ("60.50", "56.00", "69.40"),
    "RU-VOR": ("61.00", "56.60", "69.90"),
    "RU-VGG": ("61.30", "56.90", "70.20"),
}
region_prices = []
for code, (p95, p92, pdt) in PRICES.items():
    for ft, p in (("ai95", p95), ("ai92", p92), ("dt", pdt)):
        region_prices.append({"region": code, "fuelType": ft, "priceRub": p, "asOf": AS_OF})
# an older September row proves "latest as_of wins"
region_prices.append({"region": "RU-YAR", "fuelType": "ai95", "priceRub": "60.70", "asOf": "2026-09-01"})

# ENG-02: category-1 tariffs in force from 2026-03-02 (tools/tolls/tariffs-2026-draft.json; search snippets, NOT
# verified on the operators' sites). М-12: Москва — Владимир 1 737 and Владимир — Арзамас 1 713 are published;
# Арзамас — Казань 2 397 is split over the two fixture edges by length (250 : 144). No night or weekend tariff is
# published for М-12, so night = day. М-4: the ПВП at km 71 charges 310 weekdays / 400 Fri–Sun for km 21–93.
TOLL_AS_OF = "2026-03-02"
TOLLS = [
    {
        "id": "ts_m12_1",
        "roadRef": "М-12",
        "nameRu": "М-12 Москва — Владимир",
        "edge": ["M12_MKAD", "M12_BOG"],
        "fromKm": 0,
        "toKm": 182,
        "tariffDayRub": "1737",
        "tariffNightRub": "1737",
        "asOf": TOLL_AS_OF,
    },
    {
        "id": "ts_m12_2",
        "roadRef": "М-12",
        "nameRu": "М-12 Владимир — Нижний Новгород",
        "edge": ["M12_BOG", "M12_DZE"],
        "fromKm": 0,
        "toKm": 196,
        "tariffDayRub": "1713",
        "tariffNightRub": "1713",
        "asOf": TOLL_AS_OF,
    },
    {
        "id": "ts_m12_3",
        "roadRef": "М-12",
        "nameRu": "М-12 Нижний Новгород — Чебоксары",
        "edge": ["M12_DZE", "M12_CU"],
        "fromKm": 0,
        "toKm": 250,
        "tariffDayRub": "1521",
        "tariffNightRub": "1521",
        "asOf": TOLL_AS_OF,
    },
    {
        "id": "ts_m12_4",
        "roadRef": "М-12",
        "nameRu": "М-12 Чебоксары — Казань",
        "edge": ["M12_CU", "KAZ"],
        "fromKm": 0,
        "toKm": 144,
        "tariffDayRub": "876",
        "tariffNightRub": "876",
        "asOf": TOLL_AS_OF,
    },
    {
        "id": "ts_m4_1",
        "roadRef": "М-4",
        "nameRu": "М-4 Москва — Чекаевка (ПВП км 71)",
        "edge": ["DOM", "KSH"],
        "fromKm": 0,
        "toKm": 56,
        "tariffDayRub": "310",
        "tariffNightRub": "310",
        "tariffWeekendRub": "400",
        "asOf": TOLL_AS_OF,
    },
]

READY = [
    {
        "id": "rr_golden_ring",
        "hubTownId": "t_moscow",
        "titleRu": "Золотое кольцо",
        "subtitleRu": "3 дня · 8 городов · по кругу",
        "kmTotal": 745,
        "kmSign": 745,
        "ring": "long",
        "roundTrip": True,
        "daysMin": 3,
        "daysMax": 4,
        "tags": ["history", "family"],
        "coverKey": "golden_ring",
        "sort": 10,
        "points": [
            {"seq": 1, "role": "via", "townId": "t_sergiev_posad"},
            {"seq": 2, "role": "stop", "placeId": "pl_sps_lavra"},
            {"seq": 3, "role": "via", "townId": "t_pereslavl"},
            {"seq": 4, "role": "via", "townId": "t_rostov"},
            {"seq": 5, "role": "via", "townId": "t_yaroslavl"},
            {"seq": 6, "role": "stop", "placeId": "pl_kos_ipatiev"},
            {"seq": 7, "role": "via", "townId": "t_kostroma"},
            {"seq": 8, "role": "via", "townId": "t_ivanovo"},
            {"seq": 9, "role": "via", "townId": "t_suzdal"},
            {"seq": 10, "role": "via", "townId": "t_vladimir"},
        ],
        "suggestedNights": ["t_yaroslavl", "t_suzdal"],
    },
    {
        "id": "rr_yaroslavl",
        "hubTownId": "t_moscow",
        "titleRu": "Ярославль",
        "subtitleRu": "2 дня · по М-8",
        "kmTotal": 526,
        "kmSign": 263,
        "ring": "weekend",
        "roundTrip": True,
        "daysMin": 2,
        "daysMax": 2,
        "tags": ["weekend"],
        "coverKey": "yaroslavl",
        "sort": 20,
        "points": [
            {"seq": 1, "role": "via", "townId": "t_rostov"},
            {"seq": 2, "role": "via", "townId": "t_yaroslavl"},
        ],
        "suggestedNights": ["t_yaroslavl"],
    },
    {
        "id": "rr_tula_yasnaya",
        "hubTownId": "t_moscow",
        "titleRu": "Тула · Ясная Поляна",
        "subtitleRu": "2 дня · Толстой и пряники",
        "kmTotal": 414,
        "kmSign": 207,
        "ring": "weekend",
        "roundTrip": True,
        "daysMin": 2,
        "daysMax": 2,
        "tags": ["weekend", "family"],
        "coverKey": "tula",
        "sort": 30,
        "points": [
            {"seq": 1, "role": "via", "townId": "t_tula"},
            {"seq": 2, "role": "stop", "placeId": "pl_tul_yasnaya"},
            {"seq": 3, "role": "via", "townId": "t_shchekino"},
        ],
        "suggestedNights": ["t_tula"],
    },
    {
        # ADR-0011 lever 5: the hidden 2-day variant of «Золотое кольцо» (never listed by itself)
        "id": "rr_golden_ring_short",
        "parentId": "rr_golden_ring",
        "hubTownId": "t_moscow",
        "titleRu": "Золотое кольцо · коротко",
        "subtitleRu": "2 дня · Сергиев Посад, Переславль, Ростов, Ярославль",
        "kmTotal": 530,
        "kmSign": 265,
        "ring": "weekend",
        "roundTrip": True,
        "daysMin": 2,
        "daysMax": 2,
        "tags": ["history", "family"],
        "coverKey": "golden_ring",
        "sort": 11,
        "points": [
            {"seq": 1, "role": "via", "townId": "t_sergiev_posad"},
            {"seq": 2, "role": "stop", "placeId": "pl_sps_lavra"},
            {"seq": 3, "role": "via", "townId": "t_pereslavl"},
            {"seq": 4, "role": "via", "townId": "t_rostov"},
            {"seq": 5, "role": "via", "townId": "t_yaroslavl"},
        ],
        "suggestedNights": ["t_yaroslavl"],
    },
]


def check_edges(nodes, edges):
    for a, b, km, *_ in edges:
        h = hav(nodes[a][:2], nodes[b][:2])
        if km < 0.95 * h:
            sys.exit(f"edge {a}-{b}: {km} < 0.95 x {h:.1f}")


GENERATED = {}  # name → file text; with VERST_GEN_IN_MEMORY=1 nothing is written (A§16.10 test)


def write(name, data):
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    GENERATED[name] = text
    if os.environ.get("VERST_GEN_IN_MEMORY"):
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(text, encoding="utf-8")
    print(
        name,
        "places",
        len(data["places"]),
        "towns",
        len(data["towns"]),
        "nodes",
        len(data["nodes"]),
        "edges",
        len(data["edges"]),
    )


check_edges(NODES, EDGES)
central = {
    "id": "central_russia_v1",
    "asOf": AS_OF,
    "regions": [{"code": c, "nameRu": n, "tz": tz} for c, n, tz in REGIONS],
    "nodes": [{"id": k, "lat": v[0], "lon": v[1], "region": v[2]} for k, v in NODES.items()],
    "edges": [
        {"from": a, "to": b, "km": km, "speedKmh": s, "roadClass": c, "ref": r, "toll": t}
        for a, b, km, s, c, r, t in EDGES
    ],
    "towns": [
        {
            "id": i,
            "nameRu": n,
            "namePrepRu": p,
            "nameGenRu": NAME_GEN[i],
            "node": nd,
            "population": pop,
            "quality": q,
            "eveningWalk": ew,
        }
        for i, n, p, nd, pop, q, ew in TOWNS
    ],
    "places": places,
    "regionPrices": region_prices,
    "tollSegments": TOLLS,
    "readyRoutes": READY,
    "defaults": {
        "foodCheckByPopulation": [[1000000, 900], [100000, 700], [0, 550]],
        "lodgingNightByPopulation": [[1000000, 7000], [100000, 5000], [0, 4000]],
    },
}
write("central_russia_v1", central)

# =====================================================================================================
# edge_cases_v1 — «Тестовая область», synthetic straight corridors
# =====================================================================================================
LAT0, LON0 = 58.0, 50.0
DLON_100 = 100 / (111.320 * math.cos(math.radians(LAT0)))  # 100 km east at lat 58
DLAT_100 = 100 / 110.574
places = []
e_nodes = {}
for k in range(7):  # main corridor: Тестовск (0) … Конечный (600)
    e_nodes[f"E{k * 100}"] = (LAT0, round(LON0 + k * DLON_100, 5), "RU-TST")
for k in range(1, 5):  # north corridor: Тестовск → Пустошь (450 km)
    e_nodes[f"N{k * 100}"] = (round(LAT0 + k * DLAT_100, 5), LON0, "RU-TST")
e_nodes["N450"] = (round(LAT0 + 4.5 * DLAT_100, 5), LON0, "RU-TST")
e_nodes["BLZ"] = (round(LAT0 - 12 / 110.574, 5), LON0, "RU-TST")  # Ближний, 12 km south
e_nodes["OFF"] = (round(LAT0 - 2.5 / 110.574, 5), round(LON0 + 0.5 * DLON_100, 5), "RU-TST")  # no road

e_edges = []
for k in range(6):
    a, b = f"E{k * 100}", f"E{(k + 1) * 100}"
    e_edges.append(
        (a, b, round(hav(e_nodes[a][:2], e_nodes[b][:2]) * 1.0, 1) + 0.0, 90, "trunk", "Р-999", False)
    )
prev = "E0"
for name in ("N100", "N200", "N300", "N400", "N450"):
    e_edges.append(
        (prev, name, round(hav(e_nodes[prev][:2], e_nodes[name][:2]), 1), 90, "trunk", "Р-998", False)
    )
    prev = name
e_edges.append(("E0", "BLZ", 12, 60, "secondary", None, False))
e_edges = [
    (a, b, max(km, round(hav(e_nodes[a][:2], e_nodes[b][:2]), 1)), s, c, r, t)
    for a, b, km, s, c, r, t in e_edges
]
check_edges(e_nodes, e_edges)
E_KM = {frozenset((a, b)): km for a, b, km, *_ in e_edges}
CHAINS.update({"EW": [f"E{k * 100}" for k in range(7)], "NS": ["E0", "N100", "N200", "N300", "N400", "N450"]})
EDGE_KM.update(E_KM)
EDGE_REF.update({frozenset((a, b)): r for a, b, _k, _s, _c, r, _t in e_edges})

e_towns = [
    ("t_tst_testovsk", "Тестовск", "Тестовске", "E0", 200_000, 2, True),
    ("t_tst_srednii", "Средний", "Среднем", "E200", 40_000, 1, False),
    ("t_tst_seredinsk", "Серединск", "Серединске", "E300", 30_000, 1, False),
    ("t_tst_konechny", "Конечный", "Конечном", "E600", 100_000, 1, False),
    ("t_tst_pustosh", "Пустошь", "Пустоши", "N450", 5_000, 0, False),
    ("t_tst_blizhny", "Ближний", "Ближнем", "BLZ", 8_000, 0, False),
    ("t_tst_glukhovo", "Глухово", "Глухове", "OFF", 1_000, 0, False),
]
# G05: the only lodging in the whole main corridor, not dog-friendly
add(
    "pl_tst_hotel_nodog",
    "lodging",
    "Гостиница «Серединская»",
    node("E300", 0.4, 0.3),
    townId="t_tst_seredinsk",
    tags=["parking", "family_room"],
    priceNightRub=3500,
    rating=4.2,
)
# G12: fixed long-dwell sights for the marathon ready route
add(
    "pl_tst_museum_long",
    "sight",
    "Большой краеведческий музей",
    chain_anchor("EW", 80, 0.2),
    tags=["museum"],
    dwellMin=240,
    ticketAdultRub=200,
    ticketChildRub=100,
    rating=4.4,
)
add(
    "pl_tst_park_long",
    "sight",
    "Парк-усадьба «Долгая»",
    chain_anchor("EW", 160, 0.2),
    tags=["walk", "view", "free_entry"],
    dwellMin=240,
    rating=4.3,
)
add(
    "pl_tst_viewpoint",
    "sight",
    "Смотровая на Тесте",
    chain_anchor("EW", 450, 0.5),
    tags=["view", "free_entry"],
    dwellMin=30,
    rating=4.0,
)
# main corridor roadside: fuel every 40 km, rest every 50 km, cafes every 60 km
for i, km in enumerate(range(30, 600, 40)):
    add(
        f"pl_tst_fuel_{km:03d}",
        "fuel",
        f"АЗС «Тест», Р-999, {km} км",
        chain_anchor("EW", km, 0.2),
        tags=["24h"] if i % 2 else ["wc"],
        rating=3.8,
    )
for i, km in enumerate(range(40, 600, 50)):
    add(
        f"pl_tst_rest_{km:03d}",
        "rest",
        f"Площадка отдыха, Р-999, {km} км",
        chain_anchor("EW", km, -0.2),
        tags=["wc", "walk"] if i % 2 else ["wc"],
        rating=3.6,
    )
for i, km in enumerate(range(55, 600, 60)):
    add(
        f"pl_tst_cafe_{km:03d}",
        "food",
        f"Кафе «Тестовое», Р-999, {km} км",
        chain_anchor("EW", km, 0.2),
        tags=["parking"],
        avgCheckRub=550,
        rating=3.9,
        openingHours="Mo-Su 08:00-22:00",
    )
# north corridor (G11): fuel only at 40, 80 and 420 km → 300+ km with no fuel
for km in (40, 80, 420):
    add(
        f"pl_tst_n_fuel_{km:03d}",
        "fuel",
        f"АЗС «Север», Р-998, {km} км",
        chain_anchor("NS", km, 0.2),
        tags=["24h"],
        rating=3.7,
    )
for km in (60, 160, 260, 360):
    add(
        f"pl_tst_n_rest_{km:03d}",
        "rest",
        f"Площадка отдыха, Р-998, {km} км",
        chain_anchor("NS", km, -0.2),
        tags=["wc"],
        rating=3.5,
    )
for km in (120, 240, 330):
    add(
        f"pl_tst_n_cafe_{km:03d}",
        "food",
        f"Кафе «Северное», Р-998, {km} км",
        chain_anchor("NS", km, 0.2),
        tags=["parking"],
        avgCheckRub=500,
        rating=3.8,
        openingHours="24/7",
    )

edge_world = {
    "id": "edge_cases_v1",
    "asOf": AS_OF,
    "regions": [
        {"code": "RU", "nameRu": "Россия", "tz": "Europe/Moscow"},
        {"code": "RU-TST", "nameRu": "Тестовая область", "tz": "Europe/Moscow"},
    ],
    "nodes": [{"id": k, "lat": v[0], "lon": v[1], "region": v[2]} for k, v in e_nodes.items()],
    "edges": [
        {"from": a, "to": b, "km": km, "speedKmh": s, "roadClass": c, "ref": r, "toll": t}
        for a, b, km, s, c, r, t in e_edges
    ],
    "towns": [
        {
            "id": i,
            "nameRu": n,
            "namePrepRu": p,
            "nameGenRu": NAME_GEN[i],
            "node": nd,
            "population": pop,
            "quality": q,
            "eveningWalk": ew,
        }
        for i, n, p, nd, pop, q, ew in e_towns
    ],
    "places": places,
    "regionPrices": [
        {"region": r, "fuelType": ft, "priceRub": p, "asOf": AS_OF}
        for r in ("RU", "RU-TST")
        for ft, p in (("ai95", "61.00"), ("ai92", "56.50"), ("dt", "70.00"))
    ],
    "tollSegments": [],
    "readyRoutes": [
        {
            "id": "rr_tst_marathon",
            "hubTownId": "t_tst_testovsk",
            "titleRu": "Тестовый марафон",
            "subtitleRu": "1 день · два долгих места",
            "kmTotal": 200,
            "kmSign": 200,
            "ring": "weekend",
            "roundTrip": False,
            "daysMin": 1,
            "daysMax": 1,
            "tags": [],
            "coverKey": None,
            "sort": 10,
            "points": [
                {"seq": 1, "role": "stop", "placeId": "pl_tst_museum_long"},
                {"seq": 2, "role": "stop", "placeId": "pl_tst_park_long"},
                {"seq": 3, "role": "via", "townId": "t_tst_srednii"},
            ],
            "suggestedNights": [],
        }
    ],
    "defaults": {
        "foodCheckByPopulation": [[1000000, 900], [100000, 650], [0, 550]],
        "lodgingNightByPopulation": [[1000000, 6000], [100000, 4500], [0, 3500]],
    },
}
write("edge_cases_v1", edge_world)
