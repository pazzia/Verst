"""Presets, interests, pace, dwell and the walking model of ADR-0013 (one table each)."""

from __future__ import annotations

from dataclasses import dataclass

SIGHT_KINDS = (
    "museum",
    "kremlin",
    "monastery",
    "church",
    "monument",
    "park",
    "viewpoint",
    "embankment",
    "square",
    "attraction",
    # Sprint 4 (ADR-0015 §2) catalogue kinds
    "theatre",
    "zoo",
    "nature",
    "interactive",
    "playground",
)
BAR_KINDS = ("ryumochnaya", "pub", "craft", "bar")
DRINK_KINDS = frozenset(BAR_KINDS)
# CEO 2026-10-29: «Еда» — OSM restaurants, cafés, fast food, food courts (`catalogue_food`)
FOOD_KINDS = ("restaurant", "cafe", "fast_food", "food_court")
EAT_KINDS = frozenset(FOOD_KINDS)
PRESETS = ("overview", "museums", "dog_walk", "ryumochnye", "beer", "custom")
# ADR-0015 §6: places a dog usually may not enter (a warning per stop, never a block)
INDOOR_KINDS = frozenset(
    {"museum", "theatre", "interactive", "ryumochnaya", "pub", "craft", "bar"}
    | {"restaurant", "cafe", "food_court"}
)
UNLIMITED_MIN = 480  # «без ограничения»: the solver's budget; the result has no timetable
UNLIMITED_RADIUS_KM = 6.0
UNLIMITED_MAX_STOPS = 12
ADULT_PRESETS = frozenset({"ryumochnye", "beer"})
INTERESTS = ("history", "architecture", "museums", "parks", "food", "bars", "views")
DURATIONS = (120, 240, 360, 480)
PACES = {"slow": (3.5, 1.25), "normal": (4.5, 1.0), "fast": (5.5, 0.8)}  # km/h, dwell multiplier

WALK_FACTOR = 1.30
MAX_LEG_KM = 2.5
RADIUS_MAX_KM = {120: 3.0, 240: 4.0, 360: 5.0, 480: 6.0}
POOL_MAX = 60
NO_CITY_KM = 15.0
DIVERSITY = 0.6

DWELL = {
    "museum": 75,
    "kremlin": 50,
    "monastery": 50,
    "church": 20,
    "monument": 10,
    "square": 10,
    "viewpoint": 15,
    "embankment": 15,
    "park": 35,
    "attraction": 20,
    "theatre": 20,
    "zoo": 90,
    "nature": 40,
    "interactive": 60,
    "playground": 20,
    "bar": 40,
    "pub": 40,
    "craft": 40,
    "ryumochnaya": 25,
    "meal": 45,
    # CEO 2026-10-29: a sit-down meal, a coffee and a cake, a quick bite
    "restaurant": 60,
    "cafe": 40,
    "fast_food": 20,
    "food_court": 30,
}
BIG_MUSEUM_SITELINKS = 40
BIG_MUSEUM_DWELL = 90
# Release S3: «Музейный» in СПб gave 3 stops in 6 h (75-90 min per museum at the slow pace's 1.25). In this
# preset a museum gets 50 min scaled by the pace and a big one (>= 40 sitelinks: Эрмитаж, ГИМ) a flat 90 min
# (never over 2 h) with a «только главное» note; at most two short sights fill the gaps.
MUSEUM_WALK_DWELL = 50
MUSEUM_DWELL_CAP_MIN = 120
DRINK_RUB = {"ryumochnaya": 300, "pub": 600, "craft": 600, "bar": 500}
MEAL_RUB = 600
# CEO 2026-10-29: OSM gives no prices for restaurants and cafés — a food stop's price is unknown (null), never
# an estimate (ADR-0019 E-2); the generic «Обед» stop keeps MEAL_RUB, it is not a real place.
TICKETS = {"museum": (400, 200), "kremlin": (300, 150), "monastery": (300, 150)}
DEFAULT_HOURS = {"museum": "Tu-Su 10:00-18:00", "church": "Mo-Su 08:00-20:00"}
BAR_DEFAULT_HOURS = "Mo-Su 16:00-02:00"

INTEREST_KINDS: dict[str, dict[str, float]] = {
    "history": {
        "kremlin": 1.0,
        "monastery": 1.0,
        "monument": 0.9,
        "church": 0.8,
        "museum": 0.7,
        "square": 0.6,
    },
    "architecture": {"church": 1.0, "kremlin": 1.0, "monastery": 0.9, "square": 0.9, "attraction": 0.9},
    "museums": {"museum": 1.0},
    "parks": {"park": 1.0, "embankment": 0.9, "nature": 1.0, "zoo": 0.6, "playground": 0.4},
    "views": {"viewpoint": 1.0, "embankment": 0.9, "park": 0.5, "nature": 0.7},
    "bars": {"bar": 1.0, "pub": 1.0, "craft": 1.0, "ryumochnaya": 1.0},
    "food": {"restaurant": 1.0, "cafe": 1.0, "food_court": 0.6, "fast_food": 0.5},
}


@dataclass(frozen=True, slots=True)
class Preset:
    key: str
    weights: dict[str, float]
    gate_kinds: frozenset[str]
    gate_min: int
    default_duration: int
    default_pace: str
    caps: dict[str, int]
    museum_dwell_cap: int | None = None


PRESET_TABLE: dict[str, Preset] = {
    "overview": Preset(
        "overview",
        {
            "kremlin": 1.0,
            "monastery": 1.0,
            "church": 1.0,
            "attraction": 1.0,
            "monument": 0.9,
            "square": 0.9,
            "embankment": 0.9,
            "viewpoint": 0.9,
            "museum": 0.6,
            "park": 0.6,
        },
        frozenset(SIGHT_KINDS),
        4,
        240,
        "normal",
        {"museum": 2},
        museum_dwell_cap=45,
    ),
    # ADR-0015 §6 dog_walk: outdoor places only. Acceptance 2026-10-28 (traveller K3, V3): only the open
    # spaces a dog walks through — parks, nature, embankments, viewpoints, squares. A kremlin (Царь-пушка is
    # inside the ticketed Кремль), a monument (the Мавзолей) and an «attraction» (ГУМ) are not a dog walk.
    "dog_walk": Preset(
        "dog_walk",
        {
            "park": 1.0,
            "nature": 1.0,
            "embankment": 1.0,
            "viewpoint": 0.8,
            "square": 0.6,
        },
        frozenset({"park", "nature", "embankment", "viewpoint", "square"}),
        2,
        120,
        "normal",
        {},
    ),
    "museums": Preset(
        "museums",
        {"museum": 1.0, "kremlin": 0.3, "monastery": 0.25, "church": 0.2, "monument": 0.15, "square": 0.1},
        frozenset({"museum"}),
        3,
        360,
        "slow",
        {"museum": 5, "others": 2},
    ),
    # CEO 2026-10-29: strict — «По рюмочным» only рюмочные, «Пивной» only beer places; never padded with
    # generic bars (a town with few of them gets a shorter walk and says so)
    "ryumochnye": Preset(
        "ryumochnye",
        {"ryumochnaya": 1.0},
        frozenset({"ryumochnaya"}),
        3,
        240,
        "normal",
        {"drinks": 5},
    ),
    "beer": Preset(
        "beer",
        {"craft": 1.0, "pub": 0.9},
        frozenset({"pub", "craft"}),
        3,
        240,
        "normal",
        {"drinks": 5},
    ),
}
HERITAGE_BONUS = 10.0


def custom_weights(interests: tuple[str, ...], widened: bool = False) -> dict[str, float]:
    """Max over the chosen interests. The interests filter (S4 bug b3: they were weights, so «парки» in a
    town without parks gave the same monuments): other sights get 0, or 0.15 when `widened` (the fallback
    when the chosen kinds give fewer than two places); bars only when «бары» is chosen, food places only when
    «еда» is chosen."""
    chosen: dict[str, float] = {}
    for i in interests:
        for k, v in INTEREST_KINDS[i].items():
            chosen[k] = max(chosen.get(k, 0.0), v)
    base = (
        {k: (0.15 if widened else 0.0) for k in SIGHT_KINDS}
        | {k: 0.0 for k in BAR_KINDS}
        | {k: 0.0 for k in FOOD_KINDS}
    )
    return {k: chosen.get(k, v) for k, v in base.items()}


def radius_km(duration_min: int | None, speed_kmh: float) -> float:
    if duration_min is None:
        return UNLIMITED_RADIUS_KM
    return min(0.45 * speed_kmh * duration_min / 60.0, RADIUS_MAX_KM.get(duration_min, 6.0))
