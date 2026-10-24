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

REGIONS = [
    ("RU", "Россия", "Europe/Moscow"),
    ("RU-MOW", "Москва", "Europe/Moscow"),
    ("RU-MOS", "Московская область", "Europe/Moscow"),
    ("RU-YAR", "Ярославская область", "Europe/Moscow"),
    ("RU-KOS", "Костромская область", "Europe/Moscow"),
    ("RU-IVA", "Ивановская область", "Europe/Moscow"),
    ("RU-VLA", "Владимирская область", "Europe/Moscow"),
    ("RU-NIZ", "Нижегородская область", "Europe/Moscow"),
    ("RU-CU", "Чувашская Республика", "Europe/Moscow"),
    ("RU-TA", "Республика Татарстан", "Europe/Moscow"),
    ("RU-TUL", "Тульская область", "Europe/Moscow"),
    ("RU-RYA", "Рязанская область", "Europe/Moscow"),
    ("RU-LIP", "Липецкая область", "Europe/Moscow"),
    ("RU-TAM", "Тамбовская область", "Europe/Moscow"),
    ("RU-VOR", "Воронежская область", "Europe/Moscow"),
    ("RU-VGG", "Волгоградская область", "Europe/Volgograd"),
]

# node id: (lat, lon, region)
NODES = {
    "MSK": (55.7558, 37.6173, "RU-MOW"),
    # М-8
    "PUS": (56.0104, 37.8471, "RU-MOS"),
    "SPS": (56.3153, 38.1358, "RU-MOS"),
    "PRS": (56.7361, 38.8543, "RU-YAR"),
    "RST": (57.1853, 39.4146, "RU-YAR"),
    "YAR": (57.6261, 39.8845, "RU-YAR"),
    # Golden Ring
    "KOS": (57.7677, 40.9264, "RU-KOS"),
    "IVA": (57.0004, 40.9739, "RU-IVA"),
    "SUZ": (56.4197, 40.4434, "RU-VLA"),
    "VLA": (56.1290, 40.4066, "RU-VLA"),
    # М-7 west
    "NOG": (55.8522, 38.4386, "RU-MOS"),
    "POK": (55.9178, 39.1755, "RU-VLA"),
    "PET": (55.9298, 39.4592, "RU-VLA"),
    # М-7 east
    "VYZ": (56.2486, 42.1584, "RU-VLA"),
    "GOR": (56.2020, 42.6926, "RU-VLA"),
    "DZE": (56.2414, 43.4554, "RU-NIZ"),
    "NNV": (56.3269, 44.0059, "RU-NIZ"),
    "KST": (56.1508, 44.1956, "RU-NIZ"),
    "LYS": (56.0270, 45.0353, "RU-NIZ"),
    "VOR": (56.0656, 46.3436, "RU-NIZ"),
    "CHB": (56.1439, 47.2489, "RU-CU"),
    "CIV": (55.8650, 47.4729, "RU-CU"),
    "ZEL": (55.8466, 48.5010, "RU-TA"),
    "KAZ": (55.7963, 49.1088, "RU-TA"),
    # М-12 (motorway; joins the network only in Moscow and Kazan)
    "M12_MKAD": (55.8000, 37.8500, "RU-MOS"),
    "M12_BOG": (56.2000, 40.5500, "RU-VLA"),
    "M12_DZE": (56.1000, 43.4000, "RU-NIZ"),
    "M12_CU": (55.8500, 47.0000, "RU-CU"),
    # М-4 / Р-22
    "DOM": (55.4400, 37.7682, "RU-MOS"),
    "KSH": (54.8337, 38.1517, "RU-MOS"),
    "MIH": (54.2297, 39.0089, "RU-RYA"),
    "SKP": (53.8236, 39.5494, "RU-RYA"),
    "RZH": (53.7067, 40.0517, "RU-RYA"),
    "CHA": (53.2405, 39.9670, "RU-LIP"),
    "MCH": (52.8946, 40.4908, "RU-TAM"),
    "TAM": (52.7212, 41.4523, "RU-TAM"),
    "KOT": (52.5927, 41.5081, "RU-TAM"),
    "BOR": (51.3687, 42.0887, "RU-VOR"),
    "NAN": (50.5296, 42.6666, "RU-VGG"),
    "FRO": (49.7650, 43.6610, "RU-VGG"),
    "VGG": (48.7080, 44.5133, "RU-VGG"),
    # М-2
    "POD": (55.4312, 37.5458, "RU-MOS"),
    "SER": (54.9158, 37.4111, "RU-MOS"),
    "TUL": (54.1931, 37.6173, "RU-TUL"),
    "YAP": (54.0750, 37.5500, "RU-TUL"),
    "SHC": (54.0039, 37.5186, "RU-TUL"),
}

# (from, to, km, speed, class, ref, toll) — km = hand-chosen road distance (±5 % of the real road)
EDGES = [
    # М-8: Москва 0 – Пушкино 33 – Сергиев Посад 72 – Переславль 140 – Ростов 204 – Ярославль 263
    ("MSK", "PUS", 33, 60, "trunk", "М-8", False),
    ("PUS", "SPS", 39, 90, "trunk", "М-8", False),
    ("SPS", "PRS", 68, 80, "trunk", "М-8", False),
    ("PRS", "RST", 64, 80, "trunk", "М-8", False),
    ("RST", "YAR", 59, 80, "trunk", "М-8", False),
    # Golden Ring: Ярославль – Кострома 79 – Иваново 104 – Суздаль 77 – Владимир 35
    ("YAR", "KOS", 79, 70, "primary", "Р-132", False),
    ("KOS", "IVA", 104, 70, "primary", "Р-600", False),
    ("IVA", "SUZ", 77, 70, "primary", "Р-132", False),
    ("SUZ", "VLA", 35, 70, "primary", "Р-132", False),
    # М-7 west: Москва – Ногинск 53 – Покров 102 – Петушки 121 – Владимир 187
    ("MSK", "NOG", 53, 70, "trunk", "М-7", False),
    ("NOG", "POK", 49, 90, "trunk", "М-7", False),
    ("POK", "PET", 19, 90, "trunk", "М-7", False),
    ("PET", "VLA", 66, 80, "trunk", "М-7", False),
    # М-7 east: Владимир – Вязники 114 – Гороховец 35 – Дзержинск 50 – Нижний 38 – Кстово 25 – Лысково 57
    #           – Воротынец 86 – Чебоксары 72 – Цивильск 38 – Зеленодольск 72 – Казань 40
    ("VLA", "VYZ", 114, 80, "trunk", "М-7", False),
    ("VYZ", "GOR", 35, 80, "trunk", "М-7", False),
    ("GOR", "DZE", 50, 80, "trunk", "М-7", False),
    ("DZE", "NNV", 38, 60, "trunk", "М-7", False),
    ("NNV", "KST", 25, 60, "trunk", "М-7", False),
    ("KST", "LYS", 57, 80, "trunk", "М-7", False),
    ("LYS", "VOR", 86, 80, "trunk", "М-7", False),
    ("VOR", "CHB", 72, 80, "trunk", "М-7", False),
    ("CHB", "CIV", 38, 80, "trunk", "М-7", False),
    ("CIV", "ZEL", 72, 90, "trunk", "М-7", False),
    ("ZEL", "KAZ", 40, 70, "trunk", "М-7", False),
    # М-12: 18 + 182 + 196 + 250 + 144 = 790 km
    ("MSK", "M12_MKAD", 18, 60, "motorway", "М-12", False),
    ("M12_MKAD", "M12_BOG", 182, 110, "motorway", "М-12", True),
    ("M12_BOG", "M12_DZE", 196, 110, "motorway", "М-12", True),
    ("M12_DZE", "M12_CU", 250, 110, "motorway", "М-12", True),
    ("M12_CU", "KAZ", 144, 110, "motorway", "М-12", True),
    # М-4: Москва – Домодедово 37 – Кашира 108
    ("MSK", "DOM", 37, 70, "motorway", "М-4", False),
    ("DOM", "KSH", 71, 110, "motorway", "М-4", False),
    # Р-22: Кашира – Михайлов 196 – Скопин 254 – Ряжск 291 – Чаплыгин 344 – Мичуринск 398 – Тамбов 467
    #       – Котовск 483 – Борисоглебск 629 – Новоаннинский 733 – Фролово 846 – Волгоград 980
    ("KSH", "MIH", 88, 90, "trunk", "Р-22", False),
    ("MIH", "SKP", 58, 90, "trunk", "Р-22", False),
    ("SKP", "RZH", 37, 80, "trunk", "Р-22", False),
    ("RZH", "CHA", 53, 90, "trunk", "Р-22", False),
    ("CHA", "MCH", 54, 90, "trunk", "Р-22", False),
    ("MCH", "TAM", 69, 80, "trunk", "Р-22", False),
    ("TAM", "KOT", 16, 80, "trunk", "Р-22", False),
    ("KOT", "BOR", 146, 90, "trunk", "Р-22", False),
    ("BOR", "NAN", 104, 90, "trunk", "Р-22", False),
    ("NAN", "FRO", 113, 90, "trunk", "Р-22", False),
    ("FRO", "VGG", 134, 90, "trunk", "Р-22", False),
    # М-2: Москва – Подольск 40 – Серпухов 100 – Тула 183 – (Ясная Поляна) 198 – Щёкино 207
    ("MSK", "POD", 40, 70, "trunk", "М-2", False),
    ("POD", "SER", 60, 110, "motorway", "М-2", False),
    ("SER", "TUL", 83, 100, "motorway", "М-2", False),
    ("TUL", "YAP", 15, 80, "trunk", "М-2", False),
    ("YAP", "SHC", 9, 80, "trunk", "М-2", False),
]

# id, name, prep, node, population, quality, eveningWalk
TOWNS = [
    ("t_moscow", "Москва", "Москве", "MSK", 13_000_000, 3, True),
    ("t_pushkino", "Пушкино", "Пушкино", "PUS", 110_000, 1, False),
    ("t_sergiev_posad", "Сергиев Посад", "Сергиевом Посаде", "SPS", 100_000, 3, False),
    ("t_pereslavl", "Переславль-Залесский", "Переславле-Залесском", "PRS", 38_000, 3, True),
    ("t_rostov", "Ростов", "Ростове", "RST", 30_000, 3, True),
    ("t_yaroslavl", "Ярославль", "Ярославле", "YAR", 570_000, 3, True),
    ("t_kostroma", "Кострома", "Костроме", "KOS", 270_000, 3, True),
    ("t_ivanovo", "Иваново", "Иванове", "IVA", 360_000, 1, False),
    ("t_suzdal", "Суздаль", "Суздале", "SUZ", 9_000, 3, True),
    ("t_vladimir", "Владимир", "Владимире", "VLA", 350_000, 3, True),
    ("t_noginsk", "Ногинск", "Ногинске", "NOG", 100_000, 1, False),
    ("t_pokrov", "Покров", "Покрове", "POK", 17_000, 1, False),
    ("t_petushki", "Петушки", "Петушках", "PET", 13_000, 0, False),
    ("t_vyazniki", "Вязники", "Вязниках", "VYZ", 35_000, 1, False),
    ("t_gorokhovets", "Гороховец", "Гороховце", "GOR", 12_000, 2, True),
    ("t_dzerzhinsk", "Дзержинск", "Дзержинске", "DZE", 225_000, 1, False),
    ("t_nizhny", "Нижний Новгород", "Нижнем Новгороде", "NNV", 1_200_000, 3, True),
    ("t_kstovo", "Кстово", "Кстове", "KST", 65_000, 0, False),
    ("t_lyskovo", "Лысково", "Лыскове", "LYS", 21_000, 1, False),
    ("t_vorotynets", "Воротынец", "Воротынце", "VOR", 7_000, 0, False),
    ("t_cheboksary", "Чебоксары", "Чебоксарах", "CHB", 500_000, 2, True),
    ("t_tsivilsk", "Цивильск", "Цивильске", "CIV", 13_000, 0, False),
    ("t_zelenodolsk", "Зеленодольск", "Зеленодольске", "ZEL", 100_000, 1, False),
    ("t_kazan", "Казань", "Казани", "KAZ", 1_300_000, 3, True),
    ("t_domodedovo", "Домодедово", "Домодедове", "DOM", 140_000, 0, False),
    ("t_kashira", "Кашира", "Кашире", "KSH", 48_000, 1, False),
    ("t_mikhailov", "Михайлов", "Михайлове", "MIH", 11_000, 1, False),
    ("t_skopin", "Скопин", "Скопине", "SKP", 28_000, 1, False),
    ("t_ryazhsk", "Ряжск", "Ряжске", "RZH", 20_000, 0, False),
    ("t_chaplygin", "Чаплыгин", "Чаплыгине", "CHA", 12_000, 0, False),
    ("t_michurinsk", "Мичуринск", "Мичуринске", "MCH", 90_000, 2, False),
    ("t_tambov", "Тамбов", "Тамбове", "TAM", 290_000, 2, True),
    ("t_kotovsk", "Котовск", "Котовске", "KOT", 29_000, 0, False),
    ("t_borisoglebsk", "Борисоглебск", "Борисоглебске", "BOR", 62_000, 1, False),
    ("t_novoanninsky", "Новоаннинский", "Новоаннинском", "NAN", 17_000, 0, False),
    ("t_frolovo", "Фролово", "Фролове", "FRO", 37_000, 0, False),
    ("t_volgograd", "Волгоград", "Волгограде", "VGG", 1_000_000, 3, True),
    ("t_podolsk", "Подольск", "Подольске", "POD", 300_000, 0, False),
    ("t_serpukhov", "Серпухов", "Серпухове", "SER", 125_000, 2, False),
    ("t_tula", "Тула", "Туле", "TUL", 470_000, 3, True),
    ("t_shchekino", "Щёкино", "Щёкине", "SHC", 55_000, 0, False),
]

# OI-39: genitive town names («из Ярославля»), consistent with the prepositional forms above.
NAME_GEN = {
    "t_moscow": "Москвы",
    "t_pushkino": "Пушкино",
    "t_sergiev_posad": "Сергиева Посада",
    "t_pereslavl": "Переславля-Залесского",
    "t_rostov": "Ростова",
    "t_yaroslavl": "Ярославля",
    "t_kostroma": "Костромы",
    "t_ivanovo": "Иванова",
    "t_suzdal": "Суздаля",
    "t_vladimir": "Владимира",
    "t_noginsk": "Ногинска",
    "t_pokrov": "Покрова",
    "t_petushki": "Петушков",
    "t_vyazniki": "Вязников",
    "t_gorokhovets": "Гороховца",
    "t_dzerzhinsk": "Дзержинска",
    "t_nizhny": "Нижнего Новгорода",
    "t_kstovo": "Кстова",
    "t_lyskovo": "Лыскова",
    "t_vorotynets": "Воротынца",
    "t_cheboksary": "Чебоксар",
    "t_tsivilsk": "Цивильска",
    "t_zelenodolsk": "Зеленодольска",
    "t_kazan": "Казани",
    "t_domodedovo": "Домодедова",
    "t_kashira": "Каширы",
    "t_mikhailov": "Михайлова",
    "t_skopin": "Скопина",
    "t_ryazhsk": "Ряжска",
    "t_chaplygin": "Чаплыгина",
    "t_michurinsk": "Мичуринска",
    "t_tambov": "Тамбова",
    "t_kotovsk": "Котовска",
    "t_borisoglebsk": "Борисоглебска",
    "t_novoanninsky": "Новоаннинского",
    "t_frolovo": "Фролова",
    "t_volgograd": "Волгограда",
    "t_podolsk": "Подольска",
    "t_serpukhov": "Серпухова",
    "t_tula": "Тулы",
    "t_shchekino": "Щёкина",
    "t_tst_testovsk": "Тестовска",
    "t_tst_srednii": "Среднего",
    "t_tst_seredinsk": "Серединска",
    "t_tst_konechny": "Конечного",
    "t_tst_pustosh": "Пустоши",
    "t_tst_blizhny": "Ближнего",
    "t_tst_glukhovo": "Глухова",
}

CHAINS = {
    "M8": ["MSK", "PUS", "SPS", "PRS", "RST", "YAR"],
    "GR": ["YAR", "KOS", "IVA", "SUZ", "VLA"],
    "M7W": ["MSK", "NOG", "POK", "PET", "VLA"],
    "M7E": ["VLA", "VYZ", "GOR", "DZE", "NNV", "KST", "LYS", "VOR", "CHB", "CIV", "ZEL", "KAZ"],
    "M12": ["MSK", "M12_MKAD", "M12_BOG", "M12_DZE", "M12_CU", "KAZ"],
    "M4R22": [
        "MSK",
        "DOM",
        "KSH",
        "MIH",
        "SKP",
        "RZH",
        "CHA",
        "MCH",
        "TAM",
        "KOT",
        "BOR",
        "NAN",
        "FRO",
        "VGG",
    ],
    "M2": ["MSK", "POD", "SER", "TUL", "YAP", "SHC"],
}
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


# ------------------------------------------------------------------ lodgings (hand-placed)
L = "lodging"
# Ярославль: G01 (no filters), G02 (dog + family)
add(
    "pl_yar_hotel_strelka",
    L,
    "У Стрелки, в центре",
    node("YAR", 1.2, 0.6),
    townId="t_yaroslavl",
    tags=["dogs_allowed", "family_room", "parking"],
    priceNightRub=6000,
    rating=4.6,
    partner={"yandexTravelId": "yt_yar_1"},
)
add(
    "pl_yar_hotel_volga",
    L,
    "Волжская набережная",
    node("YAR", 0.8, -0.4),
    townId="t_yaroslavl",
    tags=["dogs_allowed", "family_room"],
    priceNightRub=7000,
    rating=4.5,
    partner={"yandexTravelId": "yt_yar_2"},
)
add(
    "pl_yar_hotel_kotorosl",
    L,
    "Которосль",
    node("YAR", -1.0, -1.2),
    townId="t_yaroslavl",
    tags=["parking"],
    priceNightRub=4800,
    rating=4.2,
)
add(
    "pl_yar_hostel_center",
    L,
    "Хостел «Центральный»",
    node("YAR", 0.4, 0.9),
    townId="t_yaroslavl",
    tags=[],
    priceNightRub=2500,
    rating=3.6,
    breakfastIncluded=False,
)
# Ростов, Переславль, Сергиев Посад (alternatives on М-8)
add(
    "pl_rst_hotel_kremlin",
    L,
    "Гостиница у кремля",
    node("RST", 0.3, 0.2),
    townId="t_rostov",
    tags=["dogs_allowed", "parking"],
    priceNightRub=4500,
    rating=4.4,
)
add(
    "pl_rst_guest_nero",
    L,
    "Гостевой дом «Неро»",
    node("RST", 0.9, -0.5),
    townId="t_rostov",
    tags=["family_room", "parking"],
    priceNightRub=3800,
    rating=4.3,
)
add(
    "pl_prs_hotel_lake",
    L,
    "Отель на Плещеевом",
    node("PRS", -0.6, 0.8),
    townId="t_pereslavl",
    tags=["family_room", "parking", "view"],
    priceNightRub=5200,
    rating=4.5,
)
add(
    "pl_prs_guest_goritsy",
    L,
    "Гостевой дом у Горицкого",
    node("PRS", 1.1, -0.7),
    townId="t_pereslavl",
    tags=["parking"],
    priceNightRub=3900,
    rating=4.1,
)
add(
    "pl_sps_hotel_lavra",
    L,
    "Гостиница у Лавры",
    node("SPS", 0.7, 0.3),
    townId="t_sergiev_posad",
    tags=["parking", "family_room"],
    priceNightRub=5000,
    rating=4.3,
)
add(
    "pl_sps_hotel_posad",
    L,
    "Посадский двор",
    node("SPS", -0.8, 0.5),
    townId="t_sergiev_posad",
    tags=["parking"],
    priceNightRub=4200,
    rating=4.0,
)
# Кострома, Иваново, Суздаль, Владимир
add(
    "pl_kos_hotel_volga",
    L,
    "Волга-отель",
    node("KOS", 0.5, -0.6),
    townId="t_kostroma",
    tags=["parking", "family_room"],
    priceNightRub=5000,
    rating=4.3,
)
add(
    "pl_kos_guest_snegurochka",
    L,
    "Терем Снегурочки",
    node("KOS", -0.9, 0.4),
    townId="t_kostroma",
    tags=["dogs_allowed"],
    priceNightRub=4200,
    rating=4.2,
)
add(
    "pl_iva_hotel_sitets",
    L,
    "Ситец",
    node("IVA", 0.4, 0.3),
    townId="t_ivanovo",
    tags=["parking"],
    priceNightRub=4000,
    rating=4.0,
)
add(
    "pl_iva_hotel_center",
    L,
    "Шереметьевский",
    node("IVA", -0.5, -0.2),
    townId="t_ivanovo",
    tags=["parking", "family_room"],
    priceNightRub=4600,
    rating=4.2,
)
add(
    "pl_suz_hotel_pushkarskaya",
    L,
    "Пушкарская слобода",
    node("SUZ", 0.6, -0.8),
    townId="t_suzdal",
    tags=["dogs_allowed", "family_room", "parking"],
    priceNightRub=6000,
    rating=4.7,
    partner={"yandexTravelId": "yt_suz_1"},
)
add(
    "pl_suz_guest_kamenka",
    L,
    "Гостевой дом у Каменки",
    node("SUZ", -0.4, 0.3),
    townId="t_suzdal",
    tags=["family_room"],
    priceNightRub=4500,
    rating=4.4,
)
add(
    "pl_suz_hotel_nikolaevsky",
    L,
    "Николаевский посад",
    node("SUZ", 0.2, 0.9),
    townId="t_suzdal",
    tags=["parking_guarded"],
    priceNightRub=5500,
    rating=4.5,
)
add(
    "pl_vla_hotel_zolotye",
    L,
    "У Золотых ворот",
    node("VLA", 0.3, 0.2),
    townId="t_vladimir",
    tags=["parking", "dogs_allowed"],
    priceNightRub=5200,
    rating=4.4,
)
add(
    "pl_vla_hotel_klyazma",
    L,
    "Клязьма",
    node("VLA", -1.2, -0.6),
    townId="t_vladimir",
    tags=["parking", "family_room"],
    priceNightRub=4300,
    rating=4.1,
)
# М-7 east
add(
    "pl_dze_hotel_oka",
    L,
    "Ока",
    node("DZE", 0.5, 0.4),
    townId="t_dzerzhinsk",
    tags=["parking"],
    priceNightRub=3600,
    rating=3.8,
)
add(
    "pl_dze_hotel_center",
    L,
    "Центральная",
    node("DZE", -0.4, -0.3),
    townId="t_dzerzhinsk",
    tags=[],
    priceNightRub=3200,
    rating=3.6,
)
add(
    "pl_nnv_hotel_kremlin",
    L,
    "Отель у кремля",
    node("NNV", 0.6, 0.4),
    townId="t_nizhny",
    tags=["parking", "family_room", "dogs_allowed"],
    priceNightRub=6500,
    rating=4.6,
)
add(
    "pl_nnv_hotel_volga",
    L,
    "Волжский откос",
    node("NNV", 1.1, 0.8),
    townId="t_nizhny",
    tags=["parking_guarded", "view"],
    priceNightRub=7200,
    rating=4.7,
)
add(
    "pl_nnv_hotel_pokrovka",
    L,
    "Покровка",
    node("NNV", 0.2, -0.6),
    townId="t_nizhny",
    tags=["parking"],
    priceNightRub=5000,
    rating=4.3,
)
add(
    "pl_nnv_hostel",
    L,
    "Хостел «Набережная»",
    node("NNV", -0.7, 0.2),
    townId="t_nizhny",
    tags=[],
    priceNightRub=2200,
    rating=3.7,
    breakfastIncluded=False,
)
add(
    "pl_chb_hotel_bay",
    L,
    "Залив",
    node("CHB", 0.4, 0.3),
    townId="t_cheboksary",
    tags=["parking", "view"],
    priceNightRub=4800,
    rating=4.4,
)
add(
    "pl_chb_hotel_center",
    L,
    "Чувашия",
    node("CHB", -0.3, -0.4),
    townId="t_cheboksary",
    tags=["parking", "dogs_allowed"],
    priceNightRub=4200,
    rating=4.1,
)
add(
    "pl_kaz_hotel_kremlin",
    L,
    "Кремлёвская",
    node("KAZ", 0.5, 0.6),
    townId="t_kazan",
    tags=["parking_guarded", "family_room"],
    priceNightRub=7500,
    rating=4.7,
)
add(
    "pl_kaz_hotel_bauman",
    L,
    "На Баумана",
    node("KAZ", -0.3, -0.2),
    townId="t_kazan",
    tags=["parking", "dogs_allowed"],
    priceNightRub=6000,
    rating=4.4,
)
# Р-22
add(
    "pl_ksh_hotel_oka",
    L,
    "Приокская",
    node("KSH", 0.5, 0.3),
    townId="t_kashira",
    tags=["parking"],
    priceNightRub=3500,
    rating=3.9,
)
add(
    "pl_ksh_hotel_kolomna",
    L,
    "Каширский двор",
    node("KSH", -0.6, 0.2),
    townId="t_kashira",
    tags=["parking", "family_room"],
    priceNightRub=3900,
    rating=4.0,
)
add(
    "pl_mch_hotel_michurin",
    L,
    "Мичуринская",
    node("MCH", 0.3, 0.2),
    townId="t_michurinsk",
    tags=["parking"],
    priceNightRub=3400,
    rating=3.9,
)
add(
    "pl_mch_hotel_sad",
    L,
    "Яблоневый сад",
    node("MCH", -0.5, 0.4),
    townId="t_michurinsk",
    tags=["parking", "family_room"],
    priceNightRub=3800,
    rating=4.1,
)
# Тамбов: G03 needs dog + family (2 adults + child)
add(
    "pl_tam_hotel_tambov",
    L,
    "Гостиница «Тамбов»",
    node("TAM", 0.4, 0.3),
    townId="t_tambov",
    tags=["dogs_allowed", "family_room", "parking"],
    priceNightRub=4500,
    rating=4.3,
)
add(
    "pl_tam_hotel_derzhavinskaya",
    L,
    "Державинская",
    node("TAM", -0.6, 0.5),
    townId="t_tambov",
    tags=["dogs_allowed", "family_room", "parking_guarded"],
    priceNightRub=5200,
    rating=4.4,
)
add(
    "pl_tam_hotel_solnechnaya",
    L,
    "Солнечная",
    node("TAM", 0.9, -0.7),
    townId="t_tambov",
    tags=["parking"],
    priceNightRub=3800,
    rating=4.0,
)
# Котовск: decoy for G03, three lodgings, none dog-friendly
add(
    "pl_kotovsk_hotel_1",
    L,
    "Котовск-отель",
    node("KOT", 0.3, 0.2),
    townId="t_kotovsk",
    tags=["parking", "family_room"],
    priceNightRub=3200,
    rating=4.6,
)
add(
    "pl_kotovsk_hotel_2",
    L,
    "Гостиница «Цна»",
    node("KOT", -0.4, 0.3),
    townId="t_kotovsk",
    tags=["parking", "family_room"],
    priceNightRub=3000,
    rating=4.5,
)
add(
    "pl_kotovsk_hotel_3",
    L,
    "Придорожная",
    node("KOT", 0.5, -0.4),
    townId="t_kotovsk",
    tags=["parking_guarded", "family_room"],
    priceNightRub=3500,
    rating=4.4,
)
add(
    "pl_bor_hotel_center",
    L,
    "Борисоглебская",
    node("BOR", 0.3, 0.3),
    townId="t_borisoglebsk",
    tags=["parking", "dogs_allowed"],
    priceNightRub=3600,
    rating=4.0,
)
add(
    "pl_bor_hotel_vorona",
    L,
    "Ворона",
    node("BOR", -0.5, 0.2),
    townId="t_borisoglebsk",
    tags=["parking"],
    priceNightRub=3300,
    rating=3.8,
)
add(
    "pl_vgg_hotel_volga",
    L,
    "Волгоград-отель",
    node("VGG", 0.6, 0.5),
    townId="t_volgograd",
    tags=["parking", "family_room", "dogs_allowed"],
    priceNightRub=6000,
    rating=4.5,
)
add(
    "pl_vgg_hotel_alley",
    L,
    "На Аллее Героев",
    node("VGG", -0.4, 0.8),
    townId="t_volgograd",
    tags=["parking_guarded"],
    priceNightRub=6800,
    rating=4.6,
)
# М-2
add(
    "pl_ser_hotel_oka",
    L,
    "Серпуховская",
    node("SER", 0.4, 0.2),
    townId="t_serpukhov",
    tags=["parking"],
    priceNightRub=4000,
    rating=4.0,
)
add(
    "pl_ser_hotel_vysotsky",
    L,
    "У Высоцкого монастыря",
    node("SER", -0.6, 0.5),
    townId="t_serpukhov",
    tags=["parking", "family_room"],
    priceNightRub=4400,
    rating=4.2,
)
add(
    "pl_tul_hotel_kremlin",
    L,
    "Тульский кремль-отель",
    node("TUL", 0.4, 0.3),
    townId="t_tula",
    tags=["parking", "family_room", "dogs_allowed"],
    priceNightRub=5500,
    rating=4.5,
)
add(
    "pl_tul_hotel_pryanik",
    L,
    "Пряничный двор",
    node("TUL", -0.7, 0.4),
    townId="t_tula",
    tags=["parking", "family_room"],
    priceNightRub=4800,
    rating=4.35,  # S2-01: 4.4 put G07's hotel pick within 0.03 of Тульский кремль-отель
)
add(
    "pl_tul_hotel_station",
    L,
    "Вокзальная",
    node("TUL", 0.9, -0.8),
    townId="t_tula",
    tags=[],
    priceNightRub=3000,
    rating=3.7,
    breakfastIncluded=False,
)

# ------------------------------------------------------------------ sights (hand-placed, with hours)
S = "sight"
add(
    "pl_sps_lavra",
    S,
    "Троице-Сергиева лавра",
    node("SPS", 0.5, 0.2),
    townId="t_sergiev_posad",
    tags=["monastery", "free_entry", "walk"],
    openingHours="Mo-Su 05:00-21:00",
    dwellMin=90,
    rating=4.9,
    descriptionRu="Главный монастырь России, собор XV века.",
)
add(
    "pl_prs_goritsky",
    S,
    "Горицкий монастырь",
    node("PRS", 1.0, -0.9),
    townId="t_pereslavl",
    tags=["monastery", "museum"],
    openingHours="We-Su 10:00-17:00",
    dwellMin=60,
    ticketAdultRub=300,
    ticketChildRub=150,
    rating=4.5,
)
add(
    "pl_prs_pleshcheevo",
    S,
    "Плещеево озеро",
    node("PRS", -1.2, 1.0),
    townId="t_pereslavl",
    tags=["view", "walk", "free_entry", "playground"],
    dwellMin=30,
    rating=4.6,
)
add(
    "pl_rst_kremlin",
    S,
    "Ростовский кремль",
    node("RST", 0.4, 0.3),
    townId="t_rostov",
    tags=["kremlin", "museum"],
    openingHours="Mo-Su 10:00-17:00",
    dwellMin=90,
    ticketAdultRub=400,
    ticketChildRub=200,
    rating=4.8,
)
add(
    "pl_yar_spaso",
    S,
    "Спасо-Преображенский монастырь",
    node("YAR", 0.6, -0.8),
    townId="t_yaroslavl",
    tags=["monastery", "museum"],
    openingHours="Tu-Su 10:00-18:00",
    dwellMin=90,
    ticketAdultRub=500,
    ticketChildRub=250,
    rating=4.7,
)
add(
    "pl_yar_strelka",
    S,
    "Стрелка и Волжская набережная",
    node("YAR", 1.5, 0.8),
    townId="t_yaroslavl",
    tags=["view", "walk", "evening", "free_entry"],
    dwellMin=45,
    rating=4.8,
)
add(
    "pl_kos_ipatiev",
    S,
    "Ипатьевский монастырь",
    node("KOS", -2.0, -0.3),
    townId="t_kostroma",
    tags=["monastery", "museum"],
    openingHours="Mo-Su 09:00-18:00",
    dwellMin=90,
    ticketAdultRub=500,
    ticketChildRub=250,
    rating=4.8,
)
add(
    "pl_kos_sloboda",
    S,
    "Костромская слобода",
    node("KOS", -2.4, 0.4),
    townId="t_kostroma",
    tags=["museum", "walk", "playground"],
    openingHours="Mo-Su 09:00-17:00",
    dwellMin=60,
    ticketAdultRub=300,
    ticketChildRub=150,
    rating=4.5,
)
add(
    "pl_iva_sitets",
    S,
    "Музей ивановского ситца",
    node("IVA", 0.3, -0.2),
    townId="t_ivanovo",
    tags=["museum"],
    openingHours="We-Su 10:00-18:00",
    dwellMin=60,
    ticketAdultRub=250,
    ticketChildRub=120,
    rating=4.3,
)
add(
    "pl_suz_kremlin",
    S,
    "Суздальский кремль",
    node("SUZ", 0.3, -1.0),
    townId="t_suzdal",
    tags=["kremlin", "museum"],
    openingHours="We-Mo 10:00-18:00",
    dwellMin=60,
    ticketAdultRub=400,
    ticketChildRub=200,
    rating=4.8,
)
add(
    "pl_suz_evfimiev",
    S,
    "Спасо-Евфимиев монастырь",
    node("SUZ", -0.3, 1.2),
    townId="t_suzdal",
    tags=["monastery", "museum"],
    openingHours="Mo-Su 10:00-18:00",
    dwellMin=90,
    ticketAdultRub=400,
    ticketChildRub=200,
    rating=4.7,
)
add(
    "pl_suz_wooden",
    S,
    "Музей деревянного зодчества",
    node("SUZ", 1.2, -0.5),
    townId="t_suzdal",
    tags=["museum", "walk"],
    openingHours="Mo-Su 09:00-19:00",
    dwellMin=60,
    ticketAdultRub=300,
    ticketChildRub=150,
    rating=4.5,
)
add(
    "pl_vla_golden_gate",
    S,
    "Золотые ворота",
    node("VLA", 0.4, 0.1),
    townId="t_vladimir",
    tags=["museum", "view"],
    openingHours="Tu-Su 10:00-18:00",
    dwellMin=30,
    ticketAdultRub=250,
    ticketChildRub=120,
    rating=4.7,
)
add(
    "pl_vla_assumption",
    S,
    "Успенский собор",
    node("VLA", 0.9, -0.3),
    townId="t_vladimir",
    tags=["view"],
    openingHours="Mo-Su 13:00-17:00",
    dwellMin=45,
    ticketAdultRub=300,
    ticketChildRub=150,
    rating=4.8,
)
add(
    "pl_vla_nerl",
    S,
    "Церковь Покрова на Нерли",
    node("VLA", 9.5, 1.5),
    tags=["view", "walk", "free_entry"],
    dwellMin=60,
    rating=4.9,
)
add(
    "pl_pok_chocolate",
    S,
    "Музей шоколада",
    node("POK", 0.4, 0.3),
    townId="t_pokrov",
    tags=["museum", "playground"],
    openingHours="Mo-Su 10:00-18:00",
    dwellMin=45,
    ticketAdultRub=350,
    ticketChildRub=250,
    rating=4.3,
)
add(
    "pl_gor_old_town",
    S,
    "Старый Гороховец",
    node("GOR", 0.5, 0.6),
    townId="t_gorokhovets",
    tags=["walk", "view", "free_entry"],
    dwellMin=45,
    rating=4.5,
)
add(
    "pl_nnv_kremlin",
    S,
    "Нижегородский кремль",
    node("NNV", 0.8, 0.6),
    townId="t_nizhny",
    tags=["kremlin", "walk", "view", "free_entry", "evening"],
    openingHours="Mo-Su 06:00-22:00",
    dwellMin=60,
    rating=4.8,
)
add(
    "pl_nnv_chkalov",
    S,
    "Чкаловская лестница",
    node("NNV", 1.2, 0.9),
    townId="t_nizhny",
    tags=["view", "walk", "free_entry", "evening"],
    dwellMin=30,
    rating=4.7,
)
add(
    "pl_chb_bay",
    S,
    "Чебоксарский залив",
    node("CHB", 0.5, 0.5),
    townId="t_cheboksary",
    tags=["walk", "view", "free_entry", "evening", "playground"],
    dwellMin=45,
    rating=4.5,
)
add(
    "pl_kaz_kremlin",
    S,
    "Казанский кремль",
    node("KAZ", 0.7, 0.8),
    townId="t_kazan",
    tags=["kremlin", "museum", "free_entry", "evening"],
    openingHours="Mo-Su 08:00-22:00",
    dwellMin=90,
    rating=4.9,
)
add(
    "pl_zel_sviyazhsk",
    S,
    "Остров-град Свияжск",
    node("ZEL", 2.0, -6.0),
    tags=["monastery", "museum", "walk"],
    openingHours="Mo-Su 09:00-18:00",
    dwellMin=120,
    ticketAdultRub=400,
    ticketChildRub=200,
    rating=4.8,
)
add(
    "pl_mch_michurin",
    S,
    "Дом-музей Мичурина",
    node("MCH", 0.4, 0.3),
    townId="t_michurinsk",
    tags=["museum"],
    openingHours="Tu-Sa 09:00-17:00",
    dwellMin=45,
    ticketAdultRub=150,
    ticketChildRub=80,
    rating=4.2,
)
add(
    "pl_tam_aseev",
    S,
    "Усадьба Асеевых",
    node("TAM", 0.8, 0.9),
    townId="t_tambov",
    tags=["museum"],
    openingHours="Tu-Su 10:00-18:00",
    dwellMin=60,
    ticketAdultRub=300,
    ticketChildRub=150,
    rating=4.5,
)
add(
    "pl_tam_tsna",
    S,
    "Набережная Цны",
    node("TAM", 1.0, 0.2),
    townId="t_tambov",
    tags=["walk", "view", "evening", "free_entry"],
    dwellMin=30,
    rating=4.4,
)
add(
    "pl_vgg_mamaev",
    S,
    "Мамаев курган",
    node("VGG", -1.0, 2.5),
    townId="t_volgograd",
    tags=["view", "walk", "free_entry", "museum"],
    openingHours="24/7",
    dwellMin=90,
    rating=4.9,
)
add(
    "pl_vgg_panorama",
    S,
    "Музей-панорама «Сталинградская битва»",
    node("VGG", 0.8, 0.4),
    townId="t_volgograd",
    tags=["museum"],
    openingHours="Tu-Su 10:00-18:00",
    dwellMin=90,
    ticketAdultRub=400,
    ticketChildRub=200,
    rating=4.8,
)
add(
    "pl_ser_vysotsky",
    S,
    "Высоцкий монастырь",
    node("SER", -0.5, -0.6),
    townId="t_serpukhov",
    tags=["monastery", "free_entry"],
    openingHours="Mo-Su 07:00-19:00",
    dwellMin=45,
    rating=4.6,
)
add(
    "pl_ser_prioksky",
    S,
    "Приокско-Террасный заповедник",
    chain_anchor("M2", 88, 9.0),
    tags=["walk", "playground", "view"],
    openingHours="Mo-Su 09:00-17:00",
    dwellMin=90,
    ticketAdultRub=400,
    ticketChildRub=200,
    rating=4.7,
)
add(
    "pl_tul_kremlin",
    S,
    "Тульский кремль",
    node("TUL", 0.5, 0.4),
    townId="t_tula",
    tags=["kremlin", "museum", "walk"],
    openingHours="Mo-Su 10:00-22:00",
    dwellMin=60,
    ticketAdultRub=300,
    ticketChildRub=150,
    rating=4.7,
)
add(
    "pl_tul_weapons",
    S,
    "Музей оружия",
    node("TUL", 0.7, 0.6),
    townId="t_tula",
    tags=["museum", "playground"],
    openingHours="We-Su 10:00-18:00",
    dwellMin=90,
    ticketAdultRub=400,
    ticketChildRub=200,
    rating=4.8,
)
add(
    "pl_tul_yasnaya",
    S,
    "Ясная Поляна",
    node("YAP", -1.5, 0.0),
    tags=["museum", "walk"],
    openingHours="Tu-Su 09:00-17:00",
    dwellMin=120,
    ticketAdultRub=500,
    ticketChildRub=250,
    rating=4.9,
    descriptionRu="Усадьба Льва Толстого.",
)
add(
    "pl_skp_lake",
    S,
    "Скопинское городище",
    node("SKP", 0.6, 0.4),
    townId="t_skopin",
    tags=["view", "walk", "free_entry"],
    dwellMin=30,
    rating=4.0,
)

# ------------------------------------------------------------------ food (hand-placed in towns)
F = "food"
add(
    "pl_sps_cafe_posad",
    F,
    "Трапезная «Посадская»",
    node("SPS", 0.6, 0.0),
    townId="t_sergiev_posad",
    tags=["kids_menu", "parking"],
    avgCheckRub=750,
    rating=4.5,
    openingHours="Mo-Su 09:00-21:00",
)
add(
    "pl_prs_cafe_lake",
    F,
    "Ресторан «Плещеево»",
    node("PRS", -0.5, 0.4),
    townId="t_pereslavl",
    tags=["view", "parking"],
    avgCheckRub=850,
    rating=4.4,
    openingHours="Mo-Su 11:00-22:00",
)
add(
    "pl_prs_cafe_kids",
    F,
    "Кафе «Ботик»",
    node("PRS", 0.3, 0.2),
    townId="t_pereslavl",
    tags=["kids_menu", "playground"],
    avgCheckRub=650,
    rating=4.3,
    openingHours="Mo-Su 10:00-21:00",
)
add(
    "pl_rst_cafe_kremlin",
    F,
    "Трапезная у кремля",
    node("RST", 0.3, 0.1),
    townId="t_rostov",
    tags=["kids_menu", "parking"],
    avgCheckRub=700,
    rating=4.5,
    openingHours="Mo-Su 10:00-21:00",
)
add(
    "pl_yar_rest_strelka",
    F,
    "Ресторан «Стрелка»",
    node("YAR", 1.3, 0.7),
    townId="t_yaroslavl",
    tags=["view"],
    avgCheckRub=950,
    rating=4.6,
    openingHours="Mo-Su 12:00-23:00",
)
add(
    "pl_yar_cafe_pelmen",
    F,
    "Пельменная на Кирова",
    node("YAR", 0.5, 0.2),
    townId="t_yaroslavl",
    tags=["kids_menu"],
    avgCheckRub=600,
    rating=4.3,
    openingHours="Mo-Su 09:00-22:00",
)
add(
    "pl_yar_cafe_volga",
    F,
    "Кафе «Волжанка»",
    node("YAR", -0.6, -0.5),
    townId="t_yaroslavl",
    tags=["parking"],
    avgCheckRub=700,
    rating=4.1,
    openingHours="Mo-Su 10:00-22:00",
)
add(
    "pl_kos_cafe_sbiten",
    F,
    "Сбитенная",
    node("KOS", 0.2, 0.2),
    townId="t_kostroma",
    tags=["kids_menu", "parking"],
    avgCheckRub=700,
    rating=4.4,
    openingHours="Mo-Su 10:00-22:00",
)
add(
    "pl_kos_cafe_syr",
    F,
    "Сырная лавка",
    node("KOS", -0.3, 0.1),
    townId="t_kostroma",
    tags=[],
    avgCheckRub=650,
    rating=4.2,
    openingHours="Mo-Su 09:00-20:00",
)
add(
    "pl_iva_cafe_center",
    F,
    "Кафе «Текстиль»",
    node("IVA", 0.2, 0.1),
    townId="t_ivanovo",
    tags=["kids_menu"],
    avgCheckRub=600,
    rating=4.1,
    openingHours="Mo-Su 10:00-22:00",
)
add(
    "pl_suz_rest_trapeznaya",
    F,
    "Трапезная в кремле",
    node("SUZ", 0.3, -0.9),
    townId="t_suzdal",
    tags=["kids_menu", "parking"],
    avgCheckRub=800,
    rating=4.6,
    openingHours="Mo-Su 11:00-22:00",
)
add(
    "pl_suz_cafe_medovushi",
    F,
    "Дегустационный зал медовухи",
    node("SUZ", 0.1, 0.2),
    townId="t_suzdal",
    tags=[],
    avgCheckRub=700,
    rating=4.3,
    openingHours="Mo-Su 10:00-21:00",
)
add(
    "pl_vla_cafe_gate",
    F,
    "Кафе у Золотых ворот",
    node("VLA", 0.5, 0.2),
    townId="t_vladimir",
    tags=["kids_menu", "parking"],
    avgCheckRub=700,
    rating=4.4,
    openingHours="Mo-Su 09:00-22:00",
)
add(
    "pl_vla_rest_klyazma",
    F,
    "Ресторан «Клязьма»",
    node("VLA", -0.8, -0.4),
    townId="t_vladimir",
    tags=["view"],
    avgCheckRub=900,
    rating=4.3,
    openingHours="Mo-Su 12:00-23:00",
)
add(
    "pl_pok_cafe",
    F,
    "Кафе «Покровское»",
    node("POK", 0.3, 0.1),
    townId="t_pokrov",
    tags=["kids_menu", "parking"],
    avgCheckRub=650,
    rating=4.2,
    openingHours="Mo-Su 08:00-22:00",
)
add(
    "pl_gor_cafe",
    F,
    "Трапезная Гороховца",
    node("GOR", 0.4, 0.4),
    townId="t_gorokhovets",
    tags=["parking"],
    avgCheckRub=600,
    rating=4.1,  # S2-01: 4.2 tied G06's day-1 lunch with Кафе «Привал» (5.1 / 5.1)
    openingHours="Mo-Su 10:00-21:00",
)
add(
    "pl_nnv_rest_kremlin",
    F,
    "Ресторан на Рождественской",
    node("NNV", 0.7, 0.5),
    townId="t_nizhny",
    tags=["view"],
    avgCheckRub=1000,
    rating=4.6,
    openingHours="Mo-Su 12:00-23:00",
)
add(
    "pl_nnv_cafe_kids",
    F,
    "Кафе «Волжский пряник»",
    node("NNV", 0.3, -0.2),
    townId="t_nizhny",
    tags=["kids_menu"],
    avgCheckRub=700,
    rating=4.3,
    openingHours="Mo-Su 09:00-22:00",
)
add(
    "pl_chb_cafe",
    F,
    "Чувашская кухня",
    node("CHB", 0.3, 0.2),
    townId="t_cheboksary",
    tags=["kids_menu", "parking"],
    avgCheckRub=650,
    rating=4.4,
    openingHours="Mo-Su 10:00-22:00",
)
add(
    "pl_kaz_rest_tatar",
    F,
    "Дом татарской кулинарии",
    node("KAZ", 0.4, 0.5),
    townId="t_kazan",
    tags=["kids_menu"],
    avgCheckRub=900,
    rating=4.7,
    openingHours="Mo-Su 10:00-23:00",
)
add(
    "pl_mch_cafe",
    F,
    "Кафе «Антоновка»",
    node("MCH", 0.2, 0.1),
    townId="t_michurinsk",
    tags=["parking"],
    avgCheckRub=550,
    rating=4.1,
    openingHours="Mo-Su 09:00-21:00",
)
add(
    "pl_tam_cafe",
    F,
    "Тамбовская трапезная",
    node("TAM", 0.5, 0.4),
    townId="t_tambov",
    tags=["kids_menu", "parking"],
    avgCheckRub=650,
    rating=4.3,
    openingHours="Mo-Su 10:00-22:00",
)
add(
    "pl_tam_rest",
    F,
    "Ресторан «Державин»",
    node("TAM", -0.4, 0.6),
    townId="t_tambov",
    tags=[],
    avgCheckRub=850,
    rating=4.4,
    openingHours="Mo-Su 12:00-23:00",
)
add(
    "pl_bor_cafe",
    F,
    "Кафе «Хопёр»",
    node("BOR", 0.2, 0.2),
    townId="t_borisoglebsk",
    tags=["parking"],
    avgCheckRub=550,
    rating=4.0,
    openingHours="Mo-Su 09:00-21:00",
)
add(
    "pl_vgg_rest",
    F,
    "Ресторан «Волжский»",
    node("VGG", 0.5, 0.6),
    townId="t_volgograd",
    tags=["view", "kids_menu"],
    avgCheckRub=900,
    rating=4.5,
    openingHours="Mo-Su 11:00-23:00",
)
add(
    "pl_vgg_cafe",
    F,
    "Кафе «Сталинградское»",
    node("VGG", -0.3, 0.3),
    townId="t_volgograd",
    tags=[],
    avgCheckRub=700,
    rating=4.2,
    openingHours="Mo-Su 09:00-22:00",
)
add(
    "pl_ser_cafe",
    F,
    "Кафе «Ока»",
    node("SER", 0.3, 0.1),
    townId="t_serpukhov",
    tags=["kids_menu", "parking"],
    avgCheckRub=650,
    rating=4.2,
    openingHours="Mo-Su 09:00-22:00",
)
add(
    "pl_tul_cafe_pryanik",
    F,
    "Пряничная",
    node("TUL", 0.4, 0.2),
    townId="t_tula",
    tags=["kids_menu", "playground"],
    avgCheckRub=600,
    rating=4.5,
    openingHours="Mo-Su 09:00-21:00",
)
add(
    "pl_tul_rest_kremlin",
    F,
    "Ресторан «Тульский»",
    node("TUL", 0.6, 0.5),
    townId="t_tula",
    tags=["parking"],
    avgCheckRub=850,
    rating=4.4,
    openingHours="Mo-Su 12:00-23:00",
)
add(
    "pl_yap_cafe",
    F,
    "Кафе у Ясной Поляны",
    node("YAP", -1.2, 0.2),
    tags=["kids_menu", "parking"],
    avgCheckRub=700,
    rating=4.4,
    openingHours="Mo-Su 10:00-19:00",
)
add(
    "pl_ksh_cafe",
    F,
    "Кафе «Каширское»",
    node("KSH", 0.2, 0.2),
    townId="t_kashira",
    tags=["parking"],
    avgCheckRub=600,
    rating=4.0,
    openingHours="Mo-Su 09:00-21:00",
)

# ------------------------------------------------------------------ enrichment for alternatives (A§16.6)
# Second-choice sights and cafés in the towns the golden trips pass, so that most replaceable stops have
# 2-3 alternatives within ±45 min (review R-05). Ratings sit below each town's main sights.
# id, town node, town id, name, (dx, dy) km, tags, hours, dwell, rating, adult, child
EXTRA_SIGHTS = [
    (
        "pl_sps_pyatnitskoe",
        "SPS",
        "t_sergiev_posad",
        "Пятницкое подворье",
        (-0.6, 0.5),
        ["walk", "free_entry"],
        None,
        45,
        4.2,
        None,
        None,
    ),
    (
        "pl_sps_toys",
        "SPS",
        "t_sergiev_posad",
        "Музей игрушки",
        (0.9, -0.4),
        ["museum", "playground"],
        "Tu-Su 10:00-17:00",
        60,
        4.3,
        250,
        150,
    ),
    (
        "pl_sps_gremyachiy",
        "SPS",
        "t_sergiev_posad",
        "Гремячий ключ",
        (1.6, 1.1),
        ["walk", "view", "free_entry"],
        None,
        45,
        4.1,
        None,
        None,
    ),
    (
        "pl_prs_nikitsky",
        "PRS",
        "t_pereslavl",
        "Никитский монастырь",
        (0.8, 1.4),
        ["monastery", "free_entry"],
        "Mo-Su 07:00-19:00",
        45,
        4.4,
        None,
        None,
    ),
    (
        "pl_prs_botik",
        "PRS",
        "t_pereslavl",
        "Музей-усадьба «Ботик Петра Первого»",
        (-1.6, -1.2),
        ["museum", "view"],
        "We-Su 10:00-17:00",
        60,
        4.1,
        350,
        150,
    ),
    (
        "pl_prs_blue_stone",
        "PRS",
        "t_pereslavl",
        "Синий камень",
        (-1.8, 0.9),
        ["view", "walk", "free_entry"],
        None,
        30,
        4.0,
        None,
        None,
    ),
    (
        "pl_rst_yakovlevsky",
        "RST",
        "t_rostov",
        "Спасо-Яковлевский монастырь",
        (-1.1, -0.8),
        ["monastery", "free_entry", "view"],
        "Mo-Su 08:00-19:00",
        60,
        4.4,
        None,
        None,
    ),
    (
        "pl_rst_nero",
        "RST",
        "t_rostov",
        "Набережная озера Неро",
        (0.3, -0.6),
        ["walk", "view", "free_entry"],
        None,
        30,
        4.1,
        None,
        None,
    ),
    (
        "pl_rst_finift",
        "RST",
        "t_rostov",
        "Музей ростовской финифти",
        (0.6, 0.5),
        ["museum"],
        "Mo-Su 10:00-17:00",
        45,
        4.2,
        250,
        100,
    ),
    (
        "pl_yar_ilya",
        "YAR",
        "t_yaroslavl",
        "Церковь Ильи Пророка",
        (0.5, 0.4),
        ["museum"],
        "Tu-Su 10:00-18:00",
        45,
        4.4,
        200,
        100,
    ),
    (
        "pl_yar_embankment",
        "YAR",
        "t_yaroslavl",
        "Волжская набережная",
        (0.9, 0.2),
        ["walk", "view", "free_entry"],
        None,
        45,
        4.3,
        None,
        None,
    ),
    (
        "pl_yar_tolchkovo",
        "YAR",
        "t_yaroslavl",
        "Церковь Иоанна Предтечи в Толчкове",
        (-1.4, 1.2),
        ["museum"],
        "We-Su 10:00-17:00",
        45,
        4.2,
        150,
        80,
    ),
    (
        "pl_kos_rows",
        "KOS",
        "t_kostroma",
        "Торговые ряды",
        (0.4, -0.3),
        ["walk", "free_entry"],
        None,
        45,
        4.2,
        None,
        None,
    ),
    (
        "pl_kos_jewel",
        "KOS",
        "t_kostroma",
        "Музей ювелирного искусства",
        (0.7, 0.3),
        ["museum"],
        "Tu-Su 10:00-18:00",
        45,
        4.1,
        250,
        150,
    ),
    (
        "pl_kos_snow",
        "KOS",
        "t_kostroma",
        "Терем Снегурочки",
        (-0.5, 0.6),
        ["museum", "playground"],
        "Mo-Su 10:00-18:00",
        45,
        4.0,
        300,
        250,
    ),
    (
        "pl_iva_chintz",
        "IVA",
        "t_ivanovo",
        "Музей ивановского ситца",
        (0.4, 0.5),
        ["museum"],
        "Tu-Su 10:00-18:00",
        45,
        4.1,
        200,
        100,
    ),
    (
        "pl_iva_ship",
        "IVA",
        "t_ivanovo",
        "Дом-корабль",
        (-0.6, 0.3),
        ["view", "free_entry"],
        None,
        30,
        3.9,
        None,
        None,
    ),
    (
        "pl_suz_trade",
        "SUZ",
        "t_suzdal",
        "Торговая площадь",
        (0.2, 0.3),
        ["walk", "free_entry"],
        None,
        45,
        4.3,
        None,
        None,
    ),
    (
        "pl_suz_rizopolozhensky",
        "SUZ",
        "t_suzdal",
        "Ризоположенский монастырь",
        (0.5, -0.6),
        ["monastery", "free_entry"],
        "Mo-Su 08:00-19:00",
        45,
        4.2,
        None,
        None,
    ),
    (
        "pl_suz_pokrovsky",
        "SUZ",
        "t_suzdal",
        "Покровский монастырь",
        (-0.9, 1.0),
        ["monastery", "free_entry", "view"],
        "Mo-Su 08:00-19:00",
        45,
        4.3,
        None,
        None,
    ),
    (
        "pl_vla_dmitrievsky",
        "VLA",
        "t_vladimir",
        "Дмитриевский собор",
        (0.5, -0.3),
        ["museum"],
        "Mo-Su 10:00-17:00",
        45,
        4.5,
        250,
        100,
    ),
    (
        "pl_vla_view",
        "VLA",
        "t_vladimir",
        "Смотровая у Успенского собора",
        (0.3, -0.5),
        ["view", "walk", "free_entry"],
        None,
        30,
        4.2,
        None,
        None,
    ),
    (
        "pl_vla_chambers",
        "VLA",
        "t_vladimir",
        "Палаты",
        (0.7, -0.4),
        ["museum", "playground"],
        "Tu-Su 10:00-18:00",
        60,
        4.3,
        200,
        100,
    ),
    (
        "pl_pok_park",
        "POK",
        "t_pokrov",
        "Покровский парк",
        (0.4, -0.5),
        ["walk", "playground", "free_entry"],
        None,
        30,
        3.9,
        None,
        None,
    ),
    (
        "pl_pok_monastery",
        "POK",
        "t_pokrov",
        "Свято-Введенский монастырь",
        (-1.0, 1.2),
        ["monastery", "free_entry"],
        "Mo-Su 07:00-19:00",
        45,
        4.1,
        None,
        None,
    ),
    (
        "pl_gor_houses",
        "GOR",
        "t_gorokhovets",
        "Купеческие дома Гороховца",
        (0.3, 0.6),
        ["walk", "free_entry"],
        None,
        45,
        4.1,
        None,
        None,
    ),
    (
        "pl_gor_nikolsky",
        "GOR",
        "t_gorokhovets",
        "Никольский монастырь",
        (-0.6, 0.8),
        ["monastery", "free_entry", "view"],
        "Mo-Su 07:00-19:00",
        45,
        4.0,
        None,
        None,
    ),
    (
        "pl_nnv_pokrovka",
        "NNV",
        "t_nizhny",
        "Большая Покровская",
        (0.4, -0.6),
        ["walk", "free_entry"],
        None,
        60,
        4.3,
        None,
        None,
    ),
    (
        "pl_nnv_museum",
        "NNV",
        "t_nizhny",
        "Художественный музей",
        (0.8, 0.2),
        ["museum"],
        "Tu-Su 11:00-19:00",
        60,
        4.2,
        300,
        150,
    ),
    (
        "pl_chb_monument",
        "CHB",
        "t_cheboksary",
        "Монумент Матери-покровительнице",
        (0.6, 0.5),
        ["view", "free_entry"],
        None,
        30,
        4.1,
        None,
        None,
    ),
    (
        "pl_chb_embankment",
        "CHB",
        "t_cheboksary",
        "Красная площадь и набережная",
        (0.3, 0.2),
        ["walk", "free_entry"],
        None,
        45,
        4.2,
        None,
        None,
    ),
    (
        "pl_ksh_nikitsky",
        "KSH",
        "t_kashira",
        "Никитский монастырь Каширы",
        (0.5, 0.6),
        ["monastery", "free_entry"],
        "Mo-Su 07:00-19:00",
        45,
        4.0,
        None,
        None,
    ),
    (
        "pl_ksh_oka_view",
        "KSH",
        "t_kashira",
        "Смотровая на Оку",
        (-0.4, -0.7),
        ["view", "walk", "free_entry"],
        None,
        30,
        3.9,
        None,
        None,
    ),
    (
        "pl_mih_museum",
        "MIH",
        "t_mikhailov",
        "Михайловский краеведческий музей",
        (0.3, 0.4),
        ["museum"],
        "Tu-Su 09:00-17:00",
        45,
        3.8,
        150,
        80,
    ),
    (
        "pl_skp_ceramics",
        "SKP",
        "t_skopin",
        "Музей скопинской керамики",
        (0.4, -0.3),
        ["museum"],
        "Tu-Su 09:00-17:00",
        45,
        4.0,
        150,
        80,
    ),
    (
        "pl_skp_cathedral",
        "SKP",
        "t_skopin",
        "Никольский собор Скопина",
        (-0.3, 0.5),
        ["free_entry", "view"],
        None,
        30,
        3.8,
        None,
        None,
    ),
    (
        "pl_mch_garden",
        "MCH",
        "t_michurinsk",
        "Сад Мичурина",
        (0.8, 0.6),
        ["walk", "playground", "free_entry"],
        None,
        45,
        4.1,
        None,
        None,
    ),
    (
        "pl_mch_bogolyubsky",
        "MCH",
        "t_michurinsk",
        "Боголюбский собор",
        (-0.4, 0.3),
        ["free_entry"],
        "Mo-Su 07:00-19:00",
        30,
        3.9,
        None,
        None,
    ),
    (
        "pl_tam_embankment",
        "TAM",
        "t_tambov",
        "Набережная Тамбова",
        (0.6, -0.4),
        ["walk", "free_entry"],
        None,
        45,
        4.0,
        None,
        None,
    ),
    (
        "pl_ser_vladychny",
        "SER",
        "t_serpukhov",
        "Владычный монастырь",
        (0.6, 0.4),
        ["monastery", "free_entry"],
        "Mo-Su 07:00-19:00",
        45,
        4.2,
        None,
        None,
    ),
    (
        "pl_ser_kremlin",
        "SER",
        "t_serpukhov",
        "Соборная гора",
        (-0.4, 0.5),
        ["view", "walk", "free_entry"],
        None,
        30,
        4.1,
        None,
        None,
    ),
    (
        "pl_ser_museum",
        "SER",
        "t_serpukhov",
        "Серпуховский историко-художественный музей",
        (0.3, -0.4),
        ["museum"],
        "We-Su 10:00-17:00",
        60,
        4.2,
        250,
        100,
    ),
    (
        "pl_tul_gingerbread",
        "TUL",
        "t_tula",
        "Музей «Тульский пряник»",
        (0.4, 0.3),
        ["museum", "playground"],
        "Mo-Su 10:00-18:00",
        45,
        4.3,
        200,
        100,
    ),
    (
        "pl_tul_belousov",
        "TUL",
        "t_tula",
        "Белоусовский парк",
        (-0.8, -0.6),
        ["walk", "playground", "free_entry"],
        None,
        45,
        4.1,
        None,
        None,
    ),
    (
        "pl_tul_samovar",
        "TUL",
        "t_tula",
        "Музей «Тульские самовары»",
        (0.3, 0.4),
        ["museum"],
        "Tu-Su 10:00-18:00",
        45,
        4.2,
        200,
        100,
    ),
]
EXTRA_SIGHTS += [
    (
        "pl_sps_chapel",
        "SPS",
        "t_sergiev_posad",
        "Часовня Пятницкого колодца",
        (0.4, 0.6),
        ["free_entry"],
        None,
        30,
        3.9,
        None,
        None,
    ),
    (
        "pl_prs_fedorovsky",
        "PRS",
        "t_pereslavl",
        "Фёдоровский монастырь",
        (0.9, -1.3),
        ["monastery", "free_entry"],
        "Mo-Su 07:00-19:00",
        45,
        4.1,
        None,
        None,
    ),
    (
        "pl_prs_rampart",
        "PRS",
        "t_pereslavl",
        "Земляной вал Переславля",
        (0.2, 0.3),
        ["walk", "view", "free_entry"],
        None,
        30,
        4.0,
        None,
        None,
    ),
    (
        "pl_prs_iron",
        "PRS",
        "t_pereslavl",
        "Музей утюга",
        (0.4, 0.2),
        ["museum"],
        "Mo-Su 10:00-18:00",
        30,
        3.9,
        200,
        100,
    ),
    (
        "pl_rst_gostiny",
        "RST",
        "t_rostov",
        "Гостиный двор Ростова",
        (0.3, 0.2),
        ["walk", "free_entry"],
        None,
        30,
        3.9,
        None,
        None,
    ),
    (
        "pl_rst_avraamiev",
        "RST",
        "t_rostov",
        "Авраамиев монастырь",
        (0.8, -0.5),
        ["monastery", "free_entry"],
        "Mo-Su 07:00-19:00",
        45,
        4.0,
        None,
        None,
    ),
    (
        "pl_yar_tower",
        "YAR",
        "t_yaroslavl",
        "Власьевская башня",
        (0.2, 0.3),
        ["view", "free_entry"],
        None,
        30,
        3.9,
        None,
        None,
    ),
    (
        "pl_kos_fire_tower",
        "KOS",
        "t_kostroma",
        "Пожарная каланча",
        (0.3, -0.4),
        ["view", "free_entry"],
        None,
        30,
        4.0,
        None,
        None,
    ),
    (
        "pl_kos_park",
        "KOS",
        "t_kostroma",
        "Центральный парк Костромы",
        (0.1, -0.2),
        ["walk", "playground", "free_entry"],
        None,
        30,
        3.9,
        None,
        None,
    ),
    (
        "pl_suz_alexandrovsky",
        "SUZ",
        "t_suzdal",
        "Александровский монастырь",
        (-0.4, 0.8),
        ["monastery", "free_entry", "view"],
        "Mo-Su 08:00-19:00",
        45,
        4.1,
        None,
        None,
    ),
    (
        "pl_suz_kamenka",
        "SUZ",
        "t_suzdal",
        "Набережная Каменки",
        (0.1, 0.2),
        ["walk", "view", "free_entry"],
        None,
        30,
        4.0,
        None,
        None,
    ),
    (
        "pl_vla_cathedral_square",
        "VLA",
        "t_vladimir",
        "Соборная площадь Владимира",
        (0.4, -0.4),
        ["walk", "free_entry"],
        None,
        30,
        4.1,
        None,
        None,
    ),
    (
        "pl_vla_water_tower",
        "VLA",
        "t_vladimir",
        "Старая водонапорная башня",
        (0.6, -0.3),
        ["museum", "view"],
        "Tu-Su 10:00-17:00",
        30,
        4.0,
        150,
        80,
    ),
    (
        "pl_nnv_rozhdestvenskaya",
        "NNV",
        "t_nizhny",
        "Рождественская улица",
        (0.5, -0.2),
        ["walk", "free_entry"],
        None,
        45,
        4.1,
        None,
        None,
    ),
    (
        "pl_nnv_fedorovsky",
        "NNV",
        "t_nizhny",
        "Набережная Фёдоровского",
        (0.6, 0.3),
        ["view", "walk", "free_entry"],
        None,
        30,
        4.2,
        None,
        None,
    ),
    (
        "pl_chb_park",
        "CHB",
        "t_cheboksary",
        "Парк Победы Чебоксар",
        (0.4, 0.6),
        ["walk", "playground", "free_entry"],
        None,
        30,
        3.9,
        None,
        None,
    ),
    (
        "pl_skp_park",
        "SKP",
        "t_skopin",
        "Городской парк Скопина",
        (0.2, 0.2),
        ["walk", "playground", "free_entry"],
        None,
        30,
        3.6,
        None,
        None,
    ),
    (
        "pl_mch_station",
        "MCH",
        "t_michurinsk",
        "Вокзал Мичуринска",
        (0.3, -0.2),
        ["view", "free_entry"],
        None,
        30,
        3.8,
        None,
        None,
    ),
    (
        "pl_tam_park",
        "TAM",
        "t_tambov",
        "Парк культуры Тамбова",
        (0.3, 0.4),
        ["walk", "playground", "free_entry"],
        None,
        45,
        3.9,
        None,
        None,
    ),
    (
        "pl_tam_museum",
        "TAM",
        "t_tambov",
        "Тамбовский краеведческий музей",
        (0.4, -0.2),
        ["museum"],
        "Tu-Su 10:00-18:00",
        45,
        4.0,
        200,
        100,
    ),
    (
        "pl_ser_park",
        "SER",
        "t_serpukhov",
        "Парк «Питомник»",
        (0.2, 0.3),
        ["walk", "playground", "free_entry"],
        None,
        30,
        3.9,
        None,
        None,
    ),
    (
        "pl_tul_embankment",
        "TUL",
        "t_tula",
        "Набережная Упы",
        (0.3, 0.2),
        ["walk", "view", "free_entry"],
        None,
        30,
        4.0,
        None,
        None,
    ),
    (
        "pl_tul_lefty",
        "TUL",
        "t_tula",
        "Музей «Тульский левша»",
        (0.4, 0.3),
        ["museum"],
        "Tu-Su 10:00-18:00",
        30,
        4.0,
        150,
        80,
    ),
]
for pid, n, town, name, (dx, dy), tags, hours, dwell, rating, adult, child in EXTRA_SIGHTS:
    kw = {"townId": town, "tags": tags, "dwellMin": dwell, "rating": rating}
    if hours:
        kw["openingHours"] = hours
    if adult is not None:
        kw["ticketAdultRub"] = adult
        kw["ticketChildRub"] = child
    add(pid, S, name, node(n, dx, dy), **kw)

# id, town node, town id, name, (dx, dy) km, tags, avg check, rating, hours
EXTRA_CAFES = [
    (
        "pl_sps_cafe_dvorik",
        "SPS",
        "t_sergiev_posad",
        "Кафе «Русский дворик»",
        (-0.4, 0.3),
        ["parking", "kids_menu"],
        700,
        4.2,
        "Mo-Su 10:00-22:00",
    ),
    (
        "pl_sps_cafe_bliny",
        "SPS",
        "t_sergiev_posad",
        "Блинная у лавры",
        (0.7, 0.3),
        ["parking"],
        550,
        4.1,
        "Mo-Su 09:00-21:00",
    ),
    (
        "pl_prs_cafe_sloboda",
        "PRS",
        "t_pereslavl",
        "Кафе «Переславская слобода»",
        (0.6, -0.5),
        ["parking", "kids_menu"],
        700,
        4.2,
        "Mo-Su 10:00-22:00",
    ),
    (
        "pl_prs_cafe_yam",
        "PRS",
        "t_pereslavl",
        "Трактир «Ямской двор»",
        (0.3, 0.6),
        ["parking"],
        800,
        4.1,
        "Mo-Su 11:00-23:00",
    ),
    (
        "pl_rst_cafe_podvorie",
        "RST",
        "t_rostov",
        "Кафе «Русское подворье»",
        (0.5, -0.2),
        ["parking", "kids_menu"],
        700,
        4.2,
        "Mo-Su 10:00-22:00",
    ),
    (
        "pl_rst_cafe_veliky",
        "RST",
        "t_rostov",
        "Трапезная «Ростов Великий»",
        (-0.4, 0.4),
        ["parking"],
        750,
        4.1,
        "Mo-Su 10:00-21:00",
    ),
    (
        "pl_rst_cafe_nero",
        "RST",
        "t_rostov",
        "Кафе «Неро»",
        (0.2, -0.7),
        ["view", "kids_menu"],
        650,
        4.0,
        "Mo-Su 10:00-22:00",
    ),
    (
        "pl_yar_cafe_terrace",
        "YAR",
        "t_yaroslavl",
        "Кафе «Волжская терраса»",
        (0.8, 0.1),
        ["view", "kids_menu"],
        900,
        4.2,
        "Mo-Su 11:00-23:00",
    ),
    (
        "pl_yar_cafe_sobranie",
        "YAR",
        "t_yaroslavl",
        "Ресторан «Собрание»",
        (0.4, 0.5),
        ["parking"],
        1000,
        4.3,
        "Mo-Su 12:00-23:00",
    ),
    (
        "pl_kos_cafe_sloboda",
        "KOS",
        "t_kostroma",
        "Кафе «Ипатьевская слобода»",
        (-0.7, 0.4),
        ["parking", "kids_menu"],
        700,
        4.2,
        "Mo-Su 10:00-22:00",
    ),
    (
        "pl_kos_cafe_rows",
        "KOS",
        "t_kostroma",
        "Кафе в Торговых рядах",
        (0.4, -0.2),
        ["kids_menu"],
        600,
        4.0,
        "Mo-Su 09:00-21:00",
    ),
    (
        "pl_iva_cafe_sitets",
        "IVA",
        "t_ivanovo",
        "Кафе «Ситец»",
        (0.3, 0.4),
        ["parking", "kids_menu"],
        600,
        4.0,
        "Mo-Su 10:00-22:00",
    ),
    (
        "pl_iva_cafe_station",
        "IVA",
        "t_ivanovo",
        "Столовая «Текстиль»",
        (-0.4, 0.2),
        ["parking"],
        500,
        3.9,
        "Mo-Su 08:00-20:00",
    ),
    (
        "pl_suz_cafe_kremlin",
        "SUZ",
        "t_suzdal",
        "Трапезная «Кремлёвская»",
        (0.2, -0.3),
        ["parking", "kids_menu"],
        900,
        4.2,
        "Mo-Su 11:00-22:00",
    ),
    (
        "pl_suz_cafe_pushkarka",
        "SUZ",
        "t_suzdal",
        "Кафе «Пушкарская слобода»",
        (0.6, 0.3),
        ["parking", "view"],
        1000,
        4.1,
        "Mo-Su 11:00-23:00",
    ),
    (
        "pl_vla_cafe_dmitrievsky",
        "VLA",
        "t_vladimir",
        "Кафе «Дмитриевское»",
        (0.4, -0.3),
        ["parking", "kids_menu"],
        700,
        4.2,
        "Mo-Su 10:00-22:00",
    ),
    (
        "pl_vla_cafe_georgievskaya",
        "VLA",
        "t_vladimir",
        "Кафе на Георгиевской",
        (0.6, -0.5),
        ["view"],
        750,
        4.1,
        "Mo-Su 11:00-23:00",
    ),
    (
        "pl_pok_cafe_park",
        "POK",
        "t_pokrov",
        "Кафе «Покровское подворье»",
        (0.3, -0.3),
        ["parking", "kids_menu"],
        600,
        4.0,
        "Mo-Su 09:00-21:00",
    ),
    (
        "pl_gor_cafe_kupets",
        "GOR",
        "t_gorokhovets",
        "Кафе «Купеческое»",
        (0.2, 0.4),
        ["parking"],
        600,
        4.0,
        "Mo-Su 10:00-21:00",
    ),
    (
        "pl_nnv_cafe_pokrovka",
        "NNV",
        "t_nizhny",
        "Кафе на Покровке",
        (0.4, -0.5),
        ["kids_menu"],
        800,
        4.2,
        "Mo-Su 10:00-23:00",
    ),
    (
        "pl_nnv_cafe_volga",
        "NNV",
        "t_nizhny",
        "Ресторан «Волжский откос»",
        (0.6, 0.4),
        ["view", "parking"],
        1000,
        4.3,
        "Mo-Su 12:00-23:00",
    ),
    (
        "pl_chb_cafe_bay",
        "CHB",
        "t_cheboksary",
        "Кафе у залива",
        (0.5, 0.3),
        ["view", "kids_menu"],
        700,
        4.1,
        "Mo-Su 10:00-22:00",
    ),
    (
        "pl_chb_cafe_chuvash",
        "CHB",
        "t_cheboksary",
        "Кафе «Чувашское подворье»",
        (0.2, 0.4),
        ["parking"],
        650,
        4.0,
        "Mo-Su 10:00-22:00",
    ),
    (
        "pl_ksh_cafe_oka",
        "KSH",
        "t_kashira",
        "Кафе «Ока»",
        (-0.3, -0.4),
        ["parking", "kids_menu"],
        600,
        3.9,
        "Mo-Su 09:00-21:00",
    ),
    (
        "pl_mih_cafe",
        "MIH",
        "t_mikhailov",
        "Кафе «Михайловская застава»",
        (0.3, 0.2),
        ["parking", "kids_menu"],
        550,
        3.9,
        "Mo-Su 09:00-21:00",
    ),
    (
        "pl_skp_cafe",
        "SKP",
        "t_skopin",
        "Кафе «Скопинское»",
        (0.2, 0.3),
        ["parking", "kids_menu"],
        550,
        3.9,
        "Mo-Su 09:00-21:00",
    ),
    (
        "pl_skp_cafe_lake",
        "SKP",
        "t_skopin",
        "Столовая «Городище»",
        (0.5, 0.2),
        ["parking"],
        500,
        3.8,
        "Mo-Su 08:00-20:00",
    ),
    (
        "pl_mch_cafe_garden",
        "MCH",
        "t_michurinsk",
        "Кафе «Яблоневый сад»",
        (0.6, 0.4),
        ["parking", "kids_menu"],
        600,
        4.0,
        "Mo-Su 10:00-22:00",
    ),
    (
        "pl_tam_cafe_tsna",
        "TAM",
        "t_tambov",
        "Кафе на Цне",
        (0.5, -0.3),
        ["parking", "kids_menu"],
        650,
        4.0,
        "Mo-Su 10:00-22:00",
    ),
    (
        "pl_ser_cafe_vladychny",
        "SER",
        "t_serpukhov",
        "Кафе «Владычное»",
        (0.5, 0.3),
        ["parking", "kids_menu"],
        650,
        4.0,
        "Mo-Su 10:00-22:00",
    ),
    (
        "pl_ser_cafe_oka",
        "SER",
        "t_serpukhov",
        "Кафе «Окская пристань»",
        (-0.3, -0.5),
        ["view", "parking"],
        750,
        4.1,
        "Mo-Su 11:00-22:00",
    ),
    (
        "pl_tul_cafe_samovar",
        "TUL",
        "t_tula",
        "Кафе «Самовар»",
        (0.3, 0.3),
        ["parking", "kids_menu"],
        700,
        4.2,
        "Mo-Su 10:00-22:00",
    ),
    (
        "pl_tul_cafe_kremlin",
        "TUL",
        "t_tula",
        "Кафе у кремля",
        (0.4, 0.2),
        ["kids_menu"],
        650,
        4.1,
        "Mo-Su 10:00-22:00",
    ),
]
EXTRA_CAFES += [
    (
        "pl_suz_cafe_ogurets",
        "SUZ",
        "t_suzdal",
        "Кафе «Огурец»",
        (0.1, -0.2),
        ["kids_menu"],
        800,
        4.0,
        "Mo-Su 10:00-22:00",
    ),
    (
        "pl_suz_cafe_gostiny",
        "SUZ",
        "t_suzdal",
        "Кафе в Гостином дворе",
        (0.2, 0.1),
        ["parking"],
        850,
        4.0,
        "Mo-Su 10:00-22:00",
    ),
    (
        "pl_mch_cafe_station",
        "MCH",
        "t_michurinsk",
        "Кафе «Вокзальное»",
        (0.3, -0.1),
        ["parking"],
        500,
        3.8,
        "Mo-Su 08:00-22:00",
    ),
]
for pid, n, town, name, (dx, dy), tags, check, rating, hours in EXTRA_CAFES:
    add(
        pid,
        F,
        name,
        node(n, dx, dy),
        townId=town,
        tags=tags,
        avgCheckRub=check,
        rating=rating,
        openingHours=hours,
    )

# ------------------------------------------------------------------ roadside POIs laid out along chains
FUEL_BRANDS = ["Лукойл", "Роснефть", "Газпромнефть", "Татнефть", "Башнефть", "Нефтьмагистраль"]


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
        brand = FUEL_BRANDS[i % len(FUEL_BRANDS)]
        tags = ["24h"] if i % 2 == 0 else ["wc"]
        if cafe_at_fuel and i % 3 == 1:
            tags.append("cafe_at_fuel")
        if i % 4 == 0:
            tags.append("wc")
        add(
            f"pl_{code}_fuel_{int(km):03d}",
            "fuel",
            f"{brand}, {ref_at(chain, km)}, {int(km)} км",
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

TOLLS = [
    {
        "id": "ts_m12_1",
        "roadRef": "М-12",
        "nameRu": "М-12 Москва — Владимир",
        "edge": ["M12_MKAD", "M12_BOG"],
        "fromKm": 0,
        "toKm": 182,
        "tariffDayRub": "800",
        "tariffNightRub": "560",
        "asOf": AS_OF,
    },
    {
        "id": "ts_m12_2",
        "roadRef": "М-12",
        "nameRu": "М-12 Владимир — Нижний Новгород",
        "edge": ["M12_BOG", "M12_DZE"],
        "fromKm": 0,
        "toKm": 196,
        "tariffDayRub": "1000",
        "tariffNightRub": "700",
        "asOf": AS_OF,
    },
    {
        "id": "ts_m12_3",
        "roadRef": "М-12",
        "nameRu": "М-12 Нижний Новгород — Чебоксары",
        "edge": ["M12_DZE", "M12_CU"],
        "fromKm": 0,
        "toKm": 250,
        "tariffDayRub": "1100",
        "tariffNightRub": "770",
        "asOf": AS_OF,
    },
    {
        "id": "ts_m12_4",
        "roadRef": "М-12",
        "nameRu": "М-12 Чебоксары — Казань",
        "edge": ["M12_CU", "KAZ"],
        "fromKm": 0,
        "toKm": 144,
        "tariffDayRub": "600",
        "tariffNightRub": "420",
        "asOf": AS_OF,
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
