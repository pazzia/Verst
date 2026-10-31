#!/usr/bin/env python3
"""18-month financial model for Verst: cohort-based planned trips, revenue, itemised costs, burn, runway.

Stdlib only, deterministic. Reads tools/biz/financial_assumptions.json (plan and cost inputs),
tools/biz/assumptions.json (BIZ-01: revenue per trip, CPI, activation, trips per user, Pro, contracts, tax)
and tools/biz/market_assumptions.json (for the SAM cross-check), and prints Markdown tables in Russian.
docs/investor/financial-model.md embeds the default output between the BEGIN/END markers.

Usage:
    python3 tools/biz/financial_model.py                    # founder pay off (default)
    python3 tools/biz/financial_model.py --founder-pay      # founder pay on in every table
    python3 tools/biz/financial_model.py --check docs/investor/financial-model.md

Model (one scenario, month m = 1 … 18, month 1 = November 2026):
    season(m)     = 1 + (shape_norm[calendar month] − 1) × k,  k chosen so min(season) = low_month_volume_index
    new users     = beta (month 3) + launch × (1 + growth)^(m − launch) × season(m) (m ≥ launch)
                    + paid installs = installing ad spend / (1 + VAT) / CPI
    activated     = new users × install_to_planner
    trips(m)      = Σ cohorts c: activated(c) × f(m − c), f(0) = 1, f(1) = f(2) = (trips_per_planner − 1) / 2,
                    f(a ≥ 3) = repeat × (1 − churn)^(a − 3) × season(m)
    affiliate     = trips × (hotel + excursion gross revenue per trip from BIZ-01), from affiliate_start_month
    Pro           = activated × pro_planner_to_paid × price × (1 − store fee), from pro_start_month
    contracts     = B2G pilots / 12 × revenue per pilot + sponsored businesses × fee, from contracts_start_month
    cash receipts = each stream shifted by its lag; tax = 6 % of receipts (УСН «доходы»)
    net burn      = costs + tax − receipts;  runway for a raise R = months until opening + R − Σ net burn < 0
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import market_sizing as ms
import unit_economics as ue

DEFAULT_FM = HERE / "financial_assumptions.json"
BEGIN = "<!-- BEGIN: tools/biz/financial_model.py output -->"
END = "<!-- END: tools/biz/financial_model.py output -->"
SCEN = ue.SCEN
STATUSES = ue.STATUSES
MONTHS_RU = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
UNIT_RU = {
    "users": "пользователей",
    "users per month": "польз. в месяц",
    "growth per month": "рост в месяц",
    "trips per user per month": "поездок в месяц",
    "share per month": "доля в месяц",
    "model month": "мес. модели",
    "months": "мес.",
    "RUB per month": "₽ в месяц",
    "hours per month": "ч в месяц",
    "multiplier": "×",
    "RUB per hour": "₽ в час",
    "hours": "ч",
    "RUB": "₽",
    "hours per week": "ч в неделю",
    "share": "доля",
}
num, pct, row, header = ue.num, ue.pct, ue.row, ue.header

# cost lines: key, label, category, milestone tag (for the T1 attribution)
CATEGORIES = ["Хостинг", "Куратор мест", "Реклама (только измерение)", "Исследования и полевые поездки",
              "Юрист, юрлицо, бухгалтерия", "Сервисы и ИИ-инструменты", "Резерв", "Оплата основателя"]
LINES = [
    ("host_app", None, "Хостинг", "M4"),
    ("host_maps", None, "Хостинг", "M2"),
    ("host_staging", None, "Хостинг", "M4"),
    ("host_build", None, "Хостинг", "M2"),
    ("host_backup", None, "Хостинг", "M4"),
    ("cur_wave1", "Куратор: волна 1 до M3 (тесты, онбординг, 10 маршрутов)", "Куратор мест", "M3"),
    ("cur_maint", "Куратор: перепроверка, отзывы, смена сезона", "Куратор мест", "M3"),
    ("cur_wave2", "Куратор: волна 2 (ещё 10 маршрутов)", "Куратор мест", "после M6"),
    ("ads_val02", "Реклама: тест лендинга VAL-02", "Реклама (только измерение)", "M1"),
    ("ads_beta", "Реклама: замер CPI в бете", "Реклама (только измерение)", "M4"),
    ("ads_measure", "Реклама: постоянный замер CPI", "Реклама (только измерение)", "после M6"),
    ("res_val01", "Интервью VAL-01: благодарности", "Исследования и полевые поездки", "M1"),
    ("res_des01", "Юзабилити-тест DES-01: благодарности", "Исследования и полевые поездки", "M4"),
    ("res_field", "Полевые поездки VAL-05", "Исследования и полевые поездки", "M4"),
    ("leg_odbl", "Юрист: ODbL (LEG-01)", "Юрист, юрлицо, бухгалтерия", "M1"),
    ("leg_entity", "Регистрация ООО и УКЭП (LEG-02)", "Юрист, юрлицо, бухгалтерия", "M2"),
    ("leg_privacy", "Юрист: политика ПДн, согласие, условия", "Юрист, юрлицо, бухгалтерия", "M2"),
    ("leg_accounting", "Бухгалтерия и банк ООО", "Юрист, юрлицо, бухгалтерия", "M2"),
    ("leg_corporate", "Юрист: документы раунда и права на код", "Юрист, юрлицо, бухгалтерия", "M6"),
    ("leg_trademark", "Товарный знак", "Юрист, юрлицо, бухгалтерия", "после M6"),
    ("tools", "Домены, почта, мониторинг, маркировка (из BIZ-01)", "Сервисы и ИИ-инструменты", "общие"),
    ("ai_tools", "ИИ-инструменты разработки", "Сервисы и ИИ-инструменты", "общие"),
    ("contingency", "Резерв на непредвиденное", "Резерв", "общие"),
    ("founder", "Оплата основателя (вкл./выкл.)", "Оплата основателя", "общие"),
]


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
    plan = data["plan"]
    assert len(plan["season_shape"]) == 12 and min(plan["season_shape"]) > 0, "season_shape: 12 positive values"
    assert plan["raise_sizes"] == sorted(plan["raise_sizes"]) and len(plan["raise_sizes"]) == 3, "3 raise sizes, ascending"
    months = data["meta"]["months"]
    covered = []
    for t in plan["tranches"]:
        covered += list(range(t["months"][0], t["months"][1] + 1))
    assert covered == list(range(1, months + 1)), "tranches must cover months 1…N exactly once, in order"
    for vm in plan["vms"] + [plan["build_vm"], plan["backup"]]:
        assert vm["source"] in sources, f"{vm['label_ru']}: unknown source"
    for line in LINES:
        assert line[2] in CATEGORIES, f"{line[0]}: unknown category"


def values(data: dict, sc: str) -> dict[str, float]:
    return {k: float(v["values"][sc]) for k, v in data["inputs"].items()}


def month_label(data: dict, m: int) -> str:
    y0, mo0 = (int(x) for x in data["meta"]["start_month"].split("-"))
    idx = mo0 - 1 + m - 1
    return f"{MONTHS_RU[idx % 12]} {y0 + idx // 12}"


def calendar_month(data: dict, m: int) -> int:
    mo0 = int(data["meta"]["start_month"].split("-")[1])
    return (mo0 - 1 + m - 1) % 12 + 1


# ---------------------------------------------------------------- model


def season_index(data: dict, low: float) -> list[float]:
    """Index by calendar month (1…12 → list position 0…11), mean 1, weakest month = low."""
    shape = data["plan"]["season_shape"]
    mean = sum(shape) / 12
    norm = [s / mean for s in shape]
    k = (1 - low) / (1 - min(norm))
    return [1 + (s - 1) * k for s in norm]


def simulate(fm: dict, ued: dict, sc: str, founder_on: bool) -> dict:
    N = fm["meta"]["months"]
    v = values(fm, sc)
    u = ue.scenario(ued, sc)
    pt = ue.per_trip(u)
    plan = fm["plan"]
    seas = season_index(fm, u["low_month_volume_index"])
    s = [seas[calendar_month(fm, m) - 1] for m in range(1, N + 1)]   # s[m-1]
    M = range(1, N + 1)

    # ---- costs (₽ per month, cash, incl. VAT)
    c = {key: [0.0] * N for key, *_ in LINES}

    def add(key: str, m: int, x: float) -> None:
        if 1 <= m <= N:
            c[key][m - 1] += x

    vm_month = lambda vm: (vm["vcpu"] * v["price_vcpu_month"] + vm["ram_gb"] * v["price_ram_gb_month"]
                           + vm["ssd_gb"] * v["price_ssd_gb_month"])
    for vm in plan["vms"]:
        for m in M:
            if m >= vm["start_month"]:
                add(vm["key"], m, vm_month(vm))
    b = plan["build_vm"]
    build_hourly = (b["vcpu"] * v["price_vcpu_month"] + b["ram_gb"] * v["price_ram_gb_month"]) / 730
    for m in M:
        if m >= b["start_month"]:
            add("host_build", m, v["build_hours_month"] * build_hourly * v["spot_price_factor"])
        if m >= plan["backup"]["start_month"]:
            add("host_backup", m, plan["backup"]["gb"] * v["price_object_gb_month"])

    rate = v["curator_rate"]
    add("cur_wave1", 1, v["curator_tests"] + v["curator_hours_m3"] / 2 * rate)
    add("cur_wave1", 2, v["curator_hours_m3"] / 2 * rate)
    for m in (4, 5, 6):
        add("cur_wave2", m, v["curator_wave2_hours"] / 3 * rate)
    for m in M:
        if m >= 3:
            routes_factor = 2 if (m >= 7 and v["curator_wave2_hours"] > 0) else 1
            add("cur_maint", m, v["curator_maint_hours_week"] * 52 / 12 * rate * routes_factor)
            if calendar_month(fm, m) in (5, 10):
                add("cur_maint", m, v["curator_season_hours"] * rate * routes_factor)

    add("ads_val02", 1, v["ads_val02"])
    add("ads_beta", 3, v["ads_beta"])
    for m in M:
        if m >= 6:
            add("ads_measure", m, v["ads_measure_month"])
    add("res_val01", 1, v["research_val01"])
    add("res_des01", 2, v["research_des01"])
    add("res_field", 2, v["field_trips"] / 2)
    add("res_field", 3, v["field_trips"] / 2)
    add("leg_odbl", 1, v["legal_odbl"])
    add("leg_entity", 1, v["entity_setup"])
    add("leg_privacy", 2, v["legal_privacy"])
    for m in M:
        if m >= 2:
            add("leg_accounting", m, v["accounting_month"])
    add("leg_corporate", 4, v["corporate_docs"])
    add("leg_trademark", 5, v["trademark"])
    for m in M:
        add("tools", m, u["burn_tools"])
        add("ai_tools", m, v["ai_tools_month"])
    for i in range(N):
        base = sum(c[key][i] for key, *_ in LINES if key not in ("contingency", "founder"))
        c["contingency"][i] = base * v["contingency_rate"]
        c["founder"][i] = v["founder_pay_gross"] * v["founder_load_factor"] if founder_on else 0.0
    costs = [sum(c[key][i] for key, *_ in LINES) for i in range(N)]

    # ---- users and trips
    beta = [0.0] * N
    organic = [0.0] * N
    paid = [0.0] * N
    beta[2] = v["beta_new_users"]
    L = int(v["launch_month"])
    for m in M:
        if m >= L:
            organic[m - 1] = v["launch_new_users"] * (1 + v["organic_growth"]) ** (m - L) * s[m - 1]
        installing_ads = c["ads_beta"][m - 1] + c["ads_measure"][m - 1]   # VAL-02 buys leads, not installs
        paid[m - 1] = installing_ads / (1 + v["vat_rate"]) / u["cpi"]
    new_users = [beta[i] + organic[i] + paid[i] for i in range(N)]
    activated = [x * u["install_to_planner"] for x in new_users]
    extra = (u["trips_per_planner"] - 1) / 2
    trips = [0.0] * N
    paid_trips = [0.0] * N
    for ci in range(N):
        for mi in range(ci, N):
            a = mi - ci
            if a == 0:
                f = 1.0
            elif a in (1, 2):
                f = extra
            else:
                f = v["repeat_trips_month"] * (1 - v["churn_month"]) ** (a - 3) * s[mi]
            trips[mi] += activated[ci] * f
            paid_trips[mi] += paid[ci] * u["install_to_planner"] * f

    # ---- revenue (accrual) and cash receipts
    aff_per_trip = pt["hotel"] + pt["excursion"]
    rev = {"affiliate": [0.0] * N, "pro": [0.0] * N, "contracts": [0.0] * N}
    for m in M:
        i = m - 1
        if m >= v["affiliate_start_month"]:
            rev["affiliate"][i] = trips[i] * aff_per_trip
        if m >= v["pro_start_month"]:
            rev["pro"][i] = activated[i] * u["pro_planner_to_paid"] * u["pro_price_year"] * (1 - u["store_fee"])
        if m >= v["contracts_start_month"]:
            rev["contracts"][i] = (u["b2g_pilots_per_year"] * u["b2g_revenue_per_pilot"] / 12
                                   + u["sponsored_businesses"] * u["sponsored_fee_month"])
    lags = {"affiliate": int(v["lag_affiliate"]), "pro": int(v["lag_pro"]), "contracts": int(v["lag_contracts"])}
    receipts_by = {k: [rev[k][i - lags[k]] if i - lags[k] >= 0 else 0.0 for i in range(N)] for k in rev}
    revenue = [sum(rev[k][i] for k in rev) for i in range(N)]
    receipts = [sum(receipts_by[k][i] for k in rev) for i in range(N)]
    tax = [x * u["revenue_tax_rate"] for x in receipts]
    net_burn = [costs[i] + tax[i] - receipts[i] for i in range(N)]
    cum = []
    acc = 0.0
    for x in net_burn:
        acc += x
        cum.append(acc)
    return {
        "sc": sc, "v": v, "u": u, "pt": pt, "season": s, "c": c, "costs": costs, "beta": beta, "organic": organic,
        "paid": paid, "new_users": new_users, "activated": activated, "trips": trips, "paid_trips": paid_trips,
        "rev": rev, "revenue": revenue, "receipts_by": receipts_by, "receipts": receipts, "tax": tax,
        "net_burn": net_burn, "cum": cum, "founder_on": founder_on, "aff_per_trip": aff_per_trip,
    }


def runway(fm: dict, r: dict, raise_rub: float) -> tuple[float, bool]:
    """Months covered by opening cash + raise (fractional). Second value: True if extrapolated beyond month N."""
    N = fm["meta"]["months"]
    cash = fm["plan"]["opening_cash"] + raise_rub
    for i in range(N):
        if cash - r["net_burn"][i] < 0:
            return i + (cash / r["net_burn"][i] if r["net_burn"][i] > 0 else 0.0), False
        cash -= r["net_burn"][i]
    tail = sum(r["net_burn"][N - 3:]) / 3
    return (math.inf if tail <= 0 else N + cash / tail), True


def tranche_of(fm: dict, m: int) -> str:
    for t in fm["plan"]["tranches"]:
        if t["months"][0] <= m <= t["months"][1]:
            return t["id"]
    raise ValueError(m)


def line_label(fm: dict, key: str, default: str | None) -> str:
    if default:
        return default
    plan = fm["plan"]
    for vm in plan["vms"]:
        if vm["key"] == key:
            return vm["label_ru"]
    return {"host_build": plan["build_vm"]["label_ru"], "host_backup": plan["backup"]["label_ru"]}[key]


# ---------------------------------------------------------------- formatting helpers


def k(x: float) -> str:
    """₽ → thousands of ₽, no decimals (a model of assumptions is not precise to the rouble)."""
    return num(x / 1000, 0)


def runway_str(x: float, extrapolated: bool) -> str:
    if math.isinf(x):
        return "безубыточно"
    return ("> 18 (≈ " + num(x, 1 if x < 24 else 0) + ")") if extrapolated else num(x, 1)


# ---------------------------------------------------------------- report sections


def section_inputs(fm: dict, ued: dict) -> list[str]:
    lab = ued["meta"]["scenario_labels_ru"]
    out = ["### 1. Входные данные (financial_assumptions.json; остальное — из юнит-экономики)", ""]
    out += header("Ключ", "Параметр", "Ед.", lab["conservative"], lab["base"], lab["optimistic"], "Статус", "Ист.",
                  align="lllrrrll")
    for key, inp in fm["inputs"].items():
        vals = []
        for sc in SCEN:
            x = float(inp["values"][sc])
            if inp["unit"] in ("share", "growth per month", "share per month"):
                vals.append(pct(x, 0 if abs(100 * x - round(100 * x)) < 1e-9 else 1))
            elif inp["unit"] in ("multiplier", "trips per user per month", "hours per week"):
                vals.append(num(x, 2))
            else:
                whole = all(abs(float(z) - round(float(z))) < 1e-9 for z in inp["values"].values())
                vals.append(num(x, 0 if whole else 1))
        sts = [ue.status_of(inp, sc) for sc in SCEN]
        st = ue.STATUS_RU[sts[0]] if len(set(sts)) == 1 else " / ".join(ue.STATUS_RU[s] for s in sts)
        out.append(row(f"`{key}`", inp["label_ru"], UNIT_RU[inp["unit"]], *vals, st, ", ".join(inp["sources"]) or "—"))
    n = {s: 0 for s in STATUSES}
    for inp in fm["inputs"].values():
        for sc in SCEN:
            n[ue.status_of(inp, sc)] += 1
    plan = fm["plan"]
    out += ["", (f"Значений во всех сценариях: {sum(n.values())}; допущений {n['assumed']}, из источников {n['cited']}, "
                f"измерено {n['measured']}."), ""]
    out += ["**Из юнит-экономики BIZ-01** (`assumptions.json`, статусы там же):", ""]
    out += header("Ключ BIZ-01", lab["conservative"], lab["base"], lab["optimistic"])
    for key in ("cpi", "install_to_planner", "trips_per_planner", "pro_planner_to_paid", "pro_price_year",
                "store_fee", "b2g_pilots_per_year", "b2g_revenue_per_pilot", "sponsored_businesses",
                "sponsored_fee_month", "revenue_tax_rate", "low_month_volume_index", "burn_tools"):
        inp = ued["inputs"][key]
        out.append(row(f"`{key}`", *[ue.value_str(inp, float(inp["values"][sc])) for sc in SCEN]))
    pts = {sc: ue.per_trip(ue.scenario(ued, sc)) for sc in SCEN}
    out.append(row("партнёрка на поездку до налога, ₽ (расчёт BIZ-01)",
                   *[num(pts[sc]["hotel"] + pts[sc]["excursion"], 2) for sc in SCEN]))
    out += ["", "**План** (`plan` в financial_assumptions.json, всё — допущения):", "",
            (f"- Размеры раунда для сравнения: {', '.join(num(x / 1e6, 0) + ' млн ₽' for x in plan['raise_sizes'])}. "
            f"Денег на счёте на старте: {num(plan['opening_cash'], 0)} ₽ (неизвестно — вопрос CEO)."),
            (f"- Сезонность по месяцам (янв … дек, до нормировки): "
            f"{' · '.join(num(x, 1) for x in plan['season_shape'])}; глубина провала — `low_month_volume_index` BIZ-01."),
            ("- ВМ и их размеры — architecture.md §12.2 и infra/routing/README.md; цены за vCPU, ГБ RAM и ГБ SSD — "
            "допущения до расчёта в калькуляторе провайдера."), ""]
    out += ["**Источники** (найдены 26.10.2026; веб — «по выдержке из поиска», страницы открыть вручную):", ""]
    for sid, s in fm["sources"].items():
        out.append(f"- [{sid}] {s['title']}. {s['url']} (опубл.: {s['published']})")
    return out


def section_calendar(fm: dict) -> list[str]:
    plan = fm["plan"]
    out = ["### 2. Календарь: вехи и транши", ""]
    out += header("Веха", "Неделя", "Месяц модели", "Что значит «сделано»", align="lrll")
    for ms_ in plan["milestones"]:
        out.append(row(ms_["id"], f"W{ms_['week']}", f"{ms_['month']} ({month_label(fm, ms_['month'])})", ms_["label_ru"]))
    out += [""]
    out += header("Транш", "Месяцы", "Что финансирует", "Условие выдачи", align="llll")
    for t in plan["tranches"]:
        a, b = t["months"]
        out.append(row(t["id"], f"{a}–{b} ({month_label(fm, a)} – {month_label(fm, b)})", t["label_ru"], t["gate_ru"]))
    return out


def section_monthly(fm: dict, ued: dict, res: dict) -> list[str]:
    lab = ued["meta"]["scenario_labels_ru"]
    out = ["### 3. Помесячно по сценариям (тыс. ₽; пользователи и поездки — штуки)", ""]
    for sc in SCEN:
        r = res[sc]
        title = {"conservative": "планировочный сценарий: по нему считаем деньги",
                 "base": "показываем инвестору как наиболее вероятный",
                 "optimistic": "верхняя граница, не план"}[sc]
        out += [f"**{lab[sc]}** — {title}.", ""]
        out += header("Мес.", "Месяц", "Новые польз.", "Из них платные", "Поездок", "Выручка", "Поступления",
                      "Расходы", "в т. ч. основатель", "Налог", "Чистое сжигание", "Нарастающим", align="llrrrrrrrrrr")
        for i in range(fm["meta"]["months"]):
            out.append(row(str(i + 1), month_label(fm, i + 1), num(r["new_users"][i], 0), num(r["paid"][i], 0),
                           num(r["trips"][i], 0), k(r["revenue"][i]), k(r["receipts"][i]), k(r["costs"][i]),
                           k(r["c"]["founder"][i]), k(r["tax"][i]), k(r["net_burn"][i]), k(r["cum"][i])))
        out.append(row("**Σ**", "18 мес.", num(sum(r["new_users"]), 0), num(sum(r["paid"]), 0), num(sum(r["trips"]), 0),
                       k(sum(r["revenue"])), k(sum(r["receipts"])), k(sum(r["costs"])), k(sum(r["c"]["founder"])),
                       k(sum(r["tax"])), k(sum(r["net_burn"])), "—"))
        out += [""]
    out += [("«Выручка» — начислено в месяце поездки или продажи; «Поступления» — деньги на счёте с задержкой "
            "(партнёрка и контракты 2 мес., Pro 1 мес.). Выручка последних месяцев поступает уже за горизонтом модели.")]
    return out


def section_costs(fm: dict, ued: dict, res: dict) -> list[str]:
    lab = ued["meta"]["scenario_labels_ru"]
    tr = fm["plan"]["tranches"]
    out = ["### 4. Расходы по статьям (тыс. ₽ за период)", ""]
    cons = res["conservative"]
    cols = [f"{lab['conservative']}: {t['id']} (мес. {t['months'][0]}–{t['months'][1]})" for t in tr]
    out += header("Статья", "Категория", *cols, f"{lab['conservative']}: 18 мес.", f"{lab['base']}: 18 мес.",
                  f"{lab['optimistic']}: 18 мес.", align="llrrrrrr")

    def period(r: dict, key: str, a: int, b: int) -> float:
        return sum(r["c"][key][a - 1:b])

    N = fm["meta"]["months"]
    for key, label, cat, _ in LINES:
        out.append(row(line_label(fm, key, label), cat, *[k(period(cons, key, *t["months"])) for t in tr],
                       *[k(period(res[sc], key, 1, N)) for sc in SCEN]))
    out.append(row("**Итого расходов**", "", *[k(sum(cons["costs"][t["months"][0] - 1:t["months"][1]])) for t in tr],
                   *[k(sum(res[sc]["costs"])) for sc in SCEN]))
    out += ["", "По категориям, 18 месяцев:", ""]
    out += header("Категория", *[f"{lab[sc]}, тыс. ₽" for sc in SCEN], *[f"{lab[sc]}, доля" for sc in SCEN])
    for cat in CATEGORIES:
        vals = {sc: sum(sum(res[sc]["c"][key]) for key, _, c_, _ in LINES if c_ == cat) for sc in SCEN}
        out.append(row(cat, *[k(vals[sc]) for sc in SCEN],
                       *[pct(vals[sc] / sum(res[sc]["costs"]), 0) for sc in SCEN]))
    return out


def summary(fm: dict, r: dict) -> dict:
    N = fm["meta"]["months"]
    return {
        "users": sum(r["new_users"]),
        "trips": sum(r["trips"]),
        "revenue": sum(r["revenue"]),
        "receipts": sum(r["receipts"]),
        "costs": sum(r["costs"]),
        "net": sum(r["net_burn"]),
        "peak": max(r["cum"]),
        "avg_last6": sum(r["net_burn"][N - 6:]) / 6,
        "trips_m18": r["trips"][N - 1],
        "rev_cover": sum(r["receipts"]) / sum(r["costs"]),
    }


def section_summary(fm: dict, ued: dict, res: dict, res_f: dict) -> list[str]:
    lab = ued["meta"]["scenario_labels_ru"]
    out = ["### 5. Итоги 18 месяцев", ""]
    out += header("Показатель", *[lab[sc] for sc in SCEN])
    S = {sc: summary(fm, res[sc]) for sc in SCEN}
    SF = {sc: summary(fm, res_f[sc]) for sc in SCEN}
    founder_label = "вкл." if res["conservative"]["founder_on"] else "выкл."
    rows_ = [
        ("Новых пользователей", lambda sc: num(S[sc]["users"], 0)),
        ("Запланированных поездок", lambda sc: num(S[sc]["trips"], 0)),
        ("Поездок в месяц 18", lambda sc: num(S[sc]["trips_m18"], 0)),
        ("Выручка начислено, тыс. ₽", lambda sc: num(S[sc]["revenue"] / 1000, 1)),
        ("Поступления, тыс. ₽", lambda sc: num(S[sc]["receipts"] / 1000, 1)),
        (f"Расходы (оплата основателя {founder_label}), тыс. ₽", lambda sc: k(S[sc]["costs"])),
        ("Поступления покрывают расходы на", lambda sc: pct(S[sc]["rev_cover"], 1)),
        ("**Чистое сжигание за 18 мес., тыс. ₽**", lambda sc: "**" + k(S[sc]["net"]) + "**"),
        ("Пиковая потребность в деньгах, тыс. ₽", lambda sc: k(S[sc]["peak"])),
        ("Среднее сжигание в мес. 13–18, тыс. ₽", lambda sc: k(S[sc]["avg_last6"])),
        ("Для сравнения: сжигание за 18 мес. с оплатой основателя, тыс. ₽" if not res["conservative"]["founder_on"]
         else "Для сравнения: сжигание за 18 мес. без оплаты основателя, тыс. ₽", lambda sc: k(SF[sc]["net"])),
    ]
    for label, f in rows_:
        out.append(row(label, *[f(sc) for sc in SCEN]))
    return out


def section_runway(fm: dict, ued: dict, res_off: dict, res_on: dict) -> list[str]:
    lab = ued["meta"]["scenario_labels_ru"]
    out = [("### 6. Запас хода для трёх размеров раунда (месяцев от ноября 2026; деньги на старте "
           f"{num(fm['plan']['opening_cash'], 0)} ₽)"), ""]
    out += header("Раунд", *[f"{lab[sc]}: без оплаты основателя" for sc in SCEN],
                  *[f"{lab[sc]}: с оплатой основателя" for sc in SCEN])
    for R in fm["plan"]["raise_sizes"]:
        cells = [runway_str(*runway(fm, res_off[sc], R)) for sc in SCEN]
        cells += [runway_str(*runway(fm, res_on[sc], R)) for sc in SCEN]
        out.append(row(num(R / 1e6, 0) + " млн ₽", *cells))
    out += ["", ("«> 18 (≈ N)» — денег хватает на весь горизонт; N — оценка по среднему сжиганию месяцев 16–18. "
                "Планируем по столбцу «Консерв.»; оплата основателя — отдельное решение CEO и инвестора.")]
    return out


def section_use_of_funds(fm: dict, ued: dict, res: dict, res_other: dict) -> list[str]:
    plan = fm["plan"]
    cons = res["conservative"]
    other = res_other["conservative"]
    on, off = (cons, other) if cons["founder_on"] else (other, cons)
    founder_label = "с оплатой основателя" if cons["founder_on"] else "без оплаты основателя"
    out = [f"### 7. Использование средств по траншам (планировочный сценарий, {founder_label}, тыс. ₽)", ""]
    tr = plan["tranches"]

    def cat_sum(r: dict, cat: str, a: int, b: int) -> float:
        return sum(sum(r["c"][key][a - 1:b]) for key, _, c_, _ in LINES if c_ == cat)

    def net_sum(r: dict, a: int, b: int) -> float:
        return sum(r["net_burn"][a - 1:b])

    def cost_sum(r: dict, a: int, b: int) -> float:
        return sum(r["costs"][a - 1:b])

    out += header("Категория", *[f"{t['id']}: мес. {t['months'][0]}–{t['months'][1]}" for t in tr], "Итого",
                  "Доля", align="lrrrrr")
    total = sum(cons["costs"])
    for cat in CATEGORIES:
        vals = [cat_sum(cons, cat, *t["months"]) for t in tr]
        out.append(row(cat, *[k(x) for x in vals], k(sum(vals)), pct(sum(vals) / total, 0)))
    out.append(row("**Расходы**", *[k(cost_sum(cons, *t["months"])) for t in tr], k(total), "100 %"))
    out.append(row("− поступления + налог", *[k(net_sum(cons, *t["months"]) - cost_sum(cons, *t["months"])) for t in tr],
                   k(sum(cons["net_burn"]) - total), "—"))
    out.append(row("**Транш = чистое сжигание периода**", *[k(net_sum(cons, *t["months"])) for t in tr],
                   k(sum(cons["net_burn"])), "—"))
    out.append(row("Справочно: транш без оплаты основателя", *[k(net_sum(off, *t["months"])) for t in tr],
                   k(sum(off["net_burn"])), "—"))
    out.append(row("Справочно: транш с оплатой основателя", *[k(net_sum(on, *t["months"])) for t in tr],
                   k(sum(on["net_burn"])), "—"))
    out += ["", ("Условия выдачи траншей — раздел 2. Какие транши закрывает раунд (нарастающим итогом, "
                "планировочный сценарий):"), ""]

    def cum_need(r: dict) -> list[float]:
        acc, res_ = 0.0, []
        for t in tr:
            acc += net_sum(r, *t["months"])
            res_.append(acc)
        return res_

    need_off, need_on = cum_need(off), cum_need(on)
    out += header("Раунд", *[f"без осн.: {t['id']} (нужно {k(need_off[i])})" for i, t in enumerate(tr)],
                  *[f"с осн.: {t['id']} (нужно {k(need_on[i])})" for i, t in enumerate(tr)])
    for R in plan["raise_sizes"]:
        cash = plan["opening_cash"] + R
        cell = lambda need, cash=cash: "да" if cash >= need else f"нет, на {pct(cash / need, 0)}"
        out.append(row(num(R / 1e6, 0) + " млн ₽", *[cell(x) for x in need_off], *[cell(x) for x in need_on]))
    t1 = tr[0]
    a, b = t1["months"]
    out += ["", f"**{t1['id']} по вехам M1–M6** (расходы мес. {a}–{b}, тыс. ₽; постоянные расходы — строка «общие»):", ""]
    tags = [m_["id"] for m_ in plan["milestones"]] + ["общие"]
    by_tag = {t: 0.0 for t in tags}
    by_tag_lines: dict[str, list[str]] = {t: [] for t in tags}
    for key, label, _, tag in LINES:
        x = sum(cons["c"][key][a - 1:b])
        if x <= 0:
            continue
        tag_ = tag if tag in by_tag else "общие"
        by_tag[tag_] += x
        by_tag_lines[tag_].append(line_label(fm, key, label).split(" (")[0])
    out += header("Веха", "Тыс. ₽", "Доля T1", "Статьи", align="lrrl")
    t1_total = sum(cons["costs"][a - 1:b])
    for t in tags:
        if by_tag[t] > 0 or t != "общие":
            out.append(row(t, k(by_tag[t]), pct(by_tag[t] / t1_total, 0), "; ".join(by_tag_lines[t]) or "—"))
    out.append(row("**Итого T1**", k(t1_total), "100 %", ""))
    return out


def section_crosschecks(fm: dict, ued: dict, mk: dict, res: dict) -> list[str]:
    lab = ued["meta"]["scenario_labels_ru"]
    N = fm["meta"]["months"]
    out = ["### 8. Сверки", ""]
    out += ["**8.1. Таблица целей W13 против модели** (мес. 1–3; цели — из бэклога, не прогноз)", ""]
    out += header("Показатель", "Цель W13", *[lab[sc] for sc in SCEN])
    out.append(row("Запланированных поездок к концу мес. 3", "≥ 1 000", *[num(sum(res[sc]["trips"][:3]), 0) for sc in SCEN]))
    out.append(row("Пользователей, построивших поездку, в бете", "≥ 100 семей",
                   *[num(sum(res[sc]["activated"][:3]), 0) for sc in SCEN]))
    need = {sc: 1000 / res[sc]["u"]["install_to_planner"] for sc in SCEN}
    out.append(row("Сколько новых пользователей нужно в бете для 1 000 поездок в мес. 3", "—",
                   *[num(need[sc], 0) for sc in SCEN]))
    # SAM penetration (calendar 2027 = model months whose label ends with 2027)
    mres = ms.compute(mk, ued)
    idx27 = [i for i in range(N) if month_label(fm, i + 1).endswith("2027")]
    out += ["", "**8.2. Поездки модели в 2027 году против SAM и SOM** (market-sizing.md)", ""]
    out += header("Показатель", *[lab[sc] for sc in SCEN])
    t27 = {sc: sum(res[sc]["trips"][i] for i in idx27) for sc in SCEN}
    sam27 = {sc: mres[sc]["years"][2027]["sam"] for sc in SCEN}
    out.append(row(f"Поездок в модели, {month_label(fm, idx27[0] + 1)} – {month_label(fm, idx27[-1] + 1)}",
                   *[num(t27[sc], 0) for sc in SCEN]))
    out.append(row("SAM 2027, поездок", *[num(sam27[sc], 0) for sc in SCEN]))
    out.append(row("Поездки модели ÷ SAM (верхняя граница доли)", *[pct(t27[sc] / sam27[sc], 2) for sc in SCEN]))
    out.append(row("SOM год 1 в market-sizing", *[pct(mres[sc]["years"][2027]["pen"], 2) for sc in SCEN]))
    out.append(row("Вывод", *[("согласовано (≤ 2 раз)" if (t27[sc] / sam27[sc]) / mres[sc]["years"][2027]["pen"] <= 2
                               and mres[sc]["years"][2027]["pen"] / (t27[sc] / sam27[sc]) <= 2 else "пересмотреть")
                              for sc in SCEN]))
    out += ["", ("Поездки модели — все пользователи Версты, не только сегмент SAM (Москва и МО, дети или собака, "
                "планируют в приложении), поэтому отношение к SAM — верхняя граница доли. Если она выше SOM года 1 "
                "больше чем вдвое, одно из двух допущений надо пересмотреть."), ""]
    out += ["**8.3. Расходы модели против месячных расходов BIZ-01** (средний месяц 13–18, тыс. ₽)", ""]
    out += header("Статья BIZ-01", "Ключ BIZ-01", *[f"{lab[sc]}: BIZ-01" for sc in SCEN],
                  *[f"{lab[sc]}: модель" for sc in SCEN], align="llrrrrrr")
    groups = [
        ("хостинг", "burn_hosting", ("host_app", "host_maps", "host_staging", "host_build", "host_backup")),
        ("куратор", "burn_curator", ("cur_wave1", "cur_maint", "cur_wave2")),
        ("реклама", "burn_ads", ("ads_val02", "ads_beta", "ads_measure")),
        ("бухгалтерия и банк", "burn_accounting", ("leg_accounting",)),
        ("сервисы", "burn_tools", ("tools",)),
    ]
    for label, key, lines in groups:
        ue_vals = [float(ued["inputs"][key]["values"][sc]) for sc in SCEN]
        fm_vals = [sum(sum(res[sc]["c"][ln][N - 6:]) for ln in lines) / 6 for sc in SCEN]
        out.append(row(label, f"`{key}`", *[k(x) for x in ue_vals], *[k(x) for x in fm_vals]))
    out += ["", ("Расхождения ожидаемы и объяснены: модель берёт ВМ по architecture.md §12.2 (BIZ-01 брал округлённую "
                "оценку), бухгалтерию ООО вместо ИП (D-IR-09) и рекламу только для замера (D-IR-12) вместо 30 тыс. ₽ "
                "каждый месяц. Когда будут счета провайдера и договор с куратором, обновляем оба файла."), ""]
    out += ["**8.4. Безубыточность в месяц 18**", ""]
    out += header("Показатель", *[lab[sc] for sc in SCEN])
    be = {}
    for sc in SCEN:
        r = res[sc]
        u = r["u"]
        net_trip = (r["aff_per_trip"] + (r["pt"]["pro"] if r["v"]["pro_start_month"] <= N else 0)) \
            * (1 - u["revenue_tax_rate"])
        contracts = r["rev"]["contracts"][N - 1] * (1 - u["revenue_tax_rate"])
        need_ = max(0.0, (r["costs"][N - 1] - contracts) / net_trip) if net_trip > 0 else math.inf
        be[sc] = (net_trip, contracts, need_, r["trips"][N - 1])
    out.append(row("Расходы месяца 18, тыс. ₽", *[k(res[sc]["costs"][N - 1]) for sc in SCEN]))
    out.append(row("Чистая выручка на поездку (BIZ-01, все потоки на поездку), ₽", *[num(be[sc][0], 2) for sc in SCEN]))
    out.append(row("Контракты в месяц 18 чистыми, тыс. ₽", *[k(be[sc][1]) for sc in SCEN]))
    out.append(row("Нужно поездок в месяц для безубыточности", *[num(be[sc][2], 0) for sc in SCEN]))
    out.append(row("Поездок в месяц 18 в модели", *[num(be[sc][3], 0) for sc in SCEN]))
    out.append(row("Разрыв (нужно ÷ есть), раз",
                   *[("покрыто" if be[sc][2] <= be[sc][3] else num(be[sc][2] / be[sc][3], 0)) for sc in SCEN]))
    out += ["", "**8.5. Эффективность привлечения**", ""]
    out += header("Показатель", *[lab[sc] for sc in SCEN])
    ads_inst = {sc: sum(res[sc]["c"]["ads_beta"]) + sum(res[sc]["c"]["ads_measure"]) for sc in SCEN}
    paid_act = {sc: sum(res[sc]["paid"]) * res[sc]["u"]["install_to_planner"] for sc in SCEN}
    out.append(row("Реклама на установки за 18 мес., тыс. ₽", *[k(ads_inst[sc]) for sc in SCEN]))
    out.append(row("Платных активных пользователей", *[num(paid_act[sc], 0) for sc in SCEN]))
    out.append(row("CAC на активного пользователя, ₽ (с НДС)", *[num(ads_inst[sc] / paid_act[sc], 0) for sc in SCEN]))
    out.append(row("Доля поездок от рекламы", *[pct(sum(res[sc]["paid_trips"]) / sum(res[sc]["trips"]), 1)
                                                 for sc in SCEN]))
    out += ["", ("Burn multiple и LTV/CAC не считаем: подписочной выручки нет, а выручка на поездку не измерена. "
                "Они появятся, когда BIZ-06 и M5 дадут первые реальные деньги.")]
    return out


# ---------------------------------------------------------------- self-check


def self_check(fm: dict, ued: dict, res_off: dict, res_on: dict) -> int:
    n = 0

    def ok(cond: bool, msg: str) -> None:
        nonlocal n
        assert cond, f"self-check failed: {msg}"
        n += 1

    N = fm["meta"]["months"]
    for res in (res_off, res_on):
        for sc in SCEN:
            r = res[sc]
            for i in range(N):
                ok(abs(sum(r["c"][key][i] for key, *_ in LINES) - r["costs"][i]) < 1e-6, f"{sc}/{i + 1}: lines sum")
                ok(abs(r["costs"][i] + r["tax"][i] - r["receipts"][i] - r["net_burn"][i]) < 1e-6,
                   f"{sc}/{i + 1}: net burn identity")
            base_c = [sum(r["c"][key][i] for key, *_ in LINES if key not in ("contingency", "founder")) for i in range(N)]
            ok(all(abs(r["c"]["contingency"][i] - base_c[i] * r["v"]["contingency_rate"]) < 1e-6 for i in range(N)),
               f"{sc}: contingency = rate × costs")
            ok((sum(r["c"]["founder"]) > 0) == r["founder_on"], f"{sc}: founder line follows the toggle")
            ok(abs(r["cum"][-1] - sum(r["net_burn"])) < 1e-6, f"{sc}: cumulative = Σ net burn")
            ok(sum(r["receipts"]) <= sum(r["revenue"]) + 1e-6, f"{sc}: receipts ≤ revenue (lags)")
            # trips a second way: per-cohort closed form for the first 90 days + repeat sum
            t2 = 0.0
            extra = (r["u"]["trips_per_planner"] - 1) / 2
            for ci in range(N):
                act = r["activated"][ci]
                t2 += act * (1 + extra * min(2, N - 1 - ci))
                for mi in range(ci + 3, N):
                    t2 += act * r["v"]["repeat_trips_month"] * (1 - r["v"]["churn_month"]) ** (mi - ci - 3) * r["season"][mi]
            ok(abs(t2 - sum(r["trips"])) < 1e-6, f"{sc}: trips recomputed per cohort")
            seas = season_index(fm, r["u"]["low_month_volume_index"])
            ok(abs(min(seas) - r["u"]["low_month_volume_index"]) < 1e-9 and abs(sum(seas) / 12 - 1) < 1e-9,
               f"{sc}: season index min = low_month_volume_index, mean = 1")
            prev = -1.0
            for R in fm["plan"]["raise_sizes"]:
                x, _ = runway(fm, r, R)
                ok(x >= prev, f"{sc}: runway grows with the raise")
                prev = x
        ok(sum(res["conservative"]["revenue"]) <= sum(res["base"]["revenue"]) <= sum(res["optimistic"]["revenue"]),
           "revenue: conservative ≤ base ≤ optimistic")
        ok(sum(res["conservative"]["costs"]) >= sum(res["base"]["costs"]) >= sum(res["optimistic"]["costs"]),
           "costs: conservative ≥ base ≥ optimistic")
        cons = res["conservative"]
        tr_sum = sum(sum(cons["net_burn"][t["months"][0] - 1:t["months"][1]]) for t in fm["plan"]["tranches"])
        ok(abs(tr_sum - sum(cons["net_burn"])) < 1e-6, "tranches add up to the 18-month burn")
    for sc in SCEN:
        added = sum(res_on[sc]["costs"]) - sum(res_off[sc]["costs"])
        ok(abs(added - N * res_off[sc]["v"]["founder_pay_gross"] * res_off[sc]["v"]["founder_load_factor"]) < 1e-6,
           f"{sc}: founder toggle adds exactly N × loaded pay")
    return n


# ---------------------------------------------------------------- main


def report(fm: dict, ued: dict, mk: dict, founder_on: bool) -> str:
    res_off = {sc: simulate(fm, ued, sc, False) for sc in SCEN}
    res_on = {sc: simulate(fm, ued, sc, True) for sc in SCEN}
    res, res_f = (res_on, res_off) if founder_on else (res_off, res_on)
    n = self_check(fm, ued, res_off, res_on)
    parts = [
        section_inputs(fm, ued),
        section_calendar(fm),
        section_monthly(fm, ued, res),
        section_costs(fm, ued, res),
        section_summary(fm, ued, res, res_f),
        section_runway(fm, ued, res_off, res_on),
        section_use_of_funds(fm, ued, res, res_f),
        section_crosschecks(fm, ued, mk, res),
        [(f"Самопроверка скрипта: пройдено проверок — {n} (сумма статей, тождество сжигания, резерв, переключатель "
         f"оплаты основателя, поездки по когортам вторым способом, сезонность, рост запаса хода с раундом, порядок "
         f"сценариев, сумма траншей). Модель v{fm['meta']['version']}, допущения на {fm['meta']['as_of']}; "
         f"оплата основателя: {'вкл.' if founder_on else 'выкл.'}")],
    ]
    return "\n\n".join("\n".join(p) for p in parts) + "\n"


def embedded_block(md: str) -> str | None:
    if BEGIN not in md or END not in md:
        return None
    return md.split(BEGIN, 1)[1].split(END, 1)[0].strip("\n") + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fm", type=Path, default=DEFAULT_FM)
    ap.add_argument("--assumptions", type=Path, default=ue.DEFAULT_ASSUMPTIONS)
    ap.add_argument("--market", type=Path, default=ms.DEFAULT_MARKET)
    ap.add_argument("--founder-pay", action="store_true", help="turn the founder pay line on in every table")
    ap.add_argument("--check", type=Path, metavar="MD", help="verify the block embedded in MD matches the output")
    args = ap.parse_args(argv)
    fm = load(args.fm)
    founder_on = args.founder_pay or bool(fm["plan"]["founder_pay_enabled"])
    out = report(fm, ue.load(args.assumptions), ms.load(args.market), founder_on)
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
