"""central_russia_v1: hand-placed lodgings."""


def apply(add, node):
    """Adds the places in their original order (the generated JSON is compared byte for byte)."""
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
