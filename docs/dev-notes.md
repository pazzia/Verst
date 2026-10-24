# Developer notes — Sprint 1

Running log per task: status, files, commands run with their final result lines, deviations from
`docs/architecture.md` (A§n). Deviations are also collected at the end.

## DEV-001 — Repo scaffold

Status: done.
Files: `.gitignore`, `.editorconfig`, `Makefile`, `backend/planner/pyproject.toml`,
`backend/planner/verst_planner/__init__.py` (+ empty subpackages), `backend/planner/tests/**/__init__.py`,
`tests/unit/test_smoke.py`, placeholders `backend/api/.gitkeep`, `backend/migrations/.gitkeep`,
`android/.gitkeep`, `infra/.gitkeep`, `admin/.gitkeep`, `docs/contracts/.gitkeep`.

Commands:
- `make test-planner` → `Ran 1 test` / `OK`
- `python3 -m unittest discover -s backend/planner -t backend/planner` → `OK`
- `make lint-planner typecheck-planner` → `All checks passed!` / `Success: no issues found in 8 source files`
- `git status --porcelain | grep -c '^??'` → only new paths, no `__pycache__`.

Deviation: `docs/design/.gitkeep` is **not** created. The Manager decided the canonical design folder is
`design/` (A§2 also lists `design/` at the root); a second empty `docs/design/` would invite misplaced files.

## DEV-002 — Domain model, enums, errors, JSON codec

Status: done.
Files: `verst_planner/domain/{enums,model,errors,codec}.py`, `tests/helpers.py`, `tests/unit/test_domain.py`,
`tests/unit/test_codec.py`.
Commands: `python3 -m unittest tests.unit.test_domain tests.unit.test_codec -v` → `OK`;
`python3 -c "…print(len(Tag))"` → `18`.

Deviations / decisions:
- A§3.1 rule 2 read as: `domain` imports only `domain`; `geo` imports only `domain` + `geo` (geo signatures
  take `LatLon`/`Route`, so geo cannot be import-free). `Corridor` (A§4.6) therefore lives in
  `verst_planner.pipeline` (it holds a `geo.PolylineIndex`).
- `NormalizedInput` gains `tz: str` (origin tz) so the wire `input` carries `startAt` + `tz`.
- Working-state extensions: `PlannedStop.litres`, `PlannedStop.coffee` (A§6.7 records litres / coffee upgrade);
  `OvernightChoice.nearest`, `.nearest_town`, `.region_code`, `.detour_km`, `.detour_min`.
- `Alternative.units: AltUnits` (A§7.4 says each alternative carries its units); `HotelPrice.breakfast_included`
  (A§7.4 text); `CostUnits.as_of` (line freshness so offline recompute keeps `asOf`); `CostResult.hints_ru`
  (rendered hints for `CostDTO.hints`; `hintKeys` is also emitted).
- `EngineState` extended with `days: tuple[DayState]` (per-day scheduling inputs), `candidates`
  (corridor candidates without place bodies) and `rerun` (debug counter used by G12). `replace_stop` needs them
  to re-schedule a day and rebuild its alternatives without routing (A§6.11); place bodies are re-read through
  `PlaceRepository.get_places`.
- `plan_to_json(plan, public=True, trip_id=None)`: emits `id` = `trip_id` (API owns ids); API-only fields
  `saved/shareSlug/createdAt/shareText` are added by the API. Warnings also carry `detail`; stops carry `day`
  and `tz` (needed for the round trip).
- Codec rejects unknown request keys with `InvalidInput("<path>", "unknown_field")` (DTO `extra="forbid"`).

## DEV-003 — Geometry

Status: done. Files: `verst_planner/geo/{distance,polyline,index,bearing}.py`, `tests/unit/test_geo.py`.
Command: `python3 -m unittest tests.unit.test_geo -v` → `Ran 13 tests` / `OK`.
Notes: `PolylineIndex.project_all` returns `seg_idx` as the dense polyline segment index (so `road_class` comes
from the `RouteDetail` covering it). The brute-force test compares against the same simplified segments
(the zig-zag keeps all 300 vertices, asserted). Extra helpers: `geo.polyline.min_at`, `PolylineIndex.nearest`,
`road_ref_at`.

## DEV-004 — Opening-hours parser

Status: done. Files: `verst_planner/hours.py`, `tests/unit/test_hours.py` (29 `is_open` table cases + 10 rejects).
Command: `python3 -m unittest tests.unit.test_hours -v` → `OK`.
Semantics: closing time itself is closed for `is_open`; `covers(start, end)` accepts `end == closing`; a rule
naming a day replaces that day's intervals (and their past-midnight spill).

## DEV-005 — Config, reason templates, Russian helpers

Status: done. Files: `verst_planner/config.py`, `resources/planner_config.json`, `resources/reasons.ru.json`,
`resources/strings.ru.json`, `explain/{templates,ru}.py`, tests `test_config/test_templates/test_ru`.
Command: `python3 -m unittest tests.unit.test_config tests.unit.test_templates tests.unit.test_ru -v` → `OK`.

Deviations / decisions:
- `reasons.ru.json` has exactly the A§8.1 keys. Every other Russian UI string the engine needs (month names,
  duration phrases, cost line titles and formula fragments, share-text lines, the «Ближайшая подходящая …»
  nearest-lodging text of A§6.5, «Точка на карте», «Ночёвка у трассы …») lives in a second resource
  `resources/strings.ru.json`, read by `explain.ru.text()`. Reason: backlog rule "every user-visible string in
  Russian lives in resources" + "reasons JSON contains exactly the keys of A§8.1".
- `ru.duration_genitive` added for `rest.generic` («после двух часов за рулём»); `ru.capitalize_first` for
  `sight.default` («Полтора часа на осмотр.»).
- `part_of_day`: < 12 «обеду», 12–17 «ужину», ≥ 17 «вечеру» (A§8.1 gives only the two ends).
- Config percentages used in money maths (`cost.reserve_frac`, `child_food_weight_under7`,
  `breakfast_price_frac`) are `Decimal`; per-mood maps are `MoodInts` with `.of(mood)`.
- Ruff: `tests/**` ignore RUF001/RUF003 (Cyrillic confusables in fixtures). Code under `verst_planner` keeps no
  Russian literals; ruff format is applied.

## DEV-006 — Ports, events, cancel token

Status: done. Files: `verst_planner/ports.py`, `verst_planner/events.py`, `tests/unit/test_events.py`.
Command: `python3 -m unittest tests.unit.test_events -v` → `OK`. Extra: `events.event_to_json` (SSE payloads
of A§10.4, used by the CLI `--events`).

## DEV-007 — Fake adapters and world loader

Status: done. Files: `verst_planner/adapters/fake/{__init__,world,routing,geocoding,places,prices,tolls,regions,clock}.py`,
`tests/unit/data/mini_world.json` (8 nodes, 3 towns, 12 places, 1 toll segment, 2 regions),
`tests/unit/test_fake_{world,routing,repos}.py`.
Command: `python3 -m unittest tests.unit.test_fake_world tests.unit.test_fake_routing tests.unit.test_fake_repos -v`
→ `Ran 21 tests` / `OK`. Protocol conformance: explicit port annotations in the tests pass
`mypy --strict tests/unit/test_fake_routing.py tests/unit/test_fake_repos.py`; `adapters/fake/__init__._conformance`
repeats them inside the package so the DoD mypy run covers it.

Decisions (A§5.2 left open):
- Snapping: nearest node (only nodes with edges) when it is no farther than the nearest edge point + 0.5 km,
  else the edge point (virtual split, partial edges both ways, direct link when two points share an edge).
  Snap > 2 km → `Unreachable(point_index, snap_km)`.
- Polyline: each traversed (partial) edge is cut into `max(1, round(km))` pieces.
- `FakeTollRepository`: one hit per pass (an out-and-back over a segment pays twice); endpoints matched by
  nearest `km_at`.
- Spy counters (`FakeRouting.calls`, `FakePlaceRepository.calls[...]`, `FakeRegionLocator.calls`) for the tests.
- Corridor distance uses the local equirectangular point–segment distance (same metric as anchors and
  `PolylineIndex`), so the 14.9 / 15.1 km boundary is exact.

## DEV-008 — Fixture worlds

Status: done (Architect spot check of coordinates pending, as per the backlog).
Files: `fixtures/worlds/central_russia_v1.json` (46 nodes, 47 edges, 41 towns, 322 places: 82 fuel, 81 food,
78 rest, 48 lodging, 33 sights; 16 regions; 4 М-12 toll segments; 3 ready routes),
`fixtures/worlds/edge_cases_v1.json` (14 nodes, 7 towns, 51 places, regions RU + RU-TST, `rr_tst_marathon`),
`tests/unit/test_worlds.py`.
Command: `python3 -m unittest tests.unit.test_worlds -v` → `Ran 7 tests` / `OK`.
Routing results: Москва→Ярославль 263 km; Москва→Казань М-7 814 km (avoidTolls), М-12 790 km; Москва→Волгоград
980 km; Москва→Тула 183 km; Golden Ring loop 745 km (= `kmSign`).

How the worlds support the golden trips:
- G01: Ростов at km 204 is outside the day-1 window [215, 278]; Ярославль (263) is the only town in it.
- G02: template day lengths 263 / 260 / 222 km (≤ 315); Ярославль and Суздаль each have a dog + family hotel
  at 6 000 ₽ that wins `hotel_score` («Ярославль + Суздаль, 2 × 6 000»).
- G03: window [455, 514.5]; Тамбов (467) has 2 dog + family hotels; Котовск (483) has 3 lodgings, none
  dog-friendly. The only fuel station in the evening window [427, 467] is at km 457; М-4/Р-22 stations have no
  `cafe_at_fuel` and rest areas (with playgrounds) are every 35 km so rest windows never pick a coffee stop.
- G04/G06: М-12 joins the network only in Moscow and Kazan, so no other trip can pick up its tolls.
- G05/G09–G12: straight synthetic corridors in «Тестовая область» (details in `test_worlds.test_edge_world_shapes`).
Deviation: М-4 is modelled toll-free in v1 (real М-4 has toll sections); keeps G03's cost about lodging/fuel.
Sprint-2 G18 (night tariff on М-4) will add the М-4 segments.
The JSON is generated by a one-off script with hand-chosen values (coordinates, edge km, prices, places) plus
regularly spaced roadside POIs; the JSON files are the source of truth.

## Manager copy requirements (design/decisions.md round 2, copy-ru.md §13 R-1…R-4)

Applied while on DEV-008 (Manager instruction, mid-task):
- R-1 `strings.ru.json`: `cost.title.fuel` = «Бензин {fuel_type}» (+ `fuel_type.ai92/ai95/dt` = АИ-92/АИ-95/ДТ),
  `cost.title.food` = «Питание», `cost.title.reserve` = «Резерв {pct}%», `cost.reserve` = «на пробки и «давай
  заедем»» (the «10%» moved to the title; `cost.reserve.pct` removed). «Платные дороги» was already right.
- R-2 `reasons.ru.json`: `rest.generic`/`rest.who` use `{min} {min_word}`; `ru.minutes_word(n)`.
- R-3 `ReasonTemplates.render` capitalises the first character of every rendered template (fragments that
  start with a space or comma are unaffected).
- R-4 `ru.fmt_price` («62,40») and `ru.fmt_consumption_setting` («8,0»). Note a conflict: A§7.2 and the DEV-005
  acceptance test want `fmt_consumption(8) == "8"` in cost formulas («745 км × 8 л/100 × …»). Both are kept:
  formulas use `fmt_consumption`, the Drive stage line («Считаем бензин: 8,0 л на 100 км») uses
  `fmt_consumption_setting`; fuel prices in formulas always show kopecks («62,40 ₽»).
Tests: `test_templates.test_rendered_reasons_are_capitalised`, `test_templates.test_rest_minutes_plural`,
`test_ru.test_decimal_comma_in_user_numbers`.
`DAY_OVER_BUDGET` key unchanged.

## Task order note

DEV-014's `replace_stop` tests need a working `Planner` with cost, so the order after DEV-013 is:
DEV-015 (cost) → DEV-016 (reasons/share) → DEV-014 (alternatives, assemble, engine plan + replace) → DEV-017.
Each task's own test files and acceptance commands are unchanged.

## DEV-009 — Stages 0–3

Status: done. Files: `pipeline/{__init__,resolve,base_route,corridor}.py`, `tests/unit/test_resolve.py`,
`tests/unit/test_corridor.py` (+ `tests/helpers.make_ctx/trip/town_point`).
Command: `python3 -m unittest tests.unit.test_resolve tests.unit.test_corridor -v` → `Ran 19 tests` / `OK`.
Decisions / deviations:
- `PlanContext` carries the ports (`Ports`), memoised `region_at` (key = coords rounded to 2 decimals, A§5.3.5),
  parsed opening hours, the 1-km `Profile` cache, `fuel_warnings`, `rerun` counter, and `stop_cost`
  (per-stop cost injected by the engine from `cost.model`; A§3.1 forbids `pipeline → cost`).
- `normalize_input` also rejects `adults + children > 8` (Manager decision OI-07), user vias together with a
  ready route, and an unknown ready route (`NotFound`). `round_trip=None` → the template's `round_trip`.
- `base_route.toll_warnings` returns TOLLS_UNAVOIDABLE separately (A§6.1 gives `build_base_route -> Route`).
- `corridor.place_fixed` builds VIA stops at waypoint km and projects template `stop` sights onto the pass
  between their neighbouring waypoints.
- Lodgings are projected with radius `town + lodging_from_town` (35 km) so a town's own hotels are always found.

## DEV-010 — Stages 4–5

Status: done. Files: `pipeline/{day_split,overnight}.py`, `tests/unit/test_day_split.py`,
`tests/unit/test_overnight.py`.
Command: `python3 -m unittest tests.unit.test_day_split tests.unit.test_overnight -v` → `Ran 18 tests` / `OK`.
Decisions:
- `N > max_days` → `InvalidInput("dailyKm", "too_many_days")` (A§6.4 does not say what happens).
- Day-start estimate for the ETA in the E term: day 1 = `start_at`, day d = 09:00 local on start date + d−1.
- Extra-day (F3) success: the choice for the first failing day is marked `extra_day` and one NO_LODGING
  (detail `extra_day`) is raised for it.
- Template night town without a passing lodging: fallback stays `template`, hotel `None`, NO_LODGING
  (detail `template_no_hotel`) — never a non-passing hotel.
- NO_LODGING message = SPEC text + «. Ближайшая подходящая: …» when a nearest passing lodging exists; the
  detail carries `nearest=<place id>`.

## DEV-011 — Timeline and stage 6 fuel

Status: done. Files: `pipeline/{timeline,fuel}.py`, `tests/unit/test_timeline.py`, `tests/unit/test_fuel.py`.
Command: `python3 -m unittest tests.unit.test_timeline tests.unit.test_fuel -v` → `Ran 15 tests` / `OK`.
Decisions / deviations:
- `build_day_plans(route, overnights, fixed, inp, ctx, pts, profile)` — two extra parameters (start/finish
  labels from the resolved waypoints; the shared profile).
- The plan schedules on the same 1-km resampled profile that `EngineState` persists, so `replace_stop`
  re-schedules identically.
- `fuel.range` reason param `km` = distance from the previous fill to the 20 % point (always positive);
  the last fill of a round trip gets `fuel.last`. FUEL_GAP detail is `km=<trigger>` (used by the golden
  `fuel_range` invariant to model the virtual refuel).
- A via at the overnight town is merged into the OVERNIGHT stop.

## DEV-012 — Stages 7–8

Status: done. Files: `pipeline/{rest,meals}.py`, `tests/unit/test_rest.py`, `tests/unit/test_meals.py`.
Command: `python3 -m unittest tests.unit.test_rest tests.unit.test_meals -v` → `Ran 12 tests` / `OK`.
Decisions:
- Rest windows are measured on a per-day drive clock (driving + detours, no dwell). Ties → the candidate
  closest to R (later km), then id; with that rule 6 h of driving gives 2 / 3 / 1 rests (calm / more_stops /
  just_drive) as the acceptance requires.
- Fixed an off-by-equality bug: a break exactly R minutes after the previous one no longer triggers another
  rest (strict `>`); window bounds get a 1e-6 km tolerance (inverse-profile float noise).
- Lunch candidates must also keep every sight of the day open (cheap check, avoids a re-run).
Full suite at this point: `python3 -m unittest discover` → `Ran 153 tests` / `OK`.

## DEV-013 — Stages 9–10

Status: done. Files: `pipeline/{sights,schedule}.py`, `tests/unit/test_sights.py`, `tests/unit/test_schedule.py`.
Command: `python3 -m unittest tests.unit.test_sights tests.unit.test_schedule -v` → `Ran 15 tests` / `OK`.
Decisions:
- Sights are inserted greedily by score; a sight stays only if the day is within budget, every sight's whole
  visit is inside its hours and the lunch stop (if any) still arrives in 12:00–14:30.
- Re-run: the bad days drop non-fixed, non-auto sights (lowest score, tie → later km); then all auto stops
  go, day starts are re-derived, stages 6–9 run once more (`ctx.rerun += 1`, fuel warnings replaced). Stage
  modules are called through their module attribute so the `plan_fuel` spy works.
- `PlanContext.warning(code, day_no, detail, /, **params)` is positional-only (the DAY_OVER_BUDGET template
  itself has a `day` parameter).
- Output rounding helpers (`stop_km_from_prev`, `day_km`, `drive_minutes`) live in `schedule.py` (A§6.10) and
  are used by assemble.

## DEV-015 — Cost model, recompute, contract (done before DEV-014, see task order note)

Status: done. Files: `verst_planner/cost/{money,formulas,recompute,model}.py`, `tests/unit/test_cost.py`,
`tests/contract/cost_recompute_cases.json` (31 cases), `tests/contract/test_cost_recompute_contract.py`.
Command: `python3 -m unittest tests.unit.test_cost tests.contract.test_cost_recompute_contract -v` →
`Ran 19 tests` / `OK`.
Design (A§3.1 forbids `cost → pipeline/ports/geo`):
- `cost.model.CostInput` holds trip facts as domain data (region km with prices, toll hits with local entry
  time, nights with hotel/options/default price/town check, per-day lunch facts, sights). The pipeline fills
  it; `build_units` applies every SPEC §8 rule ([D-6] meals, breakfast after nights whose hotel has none,
  toll night window, rooms [D-15], ages [D-14], `as_of`) and `recompute` (the reference algorithm, also run
  offline) produces the `CostResult`. `compute_cost = recompute(build_units(...))`, so server and offline agree
  by construction.
- Breakfast is a property of `NightUnit` (it changes with the hotel override), not a `MealUnit`.
- Tolls are aggregated per road in the formula («М-12: 3 500 ₽»), one breakdown row per hit («М-12, днём»).
- `CostUnits.mood_just_drive` added (offline hint rule needs the mood).
- Fuel prices in formulas always show kopecks («62,00 ₽», copy review R-4); the multi-region average is
  rounded to 0,10 ₽ first (A§7.1).
- Contract expected values come from an independent naive implementation of A§7.2 in the generator script
  (not from `recompute`); both agree on all 31 cases. Canvas case: 3 720 / 0 / 12 000 / 12 600 / 3 000,
  reserve 3 130, total 34 500, per person 11 500, remaining 5 500.

## DEV-016 — Explanations and share text (done before DEV-014)

Status: done. Files: `explain/{reasons,share}.py`, `tests/unit/test_reasons.py`, `tests/unit/test_share.py`.
Command: `python3 -m unittest tests.unit.test_reasons tests.unit.test_share -v` → `Ran 9 tests` / `OK`.
Decisions:
- Overnight reason: template → `overnight.template`; no hotel → `overnight.no_hotel`; widened →
  `overnight.widened`; otherwise `other` = the considered town closest to the target; `dkm < 10` →
  `overnight.on_target`; else shift (`later`/`earlier`, or `limit` when there is no other town before the
  target) + dominant factor (ties: hotels, then quality); `overnight.cap_ok` appended when day km ≤ daily km.
- VIA stops have an empty reason (they are user/template waypoints, not engine choices; no A§8.1 key).
- Share text = A§8.2 exactly; START lines use the departure time, all others the arrival.

## DEV-014 — Stage 11 alternatives, assemble, `Planner.plan` / `replace_stop`

Status: done. Files: `pipeline/{alternatives,assemble}.py`, `verst_planner/engine.py` (plan + replace; events,
cancel and `recompute_cost` are also in place for DEV-017), `tests/unit/test_alternatives.py`,
`tests/unit/test_replace.py`, `tests/helpers.make_planner`.
Command: `python3 -m unittest tests.unit.test_alternatives tests.unit.test_replace -v` → `Ran 13 tests` / `OK`.
Decisions / deviations:
- An alternative must keep the stop's neighbours (same index after insertion) and the same place type as the
  stop (a coffee stop gets coffee stops, a rest area rest areas). With that, `shift_min` (defined as the
  arrival shift of the next stop) equals `delta_min` and the offline shift is exact; A§6.11 defines `shift`
  via the rejoin time, which differs from the later-stop shift when the alternative is at another km.
- Fuel alternatives keep every gap between fills within the full-tank range (skipped when a FUEL_GAP exists).
- `replace_stop` rebuilds the day from `EngineState` (stop states now also carry reason key/params, meal,
  litres, coffee; `town_kms` persists the corridor towns), re-reads place bodies with
  `PlaceRepository.get_places`, keeps the other stops' rendered fields, re-renders times/km, recomputes that
  day's alternatives from the persisted candidates, and folds the alternative's `AltUnits` into
  `cost.units` before `recompute` (server cost == offline `recompute(units, …, replaced={…})`, tested).
- `CostInput` is built in `engine.py` (A§3.1: pipeline may not import cost). `defaults_as_of` = the oldest fuel
  price date (the ports expose no defaults date).
Full suite: `python3 -m unittest discover` → OK (see DEV-017 for the count).

## DEV-017 — `Planner` facade, events, cancellation, CLI

Status: done (acceptance 2 is re-run after DEV-018 creates the G01 case file, see DEV-018).
Files: `verst_planner/engine.py`, `verst_planner/cli.py` (`plan`, `share`, `export-config`),
`verst_planner/__init__.py` (re-exports `Planner`, `TripInput`, `TripPlan`), `tests/unit/test_engine.py`,
`tests/unit/test_cli.py`.
Command: `python3 -m unittest tests.unit.test_engine tests.unit.test_cli -v` → `Ran 14 tests` / `OK`.
Performance: Москва → Волгоград → Москва, 1 981 km, planned in 0.108 s (budget < 1.0 s).
Decisions:
- Event order exactly A§8.3; the pre-stage-2 `cancel.check()` runs before the first `stage` event, so a sink
  that cancels on the first event stops the plan after one routing call (`test_cancel_before_corridor`).
- Final `stop` events are emitted after assembly (they carry the final ids `d{day}s{nn}`).
- `stage.fuel` shows consumption with one decimal («Считаем бензин: 8,0 л на 100 км», copy review R-4).
- `recompute_cost` changes cost (and, for a hotel choice, the overnight stop's selected hotel, tags and
  cost); the input's crew/budget/reserve are updated to the patch; days and engine state are untouched.
- `export-config` is used by DEV-021 to generate `0002_app_config.sql`.
Full suite: `python3 -m unittest discover` → `Ran 223 tests` / `OK`.

## DEV-018 — Golden trips, invariants, contracts, layering

Status: done (Manager review of the expectations pending, as per the backlog).
Files: `tests/golden/{__init__,test_golden,invariants,export_contracts}.py`, `tests/golden/cases/G01…G12_*.json`,
`tests/golden/snapshots/G01…G08, G11, G12` (error cases G09/G10 have none), `tests/test_layering.py`,
`docs/contracts/plan-response.example.json` (G02), `docs/contracts/share-text/G01…G08.json`.
Commands:
- `python3 -m unittest tests.golden.test_golden -v` → `Ran 12 tests` / `OK` (each runs the 15 A§13.3
  invariants as subTests + the expectation groups + the snapshot).
- `python3 -m unittest tests.test_layering -v` → `Ran 3 tests` / `OK`; appending `import pydantic` to
  `verst_planner/hours.py` made it fail («non-stdlib import pydantic»), reverted.
- `ls backend/planner/tests/golden/cases | wc -l` → `12`; all cases load; G02 and G03 (the cases with
  `costTotalRub`) have 7 and 8 `costWorkings` lines.
- `python3 -m tests.golden.export_contracts` twice → identical sha1 of all 9 contract files
  (`git diff --stat -- docs/contracts` prints nothing; the files are new/untracked until the Manager commits).
- Editing `"km": 545 → 546` in the G01 snapshot → `snapshot mismatch` with the unified diff and
  `G01_msk_yar_round.actual.json` written; reverted → `OK` and the `.actual.json` removed.
- DEV-017 acceptance 2: `python3 -m verst_planner.cli plan --world fixtures/worlds/central_russia_v1.json
  --input tests/golden/cases/G01_msk_yar_round.json --events > /dev/null` → exit 0, 21 JSON lines on stderr.

Initial failing run (cases written before any snapshot existed), recorded per acceptance 6:
`FAILED (failures=2, errors=10)` — 10 × missing snapshot (expected), plus:
1. G03 `costTotalRub` 16 100 vs hand 17 100 (−5.8 %). Investigation: fuel (4 840) and lodging (5 200) matched my
   working exactly; my food/tickets working was wrong — I had assumed a 700 ₽ day-1 lunch and the Мичурин
   museum without doing the ETA analysis. Re-derived by hand (in the case file): at the meals stage
   «У дороги» (500 ₽) scores 6.7 vs «Ямщик» 6.5; the free Скопинское городище outranks the museum, and the
   museum would push lunch past 14:30 → food 4 630, tickets 0, total 16 100. Expectation corrected, tolerance
   kept at 5 %.
2. G06 `kmRange` 843 vs [814, 840]. Investigation: per A§6.8 the day-2 narrow rest window [60, 90] min contains
   only a coffee station on the parallel М-12, 6.4 km off the М-7 (detour 16.6 km); the rest area at km 487
   arrives at 58.9 min, just outside. The engine follows A§; my range had not allowed for the detour →
   range re-derived as [814, 850]. Raised to the Architect (see open questions).
One engine bug was found while reviewing the actual plans before generating snapshots: G07 placed the fixed
Ясная Поляна on the return pass (km 216, after Щёкино) because `project_all` merges two passes closer than
2·radius + 5 km. Fixed with `PolylineIndex.nearest_in_range` (test `test_nearest_in_range_splits_close_passes`);
Ясная Поляна is now at km 198, 09:17–11:17 on Sunday (open Tu-Su 09–17).
Disclosure: while debugging stage 11 I had printed G02's plan (total 32 300) before writing the case; the
G02 `costWorkings` are a full derivation from the world data and the A§ rules (region km × price, hotel
scores, lunch scores at their ETAs, sight selection by budget/hours, D-6 meals) and reach the same value.

Decisions:
- `OvernightReason.fallback` added (wire `reasons.overnights[].fallback`) — the golden cases assert fallbacks
  and the client needs the no-hotel state; route refs are checked through a recording routing wrapper (they
  are not in the plan payload).
- `fuel_range` models FUEL_GAP virtual refuels from the warning `detail` (`km=<trigger>`), so G11 runs the full
  invariant list. `alternatives` checks `replaceable == (kind replaceable and not a template stop)`.
- Expectation keys beyond A§13.2 used by the runner: `maxDayKm`, `warningsContain`, `stopKmRange`,
  `costFormulaContains`, `costBreakdownContains`, `remainingIsBudgetMinusTotal`, `roadRefs`, `viaBeforeFinish`,
  `rerun`, `overBudgetDays`, `errorPointIndex`.
- G04 plans to ≈ 10 h on the road (just_drive budget 600 min) and raises DAY_OVER_BUDGET — consistent with the
  hand estimate (483 min driving + stops with motorway exits ≈ 605 min); its case does not pin warnings.
Full suite: `make check` → `Ran 239 tests` / `OK`; ruff `All checks passed!`; mypy `Success`.

## DEV-019 — Sandbox coverage tool, Makefile, README check

Status: done. Files: `backend/planner/tools/stdlib_coverage.py` (Makefile `coverage-planner` already from DEV-001);
also `tools/gen_worlds.py` and `tools/gen_cost_contract.py` (the generators of the fixture worlds and of the
cost contract — re-running them reproduces the committed JSON byte-for-byte; ruff per-file ignores for
Cyrillic text/wide tables).
Commands:
- `make coverage-planner` → per-file table, `TOTAL 4389 129 97.1%`, `tests: 239 run, 0 failures, 0 errors`,
  exit 0 (≈ 18 s under tracing).
- `cd backend/planner && python3 tools/stdlib_coverage.py --fail-under 101` → `FAIL: total coverage 97.1% is
  below --fail-under 101.0%`, exit 1.
- `make check` → exit 0 (`All checks passed!` / `Success: no issues found in 51 source files` / `Ran 239 tests` /
  `OK`).
- README «Run the tests», verbatim from the repo root: all five commands exit 0; `make golden-update` exit 0
  with snapshots unchanged; the README CLI example exits 0 (37 KB JSON, 30 event lines).
Rules of the tool: executable = `ast` statements minus `if TYPE_CHECKING:` blocks, `...` bodies, docstrings
and `# pragma: no cover` lines (a marked compound statement excludes its block); a compound statement counts
when any line of its header ran; `try:` headers are not counted (they emit no line event). The tracer is
installed before test discovery so import-time lines count.

## DEV-021 — SQL DDL and seed skeleton (written, not executed)

Status: done. Files: `backend/migrations/sql/0001_initial.sql` (A§9.2 block, verbatim),
`backend/migrations/seed/0001_regions.sql` (the 16 regions of DEV-008, `geom` NULL, upsert),
`backend/migrations/seed/0002_app_config.sql` (generated by `python3 -m verst_planner.cli export-config`:
`planner` and `reasons_ru` rows, upsert). `backend/migrations/.gitkeep` removed (the folder has content now).
Command: `diff <(python3 -c "import re;s=open('docs/architecture.md').read();print(re.search(r'\`\`\`sql\n(CREATE
EXTENSION.*?)\`\`\`',s,re.S).group(1),end='')") backend/migrations/sql/0001_initial.sql` → no output.
The JSON inside `0002_app_config.sql` parses back to 22 planner keys and 47 template keys.
Execution against PostGIS is DEV-B02 (BLOCKED-ON-NETWORK).

## Summary — Sprint 1 developer scope (DEV-001…DEV-019, DEV-021; DEV-020 skipped as instructed)

Final state: `make check` → ruff `All checks passed!`, mypy `Success: no issues found in 51 source files`,
`Ran 239 tests` / `OK` (no skips); `make coverage-planner` → `TOTAL 4389 129 97.1%`; no TODO/TBD/FIXME.

Deviations from A§ (all listed above with reasons, collected here):
1. Layering rule 2 read as domain → domain only, geo → domain + geo; `Corridor` lives in `pipeline`.
2. Model extensions: `NormalizedInput.tz`; `PlannedStop.litres/coffee`; `OvernightChoice.nearest*/region/detour`;
   `Alternative.units`; `HotelPrice.breakfast_included`; `CostUnits.as_of`, `.mood_just_drive`;
   `CostResult.hints_ru`; `OvernightReason.fallback`; `EngineState.days/candidates/rerun/town_kms`, `StopState`
   with reason/meal/litres/coffee — all needed by replace/offline recompute/golden checks.
3. `strings.ru.json` holds the non-template Russian strings (reasons JSON = exactly the A§8.1 keys).
4. `pipeline → cost` forbidden: per-stop cost injected via `PlanContext.stop_cost`; `CostInput` built in
   `engine.py`; `cost.model` works on domain data only.
5. Stage signatures: `build_day_plans(…, pts, profile)`, `choose_overnights(…, profile=None)`,
   `build_base_route` + separate `toll_warnings`.
6. Alternatives keep their neighbours and place type; `shift_min` = arrival shift of later stops.
7. Fixed template stops are placed with `PolylineIndex.nearest_in_range` (pass grouping merges close passes).
8. Normalisation also enforces adults + children ≤ 8 (Manager OI-07), rejects vias with a ready route, and
   `N > max_days` → `InvalidInput("dailyKm", "too_many_days")`.
9. М-4 modelled toll-free in `central_russia_v1` (Sprint-2 G18 adds the segments).
10. `docs/design/.gitkeep` not created (canonical design folder is `design/`).
11. Copy review R-1…R-4 applied (Manager instruction); `fmt_consumption` («8») kept for formulas per A§7.2,
    one-decimal form («8,0») for the Drive stage line.

Open questions for the Architect / Manager:
- Q-A (A§6.8): the narrow rest window takes any candidate even with a large detour (G06 day 2: a coffee 6.4 km
  off the route on the parallel М-12, 27 min detour, while a rest area arrives 1 min before the window).
  Proposal: widen when the best narrow candidate's detour exceeds its dwell, or cap rest-pool lateral at 5 km.
- Q-B (A§6.1 order): meals run before sights, so a day whose sights move the schedule into 12:00–14:30 gets no
  lunch stop (G07 day 1, G08); the lunch is still costed. Proposal: run `plan_meals` once more after stage 9
  for days without a lunch that now overlap the window.
- Q-C (A§6.11): pools are small after a round trip uses each roadside place once and fixed long stops push
  candidates outside ±45 min, so many stops have 0–1 alternatives (SPEC asks for 2–3). Proposal: allow places
  used on the other pass of a round trip, or widen the window for rest stops.
- Q-D: `CostLine.as_of` uses the oldest fuel price date as the "defaults" date because the ports expose none;
  a `PriceRepository.defaults_as_of()` port method would make it exact.
- Q-E: G04 (Москва → Казань, just_drive, 790 km) ends at 16:58 and raises DAY_OVER_BUDGET by a few minutes
  (motorway exits add 9 min per stop); confirm this is the intended behaviour for a 10 h budget.
- Architect sign-off of 10 world coordinates (DEV-008 acceptance 2) and Manager review of the G01–G12
  expectations (DEV-018 acceptance 6) are pending.

---

# Sprint 1 rework (Manager verdict 2026-10-23, A§16) — R-01 … R-14

Final state: `make check` → ruff `All checks passed!`, mypy `Success: no issues found in 52 source files`,
`Ran 268 tests` / `OK`; `tools/stdlib_coverage.py --fail-under 85` → `TOTAL 4719 124 97.4%`. Alternatives
coverage gate (G01, G02, G03, G06, G07, G08): `G01 10/10, G02 6/8, G03 6/9, G06 10/13, G07 5/5, G08 4/6;
total 41/51 = 80%` (baseline 23 %).

## R-01 Breaks and rests (A§16.2, D-17)
- Execution order (first pass and re-run): 6 fuel → 8 lunch → 9 sights → 8b → 7 rests → 10 → final repair
  (`schedule.run_stages`, engine inlines it to keep the progress events in place).
- `rest.plan_rests_day`: gaps between breaks (start + stops with dwell ≥ 15) longer than R; step 1 upgrades
  a range fuel stop with a cafe in `[max(G, R−60), R+15]` to coffee; step 2 admissible candidates (unused,
  inside the day, detour ≤ `rest.max_detour_min` 10, ≥ G after b0, ≥ min(G, gap − R) before b1) in
  `[R−30, R]`, else `[max(G, R−60), R+15]`; else a virtual break. Tie: closer to R, then id.
- Config: `rest.max_detour_min = 10`, `rest.min_gap_min = 60` (seed 0002 regenerated).
- Driving for `rest.generic` = arrival at the rest − arrival at the previous break (incl. detours), rounded
  to 15 min. A short sight used as a rest keeps `sight.default`.
- New `PlannedStop.pool` / `StopState.pool` (`rest|fuel|food|sight`) records the stage pool (needed by the
  repair, the alternatives and `break_spacing`).
- Decisions: (a) the stage-6 coffee upgrade (A§6.7) is removed — coffee only where stage 7 needs a break;
  (b) the G lower bound also applies to step 1 (`max(G, R−60)`), so `break_spacing` holds for coffee too;
  (c) `day_ok` (stage 9 and the lunch probes) plans the rest reserve on a copy with `strict=False` (rests are
  placed even if they would break a lunch/sight), so a lunch or sight that only fits without its rests is
  rejected; the real stage 7 is strict (never breaks hours/lunch → virtual break instead). Without (c) the
  first lunch of G06 sat at 14:29 and every later rest was rejected.
- (d) Feasibility budget of `day_ok` = `max(day_budget_min, drive + auto + fixed stop time)`: the budget limits
  optional content only; without the fixed term G12 could never get a lunch.
- Invariants `break_spacing` (stage-7 stop ≥ G − 1 min after the previous break, detour ≤ 10) and
  `rest_reason`. An upper bound is not asserted: virtual breaks are not visible in the plan.
- First run: all new rest tests passed at once; G11 keeps no rest (rules: the only areas are 44 or 117 min
  after the start/virtual break, or < min(G, gap − R) before the lunch) — consistent with A§16.2.

## R-02 Lunch after sights (D-18)
- `sights.plan_lunches` (stage 8 with `day_ok`) and `plan_lunch_after_sights` (8b). 8b simulates the drops on
  a copy (lowest sight_score, tie later km); if no lunch fits even with every stage-9 sight dropped, nothing
  is dropped ("no feasible food place").
- Invariant `lunch_present` (opt-out `expect.noLunchDays`, unused now: G12 got its lunch after (d)).

## R-03 Vias (D-21)
- Ready-route vias produce no stop (`corridor.place_fixed`); user vias: reason `via.user`, dwell 30, `city`,
  never replaceable. Template `via.user`/`alternatives.*` added to `reasons.ru.json` and `TEMPLATE_KEYS`.

## R-04 Repair, STOP_CLOSED, over budget (D-20)
- `checks.py` (new): `in_window`, `covers_lunch_window`, `closed_sights`, `lunch_out_of_window`,
  `day_valid`, `mandatory_min`, `budget_limit`, `over_budget`.
- `DAY_OVER_BUDGET` iff `duration > max(budget, mandatory_min)`; G04 now has no warning (Q-E closed).
- `schedule.final_repair`: per day, repeat until clean: drop a closed sight (fixed → `STOP_CLOSED`, detail
  `place=<id>`), drop a lunch out of window and re-plan 8b once, re-plan the day's rests
  (`remove_rests` + `plan_rests_day`); every change re-checks, so the invariants hold by construction.

## R-05 Alternatives (D-19)
- Any position, any kind from the stop's stage pool; `Alternative.day_patch` (`StopTime`), `ScheduledStop.
  alternatives_note_ru` (`alternatives.none/one`), codec `dayPatch` / `alternativesNote`; `shift_min` is the
  arrival change of the next stop in the new order; `delta_rub` per A§16.6 (exact per-stop cost, fuel stops 0,
  + Δdetour × consumption × price(region of c)); `AltUnits.price_rub` + `region_name_ru`.
- `Planner.replace_stop` rebuilds the day with the same `trial_day` → equals `day_patch` (tested for every
  alternative of the G03-like plan).
- `recompute`: an alternative in a region the trip did not cross (and Δkm > 0) adds that region; a non-sight
  stop replaced by a sight adds its ticket. `_units_after_replace` bakes exactly the same rules.
- **Deviation (needs Architect OK):** a candidate within `CLUSTER_KM = 2 km` of the replaced stop (same town)
  takes the replaced stop's slot, its km clamped to the neighbours. With strict km order, same-town candidates
  landed after the lunch of that town and arrived +50…+115 min later (the main reason for 0–1 alternatives).
- World enrichment in `gen_worlds.py` (`EXTRA_SIGHTS` 68, `EXTRA_CAFES` 36): second-choice sights/cafés in
  the towns of the golden trips; «Ботик Петра I» renamed «…Петра Первого» (Latin «I» broke `russian_text`).
- Invariants: `alternatives` (no kind restriction; day patch covers the day, keeps the seqs, matches the
  rendered alternative) and `alternatives_note`; gate test `AlternativesGateTest` (aggregate ≥ 70 %).

## R-06 Cost patch (A§16.9)
- `recompute_cost` rejects `dog` changes and `children` 0 ↔ > 0 (`InvalidInput("crew","replan_required")`);
  after any crew change `_recrew_day` re-renders stop `cost_rub` (tickets, lunch, rooms), hotel options
  (rooms, crew price) and the alternatives' cost and `delta_rub`.

## R-07 Template fit (A§16.4)
- `template_fits` requires a crew-passing lodging in each night town; `passes` moved to `day_split` (imported
  by `overnight`, no cycle); the `template_no_hotel` path is gone (asserted).

## R-08 `.limit`
- `OvernightChoice.day_start_km`; `.limit` dkm = `day_start_km + daily_km − km_at` → G03 «На 33 км раньше
  вашего предела…».

## R-09 Cost presentation (A§16.7)
- `FuelUnits.trip_km` (= `TripPlan.km`, codec `tripKm`) is shown in the fuel formula (+ replaced Δkm offline);
  `PriceRepository.defaults_as_of()` (fake: world `asOf`) replaces the oldest-fuel stand-in;
  `PlanContext.default_check_at(km)` is the one default check for lunch stops and the food line.
  `fuel.evening` already won over `fuel.last` (only `fuel.range` becomes `last`), now tested. Invariant
  `formula_km`.

## R-10 Coupling
- `PlanContext.region_info(code)`; `grep -n "ctx\._" verst_planner/engine.py` prints nothing (test
  `test_layering.test_engine_uses_public_context`).

## R-11 Goldens
- First run after R-01…R-10 (old expectations): `FAILED (failures=11)` — 10 snapshots + G02 `costTotalRub`.
- Every expectation re-derived by hand (costWorkings in each case), then run again before regenerating:
  `FAILED (failures=10)` — snapshot mismatches only; all expectations and invariants passed. Then
  `make golden-update` and `python3 -m tests.golden.export_contracts`.
- `costTotalRub` (±5 %) now in every non-error case; `warnings` exact everywhere (G05 `["NO_LODGING"]`, G11
  `["FUEL_GAP"]`, G04/G07 `[]`); line tolerances: fuel 5 %, others 0 % (G02 food 11 250 / tickets 3 700 exact);
  G06 `kmRange` [814, 840] (832); G07/G08 food [1, 1]. Totals: G01 16 500, G02 33 800, G03 16 200, G04 8 900,
  G05 11 500, G06 17 700, G07 21 600, G08 5 700, G11 3 000, G12 3 900.
- Disclosure: the plans' structure (which sights/lunches) was visible to me from debugging runs while I wrote
  the workings; each pick in the workings is justified by the stage rule and world values, and where the rule
  is within detour noise (G01 day-2 lunch) the alternative total is stated.

## R-12 Hygiene
- Generators run in memory (`VERST_GEN_IN_MEMORY=1`, `GENERATED` / `TEXT` globals); tests
  `test_worlds.test_generator_matches_committed_json` and the contract's `test_generator_matches_committed_json`.
- Contract: 34 cases (+ `replaced_new_region_priced`, `replaced_rest_by_sight`, `trip_km_formula`) and an
  expected `fuelFormulaKm` per case.

## R-13
- `test_engine.test_engine_state_size_1500km`: 1 981 km round trip → 101 710 bytes (limit 400 KB).

## Open for the Architect / Manager
- The `CLUSTER_KM` slot rule (R-05 deviation above).
- Removing the stage-6 coffee upgrade, `strict=False` reserve and the fixed-stop term in the feasibility
  budget (R-01 c/d) are interpretations of A§16.2/16.5 — please confirm.
- Per case, G03 (67 %) and G08 (67 %) are below 70 % (G01 100, G02 75, G06 77, G07 100); the gate is applied
  to the six cases together (80 %). If the gate is meant per case, G03 needs more Р-22 roadside cafés/fuel, G08 more Суздаль
  sights.

---

# Round 2 (A§16.11) — R2-01 … R2-05

Final state: `make check` → ruff `All checks passed!`, mypy `Success: no issues found in 52 source files`,
`Ran 273 tests` / `OK`; `python3 tools/stdlib_coverage.py --fail-under 85` → `TOTAL 4730 120 97.5%`.

## R2-01 Break upper bound (A§16.11.1)
- Virtual breaks removed. After steps 1–2: step 3 extended window (detour ≤ `rest.extended_detour_min` = 15,
  driving since b0 ∈ [max(45, R − 60), R + 30]); step 4 roadside break: `PlannedStop(REST, place=None,
  «Остановка у дороги», 15 min, pool rest, reason rest.roadside)` at the km where the clock reaches R
  (`rest.roadside_break`, point interpolated on the route, `RestPool.of(corridor)` carries the route).
  Rendered sign `rest`, `placeId` null, `verified` true, not replaceable (`family()` → None, render rule
  `replaceable` needs a place), no alternatives note.
- Gap detection: a gap closed by a break this stage placed after R (widened ≤ R + 15, extended ≤ R + 30,
  coffee upgrade) is recorded in `accepted` and not re-opened — without it the extended pick at 117 min in
  G11 triggered a second roadside break 27 min before it.
- `break_spacing` now asserts driving between breaks (dwell ≥ 15, start, overnight, finish) ≤ R + 30 + 1;
  its lower bound for stage-7 stops is min(G, 45) (the extended window starts at 45) and the detour bound is
  `extended_detour_min`.
- Tests: `test_rest.test_no_gap_over_R_plus_30`, `test_roadside_break_when_no_place`,
  `test_extended_window_before_roadside` → ok. Updated: tests that expected "no stop" for an empty pool now
  expect roadside breaks; three tests pin `rest_interval_min` high to keep their minute arithmetic
  (`test_visit_must_fit_hours`, `test_sight_dropped_for_lunch`); `test_fixed_overflow_warns` 640 → 655
  (+ one roadside break).
- Goldens: G11 day 1 is now 117 / 74 / 51 / 90 min between breaks (was 242); G05 day 2 sight → lunch is 109 min
  (x = R lies within 30 min of the finish, so §16.2's "remaining drive" rule adds nothing) ≤ 120. No golden
  needed a roadside break.

## R2-02 Formula km after replace (A§16.11.4)
- `AltUnits.trip_km_delta` (codec `tripKmDelta`) = rounded trial-day km − rounded current-day km; recompute
  shows `trip_km + Σ trip_km_delta`. Rule 1 no longer pushes a delta into the first region (missing region
  with Δ ≤ 0 → no change); baked units clamp a region at 0 km. Rule 4 via `recompute.effective_tickets`
  (replaced ticket removed, sight alternative adds its own; the `fewer_sights` hint uses the effective list);
  `_units_after_replace` reuses it.
- `test_replace.test_offline_formula_km_matches_server` (every alternative of G01–G08, > 100 replaces) → ok.
- Contract: 39 cases (+ trip_km_two_replaces, replaced_fuel_same_region, replaced_region_drops_to_zero,
  replaced_lunch_null_check, replaced_sight_by_rest); the rule list of A§16.11.4 is the generator docstring
  with the cases per rule; `test_case_count` requires ≥ 35.

## R2-03 Slot rule hygiene (A§16.11.3, 16.11.5)
- `alternatives.cluster_km` (2.0) in config/seed; `trial_day` asserts the clamp moves ≤ cluster_km and the
  candidate keeps its point, detour and region.
- `test_alternatives.test_coverage_on_mini_world`: controlled corridor (one candidate before and after each
  rest / lunch / sight / range fuel stop) → every replaceable stop has ≥ 2 alternatives.
- Gate per case ≥ 60 % + aggregate ≥ 70 %: `G01 10/10 = 100%, G02 6/8 = 75%, G03 6/9 = 67%, G06 10/14 = 71%,
  G07 5/5 = 100%, G08 4/6 = 67%; total 41/52 = 79%`.

## R2-04 Goldens
- G05 and G11 re-derived by hand (breaks, fuel, food); G01 day-2 and G06 day-1 lunches written as the
  numeric lunch_score of every feasible candidate at its ETA (incl. −detour/5); winners pinned in
  `mustIncludePlaceIds` (`pl_prs_cafe_lake`, `pl_m7e_cafe_135`; the G06 tie 5.1/5.1 is broken by the lower
  km). Every fuel working is region by region (route km split at the nearest world node's region + stop
  detours, km × 0.08 × price) — G08 gives 1 130 against the engine's 1 140 (10-km buckets), within ±5 %.
- G06 total 17 700 → 18 200 (Дмитриевский собор is back on day 1 after the rest change: tickets 1 000).
- First failing run with the new expectations: `FAILED (failures=9)` — snapshot mismatches only (G12's
  snapshot was unchanged); then `make golden-update`, `python3 -m tests.golden.export_contracts`, seed
  `0002_app_config.sql` regenerated (`extended_detour_min`, `cluster_km`, `rest.roadside`).
- Totals: G01 16 500, G02 33 800, G03 16 200, G04 8 900, G05 11 500, G06 18 200, G07 21 600, G08 5 700,
  G11 3 000, G12 3 900.

---

# Sprint 2

## DEV-110 Zip-safe resource loading
- New `verst_planner/resources/__init__.py`: `read_text(name)` via `importlib.resources.files(...)`, fallback
  `Path(__file__).parent / name`; `DIR` replaces the three `RESOURCES = Path(__file__)…` constants (kept as
  aliases for `cli export-config` and tests). `config.py`, `explain/ru.py`, `explain/templates.py`, `cli.py`
  use the helper; layering rules allow `config`/`explain` → `resources`.
- `tests/unit/test_packaging.py`: `test_import_from_zip` (subprocess `python3 -I`, `sys.path = [vp.zip]`,
  config/templates/strings load, G02 output == snapshot bytes), `test_no_file_reads_outside_helper` (AST),
  `test_resources_helper`. Proof of the bug: with the helper removed the zip test fails with
  `NotADirectoryError: …/vp.zip/verst_planner/resources/planner_config.json`.
- `python3 -m unittest tests.unit.test_packaging -v` → `Ran 3 tests` / `OK`; snapshots unchanged; seed unchanged.

## DEV-111 `verst_planner/mobile.py`
- M§5.1 in full: envelope `{ok, result|error, ms}`, never raises (`INVALID_INPUT` for malformed arguments,
  `INTERNAL` with traceback in `detail` and on stderr, `NO_WORLD`, `TZDATA_MISSING`, planner codes);
  `load_world`, `selfcheck`, `set_clock` (`system`/`golden`/ISO with offset), `suggest`, `popular`
  (extra optional `origin_id`, default = most populous town), `reverse`, `ready_routes` (`bearing8` hub → first
  via), `plan` (listener `onEvent(str)`, swallowed errors logged once, cancel token per request id under a
  lock), `cancel`, `replace_stop`, `patch_cost`, `share_text`, `golden_snapshot`; CLI `selftest [--world]`.
- Suggestion subtitles use the approved copy `navigator_sub_city` «город · {region}» and `navigator_sub_place`
  «место · {region}» (design/copy-ru.md), stored as `suggest.sub.*` in `strings.ru.json`.
- Additions outside mobile: `codec.crew_from_json` (public alias), `cli.read_file` (file reads stay in cli).
- `python3 -m unittest tests.unit.test_mobile -v` → `Ran 21 tests` / `OK`; `python3 -m verst_planner.mobile
  selftest` → 26 `OK` lines, exit 0; coverage `verst_planner/mobile.py 324 7 97.8%`.

## DEV-112 Kotlin contract exports
- `tools/gen_mobile_contracts.py` → `docs/contracts/replace/` 129 files, `docs/contracts/patch/` 25 files
  (`reserve_off`, `budget_none`, `hotel_<stopId>`); compact JSON (indent 1 was 23 MB, compact 15 MB — still
  large: ask the Manager whether to gzip or to cap alternatives per case).
- `tests.unit.test_mobile_contracts` (byte-for-byte, file set, counts, shape: `after` day == alternative
  `dayPatch`) → `Ran 2 tests` / `OK`.

## DEV-113 Golden tie hygiene (S2-01)
- `tests/golden/ties.py` records the lunch, fuel, rest, overnight-town and hotel picks of every golden plan and
  their two best scores; `TiePicksTest.test_no_pick_decided_by_a_tie` requires margin ≥ 0.05 (30 picks).
- Found two: G06 day-1 lunch 5.1 / 5.1 and G07 hotel 4.25 / 4.22. Fixture: Трапезная Гороховца rating
  4.2 → 4.1, Пряничный двор 4.4 → 4.35; plans and snapshots unchanged; G06/G07 workings updated.
- `rest.rank_rests` factored out (no behaviour change) so the check can observe it.

Python state after DEV-110…113: `make check` → `Ran 301 tests` / `OK`, coverage `TOTAL 5066 121 97.6%`.

## DEV-100 Hello Compose → CI (branch `dev/DEV-100`)
- Worktree `/home/claude/verst-dev`; commits `df0448a` (3 modules, `demo` build type, committed
  `demo.keystore`, wrapper 8.14.3 generated offline in an empty dir) and `e51bcee` (ABI filters).
- Run 2 `40047400263` (df0448a, cold caches): green. build 00:56:01–00:58:58 (2 m 57 s), e2e
  00:59:00–01:01:39 (2 m 39 s), ci-logs 5 s. am-start `TotalTime: 1843`. junit 3/0, lint errors 0, warnings 1.
  Robolectric screenshot via `View.draw` (1170 × 2532, background pixel (20,20,22), text region 222 colours);
  `captureToImage` fallback not needed. Toolchain: Temurin 17.0.20.1, Python 3.12.15, Gradle 8.14.3.
- Run 4 `40047995831` (e51bcee, warm): green. build 3 m 29 s, e2e 1 m 58 s; am-start `TotalTime: 1468`;
  APK 5.57 MB, `abis ["arm64-v8a", "x86_64"]`, device ABI x86_64.
- Deviation: the backlog expects `abis == []` for hello; Compose ships `libandroidx.graphics.path.so` for
  4 ABIs, so `ndk.abiFilters arm64-v8a, x86_64` is set already (the DEV-101 target set).
- Release (acceptance 2, 6) needs the merge to main by the Manager.

## DEV-101 Chaquopy spike (branch `dev/DEV-101`, commit `15b7158`)
- Run 5 `40048288659` green on the first try with Catalog A (no Catalog B, no `extractPackages`).
  build 01:06:54–01:10:20, e2e 01:10:22–01:13:14. `OK (3 tests)`.
- `parity.json`: 10 snapshot cases `"equal": true` (G01 146 ms, G02 126, G03 101, G04 200, G05 33, G06 180,
  G07 52, G08 52, G11 13, G12 10 — total ≈ 0.9 s); G09 `UNREACHABLE`, G10 `TOO_SHORT`.
- `timings.json` (instrumentation process, second start): python 577, import 299, worlds 79, selfcheck 20,
  **total 975 ms**. The true first launch after install (am-start, logcat `VerstEngine`): python 1186,
  import 360, worlds 56, selfcheck 306, **total 1908 ms**. Both under the 4000 ms target.
- Resolved: plugin `com.chaquo.python` 16.0.0, runtime Python **3.12.7** (selfcheck), `tzdata==2025.2` from
  pypi (index also lists chaquo.com/pypi-13.1). Build warning: "Python version 3.12 may have fewer packages".
- APK 43.28 MB (`abis ["arm64-v8a", "x86_64"]`, under 60, just under the 45 warn). largestEntries:
  lib 24 805 600, assets 12 586 408, classes.dex 4 202 434, classes2.dex 1 133 937, resources.arsc 142 768,
  res 12 881, kotlin 12 053, META-INF 11 334, AndroidManifest.xml 1 577.
  Size lever: `srcDir(backend/planner)` also packs `tests/`, `tools/` and `fixtures/` (worlds then appear twice:
  as assets and inside the Python zip). Staging only `verst_planner/` with a Sync task would cut several MB.
- Hello screen (emulator `01-hello.png`): «Верста / Сборка 5 · 15b7158 / Движок 0.1.0 · 975 мс». Before ready
  it shows `Движок: STARTING`; on error `Движок: <code>`. That is a code, not copy; final copy goes to the Designer.
- Licence: not verified yet. The sandbox proxy blocks github.com raw and Maven Central, and the GitHub page
  fetch was not approved. Open: read `LICENSE.txt` from the plugin jar in the CI gradle cache.
- The branch also carries the uncommitted Python of DEV-110…113, which `mobile.py` needs.

## Review rework on `dev/DEV-101` (commits `ac72fb9`, `dc2a536`; run 7 `40050470173` green)
Architect: DEV-110 accepted; DEV-111/112/113 returned. Mirrored into this tree (not committed); `make check` →
`Ran 309 tests` / `OK`, coverage `TOTAL 5119 120 97.7%`, `mobile.py 377 7 98.1%`.

### DEV-111 R1–R5 (`verst_planner/mobile.py`)
- R1 `API_VERSION = 1`, `selfcheck().apiVersion`; `replace_stop`/`patch_cost`/`share_text` reject a trip whose
  `engineVersion` differs in major.minor → `TRIP_INCOMPATIBLE` (`field` = `engineVersion`); a missing
  `engineVersion` → `INVALID_INPUT` (`engineVersion`, `missing`). Tests `test_selfcheck_api_version`,
  `test_stale_trip_rejected`.
- R2 strict decoding: `_int` (no bool, no str, no float), `_bool` (JSON booleans only), `_str`, `_num`; crew
  fields checked then decoded inside `_parse`; `hotelChoice` must be an object of strings; `q`, `request_id`,
  `stop_id`, `alt_id` must be strings. `test_patch_strict_types` (12 bad patches + 8 bad arguments);
  `test_never_raises` no longer accepts `INTERNAL` for garbage input.
- R3 `json.dumps(..., allow_nan=False)` inside the try; a serialisation failure → `INTERNAL` envelope
  (`test_serialization_failure_is_internal`: NaN and `object()`).
- R4 `TOO_SHORT` carries `roadKm` (`test_too_short_carries_road_km`); docstring: the code list incl.
  `TRIP_INCOMPATIBLE`, `message` is diagnostic English, copy is chosen by code only.
- R5 docstring threading contract; `cancel(unknown)` stores a tombstone (≤ 32, oldest evicted) and returns
  `{"cancelled": false, "pending": true}`; a later `plan` with that id → `CANCELLED` at once and consumes it
  (`test_cancel_before_plan`). `selftest` now cancels an idle id so it never tombstones its own plan.

### DEV-112 C1–C5 (contract bundles)
- One bundle per case: `docs/contracts/replace/<case>.json.gz` (`before` once, items `stopId, altId, afterDay,
  afterCost, afterKm`) and `patch/<case>.json.gz` (items `kind, patch, afterCost, afterInput, afterHotel`).
  The generator rebuilds the full trip from `before` + item and asserts it equals the engine's output, so no
  other part changes (holds for all 129 + 25 items).
- Size: 15 MB (154 plain files) → 1.56 MB (first gz cut) → **331 067 B** (20 bundles). Gzip via
  `GzipFile(filename="", mtime=0)`, regeneration is byte-identical; the test compares decompressed text.
- The generator asserts ≤ 3 alternatives per stop (max today is 3); `test_counts`, `test_size_budget` (≤ 2 MB).
- `docs/backlog-sprint2.md` DEV-112 description/acceptance and DEV-104 `TripEditorReplaceContractTest` /
  `PatchContractTest` wording updated ("every case bundle and every item"). Still to update by the Architect:
  `architecture-android-mvp.md` §12 table row "Contracts (Kotlin)" (mentions per-alternative files).
- Kotlin loader `:core-model` `src/test/.../contract/Contracts.kt` (GZIPInputStream + kotlinx.serialization)
  and `ContractFilesTest` (bundles load, counts, ≤ 3 per stop): green in CI (junit 5 tests, 0 failures).

### DEV-113 T1 (sights in `tests/golden/ties.py`)
- New picks: `sight` (per day with the cap reached: last accepted vs the next in pool order) and `sight_drop`
  (every `lowest_sight`: dropped vs next-lowest droppable). 39 picks now (9 sight), threshold `≥ 35`.
- Found 3: G01 day-2 cap Земляной вал 5.0 = «Ботик Петра Первого» 5.0; G01 re-run drop Никитский 5.3 =
  Спасо-Преображенский 5.3 (km tie-break); G03 day-1 cap Скопинское озеро 5.233 vs Городской парк 5.2 (0.033).
- Fixture: «Ботик» 4.2 → 4.1, Никитский 4.3 → 4.4, Городской парк Скопина 3.7 → 3.6. Plans unchanged; G01
  snapshot changes only in one stop's alternatives (Музей утюга replaces «Ботик»). G01/G03 workings gain a
  sights line. (Raising Земляной вал instead moved the tie to Горицкий 5.033 vs «Ботик» 5.0.)

### Android: packaging and licences
- `stagePlannerSources` (Sync of `backend/planner/verst_planner/**`, no `__pycache__`) is the only Chaquopy
  source dir; every task whose name contains `Python` depends on it. Worlds ship once, as assets.
- APK `apk.json`: 43 280 407 B (43.28 MB, run 5) → **42 871 396 B (42.87 MB, run 7)**; assets 12 586 408 →
  12 174 863; lib unchanged 24 805 600 (the CPython + Compose native libs dominate).
- Parity still 10/10 equal, G09 `UNREACHABLE`, G10 `TOO_SHORT`. Engine: first launch 1740 ms (logcat),
  `timings.json` 1211 ms (second process).
- Licence: Gradle task `chaquopyLicences` reads the `com.chaquo.python` POMs and any LICENSE/COPYING/NOTICE
  entries in the cached artifacts → `assets/licences/chaquopy.{txt,json}` in the APK (verified with
  `unzip -l`) and `runs/<R>/build/licences/` in ci-logs. Result: **MIT License** for
  `com.chaquo.python.gradle.plugin:16.0.0`, `gradle:16.0.0` and the runtime `target:3.12.7-0`; the jars carry
  no LICENSE entry. Note: CPython itself is PSF-licensed; the MIT POM covers Chaquopy's packaging only.
- AGP owns the output dir of a generated asset source (`addGeneratedSourceDirectory`), so CI finds the files
  by `find` (run 6 failed on a fixed path).

## DEV-SLICE — thin end-to-end vertical slice (branch `dev/DEV-SLICE`, Manager re-prioritisation 2026-10-24)

Goal: a usable path on the phone now, polish later. Windshield → (own route) Navigator → Instruments → Drive →
Road ahead, and Windshield ready route → Instruments → Drive → Road ahead, on the real on-device engine.
Runs: 9–11 red (compile: nested token objects held in a `val`; `setQuery` JVM clash; a duplicate-text assertion),
12 green, 13 red (e2e flake, see below), 14 green, final run in the report.

Files:
- `:core-model`: `dto/Dtos.kt` (slice subset of the plan JSON, `ReadyRouteDto`, `SuggestionDto`, `TripDto`…,
  `PlanEventDto`, `EngineErrorDto`), `EngineJson.kt` (envelope → `EngineResult.Ok|Err`, never throws;
  `PlanRequest.toInputJson()`, `DefaultOrigin` Москва, `BudgetPresets`, `Mood`), `RuFormat.kt` (U+202F
  thousands, «HH:mm», A§11.11 estimates). `kotlinx-serialization-json` is now `api`. Test `EngineJsonTest`
  (all golden snapshots decode, envelopes, events, request JSON, formats).
- `:core-ui`: `theme/DesignTokens.kt` (see deviation 1), `components/Basics.kt` (Txt, Icon, BackLink, InfoChip,
  ToggleChip, StepperKey, PrimaryCta, SecondaryButton, PlaceholderPlate), `Scene.kt` (static WindshieldScene with
  the 5.1 §1 short-window y-scaling, SkyStrip, `dashboardSurface`, `overheadPlate`, `naviPanel`), `Signs.kt`
  (RoadSign city/tourist/service with DES-102 pictograms, arrows by `bearing8`, StartButton S/M/L, StepLine,
  ProgressBar). `HelloTheme` removed. Test `DesignTokensInSyncTest`.
- `:app`: `engine/EngineHost.kt` (+ `dispatcher` over `verst-python`, `callHere` that turns any throwable into an
  `INTERNAL` envelope and refuses the main thread, direct `cancel`, `restart`), `engine/PlannerGateway.kt`
  (`ChaquopyPlannerGateway`: waits for Ready ≤ 30 s, `readyRoutes`/`suggest`/`popular`/`plan` with a Java-visible
  `PlanEventListener`; cancelling the caller calls `mobile.cancel` from a watcher coroutine because the plan
  blocks `verst-python`), `nav/VerstFlow.kt` (back stack of 5 routes, draft, instruments, Drive pacer ≥ 400 ms
  per step + 1 000 ms auto-advance, Drive → Road replaces Drive), `feature/{windshield,navigator,instruments,
  drive,road}/*Screen.kt` (stateless, `XUi` data in), `feature/common/Common.kt`, `MainActivity` (BackHandler =
  back links; Russian `Configuration` locale), `res/values/strings_slice.xml`.
- Tests: `ScreensScreenshotTest` (Robolectric, ru locale, 18 PNGs incl. 360 × 640), emulator
  `SliceJourneyTest` (two journeys; `files/e2e/screens/01…10`; failure screenshot `zz-failed-*`).
  `HelloSmokeTest`/`HelloScreenshotTest`/`HelloThemeTest` removed. `tools/sync_design_tokens.py`.

Behaviour notes:
- Windshield: `ready_routes(Москва, 50 km)` → overhead sign (≤ 4 rows, selected row yellow on `blueSelected`);
  states loading (static placeholders, no shimmer), no-routes, error and engine-failed («Повторить» restarts the
  engine). ПОЕХАЛИ → Instruments with the selected route; the navi panel → Navigator.
- Navigator: ОТКУДА value field («изменить» makes it an input), КУДА `BasicTextField` with 250 ms debounce over
  `suggest`; < 2 chars → «ЧАСТО ИЩУТ» rows from `popular`; skeleton, no-results, suggest-error blocks; caption
  with ≈ straight-line km; < 15 km → «Слишком близко…» and start disabled; a TOO_SHORT/UNREACHABLE from Drive
  comes back as the red caption meta. No vias, no map.
- Instruments: mirror bench of 3 seats (empty → adult → child), front-seat chip, dog, km/day odometer 150–900
  step 50 with «≈ X ч Y мин» and days (A§11.11), budget presets with a simple gauge, mood chips (calm preselected
  once a child is added). The start time is the engine default (the next Saturday 08:00 — no settings sheet).
- Drive: stage texts from the engine events, paced; the bar follows the revealed step; the «N ДНЕЙ» header
  comes from the engine's `stop` events (the ×1.25 estimate said «2 ДНЯ» for a 1-day Москва → Ярославль); errors → «НЕ ПОЛУЧИЛОСЬ» + 5.4 §4.4 message and CTA
  (retry / «К приборам» / «Изменить маршрут»); `CANCELLED` → silent back; back = cancel (engine `cancel`).
- Road ahead: fixed title sign, intro chips, engine warnings as plates, per-day header, stop rows (sign, «старт» /
  «через N км», time, name, note = engine `note` or `reason`, cost), road column per item, pinned white footer
  «≈ total ₽» + per person (red label when over budget).

e2e flake found (run 13): the Navigator caption (with ПОЕХАЛИ) was hidden while `WindowInsets.isImeVisible`; the
IME did not close in time after a pick and the start button never appeared. Now the caption hides only while a
field is focused **and** the IME is up (focus is cleared on pick) — also the right UX.
Second e2e failure (run 15, failure screenshot `zz-failed-*`): on the ≈ 640 dp window the keyboard covered the
result rows (the tap landed on the IME). Real UX bug: while typing, the 150 dp scene strip now collapses and the
panel scrolls to its end when results change; the test also `performScrollTo()`s the row.

Deviations / open items:
1. `DesignTokens.kt` is not byte-identical yet: DES-100 fonts are not in `res/font`, so the `font` object uses
   `DeviceFontFamilyName("sans-serif-condensed")` / Monospace / Cursive (+ the `R` import swapped).
   `tools/sync_design_tokens.py` writes it verbatim as soon as `ibm_plex_sans_condensed_regular.ttf` exists;
   `DesignTokensInSyncTest` then requires equality.
2. Copy not in the deck: `slice_per_person` «≈ N ₽ на человека» (app module, flagged for the Designer); seat
   positions «Левое/Среднее/Правое» are the values from copy-ru `cd_instruments_seat` notes; town genitive for
   «ИЗ МОСКВЫ» is a two-entry map (Москва, Тестовск) — the worlds have no `nameGenRu` (engine field proposed).
3. copy-ru bug: `road_chip_days` is «%1$d %2$s · %3$d %4$d» — the 4th arg is a word, `%4$d` would crash; the
   slice builds the chip from plurals instead. Designer to fix the generator/deck.
4. Not done (by instruction): Waybill, Exit/booking, replace-stop sheets, save/share, debug panel, animations
   (no lane motion, pulse, flying signs, shimmer, odometer roll), vias, map picker, TalkBack strings audit,
   TokenLiteralsTest/PackageRulesTest (dp/sp literals exist in screens), ViewModels (one `VerstFlow` holder).
5. The emulator window is 1170 × 1920 px (≈ 390 × 640 dp) despite `wm size 1170x2532` in `run_e2e.sh`, so the
   e2e screens are the short-window layout; Robolectric covers 390 × 844 and 360 × 640.

## DEV-SLICE-2 — one distance, Waybill, replace stop, saved trips (branch `dev/DEV-SLICE-2`, on main `a844b9e`)

### P0 km consistency — root cause and fix
For Москва → Ярославль the slice showed three numbers from three sources:
- Navigator ≈ 249: `TripMath.haversineKm` (straight line, rows and caption);
- Instruments / Drive ≈ 312: `TripMath.roadKmEstimate` = straight line × 1.25 (A§11.11);
- Road ahead 265: the engine's `trip.km` = base route 263 + 2 km of stop detours.
Ready routes had the same issue: «Золотое кольцо» showed `kmTotal` 745 before the plan and 761 after (16 km of
sight detours). A base-route estimate alone can never agree with the plan, so the pre-plan estimate is the
engine's plan itself:
- `mobile.estimate(world, request_id, input_json)` → `{km, days}`: `Planner.plan` of the same input without
  events, cancellable like `plan` (shared `_run_plan`). Equal to the later plan by construction (deterministic
  engine, same clock); errors as `plan` (`TOO_SHORT` / `UNREACHABLE` are now known in the Navigator before
  planning, replacing the 15 km straight-line check).
- `mobile.estimate_points(world, lat, lon, points_json)` → base-route km per suggestion row (`Planner.estimate_km`,
  stages 0–2); `null` for unreachable/outside Russia. Rows are places, not trips yet: they show «≈ 263 км», the
  picked trip shows «265 км».
- `_trip_result` adds `pricesMonthRu` / `pricesYear` (Waybill footnote via `ru.month_year_ru`).
- App: `TripFigures` / `TripFiguresPick` (`:core-model`): one list of engine figures per `PlanRequest`
  (estimates and plans); the exact request wins, the same road shows its last figure as stale while the new
  estimate runs, another road shows nothing. `VerstFlow` estimates the draft 300 ms after it settles on Navigator
  and Instruments (`snapshotFlow` + `collectLatest`, which cancels a stale estimate in the engine); after a plan,
  replace or reserve toggle the trip's own km is recorded. `TripMath.haversineKm/roadKmEstimate/days` are deleted.
  Instruments days also come from the engine (the slice's ×1.25 said «2 дня» for a 1-day trip).
- Tests: `test_mobile.test_estimate_equals_plan_moscow_yaroslavl` (265 = plan; rows 263 = 265 − detours),
  `test_estimate_equals_plan_for_every_variant` (child/calm, dog/500 km, round trip, every ready route from
  Москва), `test_estimate_errors_and_cancel`; Kotlin `SliceTwoModelTest.figuresPrefer…`, `noStraightLineKmLeft…`,
  `VerstFlowTest` (estimate shown before, the plan's number after), e2e asserts Navigator == Instruments ==
  plan == Road-ahead sign. `make check` → `Ran 312 tests` / `OK`; coverage `TOTAL 5155 121 97.7%`.

### Waybill 5.6 (DEV-125 simplified) — `feature/waybill/WaybillScreen.kt`
Opened from the Road footer (now a button with the arrow, S-22). Paper sheet: header, № (saved ordinal), route,
crew, mileage; table with the engine's lines (title, formula in hand, sum), chevron, one line expanded at a time
(breakdown rows: label · formula without its trailing «= N ₽»); reserve row → `patch_cost {reserveOn}` on the
engine (no Kotlin `CostCalculator` exists yet — DEV-104), «—» when off; total; issued / left or «Перерасход» in
ink red + hint; budget «не важно» → «—»; footnote «Расчёт: … на октябрь 2026». Save / share buttons.
Not done: stamp + animation, entry slide, Pro plate/sheet, cross-fade of changed values.

### Replace stop (D-6) — Road ahead
«заменить» (components §2.6) on replaceable stops with alternatives or an `alternativesNote`. Bottom sheet
(`feature/common/Overlays.kt` `BottomSheet`, static): current stop «сейчас», alternatives with Δ min / Δ ₽, the
engine note when < 2, «ЗАМЕНИТЬ» (disabled until another row is picked), «Оставить как есть». Confirm →
`replace_stop` → the trip and the footer total update; toast «Заменили. Путевой лист: ≈ N ₽» + «Вернуть» (6 s, undo
restores the previous trip). Row sub-lines are the engine's `note`/`reason` sentence (the deck has no per-tag
copy for food/rest tags).

### Saved trips
`data/TripStore.kt`: `FileTripStore` = one JSON file `files/trips/saved.json` through `AtomicFile` (no Room);
`SavedTrips` (`:core-model`): schema 1, ≤ 50 (`LimitReached`), warning from 45, upsert by id, the engine's private
trip JSON verbatim (so a reopened trip can be replaced / re-costed / shared). Road toolbar T1 save (bookmark,
filled yellow when saved) and T2 share (`ACTION_SEND` with the engine share text); Waybill K1/K2 the same.
Windshield «Мои поездки · N» plate in the caption column (5.1 §4.4) when ≥ 1 saved; D-1 sheet rows → Road ahead
with the back label «К лобовому» (OI-27), back → Windshield. Not done: delete, «Вернуть», the 50-limit dialog
(a toast instead), past/upcoming styling.

### Designer review `design/qa/slice-review.md` (merged to main as `a844b9e`)
Fonts: rebased on main, `python3 tools/sync_design_tokens.py` → `DesignTokens.kt` verbatim (DesignTokensInSyncTest
now compares for equality). `slice_per_person` / `strings_slice.xml` removed → `road_waybill_per_person`.
- S-01 chip via `road_chip_days`. S-02 `enableEdgeToEdge(SystemBarStyle.dark(TRANSPARENT))` + `ScreenRoot(statusBar=)`
  bands (`interior.liner` on Windshield/Drive, `sky.band1` on strip screens, nav bar `dash.raised`).
- S-03 `dashboardSurface` = two elliptical arcs (`arcTo`), S-30 caps without rim.
- S-04/S-10/S-18 `drawRoad3D` (§9.1 closed form, quads, clipped at the container top) with `WindshieldRoad`,
  `NavigatorRoad`, `DriveRoad`; S-05 hills polyline; S-06 gantry legs; S-17 `DriveSky` + sun centred; S-19 `RoadSky`.
- S-07/S-08 `Mirror.Small` as one Canvas: reflected sky/ground, glass cut-out silhouettes at slots 154/193/230
  (adults outer-first), dog at the right, glare. S-09 yellow 2 dp field border in no-routes (static, no pulse).
- S-11 Navigator: back link in a 38 dp band (touch 142–186), panel top 188, value field 50, bottom inset 140.
- S-12 odometer 4 drums (last white) in the 113 × 42 frame; S-13 equal well heights; S-14 gauge per §6;
  S-15 `DogToggle` per §3.4; S-16 dashed empty seats, seat radius 14/6; S-27 mirror stem + reflected road.
- S-20 Road list is a scrolled `Column` with one road section (continuous lanes) instead of per-item road
  segments in a `LazyColumn` (deviation from DEV-124's `LazyColumn`: a trip has tens of rows); S-21 rhythm
  (title at the list top, chips +6, intro +8, road 18 below, day 1 margin 0).
- S-22 footer arrow + deck key. S-23 genitive for all 48 fixture towns (engine `nameGenRu` still requested).

### CI
Runs: 19 red (2 unit tests: NBSP in `common_km`; `advanceUntilIdle` ignores `backgroundScope`), 21 red (Chaquopy
licence step: the restored Gradle cache has no `com.chaquo.python` — main run 20 is red on the same step; the task
now resolves the POMs through a detached configuration), 22 cancelled (superseded), 23 red (e2e: one merged
finder), 25 green (`70073d4`, build + e2e 4/4), final run in the report. e2e log line:
`km navigator=265 instruments=265 plan=265 road=265`. APK 43.92 MB.
e2e screens 11–19 (`runs/<R>/e2e/screens/`): Waybill, fuel line open, reserve off (≈ 4 900 → ≈ 4 400), replace
sheet, replaced + toast, saved, Windshield «Мои поездки · 1», D-1 sheet, Road from saved («К лобовому»).
Free trips now get their Road-title arrow from the origin → destination bearing (`TripMath.bearing8`).

### Deviations / copy requests
1. `replace_delta` has one `{sign}` for both parts; mixed signs («+4 мин · −150 ₽») are composed from two
   renderings of the same template. Designer: two sign placeholders.
2. D-1 rows show the date as «31.10»: the deck has no genitive month names («7–9 ноября»).
3. Toast StorageFull = `common_storage_full_title` + body joined with «. » (no NaviDialog yet).
4. The «—» for empty Waybill values and gauge without E/F letters (no copy keys for E/F).
5. `mobile.API_VERSION` stays 1: `estimate`/`estimate_points` are additive; `_trip_result` gained two keys.

## DEV-SLICE-3 — Exit 5.7, local cost, motion, trips, debug, journey (branch `dev/DEV-SLICE-3`)

Base: main `efe955d` + `origin/des/DES-QA-SLICE2` @ `5374873` merged in (Manager: shipped together because it
changes `design/DesignTokens.kt`); `python3 tools/sync_design_tokens.py` → verbatim.

### Engine (Python) — `make check` → 314 tests OK, coverage 97.6 %
- OI-41 (acting as Architect, Manager-approved): `hotelOptions[].exitDistanceM` = round(route → hotel lateral km
  × 1000) from the corridor candidate; additive, `HotelOption.exit_distance_m` default 0. Goldens, contracts,
  share-text and DEV-112 bundles regenerated: the only diff is the new field.
- OI-39: fixtures `towns[].nameGenRu` for all 48 towns (`tools/gen_worlds.py` `NAME_GEN`, regenerated byte-identically
  otherwise), `Town.name_gen_ru`, `ru.genitive`. Exposed in `suggest`/`popular` rows (`nameGenRu`, `namePrepRu`,
  null for places), `reverse`, and trip results as `townGenRu` / `townPrepRu` maps (townId → form). Deviation from
  the OI-39 proposal (per-stop `townNameGenRu` in the plan codec): the maps live in the `mobile` result so the plan
  codec and the golden snapshots stay unchanged. Test `TownFormsTest` (every town, Cyrillic). The Kotlin 48-town
  map is deleted; the app asks `reverse` for the origin's forms and takes them from the picked suggestion.
- N-10: the split stage text («по ≈ {km} км») used the base route km (263) while the header shows the trip km (265).
  `Planner.plan(split_km_hint=…)`; `mobile.plan` takes the hint from the km of an identical earlier `estimate`
  (bounded cache by canonical input JSON) or runs a quiet estimate first on a miss (the app always estimates on
  Navigator/Instruments, so the extra run is rare). The stage line now reads «по ≈ 265 км».

### DEV-104 CostCalculator (`:core-model` `cost/`)
- `CostCalculator.recompute` = the numbers of `cost/recompute.py` (rules 1–5, BigDecimal HALF_UP; fuel km is the
  only Double, as in the units). Deviation: the Russian formula/breakdown text is not ported — the engine call
  that follows the local result brings it (local-first, M§6.3). `LocalCost` reads units / crew / alternative units
  straight from the engine trip JSON; `CostApply` puts the numbers into the shown trip.
- Tests: `CostCalculatorContractTest` (39 cases, test names `case_<name>`), `LocalCostBundleTest` (all 129 replace
  items and 25 patch items: local total and each line == engine `afterCost`), 10 000 recomputes < 5 ms each.
- Used local-first for the reserve toggle, a hotel choice (5.7) and a replace; on an engine failure the previous
  trip is restored + toast.

### 5.7 Exit + D-10 + D-13 (`feature/exit/ExitScreen.kt`)
Night scene (`ExitScene`: night bands, twinkling stars, crescent, town lights, night road with `lane.exit`,
headlight, pole), exit sign with `exitNear` (2200 ms) and «800 м» from `exitDistanceM` («ночёвка» when unknown),
turn signal blink, navi panel (header k of n · km · time, town, engine reason, NO_LODGING row, hotel options with
tag labels and crew price), Book CTA (mock copy `exit_book_partner_mock`, offline state through the debug
panel's simulated connectivity), booked CTA («Открыть бронирование»), `MockPartnerSheet` with the fictional
«Придорожная» and the ДЕМО badge — no real brand anywhere in the mock build (OI-40; the screenshot test asserts
no «Яндекс» text) — and the «Забронировали?» `NaviDialog`. Booking is per night (`stopId → placeId`, saved with
the trip); Road ahead shows «Забронировано ✓» only while the booked hotel is the selected one; «Да» → toast with
«Вернуть». Entry from «Выбрать отель →» on Road-ahead night rows.

### Motion (motion.md v1.1)
`LocalReducedMotion` (animator or transition scale 0 → static frames), one scene clock per screen
(`withInfiniteAnimationFrameMillis`, so Compose tests stay idle; drawn in draw lambdas only). Lanes on Windshield /
Navigator / Drive / Exit, roadside posts (§9.2), start pulse + press scale, mirror sway, dog wag, odometer roll
(changed drums only), needle spring (0.6 / 300), Drive step appear + progress tween + flying signs from the
engine's `stop` events (≤ 3 in flight, 1200 ms apart), Waybill sheet slide + stamp once per trip (keyed by a
trip session, a cost change does not replay it) + 200 ms cross-fade of handwritten values, bottom sheets slide in
with scrim fade and drag to dismiss (25 % or > 1200 dp/s, else spring back), toast entry, Exit twinkle / turn
signal / exit sign. Not done: screen transitions (§3), car marker, Drive lane period ramp, toast exit animation,
power-saver rule, lifecycle pause (Compose stops frames when the activity is not visible).

### Saved trips
Delete from D-1 by long-press or the TalkBack action «Удалить» → `NaviDialog` → removed + toast «Поездка удалена»
+ «Вернуть» (restores at the same position); the 50-trip limit → `NaviDialog` «Место для поездок закончилось» /
«Мои поездки» (opens the sheet) / «Отменить»; warning line from 45 in the sheet; re-saving an existing trip
works at the limit. D-1 dates from the new keys («31 октября», «7–9 ноября», «30 октября – 2 ноября»).

### Slice-2 review (design/qa/slice2-review.md) — all 11 P1
N-01 gantry legs from min(286, plate bottom − 4); N-02 caption column centred on the start button; N-03 dates;
N-04 Instruments rhythm (chip 232, summary 282, wells 322 at L14/R14 175 × 197, mood 535); N-05 ears relative to
the body; N-06 gauge E/F; N-07 Road title line box (trimmed line height); N-08 replace rows (controlAlt, radius 10,
mini sign 0.7); N-09 drawn checks after «Сохранено» / «Забронировано»; N-10 engine; N-11 Waybill sheet at 64.
P2 done: N-12, N-13, N-14 (independent signs, zero parts dropped), N-20; slice-1 S-24, S-25, S-26 (КУДА focus
cleared after a pick, no autofocus once a destination is picked), S-28. Open P2: N-15, N-16/N-17 (no «≈ N» key
without «₽» in the deck), N-18, N-19, S-27 partly, S-31–S-35 (scope).

### DEV-127 debug panel — `feature/debug/DebugScreen.kt`
Entry: a 2 s long-press on «НАВИГАТОР» (Windshield) — there is no D-4 settings sheet yet. World (central /
edge), clock (system / golden via `mobile.set_clock`), simulated offline, slow plan (0 / 5 / 25 s after the
engine), forced engine error (the next plan returns the code), engine timings, build line, «Сбросить данные».

### DEV-130 journey and budgets
e2e adds: Exit (other hotel, mock partner, booked dialog, booked, Road booked row), trip delete + undo, the debug
panel and a forced UNREACHABLE (Drive error → «Изменить маршрут» → Navigator with the error). `files/e2e/budgets.json`:
engine start and the Golden-Ring plan time (asserted: engine ≤ 4000 ms). `docs/install-ceo.md` (Russian).

### CI (DEV-SLICE-3)
Runs: 28 red (compile: a fully qualified `DrawScope.scale` extension call), 29 red (one screenshot assertion: the
fixture lacked the engine genitive after the Kotlin map was deleted — all 39 `case_*`, 129 + 25 bundle items and
the perf test passed), 30 red (e2e: «merge function called on unmergeable property PaneTitle» — the sheets
swallowed taps with `clickable`, which merges the whole sheet into one node; now `pointerInput`; and the
sentence-case «Заменить» finder), 31 green (`f9728a4`): JUnit 99 / 0 failures, lint 0 errors, e2e 5 / 5, APK
44.03 MB. Budgets (`e2e/budgets.json`): engine start 925 ms (budget 4000), Golden-Ring plan incl. Drive pacing
3947 ms (budget 10 000). e2e screens 00–30 incl. 20–21 delete/undo, 22–27 Exit → mock partner → booked → Road
booked row, 28–30 debug panel → forced UNREACHABLE → Navigator error.

## DEV-RELEASE — release fix round (branch dev/DEV-RELEASE from main 262103b)
Merged origin/des/DES-FINAL (56009cb, final-review + strings incl. `exit_book_none`, `common_dialog_cancel`;
tokens re-synced, already verbatim) and origin/arch/release-review (0ccaf28).

### ARCH P0-1 — no real brands in the mock build
- `gen_worlds.py`: fuel stops are «АЗС, <road ref>, <km> км» (no chain names); worlds, goldens, contracts and
  bundles regenerated; `make check` green (318 tests).
- Deny-list `backend/planner/tests/brand_denylist.txt` (fuel chains, map/navigation, booking/travel services),
  used by `tests/unit/test_brands.py` (both worlds, engine resources, goldens, contract JSON + gz bundles,
  Android strings referenced from Kotlin) and by `BrandDenyListTest` (every merged `R.string` of app + core-ui via
  Robolectric, > 300 fields) and `ScreensScreenshotTest.shot()` (all rendered texts + content descriptions).
- Shared text = engine text + `mock_share_note` (`MainActivity.mockShareText`).
- Decision: the unused production strings that name navigators/map apps (`stopmenu_yandex_navi`,
  `stopmenu_yandex_maps`, `stopmenu_2gis`, `stopmenu_install`) are overridden with neutral text in
  `app/src/main/res/values/strings_mock_overrides.xml` (app resources win over library ones), rather than a
  prod-only source set; design/** untouched. JSON keys (`yandexTravelId`) are field names, not scanned.

### ARCH P1-1 — saved trips
- One writer coroutine (CONFLATED channel + pending snapshots → latest wins) for saved.json, last.json and
  defaults.json; all via `AtomicFile`.
- Unreadable saved.json (corrupt or unknown schema) is renamed to `saved.json.bad-<ts>` and never overwritten; the
  app starts with an empty list.
- No write before the first load: an early save is queued (`pendingSave`) and replayed after load.
- A failed write → `Toast.StorageFull`, «Сохранено» is cleared. Decision: no dedicated «не удалось сохранить» key
  exists in the deck — **copy request to the Designer**; StorageFull is the closest existing text.
- Tests: `FileTripStoreTest` (round trip, unreadable kept aside, unknown schema), `VerstFlowTest`
  `oneWriterLatestWinsAndFailuresAreReported`, `lastTripIsWrittenAndRestored`.

### ARCH P1-2 — last.json and process death
- The current trip (plan, reserve, hotel, replace, booked stops, saved id) and the screen (road / waybill / exit)
  are written 300 ms after any change; back to the Windshield clears the screen.
- Decision: on every start, if last.json has a screen, the app opens Road ahead (+ Waybill / Exit) with that trip
  without the engine — this covers both a system kill and force-stop + relaunch.
- e2e: `app.verst.e2e.restore.ProcessDeathTest` in two instrumentations; `run_e2e.sh` runs phase 1 (plan → Road
  ahead), HOME, `am force-stop` + `am kill`, then phase 2 (fresh process → Road ahead, same title / km / total).
  The main run excludes that package; the script expects 3 «OK (» lines.

### DES F-01..F-04 (+ F-08)
- F-01: Windshield row km = `mobile.estimate` of the same request (crew, pace) for the first 4 ready routes, only
  while the Windshield is on top; the sign falls back to the fixture km until the estimate arrives.
- F-02: PlateToast 44 dp (text padding 10 dp, no row padding); Windshield toast at bottom 340 dp, others as specced.
- F-03: Exit with no hotel options → disabled CTA «exit_book_none».
- F-04: Exit scene min top 240 dp; the panel scrolls with a 16 dp fade while more is below (640 dp shows a partial
  next option).
- F-08: NaviDialog secondary button dashed outline.

### P2
- P2-1: hotel / reserve / replace replies of another trip are dropped (`tripSession`), and `costBusy` is reset first.
- Defaults (crew, km/day if chosen, budget, mood, origin) persist in defaults.json (not DataStore).
- «Сбросить данные» asks first (NaviDialog `reset`); reset also restores crew and pace.
- P2-4: unit tests run on `debug`; the demo APK no longer pulls `ui-test-manifest`; CI step fails if the merged
  demo manifest contains `androidx.activity.ComponentActivity`.
- Limit dialog secondary «Отмена» (`common_dialog_cancel`). Both ABIs kept (x86_64 + arm64-v8a).

### CI (DEV-RELEASE)
Runs: 33 red (`eed0413`: the new `BrandDenyListTest` caught two more unused production strings naming the booking
partner, `exit_book_partner` and `cd_exit_book`; now neutral overrides), 34 green (`8103f4d`), 35 green
(`59757de`): unit + lint + Robolectric screenshots, e2e «OK (5 tests)» + process-death phase 1 «OK (1 test)», «no
process after force-stop», phase 2 «OK (1 test)». F-01 on the device: Golden Ring sign 757 = plan 757 (logcat
`VerstE2e`). APK 44.05 MB, ABIs arm64-v8a + x86_64. The limit-dialog screenshot now renders the real keys
(«Отмена»). New e2e screens: 31-before-process-death, 32-restored-after-process-death.
Open: «не удалось сохранить» copy key (StorageFull used meanwhile); debug-panel error chips row scrolls past
the right edge (debug only).
