"""Bank of Russia rates for the money abroad (CEO 29.10): the app's own source, never a made-up rate.

The file is the one `tools/ci/fetch_rates.py` writes for the app (`{"asOf", "source", "rubPerUnit"}`). The
server reads it from `VERST_RATES_FILE`; without it (or without a currency in it) an amount abroad stays in
its local currency and the trip says its rouble total is incomplete. RUB needs no rate (Abkhazia).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from verst_planner import resources

RUB = "RUB"


@dataclass(frozen=True, slots=True)
class Rates:
    as_of: str
    source: str
    rub_per_unit: dict[str, Decimal]

    def rate(self, currency: str) -> Decimal | None:
        if currency == RUB:
            return Decimal(1)
        return self.rub_per_unit.get(currency)

    @staticmethod
    def from_doc(doc: object) -> Rates | None:
        """None for the placeholder (no date or no rates) and anything malformed."""
        if not isinstance(doc, dict):
            return None
        rub = doc.get("rubPerUnit")
        if not doc.get("asOf") or not isinstance(rub, dict) or not rub:
            return None
        try:
            table = {str(k): Decimal(str(v)) for k, v in rub.items() if float(v) > 0}
        except (TypeError, ValueError):
            return None
        return Rates(str(doc["asOf"]), str(doc.get("source") or ""), table) if table else None

    @staticmethod
    def load(path: Path) -> Rates | None:
        if not path.is_file():
            return None
        try:
            doc = json.loads(resources.read_file(path).decode("utf-8"))
        except (OSError, ValueError):
            return None
        return Rates.from_doc(doc)


def rate_or_none(rates: Rates | None, currency: str) -> Decimal | None:
    if currency == RUB:
        return Decimal(1)
    return rates.rate(currency) if rates is not None else None


__all__ = ["RUB", "Rates", "rate_or_none"]
