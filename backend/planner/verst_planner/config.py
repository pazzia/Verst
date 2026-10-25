"""Planner configuration (A§5.4).

Defaults ship in ``resources/planner_config.json``; production overrides (``core.app_config['planner']``)
are deep-merged by `PlannerConfig.from_dict`, which rejects unknown keys with their dotted path.
"""

from __future__ import annotations

import dataclasses
import json
import typing
from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from typing import Any

from verst_planner import resources
from verst_planner.domain.enums import Mood

RESOURCES = resources.DIR


@dataclass(frozen=True, slots=True)
class MoodInts:
    calm: int
    more_stops: int
    just_drive: int
    fun: int  # «Весело и познавательно» (ADR-0015 §5); `more_stops` is the v2 legacy value

    def of(self, mood: Mood) -> int:
        return int(getattr(self, mood.value))


@dataclass(frozen=True, slots=True)
class CorridorKm:
    sight: float
    food: float
    fuel: float
    rest: float
    fuel_motorway: float
    rest_motorway: float
    town: float
    lodging_from_town: float


@dataclass(frozen=True, slots=True)
class DetourCfg:
    winding: float
    speed_kmh: float
    access_min: int
    motorway_exit_min: int
    on_road_km: float


@dataclass(frozen=True, slots=True)
class SplitCfg:
    window_lo: float
    window_hi: float
    hard_cap: float
    widened_lo: float
    widened_hi: float
    template_hi: float
    template_lo: float


@dataclass(frozen=True, slots=True)
class OvernightScoreCfg:
    w_h: float
    w_q: float
    w_e: float
    w_km: float
    w_detour: float
    h_cap: int
    h_no_parking_weight: float
    family_room_min_people: int


@dataclass(frozen=True, slots=True)
class FuelCfg:
    usable_frac: float
    start_frac: float
    lookahead_km: float
    lookback_km: float
    coincide_km: float
    evening_next_day_km: float
    evening_window_km: float
    skip_near_finish_frac: float
    coffee_after_drive_min: int


@dataclass(frozen=True, slots=True)
class RestCfg:
    window_before_min: int
    widen_before_min: int
    widen_after_min: int
    min_remaining_drive_min: int
    break_min_dwell: int
    max_detour_min: int
    min_gap_min: int
    extended_detour_min: int


@dataclass(frozen=True, slots=True)
class DwellCfg:
    coffee: int
    fuel: int
    fuel_coffee: int
    rest: int
    lunch: int
    sight_default: int
    via: int


@dataclass(frozen=True, slots=True)
class SightsCfg:
    max_per_day: MoodInts
    min_score: float
    diversity: int = 0
    """ADR-0015 §2 diversity rules (1 = on): on for the open-data world `russia_v1`, off for the curated
    fixture worlds (their sights were picked by hand; G01-G13 keep their bytes)."""


@dataclass(frozen=True, slots=True)
class AlternativesCfg:
    window_min: int
    max: int
    cluster_km: float


@dataclass(frozen=True, slots=True)
class CostCfg:
    reserve_frac: Decimal
    line_step: int
    total_step: int
    child_food_weight_under7: Decimal
    assumed_child_age: int
    breakfast_price_frac: Decimal
    dinner_last_day_after: time


@dataclass(frozen=True, slots=True)
class PlannerConfig:
    snap_max_km: float
    too_short_km: float
    max_days: int
    corridor_km: CorridorKm
    detour: DetourCfg
    drive_time_factor: float
    day_start_first: time
    day_start_next: time
    day_budget_min: MoodInts
    split: SplitCfg
    overnight_score: OvernightScoreCfg
    overnight_eta_allowance_min: MoodInts
    fuel: FuelCfg
    rest_interval_min: MoodInts
    rest: RestCfg
    dwell_min: DwellCfg
    lunch_window: tuple[time, time]
    lunch_sweet_spot: tuple[time, time]
    sights: SightsCfg
    alternatives: AlternativesCfg
    cost: CostCfg
    toll_night: tuple[time, time]

    @classmethod
    def default(cls) -> PlannerConfig:
        return cls.from_dict({})

    @staticmethod
    def default_dict() -> dict[str, Any]:
        data: dict[str, Any] = json.loads(resources.read_text("planner_config.json"))
        return data

    @classmethod
    def from_dict(cls, d: dict[str, Any], base: PlannerConfig | None = None) -> PlannerConfig:
        """Deep-merge `d` over `base` (default: the shipped defaults) and validate."""
        raw = base.to_dict() if base is not None else cls.default_dict()
        merged = _deep_merge(raw, d, "")
        built = _build(cls, merged, "")
        assert isinstance(built, PlannerConfig)
        return built

    def to_dict(self) -> dict[str, Any]:
        out = _unbuild(self)
        assert isinstance(out, dict)
        return out


def _deep_merge(base: dict[str, Any], over: dict[str, Any], path: str) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        dotted = f"{path}{k}"
        if k not in base:
            raise ValueError(f"unknown config key: {dotted}")
        if isinstance(base[k], dict):
            if not isinstance(v, dict):
                raise ValueError(f"config key {dotted} must be an object")
            out[k] = _deep_merge(base[k], v, dotted + ".")
        else:
            out[k] = v
    return out


def _parse_time(v: Any, path: str) -> time:
    if not isinstance(v, str):
        raise ValueError(f"config key {path} must be HH:MM")
    try:
        return time.fromisoformat(v)
    except ValueError:
        raise ValueError(f"config key {path} must be HH:MM") from None


def _coerce(tp: Any, v: Any, path: str) -> Any:
    if dataclasses.is_dataclass(tp) and isinstance(tp, type):
        if not isinstance(v, dict):
            raise ValueError(f"config key {path} must be an object")
        return _build(tp, v, path + ".")
    if tp is time:
        return _parse_time(v, path)
    if typing.get_origin(tp) is tuple:
        args = typing.get_args(tp)
        if not isinstance(v, list | tuple) or len(v) != len(args):
            raise ValueError(f"config key {path} must be a list of {len(args)}")
        return tuple(_coerce(a, x, f"{path}[{i}]") for i, (a, x) in enumerate(zip(args, v, strict=True)))
    if isinstance(v, bool) or not isinstance(v, int | float):
        raise ValueError(f"config key {path} must be a number")
    if tp is Decimal:
        return Decimal(str(v))
    if tp is int:
        if float(v) != int(v):
            raise ValueError(f"config key {path} must be an integer")
        return int(v)
    return float(v)


def _build(cls: type, d: dict[str, Any], path: str) -> Any:
    hints = typing.get_type_hints(cls)
    names = [f.name for f in dataclasses.fields(cls)]
    for k in d:
        if k not in names:
            raise ValueError(f"unknown config key: {path}{k}")
    kwargs: dict[str, Any] = {}
    for name in names:
        if name not in d:
            raise ValueError(f"missing config key: {path}{name}")
        kwargs[name] = _coerce(hints[name], d[name], f"{path}{name}")
    return cls(**kwargs)


def _unbuild(v: Any) -> Any:
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return {f.name: _unbuild(getattr(v, f.name)) for f in dataclasses.fields(v)}
    if isinstance(v, time):
        return v.strftime("%H:%M")
    if isinstance(v, tuple):
        return [_unbuild(x) for x in v]
    if isinstance(v, Decimal):
        return float(v)
    return v
