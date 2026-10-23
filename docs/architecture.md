# Verst — Architecture

Status: **approved baseline for MVP implementation** · Owner: Architect · Date: 2026-10-23
Source of truth for behaviour: `docs/SPEC.md` (referred to as SPEC §n). Visual source of truth: `docs/design-canvas/*.dc.html` (design v5 «За рулём»).
This document is the source of truth for *structure*: modules, types, algorithms, schemas and interfaces. Where SPEC leaves room, the decision is made here and marked **[D-n]** (decision log in §15). Where this document deviates from or extends SPEC, it is listed in §15.2.

Conventions:
- Code, identifiers, comments, docs: English. All user-visible text: Russian, stored in resources/config, never hard-coded in engine logic (exception: test fixtures).
- "km" in the engine is a `float` kilometre along the base-route polyline (`km_at`). All public numbers are rounded only at the output boundary (§6.10).
- Times inside the engine are timezone-aware `datetime` (UTC-normalised); output is local wall time ISO 8601 without offset + IANA `tz` (SPEC §12).

---

## Table of contents

1. Context and containers
2. Repository layout
3. Backend module structure and dependency rules
4. Planner engine: domain model
5. Planner engine: ports, adapters, config
6. Planner engine: pipeline and algorithms
7. Cost model
8. Explanations and progress events
9. Database schema (PostgreSQL 16 + PostGIS 3.4)
10. HTTP API
11. Android app architecture
12. Infrastructure, environments, CI/CD, release
13. Testing strategy and golden trips
14. Sandbox vs. network
15. Decision log, SPEC deviations, traceability
16. Sprint 1 review amendments (2026-10-23) — overrides the sections that point to it

---

## 1. Context and containers

### 1.1 Context

```
                ┌───────────────────────────── Russia-hosted servers ─────────────────────────────┐
 ┌─────────┐    │  VM-A "app"                                   VM-B "maps"                        │
 │ Android │HTTPS│ ┌───────┐   ┌──────────┐   ┌───────────┐     ┌─────────────┐  ┌──────────┐      │
 │  app    ├────▶│ │ nginx ├──▶│ verst-api├──▶│ PostgreSQL│     │ GraphHopper │  │  Photon  │      │
 │ (Kotlin)│     │ └──┬────┘   │ FastAPI  │   │ + PostGIS │     │  :8989      │  │  :2322   │      │
 └──┬───┬──┘     │    │        │ +planner ├──▶│  :5432    │     └──────▲──────┘  └────▲─────┘      │
    │   │        │    │        └──┬───┬───┘   └─────▲─────┘            │ private net  │            │
    │   │        │    │           │   └───────────────────────────────┴──────────────┘            │
    │   │        │    │           ▼                 │                                              │
    │   │        │    │        ┌──────┐   ┌─────────┴──┐               ┌───────────────┐          │
    │   │        │    └───────▶│Redis │   │  Directus  │◀── curators   │ martin (tiles)│◀─────┐   │
    │   │        │   admin.*   └──────┘   │  admin UI  │   (browser)   │  :3000        │      │   │
    │   │        │                        └────────────┘               └───────────────┘      │   │
    │   │        └────────────────────────────────────────────────────────────────────────────┼───┘
    │   │  tiles.verst.app (vector tiles for the map picker) ─────────────────────────────────┘
    │   └──▶ external apps via Intent: Yandex Navigator / Yandex Maps / 2GIS; browser → Travelpayouts → Yandex Travel / Tripster
    └──────▶ AppMetrica (analytics + crashes, SDK)
```

### 1.2 Containers, responsibilities, interfaces

| Container | Tech | Responsibility | Talks to (protocol, timeout) |
| --- | --- | --- | --- |
| Android app | Kotlin 2.2, Compose, Hilt, Room | 7 screens, local defaults, offline saved trips, local cost recompute, hand-off intents | verst-api (HTTPS JSON + SSE, §10); tiles (HTTPS, MapLibre); AppMetrica SDK; external apps (Android Intents) |
| nginx | nginx 1.27 | TLS termination (Let's Encrypt), routing by host, IP rate limit (`limit_req` 120 r/min/IP), gzip, SSE pass-through (`proxy_buffering off`) | api.verst.app → verst-api:8000; admin.verst.app → directus:8055; tiles.verst.app → martin:3000 (VM-B) |
| verst-api | Python 3.12, FastAPI, uvicorn | REST + SSE (§10), auth, rate limit, persistence, partner links, runs the planner in a worker thread | PostgreSQL (psycopg 3, pool 10), Redis (cache, rate limit), GraphHopper (HTTP 6 s), Photon (HTTP 1.5 s) |
| verst_planner | pure Python package (stdlib only) | Deterministic trip planning pipeline (SPEC §7), cost model (SPEC §8), explanations | Only through ports (§5); no I/O of its own |
| PostgreSQL + PostGIS | postgis/postgis:16-3.4 | Place DB, ready routes, prices, tolls, trips, devices, feedback, app config | — |
| Redis | redis:7.4 | Route cache (24 h), geocode cache (10 min), rate-limit counters, config cache | — |
| Directus | directus/directus:11.x | Curator UI over `core` curated tables (map field for geometry), roles | PostgreSQL (role `directus`) |
| GraphHopper | graphhopper 10.x (self-hosted, Russia extract, `car` profile + custom model) | Car routing with `road_class`, `street_ref`, `toll` path details | — (private network only) |
| Photon | photon 0.6/0.7 (Russia index, `lang=ru`) | Typeahead + reverse geocoding | — (private network only) |
| martin | martin tile server, MBTiles from Planetiler | Vector tiles for the map picker | — |
| Partners | Travelpayouts (Yandex Travel, Tripster) | Affiliate booking | App opens URLs built by `GET /v1/links/*` |
| AppMetrica | Yandex SaaS | Analytics events (SPEC §15), crash reports | — |

Interface contracts between containers:
- **App ↔ API**: §10 (JSON, camelCase, UTF-8, `Authorization: Bearer <deviceToken>`). OpenAPI document generated by FastAPI is the machine contract; `docs/contracts/plan-response.example.json` is the canonical example of the plan payload (generated from golden trip G02 in Sprint 1).
- **API ↔ planner**: Python call `Planner.plan(TripInput, sink, cancel) -> TripPlan` (§5.6). The API owns ids, persistence and HTTP; the planner owns all planning and cost logic.
- **Planner ↔ map services / DB**: ports (§5.1). Adapters live in `verst_api.adapters` (real) and `verst_planner.adapters.fake` (fixtures).
- **API ↔ GraphHopper**: `POST /route` JSON (§5.3.1). **API ↔ Photon**: `GET /api`, `GET /reverse` (§5.3.2).
- **Directus ↔ DB**: Directus reads/writes curated tables only; it never alters `core` DDL (§9.6).

---

## 2. Repository layout

```
verst/
  README.md
  Makefile                      # test-planner, lint-planner, typecheck-planner, golden-update
  .editorconfig  .gitignore
  docs/
    SPEC.md  architecture.md  backlog-sprint1.md
    adr/0001-…md … 0009-…md
    contracts/plan-response.example.json      # generated (DEV-018)
    design-canvas/*.dc.html
  backend/
    planner/                    # pure-Python engine, importable as `verst_planner`
      pyproject.toml            # name=verst-planner, requires-python>=3.12, no dependencies
      verst_planner/
        __init__.py             # ENGINE_VERSION, public API re-exports
        domain/   (enums.py, model.py, errors.py, codec.py)
        geo/      (distance.py, polyline.py, index.py, bearing.py)
        hours.py                # OSM opening_hours subset
        config.py               # PlannerConfig + loader
        resources/planner_config.json  resources/reasons.ru.json
        ports.py
        events.py               # PlanEvent, ProgressSink, CancelToken
        pipeline/ (resolve.py, base_route.py, corridor.py, day_split.py, overnight.py,
                   timeline.py, fuel.py, rest.py, meals.py, sights.py, schedule.py,
                   alternatives.py, assemble.py)
        cost/     (money.py, model.py, formulas.py, recompute.py)
        explain/  (templates.py, reasons.py, share.py, ru.py)
        engine.py               # Planner facade
        cli.py                  # python -m verst_planner.cli …
        adapters/fake/ (world.py, routing.py, geocoding.py, places.py, prices.py, tolls.py,
                        regions.py, clock.py)
      fixtures/worlds/central_russia_v1.json  edge_cases_v1.json
      tools/stdlib_coverage.py      # line coverage without coverage.py (§13.5)
      tests/
        __init__.py  helpers.py
        unit/  (test_*.py)
        golden/ cases/G01_….json … snapshots/G01_….json  test_golden.py
        contract/cost_recompute_cases.json  test_cost_recompute_contract.py
        test_layering.py
    api/                        # FastAPI app, importable as `verst_api` (needs network to install deps)
      pyproject.toml
      verst_api/ (main.py settings.py deps.py auth.py ratelimit.py errors.py sse.py bridge.py logging.py metrics.py
                  routers/ schemas/ services/ adapters/ db/)
      tests/
    migrations/                 # Alembic, SQL-first
      alembic.ini env.py versions/20261101_0001_initial.py sql/0001_initial.sql seed/*.sql
  android/                      # Gradle project (§11)
  infra/
    compose/ (app.compose.yml maps.compose.yml dev.compose.yml .env.example)
    nginx/ (verst.conf)
    maps/ (build_graphhopper.sh build_photon.sh build_tiles.sh graphhopper-config.yml import_regions.sh)
    prometheus/ grafana/ backup/
  admin/
    directus/ (snapshot.yaml roles.md)
  design/                       # Designer deliverables (DES-*): tokens.json, DesignTokens.kt, components.md, screens/, icons/
  .github/workflows/ (backend.yml android.yml release-android.yml)
```

---

## 3. Backend module structure and dependency rules

### 3.1 Layers

```
 verst_api.routers      (HTTP: parse/validate pydantic DTOs, auth, map errors)        ── FastAPI
        │
 verst_api.services     (use cases: TripService, ReadyRouteService, GeocodeService,    ── no FastAPI imports
        │                LinkService, DeviceService, FeedbackService, ConfigService)
        ├──────────────▶ verst_planner.engine.Planner   (pure domain)
        │
 verst_api.adapters     (implement verst_planner.ports: GraphHopperRouting, PhotonGeocoding,
        │                PgPlaceRepository, PgPriceRepository, PgTollRepository, PgRegionLocator,
        │                CachedRouting(Redis), SystemClock)
 verst_api.db           (SQLAlchemy 2 Core tables, sessions)
```

Dependency rules (enforced by tests):
1. `verst_planner` imports **only** the Python standard library and itself. `tests/test_layering.py` parses every module with `ast` and fails on any other top-level import. (DEV-018)
2. Inside `verst_planner`: `domain` imports nothing else from the package; `geo` imports only `domain` (amended §16.1, the `Corridor` working type therefore lives in `pipeline`); `pipeline` may import `domain, geo, hours, config, ports, events, explain`; `cost` imports `domain, config, explain.ru`; `engine` imports all; `adapters.fake` imports `domain, geo, ports` only.
3. `verst_api.routers` → `services` → (`verst_planner`, `adapters`, `db`). Routers never import adapters or db directly; services never import FastAPI. Enforced by `verst_api/tests/test_layering.py` (same AST approach).
4. Pydantic models exist only in `verst_api.schemas`. The planner exchanges stdlib dataclasses; `verst_planner.domain.codec` converts them to/from camelCase JSON dicts; API schemas validate the same shape and a contract test asserts `PlanResponse.model_validate(codec.plan_to_json(plan))` succeeds for every golden snapshot.

### 3.2 Concurrency model

The planner is synchronous and CPU-light (< 300 ms for 1,500 km excluding I/O). Ports are synchronous. The API runs `Planner.plan` in a worker thread (`anyio.to_thread.run_sync`, limiter 8 threads per worker). The `ProgressSink` passed in is a `QueueSink` that pushes events into an `asyncio.Queue` with `loop.call_soon_threadsafe`; the SSE response coroutine drains the queue (§10.4). Client disconnect sets the `CancelToken`; the planner checks it between stages and raises `PlanCancelled`.

---

## 4. Planner engine: domain model

All types are `@dataclass(frozen=True, slots=True)` unless marked *(mutable)*; collections in frozen types are `tuple`/`frozenset`. Module: `verst_planner/domain/model.py`, enums in `domain/enums.py`.

### 4.1 Enums (`StrEnum`, value = wire value)

```python
class PlaceType(StrEnum):  SIGHT="sight"; FOOD="food"; FUEL="fuel"; REST="rest"; LODGING="lodging"
class Tag(StrEnum):        DOGS_ALLOWED="dogs_allowed"; KIDS_MENU="kids_menu"; PLAYGROUND="playground"
                           FAMILY_ROOM="family_room"; PARKING="parking"; PARKING_GUARDED="parking_guarded"
                           EV_CHARGER="ev_charger"; WC="wc"; CAFE_AT_FUEL="cafe_at_fuel"; H24="24h"; VIEW="view"
                           WALK="walk"; MUSEUM="museum"; KREMLIN="kremlin"; MONASTERY="monastery"
                           EVENING="evening"; FREE_ENTRY="free_entry"; CASH_ONLY="cash_only"
class Source(StrEnum):     CURATED="curated"; OSM="osm"; PARTNER="partner"
class PlaceStatus(StrEnum):DRAFT="draft"; LIVE="live"; HIDDEN="hidden"
class Mood(StrEnum):       CALM="calm"; MORE_STOPS="more_stops"; JUST_DRIVE="just_drive"
class FuelType(StrEnum):   AI92="ai92"; AI95="ai95"; DT="dt"          # UI: АИ-92 / АИ-95 / ДТ
class RoadClass(StrEnum):  MOTORWAY="motorway"; TRUNK="trunk"; PRIMARY="primary"; SECONDARY="secondary"; OTHER="other"
class StopKind(StrEnum):   START="start"; SIGHT="sight"; FOOD="food"; FUEL="fuel"; REST="rest"
                           OVERNIGHT="overnight"; VIA="via"; FINISH="finish"
class SignType(StrEnum):   CITY="city"; TOURIST="tourist"; FUEL="fuel"; FOOD="food"; REST="rest"; HOTEL="hotel"
class Meal(StrEnum):       BREAKFAST="breakfast"; LUNCH="lunch"; DINNER="dinner"
class OvernightFallback(StrEnum): NONE="none"; TEMPLATE="template"; WIDENED="widened"; EXTRA_DAY="extra_day"; NO_HOTEL="no_hotel"
class WarningCode(StrEnum):NO_LODGING="NO_LODGING"; FUEL_GAP="FUEL_GAP"; DAY_OVER_BUDGET="DAY_OVER_BUDGET"; STOP_CLOSED="STOP_CLOSED"  # §16.5
                           TOLLS_UNAVOIDABLE="TOLLS_UNAVOIDABLE"; UNVERIFIED_PLACES="UNVERIFIED_PLACES"
class StageKey(StrEnum):   SPLIT="split"; LODGING="lodging"; HOURS="hours"; FUEL="fuel"; COST="cost"
class CostKey(StrEnum):    FUEL="fuel"; TOLLS="tolls"; LODGING="lodging"; FOOD="food"; TICKETS="tickets"; RESERVE="reserve"
```

Stop kind → sign mapping (SPEC §5.5): `start/finish/via → city`, `sight → tourist`, `fuel → fuel`, `food → food`, `rest → rest`, `overnight → hotel` (or `city` when the overnight has no hotel, fallback `no_hotel`).

### 4.2 Value objects

```python
LatLon(lat: float, lon: float)                                   # WGS84, validated −90..90 / −180..180
PartnerIds(yandex_travel_id: str | None = None, tripster_id: str | None = None)
```

### 4.3 Input

```python
PointInput(point: LatLon, label: str | None = None, place_id: str | None = None, town_id: str | None = None)
Crew(adults: int, children: int, dog: bool, child_ages: tuple[int, ...] | None = None)
     # adults 1–7 (driver included), children 0–5; child_ages optional, len == children, each 0–17
Vehicle(consumption_l_per_100km: float = 8.0, fuel_type: FuelType = FuelType.AI95, tank_l: float = 50.0)
     # consumption 4.0–20.0; tank 20–150
TripInput(
    origin: PointInput,
    destination: PointInput | None,            # required unless ready_route_id
    vias: tuple[PointInput, ...] = (),         # ≤ 3, visited in order
    ready_route_id: str | None = None,
    round_trip: bool | None = None,            # None → True for ready routes, else False
    crew: Crew,
    daily_km: int,                             # 150..900, multiple of 50
    budget_rub: int | None = None,             # None = "не важно"; else 1_000..10_000_000
    vehicle: Vehicle = Vehicle(),
    start_at: datetime | None = None,          # naive local wall time in origin tz; None → next Saturday 08:00
    mood: Mood | None = None,                  # None → CALM if children > 0 else MORE_STOPS   [D-1]
    avoid_tolls: bool = False,
    reserve_on: bool = True,
    simplify: bool = False,                    # "Упростить маршрут" (SPEC §5.4): skip stage 9 sights
)
NormalizedInput  # same fields, all defaults resolved, start_at aware (origin tz), round_trip: bool, mood: Mood
```

### 4.4 Place DB entities (read models)

```python
Town(id: str, name_ru: str, name_prep_ru: str | None, point: LatLon, region_code: str,
     population: int, quality: int, evening_walk: bool, lodging_count_cache: int)
Place(id: str, type: PlaceType, name_ru: str, point: LatLon, address: str | None, region_code: str,
      town_id: str | None, opening_hours: str | None, dwell_min: int | None, avg_check_rub: int | None,
      price_night_rub: int | None, ticket_adult_rub: int | None, ticket_child_rub: int | None,
      rating_internal: float, tags: frozenset[Tag], description_ru: str | None,
      partner_ids: PartnerIds, source: Source, verified_at: date | None, status: PlaceStatus,
      breakfast_included: bool = True)
ReadyRoutePoint(seq: int, role: Literal["via", "stop"], town_id: str | None, place_id: str | None)
ReadyRoute(id: str, hub_town_id: str, title_ru: str, subtitle_ru: str, points: tuple[ReadyRoutePoint, ...],
           suggested_nights: tuple[str, ...],   # town ids, ordered by night number
           km_total: int, km_sign: int, ring: Literal["weekend", "long"], round_trip: bool,
           days_min: int, days_max: int, tags: tuple[str, ...], cover_key: str | None, sort: int)
RegionPrice(region_code: str, fuel_type: FuelType, price_rub: Decimal, as_of: date)
TollSegment(id: str, road_ref: str, name_ru: str, tariff_day_rub: Decimal, tariff_night_rub: Decimal,
            vehicle_class: int, night_from: time, night_to: time, as_of: date)
TollHit(segment: TollSegment, km_from: float, km_to: float)
RegionInfo(code: str, name_ru: str, tz: str)
GeoSuggestion(kind: Literal["city", "street", "place"], name_ru: str, subtitle_ru: str, point: LatLon, osm_id: str)
GeoLabel(name_ru: str, subtitle_ru: str, region_code: str | None)
```

### 4.5 Routing

```python
RouteRequest(points: tuple[LatLon, ...], avoid_tolls: bool)
RouteDetail(from_idx: int, to_idx: int, road_class: RoadClass, road_ref: str | None, toll: bool)  # polyline index span
Route(points: tuple[LatLon, ...],          # dense polyline
      cum_km: tuple[float, ...],           # len == len(points), cum_km[0] == 0
      cum_min: tuple[float, ...],          # free-flow minutes from routing service, monotone
      details: tuple[RouteDetail, ...],    # contiguous, cover [0, len-1]
      waypoint_idx: tuple[int, ...],       # polyline index of each requested point
      snapped: tuple[LatLon, ...],         # snapped requested points
      km_total: float, min_total: float)
```

### 4.6 Planning working state *(mutable, internal)*

```python
@dataclass(slots=True)
class Candidate:              # a place projected on the route; one per "pass" (§6.3)
    place: Place; km_at: float; lateral_km: float; detour_km: float; detour_min: int
    road_class: RoadClass; region_code: str

@dataclass(slots=True)
class TownCandidate:
    town: Town; km_at: float; lateral_km: float; detour_min: int
    lodgings: list[Candidate]           # lodgings of this town (town_id) or within 10 km of its centre

@dataclass(slots=True)
class Corridor:
    route: Route; index: "PolylineIndex"
    sights: list[Candidate]; food: list[Candidate]; fuel: list[Candidate]
    rest: list[Candidate]; lodgings: list[Candidate]; towns: list[TownCandidate]   # all sorted by (km_at, id)

@dataclass(slots=True)
class PlannedStop:
    kind: StopKind; km_at: float; name_ru: str; point: LatLon
    place: Place | None = None; town: Town | None = None
    detour_km: float = 0.0; detour_min: int = 0; dwell_min: int = 0
    fixed: bool = False                 # start/finish/via/template stop/overnight: never dropped
    auto: bool = False                  # inserted by stages 6–8 (removed before the re-run)
    score: float = 0.0
    meal: Meal | None = None
    reason_key: str = ""; reason_params: dict[str, str | int | float] = field(default_factory=dict)
    region_code: str = ""

@dataclass(slots=True)
class ScoredTown:
    town: Town; km_at: float; score: float; h_fit: float; q_town: int; e_evening: int; detour_min: int

@dataclass(slots=True)
class OvernightChoice:
    day: int; km_at: float; town: Town | None; point: LatLon; name_ru: str
    hotel: Candidate | None; hotel_options: list[Candidate]          # ≤ 3, all pass crew filters
    considered: list[ScoredTown]; fallback: OvernightFallback; score: float; target_km: float

@dataclass(slots=True)
class DayPlan:
    day: int; km_start: float; km_end: float
    start_at: datetime                   # aware
    stops: list[PlannedStop]             # ordered by km_at, includes start/overnight/finish anchors
    tz: str
```

### 4.7 Output (`TripPlan`, serialised by `codec.plan_to_json` to SPEC §12 shape)

```python
Alternative(id: str, place_id: str, name_ru: str, delta_min: int, delta_rub: int, shift_min: int,
            stop: "ScheduledStop")                         # full replacement payload for offline replace
HotelOption(place_id: str, name_ru: str, tags: tuple[Tag, ...], price_night_rub: int, rooms: int,
            price_crew_rub: int, verified: bool)
ScheduledStop(id: str,                 # "d{day}s{idx:02d}", idx from 1 within day
              seq: int,                # global order from 1
              day: int, kind: StopKind, sign: SignType,
              place_id: str | None, town_id: str | None, name_ru: str, note_ru: str | None, point: LatLon,
              arrive_at: datetime | None,   # naive local; None for START
              depart_at: datetime | None,   # naive local; None for FINISH
              tz: str, km_from_prev: int, km_at: int, dwell_min: int,
              tags: tuple[Tag, ...], cost_rub: int, verified: bool, reason_ru: str,
              replaceable: bool, alternatives: tuple[Alternative, ...],
              hotel_options: tuple[HotelOption, ...],          # only for OVERNIGHT
              selected_hotel_id: str | None)
DayResult(day: int, km: int, drive_min: int, tz: str, start_at: datetime, end_at: datetime,
          stops: tuple[ScheduledStop, ...], over_budget: bool)
CostBreakdownRow(label_ru: str, formula_ru: str, rub: int)
CostLine(key: CostKey, title_ru: str, rub: int, formula_ru: str, as_of: str,   # as_of "YYYY-MM"
         breakdown: tuple[CostBreakdownRow, ...], enabled: bool = True)
CostUnits(...)                         # §7.4 — everything the client needs to recompute offline
CostResult(lines: tuple[CostLine, ...],   # always 6, order fuel,tolls,lodging,food,tickets,reserve
           reserve_on: bool, subtotal_rub: int, total_rub: int, per_person_rub: int,
           budget_rub: int | None, remaining_rub: int | None, over_budget: bool,
           hint_keys: tuple[str, ...], prices_as_of: str, units: CostUnits)
OvernightReason(day: int, town_id: str | None, town: str, text: str, candidates: tuple[str, ...])
PlanWarning(code: WarningCode, day: int | None, message_ru: str, detail: str)
TripPlan(title_ru: str, km: int, days: int, nights: int, round_trip: bool,
         days_list: tuple[DayResult, ...], cost: CostResult,
         overnight_reasons: tuple[OvernightReason, ...], warnings: tuple[PlanWarning, ...],
         input: NormalizedInput, engine_version: str, engine_state: "EngineState")
EngineState(profile_km: tuple[float, ...], profile_min: tuple[float, ...],   # 1-km resampled route profile
            region_km: tuple[tuple[str, float], ...], toll_hits: tuple[TollHit, ...],
            drive_time_factor: float)   # persisted in trip.engine_state; needed by replace/patch, not sent to app
```

### 4.8 Errors (`domain/errors.py`)

```python
class PlannerError(Exception): code: str
class InvalidInput(PlannerError):        code="INVALID_INPUT"   (field: str, reason: str)
class Unreachable(PlannerError):         code="UNREACHABLE"     (point_index: int, snap_km: float | None)
class TooShort(PlannerError):            code="TOO_SHORT"       (road_km: float)
class UpstreamUnavailable(PlannerError): code="UPSTREAM"        (service: str)
class NotFound(PlannerError):            code="NOT_FOUND"       (entity: str, id: str)
class PlanCancelled(PlannerError):       code="CANCELLED"
class OpeningHoursParseError(ValueError)  # internal; place is excluded and logged
```
`NO_LODGING` is **not** an exception; it is a `PlanWarning` and the trip is returned (§10.6, [D-2]).

---

## 5. Planner engine: ports, adapters, config

### 5.1 Ports (`verst_planner/ports.py`, `typing.Protocol`)

```python
class RoutingPort(Protocol):
    def route(self, req: RouteRequest) -> Route: ...
    # raises Unreachable (a point cannot be snapped / no car path), UpstreamUnavailable (timeout, 5xx)

class GeocodingPort(Protocol):
    def suggest(self, q: str, near: LatLon | None, limit: int) -> list[GeoSuggestion]: ...
    def reverse(self, point: LatLon) -> GeoLabel | None: ...

class CorridorQuery(NamedTuple):
    line: tuple[LatLon, ...]     # simplified polyline (Douglas–Peucker 200 m) for the spatial prefilter
    radius_km: float
    types: frozenset[PlaceType]

class PlaceRepository(Protocol):
    def places_in_corridor(self, q: CorridorQuery) -> list[Place]: ...      # status=live only
    def towns_in_corridor(self, line: tuple[LatLon, ...], radius_km: float) -> list[Town]: ...
    def lodgings_of_towns(self, town_ids: Sequence[str]) -> dict[str, list[Place]]: ...
    def get_places(self, ids: Sequence[str]) -> dict[str, Place]: ...
    def get_towns(self, ids: Sequence[str]) -> dict[str, Town]: ...
    def get_ready_route(self, route_id: str) -> ReadyRoute | None: ...
    def ready_routes_near(self, point: LatLon, hub_radius_km: float, limit: int) -> list[ReadyRoute]: ...

class PriceRepository(Protocol):
    def fuel_price(self, region_code: str, fuel_type: FuelType) -> RegionPrice: ...
    # latest as_of for (region, fuel); falls back to region "RU"; raises NotFound if "RU" missing
    def food_default_check(self, town_population: int) -> int: ...          # from config table
    def lodging_default_night(self, town_population: int) -> int: ...
    def defaults_as_of(self) -> date: ...                                  # §16.7: date of the food/lodging defaults

class TollRepository(Protocol):
    def segments_on_route(self, route: Route) -> list[TollHit]: ...        # sorted by km_from

class RegionLocator(Protocol):
    def locate(self, point: LatLon) -> RegionInfo: ...                     # never raises; unknown → RU / Europe/Moscow

class Clock(Protocol):
    def now(self) -> datetime: ...                                         # aware UTC
```

Events (`events.py`):
```python
StageEvent(key: StageKey, text_ru: str, progress: float)                   # 0..1
StopEvent(day: int, stop_id: str, kind: StopKind, sign: SignType, name_ru: str, km_at: int, provisional: bool)
PlanEvent = StageEvent | StopEvent
class ProgressSink(Protocol):
    def emit(self, event: PlanEvent) -> None: ...
NULL_SINK: ProgressSink            # no-op
ListSink                           # collects events (tests)
class CancelToken:                 # wraps threading.Event
    def cancel(self) -> None; def is_cancelled(self) -> bool; def check(self) -> None  # raises PlanCancelled
```

### 5.2 Fake adapters (`verst_planner/adapters/fake/`) — Sprint 1, sandbox-verifiable

A **world** is one JSON fixture file that feeds all fakes (`FakeWorld.load(path)` validates and builds indexes).

```jsonc
{
  "id": "central_russia_v1",
  "asOf": "2026-10-01",
  "regions": [{"code": "RU-YAR", "nameRu": "Ярославская область", "tz": "Europe/Moscow"}],
  "nodes":   [{"id": "YAR", "lat": 57.6261, "lon": 39.8845, "region": "RU-YAR"}],
  "edges":   [{"from": "RST", "to": "YAR", "km": 55, "speedKmh": 80, "roadClass": "trunk", "ref": "М-8", "toll": false}],
  "towns":   [{"id": "t_yaroslavl", "nameRu": "Ярославль", "namePrepRu": "Ярославле", "node": "YAR",
               "population": 570000, "quality": 3, "eveningWalk": true}],
  "places":  [{"id": "pl_yar_hotel_strelka", "type": "lodging", "nameRu": "У Стрелки, в центре",
               "anchor": {"node": "YAR", "dxKm": 1.2, "dyKm": 0.6},          // or "anchor": {"edge": ["RST","YAR"], "km": 40, "lateralKm": 0.1}
               "townId": "t_yaroslavl", "tags": ["dogs_allowed","family_room","parking"],
               "priceNightRub": 6000, "rating": 4.6, "openingHours": null, "dwellMin": null,
               "source": "curated", "verifiedAt": "2026-09-15", "partner": {"yandexTravelId": "yt_123"}}],
  "regionPrices": [{"region": "RU-YAR", "fuelType": "ai95", "priceRub": "61.90", "asOf": "2026-10-01"}],
  "tollSegments": [{"id": "ts_m12_1", "roadRef": "М-12", "nameRu": "М-12 Москва — Владимир", "edge": ["MSK","M12_VLA"],
                    "fromKm": 0, "toKm": 185, "tariffDayRub": "800", "tariffNightRub": "560", "asOf": "2026-10-01"}],
  "readyRoutes": [{ "id": "rr_golden_ring", "...": "see §9 columns, camelCase" }],
  "defaults": {"foodCheckByPopulation": [[1000000, 900], [100000, 700], [0, 550]],
               "lodgingNightByPopulation": [[1000000, 7000], [100000, 5000], [0, 4000]]}
}
```

Loader rules (raise `ValueError` with the JSON path on violation): unique ids; every edge `km ≥ 0.95 × haversine(from,to)`; every place has exactly one of `lat/lon` or `anchor`; tags ⊆ `Tag`; town nodes exist; `ready_route` points resolve; a `RU` price row exists for every fuel type.
- Anchor `{"edge":[a,b],"km":k,"lateralKm":l}`: the point at fraction `k/edge.km` along the straight segment a→b, offset `l` km to the left (positive) or right (negative) of the direction of travel. Anchor `{"node":n,"dxKm":x,"dyKm":y}`: node offset east/north.

| Fake | Behaviour |
| --- | --- |
| `FakeRouting` | Undirected graph; Dijkstra on minutes (`km / speedKmh × 60`); with `avoid_tolls` the cost of toll edges is × 100. Snapping: each request point snaps to the nearest graph node, else to the nearest point on an edge (virtual split); snap distance > 2 km → `Unreachable(point_index)`. Polyline: per edge, straight interpolation every 1 km; `cum_km` scaled so each edge contributes exactly `edge.km`; `cum_min` likewise. `details`: one `RouteDetail` per edge (merged when equal). Injectable failure: `FakeRouting(world, fail_with=UpstreamUnavailable("graphhopper"))`. |
| `FakeGeocoding` | `suggest`: case-insensitive substring match on town and place names, kind `city` for towns, `place` otherwise, sorted by (prefix match first, distance to `near`), `limit`. `reverse`: nearest town within 30 km → `GeoLabel(town.name_ru, region name)`, else `None`. |
| `FakePlaceRepository` | `places_in_corridor`: brute-force haversine point-to-segment distance against `q.line`, ≤ `radius_km`, status live. Others: dictionary lookups; `ready_routes_near`: hub town within `hub_radius_km`. |
| `FakePriceRepository` | Latest `as_of` per (region, fuel), fallback `RU`; defaults from `world.defaults`. |
| `FakeTollRepository` | A toll segment's geometry = the sub-polyline of its edge between `fromKm` and `toKm`; a hit is reported when ≥ 70% of its vertices are within 0.1 km of the route (same rule the PostGIS adapter uses, §5.3.4); `km_from/km_to` = projection of its endpoints on the route. |
| `FakeRegionLocator` | Region of the nearest node. |
| `FixedClock(dt)` | Returns `dt`. Golden tests use `2026-10-23T09:00:00+03:00`. |

### 5.3 Real adapters (`verst_api/adapters/`) — need network (deps + services)

#### 5.3.1 `GraphHopperRouting`
`POST {GH_URL}/route` (timeout 6 s, 1 retry on connect error only):
```json
{"profile": "car", "points": [[lon,lat], ...], "points_encoded": false, "instructions": false,
 "calc_points": true, "details": ["road_class", "street_ref", "toll", "distance", "time"],
 "snap_preventions": ["motorway", "ferry", "tunnel"],
 "ch.disable": true,
 "custom_model": {"priority": [{"if": "toll == ALL", "multiply_by": "0.01"}]}   // only when avoid_tolls
}
```
Mapping: `paths[0].points.coordinates` → `points`; cumulative distance/time from `details.distance`/`details.time` intervals (m → km, ms → min) → `cum_km/cum_min`; `road_class` values `motorway|trunk|primary|secondary|*` → `RoadClass`; `street_ref` → `road_ref` (normalise Latin `M`→ Cyrillic `М`, `R`/`P`→`Р`, `A`→`А`); `toll ∈ {ALL}` → `toll=True`; `snapped_waypoints` → `snapped`, `waypoint_idx` from `paths[0].details`-independent search of the nearest polyline index to each snapped point. HTTP 400 with message `Cannot find point` / `Connection between locations not found` → `Unreachable`; timeout/5xx → `UpstreamUnavailable("graphhopper")`. GraphHopper server config: `profiles: [{name: car, custom_model_files: [car.json]}]`, `graph.encoded_values: road_class, road_environment, toll, max_speed, car_access, car_average_speed, street_ref`, LM preparation for `car` (flexible mode needed for the per-request custom model). Exact keys re-verified against the GraphHopper version pinned when network is enabled.

`CachedRouting(inner, redis)`: key `route:v1:{sha1(json([[round(lat,3), round(lon,3)]...], avoid_tolls))}`, value = zlib-compressed JSON of `Route`, TTL 86 400 s (SPEC §7.7).

#### 5.3.2 `PhotonGeocoding`
`GET {PHOTON_URL}/api?q=…&lat=…&lon=…&limit={limit*2}&lang=ru` (timeout 1.5 s); keep features with `countrycode == "RU"`, de-duplicate by `(name, city, osm_value)`, cut to `limit`. Kind: `osm_key == "place"` and `osm_value ∈ {city, town, village, hamlet, suburb}` → `city` (badge «Г»); `type ∈ {street, house}` or `osm_key == "highway"` → `street` («У»); else `place` («М»). `subtitle_ru` = `"{kind_ru} · {state}"` (e.g. «город · Ярославская область»). `reverse`: `GET /reverse?lat&lon&lang=ru&limit=1`. Cache: Redis `geo:s:{sha1(q.lower(), round(lat,2), round(lon,2))}` TTL 600 s.

#### 5.3.3 `PgPlaceRepository` (SQL, psycopg 3)
```sql
-- places_in_corridor(q)
SELECT … FROM core.place p
WHERE p.status = 'live' AND p.type = ANY(%(types)s)
  AND ST_DWithin(p.geom::geography, ST_GeogFromText(%(line_wkt)s), %(radius_m)s);
-- towns_in_corridor: same against core.town; lodgings_of_towns: WHERE type='lodging' AND town_id = ANY(%(ids)s)
-- ready_routes_near(point, 50 km):
SELECT rr.* FROM core.ready_route rr JOIN core.town t ON t.id = rr.hub_town_id
WHERE rr.status='live' AND ST_DWithin(t.geom::geography, ST_MakePoint(%(lon)s,%(lat)s)::geography, %(r_m)s)
ORDER BY rr.km_sign, rr.sort LIMIT %(limit)s;
```
`line_wkt` is the 200 m-simplified polyline (≤ ~3,000 vertices for 1,500 km) so the query uses the GiST index on `(geom::geography)`.

#### 5.3.4 `PgTollRepository`
```sql
WITH r AS (SELECT ST_GeogFromText(%(line_wkt)s) AS g)
SELECT s.* FROM core.toll_segment s, r
WHERE s.status='live' AND s.vehicle_class = 1 AND ST_DWithin(s.geom::geography, r.g, 50)
  AND ST_Length(ST_Intersection(s.geom::geography, ST_Buffer(r.g, 50))) >= 0.7 * ST_Length(s.geom::geography);
```
`km_from/km_to` are computed in Python by projecting the segment endpoints with `PolylineIndex` (§6.3). The `line_wkt` here is the **unsimplified** route polyline (a 1,500 km route ≈ 30k vertices; acceptable for one query per plan).

#### 5.3.5 `PgPriceRepository`, `PgRegionLocator`, `SystemClock`
- Fuel price: `SELECT DISTINCT ON (region_code, fuel_type) … ORDER BY region_code, fuel_type, as_of DESC`, loaded once per 10 min into memory.
- Region: `SELECT code, name_ru, tz FROM core.region WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(lon,lat),4326))`; per-plan memo keyed by `(round(lat,2), round(lon,2))`.
- `SystemClock.now() = datetime.now(UTC)`.

### 5.4 Configuration (`PlannerConfig`)

`verst_planner/resources/planner_config.json` holds defaults; production overrides come from `core.app_config['planner']` (deep-merged, validated by `PlannerConfig.from_dict`, unknown keys rejected). Every coefficient mentioned in this document is a field here:

| Field | Default | Used in |
| --- | --- | --- |
| `snap_max_km` | 2.0 | §6.2 |
| `too_short_km` | 20.0 | §6.2 |
| `max_days` | 14 | §6.4 |
| `corridor_km` | `{"sight":15,"food":15,"fuel":15,"rest":15,"fuel_motorway":5,"rest_motorway":5,"town":25,"lodging_from_town":10}` | §6.3 |
| `detour` | `{"winding":1.3,"speed_kmh":40,"access_min":2,"motorway_exit_min":5,"on_road_km":0.3}` | §6.3 |
| `drive_time_factor` | 1.10 | §6.6 |
| `day_start_first` | `"08:00"` (used only when `start_at` is None) | §4.3 |
| `day_start_next` | `"09:00"` | §6.6 |
| `day_budget_min` | `{"calm":540,"more_stops":600,"just_drive":600}` | §6.9 |
| `split` | `{"window_lo":0.70,"window_hi":1.05,"hard_cap":1.05,"widened_lo":0.40,"widened_hi":1.30,"template_hi":1.05,"template_lo":0.90}` | §6.4–6.5 |
| `overnight_score` | `{"w_h":3.0,"w_q":2.0,"w_e":1.5,"w_km":2.0,"w_detour":1.0,"h_cap":5,"h_no_parking_weight":0.5,"family_room_min_people":3}` | §6.5 |
| `overnight_eta_allowance_min` | `{"calm":120,"more_stops":150,"just_drive":30}` | §6.5 |
| `fuel` | `{"usable_frac":0.8,"start_frac":1.0,"lookahead_km":40,"lookback_km":100,"coincide_km":2,"evening_next_day_km":60,"evening_window_km":40,"skip_near_finish_frac":0.10,"coffee_after_drive_min":60}` | §6.7 |
| `rest_interval_min` | `{"calm":120,"more_stops":90,"just_drive":180}` | §6.8 |
| `rest` | `{"window_before_min":30,"widen_before_min":60,"widen_after_min":15,"min_remaining_drive_min":30,"break_min_dwell":15,"max_detour_min":10,"min_gap_min":60}` | §6.8, §16.2 |
| `dwell_min` | `{"coffee":15,"fuel":10,"fuel_coffee":15,"rest":20,"lunch":60,"sight_default":60,"via":30}` | §6.6 (SPEC §7.4) |
| `lunch_window` | `["12:00","14:30"]`, `lunch_sweet_spot` `["12:30","13:30"]` | §6.8 |
| `sights` | `{"max_per_day":{"calm":2,"more_stops":4,"just_drive":0},"min_score":2.0}` | §6.9 |
| `alternatives` | `{"window_min":45,"max":3}` | §6.11 |
| `cost` | `{"reserve_frac":0.10,"line_step":10,"total_step":100,"child_food_weight_under7":0.5,"assumed_child_age":8,"breakfast_price_frac":0.6,"dinner_last_day_after":"19:00"}` | §7 |
| `toll_night` | `["00:00","06:00"]` (used when a segment has no own night window) | §7.2 |

---

## 6. Planner engine: pipeline and algorithms

### 6.1 Facade and stage functions

```python
class Planner:
    def __init__(self, *, routing: RoutingPort, places: PlaceRepository, prices: PriceRepository,
                 tolls: TollRepository, regions: RegionLocator, geocoding: GeocodingPort,
                 clock: Clock, config: PlannerConfig, templates: ReasonTemplates) -> None
    def plan(self, raw: TripInput, sink: ProgressSink = NULL_SINK, cancel: CancelToken = NEVER) -> TripPlan
    def replace_stop(self, plan: TripPlan, stop_id: str, alternative_id: str) -> TripPlan
    def recompute_cost(self, plan: TripPlan, patch: CostPatch) -> TripPlan
CostPatch(crew: Crew | None = None, budget_rub: int | None | Unset = UNSET, reserve_on: bool | None = None,
          hotel_choice: tuple[str, str] | None = None)        # (stop_id, place_id)
```

`Planner.plan` is exactly this sequence (each stage a module-level pure function in `pipeline/`, `ctx` = `PlanContext(cfg, templates, ports, clock)`):

| # | SPEC §7.2 | Function (module) | Signature |
| --- | --- | --- | --- |
| 0 | 7.1 | `normalize_input` (resolve) | `(raw: TripInput, ctx) -> NormalizedInput` |
| 1 | 1 Resolve | `resolve_points` (resolve) | `(inp: NormalizedInput, ctx) -> ResolvedPoints` |
| 2 | 2 Base route | `build_base_route` (base_route) | `(pts: ResolvedPoints, inp, ctx) -> Route` |
| 3 | 3 Corridor | `build_corridor` (corridor) | `(route: Route, inp, ctx) -> Corridor` |
| 4 | 4 Day split | `split_days` (day_split) | `(route, corridor, inp, template: ReadyRoute \| None, ctx) -> DaySplit` |
| 5 | 5 Overnight | `choose_overnights` (overnight) | `(split: DaySplit, corridor, inp, ctx) -> OvernightResult` |
| — | — | `build_day_plans` (timeline) | `(route, overnights, fixed: list[PlannedStop], inp, ctx) -> list[DayPlan]` |
| 6 | 6 Fuel | `plan_fuel` (fuel) | `(days, corridor, inp, ctx) -> list[PlanWarning]` *(mutates days)* |
| 7 | 7 Rest | `plan_rests` (rest) | `(days, corridor, inp, ctx) -> None` |
| 8 | 8 Meals | `plan_meals` (meals) | `(days, corridor, inp, ctx) -> None` |
| 9 | 9 Sights | `plan_sights` (sights) | `(days, corridor, inp, ctx, frozen: bool) -> None` |
| 10 | 10 Schedule | `schedule_with_rerun` (schedule) | `(days, corridor, inp, ctx) -> tuple[list[ScheduledDay], list[PlanWarning]]` |
| 11 | 11 Alternatives | `build_alternatives` (alternatives) | `(sched, corridor, inp, ctx) -> None` |
| 12 | 12 Cost | `compute_cost` (cost.model) | `(sched, route, tolls: list[TollHit], inp, ctx) -> CostResult` |
| 13 | 13 Explain | `render_reasons` (explain.reasons) | `(sched, overnights, inp, ctx) -> tuple[...]` |
| — | — | `assemble_plan` (assemble) | `(...) -> TripPlan` |

`cancel.check()` is called before stages 2, 3, 5, 6, 9, 10, 12. Events are emitted per §8.3.

**Amended §16.2:** the stages are *executed* in the order 6 → 8 → 9 → 8b → 7 → 10 (rests last); the table keeps SPEC numbering. Approved signature changes (§16.1): `build_day_plans(route, overnights, fixed, inp, ctx, pts, profile)`, `choose_overnights(split, corridor, inp, ctx, profile=None)`, `build_base_route(...) -> Route` plus `toll_warnings(route, inp, ctx) -> list[PlanWarning]`.

### 6.2 Stages 0–2: normalize, resolve, base route

`normalize_input` validates (raises `InvalidInput(field, reason)`): Russia bbox (`41.0 ≤ lat ≤ 82.0` and (`19.0 ≤ lon ≤ 180.0` or `−180.0 ≤ lon ≤ −168.0`)); `daily_km ∈ {150,200,…,900}`; crew limits; `len(vias) ≤ 3`; `destination` or `ready_route_id` present (both allowed: destination then ignored → `InvalidInput("destination","conflicts_with_ready_route")`); `start_at` within `[now − 1 day, now + 365 days]`. Defaults: `start_at` = next Saturday strictly after today (origin tz) at `day_start_first`; `round_trip`; `mood` [D-1]; tz of origin via `RegionLocator`.

`resolve_points` builds the ordered waypoint list: origin, vias, destination (or the ready route's `via` points resolved to town coordinates; `stop` points become fixed `PlannedStop(kind=SIGHT, fixed=True)` placed later by projection), plus origin again when `round_trip`. **Amended §16.3:** ready-route `via` points are routing waypoints only and produce no stop; only user vias become `VIA` stops. Missing labels are filled with `GeocodingPort.reverse` (fallback «Точка на карте»).

`build_base_route` calls `RoutingPort.route(RouteRequest(points, avoid_tolls))`, then:
- for each `i`: `haversine(points[i], route.snapped[i]) > snap_max_km` → `Unreachable(i)`;
- non-round trips: `route.km_total < too_short_km` → `TooShort`; round trips: `km_total < 2 × too_short_km` → `TooShort`;
- if `avoid_tolls` and any `detail.toll` → warning `TOLLS_UNAVOIDABLE` (tolls are still costed).

### 6.3 Stage 3: corridor, `kmAt` projection, detour

`PolylineIndex(route, cell_deg=0.05)` (module `geo/index.py`):
1. Simplify the polyline with Douglas–Peucker at 30 m (local equirectangular metres per segment); kept vertices keep their original `cum_km`.
2. Register each simplified segment in every grid cell `(floor(lat/0.05), floor(lon/0.05))` its bounding box (expanded by 0.0005°) touches.
3. `project_all(p: LatLon, max_km: float) -> list[Projection]` where `Projection(km_at, lateral_km, seg_idx, road_class)`:

```
cells = all cells within ceil(max_km / 5.5) rings around p's cell (lon ring count scaled by 1/cos(lat))
hits = []
for seg i in unique(segments in cells):
    a, b = seg endpoints; φm = (a.lat + b.lat)/2
    to local km: X(q) = (q.lon − a.lon)·111.320·cos φm,  Y(q) = (q.lat − a.lat)·110.574
    t = clamp( (P·B) / (B·B), 0, 1 )          # P = (X(p),Y(p)), B = (X(b),Y(b)); t = 0 if B·B == 0
    d = |P − t·B|
    if d <= max_km: hits.append((cum_km[i] + t·(cum_km[i+1] − cum_km[i]), d, i))
sort hits by km_at
group into passes: a new pass starts when km_at − previous hit km_at > 2·max_km + 5
return [min(pass, key=(d, km_at)) for pass in passes]   # one projection per pass of the route near p
```
A round trip on the same road therefore yields two candidates for one roadside place (outbound and return); the trip uses each `place_id` at most once.

4. `road_class` of a projection = the `RouteDetail` covering `seg_idx`.

`build_corridor` makes **one** `places_in_corridor` call with `radius_km = max(corridor_km.sight, food, fuel, rest) = 15` and types {sight, food, fuel, rest}, **one** `towns_in_corridor(…, 25)`, and **one** `lodgings_of_towns(town_ids)` + one `places_in_corridor(types={lodging}, radius=25)` for lodgings without a town. For each place: `project_all(place.point, radius_for(type, road_class))`, where fuel and rest keep a projection only if `lateral_km ≤ 5` when the projected segment is `MOTORWAY`, else `≤ 15`. Lodgings belong to a town if `town_id` matches or the town centre is within 10 km. Detour:

```
detour_km  = 2 · lateral_km · winding                                    (winding = 1.3)
detour_min = 0                                        if lateral_km < on_road_km (0.3)
           = round(detour_km / speed_kmh · 60) + access_min (+ motorway_exit_min if road_class == MOTORWAY)
```
Candidates with `opening_hours` that fail to parse are dropped and logged (`hours_parse_error`, place id). Places with `source=osm` are allowed and later flagged `verified=false`.

### 6.4 Stage 4: day split

```
total = route.km_total
N = ceil(total / daily_km)          # ≥ 1
if template is not None and template_fits(template):  return DaySplit(N_t, boundaries=template_nights, fixed=True)
return DaySplit(N, boundaries=None, fixed=False)

template_fits(t):                    # [D-3] SPEC "±10%" bounded by US-06 "never > 5% over"
    kms = day lengths between consecutive template night towns (km_at of town projections, from route)
    return all(night town projected within 25 km)
       and max(kms) <= template_hi(1.05) · daily_km
       and len(kms) <= ceil(total / (template_lo(0.90) · daily_km))
```
**Amended §16.4:** `template_fits` additionally requires every template night town to have ≥ 1 lodging that passes the crew filters (§6.5); otherwise the engine split is used.

Invariant (asserted in tests): for every non-template day, `day_km ≤ 1.05 · daily_km` (SPEC US-06), measured on `km_at` boundaries.

### 6.5 Stage 5: overnight choice (SPEC §7.3)

Crew filters for a lodging `h` (`passes(h, crew)`): `dogs_allowed ∈ h.tags` if `crew.dog`; `family_room ∈ h.tags` if `crew.children > 0` and `adults + children ≥ family_room_min_people (3)`; `h.price_night_rub is not None`. Lodgings with `source=osm` and no `dogs_allowed` tag never pass the dog filter (SPEC §9 "never shown as dog-friendly").

Town score for town `t` with target `T` (km_at):
```
passing = [h for h in t.lodgings if passes(h, crew)]
H = min(h_cap, Σ (1.0 if {parking, parking_guarded} ∩ h.tags else h_no_parking_weight) for h in passing)
Q = t.town.quality
eta = day_start + drive_min(prev_km → t.km_at)·drive_time_factor + overnight_eta_allowance_min[mood]
E = 1 if t.town.evening_walk or any(sight in t with EVENING tag and is_open(sight, eta + 60 min)) else 0
detour = min(h.detour_min for h in passing) if passing else t.detour_min
S = w_h·H + w_q·Q + w_e·E − w_km·|t.km_at − T|/100 − w_detour·detour/15
```
Hotel choice inside the chosen town: `hotel_score(h) = rating_internal + 0.5·[parking_guarded] + 0.3·[distance to town centre ≤ 2 km] − price_night_rub/10000`; `hotel` = max, `hotel_options` = top 3 by the same score (ties → lower price, then id). Only passing lodgings are ever options.

Boundary selection with fallbacks (F1 normal → F2 widened → F3 extra day → F4 no hotel) [D-4]:

```
def choose_overnights(split, corridor, inp, ctx):
    if split.fixed: return [choice_from_template(night) for night in split.boundaries]  # fallback=TEMPLATE
    for n_days in (N, N + 1) if N + 1 <= max_days else (N,):
        result = try_split(n_days, allow_f4 = False)
        if result.ok:
            if n_days == N + 1: result.warnings.add(NO_LODGING, reason="extra_day") for each originally failing day
            return result
    return try_split(N, allow_f4 = True)                       # guaranteed ok

def try_split(n_days, allow_f4):
    prev = 0.0; choices = []
    for d in 1 .. n_days − 1:
        seg = (total − prev) / (n_days − d + 1)                # remaining distance spread evenly
        T   = prev + seg
        cap = total − (n_days − d) · hard_cap · daily_km      # remaining days must stay ≤ 105 %
        L,  U  = max(prev + window_lo·seg,  cap), prev + min(window_hi·seg,  hard_cap·daily_km)
        L2, U2 = max(prev + widened_lo·seg, cap), prev + min(widened_hi·seg, hard_cap·daily_km)
        F1 = [t for t in towns if L <= t.km_at <= U and passing(t)]
        if F1: pick = argmax(S, tie → min |km_at − T|, then town.id); fallback = NONE
        else:
            F2 = [t for t in towns if L2 <= t.km_at <= U2 and passing(t)]
            if F2: pick = argmin(|km_at − T|, tie → max S, then id); fallback = WIDENED; warn NO_LODGING(d, "widened")
            elif not allow_f4: return FAILED
            else:
                F4 = [t for t in towns if L <= t.km_at <= U]
                if F4: pick = argmax(S with H = 0); hotel = None; fallback = NO_HOTEL
                else:  pick = road point at km_at = clamp(T, L, U); name from GeocodingPort.reverse
                       or «Ночёвка у трассы {road_ref}, {km} км»; fallback = NO_HOTEL
                warn NO_LODGING(d, "no_hotel", nearest = nearest passing lodging anywhere in the corridor
                                by |km_at − T|, or None)   # SPEC US-05 "offers the nearest alternative"
        choices.append(OvernightChoice(d, pick, considered = F1 or F2 or F4 scored, …))
        prev = pick.km_at
    return OK(choices)
```
Because `seg ≤ hard_cap·daily_km` whenever `n_days ≥ total/(1.05·daily_km)`, `L ≤ U` always holds (proof in the docstring; asserted). A NO_HOTEL overnight shows sign `city`, no «Выбрать отель», lodging cost from `lodging_default_night(population)` (§7.1). The `nearest` passing lodging (if any) is rendered into the warning text («Ближайшая подходящая: {name}, {town}, {dkm} км от ночёвки») and into the stop's `note_ru`; it is never auto-selected, so a dog trip never gets an overnight hotel without `dogs_allowed` (SPEC §17 checklist). `considered` keeps every scored town in the window (shown as `candidates` in US-08).

### 6.6 Timeline and schedule primitives (`pipeline/timeline.py`)

`Profile(route)` gives `min_at(km)` by linear interpolation of `(cum_km, cum_min)` (bisect). Driving minutes between two km positions: `drive(a, b) = (min_at(b) − min_at(a)) · drive_time_factor`.

`schedule_day(day: DayPlan, profile) -> list[Slot]` with `Slot(arrive, depart)` per stop:
```
t = day.start_at; pos = day.km_start
for s in day.stops (ordered by km_at, START first):
    if s.kind == START: arrive = None; depart = t; continue
    t += drive(pos, s.km_at) + s.detour_min / 2
    arrive = t
    depart = None if s.kind in (OVERNIGHT, FINISH) else t + s.dwell_min
    t = (depart or t) + s.detour_min / 2;  pos = s.km_at
day_end = arrival at the OVERNIGHT/FINISH stop; day_duration = day_end − day.start_at
```
Day `d > 1` starts at `day_start_next` (09:00) local to the overnight town on the calendar day after the previous arrival. Dwell defaults per SPEC §7.4 (`dwell_min` config); sights use `place.dwell_min or sight_default`. `eta_if_inserted(day, candidate)` = arrival time of the candidate when tentatively inserted (used by stages 7–9 and 11). All times are computed in aware UTC and rendered in the stop's region tz.

### 6.7 Stage 6: fuel range walk

```
full   = tank_l / consumption · 100                     # km on a full tank
usable = full · usable_frac (0.8)                       # SPEC: refuel when remaining < 20 % of full
pos = 0.0; remaining = full · start_frac (1.0)
while True:
    trigger = pos + remaining − (1 − usable_frac) · full
    if trigger >= total − skip_near_finish_frac · full: break
    b = first overnight with b.km_at < trigger <= b.km_at + evening_next_day_km (60)
    if b:   window = [max(pos, b.km_at − evening_window_km), b.km_at];  reason = "fuel_evening"
    else:   window = [trigger, trigger + lookahead_km (40)];              reason = "fuel_range"
    cands = [c for c in corridor.fuel if window.lo <= c.km_at <= window.hi and c.km_at > pos and unused(c)]
    if not cands and not b:                              # look back, then use the spare 20 %
        cands = [c in [max(pos, trigger − lookback_km), trigger]]  → prefer the latest (score + 0.01·km_at)
        if not cands: cands = [c in [trigger, pos + remaining − 10]]
    if not cands: warn FUEL_GAP(km=trigger); pos = trigger; remaining = (1 − usable_frac)·full; continue_with_virtual_refuel
    best = argmax(fuel_score, tie → lower km_at, then id)
    insert PlannedStop(FUEL, auto=True, dwell = fuel(10)); pos = best.km_at; remaining = full

fuel_score(c) = 3·coincide(c) + 1·[cafe_at_fuel] + 1·[24h] + 0.5·[wc] − c.detour_min / 5
coincide(c)   = any existing stop (overnight hotel/town, fixed, via, sight, food) with |Δkm_at| ≤ 2
```
(`continue_with_virtual_refuel` sets `remaining = full` at `trigger + lookahead_km` so the walk terminates.) A fuel stop is upgraded to coffee (`dwell = fuel_coffee (15)`, counts as a break) when it has `cafe_at_fuel` and driving since the last break ≥ `coffee_after_drive_min (60)` at its ETA. Each fuel stop records `litres = (km since last fill + detour_km) · consumption / 100` for its informational `cost_rub` (§7.1).

### 6.8 Stages 7–8: rest and meals

Rest (per day, iterative) — **superseded by §16.2**:
```
R = rest_interval_min[mood]
loop:
    slots = schedule_day(day); walk stops in order accumulating driving minutes since the last break
    (a break = any stop with dwell ≥ break_min_dwell (15), or the day start)
    find the first position x (km) where accumulated driving reaches R; if none: break
    if drive(x, day.km_end) < min_remaining_drive_min (30): break
    win = km positions whose cumulative driving since break ∈ [R − 30, R]
    pool = rest ∪ sights with dwell ≤ 30 and open at ETA ∪ fuel with cafe_at_fuel (as coffee, kind FUEL)
    cands = [c in pool, km_at in win, unused]  or else the same with win = [R − 60, R + 15]
    if not cands: mark a virtual break at x (no stop) and continue
    insert argmax(rest_score) as PlannedStop(REST/SIGHT/FUEL, auto=True, dwell = rest(20) / place / coffee(15))

rest_score(c) = 1·[type rest] + 2·[playground ∧ children>0] + 1.5·[walk ∧ dog] + 1·[wc] + 0.5·[view]
              + 0.5·rating_internal·[type sight] − c.detour_min / 5
```
Meals:
- **Lunch**: if the day's schedule covers any part of `lunch_window` (12:00–14:30 local), choose among `corridor.food` in the day's km range the candidates whose `eta_if_inserted` ∈ window; `lunch_score = rating_internal + 2·[kids_menu ∧ children>0] + 1·[parking|parking_guarded] + 0.5·[view] + 0.5·[ETA ∈ 12:30–13:30] − detour_min/5`; insert with `dwell = lunch (60)`, `meal = LUNCH`, `auto=True`. No feasible candidate → no lunch stop; the meal is still costed at the town default (§7.1).
- **Dinner** is not a separate stop [D-5]: it is attached to the overnight (`meal = DINNER` in cost units) at the overnight town's median `avg_check_rub` of live food places in that town, else `food_default_check(population)`.
- **Breakfast** is included when the chosen hotel has `breakfast_included = true`; otherwise one breakfast per person the next morning at `breakfast_price_frac (0.6) × default check`.

### 6.9 Stage 9: sights

```
if inp.simplify or mood == JUST_DRIVE: return          # only the destination/fixed stops remain
budget = day_budget_min[mood]; max_n = sights.max_per_day[mood]
for day in days:
    n = count(fixed sights in day)
    pool = sorted([c in corridor.sights, day.km_start < c.km_at < day.km_end, unused,
                   sight_score(c) >= min_score], key = (−score, km_at, id))
    for c in pool:
        if n >= max_n: break
        insert c tentatively (dwell = place.dwell_min or 60); slots = schedule_day(day)
        ok = day_duration ≤ budget
             and is_open_interval(c, arrive, depart)          # hours must cover the whole visit
             and all already placed sights still open, lunch (if any) still in window
        if ok: keep (n += 1) else remove
sight_score(c) = rating_internal + 0.5·[{kremlin, monastery, museum, view} ∩ tags ≠ ∅] + 0.5·[curated]
               + 0.5·[walk ∧ dog] + 0.5·[playground ∧ children>0] − c.detour_min / 15
```
`frozen=True` (re-run) means: keep the current sights, add none.

Opening hours (`hours.py`): supported OSM subset — `24/7`; rules separated by `;`; each rule = optional weekday selector (`Mo`…`Su`, ranges `Tu-Su`, lists `Sa,Su`) followed by comma-separated time ranges `HH:MM-HH:MM` (end may be `24:00` or wrap past midnight) or `off`/`closed`; later rules override earlier ones for the days they name; rules starting with `PH` or `SH` are ignored. Anything else → `OpeningHoursParseError`. `opening_hours = None` means always open (outdoor sights, walks). API: `parse(s) -> OpeningHours`, `OpeningHours.is_open(local_dt) -> bool`, `OpeningHours.covers(start_local, end_local) -> bool`.

### 6.10 Stage 10: schedule with the single re-run rule

**Amended by §16.5** (over-budget rule, final repair, `STOP_CLOSED`).

```
def schedule_with_rerun(days, corridor, inp, ctx):
    sched = [schedule_day(d) for d in days]
    bad = {d for d in days if over_budget(d) or hours_broken(d) or lunch_out_of_window(d)}
    if bad:
        for d in bad:
            while (over_budget(d) or hours_broken(d)) and droppable_sights(d):
                drop the non-fixed sight with the lowest score (tie → later km_at); re-schedule d
        for d in days: remove stops with auto=True               # fuel, rest, lunch
        plan_fuel(days); plan_rests(days); plan_meals(days); plan_sights(days, frozen=True)   # steps 6–9 once
        sched = [schedule_day(d) for d in days]
        for d still over budget: warn DAY_OVER_BUDGET(d); DayResult.over_budget = True
    return sched, warnings
```
Output rounding: `km_at`, `km_from_prev` = round-half-up of `km_at − prev.km_at + (prev.detour_km + s.detour_km)/2`; day `km` = round(`km_end − km_start + Σ detour_km of its stops`); trip `km` = Σ day km; `drive_min` = Σ driving minutes (rounded); times rounded to the minute (half-up) at render.

### 6.11 Stage 11: alternatives

**Superseded by §16.6** (no neighbour/type restriction, per-alternative day patch, shortfall note, `delta_rub` definition).

```
for stop in all days where stop.kind ∈ {SIGHT, FOOD, FUEL, REST} and not stop.fixed:
    pool = candidates of the same stage pool (rest pool for REST, §6.8), not used anywhere in the trip,
           sorted by the stage score desc
    alts = []
    for c in pool:
        day' = day with stop replaced by c (kind kept; dwell from c); slots' = schedule_day(day')
        if |arrive'(c) − arrive(stop)| > window_min (45): continue
        if c is SIGHT and not covers(c, arrive', depart'): continue
        if any later stop in day' breaks hours / lunch window, or day_duration' > budget: continue
        alts.append(Alternative(
            id = f"alt_{stop.id}_{c.place.id}",
            delta_min = minutes(day_end' − day_end), shift_min = minutes(rejoin' − rejoin),
            delta_rub = stop_cost(c) − stop_cost(stop), stop = rendered ScheduledStop for c))
        if len(alts) == max (3): break
    stop.alternatives = alts; stop.replaceable = True       # START/FINISH/VIA/OVERNIGHT/fixed → False
```
`rejoin` = time the car is back on the route after the stop (`depart + detour/2`). Later stops of the day shift by `shift_min` (the app applies this offline; SPEC §5.5).

`Planner.replace_stop(plan, stop_id, alternative_id)`: substitutes the alternative, re-schedules **only that day** with `EngineState.profile`, recomputes alternatives for that day, recomputes cost (§7), returns a new `TripPlan`. Unknown ids → `NotFound`.

### 6.12 Ready routes (SPEC §7.6)

`ready_routes_near(start, hub_radius_km=50, limit)` sorted by `(km_sign, sort)`. The API adds `bearing8 ∈ {N, NE, E, SE, S, SW, W, NW}` = initial bearing hub → first `via` point (`geo/bearing.py`, sectors of 45° centred on N), and `ring`. Planning a ready route: `resolve_points` uses its `via` points, fixed `stop` points, `round_trip` from the template, and `split_days` checks `template_fits`.

---

## 7. Cost model (SPEC §8) — `verst_planner/cost/`

### 7.1 Inputs and unit prices

All money arithmetic uses `decimal.Decimal` with `ROUND_HALF_UP`; integers only at the output boundary. `money.round_to(x: Decimal, step: int) -> int` = `int((x / step).quantize(Decimal(1), ROUND_HALF_UP)) * step`.

| Line | Computation (exact, before rounding) | Formula string (ru) | Breakdown rows |
| --- | --- | --- | --- |
| `fuel` | `Σ_r km_r × consumption / 100 × price(r, fuel_type)`; `km_r` = trip km (incl. detours) attributed to region `r` | one region: `«745 км × 8 л/100 × 62,00 ₽»`; several: `«745 км × 8 л/100 × ≈ 61,40 ₽ (средняя по 3 регионам)»` (prices always with kopecks; the km shown is `TripPlan.km`, §16.7), where the shown price = `Σ cost_r / Σ litres_r` rounded to 0.10 ₽ | one per region: `«Ярославская область: 310 км × 8 л/100 × 61,90 ₽ = 1 540 ₽»` |
| `tolls` | `Σ_hits tariff(segment, entry_local_time)`; night tariff when the entry time is in the segment's night window (else `toll_night` config) | `«М-12: 800 ₽ + М-11: 1 200 ₽»`; none: `«платных дорог нет»` | one per hit, with «днём»/«ночью» |
| `lodging` | `Σ_nights rooms × price_night_rub(selected hotel)`; `rooms = ceil(adults / 2)`, children share; NO_HOTEL night → `lodging_default_night(population)` | equal prices & rooms=1: `«Ярославль + Суздаль, 2 × 6 000»`; else `«Ярославль 6 000 + Суздаль 2 номера × 4 500»`; default price suffix `«(средняя цена)»` | one per night |
| `food` | `people × Σ_meals check(meal)`; `people = adults + Σ child_weight` (child_weight 0.5 if age < 7 else 1; unknown age ⇒ `assumed_child_age` = 8 ⇒ 1) | uniform check: `«3 чел. × 7 приёмов × 600»`; else `«3 чел. × 7 приёмов × ≈ 640 (в среднем)»`; avg rounded to 10 | one per day: `«День 1: обед 650 + ужин 700»` |
| `tickets` | `Σ_sights adults × ticket_adult + children × (ticket_child ?? ticket_adult)`; `free_entry` or null prices ⇒ 0 | `«3 места × (2 взр. + 1 реб.)»`; none paid: `«вход свободный»` | one per paid sight: `«Ростовский кремль: 2 × 400 + 1 × 200»` |
| `reserve` | `reserve_frac × Σ rounded(lines 1–5)` | `«10% на пробки и «давай заедем»»` | — |

Meal counting [D-6]: for each day `d`: **lunch** = 1 if the day's driving schedule overlaps the lunch window (12:00–14:30); priced at the lunch stop's `avg_check_rub`, else town/region default for the nearest town at the lunch ETA. **Dinner** = 1 for every night (priced at the overnight town, §6.8) + 1 on the last day if the finish arrival is after `dinner_last_day_after` (19:00) and the finish is not the origin. **Breakfast** = 0 on day 1 (at home, SPEC §8) and after nights whose hotel has `breakfast_included = true`; otherwise 1 at `breakfast_price_frac × check(town)`.

Fuel region attribution: the planner samples the route every 10 km (`RegionLocator.locate`, memoised), assigns each 10 km bucket to the sample at its midpoint, and adds each stop's `detour_km` to the stop's region. Result is stored in `EngineState.region_km`.

Per-stop `cost_rub` (shown on Road ahead rows): sight = its ticket total; food = `people × check`; overnight = `rooms × price_night`; fuel = informational `litres × price(region)` (not summed — the fuel line is distance-based); rest/start/finish/via = 0. All rounded to 10 ₽. A food stop without `avg_check_rub` uses the same default as the food line (nearest town's population), §16.7.

### 7.2 Totals and rounding (SPEC §8 Rules)

```
line_i      = round_to(exact_i, 10)                         for fuel, tolls, lodging, food, tickets
subtotal    = Σ line_i
reserve     = round_to(reserve_frac × subtotal, 10)         (line always present; enabled = reserve_on)
total       = round_to(subtotal + (reserve if reserve_on else 0), 100)
per_person  = round_to(total / (adults + children), 100)    (children counted as 1 here)
remaining   = budget − total  (None if budget is None);  over_budget = remaining < 0
hint_keys   = over_budget ? ordered subset of ["cheaper_overnight" (if any night has a cheaper passing option),
                                              "fewer_sights" (if tickets > 0 or ≥ 1 sight), "just_drive" (if mood ≠ just_drive)] : []
```
Check against the Waybill canvas: lines 3 720 + 12 000 + 12 600 + 3 000 = 31 320; reserve 3 130; total `round_to(34 450, 100)` = **34 500** ✓.

Number formatting (`explain/ru.py`): thousands separator U+202F (narrow no-break space), decimal comma, consumption without trailing zero (`8`, `7,5`), money with `₽` separated by U+00A0. The "≈" prefix is added by the client, not inside the number.

### 7.3 Local recompute contract (SPEC §8 "recomputes only the affected lines on the device")

`cost/recompute.py: recompute(units: CostUnits, crew: Crew, reserve_on: bool, budget_rub: int | None, overrides: CostOverrides) -> CostResult` is the single reference algorithm; the Android `CostCalculator` (:core-model) is a line-by-line port. Shared contract: `backend/planner/tests/contract/cost_recompute_cases.json` (≥ 25 cases: input units + crew + overrides → expected lines, total, per person, remaining). Both the Python and the Kotlin test suites run every case.

### 7.4 `CostUnits` (serialised into the trip as `cost.units`)

```python
FuelRegionUnit(region_code: str, region_name_ru: str, km: float, price_rub: Decimal)
FuelUnits(consumption_l_per_100km: float, fuel_type: FuelType, regions: tuple[FuelRegionUnit, ...], as_of: str)
TollUnit(segment_id: str, road_ref: str, rub: int, night: bool, as_of: str)
HotelPrice(place_id: str, price_night_rub: int)
NightUnit(stop_id: str, day: int, town_name_ru: str, selected_place_id: str | None, price_night_rub: int,
          options: tuple[HotelPrice, ...], default_price: bool, breakfast_included: bool, breakfast_check_rub: int)
MealUnit(day: int, meal: Meal, stop_id: str | None, check_rub: int)
TicketUnit(stop_id: str, place_id: str, name_ru: str, adult_rub: int, child_rub: int)
CostUnits(fuel: FuelUnits, tolls: tuple[TollUnit, ...], nights: tuple[NightUnit, ...],
          meals: tuple[MealUnit, ...], tickets: tuple[TicketUnit, ...],
          reserve_frac: Decimal, line_step: int, total_step: int, child_ages: tuple[int, ...] | None,
          assumed_child_age: int, child_food_weight_under7: Decimal)
CostOverrides(hotel_by_stop: Mapping[str, str] = {},                  # stop_id → place_id among options
              replaced: Mapping[str, AltUnits] = {})                  # stop_id → units of chosen alternative
AltUnits(delta_km: float, region_code: str, check_rub: int | None, adult_rub: int | None, child_rub: int | None,
         name_ru: str, place_id: str)
```
Each `Alternative` carries its `AltUnits` (`units` field) so a replace can be costed offline. Breakfast for a night recomputes if the selected hotel changes (`breakfast_included` is per option; `HotelPrice` therefore also carries `breakfast_included: bool`).

Freshness: `CostLine.as_of` = `YYYY-MM` of the oldest price used for that line (fuel: oldest `RegionPrice.as_of`; tolls: oldest segment; lodging/food/tickets: oldest `verified_at` among used places, or the world/DB `defaults_as_of`). `CostResult.prices_as_of` = the oldest of fuel and lodging (shown «цены на октябрь 2026»).

---

## 8. Explanations, share text and progress events

### 8.1 Reason templates (SPEC §7.5)

Templates live in `verst_planner/resources/reasons.ru.json` (defaults, also the seed of `core.app_config` key `reasons_ru`); the API passes the DB version to `ReasonTemplates.from_dict`. Format: `{key: "text with {placeholders}"}`; rendering with `str.format_map` on a `SafeDict` that raises on missing keys (tested: every template renders with its documented params). Keys (all required):

| Key | Default text | Params |
| --- | --- | --- |
| `overnight.shift.hotels` | `{shift}: здесь больше отелей{crew_suffix}.` | shift, crew_suffix |
| `overnight.shift.quality` | `{shift}: город интереснее для вечера и утра.` | shift |
| `overnight.shift.evening` | `{shift}: вечером можно прогуляться по центру.` | shift |
| `overnight.on_target` | `Как раз на вашей дневной норме.` | — |
| `overnight.cap_ok` | ` Ваши {daily_km} км в день не превышены.` (appended) | daily_km |
| `overnight.shift.later` / `.earlier` | `Не в {other_prep}, а на {dkm} км дальше` / `… раньше` | other_prep, dkm |
| `overnight.shift.limit` | `На {dkm} км раньше вашего предела` | dkm |
| `overnight.widened` | `Ночёвку с вашими условиями нашли только на {dkm} км {dir} цели дня.` | dkm, dir («раньше»/«дальше») |
| `overnight.no_hotel` | `Не нашли отель с вашими условиями — заложили среднюю цену, уточните при бронировании.` | — |
| `overnight.template` | `Ночёвка из готового маршрута «{route}».` | route |
| `crew_suffix.dog` / `.family` / `.none` | `, куда пускают с собакой` / ` с семейными номерами` / `` | — |
| `fuel.evening` | `Заправиться вечером, чтобы утром сразу ехать.` | — |
| `fuel.range` | `Через {km} км в баке останется меньше 20% — заправимся здесь.` | km |
| `fuel.coincide` | `Заправка рядом с остановкой — без лишнего съезда.` | — |
| `fuel.last` | `Последняя заправка до дома.` | — |
| `rest.generic` | `Разминка {min} минут после {drive} за рулём.` | min, drive |
| `rest.who` | `Разминка {min} минут: {who}.` | min, who («ребёнку побегать, собаке погулять») |
| `lunch.kids` / `lunch.parking` / `lunch.default` | `Обед, есть детское меню.` / `Обед, парковка у входа.` / `Обед в {town_prep}.` | town_prep |
| `sight.default` | `{dwell} на осмотр.` | dwell («полтора часа») |
| `sight.dog_waits` | `{dwell} на осмотр. Собака ждёт с одним из взрослых.` | dwell |
| `sight.osm` | `По открытым данным.` | — |
| `via.user` (§16.3) | `Заезд по вашей просьбе.` | — |
| `alternatives.none` / `alternatives.one` (§16.6) | `Других вариантов в это время поблизости нет.` / `Нашли только один вариант в это время.` | — |
| `start.default` / `finish.home` / `finish.default` | `Выезд в {time}.` / `Дома к {part_of_day}.` / `Финиш.` | time, part_of_day |
| `stage.route` / `stage.split` / `stage.split_ring` | `Прокладываем дорогу` / `Делим путь на {n} {days_word} по ≈ {km} км` / `Делим кольцо на {n} {days_word} по ≈ {km} км` | n, days_word, km |
| `stage.lodging.dog` / `.family` / `.default` / `.none` | `Ищем отели, куда пустят с собакой` / `Ищем отели с семейными номерами` / `Ищем, где удобно переночевать` / `Ищем остановки по пути` | — |
| `stage.hours` | `Сверяем часы работы` | — |
| `stage.fuel` | `Считаем бензин: {consumption} л на 100 км` | consumption |
| `stage.cost` | `Считаем, сколько стоит поездка` | — |
| `hint.cheaper_overnight` / `hint.fewer_sights` / `hint.just_drive` | `Выберите ночёвку дешевле` / `Уберите пару платных мест` / `Попробуйте режим «Просто доехать»` | — |
| `warning.NO_LODGING` / `FUEL_GAP` / `DAY_OVER_BUDGET` / `TOLLS_UNAVOIDABLE` / `UNVERIFIED_PLACES` | SPEC §12 text / `На участке {km} км мало заправок — заправьтесь заранее` / `День {day} получился длинным — можно убрать остановку` / `Без платных дорог не проехать — платный участок учтён в расчёте` / `Часть мест по открытым данным — не проверены`; `warning.STOP_CLOSED` (§16.5): `«{name}» в этот день закрыт — убрали из маршрута` | km, day, name |

Overnight reason selection: `other` = the considered town closest to the target (if it is not the pick); `dkm = round(|pick.km_at − other.km_at|)`; for `.limit` (no other town considered, pick before the cap) `dkm = round(day_start_km + daily_km − pick.km_at)`, i.e. distance to the user's limit, not to the even-split target (§16.8). Dominant factor = argmax over `(w_h·ΔH, w_q·ΔQ, w_e·ΔE)` between pick and other → `.hotels` / `.quality` / `.evening`; if `dkm < 10` → `overnight.on_target`. Append `overnight.cap_ok` when the day km ≤ `daily_km`. Russian helpers in `explain/ru.py`: `plural(n, one, few, many)`, `prepositional(town)` (uses `Town.name_prep_ru`, falls back to the nominative), `duration_phrase(min)` (30 → «полчаса», 60 → «час», 90 → «полтора часа», 120 → «два часа», else «{h} ч {m} мин»), `part_of_day(time)` (< 12 «обеду» … ≥ 17 «вечеру»).

### 8.2 Share text (`explain/share.py`)

`share_text(plan) -> str`: line 1 `«{title} · {km} км · {days} {дня}»`, then per day `«День N · {km} км»` and one line per stop `«{HH:MM} {name}»`, then `«Итого ≈ {total} ₽ на {people} чел.»`, then (if a slug exists) the link — appended by the caller. A contract fixture `docs/contracts/share-text/*.json` (trip → text) is generated from golden snapshots so the Kotlin `ShareTextBuilder` produces identical output offline.

### 8.3 Progress events (SSE, SPEC §5.4, §7.7, §12)

Emitted by `Planner.plan` through `ProgressSink` (the planner never knows about HTTP):

| When | Event |
| --- | --- |
| before stage 2 (t ≈ 0, satisfies "first SSE stage ≤ 1 s") | `StageEvent(SPLIT, stage.route, 0.05)` |
| after stage 4 | `StageEvent(SPLIT, stage.split[_ring], 0.25)` |
| before stage 5 (only if days > 1) | `StageEvent(LODGING, stage.lodging.*, 0.30)` |
| after stage 5, per overnight | `StopEvent(day, f"night{d}", OVERNIGHT, HOTEL\|CITY, name, km_at, provisional=True)` |
| before stage 6 | `StageEvent(FUEL, stage.fuel, 0.50)` |
| before stage 9 | `StageEvent(HOURS, stage.hours, 0.65)` |
| after stage 10, per final stop in order | `StopEvent(…, provisional=False)` with the final stop id |
| before stage 12 | `StageEvent(COST, stage.cost, 0.90)` |

The same `key` may be emitted more than once; the client replaces the text of that step and never moves the bar backwards. One-day trips skip the lodging stage (the client shows 4 steps from whatever keys arrive). `done` and `error` are produced by the API (§10.4), not the planner.

---

## 9. Database schema (PostgreSQL 16 + PostGIS 3.4)

### 9.1 Schemas and roles

| Schema | Contents | Roles |
| --- | --- | --- |
| `core` | curated reference data (Directus-managed rows): region, town, place, ready_route, ready_route_point, region_price, toll_segment, app_config | `verst_api`: SELECT; `directus`: SELECT/INSERT/UPDATE/DELETE; `verst_migrator`: owner |
| `app` | runtime data: device, trip, trip_stop, feedback, pro_waitlist | `verst_api`: SELECT/INSERT/UPDATE/DELETE; `directus`: SELECT on feedback, pro_waitlist (curator views) |
| `directus` | Directus system tables (`directus_*`) | `directus`: owner |

Ids: `uuid` (`gen_random_uuid()`) for curated entities and devices; trips use text ids `trp_` + 12 Crockford base32 chars (`app.trip.id`), stops `d{day}s{nn}`. The planner treats all ids as opaque strings (fixtures use readable ids).

### 9.2 DDL (`backend/migrations/sql/0001_initial.sql`)

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS app;

-- Closed tag list (SPEC §9) as an immutable function so CHECK constraints stay readable
CREATE FUNCTION core.allowed_tags() RETURNS text[] LANGUAGE sql IMMUTABLE AS $$
  SELECT ARRAY['dogs_allowed','kids_menu','playground','family_room','parking','parking_guarded','ev_charger',
               'wc','cafe_at_fuel','24h','view','walk','museum','kremlin','monastery','evening','free_entry','cash_only']
$$;

CREATE FUNCTION core.touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at := now(); RETURN NEW; END $$;

-- Regions (federal subjects): fuel price key + time zone for local times
CREATE TABLE core.region (
  code        text PRIMARY KEY CHECK (code ~ '^RU(-[A-Z]{2,3})?$'),        -- ISO 3166-2:RU; 'RU' = national fallback
  name_ru     text NOT NULL,
  tz          text NOT NULL DEFAULT 'Europe/Moscow',                       -- IANA
  geom        geometry(MultiPolygon, 4326),                                -- NULL only for 'RU'
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX region_geom_gix ON core.region USING gist (geom);

CREATE TABLE core.town (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name_ru              text NOT NULL CHECK (length(name_ru) BETWEEN 1 AND 120),
  name_prep_ru         text,                                               -- «в Ярославле» form, for reasons
  geom                 geometry(Point, 4326) NOT NULL,
  region_code          text NOT NULL REFERENCES core.region(code),
  population           integer NOT NULL DEFAULT 0 CHECK (population >= 0),
  quality              smallint NOT NULL DEFAULT 0 CHECK (quality BETWEEN 0 AND 3),
  evening_walk         boolean NOT NULL DEFAULT false,
  lodging_count_cache  integer NOT NULL DEFAULT 0,
  osm_id               text UNIQUE,
  status               text NOT NULL DEFAULT 'live' CHECK (status IN ('draft','live','hidden')),
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX town_geom_gix  ON core.town USING gist (geom);
CREATE INDEX town_geog_gix  ON core.town USING gist ((geom::geography));
CREATE INDEX town_region_ix ON core.town (region_code);

CREATE TABLE core.place (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  type               text NOT NULL CHECK (type IN ('sight','food','fuel','rest','lodging','town')),
  name_ru            text NOT NULL CHECK (length(name_ru) BETWEEN 1 AND 160),
  geom               geometry(Point, 4326) NOT NULL,
  address            text,
  region_code        text NOT NULL REFERENCES core.region(code),
  town_id            uuid REFERENCES core.town(id) ON DELETE SET NULL,
  opening_hours      text,                                                 -- OSM syntax subset (§6.9)
  dwell_min          smallint CHECK (dwell_min BETWEEN 5 AND 480),
  avg_check_rub      integer CHECK (avg_check_rub >= 0),
  price_night_rub    integer CHECK (price_night_rub >= 0),                 -- per room per night
  breakfast_included boolean NOT NULL DEFAULT true,
  ticket_adult_rub   integer CHECK (ticket_adult_rub >= 0),
  ticket_child_rub   integer CHECK (ticket_child_rub >= 0),
  rating_internal    numeric(2,1) NOT NULL DEFAULT 3.0 CHECK (rating_internal BETWEEN 0 AND 5),
  tags               text[] NOT NULL DEFAULT '{}' CHECK (tags <@ core.allowed_tags()),
  description_ru     text CHECK (length(description_ru) <= 280),
  photo_keys         text[] NOT NULL DEFAULT '{}',
  yandex_travel_id   text,
  tripster_id        text,
  source             text NOT NULL CHECK (source IN ('curated','osm','partner')),
  osm_id             text UNIQUE,                                          -- 'n123' / 'w456'; import idempotency
  sponsored          boolean NOT NULL DEFAULT false,                       -- SPEC §14, always false in MVP
  verified_at        timestamptz,
  verified_by        text,                                                 -- Directus user email/id, curator only
  status             text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','live','hidden')),
  hidden_reason      text CHECK (hidden_reason IN ('feedback_closed','curator','duplicate')),
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT place_lodging_price CHECK (type <> 'lodging' OR status <> 'live' OR price_night_rub IS NOT NULL),
  CONSTRAINT place_live_verified CHECK (status <> 'live' OR source = 'osm' OR verified_at IS NOT NULL)
);
CREATE INDEX place_geom_gix      ON core.place USING gist (geom);
CREATE INDEX place_geog_live_gix ON core.place USING gist ((geom::geography)) WHERE status = 'live';
CREATE INDEX place_type_live_ix  ON core.place (type) WHERE status = 'live';
CREATE INDEX place_town_ix       ON core.place (town_id) WHERE type = 'lodging';
CREATE INDEX place_tags_gin      ON core.place USING gin (tags);
CREATE INDEX place_recheck_ix    ON core.place (verified_at) WHERE status = 'live';
CREATE TRIGGER place_touch BEFORE UPDATE ON core.place FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();
CREATE TRIGGER town_touch  BEFORE UPDATE ON core.town  FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();

-- lodging_count_cache maintenance
CREATE FUNCTION core.refresh_lodging_count() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE core.town t SET lodging_count_cache =
    (SELECT count(*) FROM core.place p WHERE p.town_id = t.id AND p.type = 'lodging' AND p.status = 'live')
  WHERE t.id IN (COALESCE(NEW.town_id, OLD.town_id), COALESCE(OLD.town_id, NEW.town_id));
  RETURN NULL;
END $$;
CREATE TRIGGER place_lodging_count AFTER INSERT OR UPDATE OF town_id, status, type OR DELETE ON core.place
  FOR EACH ROW EXECUTE FUNCTION core.refresh_lodging_count();

CREATE TABLE core.ready_route (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug          text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9-]{3,40}$'),   -- 'golden-ring'
  hub_town_id   uuid NOT NULL REFERENCES core.town(id),
  title_ru      text NOT NULL,
  subtitle_ru   text NOT NULL DEFAULT '',                                   -- «3 дня · 8 городов · по кругу»
  km_total      integer NOT NULL CHECK (km_total > 0),                      -- whole trip
  km_sign       integer NOT NULL CHECK (km_sign > 0),                       -- shown on the overhead sign (SPEC §7.6)
  ring          text NOT NULL CHECK (ring IN ('weekend','long')),
  round_trip    boolean NOT NULL DEFAULT true,
  days_min      smallint NOT NULL CHECK (days_min BETWEEN 1 AND 14),
  days_max      smallint NOT NULL CHECK (days_max BETWEEN 1 AND 14),
  tags          text[] NOT NULL DEFAULT '{}',
  cover_key     text,
  sort          integer NOT NULL DEFAULT 100,
  status        text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','live','hidden')),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CHECK (days_min <= days_max)
);
CREATE INDEX ready_route_hub_ix ON core.ready_route (hub_town_id) WHERE status = 'live';

-- SPEC "points (ordered place/town ids)" and "suggested_nights[]" normalised for FK integrity
CREATE TABLE core.ready_route_point (
  route_id   uuid NOT NULL REFERENCES core.ready_route(id) ON DELETE CASCADE,
  seq        smallint NOT NULL CHECK (seq >= 1),
  role       text NOT NULL CHECK (role IN ('via','stop','night')),
  town_id    uuid REFERENCES core.town(id),
  place_id   uuid REFERENCES core.place(id),
  PRIMARY KEY (route_id, seq),
  CHECK ((role = 'stop' AND place_id IS NOT NULL) OR (role IN ('via','night') AND town_id IS NOT NULL))
);

CREATE TABLE core.region_price (
  region_code  text NOT NULL REFERENCES core.region(code),
  fuel_type    text NOT NULL CHECK (fuel_type IN ('ai92','ai95','dt')),
  as_of        date NOT NULL,
  price_rub    numeric(6,2) NOT NULL CHECK (price_rub > 0 AND price_rub < 1000),
  source_note  text,
  PRIMARY KEY (region_code, fuel_type, as_of)
);

CREATE TABLE core.toll_segment (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  road_ref         text NOT NULL,                                          -- 'М-11'
  name_ru          text NOT NULL,                                          -- 'М-11, км 15–58'
  geom             geometry(LineString, 4326) NOT NULL,
  tariff_day_rub   numeric(8,2) NOT NULL CHECK (tariff_day_rub >= 0),
  tariff_night_rub numeric(8,2) NOT NULL CHECK (tariff_night_rub >= 0),
  night_from       time NOT NULL DEFAULT '00:00',
  night_to         time NOT NULL DEFAULT '06:00',
  vehicle_class    smallint NOT NULL DEFAULT 1 CHECK (vehicle_class BETWEEN 1 AND 4),
  as_of            date NOT NULL,
  status           text NOT NULL DEFAULT 'live' CHECK (status IN ('draft','live','hidden')),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX toll_segment_geog_gix ON core.toll_segment USING gist ((geom::geography)) WHERE status = 'live';

CREATE TABLE core.app_config (
  key         text PRIMARY KEY CHECK (key IN ('planner','reasons_ru','links','navigator_links','features',
                                               'min_app_version','copy_ru')),
  value       jsonb NOT NULL,
  updated_at  timestamptz NOT NULL DEFAULT now(),
  updated_by  text
);

-- ---------- runtime ----------
CREATE TABLE app.device (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  token_hash    bytea NOT NULL UNIQUE,                                     -- sha256(token)
  created_at    timestamptz NOT NULL DEFAULT now(),
  app_version   text NOT NULL CHECK (length(app_version) <= 32),
  locale        text NOT NULL DEFAULT 'ru-RU' CHECK (length(locale) <= 16),
  last_seen_at  timestamptz NOT NULL DEFAULT now(),
  revoked_at    timestamptz
);

CREATE TABLE app.trip (
  id              text PRIMARY KEY CHECK (id ~ '^trp_[0-9a-hjkmnp-tv-z]{12}$'),
  device_id       uuid NOT NULL REFERENCES app.device(id) ON DELETE CASCADE,
  input           jsonb NOT NULL,                                          -- normalised TripInput (camelCase)
  result          jsonb NOT NULL,                                          -- PlanResponse body (days, stops, cost, reasons)
  engine_state    jsonb NOT NULL,                                          -- EngineState, server-only
  engine_version  text NOT NULL,
  title_ru        text NOT NULL,
  km              integer NOT NULL,
  days            smallint NOT NULL,
  ready_route_id  uuid REFERENCES core.ready_route(id) ON DELETE SET NULL,
  has_warnings    boolean NOT NULL DEFAULT false,
  saved           boolean NOT NULL DEFAULT false,
  saved_at        timestamptz,
  share_slug      text UNIQUE CHECK (share_slug ~ '^[0-9a-hjkmnp-tv-z]{8}$'),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  CHECK (NOT saved OR (saved_at IS NOT NULL AND share_slug IS NOT NULL))
);
CREATE INDEX trip_device_ix  ON app.trip (device_id, created_at DESC);
CREATE INDEX trip_cleanup_ix ON app.trip (created_at) WHERE NOT saved;

CREATE TABLE app.trip_stop (
  trip_id       text NOT NULL REFERENCES app.trip(id) ON DELETE CASCADE,
  seq           smallint NOT NULL CHECK (seq >= 1),
  stop_id       text NOT NULL CHECK (stop_id ~ '^d[0-9]{1,2}s[0-9]{2}$'),
  day           smallint NOT NULL CHECK (day >= 1),
  place_id      uuid REFERENCES core.place(id) ON DELETE SET NULL,
  town_id       uuid REFERENCES core.town(id) ON DELETE SET NULL,
  kind          text NOT NULL CHECK (kind IN ('start','sight','food','fuel','rest','overnight','via','finish')),
  arrive_at     timestamp,                                                 -- local wall time of the stop
  depart_at     timestamp,
  tz            text NOT NULL,
  km_from_prev  integer NOT NULL CHECK (km_from_prev >= 0),
  km_at         integer NOT NULL CHECK (km_at >= 0),
  cost_rub      integer NOT NULL DEFAULT 0,
  reason_ru     text NOT NULL DEFAULT '',
  alternatives  jsonb NOT NULL DEFAULT '[]',
  PRIMARY KEY (trip_id, seq),
  UNIQUE (trip_id, stop_id)
);
CREATE INDEX trip_stop_place_ix ON app.trip_stop (place_id);

CREATE TABLE app.feedback (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id   uuid NOT NULL REFERENCES app.device(id) ON DELETE CASCADE,
  trip_id     text REFERENCES app.trip(id) ON DELETE SET NULL,
  place_id    uuid REFERENCES core.place(id) ON DELETE CASCADE,
  kind        text NOT NULL CHECK (kind IN ('closed','wrong_tag','price','other')),
  text        text CHECK (length(text) <= 1000),
  created_at  timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz
);
CREATE INDEX feedback_place_ix ON app.feedback (place_id, kind) WHERE resolved_at IS NULL;

-- SPEC §9 curation rule 3: hide a place after 2 'closed' reports (distinct devices) since its last verification
CREATE FUNCTION app.feedback_autohide() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  IF NEW.kind = 'closed' AND NEW.place_id IS NOT NULL THEN
    UPDATE core.place p SET status = 'hidden', hidden_reason = 'feedback_closed'
    WHERE p.id = NEW.place_id AND p.status = 'live'
      AND (SELECT count(DISTINCT f.device_id) FROM app.feedback f
           WHERE f.place_id = NEW.place_id AND f.kind = 'closed' AND f.resolved_at IS NULL
             AND f.created_at > COALESCE(p.verified_at, '-infinity')) >= 2;
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER feedback_autohide AFTER INSERT ON app.feedback FOR EACH ROW EXECUTE FUNCTION app.feedback_autohide();

CREATE TABLE app.pro_waitlist (
  device_id   uuid NOT NULL REFERENCES app.device(id) ON DELETE CASCADE,
  source      text NOT NULL CHECK (source IN ('waybill','settings','other')),
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (device_id)
);

-- Curator views (Directus): places due for re-check (SPEC §9 rule 3)
CREATE VIEW core.place_recheck_due AS
  SELECT id, type, name_ru, region_code, verified_at FROM core.place
  WHERE status = 'live' AND source <> 'osm' AND verified_at < now() - interval '180 days';
```

### 9.3 Data lifecycle
- Unsaved trips are deleted after 30 days (`jobs` service, daily 03:30 MSK: `DELETE FROM app.trip WHERE NOT saved AND created_at < now() - interval '30 days'`). Saved trips are kept until the device is revoked + 365 days.
- Devices with no activity for 400 days are deleted with cascade.
- Logs never contain coordinates with more than 3 decimals (SPEC §16): the logging filter rounds any `lat`/`lon` fields.

### 9.4 Migration strategy
- **Alembic, SQL-first**: each revision `versions/YYYYMMDD_NNNN_<slug>.py` executes `sql/NNNN_<slug>.sql` (forward) and has a hand-written `downgrade` for non-destructive changes; destructive changes are expand → migrate → contract over two releases.
- SQLAlchemy 2 Core `Table` objects in `verst_api/db/tables.py` mirror the DDL; a CI test (`test_schema_matches.py`) reflects the migrated DB and compares columns/types with `tables.py`.
- Directus never runs DDL on `core`/`app` (collections are registered against existing tables; `admin/directus/snapshot.yaml` contains only Directus metadata and is applied with `directus schema apply`).
- Seed: `migrations/seed/*.sql` (regions with geometries from OSM admin_level=4, launch ready routes, prices) applied by `make seed` in dev/staging only; production data enters via Directus.
- CI applies all migrations to an empty PostGIS container, runs `alembic downgrade -1 && alembic upgrade head`, then the API test-suite.

### 9.5 Directus
Directus 11 on the same database, connecting as role `directus`. Collections: town, place (map interface on `geom`, tags as a tag dropdown limited to `core.allowed_tags()`), ready_route (+ O2M ready_route_point), region_price, toll_segment (map line interface), app_config (JSON editor; editable by role `lead` only), feedback (read + `resolved_at`), pro_waitlist (read). Roles: `curator` (CRUD on place/town/prices, cannot set `status=live` without `verified_at` — enforced by the DB CHECK), `lead` (all + app_config + ready_route publish), `viewer`. `verified_by`/`verified_at` are set by a Directus flow on `status → live`.

---

## 10. HTTP API (`verst_api`)

### 10.1 Conventions
Base `https://api.verst.app/v1`; JSON camelCase; `Authorization: Bearer <token>` on every `/v1` endpoint except `POST /v1/devices` and `GET /v1/config`; `X-Request-Id` echoed or generated; `X-App-Version` header required (from the app) and logged. Times: local ISO 8601 without offset + `tz`. Money: integer roubles. Distances: integer km.

### 10.2 Endpoint → handler → service → engine

| Method & path | Router handler (`verst_api/routers/…`) | Service call | Engine / adapters | Notes |
| --- | --- | --- | --- | --- |
| `POST /v1/devices` | `devices.register` | `DeviceService.register(app_version, locale)` | — | 201 `{deviceId, token}`; token 32 random bytes base64url; stores sha256 |
| `GET /v1/config` | `config.get` | `ConfigService.public_config()` | — | `{minAppVersion, features, navigatorLinks, copy, configVersion}`; `ETag`, `Cache-Control: max-age=300` |
| `GET /v1/ready-routes?lat&lon&limit=20` | `ready_routes.list` | `ReadyRouteService.near(point, limit)` | `PlaceRepository.ready_routes_near(50 km)` + `geo.bearing8` | Items `{id, slug, title, subtitle, km, ring, days, bearing, coverKey, tags}` |
| `GET /v1/ready-routes/{id}` | `ready_routes.get` | `ReadyRouteService.get(id)` | `get_ready_route`, `get_towns/places` | 404 NOT_FOUND |
| `GET /v1/geocode/suggest?q&lat&lon&limit=6` | `geocode.suggest` | `GeocodeService.suggest` | `GeocodingPort.suggest` (Photon, cached) | `q` 2–100 chars; adds `distanceKm` from (lat,lon); on Photon timeout → 200 with `[]` and `degraded: true` |
| `GET /v1/geocode/reverse?lat&lon` | `geocode.reverse` | `GeocodeService.reverse` | `GeocodingPort.reverse` | 200 `{name, subtitle}`; none → 404 NOT_FOUND |
| `POST /v1/trips/plan` | `trips.plan` | `TripService.plan(device, TripInputDTO, sink, cancel)` | `Planner.plan` in thread | `Accept: text/event-stream` → SSE (§10.4); otherwise 201 `PlanResponse`; rate limit 30/h/device |
| `GET /v1/trips/{id}` | `trips.get` | `TripService.get(device, id)` | — | owner only (404 otherwise) |
| `POST /v1/trips/{id}/stops/{stopId}/replace` | `trips.replace_stop` | `TripService.replace_stop(device, id, stop_id, alt_id)` | `Planner.replace_stop` | 200 `PlanResponse` (full, so the app overwrites its copy) |
| `PATCH /v1/trips/{id}` | `trips.patch` | `TripService.patch(device, id, TripPatchDTO)` | `Planner.recompute_cost` | Allowed: crew counts (same `dog` and same `children == 0`-ness), `budgetRub`, `reserveOn`, `hotelChoice{stopId, placeId}`; otherwise 400 INVALID_INPUT `details.reason = "replan_required"` |
| `POST /v1/trips/{id}/save` | `trips.save` | `TripService.save(device, id)` | — | Idempotent; 200 `{shareSlug, shareUrl}`; 409 LIMIT_REACHED if 50 saved trips |
| `GET /v1/links/hotel?tripId&stopId&placeId` | `links.hotel` | `LinkService.hotel_link(...)` | — | `{url, partner: "yandex_travel"}` (§10.7) |
| `GET /v1/links/excursion?tripId&placeId` | `links.excursion` | `LinkService.excursion_link` | — | SPEC §14 Tripster (extension of §12) |
| `GET /v1/links/navigator?tripId&day&app&fromStopId?` | `links.navigator` | `LinkService.navigator_link` | — | `app ∈ yandex_navi, yandex_maps, dgis`; `fromStopId` for long-press "отсюда" |
| `POST /v1/feedback` | `feedback.create` | `FeedbackService.create` | DB trigger auto-hide | 201; 10/day/device |
| `POST /v1/pro-waitlist` | `pro.join` | `ProService.join(device, source)` | — | SPEC §14 waitlist (extension), idempotent 204 |
| `GET /v1/shared/{shareSlug}` | `shared.get` | `TripService.get_shared(slug)` | — | Read-only trip for deep-link recipients with the app (extension) |
| `GET /s/{shareSlug}` | `public.share_page` | `TripService.get_shared` + `explain.share.share_text` | — | HTML page, `Content-Language: ru`, Android App Link target |
| `GET /healthz`, `GET /readyz`, `GET /metrics` | `ops.*` | — | readyz checks DB, Redis, GraphHopper `/health`, Photon | `/metrics` only on the private network |

### 10.3 Request / response models (`verst_api/schemas/`, pydantic v2, `alias_generator=to_camel`, `extra="forbid"` on requests)

```python
class PointDTO(BaseModel):      lat: float = Field(ge=41, le=82); lon: float; label: str | None = Field(None, max_length=200); placeId: str | None = None
class CrewDTO(BaseModel):       adults: int = Field(ge=1, le=7); children: int = Field(0, ge=0, le=5); dog: bool = False
class VehicleDTO(BaseModel):    consumption: float = Field(8.0, ge=4, le=20); fuelType: Literal["ai92","ai95","dt"] = "ai95"; tankL: float = Field(50, ge=20, le=150)
class TripInputDTO(BaseModel):
    origin: PointDTO; destination: PointDTO | None = None; vias: list[PointDTO] = Field(default_factory=list, max_length=3)
    readyRouteId: str | None = None; roundTrip: bool | None = None; crew: CrewDTO
    dailyKm: int = Field(ge=150, le=900, multiple_of=50); budget: int | None = Field(None, ge=1000, le=10_000_000)
    vehicle: VehicleDTO = VehicleDTO(); startAt: datetime | None = None    # naive local
    mood: Literal["calm","more_stops","just_drive"] | None = None; avoidTolls: bool = False
    reserveOn: bool = True; simplify: bool = False

class PlanResponse(BaseModel):      # mirrors codec.plan_to_json; SPEC §12 fields + extensions marked (+)
    id: str; title: str; km: int; days: int; nights: int; roundTrip: bool (+)
    daysList: list[DayDTO]; cost: CostDTO; reasons: ReasonsDTO
    warnings: list[WarningDTO] (+); input: TripInputDTO (+); engineVersion: str (+)
    saved: bool (+); shareSlug: str | None (+); createdAt: datetime (+); shareText: str (+)
class DayDTO:   day: int; km: int; driveMin: int; tz: str (SPEC §12 "tz per day"); startAt: str; endAt: str; overBudget: bool; stops: list[StopDTO]
class StopDTO:  id; seq; kind; sign; placeId | None; townId | None; name; note | None; lat; lon; alternativesNote | None (§16.6);
                arriveAt | None; departAt | None; kmFromPrev; kmAt; dwellMin; tags: list[str]; costRub;
                reason; verified: bool; replaceable: bool; alternatives: list[AlternativeDTO];
                hotelOptions: list[HotelOptionDTO]; selectedHotelId | None
class AlternativeDTO: id; placeId; name; deltaMin; deltaRub; shiftMin; units: AltUnitsDTO; stop: StopDTO (alternatives=[]);
                dayPatch: list[{stopId, arriveAt | None, departAt | None, kmFromPrev, seq}]   # §16.6: the day re-timed with this alternative
class CostDTO:  lines: list[CostLineDTO]; reserveOn; subtotalRub; totalRub; perPersonRub; budgetRub | None;
                remainingRub | None; overBudget; hints: list[str] (rendered ru); pricesAsOf: str; units: CostUnitsDTO
class CostLineDTO: key; title; rub; formula; asOf; enabled; breakdown: list[{label, formula, rub}]
class ReasonsDTO: overnights: list[{day, townId | None, town, text, candidates: list[str], fallback}]   # fallback added §16.1
class WarningDTO: code; day | None; message
class TripPatchDTO: crew: CrewDTO | None; budgetRub: int | None; reserveOn: bool | None; hotelChoice: {stopId, placeId} | None
```
The canonical example is `docs/contracts/plan-response.example.json` (G02 Golden Ring snapshot rendered through the codec, matching the SPEC §12 example).

### 10.4 SSE stream (`verst_api/sse.py`)

```
HTTP/1.1 200 OK
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache
X-Accel-Buffering: no
X-Request-Id: 9b1c…

retry: 3000

event: stage
id: 1
data: {"key":"split","text":"Прокладываем дорогу","progress":0.05}

event: stage
id: 2
data: {"key":"split","text":"Делим кольцо на 3 дня по ≈ 250 км","progress":0.25}

event: stop
id: 4
data: {"day":1,"stop":{"id":"night1","kind":"overnight","sign":"hotel","name":"Ярославль","kmAt":265,"provisional":true}}

: ping

event: done
id: 19
data: {"tripId":"trp_7f3c0q2m9z4x","trip":{…PlanResponse…}}
```
- `error` event: `data: {"code":"UNREACHABLE","message":"Не нашли дорогу на машине до этой точки","details":{"pointIndex":1}}`, then the stream closes.
- Errors detected **before** the stream starts (auth, validation, rate limit) are plain HTTP errors (§10.6). Everything after the 200 is an `error` event.
- Heartbeat comment every 5 s. Server hard limit 25 s per plan → `error` `UPSTREAM`. Client disconnect → `CancelToken.cancel()`; the worker stops at the next checkpoint; nothing is persisted.
- `done.trip` is an extension of SPEC (`done {tripId}`) that saves one round trip; the app still supports fetching `GET /v1/trips/{id}` when `trip` is absent.
- Bridge: `QueueSink(loop, queue).emit(e)` → `loop.call_soon_threadsafe(queue.put_nowait, e)`; the response generator awaits `queue.get()` with a 5 s timeout (→ ping).

### 10.5 Persistence flow of `TripService.plan`
1. `RateLimiter.hit("plan", device_id, limit=30, window=3600)` (Redis ZSET sliding window) → 429.
2. `TripInputDTO` → `TripInput` (`schemas.mappers.to_domain`).
3. `trip_id = new_trip_id()`; run planner (thread) with `CachedRouting(GraphHopperRouting)`, Pg repositories, `PlannerConfig` + `ReasonTemplates` from `ConfigService` (cached 60 s).
4. In one transaction: insert `app.trip` (input, result = `codec.plan_to_json`, engine_state) and `app.trip_stop` rows; commit; emit `done`.
5. Metrics: `plan_latency_seconds` histogram (labels: outcome, km_bucket), `upstream_timeouts_total{service}`, `plan_warnings_total{code}`.

### 10.6 Error mapping (`verst_api/errors.py`)

Envelope: `{"error": {"code": "…", "message": "<ru>", "details": {…}}}`. Messages come from `core.app_config['copy_ru']` (defaults = SPEC §12 table).

| Source | HTTP | `code` | Message (ru) |
| --- | --- | --- | --- |
| pydantic `RequestValidationError`, `InvalidInput` | 400 | `INVALID_INPUT` | «Проверьте параметры поездки» |
| missing/invalid token | 401 | `UNAUTHORIZED` | «Перезапустите приложение» (app re-registers silently) |
| `NotFound` (trip, stop, alternative, ready route, slug) | 404 | `NOT_FOUND` | «Не нашли поездку» |
| `Unreachable` | 404 | `UNREACHABLE` | «Не нашли дорогу на машине до этой точки» |
| saved-trip limit | 409 | `LIMIT_REACHED` | «Можно сохранить до 50 поездок» |
| `TooShort` | 422 | `TOO_SHORT` | «Слишком близко для поездки на машине» |
| rate limit | 429 + `Retry-After` | `RATE_LIMITED` | «Слишком много запросов, подождите минуту» |
| `UpstreamUnavailable`, plan timeout, DB down | 503 | `UPSTREAM` | «Сервис маршрутов временно недоступен» |
| unhandled | 500 | `INTERNAL` | «Что-то пошло не так, попробуйте ещё раз» (logged with request id, GlitchTip) |
| `NO_LODGING` | — | in `warnings[]` of a 200/201 trip | SPEC §12 text |

[D-2] `NO_LODGING` is never an HTTP error: SPEC says "warning, trip still returned"; returning 422 with a body would break clients that treat 4xx as failure.

### 10.7 Partner links (`LinkService`, templates in `core.app_config['links']`)

```json
{"hotel": {
   "target": "https://travel.yandex.ru/hotels/{hotel_path}?checkinDate={checkin}&checkoutDate={checkout}&adults={adults}&childrenAges={children_ages}",
   "hotelPath": {"byId": "{yandex_travel_id}/", "byCity": "search/?geoId=&text={city}"},
   "wrapper": "https://tp.media/r?marker={marker}&trs={trs}&p={program}&u={target_urlencoded}&campaign_id={campaign}&sub_id={trip_id}_{stop_id}",
   "marker": "verst_app", "trs": "", "program": "", "campaign": ""},
 "excursion": {"target": "https://experience.tripster.ru/experience/{tripster_id}/", "wrapper": "…same…"}}
```
`checkin` = arrival date of the overnight; `checkout` = +1 day; `adults` = crew adults; `children_ages` = child ages or `assumed_child_age` repeated. Empty Travelpayouts ids (until the CEO provides the account) → the target URL is returned unwrapped and `affiliate: false` in the response, logged as a warning.

Navigator templates (`core.app_config['navigator_links']`, also sent in `/v1/config`; to be verified on devices in M5):
```json
{"yandex_navi": {"package": "ru.yandex.yandexnavi", "url": "yandexnavi://build_route_on_map?lat_to={to_lat}&lon_to={to_lon}{vias:&lat_via_{i}={lat}&lon_via_{i}={lon}}", "maxVias": 8},
 "yandex_maps": {"package": "ru.yandex.yandexmaps", "url": "yandexmaps://maps.yandex.ru/?rtext={from_lat},{from_lon}{vias:~{lat},{lon}}~{to_lat},{to_lon}&rtt=auto", "maxVias": 8},
 "dgis":        {"package": "ru.dublgis.dgismobile", "url": "dgis://2gis.ru/routeSearch/rsType/car/from/{from_lon},{from_lat}/to/{to_lon},{to_lat}", "maxVias": 0}}
```
`{vias:…}` is a repeat block over the day's intermediate stops (in order, truncated to `maxVias`, keeping the overnight/finish as destination).

### 10.8 Cross-cutting
- Auth dependency `current_device` (sha256 lookup, `last_seen_at` updated at most once per hour).
- Rate limits: plan 30/h/device; all other endpoints 600/h/device; nginx 120 req/min/IP.
- Logging: JSON lines (`ts, level, request_id, device_id(hash prefix 8), route, status, latency_ms, upstream`), coordinates rounded to 3 decimals.
- Timeouts: GraphHopper 6 s, Photon 1.5 s, DB statement 3 s (`SET statement_timeout`), plan 25 s.

---

## 11. Android app architecture

### 11.1 Toolchain and pinned versions (`android/gradle/libs.versions.toml`)

These are the newest versions verified by the Architect to be mutually compatible with the preinstalled **Gradle 8.14**. They are a floor, not a ceiling: **when network access is enabled, DEV-A01 must re-verify each version against Google Maven / Maven Central, bump to the latest stable patch of the same line, and record the result in this table.**

| Alias | Artifact | Version |
| --- | --- | --- |
| agp | com.android.application / library | 8.11.1 |
| kotlin | org.jetbrains.kotlin.android, plugin.compose, plugin.serialization | 2.2.0 |
| ksp | com.google.devtools.ksp | 2.2.0-2.0.2 |
| compose-bom | androidx.compose:compose-bom | 2025.07.00 |
| activity-compose | androidx.activity:activity-compose | 1.10.1 |
| lifecycle | androidx.lifecycle:lifecycle-runtime-compose, -viewmodel-compose | 2.9.1 |
| navigation | androidx.navigation:navigation-compose (type-safe routes) | 2.9.1 |
| hilt | com.google.dagger:hilt-android, hilt-compiler | 2.56.2 |
| hilt-navigation-compose | androidx.hilt:hilt-navigation-compose | 1.2.0 |
| room | androidx.room:room-runtime, -ktx, -compiler, -testing | 2.7.2 |
| datastore | androidx.datastore:datastore-preferences | 1.1.7 |
| coroutines | org.jetbrains.kotlinx:kotlinx-coroutines-android/-test | 1.10.2 |
| serialization | org.jetbrains.kotlinx:kotlinx-serialization-json | 1.9.0 |
| retrofit | com.squareup.retrofit2:retrofit + converter-kotlinx-serialization | 3.0.0 |
| okhttp | com.squareup.okhttp3:okhttp, okhttp-sse, logging-interceptor, mockwebserver3 | 5.1.0 |
| maplibre | org.maplibre.gl:android-sdk | 11.12.1 |
| appmetrica | io.appmetrica.analytics:analytics | 7.10.0 |
| core-splashscreen | androidx.core:core-splashscreen | 1.0.1 |
| junit | junit:junit | 4.13.2 |
| turbine | app.cash.turbine:turbine | 1.2.1 |
| robolectric | org.robolectric:robolectric | 4.15.1 |
| paparazzi | app.cash.paparazzi (plugin) | 1.3.5 |
| detekt / ktlint | io.gitlab.arturbosch.detekt / org.jlleitschuh.gradle.ktlint | 1.23.8 / 12.3.0 |

SDK: `minSdk 26`, `compileSdk 36`, `targetSdk 36`, JVM target 17 (Java 21 toolchain builds it). `applicationId = "app.verst"` [D-7]. Build types: `debug` (API `https://api.staging.verst.app/v1`, `.debug` suffix), `release` (R8 full mode, `https://api.verst.app/v1`). Single flavor in MVP.

### 11.2 Gradle modules and dependency graph

```
:app ──▶ :feature-windshield :feature-navigator :feature-instruments :feature-drive
         :feature-road :feature-waybill :feature-exit ──▶ :core-ui, :core-model, :data(api only via interfaces in :core-model)
:data ──▶ :core-model
:core-ui ──▶ :core-model (for formatting value types only)
:core-model ──▶ kotlin stdlib + kotlinx-serialization only (pure JVM module: `kotlin("jvm")`)
```
Rules: features never depend on each other (navigation through `:app`); features depend on `:data` only through repository interfaces declared in `:core-model` (`TripRepository`, `ReadyRouteRepository`, `GeocodeRepository`, `DefaultsRepository`, `ConfigRepository`, `LinkRepository`) and bound in `:data` with Hilt. Enforced by a Gradle check task (`checkModuleGraph`) in `:app`.

| Module | Type | Contents |
| --- | --- | --- |
| `:app` | application | `VerstApp` (@HiltAndroidApp, AppMetrica init), `MainActivity` (single activity, edge-to-edge, portrait lock), `VerstNavHost`, deep-link handling (`https://verst.app/s/{slug}`, `verst://trip/{id}`), `ExternalAppLauncher` (Intent resolution, installed-app checks via `<queries>` for the 3 navigator packages) |
| `:core-model` | JVM library | domain models (§11.5), DTOs (`@Serializable`), repository interfaces, `CostCalculator` (port of `cost/recompute.py`), `ScheduleShifter` (applies `shiftMin` after a replace), `ShareTextBuilder`, `RuFormat` (thin-space numbers, plurals день/дня/дней), `Bearing8` |
| `:core-ui` | Android library | `VerstTheme` + tokens (§11.7), fonts (res/font), components: `OverheadSign`, `RoadSign`, `Mirror`, `Odometer`, `FuelGauge`, `StartButton`, `NaviPanel`, `WindshieldScene`, `WaybillSheet`, `Shimmer`, `BackLink`, `SignBottomSheet`; `rememberReducedMotion()`; `MotionSpec` |
| `:data` | Android library | Retrofit `VerstApi`, `PlanStreamClient` (OkHttp SSE), `AuthInterceptor`, `DeviceTokenStore`, Room `VerstDatabase` + DAOs, DataStore, repository implementations, `ConnectivityObserver`, `Clock` |
| `:feature-windshield` | Android library | 5.1 Windshield screen, ready routes sheet, saved trips sheet |
| `:feature-navigator` | Android library | 5.2 Navigator + `MapPickerScreen` (MapLibre) |
| `:feature-instruments` | Android library | 5.3 Instruments + settings sheet |
| `:feature-drive` | Android library | 5.4 Drive (SSE progress) |
| `:feature-road` | Android library | 5.5 Road ahead + replace sheet + navigator hand-off |
| `:feature-waybill` | Android library | 5.6 Waybill + Pro waitlist sheet |
| `:feature-exit` | Android library | 5.7 Exit to overnight (hotel selection, booking, «Забронировали?») |

Package layout: `app.verst.<module>` (e.g. `app.verst.feature.road`), inside each feature: `RoadScreen.kt` (stateless composable taking `RoadUiState` + `(RoadIntent) -> Unit`), `RoadRoute.kt` (stateful wrapper: `hiltViewModel`, collects state, handles effects), `RoadViewModel.kt`, `RoadUiState.kt`, `RoadIntent.kt`, `RoadEffect.kt`, `components/`.

### 11.3 Navigation graph (type-safe Navigation Compose, `@Serializable` routes in `:app`)

```kotlin
@Serializable data object WindshieldRoute
@Serializable data class NavigatorRoute(val focus: Field = Field.TO)
@Serializable data object MapPickerRoute                     // returns LatLon via SavedStateHandle "picked_point"
@Serializable data class InstrumentsRoute(val readyRouteId: String? = null, val draftId: String? = null)
@Serializable data class DriveRoute(val requestId: String)   // PlanRequest kept in PlanSession (in-memory, @Singleton)
@Serializable data class RoadRoute(val tripId: String)
@Serializable data class WaybillRoute(val tripId: String)
@Serializable data class ExitRoute(val tripId: String, val stopId: String)
```
Edges (SPEC §4): Windshield → Navigator | Instruments(readyRouteId) | Instruments(mirror) | Road(saved trip); Navigator → MapPicker (result) | Instruments(draftId); Instruments → Drive; Drive → Road with `popUpTo(DriveRoute){inclusive=true}` so back from Road returns to Instruments; Road → Waybill | Exit | external; Exit → external browser. Deep link `https://verst.app/s/{slug}` → `RoadRoute` after `GET /v1/shared/{slug}` import (read-only copy saved locally). No bottom bar; every screen has `BackLink` (top-left) + system back.

### 11.4 State management (UDF/MVVM)

- One `@HiltViewModel` per screen exposing `val state: StateFlow<XUiState>` (`stateIn(viewModelScope, WhileSubscribed(5_000), initial)`), `fun onIntent(intent: XIntent)`, and `val effects: Flow<XEffect>` (`Channel(BUFFERED).receiveAsFlow()`) for one-off navigation/external intents.
- Reducers are pure functions `reduce(state, result) -> state` unit-tested without Android.
- Shared session state: `PlanDraftStore` (@Singleton, `MutableStateFlow<PlanDraft>`) holds origin/destination/vias/readyRouteId between Navigator → Instruments → Drive; persisted parts (crew, km, budget, vehicle, mood) go to DataStore on change (SPEC §5.3 "persist as defaults").
- `TripRepository` is the single source of truth for trips: `observeTrip(id): Flow<Trip?>` reads Room; network results are written to Room first, then observed.
- Example (Drive):
```kotlin
data class DriveUiState(val steps: List<DriveStep>, val progress: Float, val flyingSigns: List<SignUi>,
                        val phase: Phase /* Running, Slow, Done, Failed */, val error: UiError?)
sealed interface DriveIntent { data object Wait; data object Simplify; data object Retry; data object Back }
sealed interface DriveEffect { data class OpenRoad(val tripId: String) : DriveEffect; data object Close : DriveEffect }
```
Drive timers: `Slow` at 20 s (SPEC §5.4) shows «Подождать» / «Упростить маршрут» (cancels and re-requests with `simplify=true`); `Done` → effect `OpenRoad` after 1 000 ms; back cancels the SSE call (`EventSource.cancel()`).
- Replace (offline-capable): `RoadViewModel.onIntent(Replace(stopId, altId))` → `TripEditor.applyAlternative(trip, stopId, altId)` (pure, in `:core-model`: swaps the stop with `alt.stop`, shifts later stops of that day by `shiftMin`, recomputes cost with `CostCalculator`) → Room; then if online `POST …/replace` and overwrite with the server result; offline → `pending_ops` row replayed on reconnect (only if the alternative was cached; SPEC §13).

### 11.5 Client models and Room schema (`VerstDatabase`, version 1, `exportSchema = true` to `android/data/schemas/`)

Client models in `:core-model` are the `@Serializable` mirror of `PlanResponse` (§10.3): `TripDto`, `DayDto`, `StopDto`, `AlternativeDto`, `CostDto`, `CostUnitsDto`… plus domain wrappers `Trip(dto, local: TripLocalState)`.

| Entity / table | Columns | Notes |
| --- | --- | --- |
| `trip` | `id TEXT PK`, `title TEXT`, `km INT`, `days INT`, `start_date TEXT`, `json TEXT` (full PlanResponse incl. alternatives + cost units), `engine_version TEXT`, `saved INT`, `share_slug TEXT?`, `fetched_at INTEGER` (epoch ms), `updated_at INTEGER`, `is_last_slot INT` | Saved trips (≤ 50, warn at 45) and exactly one unsaved "last trip" row (`is_last_slot = 1`, overwritten by the next plan; SPEC §13). Index on `(saved, updated_at)` |
| `trip_local` | `trip_id TEXT PK FK→trip ON DELETE CASCADE`, `reserve_on INT`, `selected_hotels TEXT` (json map stopId→placeId), `booked_stops TEXT` (json set), `crew_override TEXT?` | Local edits; survive re-fetch |
| `pending_op` | `id INTEGER PK AUTO`, `trip_id TEXT`, `kind TEXT` (`replace`, `patch`, `save`), `payload TEXT`, `created_at INTEGER`, `attempts INT` | Replayed by `PendingOpsWorker` (coroutine on connectivity regain; no WorkManager in MVP) |
| `ready_route_cache` | `id TEXT PK`, `rank INT`, `json TEXT`, `origin_lat REAL`, `origin_lon REAL`, `fetched_at INTEGER` | Last 20 near the last start |
| `recent_search` | `id INTEGER PK AUTO`, `name TEXT`, `subtitle TEXT`, `kind TEXT`, `lat REAL`, `lon REAL`, `used_at INTEGER`; UNIQUE(`name`,`lat`,`lon`) | Keep last 10 (trim on insert) |
| `config_cache` | `id INT PK = 1`, `json TEXT`, `etag TEXT?`, `fetched_at INTEGER` | Remote config |

Migrations: every schema change adds a `Migration(n, n+1)` and an instrumented `MigrationTestHelper` test; CI runs Robolectric-based migration tests on every PR (SPEC §16 "migrations tested in CI"). `fallbackToDestructiveMigration` is **forbidden**.

### 11.6 DataStore keys (`verst_prefs`, Preferences DataStore)

| Key | Type | Default |
| --- | --- | --- |
| `device_id` / `device_token` | String | — (stored in a separate `verst_secure` DataStore file; not backed up: `android:allowBackup` rules exclude it so a reinstall registers a new device, SPEC §16) |
| `last_start_lat` / `last_start_lon` / `last_start_label` | Double / Double / String | — (Moscow fallback 55.7558, 37.6173, «Москва») |
| `crew_back_seats` | String `"adult,child,empty"` | `"empty,empty,empty"` |
| `crew_front_passenger` | Boolean | false |
| `crew_dog` | Boolean | false |
| `daily_km` | Int | 300 (UI switches to 500 for trips ≥ 800 km until the user changes it) |
| `daily_km_user_set` | Boolean | false |
| `budget_preset` | Int (index 0–5; 5 = не важно) | 2 (40 000) |
| `consumption` / `fuel_type` / `tank_l` | Float / String / Float | 8.0 / `ai95` / 50 |
| `start_time` | String `"HH:mm"` | `"08:00"` |
| `avoid_tolls` | Boolean | false |
| `mood` | String? | null (server default) |
| `location_rationale_shown` | Boolean | false |
| `onboarding_done` | Boolean | false |

### 11.7 Networking

- `OkHttpClient` (shared): `connectTimeout 5 s`, `readTimeout 10 s`, `callTimeout 15 s` (REST); `AuthInterceptor` (adds token; on 401 calls `POST /v1/devices` once, retries), `HeadersInterceptor` (`X-App-Version`, `X-Request-Id` UUID), `HttpLoggingInterceptor` (debug only, BASIC).
- `VerstApi` (Retrofit 3, kotlinx.serialization converter, `Json { ignoreUnknownKeys = true; explicitNulls = false }`): one suspend function per §10.2 endpoint.
- `PlanStreamClient`: separate OkHttp client derived with `readTimeout(30 s)`, `callTimeout(0)`; `EventSources.createFactory(client).newEventSource(request, listener)` wrapped in `callbackFlow<PlanStreamEvent>` (`Stage`, `Stop`, `Done(tripId, trip?)`, `Error(code, message)`); `awaitClose { eventSource.cancel() }`. A plain HTTP error before streaming is mapped to `Error` from its JSON envelope.
- Typeahead: `GeocodeRepository.suggest(q)` with `debounce(250)` + `distinctUntilChanged` + `mapLatest` in the ViewModel; 1.5 s client timeout; results shown ≤ 6.
- `ConnectivityObserver` (`ConnectivityManager.NetworkCallback` → `StateFlow<Boolean>`) drives offline plates.

### 11.8 DI (Hilt)

`@Module @InstallIn(SingletonComponent)`: `NetworkModule` (Json, OkHttp, Retrofit, VerstApi, PlanStreamClient, base URL from `BuildConfig.API_BASE_URL`), `DatabaseModule` (Room, DAOs), `DataStoreModule` (`@Prefs`, `@Secure` qualifiers), `RepositoryModule` (`@Binds` interfaces → impls), `DispatchersModule` (`@IoDispatcher`, `@DefaultDispatcher`), `ClockModule` (`Clock.systemDefaultZone()`), `AnalyticsModule` (`Analytics` interface → `AppMetricaAnalytics`; `NoopAnalytics` in tests). ViewModels: `@HiltViewModel` + `hiltViewModel()` in each `XRoute`.

### 11.9 Windshield scene (Compose Canvas)

`WindshieldScene(mode: SceneMode /* Idle, Drive, Dusk */, modifier, flyingSigns: List<SignUi> = emptyList())` in `:core-ui`, drawn in a single `Canvas` sized 0–540 dp of the 844 dp reference frame (scaled by width/390):
1. **Sky**: 5 flat bands `sky.1…5` at y 0/110/180/235/275 dp (heights 110/70/55/40/25), sun disc `sun` Ø68 dp at (236, 266) clipped by the horizon, hills: one `Path` from the canvas points (`M0 28 L40 18 …` offset by 272 dp), fill #3C3346 (add as token `hill` — see §15.2), ground `ground` from 300 dp.
2. **Road**: trapezoid from the vanishing point (195, 300) to the bottom edge (half-width 10 dp at the horizon → 230 dp at the bottom); fill `road`.
3. **Lane dashes**: perspective is computed analytically — for a dash at world depth `z` (0 = viewer, 1 = horizon), screen `y = 300 + 240 · (1 − z)^2.2`, width ∝ `(1 − z)`. A single `phase` float in [0, 1) advances by `rememberInfiniteTransition` — `animateFloat(0f, 1f, infiniteRepeatable(tween(durationMs, easing = LinearEasing)))`, `durationMs = 900` (Idle) / `450` (Drive) = SPEC "160 dp per 0.9 s / 0.45 s". Dashes are drawn at `z_i = frac(i/6 − phase)`.
4. **Roadside posts**: two posts with phases offset by 0.5 (= 1.3 s of 2.6 s); position along the perspective path `(195 ± 150·p, 300 + 260·p)`, scale `0.3 + 1.9·p`, `p = easeIn(t)` with `CubicBezierEasing(0.55f, 0f, 1f, 0.45f)` exactly as the canvas.
5. **Flying signs (Drive)**: each `SignUi` is drawn by the shared `RoadSignPainter` (same code as the `RoadSign` composable, via `DrawScope` extension) with scale `0.12 → 1.7`, translate `±230 dp, +40 dp`, 3.6 s, stagger 1.2 s, `CubicBezierEasing(0.6f, 0f, 1f, 0.5f)`; signs enqueue as `stop` SSE events arrive (max 3 visible).
6. **Frame**: A-pillars (two dark quads), roof liner (top band), drawn last; the rear-view `Mirror` and `OverheadSign` are normal composables layered above the Canvas in a `Box` (they are interactive and need semantics).
7. **Performance**: all `Path`s and `Brush`es are created once in `remember`/`drawWithCache`; per-frame work is only transforms; only the Canvas draw phase reads the animated `State` (lambda-based `graphicsLayer`/`drawBehind`) so no recomposition per frame. Target 60 fps (SPEC §6, §16); verified with a Macrobenchmark in M6.
8. **Reduced motion**: `rememberReducedMotion()` reads `Settings.Global.ANIMATOR_DURATION_SCALE == 0f` (re-read on `ON_RESUME`); when true all infinite transitions are replaced by a static frame (`phase = 0.35f`). Animations stop when the screen is not visible because `rememberInfiniteTransition` is cancelled with the composition and `LifecycleResumeEffect` pauses the Drive clock.
9. Dusk mode (Exit screen) uses the same scene with `sky` bands shifted one step darker (tokens `sky.1`–`sky.4` + `dash`) and the `TurnSignal` composable (0.9 s, 55 % on, `signal.green`).

### 11.10 Design tokens in code

`:core-ui/theme/VerstTokens.kt` is generated by hand from SPEC §6 and is the **only** place where colour literals and font sizes appear:
```kotlin
object VerstColors { val Dash = Color(0xFF141416); val DashRaised = Color(0xFF161618); val DashControl = Color(0xFF232327)
  val DashControlAlt = Color(0xFF2A2A2E); val TextPrimary = Color(0xFFF4F4F0); val TextSecondary = Color(0xFFB9B9C0)
  val TextMuted = Color(0xFF8C8C93); val SignBlue = Color(0xFF1E4FA3); val SignBrown = Color(0xFF6B3E26); val SignWhite = Color(0xFFF4F4F0)
  val AccentYellow = Color(0xFFFFD23F); val AccentRed = Color(0xFFD8402B); val SignalGreen = Color(0xFF6FD18A)
  val NaviScreen = Color(0xFF0B1218); val NaviField = Color(0xFF16222C); val NaviFieldBorder = Color(0xFF2B3D4D)
  val NaviLabel = Color(0xFF7FA6D9); val NaviLabelAlt = Color(0xFF8FA4B8)
  val Sky = listOf(Color(0xFF2B2850), Color(0xFF4E3768), Color(0xFF8E4A6B), Color(0xFFD9655A), Color(0xFFF29A5E))
  val Sun = Color(0xFFFFD99A); val Ground = Color(0xFF2C3A33); val Road = Color(0xFF3A3A3F)
  val Paper = Color(0xFFEEF2F4); val PaperLine = Color(0xFF9FB0BE); val Ink = Color(0xFF1B3FA0); val Stamp = Color(0xFF5B3FA0) }
object VerstType { val Display; val Sign; val Title; val Body; val Label; val Odometer; val Handwriting }   // TextStyle per SPEC §6, tabular nums via fontFeatureSettings = "tnum"
object VerstMotion { const val LaneIdleMs = 900; const val LaneDriveMs = 450; const val PostMs = 2600; const val FlySignMs = 3600
  const val SelectionMs = 200; const val StampMs = 500; const val TurnSignalMs = 900; val GaugeSpring = spring<Float>(dampingRatio = 0.6f, stiffness = 300f) }
```
`VerstTheme` provides them via `CompositionLocal` (`LocalVerstColors`, `LocalVerstType`); Material3 `MaterialTheme` is wrapped only for ripple/accessibility primitives with a colour scheme mapped from these tokens. A detekt custom rule (`NoColorLiteralOutsideTokens`) fails the build on `Color(0x…)` outside `VerstTokens.kt`. Fonts bundled in `:core-ui/src/main/res/font/` (`ibm_plex_sans_condensed_{400,500,600,700}.ttf`, `ibm_plex_mono_600.ttf`, `marck_script_400.ttf`, OFL; Cyrillic subset check in DES-003). Strings: `:core-ui/res/values/strings.xml` (common) + each feature's `res/values/strings.xml`, plurals via `<plurals>` (ICU rules for ru).

### 11.11 Screen notes (beyond SPEC §5)

| Screen | ViewModel inputs | Key details |
| --- | --- | --- |
| Windshield | `ReadyRouteRepository`, `DefaultsRepository`, `TripRepository.observeSaved()` | Start resolution order: last start → coarse location (`FusedLocation` is GMS — not available on all RuStore devices; use `LocationManager.getLastKnownLocation(NETWORK_PROVIDER)` [D-8]) → Moscow. Arrow from `bearing` (server) mapped to 8 arrow vectors. Shimmer ≤ 2 s, then cached/empty state |
| Navigator | `GeocodeRepository`, `RecentSearchDao`, `PlanDraftStore` | Badges Г/У/М colours per canvas (city `sign.blue`, place `sign.brown`, street `navi.fieldBorder`). Vias drag-reorder via `Modifier.draggable` long-press |
| Instruments | `DefaultsRepository`, `PlanDraftStore` | Seat cycle empty → adult → child → empty; adults = 1 + front + back adults; "≈ X ч Y мин" = `round(km / 70 × 60 / 10) × 10` min (canvas formula); days = `ceil(tripKm / km)` with `tripKm` from the ready route or straight-line × 1.25 until planned |
| Drive | `PlanStreamClient`, `TripRepository` | Steps in fixed order split → lodging → hours → fuel → cost; a step is checked when a later key arrives or on `done` |
| Road ahead | `TripRepository`, `LinkRepository`, `ExternalAppLauncher` | `LazyColumn` with stable keys = stop id; vertical road + car marker are `drawBehind`; TalkBack label per SPEC §16 |
| Waybill | `TripRepository`, `CostCalculator` | Reserve toggle recompute ≤ 100 ms locally (pure function, measured in unit test < 5 ms); stamp anim 500 ms delayed 1 s |
| Exit | `TripRepository`, `LinkRepository` | On return (`ON_RESUME` after a booking launch) show «Забронировали?»; yes → `booked_stops` |

---

## 12. Infrastructure, environments, CI/CD, release

### 12.1 Compose services

`infra/compose/app.compose.yml` (VM-A "app"):

| Service | Image (pin digest at deploy) | Ports | Volumes / notes |
| --- | --- | --- | --- |
| nginx | nginx:1.27-alpine | 80, 443 | `infra/nginx/verst.conf`, certbot volume |
| certbot | certbot/certbot:v3 | — | renew every 12 h |
| api | `ghcr.io/<org>/verst-api:<git-sha>` (python:3.12-slim base) | 8000 internal | `uvicorn verst_api.main:app --workers 4 --proxy-headers`; env from `.env` |
| jobs | same image, `python -m verst_api.jobs` | — | daily cleanup (§9.3), 180-day recheck digest to Telegram |
| postgres | postgis/postgis:16-3.4 | 5432 internal | `pgdata` volume; `shared_buffers=2GB`, `work_mem=32MB` |
| redis | redis:7.4-alpine | 6379 internal | `--maxmemory 512mb --maxmemory-policy allkeys-lru`, no persistence |
| directus | directus/directus:11 | 8055 internal | `DB_CLIENT=pg`, role `directus`; uploads volume (photos) |
| backup | prodrigestivill/postgres-backup-local:16 | — | daily 03:00 MSK, keep 14 days (SPEC §11), plus weekly copy to S3-compatible object storage in Russia |
| prometheus, grafana, glitchtip(+worker), node-exporter, postgres-exporter | pinned | internal / grafana via nginx basic auth | Telegram alert contact point |

`infra/compose/maps.compose.yml` (VM-B "maps"): `graphhopper` (israelhikingmap/graphhopper:10.x or self-built JAR image, `-Xmx20g`, graph cache volume), `photon` (Photon jar + Russia index volume, `-Xmx6g`), `martin` (ghcr.io/maplibre/martin, `russia.mbtiles`), `node-exporter`. Ports exposed only on the private network, except martin behind nginx on VM-A (`tiles.verst.app` → VM-B:3000, cache 7 days).

`infra/compose/dev.compose.yml` (developer laptop / CI): postgres, redis, api (reload), graphhopper with the **Central Federal District extract** (~400 MB PBF, `-Xmx4g`), photon with a small index. `make dev-up`.

### 12.2 VM sizing (start; Yandex Cloud or Selectel, CEO decision)

| VM | vCPU / RAM / disk | Rationale |
| --- | --- | --- |
| VM-A app | 4 vCPU / 8 GB / 100 GB SSD | API (4 workers ≈ 1.2 GB), Postgres (2 GB buffers), Directus, monitoring |
| VM-B maps | 8 vCPU / 32 GB / 200 GB SSD (SPEC §11) | GraphHopper Russia graph (~3.5 GB PBF → ~12–16 GB RAM with LM), Photon Russia index (~25 GB disk), tiles (~15 GB) |
| Build (ephemeral) | 16 vCPU / 64 GB, spot/preemptible | Weekly OSM rebuild: GraphHopper import + Photon (via Nominatim export) + Planetiler, then rsync artifacts to VM-B and blue/green container switch |

### 12.3 Environments
| Env | Where | Data | Purpose |
| --- | --- | --- | --- |
| `local` | laptop / sandbox | fixtures (planner), dev compose | development; **sandbox = planner only** |
| `ci` | GitHub Actions | ephemeral PostGIS + fixtures; GraphHopper not used (fakes) | tests |
| `staging` | VM-A' small (2 vCPU / 4 GB) + shares VM-B maps | copy of `core` from prod nightly (no `app` data) | app debug builds, contract tests vs real routing, golden trips "real mode" |
| `prod` | VM-A + VM-B | live | release |

Config by environment variables (`verst_api/settings.py`, `pydantic-settings`): `VERST_ENV`, `DATABASE_URL`, `REDIS_URL`, `GRAPHHOPPER_URL`, `PHOTON_URL`, `GLITCHTIP_DSN`, `TP_MARKER`, `LOG_LEVEL`, `PLAN_TIMEOUT_S=25`, `RATE_PLAN_PER_HOUR=30`.

### 12.4 CI pipeline (GitHub Actions)

`backend.yml` (on PR and main):
1. **planner** (no network deps; runs even if PyPI is blocked): `python3 -m unittest discover -s backend/planner -t backend/planner -v`; `ruff check backend/planner`; `mypy --strict backend/planner/verst_planner`; coverage via `python -m trace` is not enough → once PyPI is available, `coverage run -m unittest` with gate **≥ 85 % of `verst_planner`** (SPEC §17).
2. **api**: install `backend/api` deps (locked `requirements.lock` with hashes), start `postgis/postgis:16-3.4` + `redis:7.4` services, `alembic upgrade head`, downgrade/upgrade check, `pytest backend/api` (unit + OpenAPI contract via `schemathesis` against the app with fake adapters), `test_schema_matches`.
3. **golden**: `cd backend/planner && python3 -m unittest tests.golden.test_golden -v` (already in 1; separate job on main that also runs "real mode" against staging GraphHopper nightly, reporting drift but not failing).
4. **image** (main only): build & push `verst-api:<sha>`, Trivy scan (fail on CRITICAL).
5. **deploy-staging** (main): SSH + `docker compose pull && up -d` + migrations + smoke (`/readyz`, plan G01 via API).
6. **deploy-prod**: manual approval on a tag `api-v*`.

`android.yml`: `./gradlew ktlintCheck detekt lint testDebugUnitTest verifyPaparazziDebug checkModuleGraph assembleDebug` + Room migration tests; artifacts: debug APK. `release-android.yml` on tag `android-v*`: `bundleRelease` + `assembleRelease` signed with the upload key from GitHub secrets (`VERST_KEYSTORE_B64`, passwords), mapping file upload to AppMetrica, attach AAB/APK to the release, upload to RuStore via the RuStore Public API (draft → manual "submit for review" in RuStore Console). Version: `versionCode = <run number>`, `versionName = <tag>`.

### 12.5 Release to RuStore
1. Closed testing track (≥ 30 testers) built from `android-v0.x` tags; submitted 2 weeks before launch (SPEC §19).
2. RuStore listing in Russian, privacy policy URL `https://verst.app/privacy`, content rating, screenshots from Paparazzi golden images.
3. Production release = promote the approved beta build; staged rollout 20 % → 100 % after 48 h with crash-free ≥ 99.5 %.
4. `min_app_version` in `/v1/config` forces an update screen for incompatible clients.

---

## 13. Testing strategy (SPEC §17)

### 13.1 Layers

| Layer | Location | Tooling now (sandbox) | Tooling after network | Gate |
| --- | --- | --- | --- | --- |
| Planner unit | `backend/planner/tests/unit/test_*.py` | stdlib `unittest` | same (+ `coverage.py`) | all green; coverage ≥ 85 % of `verst_planner` (sandbox: `tools/stdlib_coverage.py`, §13.5) |
| Golden trips | `backend/planner/tests/golden/` | `unittest`, fake adapters | + nightly "real mode" vs staging GraphHopper/PostGIS (report only) | expectations + exact snapshots |
| Cost recompute contract | `backend/planner/tests/contract/` | `unittest` | + Kotlin JUnit runs the same JSON | identical results |
| Layering | `backend/planner/tests/test_layering.py` | `unittest` + `ast` | same | no non-stdlib imports |
| Static | — | `ruff check`, `mypy --strict` (preinstalled) | same | 0 errors |
| API unit/contract | `backend/api/tests/` | — | pytest, httpx, schemathesis, PostGIS service | OpenAPI contract green; SSE event order test |
| DB | `backend/api/tests/db/` | — | pytest + PostGIS container | migrations up/down; triggers (lodging count, auto-hide) |
| Android unit | `android/*/src/test` | — | JUnit4, Turbine, coroutines-test, Robolectric | ViewModels, reducers, `CostCalculator` contract, Room migrations |
| Android UI | `android/*/src/test` (Paparazzi), `src/androidTest` | — | Paparazzi screenshots per screen state; Compose UI tests for navigation | diff ≤ 0.1 %; matches canvas within 4 dp (DES-005 reference images) |
| Devices / field | manual | — | 4 devices + 3 field trips | SPEC §17 checklist |

### 13.2 Golden-trip fixture format

One JSON file per case in `backend/planner/tests/golden/cases/`, file name `Gnn_<slug>.json`:

```jsonc
{
  "id": "G03",
  "slug": "msk_volgograd_dog_child",
  "titleRu": "Москва → Волгоград, 500 км/день, с собакой и ребёнком",
  "world": "central_russia_v1",                  // fixtures/worlds/<world>.json
  "clock": "2026-10-23T09:00:00+03:00",          // FixedClock
  "config": {},                                  // optional PlannerConfig overrides (deep-merged)
  "input": {                                     // exactly TripInputDTO (camelCase, §10.3)
    "origin": {"lat": 55.7558, "lon": 37.6173, "label": "Москва"},
    "destination": {"lat": 48.7080, "lon": 44.5133, "label": "Волгоград"},
    "crew": {"adults": 2, "children": 1, "dog": true, "childAges": [5]},
    "dailyKm": 500, "budget": 60000, "startAt": "2026-10-24T08:00"
  },
  "expect": {
    "error": null,                               // or "UNREACHABLE" | "TOO_SHORT" | "INVALID_INPUT" (then nothing else is checked)
    "days": 2, "nights": 1,
    "kmRange": [940, 1010],
    "overnightTownIds": ["t_tambov"],            // ordered by night
    "overnightFallbacks": ["none"],
    "warnings": [],                              // exact multiset of codes
    "mustIncludePlaceIds": [],                   // anywhere in the trip
    "mustExcludePlaceIds": ["pl_kotovsk_hotel_1"],
    "stopKindsPerDay": {"1": {"fuel": [1, 1]}},  // [min, max] counts
    "costTotalRub": {"value": 52000, "tolerancePct": 5},
    "costLinesRub": {"fuel": {"value": 7400, "tolerancePct": 5}},
    "invariants": ["all"],                       // or a list of names from §13.3
    "costWorkings": [                            // hand calculation behind costTotalRub (required when costTotalRub is set)
      "fuel: 975 km × 8 / 100 × 61.5 ≈ 4 797 → 4 800", "lodging: 1 night × 1 room × 5 500 = 5 500", "…"]
  }
}
```
- `expect` is authored by hand from the world data, never copied from engine output; `costWorkings` documents the arithmetic so the Manager can re-check it (±5 % for cost per SPEC §17).
- `snapshots/Gnn_<slug>.json` is the full `codec.plan_to_json(plan)` output with `id` replaced by `"trp_golden"`. The test compares exactly; on mismatch it writes `snapshots/Gnn_<slug>.actual.json` and prints a unified diff of the first 80 lines. Snapshots are regenerated only with `cd backend/planner && VERST_GOLDEN_UPDATE=1 python3 -m unittest tests.golden.test_golden` (alias `make golden-update`) and committed with a reviewed diff.
- Each case also runs the stream once with `ListSink` and asserts the event contract (§13.3 `events`).

### 13.3 Invariants (`tests/golden/invariants.py`, applied to every golden plan when `"all"`)

| Name | Check |
| --- | --- |
| `day_cap` | every non-template day: `day.km ≤ 1.05 × dailyKm` (US-06) |
| `dog_lodging` | crew.dog ⇒ every selected hotel and every `hotelOptions` entry has `dogs_allowed` (US-05, §17) |
| `monotonic_time` | per day: `arriveAt ≤ departAt < next.arriveAt`; days strictly increasing |
| `monotonic_km` | `kmAt` non-decreasing; `kmFromPrev ≥ 0`; Σ day km = trip km |
| `hours_open` | every sight's `[arriveAt, departAt]` is covered by its opening hours |
| `lunch_window` | each lunch stop arrives in 12:00–14:30 local |
| `fuel_range` | simulated tank never drops below 0 (fuel stops at their km refill to full) |
| `unique_places` | no `placeId` used twice as a stop |
| `alternatives` | each alternative: different place, same kind, `|Δarrive| ≤ 45` min, ≤ 3 per stop; `replaceable == (len > 0 or kind in replaceable kinds)` |
| `cost_sum` | lines are multiples of 10; total multiple of 100; total = round100(Σ lines + reserve·on); per person rule |
| `cost_recompute` | `recompute(units, crew, reserveOn, budget, {})` == `cost` (server and offline agree) |
| `reasons` | every overnight has non-empty `reason` and ≥ 1 candidate (unless `no_hotel` with empty window); every auto stop has a reason |
| `determinism` | planning the same input twice gives identical JSON |
| `events` | first event is `stage split`; progress non-decreasing; one non-provisional `stop` event per final stop, in order |
| `russian_text` | every `*_ru`/reason/formula string contains no Latin letters except road refs and units |
| `break_spacing` (§16.2) | consecutive breaks (stops with dwell ≥ 15 min, day start) are ≥ `rest.min_gap_min` driving minutes apart, except lunch/sight/overnight following a user or template stop |
| `rest_reason` (§16.2) | the `drive` value in a `rest.generic` reason equals driving since the previous break ±15 min |
| `lunch_present` (§16.2) | a day overlapping 12:00–14:30 has a lunch stop unless the case lists it in `expect.noLunchDays` |
| `alternatives_note` (§16.6) | every replaceable stop has ≥ 2 alternatives or a non-empty `alternativesNote` |
| `formula_km` (§16.7) | the km in the fuel formula equals `TripPlan.km` |

### 13.4 The 20 golden trips

Worlds: `central_russia_v1` (Moscow hub: М-1…М-12, Р-22, Golden Ring, Tula, Kazan, Volgograd corridors; ≈ 120 nodes, 60 towns, 250 places; synthetic but geographically plausible coordinates and distances within ±5 % of real road km) and `edge_cases_v1` (a synthetic «Тестовая область» corridor for failure modes). Further worlds are added in Sprint 2.

| ID | Case | World | Key expectation | Sprint |
| --- | --- | --- | --- | --- |
| G01 | Москва → Ярославль → Москва (round trip), 2 adults, 300 km/day | central | 2 days, overnight Ярославль, no warnings | 1 |
| G02 | Ready route «Золотое кольцо», 2 adults + 1 child + dog, 300 km/day, budget 40 000 | central | 3 days, nights Ярославль, Суздаль (`template`), total = hand calculation from world prices ±5 % (5 meals per SPEC §8 rules; the canvas «7 приёмов» example is not reproducible, see D-16) | 1 |
| G03 | Москва → Волгоград, 500 km/day, 2 adults + child (5) + dog | central | 2 days, overnight Тамбов (dog-friendly), decoy town without dog hotels excluded, 1 evening fuel stop | 1 |
| G04 | Москва → Казань by М-12, `just_drive`, 1 adult, 900 km/day | central | 1 day, no sights, 1 fuel, rests every 3 h, tolls line > 0 | 1 |
| G05 | Тестовск → Конечный, dog, only lodging in corridor lacks `dogs_allowed` | edge | warning `NO_LODGING`, fallback `no_hotel`, no hotel selected, lodging line uses default price | 1 |
| G06 | Москва → Казань, `avoidTolls`, 2 adults, 450 km/day | central | route via М-7, tolls = 0, overnight Нижний Новгород | 1 |
| G07 | Ready route «Тула · Ясная Поляна», 2 adults + 2 children, 300 km/day | central | 2 days (round 400 km), night Тула; playground/kids_menu preferred | 1 |
| G08 | Москва → Владимир (via) → Суздаль, `more_stops`, 2 adults, 300 km/day | central | 1 day, via honoured, ≤ 4 sights, all open | 1 |
| G09 | Edge: destination 2.5 km off any road | edge | error `UNREACHABLE` | 1 |
| G10 | Edge: A → B 12 km | edge | error `TOO_SHORT` | 1 |
| G11 | Edge: sparse fuel corridor | edge | warning `FUEL_GAP` | 1 |
| G12 | Edge: day over budget with long fixed stops | edge | re-run drops sights, then `DAY_OVER_BUDGET` | 1 |
| G13 | Москва → Санкт-Петербург, М-11, 400 km/day | world `nw_russia_v1` | 2 days, M-11 tolls day tariff | 2 |
| G14 | Санкт-Петербург → Выборг (SPEC), 1 day | nw | 1 day, sights only | 2 |
| G15 | Казань → Пермь (SPEC), 400 km/day | `volga_ural_v1` | 2 days, OSM-only places flagged `verified=false` → `UNVERIFIED_PLACES` | 2 |
| G16 | Москва → Рускеала (≈ 1 050 km), dog, 400 km/day | nw | 3 days, 2 dog-friendly nights | 2 |
| G17 | Ready route «Нижний Новгород → Казань» | central | template fit check rejects when dailyKm = 200 → engine split | 2 |
| G18 | Москва → Воронеж, М-4, start 22:00 | central | night toll tariff used | 2 |
| G19 | Москва → Самара, 600 km/day | volga | crosses into `Europe/Samara`; local times per day `tz` | 2 |
| G20 | Екатеринбург → Пермь (Navigator canvas «другие») | volga | non-Moscow start, no ready routes near; trip still planned | 2 |

G01–G12 are Sprint 1 (G01–G05 are the Manager's mandatory set). SPEC §17 counts "20 golden trips"; G09–G12 are failure-mode trips and count toward the 20.

### 13.5 Coverage in the sandbox
`backend/planner/tools/stdlib_coverage.py` runs the unittest suite under `sys.settrace`, counts executed lines of `verst_planner/**/*.py` against executable lines (`ast` statements, excluding `if TYPE_CHECKING:` blocks, `...` bodies of Protocols and lines marked `# pragma: no cover`), prints a per-file table and exits 1 below `--fail-under 85`. Replaced by `coverage.py` once PyPI is reachable (numbers must agree within 2 points).

---

## 14. Sandbox vs. network

| Component | Build now (sandbox) | Verify now | Needs network for | Blocked work items |
| --- | --- | --- | --- | --- |
| `verst_planner` (domain, geo, hours, pipeline, cost, explain, codec, CLI) | ✅ stdlib only | ✅ `unittest`, `ruff`, `mypy --strict`, stdlib coverage | `coverage.py` (optional) | — |
| Fake adapters + worlds + golden trips G01–G12 | ✅ | ✅ | — | — |
| Cost recompute contract JSON | ✅ | ✅ (Python side) | Kotlin side needs Gradle deps | DEV-A06 |
| Plan JSON contract example, share-text fixtures | ✅ generated by CLI | ✅ | — | — |
| `verst_api` FastAPI app | ⚠️ code can be written; starlette/uvicorn/pydantic exist, **FastAPI, SQLAlchemy, psycopg, redis, httpx, alembic absent** | ❌ | PyPI | DEV-B01…B05 (Sprint 2) |
| SSE bridge prototype | ✅ on plain Starlette (`StreamingResponse`) with fakes — optional spike DEV-020 | ✅ `uvicorn` + `curl -N` | — | — |
| SQL DDL `0001_initial.sql` | ✅ written | ⚠️ `psql` client exists, no server; Docker present but images need registry | Docker Hub (postgis image) | DEV-B02 |
| Alembic migrations | ✅ written | ❌ | PyPI | DEV-B02 |
| GraphHopper / Photon / martin images & Russia extract | ✅ scripts and configs | ❌ | Docker Hub, Geofabrik, Maven | INF-001…003 |
| Directus | ✅ snapshot/roles doc | ❌ | Docker Hub/npm | ADM-001 |
| Android project (Gradle, Compose, Hilt, Room) | ⚠️ files can be written | ❌ (Gradle cannot resolve AGP/Kotlin plugins; no Android SDK) | Google Maven, Maven Central, Gradle plugin portal, Android SDK | DEV-A01…A07 |
| Fonts (IBM Plex, Marck Script) in the APK | ❌ | ❌ | Google Fonts / GitHub download | DES-003 |
| CI workflows | ✅ YAML | ⚠️ `actionlint` absent; run on GitHub | GitHub | — |
| Real routing quality, p95 latency | ❌ | ❌ | maps VM | M1/M4 |

---

## 15. Decision log, SPEC deviations, traceability

### 15.1 Decisions where SPEC left room

| ID | Decision | Default |
| --- | --- | --- |
| D-1 | Mood default when not given | `calm` if children > 0 (SPEC) else `more_stops` (balanced; `just_drive` only on explicit choice) |
| D-2 | `NO_LODGING` transport | `warnings[]` inside a successful trip; never an HTTP error |
| D-3 | Ready-route template fit | template nights used if every template day ≤ 105 % × dailyKm and number of days ≤ ceil(total / (0.9 × dailyKm)) |
| D-4 | Overnight fallback chain | F1 window 70–105 % → F2 widened 40–130 % (capped at 105 % of dailyKm) → F3 one extra day → F4 town/road point without hotel; F2–F4 raise `NO_LODGING` |
| D-5 | Dinner placement | dinner is costed at the overnight town, not inserted as a separate stop |
| D-6 | Meal counting | lunch on days overlapping 12:00–14:30; dinner each night; breakfast from hotel unless `breakfast_included=false` |
| D-7 | Android applicationId | `app.verst` (domain `verst.app` is a CEO open question) |
| D-8 | Location source | `LocationManager` network provider (no Google Play Services dependency for RuStore devices) |
| D-9 | Detour model | `2 × lateral × 1.3` at 40 km/h + 2 min access (+5 min motorway exit); config |
| D-10 | Drive-time factor | routing free-flow minutes × 1.10 (traffic/caution), config; calibrated in field trips |
| D-11 | Unsaved trips retention | 30 days server-side; 1 local slot |
| D-12 | Money arithmetic | `Decimal`, ROUND_HALF_UP; lines to 10 ₽, total and per person to 100 ₽ |
| D-13 | Tolls when `avoidTolls` impossible | route kept, toll costed, warning `TOLLS_UNAVOIDABLE` |
| D-14 | Children ages | optional `childAges`; unknown age counts as ≥ 7 (food weight 1, child ticket) — conservative estimate |
| D-15 | Rooms rule | `ceil(adults / 2)` rooms (SPEC), children share; dog adds no cost in MVP |
| D-17 | Rest placement (Q-A, review 2026-10-23) | Rests are planned last, between existing breaks; candidates need `detour_min ≤ 10`; breaks ≥ 60 driving minutes apart; an existing fuel stop in the window is upgraded to coffee (§16.2) |
| D-18 | Lunch after sights (Q-B) | lunch planned before and again after sights; a family day overlapping 12:00–14:30 drops optional sights before it drops lunch (§16.2) |
| D-19 | Alternatives (Q-C) | any pool member within ±45 min at any position; offline exactness via a per-alternative day patch; < 2 → explicit note (§16.6) |
| D-20 | Day time budget (Q-E) | the budget caps optional content; `DAY_OVER_BUDGET` only when the day exceeds `max(budget, mandatory minutes)` (§16.5) |
| D-21 | Template vias | routing waypoints only, no stop rows (§16.3) |
| D-16 | Meals vs. Waybill canvas (Q-4, decided by Manager 2026-10-23) | Follow SPEC §8: breakfast at the hotel included, lunch + dinner on the road, first day after breakfast at home → 5 meals for the 3-day Golden Ring; the canvas «7 приёмов» example is illustrative only and is corrected by DES-004 |

### 15.2 SPEC deviations and extensions (for CEO/Manager visibility)

| # | Item | Why |
| --- | --- | --- |
| X-1 | Added `core.region` (geometry + tz) and `core.app_config` tables | needed for fuel-by-region, local times per stop (SPEC §12), remote config/templates (SPEC §7.5, §10) |
| X-2 | `ready_route.points` / `suggested_nights[]` normalised into `core.ready_route_point` (`role` via/stop/night); added `slug`, `km_sign`, `ring`, `round_trip` | FK integrity; SPEC §7.6 rings and sign km |
| X-3 | `place` added `breakfast_included`, `osm_id`, `sponsored`, `hidden_reason`, `created_at/updated_at`; `town` added `name_prep_ru`, `osm_id`, `status` | SPEC §8 breakfast rule, §9 import, §14 sponsored, Russian prepositional case in reasons |
| X-4 | `trip` added `engine_state`, `engine_version`, denormalised `title_ru/km/days`, `saved_at`; `trip_stop` added `stop_id`, `town_id`, `tz` | replace/patch without re-routing; listing; local times |
| X-5 | `device.token_hash`, `revoked_at` | anonymous token auth (ADR-0007) |
| X-6 | Endpoints `GET /v1/links/excursion`, `POST /v1/pro-waitlist`, `GET /v1/shared/{slug}`, `/healthz`, `/readyz`, `/metrics` | SPEC §14 excursions & waitlist, §5.6 share deep link, ops |
| X-7 | SSE `done` carries the full trip in addition to `tripId`; extra `stage` with key `split` for "Прокладываем дорогу" | saves a round trip; first event ≤ 1 s |
| X-8 | `TripInput` adds `reserveOn`, `simplify`, `crew.childAges` | SPEC §5.4 «Упростить маршрут», §8 child rules |
| X-9 | Errors add `UNAUTHORIZED` 401, `NOT_FOUND` 404, `LIMIT_REACHED` 409, `INTERNAL` 500 | completeness |
| X-10 | Design token `hill` #3C3346 used by the canvas but missing from SPEC §6 | canvas is the visual source of truth; to be added to SPEC §6 (DES-001) |
| X-12 | Warning `STOP_CLOSED`; DTO fields `alternativesNote`, `dayPatch`, `reasons.overnights[].fallback`; port method `PriceRepository.defaults_as_of()` | review amendments §16 |
| X-11 | Python 3.12 target, but sandbox verification on 3.13; the planner must run on both (no 3.13-only syntax) | environment |

### 15.3 Traceability (SPEC → design)

| SPEC | Requirement | Design element |
| --- | --- | --- |
| 7.1 | Input fields and rules | `TripInput`, `NormalizedInput` (§4.3); `normalize_input` (§6.2); `TripInputDTO` (§10.3) |
| 7.1 | `roundTrip` default, `mood` default, `startAt` default | `normalize_input` (§6.2), D-1 |
| 7.2.1 | Snap ≤ 2 km, `UNREACHABLE` | `resolve_points`, `build_base_route` (§6.2), `Unreachable` (§4.8), `snap_max_km` |
| 7.2.2 | Base route with avoidTolls, polyline, segment distance/duration, road refs | `RoutingPort.route`, `Route`, `RouteDetail` (§4.5, §5.1); `GraphHopperRouting` (§5.3.1) |
| 7.2.3 | Corridor 15 / 5 (motorway fuel/rest) / 25 km, `kmAt`, detour | `build_corridor`, `PolylineIndex.project_all` (§6.3), `corridor_km`, `detour` config |
| 7.2.4 | Day split N = ceil, even targets, template nights ±10 % | `split_days`, `template_fits` (§6.4), D-3 |
| 7.2.5, 7.3 | Overnight 70–105 % window, score formula, ties | `choose_overnights`, `try_split`, town score (§6.5), `overnight_score` config |
| 7.2.6 | Fuel usable range, < 20 % trigger, next 40 km, coincide ≤ 2 km | `plan_fuel` (§6.7), `fuel` config |
| 7.2.7 | Rest every R h by mood, playgrounds, dog walk | `plan_rests`, `rest_score` (§6.8), `rest_interval_min` |
| 7.2.8 | Lunch 12:00–14:30, dinner at overnight, kids_menu | `plan_meals` (§6.8), D-5, D-6 |
| 7.2.9 | Sights fill to 9 h / 10 h, opening hours, just_drive none | `plan_sights` (§6.9), `hours.py`, `day_budget_min` |
| 7.2.10 | Schedule from durations + dwell; one re-run dropping lowest sights | `schedule_day` (§6.6), `schedule_with_rerun` (§6.10) |
| 7.2.11 | 2–3 alternatives within ±45 min with Δ time, Δ cost | `build_alternatives` (§6.11), `Alternative` (§4.7) |
| 7.2.12 | Cost model | `compute_cost` (§7) |
| 7.2.13, 7.5 | Reason templates in config | `ReasonTemplates`, `reasons.ru.json`, `core.app_config['reasons_ru']` (§8.1) |
| 7.4 | Dwell defaults | `dwell_min` config (§5.4), `schedule_day` |
| 7.6 | Ready routes within 50 km of hub, rings, sign km | `ready_routes_near`, `core.ready_route` (`ring`, `km_sign`), bearing8 (§6.12, §9.2) |
| 7.7 | p95 < 10 s, SSE `stage/stop/done/error`, 24 h route cache | events (§8.3), SSE (§10.4), `CachedRouting` (§5.3.1), metrics (§10.5) |
| 8 | Six lines with formulas and data sources | `CostLine`, table §7.1 |
| 8 | Fuel by region | region attribution (§7.1), `core.region`, `core.region_price` |
| 8 | Tolls day/night, class 1 | `TollRepository`, `core.toll_segment`, §7.1 |
| 8 | Lodging rooms = ceil(adults/2) | §7.1, D-15 |
| 8 | Food people × meals × check; under-7 = 0.5 | §7.1, D-6, D-14 |
| 8 | Tickets adult/child | §7.1 |
| 8 | Reserve 10 % toggle, rounding 10 / 100 ₽, per person | §7.2, D-12 |
| 8 | Budget remaining, overspend hints | §7.2 `hint_keys`, §8.1 hints |
| 8 | Local recompute with unit prices | `CostUnits` (§7.4), `recompute` (§7.3), Android `CostCalculator` (§11.2) |
| 8 | `asOf` freshness | `CostLine.as_of`, `prices_as_of` (§7.4) |
| 9 | Entities place, town, ready_route, region_price, toll_segment, trip, trip_stop, device, feedback | DDL §9.2 (one table each; X-1…X-5) |
| 9 | Closed tag list | `Tag` enum (§4.1), `core.allowed_tags()` CHECK (§9.2) |
| 9 | Curation: draft/live, verified_at, 180-day re-check | `place.status`, `place_live_verified` CHECK, `core.place_recheck_due` view, jobs digest (§9.2, §12.1) |
| 9 | Hide after 2 `closed` reports | `app.feedback_autohide` trigger (§9.2) |
| 9 | Outside curated regions: «не проверено», never dog-friendly without info | `verified=false` on `source=osm`, `sight.osm` reason, dog filter rule (§6.5) |
| 12 | All 15 endpoints | §10.2 table (+ X-6) |
| 12 | Plan response shape | `PlanResponse` (§10.3), `codec.plan_to_json`, `plan-response.example.json` |
| 12 | SSE events | §10.4 |
| 12 | Error codes and messages | §10.6 |
| 12 | Rate limit 30 / device / hour | §10.5, §10.8 |
| 12 | Local times + `tz` per day | `DayResult.tz`, `ScheduledStop.tz` (§4.7), §6.6 |
| 13 | Offline storage | Room schema (§11.5), DataStore (§11.6), pending ops (§11.4) |
| 16 | Startup, 60 fps, reduced motion, privacy, rounding coords in logs | §11.9, §11.10, §9.3, §10.8 |
| 17 | Unit ≥ 85 %, 20 golden trips, contract tests | §13 |

### 15.4 Open questions for the CEO (each with the default the team proceeds with)

| ID | Question | Default if no answer |
| --- | --- | --- |
| Q-1 | When will package registries / Docker Hub / Geofabrik be reachable from the dev sandbox? | Sprint 1 = planner only; Sprint 2 (API, DB, Android, maps) starts the day access is enabled. Needed: PyPI, Maven Central, Google Maven, Gradle Plugin Portal, Docker Hub, ghcr.io, download.geofabrik.de, GitHub releases (fonts), Android SDK repository |
| Q-2 | Domain and package name | `verst.app` (`api.`, `admin.`, `tiles.` subdomains), Android `applicationId = app.verst` |
| Q-3 | Hosting provider | Selectel (2 VMs per §12.2, Moscow region); Yandex Cloud is equivalent for the design — only the backup target changes |
| Q-4 | ~~Meals rule vs. canvas «7 приёмов»~~ | **Decided** → D-16 (follow SPEC §8, 5 meals) |
| Q-5 | Default mood for adults-only trips | `more_stops` (D-1) |
| Q-6 | Ask children's ages in the Instruments mirror? | Not in MVP UI; API accepts optional `childAges`; unknown age counts as ≥ 7 (conservative cost) |
| Q-7 | Travelpayouts marker/program ids | Until provided, partner links open unwrapped (no attribution) and are logged; booking UX unchanged |
| Q-8 | Keep «Пример расчёта» wording until the 3 field trips confirm ±15 % | Yes (copy key `waybill.footnote` switches by feature flag `cost_confirmed`) |

---

## 16. Sprint 1 review amendments (2026-10-23)

These amendments come from the tech-lead review of DEV-001…021. They take precedence over the sections that point here.

### 16.1 Approved implementation deviations (from `docs/dev-notes.md`)

| # | Deviation | Verdict |
| --- | --- | --- |
| 1 | `geo` may import `domain`; `Corridor` lives in `pipeline` | Approved (§3.1 rule 2 amended) |
| 2 | Model extensions: `NormalizedInput.tz`; `PlannedStop.litres/coffee`; `OvernightChoice.nearest/nearest_town/region_code/detour_km/detour_min`; `Alternative.units`; `HotelPrice.breakfast_included`; `CostUnits.as_of/mood_just_drive`; `CostResult.hints_ru`; `OvernightReason.fallback`; `EngineState.days/candidates/rerun/town_kms` and `StopState` | Approved. `EngineState` is server-only; budget: ≤ 400 KB JSON for a 1,500 km trip (test added, §16.9) |
| 3 | Non-template Russian strings in `resources/strings.ru.json` | Approved |
| 4 | `pipeline → cost` forbidden; per-stop cost injected through `PlanContext.stop_cost`; `CostInput` built in `engine.py` | Approved. `engine.py` must use a public `PlanContext.region_info(code)` instead of `ctx._region_by_code` |
| 5 | Stage signature changes | Approved (§6.1 amended) |
| 6 | Alternatives keep neighbours and place type; `shift_min` = arrival shift of the next stop | **Rejected**, replaced by §16.6 |
| 7 | Fixed template stops placed with `PolylineIndex.nearest_in_range` | Approved |
| 8 | `adults + children ≤ 8` (Manager OI-07), vias rejected with a ready route, `N > max_days` → `InvalidInput("dailyKm","too_many_days")` | Approved (§6.2) |
| 9 | М-4 toll-free in `central_russia_v1` | Approved for Sprint 1; G18 (Sprint 2) adds the М-4 segments |
| 10 | No `docs/design/.gitkeep` | Approved |
| 11 | Copy review R-1…R-4; formulas «8 л/100», settings/Drive «8,0», prices with kopecks | Approved (§7.1 amended) |
| — | Other recorded decisions: hours semantics (closing minute closed, `covers` accepts end == closing); fake snapping rule; one toll hit per pass; F3 marks the first failing day; template night without passing hotel; via at the overnight town merged into it; rest clock on driving minutes | Approved, except the template night case (superseded by §16.4) |

### 16.2 Breaks, rests and lunch (replaces the rest part of §6.8; D-17, D-18)

Execution order per plan (and in the single re-run): **6 fuel → 8 lunch → 9 sights → 8b lunch for days still without one → 7 rests → 10 schedule/re-run → final repair (§16.5)**.

*Breaks* are the day start and every stop with `dwell_min ≥ break_min_dwell` (15): sights, lunch, coffee fuel stops, rests, vias.

```
plan_rests(day):                                   # runs after lunch and sights
  R = rest_interval_min[mood]; G = rest.min_gap_min (60)
  loop:
    clock = DriveClock.of(day)                     # driving minutes incl. detours, no dwell
    find the first gap between consecutive breaks b0, b1 (b1 = day end if none) with drive(b0→b1) > R
    if none: break
    x = km where drive since b0 = R
    if drive(x → day end) < min_remaining_drive_min: break
    admissible(c) = c in rest pool, unused, inside the day, c.detour_min ≤ rest.max_detour_min (10),
                    drive(b0 → c) ≥ G and drive(c → b1) ≥ min(G, drive(b0 → b1) − R)
    1. an existing FUEL stop f with drive(b0→f) ∈ [R − 60, R + 15] and not coffee:
         upgrade f to coffee (dwell fuel_coffee = 15) if f has cafe_at_fuel → continue
    2. cands = admissible with drive(b0→c) ∈ [R − 30, R]; else ∈ [max(G, R − 60), R + 15]
    3. no cands → virtual break at x (no stop), continue
    insert argmax rest_score (tie: closer to R, then id)
```
- The rest pool is unchanged (§6.8). A short sight used as a rest keeps its own reason (`sight.default`).
- `rest.generic` gets `drive` = driving since `b0`, rounded to 15 min.

Sights and the rest reserve: `day_ok(day)` (stage 9 and the lunch probes) evaluates the budget on a **copy** of the day after running `plan_rests` on it, so sights can never push rests out of the budget. Runtime gate: the 1,500 km perf test stays < 1.0 s.

Lunch 8b: for each day overlapping the lunch window without a lunch stop, run the lunch selection of §6.8. If no candidate is feasible and the day has non-fixed sights, drop sights in ascending `sight_score` (tie: later km) one at a time and retry, until a lunch fits or no droppable sight is left. A missing lunch is acceptable only when the day's corridor has no feasible food place at all. Dinner and breakfast stay cost-only (D-5).

### 16.3 Vias (D-21)

- Ready-route `via` points: routing waypoints only. No `VIA` stop, no dwell, no row. The towns appear through their sights, lunch and overnights.
- User vias (Navigator «+ заехать по пути»): `VIA` stop, dwell `dwell_min.via` (30), sign `city`, reason `via.user`, never replaceable.

### 16.4 Template nights with the crew filter

`template_fits` = the §6.4 rule **and** every night town has ≥ 1 lodging passing `passes(h, crew)`. If it fails, the engine split (§6.5) runs and may still pick the template town. The `template_no_hotel` path is removed.

### 16.5 Day budget, final repair, `STOP_CLOSED` (D-20)

- `mandatory_min(day)` = driving + detours + dwell of all `auto` stops (fuel, coffee, rests, lunch). The time budget limits optional content: sights added by stage 9 must fit `day_budget_min[mood]`.
- A day is over budget iff `duration > max(day_budget_min[mood], mandatory_min) + 1e-6`. It can then only be caused by fixed or user stops (template sights, user vias). In that case raise `DAY_OVER_BUDGET` and set `DayResult.over_budget = true`. A long drive the user asked for through `dailyKm` (G04) raises no warning.
- **Final repair**, after the re-run (or after the first pass when there is no re-run), one pass per day in stop order:
  1. a non-fixed sight not open for its whole visit → drop it and reschedule;
  2. a fixed sight not open → drop it, warning `STOP_CLOSED` (`name`), reschedule;
  3. a lunch out of window → drop it, then run lunch 8b once for that day;
  4. run `plan_rests` for the day again (breaks may have moved).
  After the repair, invariants `hours_open`, `lunch_window` and `break_spacing` must hold by construction.
- `STOP_CLOSED` is a warning in `warnings[]`, never an HTTP error. The message comes from `warning.STOP_CLOSED`.

### 16.6 Alternatives (replaces §6.11; D-19)

```
for each replaceable stop s (kinds SIGHT, FOOD, FUEL, REST; not fixed; template sights excluded):
  pool = the stage pool of s: rest pool for stops inserted by stage 7 (rests, coffee fuel, short sights),
         food for lunch, fuel for range fuel stops, sights for stage-9 sights
  for c in pool by stage score desc, unused anywhere in the trip, inside the day:
      day' = day with s removed and c inserted at its km position (ANY position; order may change)
      re-plan nothing else; schedule day'
      keep c iff |arrive'(c) − arrive(s)| ≤ 45 min (SPEC 7.2.11)
             and every sight of day' open, lunch in window, duration' ≤ max(budget, duration(day)),
             fuel: every gap between fills ≤ full range (skip when FUEL_GAP)
      stop after 3 kept alternatives
  alternatives_note_ru = None if ≥ 2 kept; else render `alternatives.none` (0) / `alternatives.one` (1)
```
- `Alternative.day_patch: tuple[StopTime, ...]`, `StopTime(stop_id: str, seq: int, arrive_at, depart_at, km_from_prev: int)`. It covers every stop of the day in the new order, with the alternative carrying the replaced stop's id. Offline replace applies the patch verbatim: no client-side shift arithmetic. `shift_min` stays for display only: the arrival shift of the first stop after the replaced one in the new order (0 if none).
- `delta_min` = change of the day's end time. `delta_rub` = `round_to(Δ stop cost excl. fuel stops + Δ detour_km × consumption / 100 × price(region of c), 10)`. Fuel stops have Δ stop cost 0: the fuel line is distance-based, so only the detour changes it. Test: for every alternative of every golden trip, `recompute(units, replaced={s: alt.units})` changes Σ of the 5 base lines by `delta_rub ± 10`.
- `Planner.replace_stop` reproduces exactly the day of the alternative's `day_patch` (test: equal arrive/depart/km for all stops). It then recomputes that day's alternatives.
- Coverage gate (golden, central world, moods calm/more_stops: G01, G02, G03, G06, G07, G08): ≥ 70 % of replaceable stops have ≥ 2 alternatives. The world fixture is enriched if needed (more rest areas, cafés and sights within ±45 min of the planned ones). The golden runner prints the share per case.

### 16.7 Cost presentation and defaults date

- Fuel formula km = `TripPlan.km` (Σ day km). Exact region km stay in `units` and the breakdown. Invariant `formula_km`.
- `PriceRepository.defaults_as_of() -> date` (fake: `world.asOf`; Pg: `core.app_config['planner'].updated_at` date) replaces the "oldest fuel price" stand-in for lodging/food/tickets defaults.
- A food stop's `cost_rub` and the food line use the same default check (nearest town by population at the lunch ETA, §7.1).
- Fuel reasons: `fuel.evening` takes precedence over `fuel.last`.

### 16.8 Reasons
- `.limit` dkm per §8.1 (distance to `day_start_km + daily_km`).
- VIA reason `via.user` (§16.3).

### 16.9 Cost patch (`Planner.recompute_cost`)
- Reject with `InvalidInput("crew", "replan_required")` when the patch changes `dog`, or changes `children` between 0 and > 0. These change the lodging filters (US-05 invariant).
- After any crew change, re-render every stop's `cost_rub` (tickets, meals, rooms) and every `HotelOption.price_crew_rub`/`rooms`, so Road ahead rows agree with the Waybill.
- `EngineState` size test: the JSON of a 1,500 km trip is ≤ 400 KB.

### 16.10 Fixture/tooling hygiene
- `tools/gen_worlds.py` is the source of the worlds. `tests/unit/test_worlds.test_generator_matches_committed_json` regenerates in memory and compares byte-for-byte with the committed files. The same applies to `gen_cost_contract.py`.
- Golden line tolerances: `fuel` ±5 %; all other lines are integer world prices → tolerance 0. Every non-error case pins `costTotalRub` (±5 %, SPEC §17) and `warnings` exactly.
