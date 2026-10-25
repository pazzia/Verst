#!/usr/bin/env python3
"""BIZ-01 unit economics for Verst: revenue per planned trip versus acquisition cost.

Stdlib only. Reads tools/biz/assumptions.json and prints Markdown tables (Russian labels) to stdout,
deterministically. docs/traction/unit-economics.md embeds this output between the BEGIN/END markers.

Usage:
    python3 tools/biz/unit_economics.py                      # print the tables
    python3 tools/biz/unit_economics.py --check docs/traction/unit-economics.md
                                                             # exit 1 if the embedded block is stale
    python3 tools/biz/unit_economics.py --assumptions other.json

Formulas (per planned trip, one scenario):
    hotel  = ctr × conversion × (1 − cancellation) × (1 − leakage) × price_night × season_index × nights × commission
    excur. = ctr × conversion × (1 − loss) × avg_check × commission
    pro    = (planner_to_paid / trips_per_planner) × price_year × (1 − store_fee)
    net    = (hotel + excursions + pro) × (1 − tax)
    trips_per_install   = install_to_planner × trips_per_planner
    cost per paid trip  = cpi / trips_per_install
    monthly: paid trips = ads / cost per trip; organic trips needed = (burn − fixed contracts − paid × net) / net
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_ASSUMPTIONS = HERE / "assumptions.json"
BEGIN = "<!-- BEGIN: tools/biz/unit_economics.py output -->"
END = "<!-- END: tools/biz/unit_economics.py output -->"
SCEN = ("conservative", "base", "optimistic")
STATUSES = ("assumed", "measured", "cited")
STATUS_RU = {"assumed": "допущение", "measured": "измерено", "cited": "источник"}
UNIT_RU = {
    "share of planned trips": "доля поездок",
    "share of trips with a hotel click": "доля поездок с кликом",
    "RUB per room-night": "₽ за номер-ночь",
    "nights per booking": "ночей",
    "multiplier vs annual average": "× к среднегодовой",
    "share of paid bookings": "доля броней",
    "share of Verst-driven bookings not credited": "доля броней",
    "share of completed booking value": "доля суммы",
    "share of trips with an excursion click": "доля поездок с кликом",
    "RUB per order": "₽ за заказ",
    "share of orders not credited": "доля заказов",
    "share of order value": "доля суммы",
    "share of installs": "доля установок",
    "share of activated users": "доля активных",
    "RUB per paying user per year": "₽ в год",
    "share of Pro price": "доля цены",
    "RUB per install": "₽ за установку",
    "planned trips per activated user": "поездок",
    "share of revenue": "доля выручки",
    "pilots per year": "пилотов в год",
    "RUB per pilot per year": "₽ за пилот",
    "businesses": "точек",
    "RUB per business per month": "₽ в месяц",
    "RUB per month": "₽ в месяц",
    "RUB per month incl. taxes": "₽ в месяц",
    "ratio of organic planned trips": "доля",
}
PER_TRIP_GROUPS = ("hotel", "excursion", "pro", "acquisition", "tax")
AFFILIATE_GROUPS = ("hotel", "excursion", "tax")
BURN_KEYS = ("burn_hosting", "burn_curator", "burn_ads", "burn_accounting", "burn_tools")


# ---------------------------------------------------------------- formatting (Russian style, deterministic)


def num(x: float, dec: int = 0) -> str:
    """1234567.891 → '1 234 567,89' (regular spaces, decimal comma)."""
    if x is None or (isinstance(x, float) and math.isinf(x)):
        return "∞"
    s = f"{x:,.{dec}f}"
    if float(s.replace(",", "")) == 0:
        s = s.lstrip("-")  # no "−0,00"
    return s.replace(",", " ").replace(".", ",").replace("-", "−")


def pct(x: float, dec: int = 1) -> str:
    return num(100 * x, dec) + " %"


def value_str(inp: dict, x: float) -> str:
    """One format per input, so all three scenarios of a row read alike."""
    unit, vals = inp["unit"], [float(v) for v in inp["values"].values()]
    if unit.startswith("share") or unit.startswith("ratio"):
        whole = all(abs(100 * v - round(100 * v)) < 1e-9 for v in vals)
        return pct(x, 0 if whole else 1)
    if unit.startswith("RUB"):
        return num(x, 0)
    return num(x, 0 if all(abs(v - round(v)) < 1e-9 for v in vals) else 2)


def row(*cells: str) -> str:
    return "| " + " | ".join(cells) + " |"


def header(*cells: str, align: str = "") -> list[str]:
    al = align or ("l" + "r" * (len(cells) - 1))
    return [row(*cells), row(*[":---" if a == "l" else "---:" for a in al])]


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
            st = status_of(inp, sc)
            assert st in STATUSES, f"input {key}/{sc}: status '{st}' not in {STATUSES}"
            if st == "cited":
                assert inp["sources"], f"input {key}/{sc}: cited value needs a source"
        for sid in inp["sources"]:
            assert sid in sources, f"input {key}: unknown source {sid}"
        assert inp["reasoning"].strip(), f"input {key}: reasoning required"


def status_of(inp: dict, sc: str) -> str:
    st = inp["status"]
    return st[sc] if isinstance(st, dict) else st


def scenario(data: dict, sc: str) -> dict[str, float]:
    return {k: float(v["values"][sc]) for k, v in data["inputs"].items()}


# ---------------------------------------------------------------- model


def per_trip(v: dict[str, float]) -> dict[str, float]:
    """Revenue per planned trip by stream (gross and net of tax) plus the funnel behind it."""
    h_click = v["hotel_ctr"]
    h_paid = h_click * v["hotel_booking_conversion"]
    h_credited = h_paid * (1 - v["hotel_cancellation_rate"]) * (1 - v["hotel_attribution_leakage"])
    h_value = v["hotel_price_night"] * v["hotel_season_price_index"] * v["hotel_nights_per_booking"]
    hotel = h_credited * h_value * v["hotel_commission"]

    e_click = v["exc_ctr"]
    e_paid = e_click * v["exc_conversion"]
    e_credited = e_paid * (1 - v["exc_loss_rate"])
    excursion = e_credited * v["exc_avg_check"] * v["exc_commission"]

    tpi = v["install_to_planner"] * v["trips_per_planner"]
    pro_payers = v["pro_planner_to_paid"] / v["trips_per_planner"]
    pro = pro_payers * v["pro_price_year"] * (1 - v["store_fee"])

    keep = 1 - v["revenue_tax_rate"]
    gross = hotel + excursion + pro
    return {
        "h_click": h_click,
        "h_paid": h_paid,
        "h_credited": h_credited,
        "h_value": h_value,
        "hotel": hotel,
        "e_click": e_click,
        "e_paid": e_paid,
        "e_credited": e_credited,
        "excursion": excursion,
        "pro_payers": pro_payers,
        "pro": pro,
        "gross": gross,
        "tax": gross * v["revenue_tax_rate"],
        "net": gross * keep,
        "affiliate_net": (hotel + excursion) * keep,
        "tpi": tpi,
        "cost_per_trip": v["cpi"] / tpi,
        "net_per_hotel_booking": h_value * v["hotel_commission"] * keep,
    }


def fixed_monthly_net(v: dict[str, float]) -> dict[str, float]:
    b2g = v["b2g_pilots_per_year"] * v["b2g_revenue_per_pilot"] / 12
    sponsored = v["sponsored_businesses"] * v["sponsored_fee_month"]
    return {"b2g": b2g, "sponsored": sponsored, "net": (b2g + sponsored) * (1 - v["revenue_tax_rate"])}


def breakeven(v: dict[str, float], r: float, fixed: float) -> dict[str, float]:
    """Trips per month so that revenue covers the whole burn; ads buy paid trips at cost_per_trip.

    organic × r + paid × r + fixed = burn  →  organic = (burn − fixed − paid × r) / r  (floored at 0).
    Weak month: organic volume × low_month_volume_index, paid volume unchanged.
    """
    burn = sum(v[k] for k in BURN_KEYS)
    paid = v["burn_ads"] / per_trip(v)["cost_per_trip"]
    base = {"burn": burn, "paid": paid, "r": r, "fixed": fixed}
    if r <= 0:
        return {**base, "organic": math.inf, "total": math.inf, "weak": math.inf}
    organic = max(0.0, (burn - fixed - paid * r) / r)
    weak = organic / v["low_month_volume_index"] + paid
    return {**base, "organic": organic, "total": organic + paid, "weak": weak}


# ---------------------------------------------------------------- report sections


def section_inputs(data: dict) -> list[str]:
    lab = data["meta"]["scenario_labels_ru"]
    out = ["### 1. Входные данные (assumptions.json)", ""]
    out += header("Ключ", "Параметр", "Ед.", lab["conservative"], lab["base"], lab["optimistic"], "Статус", "Ист.",
                  align="lllrrrll")
    for key, inp in data["inputs"].items():
        vals = [value_str(inp, inp["values"][sc]) for sc in SCEN]
        sts = [status_of(inp, sc) for sc in SCEN]
        st = STATUS_RU[sts[0]] if len(set(sts)) == 1 else " / ".join(STATUS_RU[s] for s in sts)
        src = ", ".join(inp["sources"]) or "—"
        out.append(row(f"`{key}`", inp["label_ru"], UNIT_RU[inp["unit"]], *vals, st, src))
    n = {s: 0 for s in STATUSES}
    for inp in data["inputs"].values():
        for sc in SCEN:
            n[status_of(inp, sc)] += 1
    total = sum(n.values())
    out += ["", f"Значений во всех сценариях: {total}; допущений {n['assumed']}, из источников {n['cited']}, "
                f"измерено {n['measured']}. Обоснование каждого значения — поле `reasoning` в assumptions.json.", ""]
    out += ["**Источники** (дата доступа 2026-10-25; цитаты получены через веб-поиск, страницы перепроверить вручную):", ""]
    for sid, s in data["sources"].items():
        out.append(f"- [{sid}] {s['title']}. {s['url']} (опубл.: {s['published']})")
    return out


def section_revenue(data: dict, res: dict[str, dict]) -> list[str]:
    lab = data["meta"]["scenario_labels_ru"]
    out = ["### 2. Выручка на одну запланированную поездку и на 1 000 поездок", ""]
    cols = [f"{lab[sc]}, ₽/поездка" for sc in SCEN] + [f"{lab[sc]}, ₽/1 000" for sc in SCEN]
    out += header("Поток", *cols)
    lines = [
        ("Отели (Travelpayouts → Яндекс Путешествия / Островок)", "hotel"),
        ("Экскурсии (Travelpayouts → Tripster)", "excursion"),
        ("Trip Pro (в MVP оплат нет; консерв. = 0)", "pro"),
        ("**Итого до налога**", "gross"),
        (f"Налог ({pct(data['inputs']['revenue_tax_rate']['values']['base'], 0)})", "tax"),
        ("**Итого чистыми**", "net"),
        ("в т. ч. только партнёрка (отели + экскурсии), чистыми", "affiliate_net"),
    ]
    for label, k in lines:
        sign = -1 if k == "tax" else 1
        out.append(row(label, *[num(sign * res[sc][k], 2) for sc in SCEN],
                       *[num(sign * 1000 * res[sc][k], 0) for sc in SCEN]))
    out += ["", "Воронка партнёрки на 1 000 запланированных поездок:", ""]
    out += header("Шаг", *[lab[sc] for sc in SCEN])
    funnel = [
        ("Поездок с кликом «Забронировать ночь»", lambda r: num(1000 * r["h_click"], 1)),
        ("Оплаченных броней", lambda r: num(1000 * r["h_paid"], 2)),
        ("Засчитанных броней (минус отмены и потеря атрибуции)", lambda r: num(1000 * r["h_credited"], 2)),
        ("Сумма одной брони, ₽ (цена ночи × сезон × ночей)", lambda r: num(r["h_value"], 0)),
        ("Чистый доход с одной засчитанной брони, ₽", lambda r: num(r["net_per_hotel_booking"], 0)),
        ("Поездок с кликом на экскурсию", lambda r: num(1000 * r["e_click"], 1)),
        ("Засчитанных экскурсий", lambda r: num(1000 * r["e_credited"], 2)),
        ("Покупок Pro (на 1 000 поездок)", lambda r: num(1000 * r["pro_payers"], 2)),
    ]
    for label, f in funnel:
        out.append(row(label, *[f(res[sc]) for sc in SCEN]))
    return out


def section_acquisition(data: dict, res: dict[str, dict]) -> list[str]:
    lab = data["meta"]["scenario_labels_ru"]
    out = ["### 3. Платное привлечение и точка безубыточности на поездку", ""]
    out += header("Показатель", *[lab[sc] for sc in SCEN])
    vals = {sc: scenario(data, sc) for sc in SCEN}
    rows = [
        ("Цена установки (CPI), ₽ — допущение, VAL-02 измерит", lambda sc: num(vals[sc]["cpi"], 0)),
        ("Поездок на одну установку", lambda sc: num(res[sc]["tpi"], 2)),
        ("**Стоимость одной платной поездки, ₽**", lambda sc: "**" + num(res[sc]["cost_per_trip"], 0) + "**"),
        ("Безубыточная цена поездки: только партнёрка, ₽", lambda sc: num(res[sc]["affiliate_net"], 2)),
        ("Безубыточная цена поездки: все потоки на поездку, ₽", lambda sc: num(res[sc]["net"], 2)),
        ("Безубыточный CPI: только партнёрка, ₽", lambda sc: num(res[sc]["affiliate_net"] * res[sc]["tpi"], 2)),
        ("Безубыточный CPI: все потоки на поездку, ₽", lambda sc: num(res[sc]["net"] * res[sc]["tpi"], 2)),
        ("Партнёрка покрывает стоимость платной поездки на",
         lambda sc: pct(res[sc]["affiliate_net"] / res[sc]["cost_per_trip"], 2)),
        ("Все потоки на поездку покрывают её на", lambda sc: pct(res[sc]["net"] / res[sc]["cost_per_trip"], 2)),
        ("Результат одной платной поездки (все потоки − стоимость), ₽",
         lambda sc: num(res[sc]["net"] - res[sc]["cost_per_trip"], 0)),
        ("Нужно засчитанных броней отеля на 100 поездок, чтобы отели одни окупили платную поездку",
         lambda sc: num(100 * res[sc]["cost_per_trip"] / res[sc]["net_per_hotel_booking"], 1)),
        ("… а модель даёт засчитанных броней на 100 поездок", lambda sc: num(100 * res[sc]["h_credited"], 2)),
        ("Разрыв (нужно ÷ даёт), раз",
         lambda sc: num(res[sc]["cost_per_trip"] / res[sc]["net_per_hotel_booking"] / res[sc]["h_credited"], 0)),
    ]
    for label, f in rows:
        out.append(row(label, *[f(sc) for sc in SCEN]))
    return out


def section_fixed(data: dict) -> list[str]:
    lab = data["meta"]["scenario_labels_ru"]
    out = ["### 4. Контрактные потоки (не на поездку): B2G и спонсорские остановки, ₽ в месяц", ""]
    out += header("Поток", *[lab[sc] for sc in SCEN])
    fx = {sc: fixed_monthly_net(scenario(data, sc)) for sc in SCEN}
    out.append(row("B2G: пилоты × выручка / 12", *[num(fx[sc]["b2g"], 0) for sc in SCEN]))
    out.append(row("Спонсорские остановки: точки × плата", *[num(fx[sc]["sponsored"], 0) for sc in SCEN]))
    out.append(row("**Итого чистыми (после налога)**", *[num(fx[sc]["net"], 0) for sc in SCEN]))
    out += ["", "Лицензирование движка (BIZ-05) исключено из расчёта: " + data["reference"]["licensing"]["note_ru"]]
    return out


def section_breakeven(data: dict, res: dict[str, dict]) -> list[str]:
    lab = data["meta"]["scenario_labels_ru"]
    out = ["### 5. Месячные расходы и сколько поездок нужно для безубыточности", ""]
    out += header("Статья расходов, ₽ в месяц", *[lab[sc] for sc in SCEN])
    vals = {sc: scenario(data, sc) for sc in SCEN}
    for k in BURN_KEYS:
        out.append(row(data["inputs"][k]["label_ru"].replace("Расходы: ", ""), *[num(vals[sc][k], 0) for sc in SCEN]))
    out.append(row("**Итого расходов (без оплаты основателей)**",
                   *["**" + num(sum(vals[sc][k] for k in BURN_KEYS), 0) + "**" for sc in SCEN]))
    out.append(row("Платных поездок на рекламный бюджет", *[num(vals[sc]["burn_ads"] / res[sc]["cost_per_trip"], 0)
                                                            for sc in SCEN]))
    out += ["", "Поездок в месяц для покрытия всех расходов (органические + купленные рекламой):", ""]
    out += header("Вариант выручки", *[f"{lab[sc]}: органич." for sc in SCEN], *[f"{lab[sc]}: всего" for sc in SCEN])
    variants = breakeven_variants(data, res)
    for label, be in variants:
        out.append(row(label, *[num(be[sc]["organic"], 0) for sc in SCEN], *[num(be[sc]["total"], 0) for sc in SCEN]))
    out += ["", "Каждые дополнительные 10 000 ₽ месячных расходов требуют ещё органических поездок в месяц:", ""]
    out += header("Вариант выручки", *[lab[sc] for sc in SCEN])
    for label, be in variants:
        out.append(row(label, *[num(10000 / be[sc]["r"], 0) if be[sc]["r"] > 0 else "∞" for sc in SCEN]))
    out += ["", "С учётом сезонности: сколько поездок нужно в средний месяц, чтобы и самый слабый месяц "
                "покрывал расходы (органика в слабый месяц = средняя × `low_month_volume_index`):", ""]
    out += header("Вариант выручки", *[lab[sc] for sc in SCEN])
    for label, be in variants:
        out.append(row(label, *[num(be[sc]["weak"], 0) for sc in SCEN]))
    return out


def breakeven_variants(data: dict, res: dict[str, dict]) -> list[tuple[str, dict]]:
    out = []
    for label, rk, with_fixed in (
        ("Только партнёрка (отели + экскурсии)", "affiliate_net", False),
        ("Все потоки на поездку (+ Trip Pro)", "net", False),
        ("Все потоки + контракты B2G и спонсоров", "net", True),
    ):
        be = {}
        for sc in SCEN:
            v = scenario(data, sc)
            be[sc] = breakeven(v, res[sc][rk], fixed_monthly_net(v)["net"] if with_fixed else 0.0)
        out.append((label, be))
    return out


def tornado(data: dict, metric, groups: tuple[str, ...]) -> list[tuple[str, float, float, float, float, float]]:
    """One-at-a-time swing: each input to its conservative and optimistic value, the rest at base."""
    base = scenario(data, "base")
    rows = []
    for key, inp in data["inputs"].items():
        if inp["group"] not in groups:
            continue
        lo_v, hi_v = inp["values"]["conservative"], inp["values"]["optimistic"]
        if lo_v == hi_v:
            continue
        lo = metric({**base, key: float(lo_v)})
        hi = metric({**base, key: float(hi_v)})
        if abs(hi - lo) < 1e-9:
            continue  # the input does not enter this metric
        rows.append((key, lo_v, hi_v, lo, hi, abs(hi - lo)))
    rows.sort(key=lambda r: (-round(r[5], 9), r[0]))
    return rows


def section_sensitivity(data: dict) -> list[str]:
    out = ["### 6. Чувствительность (база; каждый параметр по очереди ставится в консервативное и оптимистичное "
           "значение)", ""]
    specs = [
        ("6.1. Чистая выручка на поездку, все потоки, ₽", lambda v: per_trip(v)["net"], PER_TRIP_GROUPS, None),
        ("6.2. Чистая выручка партнёрки на поездку, ₽", lambda v: per_trip(v)["affiliate_net"], AFFILIATE_GROUPS, 5),
        ("6.3. Результат одной платной поездки (выручка − стоимость), ₽",
         lambda v: per_trip(v)["net"] - per_trip(v)["cost_per_trip"], PER_TRIP_GROUPS, 5),
    ]
    base = scenario(data, "base")
    for title, metric, groups, limit in specs:
        rows = tornado(data, metric, groups)
        shown = rows if limit is None else rows[:limit]
        out += [f"**{title}** — база: {num(metric(base), 2)}", ""]
        out += header("#", "Параметр", "Конс. → оптим. значение", "Результат при конс.", "Результат при оптим.",
                      "Размах", align="llrrrr")
        for i, (k, lo_v, hi_v, lo, hi, sw) in enumerate(shown, 1):
            inp = data["inputs"][k]
            name = f"`{k}`"
            if i <= 3:
                name = f"**{name}**"
            out.append(row(str(i), name, f"{value_str(inp, lo_v)} → {value_str(inp, hi_v)}", num(lo, 2), num(hi, 2),
                           num(sw, 2)))
        top = ", ".join(f"`{r[0]}`" for r in rows[:3])
        out += ["", f"Три самых влиятельных параметра: {top}.", ""]
    return out[:-1]


def section_crosschecks(data: dict, res: dict[str, dict]) -> list[str]:
    rv = data["reference"]["review_estimate"]
    review = rv["ctr"] * rv["booking_conversion"] * rv["booking_value_rub"] * rv["commission"]
    eng = data["reference"]["engine_lodging"]
    family_mid = eng["night_by_population_rub"]["100k_to_1m"] * eng["family_room_factor"]
    cited = data["inputs"]["hotel_price_night"]["values"]["base"]
    out = ["### 7. Сверки", ""]
    out.append(f"- Формула ревью: {pct(rv['ctr'], 0)} × {pct(rv['booking_conversion'], 0)} × "
               f"{num(rv['booking_value_rub'])} ₽ × {pct(rv['commission'], 0)} = **{num(review, 2)} ₽** на поездку "
               f"(в ревью округлено до ≈ {rv['stated_result_rub_per_trip']} ₽). Ревью не учитывает отмены, потерю "
               f"атрибуции и налог; с ними та же формула даёт "
               f"{num(review * (1 - data['inputs']['hotel_cancellation_rate']['values']['base']) * (1 - data['inputs']['hotel_attribution_leakage']['values']['base']) * (1 - data['inputs']['revenue_tax_rate']['values']['base']), 2)} ₽ "
               f"при базовых отменах и потерях.")
    out.append(f"- Отели в модели, база: {num(res['base']['hotel'], 2)} ₽ до налога на поездку; "
               f"оптимистичный сценарий: {num(res['optimistic']['hotel'], 2)} ₽.")
    out.append(f"- Цена ночи: семейный номер в движке для города 100 тыс.–1 млн = {num(eng['night_by_population_rub']['100k_to_1m'])} × "
               f"{num(eng['family_room_factor'], 1)} = {num(family_mid)} ₽; Яндекс Путешествия, ЦФО 2025 = {num(cited)} ₽ "
               f"(расхождение {pct(family_mid / cited - 1, 1)}).")
    return out


# ---------------------------------------------------------------- self-check


def self_check(data: dict, res: dict[str, dict]) -> int:
    n = 0

    def ok(cond: bool, msg: str) -> None:
        nonlocal n
        assert cond, f"self-check failed: {msg}"
        n += 1

    for sc in SCEN:
        r = res[sc]
        ok(abs(r["hotel"] + r["excursion"] + r["pro"] - r["gross"]) < 1e-9, f"{sc}: streams sum to gross")
        ok(abs(r["gross"] - r["tax"] - r["net"]) < 1e-9, f"{sc}: gross − tax = net")
        ok(r["affiliate_net"] <= r["net"] + 1e-12, f"{sc}: affiliate ≤ total")
        for label, be in breakeven_variants(data, res):
            b = be[sc]
            covered = (b["organic"] + b["paid"]) * b["r"] + b["fixed"]
            if b["organic"] > 0:
                ok(abs(covered - b["burn"]) < 1e-6, f"{sc}/{label}: organic×r + paid×r + fixed = burn")
            else:
                ok(covered >= b["burn"] - 1e-6, f"{sc}/{label}: fixed + paid revenue already cover burn")
            ok(abs(b["total"] - b["organic"] - b["paid"]) < 1e-9, f"{sc}/{label}: total = organic + paid")
    ok(res["conservative"]["net"] <= res["base"]["net"] <= res["optimistic"]["net"],
       "planning case is the lowest revenue per trip")
    ok(res["conservative"]["cost_per_trip"] >= res["base"]["cost_per_trip"] >= res["optimistic"]["cost_per_trip"],
       "planning case is the highest cost per trip")
    rv = data["reference"]["review_estimate"]
    ok(abs(rv["ctr"] * rv["booking_conversion"] * rv["booking_value_rub"] * rv["commission"] - 7.68) < 1e-9,
       "review formula reproduces 7.68 ₽")
    # an independent second computation of the base hotel line
    b = scenario(data, "base")
    hotel2 = (1000 * b["hotel_ctr"] * b["hotel_booking_conversion"] * (1 - b["hotel_cancellation_rate"])
              * (1 - b["hotel_attribution_leakage"])) * (b["hotel_price_night"] * b["hotel_season_price_index"]
                                                         * b["hotel_nights_per_booking"] * b["hotel_commission"]) / 1000
    ok(abs(hotel2 - res["base"]["hotel"]) < 1e-9, "base hotel line recomputed a second way")
    return n


# ---------------------------------------------------------------- main


def report(data: dict) -> str:
    res = {sc: per_trip(scenario(data, sc)) for sc in SCEN}
    n = self_check(data, res)
    parts = [
        section_inputs(data),
        section_revenue(data, res),
        section_acquisition(data, res),
        section_fixed(data),
        section_breakeven(data, res),
        section_sensitivity(data),
        section_crosschecks(data, res),
        [f"Самопроверка скрипта: пройдено проверок — {n} (суммы потоков, налог, тождества безубыточности, "
         f"порядок сценариев, формула ревью, повторный расчёт отелей). Модель v{data['meta']['version']}, "
         f"допущения на {data['meta']['as_of']}."],
    ]
    return "\n\n".join("\n".join(p) for p in parts) + "\n"


def embedded_block(md: str) -> str | None:
    if BEGIN not in md or END not in md:
        return None
    return md.split(BEGIN, 1)[1].split(END, 1)[0].strip("\n") + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--assumptions", type=Path, default=DEFAULT_ASSUMPTIONS)
    ap.add_argument("--check", type=Path, metavar="MD", help="verify the block embedded in MD matches the output")
    args = ap.parse_args(argv)
    out = report(load(args.assumptions))
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


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
