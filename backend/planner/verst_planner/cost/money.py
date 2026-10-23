"""Money arithmetic [D-12]: `Decimal` with ROUND_HALF_UP; integers only at the output boundary (A§7.1)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal(0)


def dec(x: int | float | str | Decimal) -> Decimal:
    """Exact decimal of `x` (floats through their shortest repr, so 61.9 -> Decimal("61.9"))."""
    if isinstance(x, Decimal):
        return x
    if isinstance(x, float):
        return Decimal(repr(x))
    return Decimal(x)


def round_to(x: Decimal, step: int) -> int:
    """`int((x / step).quantize(1, ROUND_HALF_UP)) * step`."""
    return int((x / step).quantize(Decimal(1), ROUND_HALF_UP)) * step


def quantize(x: Decimal, places: int) -> Decimal:
    return x.quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP)
