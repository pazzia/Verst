"""Russian text helpers (A§7.2 number formatting, A§8.1 helpers).

Russian words live in ``resources/strings.ru.json``; this module only holds the rules.
Thousands separator U+202F (narrow no-break space), decimal comma, money ``"34 500 ₽"`` with U+00A0
before the rouble sign. The "≈" prefix of estimates is added by the client, not here.
"""

from __future__ import annotations

import json
from datetime import date, time
from decimal import ROUND_HALF_UP, Decimal
from functools import cache
from typing import Any

from verst_planner import resources
from verst_planner.domain.model import Town

RESOURCES = resources.DIR
THIN = chr(0x202F)  # narrow no-break space
NBSP = chr(0x00A0)  # no-break space
RUB = chr(0x20BD)  # rouble sign


@cache
def _strings() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(resources.read_text("strings.ru.json"))
    return data


def text(key: str, **params: str | int | float) -> str:
    """A Russian UI string from ``strings.ru.json`` rendered with `params` (missing ones raise KeyError)."""
    raw = _strings()[key]
    if not isinstance(raw, str):
        raise KeyError(f"{key} is not a string")
    return raw.format(**params) if params else raw


def words(key: str) -> list[str]:
    raw = _strings()[key]
    if not isinstance(raw, list):
        raise KeyError(f"{key} is not a list")
    return [str(x) for x in raw]


def plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def plural_word(n: int, key: str) -> str:
    one, few, many = words(key)
    return plural(n, one, few, many)


def days_word(n: int) -> str:
    return plural_word(n, "plural.day")


def _group(digits: str) -> str:
    parts = []
    while len(digits) > 3:
        parts.append(digits[-3:])
        digits = digits[:-3]
    parts.append(digits)
    return THIN.join(reversed(parts))


def fmt_int(n: int) -> str:
    """``34500 → "34 500"`` (U+202F); numbers below 10 000 are grouped as well (``1 540``)."""
    sign = "-" if n < 0 else ""
    return sign + _group(str(abs(int(n))))


def fmt_rub(n: int) -> str:
    return f"{fmt_int(n)}{NBSP}{RUB}"


def fmt_decimal(x: float | Decimal, places: int) -> str:
    """Half-up rounding to `places`, decimal comma, U+202F thousands: ``61.4, 2 → "61,40"``."""
    q = Decimal(1).scaleb(-places) if places > 0 else Decimal(1)
    d = Decimal(str(x)).quantize(q, ROUND_HALF_UP)
    sign = "-" if d < 0 else ""
    whole, _, frac = str(abs(d)).partition(".")
    out = sign + _group(whole)
    return f"{out},{frac}" if places > 0 else out


def fmt_consumption(x: float | Decimal) -> str:
    """``8 → "8"``, ``7.5 → "7,5"`` (at most one decimal, no trailing zero)."""
    d = Decimal(str(x)).quantize(Decimal("0.1"), ROUND_HALF_UP)
    if d == d.to_integral_value():
        return fmt_int(int(d))
    return fmt_decimal(d, 1)


def fmt_consumption_setting(x: float | Decimal) -> str:
    """Consumption as set in the Instruments settings, always one decimal: ``8 → "8,0"`` (copy review R-4).

    Used for the Drive stage line («Считаем бензин: 8,0 л на 100 км»); cost formulas keep `fmt_consumption`
    («8 л/100», A§7.2).
    """
    return fmt_decimal(x, 1)


def fmt_price(x: float | Decimal) -> str:
    """Unit price in roubles with kopecks and a decimal comma: ``62.4 → "62,40"`` (copy review R-4)."""
    return fmt_decimal(x, 2)


def minutes_word(n: int) -> str:
    """«минута / минуты / минут» for `n` (copy review R-2)."""
    return plural_word(n, "plural.minute")


def fuel_type_label(fuel_type: str) -> str:
    """«АИ-92», «АИ-95», «ДТ» for a `FuelType` value."""
    return text(f"fuel_type.{fuel_type}")


def fmt_km(x: float) -> str:
    return fmt_int(int(Decimal(str(x)).quantize(Decimal(1), ROUND_HALF_UP)))


_NAMED_DURATIONS = (30, 60, 90, 120)


def _numeric_duration(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    if h == 0:
        return text("duration.m", m=m)
    if m == 0:
        return text("duration.h", h=h)
    return text("duration.hm", h=h, m=m)


def fmt_duration(minutes: int) -> str:
    """Always numeric: 120 → «2 ч», 150 → «2 ч 30 мин», 45 → «45 мин»."""
    return _numeric_duration(minutes)


def duration_phrase(minutes: int) -> str:
    """30 → «полчаса», 60 → «час», 90 → «полтора часа», 120 → «два часа», else «2 ч 15 мин»."""
    if minutes in _NAMED_DURATIONS:
        return text(f"duration.{minutes}")
    return _numeric_duration(minutes)


def duration_genitive(minutes: int) -> str:
    """Genitive form for «после …»: 120 → «двух часов»; numeric forms are abbreviations and do not change."""
    if minutes in _NAMED_DURATIONS:
        return text(f"duration.gen.{minutes}")
    return _numeric_duration(minutes)


def part_of_day(t: time) -> str:
    """Dative noun for «Дома к …»: before 12:00 «обеду», before 17:00 «ужину», later «вечеру»."""
    if t.hour < 12:
        return text("part_of_day.morning")
    if t.hour < 17:
        return text("part_of_day.afternoon")
    return text("part_of_day.evening")


def prepositional(town: Town) -> str:
    """Prepositional form («в Ярославле»), falling back to the nominative name."""
    return town.name_prep_ru or town.name_ru


def genitive(town: Town) -> str:
    """Genitive form («из Ярославля», OI-39), falling back to the nominative name."""
    return town.name_gen_ru or town.name_ru


def month_year_ru(as_of: str | date) -> str:
    """``"2026-10"`` or a date → «октябрь 2026»."""
    if isinstance(as_of, date):
        year, month = as_of.year, as_of.month
    else:
        y, m = as_of.split("-")[:2]
        year, month = int(y), int(m)
    return f"{words('months')[month - 1]} {year}"


def capitalize_first(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s
