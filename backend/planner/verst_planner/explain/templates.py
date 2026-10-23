"""Reason templates (A§8.1): ``{key: "text with {placeholders}"}`` loaded from config."""

from __future__ import annotations

import json
import string
from collections.abc import Mapping
from pathlib import Path
from typing import Any

RESOURCES = Path(__file__).resolve().parent.parent / "resources"

TEMPLATE_KEYS: tuple[str, ...] = (
    "overnight.shift.hotels",
    "overnight.shift.quality",
    "overnight.shift.evening",
    "overnight.on_target",
    "overnight.cap_ok",
    "overnight.shift.later",
    "overnight.shift.earlier",
    "overnight.shift.limit",
    "overnight.widened",
    "overnight.no_hotel",
    "overnight.template",
    "crew_suffix.dog",
    "crew_suffix.family",
    "crew_suffix.none",
    "fuel.evening",
    "fuel.range",
    "fuel.coincide",
    "fuel.last",
    "rest.generic",
    "rest.who",
    "lunch.kids",
    "lunch.parking",
    "lunch.default",
    "sight.default",
    "sight.dog_waits",
    "sight.osm",
    "start.default",
    "finish.home",
    "finish.default",
    "via.user",
    "alternatives.none",
    "alternatives.one",
    "stage.route",
    "stage.split",
    "stage.split_ring",
    "stage.lodging.dog",
    "stage.lodging.family",
    "stage.lodging.default",
    "stage.lodging.none",
    "stage.hours",
    "stage.fuel",
    "stage.cost",
    "hint.cheaper_overnight",
    "hint.fewer_sights",
    "hint.just_drive",
    "warning.NO_LODGING",
    "warning.FUEL_GAP",
    "warning.DAY_OVER_BUDGET",
    "warning.TOLLS_UNAVOIDABLE",
    "warning.UNVERIFIED_PLACES",
    "warning.STOP_CLOSED",
)
"""Every key of A§8.1, all required."""


class _SafeDict(dict[str, Any]):
    def __missing__(self, key: str) -> Any:
        raise KeyError(f"missing template parameter: {key}")


def placeholders(text: str) -> frozenset[str]:
    return frozenset(name for _, name, _, _ in string.Formatter().parse(text) if name)


class ReasonTemplates:
    def __init__(self, templates: Mapping[str, str]) -> None:
        missing = [k for k in TEMPLATE_KEYS if k not in templates]
        if missing:
            raise ValueError(f"missing reason templates: {', '.join(missing)}")
        unknown = [k for k in templates if k not in TEMPLATE_KEYS]
        if unknown:
            raise ValueError(f"unknown reason templates: {', '.join(unknown)}")
        self._t = dict(templates)

    @classmethod
    def default(cls) -> ReasonTemplates:
        with (RESOURCES / "reasons.ru.json").open(encoding="utf-8") as f:
            return cls(json.load(f))

    @classmethod
    def from_dict(cls, d: Mapping[str, str]) -> ReasonTemplates:
        return cls(d)

    def keys(self) -> tuple[str, ...]:
        return tuple(self._t)

    def raw(self, key: str) -> str:
        return self._t[key]

    def render(self, key: str, **params: str | int | float) -> str:
        """Render `key` with its first character capitalised (copy review R-3: one rule for every reason).

        Unknown keys and missing parameters raise `KeyError`. Fragments that start with a space or a comma
        (`overnight.cap_ok`, `crew_suffix.*`) are unaffected by the capitalisation.
        """
        if key not in self._t:
            raise KeyError(f"unknown template: {key}")
        text = self._t[key].format_map(_SafeDict(params))
        return text[:1].upper() + text[1:]
