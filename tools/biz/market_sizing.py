#!/usr/bin/env python3
"""Market sizing for Verst: TAM / SAM / SOM, bottom-up first, with a top-down cross-check.

Stdlib only, deterministic. Reads tools/biz/market_assumptions.json (market inputs) and
tools/biz/assumptions.json (revenue per planned trip, through unit_economics.py) and prints Markdown
tables (Russian labels). docs/investor/market-sizing.md embeds the output between the BEGIN/END markers.

Usage:
    python3 tools/biz/market_sizing.py
    python3 tools/biz/market_sizing.py --check docs/investor/market-sizing.md

Formulas (one scenario):
    car_trips(year)  = car_trips_base_year × (1 + market_growth) ^ (year − base_year)
    TAM trips        = car_trips(year)                          every car trip with an overnight in Russia
    SAM trips        = TAM trips × share_moscow_origin × share_family_or_dog × share_app_planned
    SOM trips        = SAM trips × som_penetration_y{1,2,3}
    ₽                = trips × gross revenue per planned trip (unit_economics.per_trip()["gross"])
    top-down ceiling = trips × aggregator_share × (price_night × season × nights) × commission
                       (the whole affiliate hotel commission if every aggregator booking came through Verst)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import unit_economics as ue  # same folder: shared formatting and the per-trip revenue model

DEFAULT_MARKET = HERE / "market_assumptions.json"
DEFAULT_UE = HERE / "assumptions.json"
BEGIN = "<!-- BEGIN: tools/biz/market_sizing.py output -->"
END = "<!-- END: tools/biz/market_sizing.py output -->"
SCEN = ue.SCEN
STATUSES = ue.STATUSES
UNIT_RU = {
    "million trips per year": "млн поездок в год",
    "growth per year": "рост в год",
    "share of car trips": "доля автопоездок",
    "share of SAM trips": "доля поездок SAM",
    "share of hotel bookings": "доля броней",
}
num, pct, row, header = ue.num, ue.pct, ue.row, ue.header


def sig(x: float, digits: int = 3) -> str:
    """Round to `digits` significant figures: market sizes are not known better than that."""
    if x == 0:
        return "0"
    mag = math.floor(math.log10(abs(x)))
    dec = max(0, digits - 1 - mag)
    return num(round(x, dec), dec) if dec else num(round(x, digits - 1 - mag), 0)


# ---------------------------------------------------------------- loading and validation


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    validate(data)
    return data


def validate(data: dict) -> None:
    sources = data["sources"]
    for sid, s in sources.items():
        assert s.get("url") and s.get("title") and s.get("accessed"), f"source {sid}: url/title/accessed required"
    for key, inp in data["inputs"].items():
        for field in ("label_ru", "group", "unit", "values", "status", "sources", "reasoning", "date"):
            assert field in inp, f"input {key}: missing '{field}'"
        assert inp["unit"] in UNIT_RU, f"input {key}: unit '{inp['unit']}' has no Russian label"
        assert set(inp["values"]) == set(SCEN), f"input {key}: values must cover {SCEN}"
        for sc in SCEN:
            assert isinstance(inp["values"][sc], (int, float)), f"input {key}/{sc}: value must be a number"
            st = ue.status_of(inp, sc)
            assert st in STATUSES, f"input {key}/{sc}: status '{st}' not in {STATUSES}"
            if st == "cited":
                assert inp["sources"], f"input {key}/{sc}: cited value needs a source"
        for sid in inp["sources"]:
            assert sid in sources, f"input {key}: unknown source {sid}"
        assert inp["reasoning"].strip(), f"input {key}: reasoning required"


def values(data: dict, sc: str) -> dict[str, float]:
    return {k: float(v["values"][sc]) for k, v in data["inputs"].items()}


# ---------------------------------------------------------------- model


def compute(mk: dict, ued: dict) -> dict[str, dict]:
    """All numbers per scenario: units funnel, per-trip revenue, TAM/SAM/SOM by year, top-down ceiling."""
    base_year = mk["meta"]["base_year"]
    years = mk["meta"]["som_years"]
    out: dict[str, dict] = {}
    for sc in SCEN:
        v = values(mk, sc)
        u = ue.scenario(ued, sc)
        pt = ue.per_trip(u)
        sam_filter = v["share_moscow_origin"] * v["share_family_or_dog"] * v["share_app_planned"]
        booking_value = u["hotel_price_night"] * u["hotel_season_price_index"] * u["hotel_nights_per_booking"]
        r = {
            "v": v,
            "pt": pt,
            "rev": pt["gross"],
            "sam_filter": sam_filter,
            "booking_value": booking_value,
            "commission": u["hotel_commission"],
            "years": {},
        }
        t0 = v["car_trips_base_year"] * 1e6
        r["funnel"] = {
            "car": t0,
            "moscow": t0 * v["share_moscow_origin"],
            "family": t0 * v["share_moscow_origin"] * v["share_family_or_dog"],
            "sam": t0 * sam_filter,
        }
        for i, y in enumerate(years, 1):
            tam = t0 * (1 + v["market_growth"]) ** (y - base_year)
            sam = tam * sam_filter
            som = sam * v[f"som_penetration_y{i}"]
            ceiling_per_trip = v["aggregator_share"] * booking_value * u["hotel_commission"]
            r["years"][y] = {
                "tam": tam,
                "sam": sam,
                "som": som,
                "pen": v[f"som_penetration_y{i}"],
                "tam_rub": tam * pt["gross"],
                "sam_rub": sam * pt["gross"],
                "som_rub": som * pt["gross"],
                "tam_hotel_rub": tam * pt["hotel"],
                "tam_ceiling_rub": tam * ceiling_per_trip,
                "sam_ceiling_rub": sam * ceiling_per_trip,
                "tam_gmv": tam * booking_value,
                "sam_gmv": sam * booking_value,
            }
        out[sc] = r
    return out


# ---------------------------------------------------------------- report sections


def labels(ued: dict) -> dict[str, str]:
    return ued["meta"]["scenario_labels_ru"]


def section_inputs(mk: dict, ued: dict) -> list[str]:
    lab = labels(ued)
    out = ["### 1. Входные данные (market_assumptions.json)", ""]
    out += header("Ключ", "Параметр", "Ед.", lab["conservative"], lab["base"], lab["optimistic"], "Статус", "Ист.",
                  align="lllrrrll")
    for key, inp in mk["inputs"].items():
        three_dec = any(abs(1000 * float(z) - round(1000 * float(z))) > 1e-9 for z in inp["values"].values())
        fmt = (lambda x: num(x, 2)) if inp["unit"].startswith("million") else (
            lambda x, d=2 if three_dec else 1: pct(x, d))
        vals = [fmt(float(inp["values"][sc])) for sc in SCEN]
        sts = [ue.status_of(inp, sc) for sc in SCEN]
        st = ue.STATUS_RU[sts[0]] if len(set(sts)) == 1 else " / ".join(ue.STATUS_RU[s] for s in sts)
        out.append(row(f"`{key}`", inp["label_ru"], UNIT_RU[inp["unit"]], *vals, st, ", ".join(inp["sources"]) or "—"))
    n = {s: 0 for s in STATUSES}
    for inp in mk["inputs"].values():
        for sc in SCEN:
            n[ue.status_of(inp, sc)] += 1
    out += ["", (f"Значений во всех сценариях: {sum(n.values())}; допущений {n['assumed']}, из источников {n['cited']}, "
                f"измерено {n['measured']}. Выручка на поездку берётся из юнит-экономики (`assumptions.json`, "
                f"статусы там же). Обоснование каждого значения — поле `reasoning`."), ""]
    out += [("**Источники** (найдены веб-поиском 26.10.2026; страницы из рабочей среды не открываются, поэтому всё — "
            "«по выдержке из поиска», перед декой открыть вручную):"), ""]
    for sid, s in mk["sources"].items():
        out.append(f"- [{sid}] {s['title']}. {s['url']} (опубл.: {s['published']})")
    return out


def section_funnel(mk: dict, ued: dict, res: dict) -> list[str]:
    lab = labels(ued)
    by = mk["meta"]["base_year"]
    out = [f"### 2. Снизу вверх: счётные единицы, базовый год {by}", ""]
    out += header("Шаг", *[f"{lab[sc]}, тыс. поездок" for sc in SCEN], "Доля шага (конс. / база / оптим.)")
    steps = [
        ("Турпоездки на автомобиле по России (с ночёвкой)", "car", None),
        ("× старт в Москве и МО", "moscow", "share_moscow_origin"),
        ("× с детьми или собакой", "family", "share_family_or_dog"),
        ("× планируют в приложении или онлайн-сервисе = **SAM**", "sam", "share_app_planned"),
    ]
    for label, k, inp in steps:
        share = "—" if inp is None else " / ".join(pct(res[sc]["v"][inp], 1) for sc in SCEN)
        out.append(row(label, *[sig(res[sc]["funnel"][k] / 1e3) for sc in SCEN], share))
    out += ["", "SAM как доля всех автопоездок: " + " / ".join(pct(res[sc]["sam_filter"], 2) for sc in SCEN) + "."]
    return out


def section_revenue(ued: dict, res: dict) -> list[str]:
    lab = labels(ued)
    out = ["### 3. Выручка на одну запланированную поездку (из юнит-экономики, до налога)", ""]
    out += header("Поток, ₽ на поездку", *[lab[sc] for sc in SCEN])
    for label, k in (("Отели (партнёрка)", "hotel"), ("Экскурсии (партнёрка)", "excursion"),
                     ("Trip Pro (в консерв. = 0)", "pro"), ("**Итого до налога**", "gross"),
                     ("для справки: чистыми после 6 % налога", "net")):
        out.append(row(label, *[num(res[sc]["pt"][k], 2) for sc in SCEN]))
    out += ["", ("B2G-пилоты, спонсорские остановки и лицензирование не масштабируются с числом поездок и в TAM/SAM/SOM "
                "не входят (они в финансовой модели отдельными строками).")]
    return out


def section_tss(mk: dict, ued: dict, res: dict) -> list[str]:
    lab = labels(ued)
    out = ["### 4. TAM, SAM и SOM на три года", ""]
    out += header("Сценарий", "Год", "TAM, млн поездок", "TAM, млн ₽", "SAM, тыс. поездок", "SAM, млн ₽",
                  "SOM, % SAM", "SOM, тыс. поездок", "SOM, тыс. ₽", align="llrrrrrrr")
    for sc in SCEN:
        for y, t in res[sc]["years"].items():
            out.append(row(lab[sc], str(y), sig(t["tam"] / 1e6), sig(t["tam_rub"] / 1e6),
                           sig(t["sam"] / 1e3), sig(t["sam_rub"] / 1e6), pct(t["pen"], 2),
                           sig(t["som"] / 1e3), sig(t["som_rub"] / 1e3)))
    out += ["", ("TAM — все автопоездки с ночёвкой по России × выручка Версты на поездку, как если бы каждую из них "
                "планировали в Версте. SAM — только поездки из Москвы и МО, с детьми или собакой, которые планируют "
                "в приложении. SOM — доля SAM, которую Верста реально спланирует (допущение, сверено с финансовой "
                "моделью).")]
    return out


def section_topdown(mk: dict, ued: dict, res: dict) -> list[str]:
    lab = labels(ued)
    ref = mk["reference"]
    y1 = mk["meta"]["som_years"][0]
    out = ["### 5. Сверка сверху вниз", "",
           "**5.1. Сколько автопоездок с ночёвкой в год: разные источники**", ""]
    out += header("Оценка", "Млн в год", "Что считает", "Ист.", align="lrll")
    rows_ = [
        ("Минэкономразвития, 2023", num(ref["car_trips_2023_mln"], 1), "турпоездки на автомобиле", "M02"),
        ("Минэкономразвития, автотуристы", (f"{num(ref['minec_car_tourists_mln'][0], 0)}–"
                                           f"{num(ref['minec_car_tourists_mln'][1], 0)}"), "люди, не поездки", "M04"),
        ("РСТ, автотуристы (верхняя оценка)", f"до {num(ref['rst_car_tourists_max_mln'], 0)}", "люди, не поездки",
         "M04"),
        ("Росстат 2025: размещённые в КСР × доля авто 38 %",
         num(ref["ksr_guests_2025_mln"] * ref["car_share_2024"], 2), "гости гостиниц × доля туристов на авто", "M01, M03"),
        ("Росстат 2025: размещённые в КСР × доля авто 43 % (прогноз)",
         num(ref["ksr_guests_2025_mln"] * ref["car_share_2025_forecast"], 2), "то же", "M01, M03"),
        ("Цель концепции автотуризма на 2030", num(ref["car_trips_2030_target_mln"], 0), "цель, не прогноз", "M02"),
    ]
    for r in rows_:
        out.append(row(*r))
    out += ["", (f"Модель берёт {' / '.join(num(res[sc]['v']['car_trips_base_year'], 2) for sc in SCEN)} млн "
                f"(конс. / база / оптим.) — внутри разброса источников. Расхождение самих источников велико: "
                f"Росстат за 2023 год встречается и как {num(ref['ksr_guests_2023_tourdom_mln'], 0)}, и как "
                f"{num(ref['ksr_guests_2023_chernyshenko_mln'], 1)} млн размещённых (M11, M01), поэтому точность выше "
                f"«≈ 25–40 млн поездок» не заявляем."), ""]
    out += [(f"**5.2. Потолок партнёрки по отелям, {y1} год** (сверху вниз: если бы каждая бронь через агрегатор "
            f"шла по ссылке Версты)"), ""]
    out += header("Показатель", *[lab[sc] for sc in SCEN])
    t = {sc: res[sc]["years"][y1] for sc in SCEN}
    out.append(row("Автопоездок, млн", *[sig(t[sc]["tam"] / 1e6) for sc in SCEN]))
    out.append(row("× доля броней через агрегаторы", *[pct(res[sc]["v"]["aggregator_share"], 0) for sc in SCEN]))
    out.append(row("× сумма брони, ₽ (цена ночи × сезон × ночей)", *[num(res[sc]["booking_value"], 0) for sc in SCEN]))
    out.append(row("× комиссия вебмастеру", *[pct(res[sc]["commission"], 0) for sc in SCEN]))
    out.append(row("**= потолок комиссии, вся Россия, млн ₽**", *[sig(t[sc]["tam_ceiling_rub"] / 1e6) for sc in SCEN]))
    out.append(row("**= потолок комиссии в SAM, млн ₽**", *[sig(t[sc]["sam_ceiling_rub"] / 1e6) for sc in SCEN]))
    out.append(row("Снизу вверх: строка отелей в TAM, млн ₽", *[sig(t[sc]["tam_hotel_rub"] / 1e6) for sc in SCEN]))
    out.append(row("Снизу вверх ÷ потолок", *[pct(t[sc]["tam_hotel_rub"] / t[sc]["tam_ceiling_rub"], 1)
                                              for sc in SCEN]))
    out += ["", ("Снизу вверх берёт из потолка лишь малую часть: на поездку приходится клик, конверсия в бронь, отмены и "
                "потеря атрибуции (юнит-экономика, воронка партнёрки). Это и есть главная проверка: модель Версты не "
                "обещает больше денег, чем существует на рынке, и показывает, во сколько раз выросла бы выручка, если "
                "бы Верста стала каналом бронирования, а не ссылкой."), ""]
    out += [(f"**5.3. Оборот ночёвок в автопоездках, {y1} год** (деньги путешественников, не выручка Версты; "
            f"для разговора с отелями, BIZ-02)"), ""]
    out += header("Показатель", *[lab[sc] for sc in SCEN])
    out.append(row("Оборот ночёвок, вся Россия, млрд ₽", *[sig(t[sc]["tam_gmv"] / 1e9) for sc in SCEN]))
    out.append(row("Оборот ночёвок в SAM, млрд ₽", *[sig(t[sc]["sam_gmv"] / 1e9) for sc in SCEN]))
    out += ["", ("Верхняя граница: считаем, что в каждой поездке есть одна оплаченная бронь. Часть автотуристов ночует "
                "у родственников или на дачах, поэтому реальный оборот ниже.")]
    return out


def section_sensitivity(mk: dict, ued: dict, res: dict) -> list[str]:
    y1 = mk["meta"]["som_years"][0]
    base = res["base"]
    out = [(f"### 6. Чувствительность SAM в рублях, {y1} год (база; один параметр — в консервативное и "
           f"оптимистичное значение)"), ""]
    out += header("Параметр", "Конс. → оптим.", "SAM при конс., млн ₽", "SAM при оптим., млн ₽", "Размах, млн ₽",
                  align="lrrrr")
    t_base = base["years"][y1]
    items = []
    for key in ("car_trips_base_year", "market_growth", "share_moscow_origin", "share_family_or_dog",
                "share_app_planned"):
        lo_v, hi_v = (float(mk["inputs"][key]["values"][s]) for s in ("conservative", "optimistic"))
        sam_lo = t_base["sam_rub"] * scale(mk, key, lo_v, base["v"], y1)
        sam_hi = t_base["sam_rub"] * scale(mk, key, hi_v, base["v"], y1)
        fmt = (lambda x: num(x, 2)) if key == "car_trips_base_year" else (lambda x: pct(x, 1))
        items.append((f"`{key}`", f"{fmt(lo_v)} → {fmt(hi_v)}", sam_lo, sam_hi))
    rlo, rhi = res["conservative"]["rev"], res["optimistic"]["rev"]
    items.append(("выручка на поездку (юнит-экономика)", f"{num(rlo, 2)} → {num(rhi, 2)} ₽",
                  t_base["sam_rub"] * rlo / base["rev"], t_base["sam_rub"] * rhi / base["rev"]))
    items.sort(key=lambda x: -(x[3] - x[2]))
    for name, rng, lo, hi in items:
        out.append(row(name, rng, sig(lo / 1e6), sig(hi / 1e6), sig((hi - lo) / 1e6)))
    out += ["", (f"База: SAM {y1} = {sig(t_base['sam_rub'] / 1e6)} млн ₽. Самый сильный рычаг — выручка на поездку, "
                f"а не размер рынка.")]
    return out


def scale(mk: dict, key: str, new: float, v: dict[str, float], year: int) -> float:
    """Multiplier on base SAM when one input changes to `new`."""
    if key == "market_growth":
        n = year - mk["meta"]["base_year"]
        return ((1 + new) / (1 + v[key])) ** n
    return new / v[key]


# ---------------------------------------------------------------- self-check


def self_check(mk: dict, ued: dict, res: dict) -> int:
    n = 0

    def ok(cond: bool, msg: str) -> None:
        nonlocal n
        assert cond, f"self-check failed: {msg}"
        n += 1

    ref = mk["reference"]
    vb, vo, vc = (res[s]["v"] for s in ("base", "optimistic", "conservative"))
    ok(abs(ref["ksr_guests_2025_mln"] * ref["car_share_2024"] - vb["car_trips_base_year"]) < 0.01,
       "base car trips = KSR 2025 × 38 %")
    ok(abs(ref["ksr_guests_2025_mln"] * ref["car_share_2025_forecast"] - vo["car_trips_base_year"]) < 0.01,
       "optimistic car trips = KSR 2025 × 43 %")
    ok(abs(ref["car_trips_2023_mln"] - vc["car_trips_base_year"]) < 1e-9, "conservative car trips = MinEc 2023")
    ok(abs(ref["ksr_guests_2025_mln"] / ref["ksr_guests_2024_mln"] - 1 - vc["market_growth"]) < 0.0005,
       "conservative growth = KSR 2025 / 2024")
    ok(abs((ref["car_trips_2030_target_mln"] / ref["car_trips_2023_mln"]) ** (1 / 7) - 1 - vo["market_growth"]) < 0.0005,
       "optimistic growth = 2030 target CAGR")
    ok(abs(ref["moscow_agglomeration_mln"] / ref["russia_population_mln"] - vc["share_moscow_origin"]) < 0.0005,
       "conservative Moscow share = population share")
    years = mk["meta"]["som_years"]
    for sc in SCEN:
        r = res[sc]
        ok(abs(r["funnel"]["sam"] - r["funnel"]["car"] * r["sam_filter"]) < 1e-6, f"{sc}: SAM = car × filters")
        prev = 0.0
        for y in years:
            t = r["years"][y]
            ok(t["tam"] >= t["sam"] >= t["som"] > 0, f"{sc}/{y}: TAM ≥ SAM ≥ SOM > 0")
            ok(t["pen"] <= 0.05, f"{sc}/{y}: SOM ≤ 5 % of SAM (new-entrant ceiling)")
            ok(t["tam_hotel_rub"] <= t["tam_ceiling_rub"], f"{sc}/{y}: bottom-up hotel revenue ≤ top-down ceiling")
            ok(t["som"] >= prev, f"{sc}/{y}: SOM does not fall year to year")
            prev = t["som"]
            # independent second computation of SOM ₽
            som2 = (r["v"]["car_trips_base_year"] * 1e6 * (1 + r["v"]["market_growth"]) ** (y - mk["meta"]["base_year"])
                    * r["v"]["share_moscow_origin"] * r["v"]["share_family_or_dog"] * r["v"]["share_app_planned"]
                    * t["pen"] * r["rev"])
            ok(abs(som2 - t["som_rub"]) < 1e-6, f"{sc}/{y}: SOM ₽ recomputed a second way")
    for y in years:
        for k in ("tam_rub", "sam_rub", "som_rub"):
            ok(res["conservative"]["years"][y][k] <= res["base"]["years"][y][k] <= res["optimistic"]["years"][y][k],
               f"{y}/{k}: conservative ≤ base ≤ optimistic")
    return n


# ---------------------------------------------------------------- main


def report(mk: dict, ued: dict) -> str:
    res = compute(mk, ued)
    n = self_check(mk, ued, res)
    parts = [
        section_inputs(mk, ued),
        section_funnel(mk, ued, res),
        section_revenue(ued, res),
        section_tss(mk, ued, res),
        section_topdown(mk, ued, res),
        section_sensitivity(mk, ued, res),
        [(f"Самопроверка скрипта: пройдено проверок — {n} (пересчёт входных данных из справочных значений, "
         f"SAM = произведение фильтров, TAM ≥ SAM ≥ SOM, SOM ≤ 5 % SAM, снизу вверх ≤ потолка сверху вниз, "
         f"повторный расчёт SOM в рублях, порядок сценариев). Модель v{mk['meta']['version']}, допущения на "
         f"{mk['meta']['as_of']}; юнит-экономика v{ued['meta']['version']} на {ued['meta']['as_of']}.")],
    ]
    return "\n\n".join("\n".join(p) for p in parts) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--market", type=Path, default=DEFAULT_MARKET)
    ap.add_argument("--assumptions", type=Path, default=DEFAULT_UE)
    ap.add_argument("--check", type=Path, metavar="MD", help="verify the block embedded in MD matches the output")
    args = ap.parse_args(argv)
    out = report(load(args.market), ue.load(args.assumptions))
    if args.check:
        block = embedded_block(args.check.read_text(encoding="utf-8"))
        if block is None:
            print(f"{args.check}: markers not found", file=sys.stderr)
            return 1
        if block != out:
            print(f"{args.check}: embedded output is STALE — re-run and paste", file=sys.stderr)
            return 1
        print(f"{args.check}: embedded output matches ({len(out.splitlines())} lines)")
        return 0
    sys.stdout.write(out)
    return 0


def embedded_block(md: str) -> str | None:
    if BEGIN not in md or END not in md:
        return None
    return md.split(BEGIN, 1)[1].split(END, 1)[0].strip("\n") + "\n"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
