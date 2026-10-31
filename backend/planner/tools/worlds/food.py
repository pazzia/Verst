"""central_russia_v1: hand-placed food in towns."""


def apply(add, node):
    """Adds the places in their original order (the generated JSON is compared byte for byte)."""
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
