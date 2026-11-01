"""The curated tables of trips abroad (CEO 29.10): `abroad_rules.json` and `border_crossings.json`.

Both are copies of `docs/plan/abroad-wave1-sources.md`: every value carries the URL and the source type given
there. The facts were read from search results, not from the opened pages, so everything built from these
tables is marked «не проверено» (`UNVERIFIED`).
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from verst_planner import resources
from verst_planner.domain.enums import FuelType

RUSSIA = "RU"
COUNTED_TYPES = frozenset({"official", "primary"})
"""Sources doc §0/§12: only an official or primary source makes an amount a fact the trip may count."""
TYPE_RU = {
    "official": "официальный источник",
    "primary": "первичный источник",
    "secondary": "вторичный источник",
}


@dataclass(frozen=True, slots=True)
class Source:
    url: str
    type: str  # official | primary | secondary

    def to_json(self) -> dict[str, str]:
        return {"url": self.url, "type": self.type, "typeRu": TYPE_RU.get(self.type, self.type)}


def _sources(rows: Any) -> tuple[Source, ...]:
    return tuple(Source(str(r["url"]), str(r["type"])) for r in rows or ())


def sources_json(sources: tuple[Source, ...]) -> list[dict[str, str]]:
    return [s.to_json() for s in sources]


@dataclass(frozen=True, slots=True)
class Fact:
    text_ru: str
    sources: tuple[Source, ...]
    months: tuple[int, ...] = ()  # a seasonal risk: the months it applies to

    def to_json(self) -> dict[str, Any]:
        return {"textRu": self.text_ru, "sources": sources_json(self.sources)}


def _facts(rows: Any) -> tuple[Fact, ...]:
    return tuple(
        Fact(str(r["textRu"]), _sources(r.get("sources")), tuple(int(m) for m in r.get("months", ())))
        for r in rows or ()
    )


@dataclass(frozen=True, slots=True)
class FuelPrice:
    """A fuel's price in the local currency: one value or the [lowest, highest] the source gives."""

    values: tuple[Decimal, ...]
    valid_from: date
    note_ru: str | None = None

    @property
    def budget(self) -> Decimal:
        """The price the trip budgets: the highest the source names (never an average we made up)."""
        return max(self.values)


@dataclass(frozen=True, slots=True)
class Fee:
    key: str
    text_ru: str
    mandatory: bool
    sources: tuple[Source, ...]
    rule_sources: tuple[Source, ...] = ()
    currency: str | None = None
    amount: Decimal | None = None
    variants: tuple[tuple[Decimal, int], ...] = ()  # (amount, days covered)
    conflict: bool = False

    @property
    def counted(self) -> bool:
        """Counted in the trip's money: mandatory, an amount from an official or primary source, not
        contradicted by another source (sources doc §12: secondary amounts are shown, never counted)."""
        has_amount = self.amount is not None or bool(self.variants)
        return (
            self.mandatory
            and has_amount
            and not self.conflict
            and self.currency is not None
            and any(s.type in COUNTED_TYPES for s in self.sources)
        )

    def amount_for(self, days: int) -> tuple[Decimal, int | None] | None:
        """(amount, days of the variant) for a trip of `days` days; None when no variant covers it."""
        if self.variants:
            fit = [(a, d) for a, d in self.variants if d >= days]
            return min(fit, key=lambda x: x[1]) if fit else None
        return (self.amount, None) if self.amount is not None else None


@dataclass(frozen=True, slots=True)
class Closure:
    until: date
    until_local: datetime  # aware, in the country's zone
    message_ru: str
    note_ru: str
    sources: tuple[Source, ...]

    def active(self, now: datetime) -> bool:
        return now < self.until_local


@dataclass(frozen=True, slots=True)
class TollInfo:
    status: str  # zero | unknown | none_found
    text_ru: str
    sources: tuple[Source, ...]


@dataclass(frozen=True, slots=True)
class CountryRules:
    code: str
    name_ru: str
    currency: str
    fuel: dict[FuelType, FuelPrice]
    fuel_sources: tuple[Source, ...]
    fuel_note_ru: str
    tolls: TollInfo
    fees: tuple[Fee, ...]
    documents: tuple[Fact, ...]
    rules: tuple[Fact, ...]
    closed: Closure | None = None


@dataclass(frozen=True, slots=True)
class Anchor:
    country: str
    towns: tuple[str, ...]
    region: str | None = None


@dataclass(frozen=True, slots=True)
class Crossing:
    id: str
    between: tuple[str, str]
    name_ru: str
    marker: bool
    anchor: Anchor | None
    facts: tuple[Fact, ...]
    risks: tuple[Fact, ...]
    wait: Fact | None


def _dec(v: Any) -> Decimal:
    return Decimal(str(v))


def _fee(r: dict[str, Any]) -> Fee:
    return Fee(
        key=str(r["key"]),
        text_ru=str(r["textRu"]),
        mandatory=bool(r.get("mandatory", False)),
        sources=_sources(r.get("sources")),
        rule_sources=_sources(r.get("ruleSources")),
        currency=r.get("currency"),
        amount=_dec(r["amount"]) if r.get("amount") is not None else None,
        variants=tuple((_dec(v["amount"]), int(v["days"])) for v in r.get("variants", ())),
        conflict=bool(r.get("conflict", False)),
    )


def _country(code: str, r: dict[str, Any]) -> CountryRules:
    closed = None
    if r.get("closed"):
        c = r["closed"]
        until_local = datetime.fromisoformat(str(c["untilLocal"])).replace(tzinfo=ZoneInfo(str(c["tz"])))
        closed = Closure(
            date.fromisoformat(str(c["until"])),
            until_local,
            str(c["messageRu"]),
            str(c.get("noteRu", "")),
            _sources(c.get("sources")),
        )
    fuel = {
        FuelType(k): FuelPrice(
            tuple(_dec(x) for x in v["values"]), date.fromisoformat(str(v["validFrom"])), v.get("noteRu")
        )
        for k, v in (r.get("fuel") or {}).items()
    }
    t = r["tolls"]
    return CountryRules(
        code=code,
        name_ru=str(r["nameRu"]),
        currency=str(r["currency"]),
        fuel=fuel,
        fuel_sources=_sources(r.get("fuelSources")),
        fuel_note_ru=str(r.get("fuelNoteRu", "")),
        tolls=TollInfo(str(t["status"]), str(t["textRu"]), _sources(t.get("sources"))),
        fees=tuple(_fee(f) for f in r.get("fees", ())),
        documents=_facts(r.get("documents")),
        rules=_facts(r.get("rules")),
        closed=closed,
    )


def _crossing(r: dict[str, Any]) -> Crossing:
    a = r.get("anchor")
    anchor = None
    if a:
        anchor = Anchor(str(a["country"]), tuple(str(x) for x in a.get("towns", ())), a.get("region"))
    wait = r.get("wait")
    a_, b_ = r["between"]
    return Crossing(
        id=str(r["id"]),
        between=(str(a_), str(b_)),
        name_ru=str(r["nameRu"]),
        marker=bool(r.get("marker", False)),
        anchor=anchor,
        facts=_facts(r.get("facts")),
        risks=_facts(r.get("risks")),
        wait=Fact(str(wait["textRu"]), _sources(wait.get("sources"))) if wait else None,
    )


@dataclass(frozen=True, slots=True)
class Rules:
    checked_at: date
    countries: dict[str, CountryRules]
    crossings: tuple[Crossing, ...]

    @staticmethod
    def from_docs(rules: dict[str, Any], crossings: dict[str, Any]) -> Rules:
        return Rules(
            checked_at=date.fromisoformat(str(rules["checkedAt"])),
            countries={k: _country(k, v) for k, v in rules["countries"].items()},
            crossings=tuple(_crossing(c) for c in crossings["crossings"]),
        )

    @staticmethod
    def from_resources() -> Rules:
        return Rules.from_docs(
            json.loads(resources.read_text("abroad_rules.json")),
            json.loads(resources.read_text("border_crossings.json")),
        )

    def path(self, a: str, b: str, allowed: frozenset[str]) -> list[Crossing] | None:
        """The crossings of the shortest country path from `a` to `b` through `allowed` countries (breadth
        first, ties by the table order), or None when there is none. Same country → []."""
        if a == b:
            return []
        prev: dict[str, tuple[str, Crossing] | None] = {a: None}
        queue = deque([a])
        while queue:
            cur = queue.popleft()
            for c in self.crossings:
                if cur not in c.between:
                    continue
                nxt = c.between[1] if c.between[0] == cur else c.between[0]
                if nxt in prev or nxt not in allowed:
                    continue
                prev[nxt] = (cur, c)
                if nxt == b:
                    out: list[Crossing] = []
                    node = b
                    while (step := prev[node]) is not None:
                        out.append(step[1])
                        node = step[0]
                    return out[::-1]
                queue.append(nxt)
        return None


UNVERIFIED_RU = (
    "Цены, сборы и правила за границей взяты из текста поисковой выдачи 29.10.2026; страницы первоисточников "
    "не открывались — не проверено."
)

__all__ = [
    "RUSSIA",
    "UNVERIFIED_RU",
    "Anchor",
    "Closure",
    "CountryRules",
    "Crossing",
    "Fact",
    "Fee",
    "FuelPrice",
    "Rules",
    "Source",
    "TollInfo",
    "sources_json",
]
