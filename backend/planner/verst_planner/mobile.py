"""App-facing engine API for the on-device mock build (DEV-111, M§5.1, ADR-0010).

A stdlib-only composition root like `cli.py`: the Android app (Chaquopy) calls only these functions.
Every public function takes and returns JSON `str` and never raises, not even while serialising its
result. The envelope is

    {"ok": true,  "result": <payload>, "ms": 12}
    {"ok": false, "error": {"code", "message", "field", "reason", "pointIndex", "roadKm", "detail"}, "ms": 3}

Error codes: the `PlannerError.code` values (`INVALID_INPUT` with `field`/`reason`, `UNREACHABLE` with
`pointIndex`, `TOO_SHORT` with `roadKm`, `UPSTREAM`, `NOT_FOUND`, `CANCELLED`), plus `NO_WORLD`,
`TZDATA_MISSING`, `TRIP_INCOMPATIBLE` (a trip whose `engineVersion` differs from `ENGINE_VERSION` in
major.minor; `field` = `engineVersion`) and `INTERNAL` (any other exception; the traceback goes to `detail`
and to stderr, which Chaquopy routes to logcat). `message` is diagnostic English for logs only: the app picks
its copy by `code` (and `field`/`reason`) alone. Arguments are decoded strictly: JSON booleans only where a
boolean is expected, integers that are not booleans, strings where a string is expected.

`API_VERSION` (returned by `selfcheck` as `apiVersion`) changes whenever a signature or envelope changes.

Threading: the app makes every call from one thread (`verst-python`, M§5.2) — the module state (worlds, clock)
is not guarded otherwise. `cancel` is the only call allowed from another thread. A `cancel` for an id that
has no running `plan` leaves a tombstone (the last 32 ids are kept): a later `plan` with that id returns
`CANCELLED` at once, so a cancel that overtakes its plan is not lost.

CLI: ``python3 -m verst_planner.mobile selftest [--world PATH …]`` runs the whole API against the worlds
(default: both fixture worlds next to the package) and prints one ``OK <function> <ms>`` line per call.
"""

from __future__ import annotations

import argparse
import dataclasses
import gc
import json
import sys
import threading
import time
import traceback
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from verst_planner import ENGINE_VERSION
from verst_planner import handoff as handoff_mod
from verst_planner.adapters.catalogue import CataloguePorts, CatalogueWorld, build_catalogue_ports, compose
from verst_planner.adapters.catalogue.world import WORLD_ID as CATALOGUE_WORLD
from verst_planner.adapters.fake import GOLDEN_CLOCK, FakePorts, FakeWorld, build_fakes
from verst_planner.catalogue import Catalogue, CatalogueError, load_packaged
from verst_planner.catalogue.photos import image_urls
from verst_planner.city import presets as city_presets_mod
from verst_planner.city.route import NotEnoughPois, WalkTown, build_walk, request_key
from verst_planner.city.walk import (
    Candidate,
    WalkInput,
    bar_hours,
    dwell_for,
    long_visit,
    parse_input,
    planned_start,
    weights_for,
)
from verst_planner.config import PlannerConfig
from verst_planner.domain import codec
from verst_planner.domain.enums import PlaceType, Source, Tag
from verst_planner.domain.errors import (
    InvalidInput,
    NotFound,
    PlanCancelled,
    PlannerError,
    TooShort,
    Unreachable,
)
from verst_planner.domain.model import UNSET, CostPatch, GeoSuggestion, LatLon, Place, Town, TripPlan
from verst_planner.engine import Planner
from verst_planner.events import NULL_SINK, CancelToken, PlanEvent, event_to_json
from verst_planner.explain import ru
from verst_planner.explain.share import share_text as render_share_text
from verst_planner.explain.templates import ReasonTemplates
from verst_planner.fit import NoFit
from verst_planner.geo.bearing import bearing8
from verst_planner.geo.distance import haversine_km
from verst_planner.geo.grid import GridIndex
from verst_planner.hours import parse as parse_hours
from verst_planner.parking import ParkingInfo
from verst_planner.pipeline.sights import category_of

API_VERSION = 3
REQUIRED_ZONES = ("Europe/Moscow", "Europe/Volgograd")
TOMBSTONES = 32


class Listener(Protocol):
    """The Kotlin `PlanEventListener` (duck-typed: anything with `onEvent(str)`)."""

    def onEvent(self, event_json: str) -> object: ...


class EngineFailure(Exception):
    """App-facing error that is no `PlannerError`: `NO_WORLD`, `TZDATA_MISSING`, `TRIP_INCOMPATIBLE`."""

    def __init__(self, code: str, message: str = "", field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.field = field


class SystemClock:
    """Wall-clock time (aware UTC); the default on the phone."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class _Fixed:
    def __init__(self, dt: datetime) -> None:
        self._dt = dt.astimezone(UTC)

    def now(self) -> datetime:
        return self._dt


@dataclass(slots=True)
class _World:
    world: FakeWorld
    fakes: FakePorts | CataloguePorts
    planner: Planner
    catalogue: CatalogueWorld | None = None
    bars: GridIndex[str] | None = None


_WORLDS: dict[str, _World] = {}
_CATALOGUE: list[Catalogue] = []  # the loaded catalogue (0 or 1 element)
_CLOCK: SystemClock | _Fixed = SystemClock()
_CANCELS: dict[str, CancelToken] = {}
_TOMBSTONES: dict[str, None] = {}  # insertion-ordered set of ids cancelled before their plan started
_LOCK = threading.Lock()


# ---------------------------------------------------------------------------------------------- envelope


def _error(code: str, message: str = "", **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "code": code,
        "message": message,
        "field": None,
        "reason": None,
        "pointIndex": None,
        "roadKm": None,
        "detail": None,
    }
    out.update(extra)
    return out


def _dump(body: dict[str, Any]) -> str:
    return json.dumps(body, ensure_ascii=False, allow_nan=False)


def _failure(e: BaseException) -> dict[str, Any]:
    tb = traceback.format_exc()
    sys.stderr.write(tb)
    return {"ok": False, "error": _error("INTERNAL", repr(e), detail=tb)}


def _envelope(fn: Callable[[], Any]) -> str:
    t0 = time.perf_counter()

    def ms() -> int:
        return round((time.perf_counter() - t0) * 1000)

    try:
        try:
            body: dict[str, Any] = {"ok": True, "result": fn()}
        except InvalidInput as e:
            body = {"ok": False, "error": _error(e.code, str(e), field=e.field, reason=e.reason)}
        except Unreachable as e:
            body = {"ok": False, "error": _error(e.code, str(e), pointIndex=e.point_index)}
        except TooShort as e:
            body = {"ok": False, "error": _error(e.code, str(e), roadKm=e.road_km)}
        except NotEnoughPois as e:
            body = {
                "ok": False,
                "error": _error(
                    e.code, str(e), field=e.field, suggestions=e.suggestions, requestKey=e.request_key
                ),
            }
        except PlannerError as e:
            body = {"ok": False, "error": _error(e.code, str(e))}
        except EngineFailure as e:
            body = {"ok": False, "error": _error(e.code, str(e), field=e.field)}
        except _BadInput as e:
            body = {"ok": False, "error": _error("INVALID_INPUT", str(e), detail=repr(e.__cause__))}
        body["ms"] = ms()
        return _dump(body)
    except Exception as e:  # never raise across the bridge, serialisation (NaN, non-JSON types) included
        body = _failure(e)
        body["ms"] = ms()
        return _dump(body)


class _BadInput(Exception):
    """Malformed arguments (JSON, types, keys) — reported as `INVALID_INPUT`."""


def _decode(text: Any, what: str) -> Any:
    try:
        return json.loads(text)
    except (TypeError, ValueError) as e:
        raise _BadInput(f"{what}: not JSON") from e


def _parse(what: str, fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except PlannerError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        raise _BadInput(f"{what}: {e!r}") from e


def _world(world_id: Any) -> _World:
    w = _WORLDS.get(str(world_id))
    if w is None:
        raise EngineFailure("NO_WORLD", f"world {world_id!r} is not loaded")
    return w


def _point(lat: Any, lon: Any) -> LatLon | None:
    if lat is None or lon is None:
        return None
    point: LatLon = _parse("lat/lon", lambda: LatLon(_num(lat, "lat"), _num(lon, "lon")))
    return point


def _int(v: Any, what: str) -> int:
    """A real integer (a JSON number without fraction); booleans and strings are rejected."""
    if isinstance(v, bool) or not isinstance(v, int):
        raise _BadInput(f"{what}: not an integer")
    return v


def _bool(v: Any, what: str) -> bool:
    if not isinstance(v, bool):
        raise _BadInput(f"{what}: not a boolean")
    return v


def _str(v: Any, what: str) -> str:
    if not isinstance(v, str):
        raise _BadInput(f"{what}: not a string")
    return v


def _num(v: Any, what: str) -> float:
    if isinstance(v, bool) or not isinstance(v, int | float):
        raise _BadInput(f"{what}: not a number")
    return float(v)


# ---------------------------------------------------------------------------------------------- planners


# ADR-0015 §2 rules and the M9 ready-route template rule for russia_v1
OPEN_DATA_CONFIG: dict[str, Any] = {"sights": {"diversity": 1}, "split": {"honour_template": 1}}


def _planner(fakes: FakePorts | CataloguePorts, clock: Any, config: dict[str, Any] | None = None) -> Planner:
    return Planner(
        routing=fakes.routing,
        places=fakes.places,
        prices=fakes.prices,
        tolls=fakes.tolls,
        regions=fakes.regions,
        geocoding=fakes.geocoding,
        clock=clock,
        config=PlannerConfig.from_dict(config or {}),
        templates=ReasonTemplates.default(),
        parking=getattr(fakes, "parking", None),
    )


def _load_world(text: Any) -> dict[str, Any]:
    data = _decode(text, "world")
    world = _parse("world", lambda: FakeWorld.from_dict(data))
    fakes = build_fakes(world)
    _WORLDS[world.id] = _World(world, fakes, _planner(fakes, _CLOCK))
    return {
        "id": world.id,
        "asOf": world.as_of.isoformat(),
        "towns": len(world.towns),
        "places": len(world.places),
        "readyRoutes": len(world.ready_routes),
    }


def load_world(text: str) -> str:
    """Load a fixture world from its JSON text; one `Planner` per world."""
    return _envelope(lambda: _load_world(text))


def _selfcheck() -> dict[str, Any]:
    PlannerConfig.from_dict({})
    ReasonTemplates.default()
    ru.text("label.map_point")
    zones = set(REQUIRED_ZONES) | {r.tz for w in _WORLDS.values() for r in w.world.regions.values()}
    tz: dict[str, bool] = {}
    for name in sorted(zones):
        try:
            ZoneInfo(name)
            tz[name] = True
        except Exception:
            tz[name] = False
    missing = [k for k, v in tz.items() if not v]
    if missing:
        raise EngineFailure("TZDATA_MISSING", ", ".join(missing))
    return {
        "engineVersion": ENGINE_VERSION,
        "apiVersion": API_VERSION,
        "python": ".".join(str(x) for x in sys.version_info[:3]),
        "tz": tz,
        "resources": True,
        "worlds": sorted(_WORLDS),
        "catalogue": _CATALOGUE[0].info() if _CATALOGUE else None,
    }


def selfcheck() -> str:
    """Resources load and every time zone of the loaded worlds resolves (`TZDATA_MISSING` otherwise)."""
    return _envelope(_selfcheck)


def _set_clock(spec: Any) -> dict[str, Any]:
    global _CLOCK
    s = str(spec)
    if s == "system":
        _CLOCK = SystemClock()
    elif s == "golden":
        _CLOCK = _Fixed(GOLDEN_CLOCK)
    else:
        dt = _parse("clock", lambda: datetime.fromisoformat(s))
        if dt.tzinfo is None:
            raise _BadInput("clock: needs a UTC offset")
        _CLOCK = _Fixed(dt)
    for w in _WORLDS.values():
        w.planner.clock = _CLOCK
    return {"now": _CLOCK.now().isoformat()}


def set_clock(spec: str) -> str:
    """`"system"` (default), `"golden"` (2026-10-23T09:00+03:00) or an ISO datetime with offset."""
    return _envelope(lambda: _set_clock(spec))


# ---------------------------------------------------------------------------------------------- search


def _suggestion(world: FakeWorld, s: GeoSuggestion) -> dict[str, Any]:
    key = "suggest.sub.city" if s.kind == "city" else "suggest.sub.place"
    town = world.towns.get(s.osm_id or "") if s.kind == "city" else None
    return {
        "kind": s.kind,
        "name": s.name_ru,
        "subtitle": ru.text(key, region=s.subtitle_ru),
        "lat": s.point.lat,
        "lon": s.point.lon,
        "id": s.osm_id,
        # OI-39: the forms the app's copy needs («из Ярославля», «в Ярославле»); null for places.
        "nameGenRu": ru.genitive(town) if town else None,
        "namePrepRu": ru.prepositional(town) if town else None,
    }


def suggest(world: str, q: str, lat: float | None = None, lon: float | None = None, limit: int = 6) -> str:
    """Towns and places whose name contains `q` (prefix matches first, then by distance to lat/lon)."""

    def run() -> list[dict[str, Any]]:
        w = _world(world)
        near = _point(lat, lon)
        found = w.fakes.geocoding.suggest(_str(q, "q"), near, _int(limit, "limit"))
        return [_suggestion(w.world, s) for s in found]

    return _envelope(run)


def popular(world: str, limit: int = 6, origin_id: str | None = None) -> str:
    """Towns by population, without the origin (default: the most populous town) — «ЧАСТО ИЩУТ»."""

    def run() -> list[dict[str, Any]]:
        w = _world(world)
        towns = sorted(w.world.towns.values(), key=lambda t: (-t.population, t.id))
        origin = origin_id if origin_id is not None else (towns[0].id if towns else None)
        out = []
        for t in towns:
            if t.id == origin:
                continue
            region = w.world.regions.get(t.region_code)
            s = GeoSuggestion("city", t.name_ru, region.name_ru if region else t.region_code, t.point, t.id)
            out.append(_suggestion(w.world, s))
        return out[: _int(limit, "limit")]

    return _envelope(run)


def reverse(world: str, lat: float, lon: float) -> str:
    """The nearest town within 30 km as `{"name", "subtitle"}`, or null."""

    def run() -> dict[str, Any] | None:
        w = _world(world)
        p = _point(lat, lon)
        if p is None:
            raise _BadInput("lat/lon required")
        label = w.fakes.geocoding.reverse(p)
        if label is None:
            return None
        town = next((t for t in w.world.towns.values() if t.name_ru == label.name_ru), None)
        return {
            "name": label.name_ru,
            "subtitle": ru.text("suggest.sub.city", region=label.subtitle_ru),
            "nameGenRu": ru.genitive(town) if town else label.name_ru,
            "namePrepRu": ru.prepositional(town) if town else label.name_ru,
        }

    return _envelope(run)


def ready_routes(world: str, lat: float, lon: float, radius_km: float = 50, limit: int = 20) -> str:
    """Ready routes whose hub town is within `radius_km`, sorted `(kmSign, sort)` (A§6.12)."""

    def run() -> list[dict[str, Any]]:
        w = _world(world)
        p = _point(lat, lon)
        if p is None:
            raise _BadInput("lat/lon required")
        radius = _num(radius_km, "radius_km")
        out = []
        for r in w.fakes.places.ready_routes_near(p, radius, _int(limit, "limit")):
            hub = w.world.towns[r.hub_town_id]
            first = next((x.town_id for x in r.points if x.role == "via" and x.town_id), None)
            target = w.world.towns[first].point if first in w.world.towns else hub.point
            out.append(
                {
                    "id": r.id,
                    "title": r.title_ru,
                    "subtitle": r.subtitle_ru,
                    "kmTotal": r.km_total,
                    "kmSign": r.km_sign,
                    "ring": r.ring,
                    "roundTrip": r.round_trip,
                    "daysMin": r.days_min,
                    "daysMax": r.days_max,
                    "tags": list(r.tags),
                    "hubTownId": r.hub_town_id,
                    "bearing8": bearing8(hub.point, target),
                    "coverKey": r.cover_key,
                }
            )
        return out

    return _envelope(run)


# ---------------------------------------------------------------------------------------------- planning


class _ListenerSink:
    """Forwards events to the app listener; its exceptions are swallowed, the first one is logged."""

    def __init__(self, listener: Any) -> None:
        self.listener = listener
        self.failed = False

    def emit(self, event: PlanEvent) -> None:
        if self.listener is None:
            return
        try:
            self.listener.onEvent(json.dumps(event_to_json(event), ensure_ascii=False))
        except Exception:
            if not self.failed:
                self.failed = True
                sys.stderr.write(
                    "verst_planner.mobile: listener failed (logged once)\n" + traceback.format_exc()
                )


def with_driven_km(trip: dict[str, Any]) -> dict[str, Any]:
    """API v3 (ADR-0015 §7): every stop gets `kmDriven` (Σ `kmFromPrev` from the trip start, detours included)
    and `kmLeft` (the rest of the trip's driven km), so «пройдено N км» needs no arithmetic in the app.
    Added in the bridge, so the golden snapshots (the codec output) keep their bytes."""
    total = int(trip.get("km") or 0)
    before = 0  # the driven km of the previous days (their `km`, which counts each detour in full)
    for d in trip.get("daysList", []):
        driven = before
        for s in d.get("stops", []):
            driven += int(s.get("kmFromPrev") or 0)
            s["kmDriven"] = min(driven, before + int(d.get("km") or 0))
            s["kmLeft"] = max(0, total - s["kmDriven"])
        stops = d.get("stops", [])
        before += int(d.get("km") or 0)
        if stops and stops[-1].get("kind") in ("overnight", "finish"):
            stops[-1]["kmDriven"] = before  # the day ends where its km end
            stops[-1]["kmLeft"] = max(0, total - before)
    return trip


AMENITY_TAGS = ("wc", "cafe_at_fuel", "playground", "walk", "view", "parking", "ev_charger", "24h")


def with_amenities(trip: dict[str, Any]) -> dict[str, Any]:
    """API v3 (ADR-0015 §5): rest and fuel rows list their amenities in a fixed order, for the row icons."""
    for d in trip.get("daysList", []):
        for s in d.get("stops", []):
            if s.get("kind") in ("rest", "fuel"):
                tags = set(s.get("tags") or [])
                s["amenities"] = [t for t in AMENITY_TAGS if t in tags]
    return trip


WHY_SITELINKS = 15  # «статьи в N разделах Википедии» from this many language editions


def why_ru(w: _World, p: Place) -> str | None:
    """API v3: one line why a catalogue sight is worth the stop — heritage, Wikivoyage, wide fame; None for
    a curated sight (its description says it) or when the open data says nothing."""
    poi = _cat_poi(w, p.id)
    if poi is None or p.source is Source.CURATED:
        return None
    parts = []
    if poi.heritage:
        parts.append(ru.text("poi.why.heritage"))
    if poi.extract_src == "wikivoyage":
        parts.append(ru.text("poi.why.voyage"))
    if poi.sitelinks >= WHY_SITELINKS:
        parts.append(ru.text("poi.why.famous", n=poi.sitelinks))
    return " · ".join(parts) or None


OSM_PLACE_ATTRIBUTION = "poi.osm_place"


def place_source(w: _World, place_id: str) -> dict[str, Any]:
    """M9 (ODbL): `placeSource` = curated | wikidata | osm and, for an OSM-only place (or a bar),
    `placeAttributionRu` (the `poi.osm_place` line) for the card and the stop sheet."""
    p = w.world.places.get(place_id)
    if p is not None and p.source is Source.CURATED:
        return {"placeSource": "curated", "placeAttributionRu": None}
    osm = place_id.startswith("osm_") or (bool(_CATALOGUE) and place_id in _CATALOGUE[0].bar_by_id)
    if osm:
        return {"placeSource": "osm", "placeAttributionRu": ru.text(OSM_PLACE_ATTRIBUTION)}
    return {"placeSource": "wikidata", "placeAttributionRu": None}


def _photo_source(w: _World, place_id: str) -> str | None:
    """Where the stop's photo comes from: p18 (the item's own image) | wikipedia | osm | geosearch (a
    Commons photo taken near the place, labelled «Фото поблизости»); None = no photo."""
    if not _CATALOGUE:
        return None
    cat = _CATALOGUE[0]
    link = cat.links.get(place_id)
    if link is not None:
        return "p18" if link.image else None
    poi = _cat_poi(w, place_id)
    if poi is None or not poi.image:
        return None
    return poi.image_src or "p18"


def _hm(t: Any) -> str:
    return str(t.strftime("%H:%M"))


def parking_sheet(info: ParkingInfo, unit: dict[str, Any]) -> dict[str, Any]:
    """API v3 stop `parking`: the cost unit's numbers plus the sheet texts (ADR-0015 §4).
    zoneRu — the tariff zone or the evidence; whereRu — where the car stands; sundayRu — the Sunday and
    holiday rule (zones only, else null); freeRu — why it is free at this arrival (null when paid)."""
    if info.source in ("zone", "free") and info.city is not None:
        night = (
            ru.text("parking.night_free")
            if not info.night_rub
            else ru.text("parking.night_rub", rub=info.night_rub)
        )
        zone = ru.text(
            "parking.zone",
            city=info.city,
            km=f"{info.band_km or 0:g}".replace(".", ","),
            rub=info.day_rub or 0,
            start=_hm(info.day_from),
            end=_hm(info.day_to),
            night=night,
        )
        where = ru.text("parking.where.zone")
        sunday = ru.text(f"parking.sunday.{info.sunday or 'paid'}")
        if info.holidays_free:
            sunday = ru.text("parking.sunday_holidays", sunday=sunday)
    elif info.source in ("osm", "unknown"):
        zone = ru.text(f"parking.zone_{info.source}")
        where = ru.text("parking.where.osm", m=info.osm_m or 0)
        sunday = None
    else:
        zone = ru.text("parking.zone_none")
        where = ru.text("parking.where.free")
        sunday = None
    free = None
    if info.free_reason is not None:
        free = ru.text(
            f"parking.free.{info.free_reason}",
            start=_hm(info.day_from) if info.day_from else "",
            end=_hm(info.day_to) if info.day_to else "",
        )
    return {**unit, "zoneRu": zone, "whereRu": where, "sundayRu": sunday, "freeRu": free}


def _stop_parking(w: _World, s: dict[str, Any], unit: dict[str, Any] | None) -> dict[str, Any] | None:
    model = getattr(w.fakes, "parking", None)
    if model is None or unit is None or not s.get("arriveAt"):
        return None
    arrive = datetime.fromisoformat(s["arriveAt"])
    info = model.explain(LatLon(s["lat"], s["lon"]), arrive)
    return parking_sheet(info, {k: unit[k] for k in ("rub", "rubPerHour", "hours", "source")})


PARKED_STOPS = ("sight", "food", "rest")


def _decorate_sight(w: _World, s: dict[str, Any], unit: dict[str, Any] | None) -> None:
    if s.get("kind") in PARKED_STOPS:  # M9: every stop where the car is left (rub null = unknown tariff)
        s["parking"] = _stop_parking(w, s, unit)
    p = w.world.places.get(s.get("placeId") or "")
    if s.get("kind") != "sight" or p is None:
        return
    s["poiKind"] = card_kind(w, p)
    s["poiKindRu"] = ru.kind_label(s["poiKind"])
    s["whyRu"] = why_ru(w, p)
    s["photoSource"] = _photo_source(w, p.id)
    s.update(place_source(w, p.id))


def with_stop_details(trip: dict[str, Any], w: _World | None) -> dict[str, Any]:
    """API v3 (ADR-0015 §3-4): sight stops — and the stops of their alternatives — get `poiKind` (the card
    kind; `kind` stays the stop type), `whyRu`, `photoSource` and `parking` (null without parking data)."""
    if w is None:
        return trip
    units = {u["stopId"]: u for u in trip.get("cost", {}).get("units", {}).get("parking", [])}
    for d in trip.get("daysList", []):
        for s in d.get("stops", []):
            _decorate_sight(w, s, units.get(s.get("id")))
            for a in s.get("alternatives", []):
                u = a.get("units", {})
                alt_unit = (
                    None
                    if "parkingSource" not in u
                    else {
                        "rub": u["parkingRub"],
                        "rubPerHour": u["parkingRubPerHour"],
                        "hours": u["parkingHours"],
                        "source": u["parkingSource"],
                    }
                )
                _decorate_sight(w, a.get("stop", {}), alt_unit)
    return trip


def _trip_result(plan: TripPlan, w: _World | None = None) -> dict[str, Any]:
    """The private trip, its share text, the Waybill footnote month/year («октябрь», "2026") and the
    prepositional names of the overnight towns (5.7 «Отметим ночёвку в Ярославле…»)."""
    month, year = ru.month_year_ru(plan.cost.prices_as_of).split(" ")
    prep: dict[str, str] = {}
    gen: dict[str, str] = {}
    world = w.world if w is not None else None
    if world is not None:
        for d in plan.days_list:
            for s in d.stops:
                town = world.towns.get(s.town_id or "")
                if town is not None:
                    prep[town.id] = ru.prepositional(town)
                    gen[town.id] = ru.genitive(town)
    return {
        "trip": with_stop_details(with_amenities(with_driven_km(codec.plan_to_json(plan, public=False))), w),
        "shareText": render_share_text(plan),
        "pricesMonthRu": month,
        "pricesYear": year,
        "townPrepRu": prep,
        "townGenRu": gen,
    }


_TRIP_KM: dict[str, int] = {}  # (world, canonical input) → trip km of an `estimate` (bounded, oldest evicted)
TRIP_KM_CACHE = 64


def _input_key(world_id: str, raw: Any) -> str:
    return world_id + "\n" + json.dumps(raw, sort_keys=True, ensure_ascii=False)


def _run_plan(w: _World, request_id: Any, input_json: Any, sink: Any, hint: bool = False) -> TripPlan:
    """Decode the input and run `Planner.plan` under a cancel token registered for `request_id`. With
    `hint`, the split stage uses the trip km of an identical earlier `estimate` (run quietly if missing)."""
    raw = _decode(input_json, "input")
    if not isinstance(raw, dict):
        raise _BadInput("input: not an object")
    trip_input = _parse("input", lambda: codec.input_from_json(raw))
    token = CancelToken()
    rid = _str(request_id, "request_id")
    with _LOCK:
        if rid in _TOMBSTONES:
            del _TOMBSTONES[rid]
            raise PlanCancelled()
        _CANCELS[rid] = token
    try:
        km: int | None = None
        if hint:
            key = _input_key(w.world.id, raw)
            km = _TRIP_KM.get(key)
            if km is None:
                km = w.planner.plan(trip_input, NULL_SINK, token).km
        plan = w.planner.plan(trip_input, sink, token, split_km_hint=km)
        _remember_km(w.world.id, raw, plan.km)
        return plan
    finally:
        with _LOCK:
            if _CANCELS.get(rid) is token:
                del _CANCELS[rid]


def _remember_km(world_id: str, raw: Any, km: int) -> None:
    key = _input_key(world_id, raw)
    _TRIP_KM.pop(key, None)
    _TRIP_KM[key] = km
    while len(_TRIP_KM) > TRIP_KM_CACHE:
        del _TRIP_KM[next(iter(_TRIP_KM))]


def _no_fit_result(nf: NoFit, w: _World) -> dict[str, Any]:
    """ADR-0011 «не помещается в бюджет»: the minimum (a private trip, never a normal plan) + options."""
    options = []
    for o in nf.options:
        dest = None
        if o.destination is not None:
            p = o.destination
            dest = {"lat": p.point.lat, "lon": p.point.lon, "label": p.label, "townId": p.town_id}
        options.append(
            {
                "kind": o.kind,
                "totalRub": o.total_rub,
                "budgetRub": o.budget_rub,
                "days": o.days,
                "dailyKm": o.daily_km,
                "readyRouteId": o.ready_route_id,
                "destination": dest,
                "titleRu": o.title_ru,
                "fits": o.fits,
            }
        )
    return {
        "outcome": "no_fit",
        "budgetRub": nf.budget_rub,
        "allowedRub": nf.allowed,
        "minimum": {
            "totalRub": nf.minimum.cost.total_rub,
            "levers": [{"code": x.code, "savedRub": x.saved_rub} for x in nf.levers],
            **_trip_result(nf.minimum, w),
        },
        "options": options,
        "textRu": nf.text_ru,
    }


def plan(world: str, request_id: str, input_json: str, listener: Any = None) -> str:
    """Plan a trip; `listener.onEvent(json)` per progress event; cancellable by `cancel(request_id)`."""

    def run() -> dict[str, Any]:
        w = _world(world)
        try:
            trip = _run_plan(w, request_id, input_json, _ListenerSink(listener), hint=True)
        except NoFit as nf:
            return _no_fit_result(nf, w)
        return {"outcome": "plan", **_trip_result(trip, w)}

    return _envelope(run)


def estimate(world: str, request_id: str, input_json: str) -> str:
    """Pre-plan distance and days of a trip input (the same `TripInputDTO` as `plan`):
    `{"km": int, "days": int}`.

    One source of truth for every distance the app shows before Road ahead (Navigator caption, Instruments,
    Drive header): it *is* the engine's plan of that input, run without events, so `km`/`days` equal the later
    `plan(...).trip.km`/`.days` exactly (the engine is deterministic for a given input and clock).
    Cancellable by `cancel(request_id)` like `plan`; errors as `plan`."""

    def run() -> dict[str, Any]:
        w = _world(world)
        try:
            trip = _run_plan(w, request_id, input_json, _ListenerSink(None))
        except NoFit as nf:
            m = nf.minimum
            return {
                "km": m.km,
                "days": m.days,
                "outcome": "no_fit",
                "totalRub": m.cost.total_rub,
                "budgetStatus": None,
            }
        status = None
        if trip.input.budget_rub is not None:
            status = trip.budget_fit.status if trip.budget_fit is not None else "fits"
        return {
            "km": trip.km,
            "days": trip.days,
            "outcome": "plan",
            "totalRub": trip.cost.total_rub,
            "budgetStatus": status,
        }

    return _envelope(run)


def estimate_points(world: str, lat: float, lon: float, points_json: str) -> str:
    """Road km of the engine's base route from (lat, lon) to each `{"lat", "lon"}` of `points_json` — the
    Navigator suggestion rows, before a destination (and so a trip) exists; `null` where unreachable or
    invalid (outside Russia). A too-short distance is still returned (the caption validates the chosen trip
    with `estimate`)."""

    def run() -> list[int | None]:
        w = _world(world)
        origin = _point(lat, lon)
        if origin is None:
            raise _BadInput("lat/lon required")
        pts = _decode(points_json, "points")
        if not isinstance(pts, list):
            raise _BadInput("points: not a list")
        out: list[int | None] = []
        for p in pts:
            dest = _point(p.get("lat"), p.get("lon")) if isinstance(p, dict) else None
            if dest is None:
                raise _BadInput("points: {lat, lon} objects required")
            raw = {
                "origin": {"lat": origin.lat, "lon": origin.lon},
                "destination": {"lat": dest.lat, "lon": dest.lon},
                "crew": {"adults": 1},
                "dailyKm": 300,
            }
            try:
                out.append(w.planner.estimate_km(codec.input_from_json(raw), check_too_short=False))
            except (Unreachable, InvalidInput):
                out.append(None)
        return out

    return _envelope(run)


def cancel(request_id: str) -> str:
    """Cancel a `plan` (the one call allowed from any thread). A running plan fails with `CANCELLED` at its
    next check (`{"cancelled": true}`); for an id with no running plan a tombstone is kept, so that plan
    returns `CANCELLED` when it starts (`{"cancelled": false, "pending": true}`)."""

    def run() -> dict[str, Any]:
        rid = _str(request_id, "request_id")
        with _LOCK:
            token = _CANCELS.get(rid)
            if token is None:
                _TOMBSTONES.pop(rid, None)
                _TOMBSTONES[rid] = None
                while len(_TOMBSTONES) > TOMBSTONES:
                    del _TOMBSTONES[next(iter(_TOMBSTONES))]
                return {"cancelled": False, "pending": True}
        token.cancel()
        return {"cancelled": True}

    return _envelope(run)


def _trip(trip_json: Any) -> TripPlan:
    data = _decode(trip_json, "trip")
    if not isinstance(data, dict):
        raise _BadInput("trip: not an object")
    version = data.get("engineVersion")
    if not isinstance(version, str):
        raise InvalidInput("engineVersion", "missing")
    if version.split(".")[:2] != ENGINE_VERSION.split(".")[:2]:
        raise EngineFailure(
            "TRIP_INCOMPATIBLE", f"trip engine {version!r}, engine {ENGINE_VERSION}", field="engineVersion"
        )
    plan_obj: TripPlan = _parse("trip", lambda: codec.plan_from_json(data))
    return plan_obj


def replace_stop(world: str, trip_json: str, stop_id: str, alt_id: str) -> str:
    """Swap in an alternative (`Planner.replace_stop`); returns the new private trip and share text."""

    def run() -> dict[str, Any]:
        w = _world(world)
        trip = _trip(trip_json)
        return _trip_result(w.planner.replace_stop(trip, _str(stop_id, "stop_id"), _str(alt_id, "alt_id")), w)

    return _envelope(run)


def _crew(raw: Any) -> Any:
    if isinstance(raw, dict):
        for key in ("adults", "children"):
            if key in raw:
                _int(raw[key], f"crew.{key}")
        if "dog" in raw:
            _bool(raw["dog"], "crew.dog")
        for age in raw.get("childAges") or []:
            _int(age, "crew.childAges")
    return _parse("crew", lambda: codec.crew_from_json(raw))


def _cost_patch(patch_json: Any) -> CostPatch:
    d = _decode(patch_json, "patch")
    if not isinstance(d, dict):
        raise _BadInput("patch: not an object")
    unknown = set(d) - {"crew", "budget", "reserveOn", "hotelChoice"}
    if unknown:
        raise InvalidInput("patch", "unknown_key")
    crew = _crew(d["crew"]) if "crew" in d else None
    budget: Any = UNSET
    if "budget" in d:
        budget = None if d["budget"] is None else _int(d["budget"], "budget")
    reserve = None if d.get("reserveOn") is None else _bool(d["reserveOn"], "reserveOn")
    hotel = None
    if d.get("hotelChoice") is not None:
        hc = d["hotelChoice"]
        if not isinstance(hc, dict):
            raise _BadInput("hotelChoice: not an object")
        hotel = (_str(hc.get("stopId"), "hotelChoice.stopId"), _str(hc.get("placeId"), "hotelChoice.placeId"))
    return CostPatch(crew=crew, budget_rub=budget, reserve_on=reserve, hotel_choice=hotel)


def patch_cost(world: str, trip_json: str, patch_json: str) -> str:
    """Crew, budget (null = «не важно»), reserve or hotel choice — cost only (`Planner.recompute_cost`)."""

    def run() -> dict[str, Any]:
        w = _world(world)
        return _trip_result(w.planner.recompute_cost(_trip(trip_json), _cost_patch(patch_json)), w)

    return _envelope(run)


def share_text(trip_json: str) -> str:
    """The share text of a trip (A§8.2)."""
    return _envelope(lambda: render_share_text(_trip(trip_json)))


def _golden_snapshot(case_json: Any) -> str:
    case = _decode(case_json, "case")
    if not isinstance(case, dict):
        raise _BadInput("case: not an object")
    w = _world(case.get("world"))
    now = _parse("clock", lambda: datetime.fromisoformat(case["clock"]))
    fakes = build_fakes(w.world, now)
    planner = _planner(fakes, fakes.clock, case.get("config") or {})
    trip = planner.plan(_parse("input", lambda: codec.input_from_json(case["input"])))
    return json.dumps(codec.plan_to_json(trip, trip_id="trp_golden"), ensure_ascii=False, indent=2) + "\n"


def golden_snapshot(case_json: str) -> str:
    """Exactly `tests/golden/test_golden.snapshot_text` for a golden case (emulator parity, M§5.3)."""
    return _envelope(lambda: _golden_snapshot(case_json))


# ---------------------------------------------------------------------------------------------- API v2


NEAREST_MAX_KM = 2000.0
INSIDE_RUSSIA_KM = 60.0
TAG_KIND = (
    (Tag.KREMLIN, "kremlin"),
    (Tag.MONASTERY, "monastery"),
    (Tag.MUSEUM, "museum"),
    (Tag.VIEW, "viewpoint"),
)


def _load_catalogue() -> dict[str, Any]:
    base = _WORLDS.get("central_russia_v1")
    if base is None:
        raise EngineFailure("NO_WORLD", "central_russia_v1 must be loaded before the catalogue")
    t0 = time.perf_counter()
    # M9: ~100 k long-lived objects; the cyclic GC would rescan them several times while they are created
    # (≈ 30 % of the load). Pause it, then freeze the result so later collections skip it too.
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        try:
            cat = load_packaged()
        except CatalogueError as e:
            raise EngineFailure("NO_CATALOGUE", str(e)) from e
        cw = compose(base.world, cat)
        ports = build_catalogue_ports(cw, _CLOCK.now())
        bars: GridIndex[str] = GridIndex(0.05)
        for b in cat.bars:
            bars.add(b.point, b.id)
    finally:
        if was_enabled:
            gc.enable()
    gc.freeze()
    _WORLDS[CATALOGUE_WORLD] = _World(cw.world, ports, _planner(ports, _CLOCK, OPEN_DATA_CONFIG), cw, bars)
    _CATALOGUE[:] = [cat]
    return {
        **cat.info(),
        "world": CATALOGUE_WORLD,
        "places": len(cw.world.places),
        "ms": round((time.perf_counter() - t0) * 1000),
    }


def load_catalogue() -> str:
    """Compose `russia_v1` from `central_russia_v1` and the packaged catalogue (ADR-0012 §4)."""
    return _envelope(_load_catalogue)


def _town_json(w: _World, t: Town) -> dict[str, Any]:
    region = w.world.regions.get(t.region_code)
    return {
        "id": t.id,
        "name": t.name_ru,
        "nameGenRu": ru.genitive(t),
        "namePrepRu": ru.prepositional(t),
        "regionRu": region.name_ru if region else t.region_code,
        "tz": region.tz if region else DEFAULT_TZ,
        "lat": t.point.lat,
        "lon": t.point.lon,
        "population": t.population,
    }


def _nearest_town(w: _World, p: LatLon, max_km: float) -> tuple[float, Town] | None:
    if isinstance(w.fakes, CataloguePorts):
        return w.fakes.geocoding.nearest_town(p, max_km)
    best = min(
        ((haversine_km(p, t.point), t.id, t) for t in w.world.towns.values()),
        default=None,
        key=lambda x: (x[0], x[1]),
    )
    if best is None or best[0] > max_km:
        return None
    return best[0], best[2]


def _photo_file(w: _World, place_or_town_id: str) -> tuple[str | None, int | None]:
    """The Commons file and credit index of a place or town (catalogue item or linked fixture item)."""
    if not _CATALOGUE:
        return None, None
    cat = _CATALOGUE[0]
    link = cat.links.get(place_or_town_id)
    if link is not None:
        return link.image, link.credit
    poi = cat.poi_by_id.get(place_or_town_id)
    if poi is not None:
        return poi.image, poi.credit
    town = cat.town_by_id.get(place_or_town_id)
    if town is not None:
        return town.image, town.credit
    return None, None


def _poi_kind(w: _World, p: Place) -> str:
    if w.catalogue is not None and p.id in w.catalogue.poi_kind:
        return w.catalogue.poi_kind[p.id]
    for tag, kind in TAG_KIND:
        if tag in p.tags:
            return kind
    return "park" if Tag.WALK in p.tags else "attraction"


def card_kind(w: _World, p: Place) -> str:
    """API v3 `poiKind` of a sight on cards, geo search, trip and walk stops (M9: the same rule as the
    diversity category — name first: «Церковь…» is a temple, «Золотые ворота» a monument)."""
    return category_of(p)


def _sitelinks(place_id: str) -> int:
    if not _CATALOGUE:
        return 0
    poi = _CATALOGUE[0].poi_by_id.get(place_id)
    return poi.sitelinks if poi is not None else 0


def _geo_search(world: Any, q: Any, lat: Any, lon: Any, limit: Any, kinds: Any) -> list[dict[str, Any]]:
    w = _world(world)
    near = _point(lat, lon)
    n = _int(limit, "limit")
    want = {"city", "poi", "place"} if kinds is None else set(_decode(kinds, "kinds"))
    if not want <= {"city", "poi", "place"}:
        raise _BadInput("kinds: unknown kind")
    out = []
    for s in w.fakes.geocoding.suggest(_str(q, "q"), near, max(n * 3, n)):
        row = _suggestion(w.world, s)
        if s.kind == "city":
            t = w.world.towns[s.osm_id or ""]
            row.update(
                {"kind": "city", "population": t.population, "regionRu": s.subtitle_ru, "poiKind": None}
            )
            row["hasPhoto"] = _photo_file(w, t.id)[0] is not None
        else:
            p = w.world.places.get(s.osm_id or "")
            if p is None or p.type is not PlaceType.SIGHT:
                continue
            row.update(
                {
                    "kind": "poi" if p.source is Source.OSM else "place",
                    "population": None,
                    "regionRu": s.subtitle_ru,
                    "poiKind": card_kind(w, p),
                    "hasPhoto": _photo_file(w, p.id)[0] is not None,
                }
            )
        if row["kind"] in want:
            out.append(row)
    return out[:n]


def geo_search(
    world: str,
    q: str,
    lat: float | None = None,
    lon: float | None = None,
    limit: int = 8,
    kinds: str | None = None,
) -> str:
    """Offline typeahead over towns and places (ADR-0012 §5); `kinds` = JSON list of city/poi/place."""
    return _envelope(lambda: _geo_search(world, q, lat, lon, limit, kinds))


def _geo_nearest(world: Any, lat: Any, lon: Any) -> dict[str, Any]:
    w = _world(world)
    p = _point(lat, lon)
    if p is None:
        raise _BadInput("lat/lon required")
    hit = _nearest_town(w, p, NEAREST_MAX_KM)
    if hit is None:
        return {"town": None, "distanceKm": None, "insideRussia": False}
    d, t = hit
    return {"town": _town_json(w, t), "distanceKm": round(d, 1), "insideRussia": d <= INSIDE_RUSSIA_KM}


def geo_nearest(world: str, lat: float, lon: float) -> str:
    """GPS → the nearest town (`insideRussia` = within 60 km of one)."""
    return _envelope(lambda: _geo_nearest(world, lat, lon))


# -------------------------------------------------------------------------------- city walks (ADR-0013)


def _walk_town(w: _World, start: LatLon, town_id: str | None) -> Town:
    if town_id is not None:
        t = w.world.towns.get(town_id)
        if t is None:
            raise NotFound("town", town_id)
        return t
    hit = _nearest_town(w, start, city_presets_mod.NO_CITY_KM)
    if hit is None:
        raise EngineFailure("NO_CITY", "no town within 15 km")
    return hit[1]


def _safe_hours(text: str | None) -> Any:
    if not text:
        return None
    try:
        return parse_hours(text)
    except Exception:  # an OSM value outside the supported subset: the kind's default applies
        return None


def _osm_hours(place_id: str) -> str | None:
    """The OSM `opening_hours` of a catalogue POI (ADR-0015 §3), if the data build found one."""
    if not _CATALOGUE:
        return None
    poi = _CATALOGUE[0].poi_by_id.get(place_id)
    return poi.hours if poi is not None else None


def _candidates(w: _World, inp: WalkInput, radius: float) -> list[Candidate]:
    weights = weights_for(inp)
    crew_tickets = inp.adults, inp.children
    out: list[Candidate] = []
    for p in w.fakes.places.places_near(inp.start, radius, frozenset({PlaceType.SIGHT})):
        if p.id in inp.exclude:
            continue
        kind = _poi_kind(w, p)
        weight = weights.get(kind, 0.0)
        if weight <= 0:
            continue
        hours = _safe_hours(p.opening_hours)
        osm_hours = _osm_hours(p.id) is not None and hours is not None
        adult = p.ticket_adult_rub or 0
        child = p.ticket_child_rub if p.ticket_child_rub is not None else adult
        cost = 0 if Tag.FREE_ENTRY in p.tags else crew_tickets[0] * adult + crew_tickets[1] * child
        out.append(
            Candidate(
                id=p.id,
                name=p.name_ru,
                kind=kind,
                point=p.point,
                popularity=max(0.0, min(1.0, (p.rating_internal - 3.5) / 1.5)),
                heritage=False,
                hours=hours,
                hours_verified=(p.source is Source.CURATED and p.opening_hours is not None) or osm_hours,
                hours_source="curated"
                if p.source is Source.CURATED and p.opening_hours is not None
                else ("osm" if osm_hours else "default"),
                cost_rub=cost,
                dwell_min=dwell_for(kind, _sitelinks(p.id), inp),
                long_visit=inp.preset == "museums" and long_visit(kind, _sitelinks(p.id)),
                has_photo=_photo_file(w, p.id)[0] is not None,
                weight=weight,
            )
        )
    if w.bars is not None and _CATALOGUE:
        cat = _CATALOGUE[0]
        for _d, bid in w.bars.within(inp.start, radius):
            b = cat.bar_by_id[bid]
            weight = weights.get(b.kind, 0.0)
            if bid in inp.exclude or weight <= 0:
                continue
            pop = (
                0.5
                + (0.2 if b.hours else 0.0)
                + (0.2 if b.kind == "ryumochnaya" and inp.preset == "ryumochnye" else 0.0)
            )
            out.append(
                Candidate(
                    id=b.id,
                    name=b.name,
                    kind=b.kind,
                    point=b.point,
                    popularity=pop,
                    heritage=False,
                    hours=bar_hours(b.hours),
                    hours_verified=False,
                    cost_rub=city_presets_mod.DRINK_RUB[b.kind] * inp.adults,
                    dwell_min=dwell_for(b.kind, 0, inp),
                    has_photo=False,
                    weight=weight,
                )
            )
    out.sort(key=lambda c: (-round(c.base_score, 9), c.id))
    return out[: city_presets_mod.POOL_MAX]


DEFAULT_TZ = "Europe/Moscow"


def _now_local(tz: str) -> datetime:
    return _CLOCK.now().astimezone(ZoneInfo(tz)).replace(tzinfo=None)


def _city_route(world: Any, request_id: Any, input_json: Any) -> dict[str, Any]:
    w = _world(world)
    raw = _decode(input_json, "input")
    if not isinstance(raw, dict):
        raise _BadInput("input: not an object")
    rid = _str(request_id, "request_id")
    start_raw = raw.get("start") if isinstance(raw.get("start"), dict) else None
    probe = _point(start_raw.get("lat"), start_raw.get("lon")) if start_raw else None
    if probe is None:
        raise InvalidInput("start", "required")
    town = _walk_town(w, probe, raw.get("townId") if isinstance(raw.get("townId"), str) else None)
    region = w.world.regions.get(town.region_code)
    tz = region.tz if region else DEFAULT_TZ
    now_local = _now_local(tz)
    inp = parse_input(raw, now_local)
    token = CancelToken()
    with _LOCK:
        if rid in _TOMBSTONES:
            del _TOMBSTONES[rid]
            raise PlanCancelled()
        _CANCELS[rid] = token
    try:
        wt = WalkTown(town.id, town.name_ru, ru.prepositional(town), tz)
        key = request_key(str(world), inp)
        try:
            return {
                **_walk_details(w, _solve_walk(w, inp, wt, now_local, f"wlk_{rid}", token)),
                "requestKey": key,
            }
        except NotEnoughPois as e:
            e.suggestions = _walk_suggestions(w, inp, wt, now_local, token)
            e.request_key = key
            raise
    finally:
        with _LOCK:
            if _CANCELS.get(rid) is token:
                del _CANCELS[rid]


def _walk_details(w: _World, result: dict[str, Any]) -> dict[str, Any]:
    """M9: walk stops carry the same `poiKind` / `poiKindRu` and place source as trip stops (`kind` stays
    the walk solver's kind)."""
    for s in result.get("stops", []):
        pid = s.get("poiId") or ""
        p = w.world.places.get(pid)
        if p is not None:
            s["poiKind"] = card_kind(w, p)
            s["poiKindRu"] = ru.kind_label(s["poiKind"])
        s.update(place_source(w, pid))
    return result


def _walk_candidates(w: _World, inp: WalkInput) -> tuple[WalkInput, list[Candidate]]:
    """The candidates; a custom walk whose interests give < 2 places widens to other sights (flagged)."""
    radius = city_presets_mod.radius_km(inp.duration_min, city_presets_mod.PACES[inp.pace][0])
    cands = _candidates(w, inp, radius)
    if inp.preset == "custom" and not inp.widened:
        sights = [c for c in cands if c.kind not in city_presets_mod.DRINK_KINDS]
        if len(sights) < 2:
            inp = dataclasses.replace(inp, widened=True)
            cands = _candidates(w, inp, radius)
    return inp, cands


def _solve_walk(
    w: _World, inp: WalkInput, wt: WalkTown, now_local: datetime, route_id: str, token: CancelToken
) -> dict[str, Any]:
    inp, cands = _walk_candidates(w, inp)
    if inp.start_at is not None:
        start_dt, tomorrow = inp.start_at, inp.start_at.date() > now_local.date()
    else:
        start_dt, tomorrow = planned_start(now_local, inp.preset, inp.interests, inp.duration_min or 120)
    return build_walk(inp, cands, wt, start_dt, ENGINE_VERSION, route_id, token, tomorrow)


MAX_SUGGESTIONS = 3


def _walk_suggestions(
    w: _World, inp: WalkInput, wt: WalkTown, now_local: datetime, token: CancelToken
) -> list[dict[str, Any]]:
    """ADR-0015 §6 / S4 bug c: what would work instead, each one solved and never the current value."""
    trials: list[tuple[dict[str, Any], WalkInput]] = []
    if inp.exclude:
        trials.append(({"clearExclude": True}, dataclasses.replace(inp, exclude=frozenset())))
    if inp.duration_min is not None:
        for d in city_presets_mod.DURATIONS:
            if d > inp.duration_min:
                trials.append(({"durationMin": d}, dataclasses.replace(inp, duration_min=d)))
        trials.append(({"durationMin": None}, dataclasses.replace(inp, duration_min=None)))
    for p in ("dog_walk", "overview", "custom") if inp.dog else ("overview", "custom"):
        if p == inp.preset:
            continue
        table = city_presets_mod.PRESET_TABLE.get(p)
        trials.append(
            (
                {"preset": p},
                dataclasses.replace(
                    inp,
                    preset=p,
                    interests=("history", "architecture", "parks", "views") if p == "custom" else (),
                    duration_min=table.default_duration if table else inp.duration_min,
                    widened=False,
                ),
            )
        )
    out: list[dict[str, Any]] = []
    for label, trial in trials:
        if len(out) >= MAX_SUGGESTIONS:
            break
        try:
            r = _solve_walk(w, trial, wt, now_local, "probe", token)
        except NotEnoughPois:
            continue
        out.append({**label, "stops": len(r["stops"]), "titleRu": _suggestion_title(label)})
    return out


def _suggestion_title(label: dict[str, Any]) -> str:
    """The chip text of a checked NOT_ENOUGH_POIS suggestion."""
    if label.get("clearExclude"):
        return ru.text("walk.suggest.clear_exclude")
    if "durationMin" in label:
        d = label["durationMin"]
        if d is None:
            return ru.text("walk.suggest.unlimited")
        return ru.text("walk.suggest.duration", duration=ru.fmt_duration(d))
    return ru.text(f"walk.suggest.preset.{label['preset']}")


def city_route(world: str, request_id: str, input_json: str) -> str:
    """A walking route inside one city (ADR-0013); cancellable by `cancel(request_id)`."""
    return _envelope(lambda: _city_route(world, request_id, input_json))


def _city_presets(world: Any, lat: Any, lon: Any) -> dict[str, Any]:
    w = _world(world)
    p = _point(lat, lon)
    if p is None:
        raise _BadInput("lat/lon required")
    town = _walk_town(w, p, None)
    region = w.world.regions.get(town.region_code)
    now_local = _now_local(region.tz if region else DEFAULT_TZ)
    out = []
    for key in city_presets_mod.PRESETS:
        preset = city_presets_mod.PRESET_TABLE.get(key)
        duration = preset.default_duration if preset else 240
        pace = preset.default_pace if preset else "normal"
        probe = WalkInput(
            start=p,
            label="",
            town_id=town.id,
            preset=key,
            duration_min=duration,
            interests=("history", "architecture", "museums", "parks", "views") if key == "custom" else (),
            pace=pace,
            budget_rub=None,
            return_to_start=True,
            start_at=None,
            adults=1,
            children=0,
            adult_confirmed=True,
            exclude=frozenset(),
        )
        cands = _candidates(w, probe, city_presets_mod.radius_km(duration, city_presets_mod.PACES[pace][0]))
        if preset is not None:
            count = sum(1 for c in cands if c.kind in preset.gate_kinds)
            available = count >= preset.gate_min
        else:
            count = len(cands)
            available = count >= 2
        start_dt, tomorrow = planned_start(now_local, key, probe.interests, duration)
        out.append(
            {
                "preset": key,
                "available": available,
                "count": count,
                "startAt": start_dt.strftime("%Y-%m-%dT%H:%M"),
                "startsTomorrow": tomorrow,
                "defaultDurationMin": duration,
                "defaultPace": pace,
                "adultOnly": key in city_presets_mod.ADULT_PRESETS,
                "titleRu": ru.text(f"walk.preset.{key}"),
            }
        )
    return {"town": _town_json(w, town), "now": now_local.strftime("%Y-%m-%dT%H:%M"), "presets": out}


def city_presets(world: str, lat: float, lon: float) -> str:
    """Presets the city around (lat, lon) supports (ADR-0013 gates)."""
    return _envelope(lambda: _city_presets(world, lat, lon))


# ----------------------------------------------------------------------------------- POI card (ARCH-307)


def _image(
    w: _World, file: str | None, credit_idx: int | None, area_town: Town | None, source: str | None = None
) -> dict[str, Any] | None:
    """The card photo; API v3 `source` = p18 | wikipedia | osm | geosearch | area (see `_photo_source`)."""
    if not file:
        return None
    credit = _CATALOGUE[0].credit(credit_idx) if _CATALOGUE else None
    credit_json = None
    nearby = source == "geosearch"
    label = ru.text("poi.photo_nearby" if nearby else "poi.photo")
    if credit is not None:
        credit_json = {"author": credit.author, "licence": credit.licence, "licenceUrl": credit.url}
        parts = [x for x in (credit.author, credit.licence) if x]
        if parts:
            key = "poi.photo_nearby_credit" if nearby else "poi.photo_credit"
            label = ru.text(key, credit=" · ".join(parts))
    if area_town is not None:
        label = ru.text("poi.area_photo", town=area_town.name_ru)
        source = "area"
    return {
        **image_urls(file),
        "credit": credit_json,
        "isArea": area_town is not None,
        "labelRu": label,
        "source": source or "p18",
    }


# Outdoor kinds whose photo may stand for the area when the town's own photo does not qualify (5.9 §3).
AREA_FALLBACK_KINDS = ("square", "embankment", "viewpoint", "park")


def _area_photo(w: _World, town: Town) -> tuple[str | None, int | None]:
    """The town's photo, else the best outdoor sight photo in the town; never a collage, map or flag."""
    blocked = _CATALOGUE[0].area_blocked if _CATALOGUE else frozenset()
    file, credit = _photo_file(w, town.id)
    if file and file not in blocked:
        return file, credit
    best = None
    for p in w.world.places.values():
        if (
            p.town_id != town.id
            or p.type is not PlaceType.SIGHT
            or _poi_kind(w, p) not in AREA_FALLBACK_KINDS
        ):
            continue
        f, c = _photo_file(w, p.id)
        key = (AREA_FALLBACK_KINDS.index(_poi_kind(w, p)), -_sitelinks(p.id), p.id)
        if f and f not in blocked and (best is None or key < best[0]):
            best = (key, f, c)
    return (best[1], best[2]) if best else (None, None)


EXTRACT_LICENCE = {
    "wikipedia": "CC BY-SA 4.0",
    "wikivoyage": "CC BY-SA 3.0",
    "osm": "ODbL",
    "wikidata": "CC0",
}


def _cat_poi(w: _World, place_id: str) -> Any:
    if not _CATALOGUE or w.catalogue is None:
        return None
    qid = w.catalogue.qid_of_place.get(place_id, place_id)
    return _CATALOGUE[0].poi_by_id.get(qid)


def _poi_details(world: Any, place_id: Any) -> dict[str, Any]:
    w = _world(world)
    pid = _str(place_id, "place_id")
    p = w.world.places.get(pid)
    if p is not None and p.type is PlaceType.SIGHT:
        file, credit = _photo_file(w, p.id)
        town = w.world.towns.get(p.town_id or "")
        hours = None
        if p.opening_hours:
            verified = p.source is Source.CURATED
            hours = {
                "textRu": p.opening_hours if verified else ru.text("poi.hours_default"),
                "verified": verified,
            }
        ticket = None
        if p.ticket_adult_rub and Tag.FREE_ENTRY not in p.tags:
            ticket = {
                "adultRub": p.ticket_adult_rub,
                "childRub": p.ticket_child_rub,
                "estimate": p.source is not Source.CURATED,
            }
        poi = _cat_poi(w, p.id)
        if poi is not None and poi.hours and hours is not None:
            hours = {"textRu": poi.hours, "verified": True, "source": "osm"}
        attribution = []
        if poi is not None and poi.extract_src:
            attribution.append(ru.text(f"poi.source.{poi.extract_src}"))
        if poi is not None and (poi.hours or poi.fee is not None):
            attribution.append(ru.text("poi.osm"))
        return {
            "id": p.id,
            "kind": "sight",
            "poiKind": card_kind(w, p),
            "poiKindRu": ru.kind_label(card_kind(w, p)),
            "nameRu": p.name_ru,
            "descriptionRu": p.description_ru,
            # API v3 (ADR-0015 §3): the extra sources and the card level the 5.9 card is laid out for
            "extractRu": poi.extract if poi else None,
            "extractSource": None
            if poi is None or not poi.extract_src
            else {
                "key": poi.extract_src,
                "nameRu": ru.text(f"poi.source.{poi.extract_src}"),
                "licence": EXTRACT_LICENCE[poi.extract_src],
            },
            "cardLevel": poi.level if poi else (4 if p.source is Source.CURATED else 2),
            "quality": None if poi is None or poi.quality is None else round(poi.quality * 100),
            "fee": poi.fee if poi else None,
            "website": poi.website if poi else None,
            "townName": town.name_ru if town else None,
            "lat": p.point.lat,
            "lon": p.point.lon,
            "image": _image(w, file, credit, None, _photo_source(w, p.id)),
            "whyRu": why_ru(w, p),
            "hours": hours,
            "ticket": ticket,
            "isFictional": False,
            "attributionRu": attribution,
            "wikidataId": w.catalogue.qid_of_place.get(p.id) if w.catalogue else None,
            **place_source(w, p.id),
        }
    if p is not None and p.type is PlaceType.LODGING:
        town = w.world.towns.get(p.town_id or "")
        file, credit = _area_photo(w, town) if town else (None, None)
        return {
            "id": p.id,
            "kind": "hotel",
            "poiKind": None,
            "nameRu": p.name_ru,
            "descriptionRu": ru.text("poi.fictional_hotel"),
            "townName": town.name_ru if town else None,
            "lat": p.point.lat,
            "lon": p.point.lon,
            "image": _image(w, file, credit, town) if town else None,
            "hours": None,
            "ticket": None,
            "isFictional": True,
            "attributionRu": [],
            "wikidataId": None,
        }
    if _CATALOGUE and pid in _CATALOGUE[0].bar_by_id:
        b = _CATALOGUE[0].bar_by_id[pid]
        town_id = w.catalogue.town_of_qid.get(b.town) if w.catalogue else None
        town = w.world.towns.get(town_id or "")
        return {
            "id": b.id,
            "kind": "bar",
            "poiKind": b.kind,
            "nameRu": b.name,
            "descriptionRu": None,
            "townName": town.name_ru if town else None,
            "lat": b.point.lat,
            "lon": b.point.lon,
            "image": None,
            "hours": {"textRu": b.hours or ru.text("poi.hours_default"), "verified": False},
            "ticket": None,
            "isFictional": False,
            "attributionRu": [ru.text("poi.osm")],
            "wikidataId": None,
            "placeSource": "osm",
            "placeAttributionRu": ru.text(OSM_PLACE_ATTRIBUTION),
        }
    raise NotFound("place", pid)


def poi_details(world: str, place_id: str) -> str:
    """The card of a sight, hotel or bar (photo URLs, credits, hours/ticket notes); others → NOT_FOUND."""
    return _envelope(lambda: _poi_details(world, place_id))


def _handoff(world: Any, route_json: Any, options_json: Any) -> dict[str, Any]:
    _world(world)
    route = _decode(route_json, "route")
    options = _decode(options_json, "options")
    if not isinstance(route, dict) or not isinstance(options, dict):
        raise _BadInput("route/options: not objects")
    try:
        return handoff_mod.handoff(route, options)
    except handoff_mod.HandoffError as e:
        raise InvalidInput(e.field, e.reason) from e
    except (KeyError, TypeError, ValueError) as e:
        raise _BadInput(f"route: {e!r}") from e


def handoff(world: str, route_json: str, options_json: str) -> str:
    """Яндекс Навигатор / Карты / web links of a trip day or a walk (ADR-0014)."""
    return _envelope(lambda: _handoff(world, route_json, options_json))


# ---------------------------------------------------------------------------------------------- selftest

DEFAULT_WORLDS = ("central_russia_v1", "edge_cases_v1")


def _default_world_paths() -> list[Path]:
    root = Path(__file__).resolve().parent.parent / "fixtures" / "worlds"
    return [root / f"{name}.json" for name in DEFAULT_WORLDS]


class _Recorder:
    def __init__(self) -> None:
        self.events: list[str] = []

    def onEvent(self, event_json: str) -> None:
        self.events.append(event_json)


def selftest(world_texts: Sequence[str], out: Any = None) -> int:
    """Run every function against every world; one ``OK <function> <ms>`` line each. 0 = all ok."""
    out = out if out is not None else sys.stdout
    failures = 0

    def check(name: str, envelope: str) -> dict[str, Any]:
        nonlocal failures
        body: dict[str, Any] = json.loads(envelope)
        status = "OK" if body["ok"] else "FAIL"
        failures += 0 if body["ok"] else 1
        out.write(
            f"{status} {name} {body['ms']}" + ("" if body["ok"] else f" {body['error']['code']}") + "\n"
        )
        return body

    check("set_clock", set_clock("golden"))
    for text in world_texts:
        info = check("load_world", load_world(text))
        if not info["ok"]:
            continue
        wid = info["result"]["id"]
        w = _WORLDS[wid]
        towns = sorted(w.world.towns.values(), key=lambda t: (-t.population, t.id))
        origin, dest = towns[0], towns[1]
        check("selfcheck", selfcheck())
        check("suggest", suggest(wid, dest.name_ru[:3], origin.point.lat, origin.point.lon, 6))
        check("popular", popular(wid, 6))
        check("reverse", reverse(wid, origin.point.lat, origin.point.lon))
        check("ready_routes", ready_routes(wid, origin.point.lat, origin.point.lon, 50, 20))
        trip_input = {
            "origin": {"lat": origin.point.lat, "lon": origin.point.lon, "label": origin.name_ru},
            "destination": {"lat": dest.point.lat, "lon": dest.point.lon, "label": dest.name_ru},
            "crew": {"adults": 2, "children": 0, "dog": False},
            "dailyKm": 300,
            "startAt": "2026-10-24T08:00",
        }
        check("estimate", estimate(wid, f"selftest-{wid}-estimate", json.dumps(trip_input)))
        dest_pt = [{"lat": dest.point.lat, "lon": dest.point.lon}]
        check(
            "estimate_points", estimate_points(wid, origin.point.lat, origin.point.lon, json.dumps(dest_pt))
        )
        planned = check("plan", plan(wid, f"selftest-{wid}", json.dumps(trip_input), _Recorder()))
        check("cancel", cancel(f"selftest-{wid}-idle"))  # leaves a tombstone for an id never planned
        if not planned["ok"]:
            continue
        trip = planned["result"]["trip"]
        trip_text = json.dumps(trip, ensure_ascii=False)
        alt = next((a for d in trip["daysList"] for s in d["stops"] for a in s["alternatives"]), None)
        if alt is not None:
            sid = next(s["id"] for d in trip["daysList"] for s in d["stops"] if alt in s["alternatives"])
            check("replace_stop", replace_stop(wid, trip_text, sid, alt["id"]))
        check("patch_cost", patch_cost(wid, trip_text, json.dumps({"reserveOn": False})))
        check("share_text", share_text(trip_text))
        case = {"world": wid, "clock": GOLDEN_CLOCK.isoformat(), "config": {}, "input": trip_input}
        check("golden_snapshot", golden_snapshot(json.dumps(case)))
    check("set_clock", set_clock("system"))
    return 1 if failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    from verst_planner.cli import read_file

    parser = argparse.ArgumentParser(prog="python3 -m verst_planner.mobile")
    sub = parser.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("selftest", help="run the app-facing API against the fixture worlds")
    st.add_argument("--world", action="append", help="world JSON path (repeatable)")
    args = parser.parse_args(argv)
    paths = args.world or [str(p) for p in _default_world_paths()]
    return selftest([read_file(p) for p in paths])


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "API_VERSION",
    "cancel",
    "city_presets",
    "city_route",
    "geo_nearest",
    "geo_search",
    "golden_snapshot",
    "handoff",
    "load_catalogue",
    "load_world",
    "patch_cost",
    "plan",
    "poi_details",
    "popular",
    "ready_routes",
    "replace_stop",
    "reverse",
    "selfcheck",
    "set_clock",
    "share_text",
    "suggest",
]
