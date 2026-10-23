"""Shared test factories (A§2 `tests/helpers.py`)."""

from __future__ import annotations

import itertools
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from verst_planner.domain.enums import (
    CostKey,
    FuelType,
    Meal,
    Mood,
    PlaceStatus,
    PlaceType,
    RoadClass,
    SignType,
    Source,
    StopKind,
    Tag,
    WarningCode,
)
from verst_planner.domain.model import (
    Alternative,
    AltUnits,
    CandidateState,
    CostBreakdownRow,
    CostLine,
    CostResult,
    CostUnits,
    Crew,
    DayResult,
    DayState,
    EngineState,
    FuelRegionUnit,
    FuelUnits,
    HotelOption,
    HotelPrice,
    LatLon,
    MealUnit,
    NightUnit,
    NormalizedInput,
    OvernightReason,
    PartnerIds,
    Place,
    PlanWarning,
    PointInput,
    Route,
    RouteDetail,
    ScheduledStop,
    StopState,
    TicketUnit,
    TollHit,
    TollSegment,
    TollUnit,
    Town,
    TripPlan,
    Vehicle,
)

PLANNER_ROOT = Path(__file__).resolve().parent.parent
WORLDS = PLANNER_ROOT / "fixtures" / "worlds"
UNIT_DATA = Path(__file__).resolve().parent / "unit" / "data"
MSK = ZoneInfo("Europe/Moscow")


def make_place(
    id: str = "pl_x",
    type: PlaceType = PlaceType.SIGHT,
    lat: float = 56.0,
    lon: float = 38.0,
    tags: frozenset[Tag] | set[Tag] = frozenset(),
    **kw: Any,
) -> Place:
    base: dict[str, Any] = {
        "name_ru": "Место",
        "address": None,
        "region_code": "RU-MOS",
        "town_id": None,
        "opening_hours": None,
        "dwell_min": None,
        "avg_check_rub": None,
        "price_night_rub": None,
        "ticket_adult_rub": None,
        "ticket_child_rub": None,
        "rating_internal": 4.0,
        "description_ru": None,
        "partner_ids": PartnerIds(),
        "source": Source.CURATED,
        "verified_at": date(2026, 9, 1),
        "status": PlaceStatus.LIVE,
    }
    base.update(kw)
    return Place(id=id, type=type, point=LatLon(lat, lon), tags=frozenset(tags), **base)


def make_town(id: str = "t_x", lat: float = 56.0, lon: float = 38.0, **kw: Any) -> Town:
    base: dict[str, Any] = {
        "name_ru": "Город",
        "name_prep_ru": "Городе",
        "region_code": "RU-MOS",
        "population": 50_000,
        "quality": 1,
        "evening_walk": False,
        "lodging_count_cache": 0,
    }
    base.update(kw)
    return Town(id=id, point=LatLon(lat, lon), **base)


def sample_normalized() -> NormalizedInput:
    return NormalizedInput(
        origin=PointInput(LatLon(55.7558, 37.6173), "Москва"),
        destination=PointInput(LatLon(57.6261, 39.8845), "Ярославль", None, "t_yaroslavl"),
        vias=(),
        ready_route_id=None,
        round_trip=False,
        crew=Crew(2, 1, True, (5,)),
        daily_km=300,
        budget_rub=40_000,
        vehicle=Vehicle(7.5, FuelType.AI95, 55.0),
        start_at=datetime(2026, 10, 24, 8, 0, tzinfo=MSK),
        mood=Mood.CALM,
        avoid_tolls=False,
        reserve_on=True,
        simplify=False,
        tz="Europe/Moscow",
    )


def _stop(
    id: str,
    seq: int,
    kind: StopKind,
    sign: SignType,
    name: str,
    km_at: int,
    km_prev: int,
    arrive: datetime | None,
    depart: datetime | None,
    **kw: Any,
) -> ScheduledStop:
    base: dict[str, Any] = {
        "place_id": None,
        "town_id": None,
        "note_ru": None,
        "tz": "Europe/Moscow",
        "dwell_min": 0,
        "tags": (),
        "cost_rub": 0,
        "verified": True,
        "reason_ru": "",
        "replaceable": False,
        "alternatives": (),
        "hotel_options": (),
        "selected_hotel_id": None,
    }
    base.update(kw)
    return ScheduledStop(
        id=id,
        seq=seq,
        day=int(id[1]),
        kind=kind,
        sign=sign,
        name_ru=name,
        point=LatLon(56.0, 38.0),
        arrive_at=arrive,
        depart_at=depart,
        km_from_prev=km_prev,
        km_at=km_at,
        **base,
    )


def sample_plan() -> TripPlan:
    """A small hand-built 2-day plan (Москва → Ярославль with one overnight in Ростов)."""
    d = datetime
    alt_stop = _stop(
        "d1s02",
        2,
        StopKind.FOOD,
        SignType.FOOD,
        "Кафе «Дорога»",
        120,
        120,
        d(2026, 10, 24, 12, 50),
        d(2026, 10, 24, 13, 50),
        place_id="pl_cafe2",
        dwell_min=60,
        cost_rub=1750,
        reason_ru="Обед в Переславле.",
        replaceable=True,
    )
    alt = Alternative(
        id="alt_d1s02_pl_cafe2",
        place_id="pl_cafe2",
        name_ru="Кафе «Дорога»",
        delta_min=5,
        delta_rub=-250,
        shift_min=5,
        stop=alt_stop,
        units=AltUnits(0.8, "RU-YAR", 700, None, None, "Кафе «Дорога»", "pl_cafe2"),
    )
    day1 = DayResult(
        day=1,
        km=200,
        drive_min=170,
        tz="Europe/Moscow",
        start_at=d(2026, 10, 24, 8, 0),
        end_at=d(2026, 10, 24, 15, 30),
        stops=(
            _stop(
                "d1s01",
                1,
                StopKind.START,
                SignType.CITY,
                "Москва",
                0,
                0,
                None,
                d(2026, 10, 24, 8, 0),
                reason_ru="Выезд в 08:00.",
            ),
            _stop(
                "d1s02",
                2,
                StopKind.FOOD,
                SignType.FOOD,
                "Кафе «Ель»",
                118,
                118,
                d(2026, 10, 24, 12, 45),
                d(2026, 10, 24, 13, 45),
                place_id="pl_cafe1",
                dwell_min=60,
                tags=(Tag.KIDS_MENU,),
                cost_rub=2000,
                reason_ru="Обед, есть детское меню.",
                replaceable=True,
                alternatives=(alt,),
            ),
            _stop(
                "d1s03",
                3,
                StopKind.OVERNIGHT,
                SignType.HOTEL,
                "Ростов",
                200,
                82,
                d(2026, 10, 24, 15, 30),
                None,
                town_id="t_rostov",
                place_id="pl_rst_hotel",
                cost_rub=5000,
                reason_ru="Как раз на вашей норме.",
                hotel_options=(
                    HotelOption(
                        "pl_rst_hotel", "Отель «Ростов»", (Tag.DOGS_ALLOWED, Tag.PARKING), 5000, 1, 5000, True
                    ),
                ),
                selected_hotel_id="pl_rst_hotel",
            ),
        ),
        over_budget=False,
    )
    day2 = DayResult(
        day=2,
        km=55,
        drive_min=50,
        tz="Europe/Moscow",
        start_at=d(2026, 10, 25, 9, 0),
        end_at=d(2026, 10, 25, 9, 50),
        stops=(
            _stop("d2s01", 4, StopKind.START, SignType.CITY, "Ростов", 200, 0, None, d(2026, 10, 25, 9, 0)),
            _stop(
                "d2s02",
                5,
                StopKind.FINISH,
                SignType.CITY,
                "Ярославль",
                255,
                55,
                d(2026, 10, 25, 9, 50),
                None,
                town_id="t_yaroslavl",
                reason_ru="Финиш.",
            ),
        ),
        over_budget=False,
    )
    units = CostUnits(
        fuel=FuelUnits(
            7.5,
            FuelType.AI95,
            (
                FuelRegionUnit("RU-MOS", "Московская область", 120.5, Decimal("61.20")),
                FuelRegionUnit("RU-YAR", "Ярославская область", 134.5, Decimal("61.90")),
            ),
            "2026-10",
        ),
        tolls=(TollUnit("ts_1", "М-12", 800, False, "2026-10"),),
        nights=(
            NightUnit(
                "d1s03",
                1,
                "Ростов",
                "pl_rst_hotel",
                5000,
                (HotelPrice("pl_rst_hotel", 5000, True),),
                False,
                True,
                330,
            ),
        ),
        meals=(MealUnit(1, Meal.LUNCH, "d1s02", 800), MealUnit(1, Meal.DINNER, None, 700)),
        tickets=(TicketUnit("d1s04", "pl_kreml", "Ростовский кремль", 400, 200),),
        reserve_frac=Decimal("0.10"),
        line_step=10,
        total_step=100,
        child_ages=(5,),
        assumed_child_age=8,
        child_food_weight_under7=Decimal("0.50"),
        as_of=(("fuel", "2026-10"), ("lodging", "2026-09")),
    )
    cost = CostResult(
        lines=(
            CostLine(
                CostKey.FUEL,
                "Бензин",
                1180,
                "255 км × 7,5 л/100 × ≈ 61,60 ₽",
                "2026-10",
                (CostBreakdownRow("Московская область", "120 км × 7,5 л/100 × 61,20 ₽", 550),),
            ),
            CostLine(CostKey.TOLLS, "Платные дороги", 800, "М-12: 800 ₽", "2026-10", ()),
            CostLine(CostKey.LODGING, "Ночёвки", 5000, "Ростов, 1 × 5 000", "2026-09", ()),
            CostLine(CostKey.FOOD, "Еда", 3750, "2,5 чел. × 2 приёма × ≈ 750 (в среднем)", "2026-09", ()),
            CostLine(CostKey.TICKETS, "Билеты", 1000, "1 место × (2 взр. + 1 реб.)", "2026-09", ()),
            CostLine(CostKey.RESERVE, "Запас", 1170, "10% на пробки", "2026-10", (), enabled=True),
        ),
        reserve_on=True,
        subtotal_rub=11730,
        total_rub=12900,
        per_person_rub=4300,
        budget_rub=40000,
        remaining_rub=27100,
        over_budget=False,
        hint_keys=(),
        prices_as_of="2026-09",
        units=units,
        hints_ru=(),
    )
    seg = TollSegment(
        "ts_1",
        "М-12",
        "М-12 Москва — Владимир",
        Decimal("800"),
        Decimal("560"),
        1,
        time(0, 0),
        time(6, 0),
        date(2026, 10, 1),
    )
    state = EngineState(
        profile_km=(0.0, 1.0, 2.0),
        profile_min=(0.0, 0.8, 1.6),
        region_km=(("RU-MOS", 120.5), ("RU-YAR", 134.5)),
        toll_hits=(TollHit(seg, 10.0, 60.5),),
        drive_time_factor=1.1,
        days=(
            DayState(
                1,
                0.0,
                200.0,
                datetime(2026, 10, 24, 8, 0, tzinfo=MSK),
                "Europe/Moscow",
                540,
                (
                    StopState(
                        "d1s02", StopKind.FOOD, 118.2, 0.8, 3, 60, False, True, 5.5, "pl_cafe1", "RU-YAR"
                    ),
                ),
            ),
        ),
        candidates=(CandidateState("pl_cafe2", 120.0, 0.3, 0.78, 3, RoadClass.TRUNK, "RU-YAR"),),
        rerun=1,
    )
    return TripPlan(
        title_ru="Москва → Ярославль",
        km=255,
        days=2,
        nights=1,
        round_trip=False,
        days_list=(day1, day2),
        cost=cost,
        overnight_reasons=(
            OvernightReason(
                1, "t_rostov", "Ростов", "Как раз на вашей дневной норме.", ("Переславль-Залесский", "Ростов")
            ),
        ),
        warnings=(PlanWarning(WarningCode.FUEL_GAP, 1, "На участке 120 км мало заправок", "km=120"),),
        input=sample_normalized(),
        engine_version="0.1.0",
        engine_state=state,
    )


def make_route(
    points: list[LatLon] | list[tuple[float, float]],
    speed_kmh: float = 60.0,
    road_class: RoadClass = RoadClass.TRUNK,
    road_ref: str | None = "М-8",
    cum_km: list[float] | None = None,
) -> Route:
    """A route through `points`; `cum_km` defaults to cumulative haversine distance."""
    from verst_planner.geo.distance import haversine_km

    pts = tuple(p if isinstance(p, LatLon) else LatLon(*p) for p in points)
    if cum_km is None:
        cum = [0.0]
        for a, b in itertools.pairwise(pts):
            cum.append(cum[-1] + haversine_km(a, b))
    else:
        cum = list(cum_km)
    mins = tuple(k / speed_kmh * 60.0 for k in cum)
    return Route(
        points=pts,
        cum_km=tuple(cum),
        cum_min=mins,
        details=(RouteDetail(0, len(pts) - 1, road_class, road_ref, False),),
        waypoint_idx=(0, len(pts) - 1),
        snapped=(pts[0], pts[-1]),
        km_total=cum[-1],
        min_total=mins[-1],
    )


def line_north(lat0: float, lon0: float, km: float, step_km: float = 1.0) -> list[LatLon]:
    """Points every `step_km` along a meridian going north for `km` kilometres."""
    n = round(km / step_km)
    return [LatLon(lat0 + i * step_km / 111.195, lon0) for i in range(n + 1)]


def make_ctx(
    world: str | Path = "central_russia_v1",
    now: datetime | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[Any, Any]:
    """`(PlanContext, FakePorts)` over a fixture world name (or a path)."""
    from verst_planner.adapters.fake import GOLDEN_CLOCK, build_fakes
    from verst_planner.config import PlannerConfig
    from verst_planner.explain.templates import ReasonTemplates
    from verst_planner.pipeline import PlanContext, Ports

    path = world if isinstance(world, Path) else WORLDS / f"{world}.json"
    fakes = build_fakes(_load_world(str(path)), now or GOLDEN_CLOCK)
    ctx = PlanContext(
        cfg=PlannerConfig.from_dict(config or {}),
        templates=ReasonTemplates.default(),
        ports=Ports(fakes.routing, fakes.places, fakes.prices, fakes.tolls, fakes.regions, fakes.geocoding),
        clock=fakes.clock,
    )
    return ctx, fakes


_WORLD_CACHE: dict[str, Any] = {}


def _load_world(path: str) -> Any:
    from verst_planner.adapters.fake import FakeWorld

    if path not in _WORLD_CACHE:
        _WORLD_CACHE[path] = FakeWorld.load(path)
    return _WORLD_CACHE[path]


def town_point(world: str, town_id: str) -> LatLon:
    w = _load_world(str(WORLDS / f"{world}.json"))
    p: LatLon = w.towns[town_id].point
    return p


def trip(
    origin: str = "t_moscow",
    destination: str | None = "t_yaroslavl",
    world: str | Path = "central_russia_v1",
    vias: tuple[str, ...] = (),
    **kw: Any,
) -> Any:
    """A `TripInput` between fixture towns (labels = town names)."""
    from verst_planner.domain.model import TripInput

    w = _load_world(str(world if isinstance(world, Path) else WORLDS / f"{world}.json"))

    def pi(tid: str) -> PointInput:
        t = w.towns[tid]
        return PointInput(t.point, t.name_ru, None, tid)

    base: dict[str, Any] = {
        "crew": Crew(2, 0, False),
        "daily_km": 300,
        "start_at": datetime(2026, 10, 24, 8, 0),
    }
    base.update(kw)
    return TripInput(
        origin=pi(origin),
        destination=pi(destination) if destination else None,
        vias=tuple(pi(v) for v in vias),
        **base,
    )


def make_planner(
    world: str | Path = "central_russia_v1", now: datetime | None = None, config: dict[str, Any] | None = None
) -> tuple[Any, Any]:
    """`(Planner, FakePorts)` over a fixture world (fresh fakes, so spy counters start at zero)."""
    from verst_planner.adapters.fake import GOLDEN_CLOCK, build_fakes
    from verst_planner.config import PlannerConfig
    from verst_planner.engine import Planner
    from verst_planner.explain.templates import ReasonTemplates

    path = world if isinstance(world, Path) else WORLDS / f"{world}.json"
    f = build_fakes(_load_world(str(path)), now or GOLDEN_CLOCK)
    planner = Planner(
        routing=f.routing,
        places=f.places,
        prices=f.prices,
        tolls=f.tolls,
        regions=f.regions,
        geocoding=f.geocoding,
        clock=f.clock,
        config=PlannerConfig.from_dict(config or {}),
        templates=ReasonTemplates.default(),
    )
    return planner, f
