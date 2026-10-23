# Verst — Sprint 1 backlog

Sprint: 1 (2 weeks, starts 2026-10-26) · Owner: Architect · Acceptance: Manager
Goal: **the complete planner engine runs and is verified in the sandbox** — repo scaffold, pure-Python `verst_planner` with all 13 pipeline stages (SPEC §7.2), the cost model (SPEC §8), fake adapters with fixture worlds, golden trips G01–G12, and a `unittest` suite that passes with `python3 -m unittest discover`. Android, API and infrastructure tasks are written down and marked **BLOCKED-ON-NETWORK**.

References: `docs/architecture.md` (cited as A§n), `docs/SPEC.md` (SPEC §n), ADRs in `docs/adr/`.

## Rules for every task

- Code and comments in English; every user-visible string in Russian lives in `verst_planner/resources/*.json` (never inline in logic). Test fixtures may contain Russian.
- `verst_planner` imports the standard library only (A§3.1). Python ≥ 3.12 syntax only (verified on the sandbox's 3.13).
- All commands below are run from the repo root `/home/claude/verst` unless they start with `cd`.
- Definition of done for each DEV task (in addition to its own criteria):
  - `cd backend/planner && python3 -m unittest discover -v` → ends with `OK` (no skips except those marked in this backlog);
  - `ruff check backend/planner` → `All checks passed!`;
  - `mypy --strict backend/planner/verst_planner` → `Success: no issues found`;
  - no `TODO`/`TBD`/`FIXME` without a task ID: `grep -rnE 'TODO|TBD|FIXME' backend/planner | grep -vE 'DEV-[0-9]{3}'` prints nothing.
- The Developer does not commit; the Manager commits after acceptance.

## Order and dependencies

```
DEV-001 ─▶ DEV-002 ─┬─▶ DEV-003 ─┐
                    ├─▶ DEV-004 ─┤
                    ├─▶ DEV-005 ─┼─▶ DEV-007 ─▶ DEV-008 ─▶ DEV-009 ─▶ DEV-010 ─▶ DEV-011 ─▶ DEV-012 ─▶ DEV-013 ─▶ DEV-014 ─┐
                    └─▶ DEV-006 ─┘                                                                                      │
                    DEV-005 ─▶ DEV-015 (cost, parallel to 009–014) ─────────────────────────────────────────────────────┤
                                                                                     DEV-016 ─▶ DEV-017 ─▶ DEV-018 ─▶ DEV-019
Designer: DES-001, DES-002, DES-004, DES-006 in parallel from day 1; DES-003, DES-005 BLOCKED-ON-NETWORK
```

| ID | Title | Owner | Depends on | Estimate |
| --- | --- | --- | --- | --- |
| DEV-001 | Repo scaffold | Developer | — | 0.5 d |
| DEV-002 | Domain model, enums, errors, JSON codec | Developer | 001 | 1 d |
| DEV-003 | Geometry: distance, polyline, PolylineIndex, bearing | Developer | 002 | 1 d |
| DEV-004 | Opening-hours parser | Developer | 002 | 0.5 d |
| DEV-005 | Config, reason templates, Russian helpers | Developer | 002 | 1 d |
| DEV-006 | Ports, events, cancel token | Developer | 002 | 0.25 d |
| DEV-007 | Fake adapters and world loader | Developer | 003, 006 | 1 d |
| DEV-008 | Fixture worlds `central_russia_v1`, `edge_cases_v1` | Developer (+ Architect review) | 007 | 1.5 d |
| DEV-009 | Stages 0–3: normalize, resolve, base route, corridor | Developer | 008 | 1 d |
| DEV-010 | Stages 4–5: day split and overnight choice | Developer | 009 | 1.5 d |
| DEV-011 | Timeline primitives and stage 6 fuel | Developer | 010, 004 | 1 d |
| DEV-012 | Stages 7–8: rest and meals | Developer | 011 | 1 d |
| DEV-013 | Stages 9–10: sights and schedule with re-run | Developer | 012 | 1 d |
| DEV-014 | Stage 11: alternatives; `replace_stop` | Developer | 013 | 1 d |
| DEV-015 | Cost model, recompute, contract cases | Developer | 005 | 1.5 d |
| DEV-016 | Explanations (stage 13) and share text | Developer | 014, 015 | 0.75 d |
| DEV-017 | `Planner` facade, progress events, cancellation, CLI | Developer | 016 | 0.75 d |
| DEV-018 | Golden-trip runner, invariants, G01–G12, contracts, layering test | Developer (+ Manager review of expectations) | 017 | 2 d |
| DEV-019 | Sandbox coverage tool, Makefile targets, README check | Developer | 018 | 0.5 d |
| DEV-020 | (optional) SSE bridge spike on bare Starlette | Developer | 017 | 0.5 d |
| DEV-021 | SQL DDL file and seed skeleton (written, not executed) | Developer | 002 | 0.5 d |
| DES-001 | Token reconciliation (canvas ↔ SPEC §6) | Designer | — | 0.5 d |
| DES-002 | Road-sign pictograms and arrows as SVG | Designer | — | 1.5 d |
| DES-004 | Russian copy deck and reason-template review | Designer | DEV-005 draft | 1 d |
| DES-006 | Missing states (loading, offline, empty, error, slow, NO_LODGING) | Designer | — | 2 d |

---

## DEV-001 — Repo scaffold

**Description.** Create the repository skeleton of A§2 for the parts needed in Sprint 1, plus empty placeholder directories (with `.gitkeep`) for `backend/api`, `backend/migrations`, `android`, `infra`, `admin`.

**Files.**
- `/.gitignore` (Python, Gradle/Android, IDE, `*.actual.json`, `.coverage*`), `/.editorconfig` (utf-8, LF, 4 spaces for py/kt, 2 for json/yml/md).
- `/Makefile` with targets: `test-planner` (`cd backend/planner && python3 -m unittest discover -v`), `lint-planner` (`ruff check backend/planner`), `typecheck-planner` (`mypy --strict backend/planner/verst_planner`), `golden-update`, `coverage-planner` (DEV-019), `check` (= lint + typecheck + test).
- `backend/planner/pyproject.toml`: `[project] name="verst-planner"`, `version="0.1.0"`, `requires-python=">=3.12"`, `dependencies=[]`; `[tool.ruff] line-length=110, target-version="py312"`, `[tool.ruff.lint] select=["E","F","W","I","B","UP","SIM","RUF"]`; `[tool.mypy] strict=true, python_version="3.12"`.
- `backend/planner/verst_planner/__init__.py` with `ENGINE_VERSION = "0.1.0"`; empty subpackages `domain, geo, pipeline, cost, explain, adapters, adapters/fake` (each with `__init__.py`), `resources/` directory.
- `backend/planner/tests/__init__.py`, `tests/unit/__init__.py`, `tests/golden/__init__.py`, `tests/contract/__init__.py`, `tests/unit/test_smoke.py` (asserts `ENGINE_VERSION` matches `^\d+\.\d+\.\d+$`).
- Placeholders: `backend/api/.gitkeep`, `backend/migrations/.gitkeep`, `android/.gitkeep`, `infra/.gitkeep`, `admin/.gitkeep`, `docs/contracts/.gitkeep`, `docs/design/.gitkeep`.

**Acceptance.**
1. `make test-planner` → exit 0, output contains `Ran 1 test` and `OK`.
2. `python3 -m unittest discover -s backend/planner -t backend/planner` → `OK` (works from repo root too).
3. `make lint-planner typecheck-planner` → exit 0.
4. `git status --porcelain | grep -c '^??'` shows only new files (no generated junk: no `__pycache__` listed).

---

## DEV-002 — Domain model, enums, errors, JSON codec

**Description.** Implement A§4 exactly (field names, types, defaults, frozen/slots). Implement `domain/codec.py`: `input_from_json(d: dict) -> TripInput`, `input_to_json(i) -> dict`, `plan_to_json(p: TripPlan) -> dict`, `plan_from_json(d) -> TripPlan` (round-trip incl. `engine_state`, used by `replace_stop` after loading from DB). Wire format = camelCase field names of A§10.3; datetimes as `YYYY-MM-DDTHH:MM` local (naive) strings; `Decimal` as strings with 2 decimals inside `units`; enums as their values; `engine_state` serialised under the key `engineState` but **excluded** from `plan_to_json(..., public=True)` (the default used for API responses).

**Files.** `verst_planner/domain/{enums.py, model.py, errors.py, codec.py}`; tests `tests/unit/test_domain.py`, `tests/unit/test_codec.py`.

**Acceptance.**
1. `cd backend/planner && python3 -m unittest tests.unit.test_domain tests.unit.test_codec -v` → `OK`, with at least these tests: `test_enum_wire_values` (every value in A§4.1), `test_tag_list_is_closed` (exactly the 18 SPEC §9 tags), `test_models_frozen` (assigning a field raises `FrozenInstanceError`), `test_crew_validation` (adults 0 and 8, children 6, `child_ages` length mismatch → `InvalidInput`), `test_input_roundtrip`, `test_plan_roundtrip` (builds a small TripPlan by hand → JSON → back → equal), `test_public_json_has_no_engine_state`, `test_error_codes` (code strings equal A§4.8).
2. `python3 -c "import sys; sys.path.insert(0,'backend/planner'); from verst_planner.domain.enums import Tag; print(len(Tag))"` → `18`.

---

## DEV-003 — Geometry

**Description.** A§6.3 and A§6.12: `geo/distance.py` (`haversine_km(a, b)`, mean Earth radius 6371.0088 km; `point_segment_km(p, a, b)` using the local equirectangular projection of A§6.3), `geo/polyline.py` (`douglas_peucker(points, cum_km, tol_m) -> list[int]` returning kept indices, `interpolate(route, km) -> LatLon`, `resample(route, step_km=1.0) -> (km tuple, min tuple)`), `geo/index.py` (`PolylineIndex(route, cell_deg=0.05)`, `project_all(p, max_km) -> list[Projection]` with pass grouping), `geo/bearing.py` (`initial_bearing_deg(a, b)`, `bearing8(a, b) -> Literal["N","NE","E","SE","S","SW","W","NW"]`).

**Files.** `verst_planner/geo/*.py`; tests `tests/unit/test_geo.py`.

**Acceptance.** `cd backend/planner && python3 -m unittest tests.unit.test_geo -v` → `OK`, including:
- `test_haversine_moscow_yaroslavl`: (55.7558, 37.6173)–(57.6261, 39.8845) = 249.8 ± 0.5 km.
- `test_project_on_straight_line`: a 100 km north–south line, point 3 km east at its middle → one projection, `km_at = 50 ± 0.2`, `lateral_km = 3 ± 0.05`.
- `test_project_beyond_radius` → empty list.
- `test_round_trip_two_passes`: out-and-back polyline (0→100→0 km along the same line), point 1 km off at the 30 km mark → two projections with `km_at ≈ 30` and `≈ 170` (±0.5).
- `test_dp_keeps_endpoints_and_corners`.
- `test_index_matches_bruteforce`: 500 random points near a 300-vertex synthetic zig-zag; `project_all` nearest result equals brute force within 1e-6 km (seeded `random.Random(42)`).
- `test_bearing8`: Moscow→Yaroslavl `NE`, Moscow→Tula `S`, Moscow→Tver `NW`, Moscow→Vladimir `E` (Vladimir 56.1290, 40.4066 → initial bearing ≈ 75° → `E`; Tver ≈ 320° → `NW`; Yaroslavl ≈ 33° → `NE`; Tula 180° → `S`).

---

## DEV-004 — Opening-hours parser

**Description.** A§6.9 subset of OSM `opening_hours`: `parse(s: str) -> OpeningHours`; `OpeningHours.is_open(local_dt)`, `.covers(start_local, end_local)`; raises `OpeningHoursParseError` for unsupported syntax.

**Files.** `verst_planner/hours.py`; tests `tests/unit/test_hours.py`.

**Acceptance.** `cd backend/planner && python3 -m unittest tests.unit.test_hours -v` → `OK`, with table-driven cases (≥ 20) including: `24/7`; `Mo-Su 09:00-18:00`; `Tu-Su 10:00-17:00` closed on Monday; `Mo-Fr 08:00-20:00; Sa,Su 10:00-18:00`; `Mo-Su 10:00-14:00,15:00-19:00` closed at 14:30; `Fr-Sa 18:00-02:00` open Saturday 01:00 (wrap past midnight); `Mo-Su 09:00-18:00; Mo off`; `Mo-Su 00:00-24:00`; `PH off` ignored; `sunrise-sunset` → `OpeningHoursParseError`; `covers(10:00, 11:30)` false for `10:00-11:00`.

---

## DEV-005 — Config, reason templates, Russian helpers

**Description.** `config.py`: `PlannerConfig` frozen dataclass mirroring every field of A§5.4 table; `PlannerConfig.default()` loads `resources/planner_config.json`; `PlannerConfig.from_dict(d, base=None)` deep-merges and rejects unknown keys with `ValueError("unknown config key: <dotted.path>")`. `explain/templates.py`: `ReasonTemplates.default()` from `resources/reasons.ru.json`, `.render(key, **params)` raising `KeyError` for missing keys/params; the JSON contains exactly the keys of A§8.1. `explain/ru.py`: `plural`, `fmt_int` (U+202F thousands), `fmt_rub` (`"34 500 ₽"` with U+202F and U+00A0), `fmt_decimal(x, places)` (decimal comma), `fmt_consumption` (`8`, `7,5`), `duration_phrase`, `part_of_day`, `prepositional`, `month_year_ru(as_of)` («октябрь 2026»).

**Files.** `verst_planner/config.py`, `verst_planner/resources/planner_config.json`, `verst_planner/resources/reasons.ru.json`, `verst_planner/explain/{templates.py, ru.py}`; tests `tests/unit/test_config.py`, `tests/unit/test_templates.py`, `tests/unit/test_ru.py`.

**Acceptance.** `cd backend/planner && python3 -m unittest tests.unit.test_config tests.unit.test_templates tests.unit.test_ru -v` → `OK`, including:
- `test_defaults_match_spec`: overnight weights 3 / 2 / 1.5 / 2 / 1, h_cap 5, window 0.70–1.05, rest intervals 120/90/180, fuel usable 0.8 and lookahead 40, dwell 15/10/15/20/60/60, lunch 12:00–14:30, day budgets 540/600/600, corridor 15/5/25, alternatives window 45 and max 3, reserve 0.10, rounding 10/100.
- `test_unknown_key_rejected`, `test_partial_override`.
- `test_every_template_renders` (each key of A§8.1 rendered with its documented params, result non-empty, no `{` left).
- `test_plural` (1 день, 2 дня, 5 дней, 11 дней, 21 день, 22 дня), `test_fmt_rub` (`34500 → "34 500 ₽"`), `test_duration_phrase` (30, 60, 90, 120, 135).

---

## DEV-006 — Ports, events, cancel token

**Description.** `ports.py` exactly as A§5.1 (Protocols, `CorridorQuery`); `events.py` with `StageEvent`, `StopEvent`, `ProgressSink`, `NULL_SINK`, `ListSink`, `CancelToken` (+ `NEVER` token that is never cancelled).

**Files.** `verst_planner/ports.py`, `verst_planner/events.py`; tests `tests/unit/test_events.py`.

**Acceptance.** `cd backend/planner && python3 -m unittest tests.unit.test_events -v` → `OK` (`ListSink` collects in order; `CancelToken.check()` raises `PlanCancelled` only after `cancel()`; thread-safety test: cancel from a `threading.Thread`).

---

## DEV-007 — Fake adapters and world loader

**Description.** A§5.2: `adapters/fake/world.py` (`FakeWorld.load(path) -> FakeWorld`, validation rules of A§5.2 with JSON-path error messages, anchors), and `FakeRouting`, `FakeGeocoding`, `FakePlaceRepository`, `FakePriceRepository`, `FakeTollRepository`, `FakeRegionLocator`, `FixedClock`. Each fake must structurally satisfy its Protocol (checked by mypy via explicit annotations in tests: `r: RoutingPort = FakeRouting(world)`). Also `adapters/fake/__init__.py: build_fakes(world) -> FakePorts` (NamedTuple of all seven).

**Files.** `verst_planner/adapters/fake/*.py`; test world `tests/unit/data/mini_world.json` (≈ 8 nodes, 3 towns, 12 places, 1 toll segment, 2 regions); tests `tests/unit/test_fake_world.py`, `tests/unit/test_fake_routing.py`, `tests/unit/test_fake_repos.py`.

**Acceptance.** `cd backend/planner && python3 -m unittest tests.unit.test_fake_world tests.unit.test_fake_routing tests.unit.test_fake_repos -v` → `OK`, including:
- `test_invalid_world_messages`: duplicate id → message contains `places[3].id`; edge shorter than straight line → contains `edges[2].km`.
- `test_route_km_equals_edge_sum`, `test_route_cum_monotonic`, `test_avoid_tolls_takes_free_edge` (mini world has a toll and a free alternative), `test_snap_over_2km_unreachable` (`Unreachable.point_index == 1`), `test_upstream_failure_injection`.
- `test_corridor_query_radius` (place at 14.9 km included, 15.1 km excluded), `test_status_live_only`, `test_price_fallback_ru`, `test_toll_hit_km_range`.

---

## DEV-008 — Fixture worlds

**Description.** Author `fixtures/worlds/central_russia_v1.json` and `fixtures/worlds/edge_cases_v1.json` in the A§5.2 format, sized and shaped for G01–G12 (A§13.4). Coordinates of towns are real (±0.01°); edge `km` within ±5 % of real road distance; speeds 60–110 km/h by road class; prices synthetic but plausible (fuel АИ-95 58–64 ₽, hotels 3 500–8 000 ₽, checks 500–1 000 ₽, tickets 0–600 ₽), `asOf` = `2026-10-01`.

`central_russia_v1` must contain at least:
- Corridors: М-8 Москва–Сергиев Посад–Переславль-Залесский–Ростов–Ярославль; Ярославль–Кострома–Иваново–Суздаль–Владимир (Golden Ring loop); М-7 Москва–Владимир–Нижний Новгород–Чебоксары–Казань (free); М-12 Москва–Владимир (bypass)–Нижний Новгород (bypass)–Казань (toll segments with day/night tariffs); М-4 Москва–Кашира + Р-22 Кашира–Михайлов–Мичуринск–Тамбов–Борисоглебск–Волгоград; М-2 Москва–Серпухов–Тула + Ясная Поляна.
- Towns (≥ 30) with quality/population/eveningWalk, incl. Сергиев Посад, Переславль-Залесский, Ростов, Ярославль, Кострома, Иваново, Суздаль, Владимир, Нижний Новгород, Чебоксары, Казань, Кашира, Михайлов, Мичуринск, Тамбов, Котовск (decoy for G03: 3 lodgings, none `dogs_allowed`, within the G03 window), Борисоглебск, Волгоград, Серпухов, Тула.
- Places (≥ 150): every town on a planned overnight has ≥ 2 lodgings (Ярославль and Тамбов ≥ 2 with `dogs_allowed`; Суздаль ≥ 1 with `dogs_allowed` + `family_room`); fuel stations every 25–50 km on main roads, some `cafe_at_fuel`/`24h`; ≥ 1 `rest` area every 60 km; ≥ 25 sights with opening hours (Троице-Сергиева лавра, Ростовский кремль, Ипатьевский монастырь, Золотые ворота, Ясная Поляна `Tu-Su 09:00-17:00`, …), ≥ 15 food places, some `kids_menu`.
- Regions: RU, RU-MOW, RU-MOS, RU-YAR, RU-KOS, RU-IVA, RU-VLA, RU-NIZ, RU-CU, RU-TA, RU-TUL, RU-RYA, RU-LIP, RU-TAM, RU-VOR, RU-VGG with АИ-92/95/ДТ prices.
- Ready routes: `rr_golden_ring` (hub Москва, points Сергиев Посад → Переславль → Ростов → Ярославль → Кострома → Иваново → Суздаль → Владимир, nights Ярославль, Суздаль, kmSign 745), `rr_yaroslavl`, `rr_tula_yasnaya` (night Тула).

`edge_cases_v1` («Тестовая область», synthetic straight corridors, region `RU-TST` tz Europe/Moscow) must support: G05 (Тестовск → Конечный ≈ 600 km, the only lodging within the corridor is `pl_tst_hotel_nodog` without `dogs_allowed`), G09 (a node 2.5 km from any edge for UNREACHABLE), G10 (two nodes 12 km apart), G11 (a 300 km stretch with no fuel), G12 (fixed long-dwell sights that overflow a day).

**Files.** `backend/planner/fixtures/worlds/central_russia_v1.json`, `backend/planner/fixtures/worlds/edge_cases_v1.json`; test `tests/unit/test_worlds.py`.

**Acceptance.**
1. `cd backend/planner && python3 -m unittest tests.unit.test_worlds -v` → `OK`; it loads both worlds and asserts the minimum counts above, that all edges satisfy `km ≥ 0.95 × haversine`, and `test_real_distances`: FakeRouting Москва→Ярославль 255–275 km, Москва→Казань via М-7 790–840 km, Москва→Волгоград 940–1010 km, Москва→Тула 175–195 km.
2. Architect sign-off recorded in the Manager's acceptance note (spot check of 10 coordinates against a map).

---

## DEV-009 — Stages 0–3: normalize, resolve, base route, corridor

**Description.** A§6.2–6.3: `pipeline/resolve.py` (`normalize_input`, `resolve_points`, `ResolvedPoints(points, labels, fixed_stops, template)`), `pipeline/base_route.py` (`build_base_route` with TooShort, Unreachable re-check, TOLLS_UNAVOIDABLE), `pipeline/corridor.py` (`build_corridor` with the exact port calls of A§6.3, motorway 5 km rule, detour formula, hours parse filtering). `PlanContext` dataclass in `pipeline/__init__.py`.

**Files.** `verst_planner/pipeline/{__init__.py, resolve.py, base_route.py, corridor.py}`; tests `tests/unit/test_resolve.py`, `tests/unit/test_corridor.py`.

**Acceptance.** `cd backend/planner && python3 -m unittest tests.unit.test_resolve tests.unit.test_corridor -v` → `OK`, including: `test_default_start_next_saturday` (clock Fri 2026-10-23 09:00 MSK → 2026-10-24 08:00), `test_default_mood` (children>0 → calm, else more_stops), `test_ready_route_defaults_round_trip`, `test_outside_russia_invalid`, `test_daily_km_step`, `test_too_short`, `test_round_trip_appends_origin`, `test_motorway_fuel_5km` (fuel 8 km off a motorway excluded, 8 km off a trunk included), `test_town_corridor_25km`, `test_detour_formula` (lateral 3 km, trunk → 2·3·1.3 = 7.8 km → round(7.8/40·60)+2 = 14 min), `test_unparseable_hours_dropped`, `test_corridor_calls_ports_once` (spy counts: 2 × `places_in_corridor`, 1 × `towns_in_corridor`, 1 × `lodgings_of_towns`).

---

## DEV-010 — Stages 4–5: day split and overnight choice

**Description.** A§6.4–6.5 including the template fit rule (D-3), crew filters, `H/Q/E/detour` score, hotel choice, the full fallback chain F1→F2→F3→F4 with warnings and `nearest` alternative, `considered` lists.

**Files.** `verst_planner/pipeline/{day_split.py, overnight.py}`; tests `tests/unit/test_day_split.py`, `tests/unit/test_overnight.py`.

**Acceptance.** `cd backend/planner && python3 -m unittest tests.unit.test_day_split tests.unit.test_overnight -v` → `OK`, including:
- `test_n_days` (530/300 → 2, 745/300 → 3, 300/300 → 1, 301/300 → 2).
- `test_window_bounds_property`: for 200 seeded random (total 100–2500, daily 150–900) `L ≤ U` at every boundary and every resulting day ≤ 1.05 × daily.
- `test_score_formula`: hand-built town (H=4, Q=2, E=1, |Δkm|=30, detour 15) → 3·4 + 2·2 + 1.5·1 − 2·0.3 − 1·1 = 15.9 (`assertAlmostEqual`, places=6).
- `test_h_cap_and_parking_weight` (7 passing lodgings → 5; 2 without parking → 1.0).
- `test_tie_closer_to_target`.
- `test_dog_filter_excludes` (only non-dog lodgings in window → F2 or F4, never a non-dog hotel selected).
- `test_osm_lodging_never_dog_friendly`.
- `test_fallback_widened_warns`, `test_fallback_extra_day`, `test_fallback_no_hotel_with_nearest`.
- `test_template_used_when_fits`, `test_template_rejected_when_day_over_105pct` (Golden Ring at 200 km/day).

---

## DEV-011 — Timeline primitives and stage 6 fuel

**Description.** A§6.6 (`Profile`, `drive`, `schedule_day`, `eta_if_inserted`, `build_day_plans` including day starts at 09:00 local next calendar day, tz from `RegionLocator`) and A§6.7 fuel walk (evening rule, lookahead, lookback, FUEL_GAP, coffee upgrade, `litres`).

**Files.** `verst_planner/pipeline/{timeline.py, fuel.py}`; tests `tests/unit/test_timeline.py`, `tests/unit/test_fuel.py`.

**Acceptance.** `cd backend/planner && python3 -m unittest tests.unit.test_timeline tests.unit.test_fuel -v` → `OK`, including: `test_schedule_simple` (100 km at 60 km/h free-flow, factor 1.1, 30-min stop at km 50 with detour 10 min → arrival at finish = start + 110 + 30 + 10 min), `test_day2_starts_0900_next_day`, `test_local_tz_rendering` (stop in Europe/Samara shows +1 h), `test_fuel_range_math` (tank 50, 8 l → full 625, trigger at 500 km), `test_fuel_prefers_coincide` (station 1.5 km from a lunch stop wins over a better-rated one), `test_fuel_evening_before_overnight` (G03-like: overnight at 460, trigger 500 → station in [420, 460]), `test_no_fuel_near_finish`, `test_fuel_gap_warning`, `test_fuel_coffee_upgrade`.

---

## DEV-012 — Stages 7–8: rest and meals

**Description.** A§6.8: rest insertion loop with breaks counted from any stop with dwell ≥ 15 min, windows and widening, `rest_score`, virtual breaks; lunch selection by ETA window and `lunch_score`; dinner/breakfast are cost units only (D-5, D-6).

**Files.** `verst_planner/pipeline/{rest.py, meals.py}`; tests `tests/unit/test_rest.py`, `tests/unit/test_meals.py`.

**Acceptance.** `cd backend/planner && python3 -m unittest tests.unit.test_rest tests.unit.test_meals -v` → `OK`, including: `test_rest_interval_by_mood` (6 h driving: calm → 2 breaks, more_stops → 3, just_drive → 1), `test_existing_stop_counts_as_break`, `test_playground_preferred_with_children`, `test_walk_preferred_with_dog`, `test_no_rest_near_day_end`, `test_lunch_in_window` (ETA 12:00–14:30), `test_kids_menu_preferred`, `test_no_lunch_when_day_outside_window` (day ends 11:30 → no lunch stop).

---

## DEV-013 — Stages 9–10: sights and schedule with re-run

**Description.** A§6.9 sights (`sight_score`, per-mood max, budget check, opening-hours coverage, `simplify` and `just_drive` skip) and A§6.10 `schedule_with_rerun` (single re-run, drop lowest-score sights first, DAY_OVER_BUDGET, output rounding rules).

**Files.** `verst_planner/pipeline/{sights.py, schedule.py}`; tests `tests/unit/test_sights.py`, `tests/unit/test_schedule.py`.

**Acceptance.** `cd backend/planner && python3 -m unittest tests.unit.test_sights tests.unit.test_schedule -v` → `OK`, including: `test_closed_sight_skipped` (Monday, `Tu-Su`), `test_visit_must_fit_hours` (arrive 16:30, closes 17:00, dwell 60 → skipped), `test_budget_respected` (calm day never > 540 min), `test_just_drive_no_sights`, `test_simplify_no_sights`, `test_max_per_day`, `test_rerun_drops_lowest_first`, `test_rerun_only_once` (a spy counts `plan_fuel` calls == 2 at most), `test_day_over_budget_warning`, `test_km_rounding_sum` (Σ day km == trip km).

---

## DEV-014 — Stage 11: alternatives; `replace_stop`

**Description.** A§6.11: candidate pools per kind, ±45 min arrival window, hours/lunch/budget checks, `delta_min`, `shift_min`, `delta_rub`, `AltUnits`; deterministic ids `alt_{stopId}_{placeId}`; `Planner.replace_stop` re-schedules only the affected day from `EngineState` (no routing call).

**Files.** `verst_planner/pipeline/{alternatives.py, assemble.py}` (assemble builds `ScheduledStop`/`DayResult`, ids `d{day}s{nn}`, signs), `verst_planner/engine.py` (`replace_stop` part); tests `tests/unit/test_alternatives.py`, `tests/unit/test_replace.py`.

**Acceptance.** `cd backend/planner && python3 -m unittest tests.unit.test_alternatives tests.unit.test_replace -v` → `OK`, including: `test_alternatives_within_45min`, `test_max_three`, `test_not_for_start_finish_overnight`, `test_alt_excludes_used_places`, `test_alt_sight_must_be_open`, `test_replace_updates_only_that_day` (other days byte-identical in JSON), `test_replace_no_routing_call` (FakeRouting call count unchanged), `test_replace_unknown_ids_not_found`, `test_replace_matches_offline_shift` (applying `shift_min` to the old schedule equals the new schedule of later stops ±1 min).

---

## DEV-015 — Cost model, recompute, contract cases

**Description.** A§7 completely: `cost/money.py` (`round_to`, Decimal helpers), `cost/formulas.py` (formula and breakdown strings for every line, A§7.1 table, using `explain/ru.py`), `cost/model.py` (`compute_cost` incl. region attribution input, toll day/night, rooms, meals per D-6, child weights, tickets, per-stop `cost_rub`, hints, `as_of`), `cost/recompute.py` (`recompute(units, crew, reserve_on, budget_rub, overrides)`), and the shared contract file.

**Files.** `verst_planner/cost/*.py`; `tests/unit/test_cost.py`; `tests/contract/cost_recompute_cases.json` (≥ 25 cases), `tests/contract/test_cost_recompute_contract.py`.

**Acceptance.** `cd backend/planner && python3 -m unittest tests.unit.test_cost tests.contract.test_cost_recompute_contract -v` → `OK`, including:
- `test_waybill_canvas_rounding`: lines 3 720 / 0 / 12 000 / 12 600 / 3 000, reserve on → reserve 3 130, total 34 500; reserve off → 31 300; budget 40 000 → remaining 5 500 (on).
- `test_fuel_by_region` (2 regions → 2 breakdown rows, formula «≈ … (средняя по 2 регионам)»).
- `test_toll_night_tariff`, `test_rooms_ceil` (3 adults → 2 rooms), `test_child_under7_half_food`, `test_unknown_child_age_counts_full`, `test_child_ticket_fallback_to_adult`, `test_free_entry_zero`, `test_per_person_rounding` (34 500 / 3 → 11 500), `test_half_up_rounding` (exact 1 245.00 → 1 250; 1 244.99 → 1 240), `test_over_budget_hints_order`, `test_as_of_oldest`, `test_formula_strings_russian` (no Latin letters, thin spaces).
- The contract test iterates every case and compares all lines, subtotal, total, per person, remaining, over_budget.

---

## DEV-016 — Explanations and share text

**Description.** A§8.1 reason selection (dominant factor, `dkm`, cap suffix, fallback texts, per-kind stop reasons and notes, warning messages incl. `nearest`) and A§8.2 `share_text`.

**Files.** `verst_planner/explain/{reasons.py, share.py}`; tests `tests/unit/test_reasons.py`, `tests/unit/test_share.py`.

**Acceptance.** `cd backend/planner && python3 -m unittest tests.unit.test_reasons tests.unit.test_share -v` → `OK`, including: `test_overnight_shift_hotels_text` (pick Ярославль vs other Ростов 55 km earlier, dog crew → «Не в Ростове, а на 55 км дальше: здесь больше отелей, куда пускают с собакой. Ваши 300 км в день не превышены.»), `test_on_target`, `test_no_hotel_text`, `test_every_auto_stop_has_reason`, `test_share_text_format` (exact expected multi-line string for a hand-built 2-day plan).

---

## DEV-017 — `Planner` facade, progress events, cancellation, CLI

**Description.** `engine.py: Planner` (A§6.1) wiring stages 0–13, `recompute_cost` (A§6.1 `CostPatch`), events exactly per A§8.3, `cancel.check()` at the listed points, `ENGINE_VERSION` in the plan. `cli.py`: `python3 -m verst_planner.cli plan --world <path> --input <case-or-input.json> [--clock ISO] [--events] [--out file]` prints the public plan JSON (pretty, `ensure_ascii=False`) and, with `--events`, one JSON line per event to stderr; `share` subcommand prints the share text.

**Files.** `verst_planner/engine.py`, `verst_planner/cli.py`, `verst_planner/__init__.py` (re-export `Planner`, `TripInput`, `TripPlan`); tests `tests/unit/test_engine.py`, `tests/unit/test_cli.py`.

**Acceptance.**
1. `cd backend/planner && python3 -m unittest tests.unit.test_engine tests.unit.test_cli -v` → `OK`, including `test_event_order` (first event `stage/split` progress 0.05; progress non-decreasing; final stop events match the plan), `test_one_day_trip_has_no_lodging_stage`, `test_cancel_before_corridor` (cancel from the sink on the first event → `PlanCancelled`, routing called once), `test_upstream_error_propagates`, `test_patch_reserve_and_crew` (`recompute_cost` changes only cost), `test_patch_hotel_choice`, `test_determinism` (two runs → identical JSON).
2. `cd backend/planner && python3 -m verst_planner.cli plan --world fixtures/worlds/central_russia_v1.json --input tests/golden/cases/G01_msk_yar_round.json --events > /dev/null` → exit 0; stderr has ≥ 5 JSON lines.
3. Performance: `test_engine.test_perf_1500km` plans a ≥ 1 400 km fake trip in < 1.0 s wall time on the sandbox (CPU-only budget; the 10 s SPEC budget is dominated by I/O).

---

## DEV-018 — Golden trips, invariants, contracts, layering test

**Description.** A§13.2–13.4: golden runner `tests/golden/test_golden.py` (one generated test method per case file, `subTest` per invariant, snapshot compare with `.actual.json` + diff, `VERST_GOLDEN_UPDATE=1`), `tests/golden/invariants.py` (all invariants of A§13.3), case files G01–G12 with hand-authored `expect` and `costWorkings`, snapshots, and generated contracts: `docs/contracts/plan-response.example.json` (G02) and `docs/contracts/share-text/G01.json … G08.json` (`{"plan": …, "text": …}`), written by `tests/golden/export_contracts.py` (run as `cd backend/planner && python3 -m tests.golden.export_contracts`). `tests/test_layering.py` per A§3.1 rules 1–2.

Golden inputs (all `startAt` explicit; clock `2026-10-23T09:00:00+03:00`; vehicle default unless stated):

| Case | Input | Mandatory expectations |
| --- | --- | --- |
| G01 `msk_yar_round` | Москва → Ярославль, `roundTrip: true`, crew 2/0/no dog, dailyKm 300, startAt 2026-10-24T08:00 | days 2; night 1 = Ярославль; fallback none; no warnings; each day ≤ 315 km |
| G02 `golden_ring` | `readyRouteId: rr_golden_ring`, crew 2 adults + 1 child + dog, dailyKm 300, budget 40000, startAt 2026-11-07T08:00 | days 3; nights Ярославль, Суздаль; fallbacks template, template; selected hotels `dogs_allowed`; total = `costWorkings` ±5 %; remaining = 40000 − total |
| G03 `msk_volgograd_dog_child` | Москва → Волгоград, crew 2 + 1 child (age 5) + dog, dailyKm 500, budget 60000, startAt 2026-10-24T07:00 | days 2; night Тамбов; Котовск lodgings in `mustExcludePlaceIds`; exactly 1 fuel stop on day 1 positioned before the overnight (evening rule); food line uses weight 0.5 for the child |
| G04 `msk_kazan_just_drive` | Москва → Казань, `avoidTolls: false`, crew 1/0/no, dailyKm 900, mood just_drive, startAt 2026-10-24T06:00 | days 1; 0 sights; ≥ 1 fuel; rests ≈ every 3 h (count 2 ± 1); tolls line > 0 with М-12 breakdown rows |
| G05 `edge_no_dog_lodging` | Тестовск → Конечный (edge world), crew 2/0/dog, dailyKm 300, startAt 2026-10-24T08:00 | warnings contain `NO_LODGING`; overnight fallback `no_hotel`; `pl_tst_hotel_nodog` never selected nor offered; lodging breakdown says «(средняя цена)» |
| G06 `msk_kazan_no_tolls` | Москва → Казань, `avoidTolls: true`, crew 2/0/no, dailyKm 450, startAt 2026-10-24T08:00 | days 2; night Нижний Новгород; tolls line 0; route refs contain «М-7» only on main stretch |
| G07 `tula_yasnaya` | `readyRouteId: rr_tula_yasnaya`, crew 2 + 2 children, dailyKm 300, startAt 2026-10-24T09:00 (Saturday) | days 2; night Тула; Ясная Поляна included and open during visit |
| G08 `msk_suzdal_via_vladimir` | Москва → Суздаль, via Владимир, crew 2/0/no, mood more_stops, dailyKm 300, startAt 2026-10-24T08:00 | days 1; via stop present before Суздаль; 1–4 sights all open |
| G09 `edge_unreachable` | destination = the off-road node | `expect.error = UNREACHABLE` |
| G10 `edge_too_short` | 12 km apart | `expect.error = TOO_SHORT` |
| G11 `edge_fuel_gap` | through the 300 km no-fuel stretch, tank 30 l | warnings contain `FUEL_GAP` |
| G12 `edge_day_over_budget` | fixed long sights, calm | at least one sight dropped vs. the first pass (asserted via a `ListSink` hook or `engine_state` debug counter `rerun=1`) and/or `DAY_OVER_BUDGET` exactly as written in the case |

**Files.** `tests/golden/{__init__.py, test_golden.py, invariants.py, export_contracts.py}`, `tests/golden/cases/G01…G12_*.json`, `tests/golden/snapshots/G01…G08_*.json` (error cases have no snapshot), `tests/test_layering.py`, `docs/contracts/plan-response.example.json`, `docs/contracts/share-text/*.json`.

**Acceptance.**
1. `cd backend/planner && python3 -m unittest tests.golden.test_golden -v` → `OK`, 12 golden tests, each with every invariant of A§13.3 as a subTest.
2. `cd backend/planner && python3 -m unittest tests.test_layering -v` → `OK`; temporarily adding `import pydantic` to any `verst_planner` module makes it fail (Manager checks once).
3. `ls backend/planner/tests/golden/cases | wc -l` → `12`; `python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('backend/planner/tests/golden/cases/*.json')]"` → no error; every case with `costTotalRub` has non-empty `costWorkings`.
4. Determinism: `cd backend/planner && python3 -m tests.golden.export_contracts && git diff --stat -- ../../docs/contracts` → no changes on a second run.
5. Editing one snapshot value by hand makes the run fail with a diff and creates `*.actual.json` (Manager checks once, then reverts).
6. Manager review: the expectation tables in each case file are justified by `costWorkings` and the world data (not copied from engine output — the Developer writes cases **before** generating snapshots and records the initial failing run in the acceptance note).

---

## DEV-019 — Sandbox coverage tool, Makefile targets, README check

**Description.** A§13.5 `tools/stdlib_coverage.py` (`python3 tools/stdlib_coverage.py --fail-under 85` from `backend/planner`), Makefile `coverage-planner`, verify README commands.

**Files.** `backend/planner/tools/stdlib_coverage.py`, Makefile update.

**Acceptance.**
1. `make coverage-planner` → prints a per-file table and `TOTAL … ≥ 85.0%`, exit 0.
2. `cd backend/planner && python3 tools/stdlib_coverage.py --fail-under 101` → exit 1.
3. `make check` → exit 0. Every command in `README.md` "Run the tests" section succeeds verbatim.

---

## DEV-020 — (optional) SSE bridge spike on bare Starlette

**Description.** Prove the A§10.4 thread → asyncio bridge with the real planner and fakes using only preinstalled Starlette + uvicorn. Throwaway code under `backend/spikes/sse_spike.py` (deleted when DEV-B01 lands); not part of the product.

**Acceptance.** `python3 backend/spikes/sse_spike.py &` then `curl -sN -X POST localhost:8765/plan -H 'Accept: text/event-stream' -d @backend/planner/tests/golden/cases/G02_golden_ring.json | head -20` shows `event: stage` first and `event: done` last; Ctrl-C of curl mid-stream logs `cancelled` on the server.

---

## DEV-021 — SQL DDL and seed skeleton (written, not executed)

**Description.** Copy A§9.2 into `backend/migrations/sql/0001_initial.sql` verbatim (the architecture block is the source; any change goes to both). Seed skeleton `backend/migrations/seed/0001_regions.sql` with the 16 region rows of DEV-008 (geometry NULL, filled from OSM in INF-001) and `0002_app_config.sql` inserting `planner` and `reasons_ru` from the planner resources (generated by `python3 -m verst_planner.cli export-config > …`).

**Acceptance.** File exists; `diff <(python3 -c "import re;s=open('docs/architecture.md').read();print(re.search(r'\`\`\`sql\n(CREATE EXTENSION.*?)\`\`\`',s,re.S).group(1),end='')") backend/migrations/sql/0001_initial.sql` → no output. Execution against PostGIS is DEV-B02 (BLOCKED-ON-NETWORK).

---

## Designer tasks

### DES-001 — Token reconciliation
Compare every colour, radius and size in `docs/design-canvas/*.dc.html` with SPEC §6 tokens; output `docs/design/tokens.json` (`{"color": {"dash": "#141416", …, "hill": "#3C3346"}, "radius": {…}, "type": {…}, "motion": {…}}`) and list every canvas literal not covered by a token with a proposed token name (e.g. `hill` #3C3346, seat fill #3A3A42, dashed seat border #55555E, dog #C99A5B, radio border #3A5266, child-silhouette #E9E2F2, highlight row #1A2C3B / #0F1A22).
**Acceptance:** `python3 -m json.tool docs/design/tokens.json > /dev/null`; `grep -ohE '#[0-9A-Fa-f]{6}' docs/design-canvas/*.dc.html | tr a-f A-F | sort -u` — every printed colour appears in `tokens.json` (Manager runs `python3 -c` one-liner comparing sets; output empty).

### DES-002 — Road-sign pictograms and arrows
SVG set (24×24 viewBox, single-colour, stroke-free paths) for: fuel 7.3, food 7.7, rest 7.11, hotel 7.12, tourist pictograms (kremlin, monastery, museum, view, walk, generic), 8 direction arrows (the canvas paths UR/UP/DN/DL + the remaining 4), dog, child, adult silhouettes; plus `docs/design/signs.md` specifying each `RoadSign` variant's geometry (border widths 3/2 dp, radii) for Compose.
**Acceptance:** `ls docs/design/icons/*.svg | wc -l` ≥ 21; each file contains `viewBox="0 0 24 24"` and no `<image`/`<text`; `python3 -c "import xml.dom.minidom,glob;[xml.dom.minidom.parse(f) for f in glob.glob('docs/design/icons/*.svg')]"` passes.

### DES-003 — Fonts (BLOCKED-ON-NETWORK)
Download IBM Plex Sans Condensed 400/500/600/700, IBM Plex Mono 600, Marck Script 400 (OFL) and verify Cyrillic coverage (А–я, Ёё, №, ₽, U+202F) with a glyph check; place into `android/core-ui/src/main/res/font/` with OFL texts in `android/core-ui/src/main/assets/licenses/`.

### DES-004 — Russian copy deck and reason-template review
`docs/design/copy-ru.md`: every user-visible string per screen and state (SPEC §5, §12 errors, A§8.1 templates, warnings, empty/offline states), with string resource keys (`windshield_offline_title`, …) and plural forms. Review `reasons.ru.json` (DEV-005) for tone and length (≤ 140 characters per rendered reason). Resolve Q-4: Waybill example text with 5 meals.
**Acceptance:** every key in `backend/planner/verst_planner/resources/reasons.ru.json` appears in `copy-ru.md` (`python3 -c` key check prints nothing missing); Manager reads the deck.

### DES-005 — Reference screenshots (BLOCKED-ON-NETWORK: needs a headless browser and fonts)
PNG 390×844 per screen and state rendered from the canvases into `docs/design/reference/`, used as Paparazzi comparison targets.

### DES-006 — Missing states
Design (as additional `.dc.html` canvases in `docs/design-canvas/states/`) the states that SPEC §5 requires but the canvas does not show: Windshield loading (shimmer plates), offline, no ready routes; Navigator no results / far from Russia; Drive slow (20 s) and error; Road ahead with a `NO_LODGING` overnight (no hotel sign, warning plate, «ближайшая подходящая»), with an over-budget day; Waybill over budget (red «перерасход» + hints); offline plates «Нужен интернет».
**Acceptance:** one canvas per state listed (≥ 11 files); each uses only tokens from DES-001.

---

## BLOCKED-ON-NETWORK (planned, do not start until the CEO enables registry access)

| ID | Task | Needs | Acceptance (when unblocked) |
| --- | --- | --- | --- |
| DEV-A01 | Android Gradle scaffold: settings with all 11 modules, `build-logic` convention plugins, `libs.versions.toml` from A§11.1 **re-verified** against Google Maven/Maven Central (update A§11.1 table), `checkModuleGraph` task | Google Maven, Maven Central, Gradle Plugin Portal, Android SDK 36 | `cd android && ./gradlew assembleDebug checkModuleGraph` green; APK installs on API 26 emulator and shows a dark screen with «Верста» |
| DEV-A02 | `:core-ui` tokens, theme, fonts (DES-003), detekt rule `NoColorLiteralOutsideTokens` | same + fonts | `./gradlew :core-ui:detekt` fails on a planted `Color(0xFF000000)` in a component file |
| DEV-A03 | `:core-model` DTOs + `CostCalculator` + `ShareTextBuilder` running the Python contract files | same | `./gradlew :core-model:test` runs all `cost_recompute_cases.json` and `share-text/*.json` cases green |
| DEV-A04 | `WindshieldScene` Canvas (A§11.9) with reduced motion + Paparazzi test | same | Paparazzi snapshot vs DES-005 within 0.1 %; static frame when animator scale = 0 |
| DEV-A05 | `:data` Retrofit/OkHttp/SSE client against MockWebServer, Room v1 schema export, DataStore | same | `./gradlew :data:testDebugUnitTest` incl. SSE event parsing and Room schema JSON in `android/data/schemas/1.json` |
| DEV-A06 | Navigation skeleton with 7 empty screens + back behaviour | same | Compose UI test walks Windshield → … → Exit and back |
| DEV-A07 | CI `android.yml` | GitHub Actions + network | workflow green on PR |
| DEV-B01 | `verst_api` FastAPI skeleton: settings, auth, errors, `/v1/devices`, `/v1/config`, `/v1/trips/plan` (JSON + SSE) with **fake** adapters | PyPI (fastapi, sqlalchemy, psycopg, redis, alembic, httpx, pytest, schemathesis) | `pytest backend/api` green; `curl -N` SSE as in DEV-020 |
| DEV-B02 | Run `0001_initial.sql` via Alembic on `postgis/postgis:16-3.4`; schema test; triggers tests | Docker Hub, PyPI | `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` green; feedback auto-hide test green |
| DEV-B03 | Real adapters (GraphHopper, Photon, Pg repositories) + contract tests vs dev compose | as above + maps | Moscow→Yaroslavl route and «Яро» suggest from local services (SPEC M1) |
| INF-001 | Maps build scripts (CFD extract for dev, Russia for prod), `maps.compose.yml`, `dev.compose.yml` | Docker Hub, Geofabrik, Maven | `make dev-up` then `curl localhost:8989/health` → `OK` |
| INF-002 | `app.compose.yml`, nginx (SSE settings), backups, monitoring | Docker Hub | staging up, `/readyz` 200 |
| ADM-001 | Directus 11 on dev DB, roles, snapshot | Docker Hub / npm | curator can create a `live` place only with `verified_at` (DB rejects otherwise) |

## Sprint 1 exit criteria (Manager checklist)

- [ ] `cd backend/planner && python3 -m unittest discover -v` → `OK` (expected ≥ 150 tests incl. 12 golden).
- [ ] `make check` and `make coverage-planner` (≥ 85 %) green.
- [ ] G01–G05 expectations hold and are hand-justified (`costWorkings`).
- [ ] Dog invariant holds on all golden trips; G05 shows `NO_LODGING`.
- [ ] `docs/contracts/plan-response.example.json` exists and matches the SPEC §12 shape (fields `id, title, km, days, nights, daysList[].stops[], cost.lines[], reasons.overnights[]`).
- [ ] No non-stdlib imports in `verst_planner` (layering test).
- [ ] DES-001, DES-002, DES-004, DES-006 delivered.
