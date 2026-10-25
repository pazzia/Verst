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

### Manager return — Windshield km (run 36 green, `8763cf9`)
Problem: rows without an estimate yet showed the fixture km (`kmSign` 263 / 745) and then jumped to the engine km
(537 / 757). Ярославль is a there-and-back ready route (`roundTrip: true`, `kmTotal` 526, `kmSign` 263 = one way),
so its engine km (537 for 2 adults + 1 child) is the whole round trip.
- A row never shows template km: until the estimate for the current request is in, it shows a static
  `PlaceholderPlate` (components §16, `sign.plate`), tag `windshield.route.N.km.pending`. Decision: static, no shimmer
  animation (the existing placeholder plates are static; motion budget).
- Estimates run on the engine thread for all visible rows, selected row first, then top to bottom. The cache key is
  the whole `PlanRequest` (route id, crew, pace, budget, mood, origin); a world or clock change clears it. A crew
  change makes new requests, so rows go back to the placeholder and get re-estimated. Cache size raised to 48.
- Caption meta of a there-and-back route: «<subtitle> · туда и обратно» (loops already say «по кругу»), wrapped to
  two lines. **Copy request to the Designer:** `windshield_meta_round_trip` = «туда и обратно» is a new key, kept in
  `app/src/main/res/values/strings_pending_copy.xml` until it reaches the deck.
- Tests: `VerstFlowTest.windshieldRowsShowOnlyEngineKmSelectedFirstAndReestimateOnCrewChange`; screenshot
  `windshield/estimating` (no template km rendered); e2e `windshieldSignKmIsThePlanKmOfEveryRow`: each visible row
  equals `plan(routeRequest(row))`.km for the same crew. The e2e now shows «OK (6 tests)» plus both
  process-death phases.

## S3-R1 — Sprint 3, round R1 (branch dev/S3-R1 from main 5ca38d0)
Android only, independent of the Architect's engine work (arch/sprint-3) and the Designer's specs (des/sprint-3).

### 1. Focus restore (CEO 2.1)
- `VerstFlow.roadFocusId` = the row acted on (Exit «Выбрать отель», «заменить», the stop menu), `roadTopId` =
  the top visible row (reported by Road ahead 250 ms after scrolling settles), `roadFocusSeq` bumps on every return
  (back to Road, a sheet closed, a restore). Road ahead measures each row's offset in the scrolled content; on a
  return it centres the focus row in the list viewport and highlights it (`accent.yellow` 14 %, 1.2 s, fades;
  reduced motion: on, then off), else puts the top row back at the top. A new trip clears both.
- Both ids go to last.json (`LastTripDto.roadFocusId/roadTopId`): after process death the same rows come back; a
  restore onto Exit makes that night the focus for the way back.
- Decision: Waybill (a footer, not a row) restores the position only, without a highlight.
- Decision: the highlight has no motion token; 1.2 s is provisional — **Designer: token + colour for «returned
  row» highlight**.
- e2e `RoundR1Test.focusComesBackToTheSecondNightAfterBooking` (Golden Ring night 2 → Exit → book → back: the row
  is in the list viewport without scrolling; Waybill and back keeps the top row); `ProcessDeathTest` scrolls to
  the last row before the kill and checks that row after the relaunch.

### 2. Navigator hand-off (CEO 4)
- `core-model/NaviLinks`: `yandexnavi://build_route_on_map?lat_from&lon_from&lat_to&lon_to&lat_via_N&lon_via_N`,
  web `https://yandex.ru/maps/?rtext=lat,lon~…&rtt=auto`, maps app `yandexmaps://maps.yandex.ru/?rtext=…&rtt=…`,
  walking helper (`rtt=pd`, city mode later). Coordinates: dot decimal, 6 places, any locale.
- Decision (limits): 8 via points for the navigator, 10 points in all for the web route; above that the vias are
  thinned evenly keeping order and the first/last via. Consecutive duplicate points (day start = last night) are
  dropped. A day link: first stop → last stop of the day. «навигатор отсюда»: this stop → end of its day; on the
  day's last stop → the next day; on the trip's last stop → to it from the phone's position (no `lat_from`).
- Stops now carry `lat`/`lon` (`StopDto`, nullable — old saved trips have none and simply get no link).
- Road ahead: «в навигатор ↗» right on every day header (offline: «в навигатор», disabled colour, toast
  `common_need_internet_navigator`); long-press a row (haptic) → D-5 stop menu: «ОТКРЫТЬ В НАВИГАТОРЕ ОТСЮДА»
  (target named below: «Яндекс Навигатор» when installed, else «Яндекс Карты · в браузере») and «Заменить»;
  TalkBack custom actions on each row. «Сообщить об ошибке» (D-7) not built.
- `IntentHandoffLauncher`: the navigator package when it resolves, else the browser, else toast `stopmenu_none`.
  Manifest `<queries>`: the navigator and maps packages, `yandexnavi:` VIEW, https BROWSABLE.
- Brands: `backend/planner/tests/brand_handoff_keys.txt` = the explicit allow-list (`stopmenu_yandex_navi`,
  `stopmenu_yandex_maps`), read by `test_brands.py`, `BrandDenyListTest` (each listed key must exist and start with
  «Яндекс ») and the rendered-screen scan (only those values are cut out). Their mock overrides were removed;
  `stopmenu_2gis`, `stopmenu_install` and the booking-partner keys stay neutral.
- Tests: `NaviLinksTest` (format in the ru locale, via order, limits, walking, day / from-stop on G02),
  `VerstFlowTest.handoffOpensTheDayAndFromStopRoutesAndNeedsTheNetwork`, e2e
  `dayLinkAndLongPressHandOffToTheNavigatorWithViaPoints` (dry run: the e2e records the link instead of leaving
  the app; the emulator has no navigator → the browser target).

### 3. GPS (CEO 3)
- Manifest: INTERNET, ACCESS_COARSE_LOCATION, ACCESS_FINE_LOCATION.
- Decision: platform `LocationManager` (`AndroidLocator`: fused provider on API 31+, GPS, network; one fresh fix
  each with a 10 s timeout, else the newest last-known). No FusedLocationProviderClient: it needs Google Play
  services, which RuStore phones may lack.
- «Куда угодно» (5.2): the first visit shows a rationale card under КУДА (`windshield_location_rationale`,
  «Разрешить» → the system dialog, «Не разрешать» → toast `windshield_location_denied`, never asked again);
  «don't ask again» → `windshield_location_blocked` + «Настройки» (app settings). Granted → located on the next
  «Куда угодно» unless the origin was picked by hand. ОТКУДА «изменить» → «Моё местоположение».
- Origin = the engine's town within 30 km (`reverse` + its `suggest` row, for coordinates and name forms), else
  the nearest `popular` town (haversine). The Architect's catalogue replaces this. «ВЫ: <ГОРОД>» on the
  Windshield, «GPS ●» / «GPS ○» in the Navigator header. Persisted in defaults.json (`locationAsked`,
  `originFromGps`).
- Debug panel: «Имитация местоположения» (нет / Ярославль / Тула / Владимир / поле); e2e uses it, and a separate
  last instrumentation `RealGpsTest` runs on the emulator's real stack (`pm grant` + `adb emu geo fix` Тула).
- Tests: `VerstFlowTest.gpsOriginIsTheNearestTownWithRationaleAndDenyPaths`, e2e
  `locationRationaleDenyThenMockLocationSetsTheOrigin`, `RealGpsTest`.

### Provisional copy (strings_pending_copy.xml) — for the Designer
`navigator_location_deny` «Не разрешать», `navigator_location_failed` «Не получилось определить, где вы. Старт
прежний», `debug_mock_location` «Имитация местоположения», `stopmenu_web_fallback` «в браузере» (plus the open
`windshield_meta_round_trip` from DEV-RELEASE). Also needed: the D-5 stop-menu layout, the rationale card
layout in 5.2, the highlight token.

### CI (S3-R1)
Runs: 38 red (compile: a local `app` shadowed the `app.verst` package in DebugScreen), 39 red (a test fake broke
the Moscow genitive), 40 red (e2e: Golden Ring text matched twice once it was the selected route; the top-row
report waits on the composition clock, which `Thread.sleep` does not advance; auto-locate closed ОТКУДА under
the test's tap), 42 red (the IME shifted the ОТКУДА layout under a tap in RealGpsTest), 43 green (`d65ae0c`):
unit + lint + Robolectric screenshots, e2e «OK (9 tests)», process-death phases «OK (1 test)» ×2 with «no
process after force-stop», RealGpsTest «OK (1 test)» (emulator fix → Тула, «ВЫ: ТУЛА»). APK 44.1 MB, both ABIs.
Screens: e2e 40–50 (focus restore, stop menu, offline day link, rationale / deny, debug mock, GPS origin, real
GPS); screenshots road/stop-menu, road/stop-menu-offline, road/focus-restored, navigator/location-rationale,
navigator/gps-origin.
Open: the Navigator still autofocuses КУДА (IME up) right after ОТКУДА is set — existing 5.2 behaviour, spec
question for the Designer; D-7 «Сообщить об ошибке» not built.

# Sprint 3 (engine side owned by the Architect, branch `arch/sprint-3`)

## Contract changes (read me first, Developer)
- `mobile.API_VERSION = 2`; `ENGINE_VERSION` stays `0.1.0` (saved Sprint 2 trips stay editable).
- New calls and examples: `docs/contracts/v2/*.json` (`{"request", "response"}`), regenerated by
  `backend/planner/tools/gen_api_contracts.py`; `index.json` lists them. Until the CI data run is merged the
  catalogue is the **sample** (`tests/data/samples/raw`, placeholder ids `Q9000xx`); ids change with the real data,
  shapes do not.
- `plan` result gains `"outcome": "plan"`; trips on synthetic routes carry `"approxDistances": true`.
- `estimate` gains `outcome`, `totalRub`, `budgetStatus` (null until the budget fitter, ARCH-301).
- New world `russia_v1` (load with `load_catalogue()` after both `load_world` calls). New error codes
  `NO_CATALOGUE`, `NO_CITY`, `NOT_ENOUGH_POIS` (`field = preset`).

## ARCH-303/304/305/306/307 — first cut (M1)
- `verst_planner/catalogue/` (columnar gzip format + loader), `adapters/catalogue/` (compose, `HybridRouting`,
  indexed repos, fictional services), `city/` (walk input, solver, assembly), `handoff.py`, `catalogue/photos.py`.
- Road model calibrated on 818 fixture town pairs (`tools/calibrate_detour.py` → `resources/detour_model.json`):
  ratio 1.089 (h≈66 km) → 1.388 (h≈709 km); km error MAPE 17.1 %, p90 35.2 %, max 74.7 %; minutes MAPE 18.4 %.
- `HybridRouting`: fixture graph when every point is ≤ 2 km from it; graph + straight access legs when ≤ 20 km;
  otherwise synthetic (`approxDistances`). A point > 60 km from any town → `UNREACHABLE`.
- Walk solver: two greedy constructions (Δscore/Δmin, Δscore) + 2-opt + replace + drop-and-refill; waits ≤ 60 min
  for opening; brute-force check 200 seeds (≥ 0.9 × optimum in ≥ 190). 60 candidates: 9 ms (2 h), 27 ms (4 h),
  165 ms (8 h) on the sandbox desktop. Drink walks start ≥ 18:00, museum walks ≥ 10:00 by default.
- Brand allow-list `tests/brand_allowlist.txt`: only `links.{navigator,maps,web}` values in engine output and
  `handoff_*` Android keys. The catalogue files and the composed world are deny-list scanned.
- Coverage gate raised to 95 % (`make coverage-planner`).

## S3-R2 — Sprint 3, round R2 (branch dev/S3-R2 from main 6a3c50e)
Inputs merged: origin/des/sprint-3 @ 0beef17 (5.8–5.13, §8 in 5.1–5.5, components §17.5–§23, motion §2.4, copy §15,
DesignTokens — `tools/sync_design_tokens.py` run) and origin/arch/sprint-3 M1 @ 0a8757f (API v2 + contracts on the
sample catalogue). Default world is now `russia_v1`; `EngineHost` calls `load_catalogue` after the worlds
(`EngineTimings.catalogueMs`; e2e asserts engine start ≤ 5 000 ms).

### DEV-300 network, images, permissions
- OkHttp 4.12.0 (UA `Verst/0.3 (Android; +https://github.com/pazzia/Verst)`), Coil 2.7.0 (`VerstApp` is the
  `ImageLoaderFactory`, 64 MB `cacheDir/images`, cache headers ignored, offline = disk cache only).
- `NetworkConnectivity` (default-network callback) feeds `Connectivity.network`; the debug «нет сети» is
  `simulatedOffline` on top.
- `PhotoFrame` (components §18): 3 : 2, crop (portrait bias −0.35) or contain on the mat (decided from the
  decoded size), scrim + credit, «ФОТО РАЙОНА», the 7 vector placeholders, `photoFadeIn`.
- Manifest: exactly INTERNET, ACCESS_NETWORK_STATE, ACCESS_COARSE_LOCATION, ACCESS_FINE_LOCATION (a CI step diffs
  the merged manifest), no `usesCleartextTraffic`. Decision: `network_security_config` allows cleartext only for
  127.0.0.1 / localhost (MockWebServer in e2e S3-6).
- «О данных» from the debug panel and from Road ahead's «Расстояния приблизительные · О данных».

### DEV-301 location (5.12)
- Rationale sheet «Откуда поедем?» («Разрешить» → coarse, «Выберу сам» → ОТКУДА input) on the first «Куда
  угодно», the first «По городу» or a tap on «ВЫ: …»; never again once answered.
- Fix → `geo_nearest`: the origin town names «ВЫ: <ГОРОД>», the trip starts at the fix itself. Outside Russia →
  the state block, ПОЕХАЛИ disabled. Coarse → «примерно, по сети» + «Точнее» (fine dialog). Online → Nominatim
  reverse «ул. Советская, 1 · вы здесь». Denied / blocked / off / timeout → the deck toasts with their actions.
- Decision: the denied «plate» is the plate toast with «Выбрать» (6 s), not a persistent plate.

### DEV-302 search (5.12 §2)
- Typeahead = `geo_search` (offline, towns + places). An address-like query (digit, comma, ул/пр/пер/д/наб/пл/ш)
  shows the helper line and «Найти адрес «…»»; the IME «Найти» submits too. Never per keystroke.
- `NominatimClient`: `/search` (`countrycodes=ru`, `accept-language=ru`, `limit=5`) and `/reverse`, one shared
  1 req/s bucket (a second call waits — no toast), 24 h in-memory cache, offline → the hint row, no request.
  «© OpenStreetMap» under the rows. e2e journeys point it at a closed loopback port (no real traffic from CI).

### DEV-303 budget fit (5.8)
- `planOutcome` (v2 `outcome`): `no_fit` → Drive «Смотреть варианты» (auto-advance) → the no-fit screen (limit
  sign, engine text, minimum plate, options, «Показать самый экономный вариант»). An option → Instruments with it
  applied (raise → the exact «до 42 000 ₽», needle interpolated; shorten / cheaper → the ready route or a longer
  pace) → ПОЕХАЛИ again. The minimum opens Road ahead over budget everywhere; Waybill «Подогнать под бюджет →»
  re-plans the same request.
- Road footer: «ПУТЕВОЙ ЛИСТ · ✓ В БЮДЖЕТЕ» / TightDot + «ЧУТЬ БОЛЬШЕ: +N ₽» / «ПЕРЕРАСХОД». Waybill lever lines,
  «Сверх бюджета». Replace sheet: red dot + «не в бюджете» on `breaksBudget`. D-1 dots (yellow / red).
  Instruments caption suffix from `estimate.outcome` (decision: an engine without the fitter answers `plan` over
  budget — then no suffix, never a false «в бюджете»).
- `CostCalculator` explicit rooms (`NightUnitDto.rooms`, `HotelPriceDto.rooms`, null = ceil(adults/2)); Kotlin
  unit test now, the contract cases come with ARCH-301.
- M2 merged (arch/sprint-3 @ fde7aab: ARCH-301 fitter + G13, ARCH-302..306 as built). The CEO case now plans
  (G13: 58 400 → 27 400 ₽, the short ring). e2e S3-1 asserts it strictly: a fitted plan ≤ 31 500 ₽, or the
  no-fit screen → an option with `fits` (Тула, cheaper route, shorten, else raise) → a plan within it.
- `BudgetOptionDto.fits` / `dailyKm`: a cheaper-route option with `fits: false` says «дешевле, но больше бюджета»
  (pending copy) and never «помещается в бюджет».

### DEV-304 cards (5.9) / DEV-305 focus
- Only sights and hotel nights are tappable (row tap + click semantics); fuel/rest/start/finish/food have no
  click semantics (Robolectric test). Card = `poi_details`: kind line, PhotoFrame + credit (link to the file
  page), hotel «Фото района» + the fictional note, description (6 lines, tap for more), facts, «Выбрать отель» /
  «Заменить» / «Убрать эту точку», bar ODbL line.
- Focus: the exact scroll offset (`roadScrollY`, also in last.json) is restored, then the row is brought into view
  if needed; `returnToItem` = `dash.pressed` flash 1 200 ms (none under reduced motion).
- Not built: the mini sign in the card title row (the shared BottomSheet header), TalkBack focus move, D-7.

### DEV-306 «По городу» (5.10 / 5.11)
- Windshield plate «По городу · пешком»; CityScene, street plate (+ house square), presets from `city_presets`
  (unavailable hidden, «Свой маршрут» last), 18+ asked every time (children → «не с детьми» + toast; «Нет»
  sends nothing), custom sheet (duration, interests, pace, budget, return), ПОШЛИ (walker + loading arc),
  `NO_CITY` / `NOT_ENOUGH_POIS` plates. Walk result: city strip, WalkTitleSign, chips, ±15 % line, the walk
  hand-off (parts), responsible plate, walking column, «Другой вариант», cost plate, save / share.
- The caption start time follows the engine's default rule (now rounded up to a quarter hour, ≥ 18:00 for drink
  walks, ≥ 10:00 for museums) in device time; `city_presets` has no town tz (ask: add `tz` or `startAt` per
  preset). The walk result shows the engine's `startAt`. The walk title sign carries «≈ 6,0 км» (§21).
- Decision: walk share text is composed on the phone (no engine share for walks) and carries the responsible line.

### DEV-307 hand-off (5.13)
- Engine `handoff` links (day `fromHere`, `fromStopId`, walk); R1's `NaviLinks` stays as the fallback when the
  engine call fails. Day header link → day menu; stop menu first item `handoff_from_stop`; target line resolved
  from the installed apps (navigator → maps → web; walk maps → web); truncated note; toasts after a web fallback,
  offline without an app, all links failing. Robolectric `HandoffLauncherTest` (ShadowPackageManager).
- Allow-list = `android:handoff_*` from `brand_allowlist.txt` (Python and Kotlin); `brand_handoff_keys.txt`
  removed; the old `stopmenu_yandex_*` keys are neutral again in the mock overrides.

### DEV-308 saved trips schema 2
- `SavedTripDto.kind` (`trip` | `walk`), `walk` (the city_route result), `budgetStatus`; schema 1 reads as trips
  and is written as 2 on the next save; schema 3+ is kept aside. «Мои поездки» shows walks with the walker plate.

### DEV-309 journeys
S3-1 (skipped until ARCH-301, see above), S3-2 + S3-3 card / focus / offline placeholder, S3-4 Ярославль walk →
web pedestrian link, S3-5 Пермь synthetic route + «О данных», S3-6 address search on MockWebServer.
`budgets_s3.json`: `cityRouteMs`, `ceoPlanMs` (when S3-1 runs).
Photos: the M1 sample catalogue names files that do not exist on Commons, so on CI the sight cards show «Фото
пока нет» / error placeholders; real photos come with the data run (ARCH-302).

### Provisional copy (strings_pending_copy.xml)
`card_per_night` «за ночь», `navigator_type_address` «У», `walk_distance_m` «%d м», `debug_mock_location`,
`windshield_meta_round_trip` «туда и обратно», `budget_option_cheaper_sub_over` «≈ {amount} ₽ · дешевле, но больше
бюджета». Deck keys replaced the R1 ones (`navigator_location_deny` →
`loc_manual`, `navigator_location_failed` → `loc_timeout`, `stopmenu_web_fallback` → `handoff_web`).

Fix found by run 52: Coil 2's `rememberAsyncImagePainter` resolves its size from the first draw. `PhotoFrame` draws
the painter only once it has loaded, so a real URL stayed «loading» forever (it hit the hotel area photo in S3-2). The
request now has an explicit 1200 × 800 size.
## ARCH-301 — budget fitter (M2)
- `Planner.plan` = plain plan → ADR-0011 ladder → fitted plan (`budgetFit`) or `fit.NoFit`; the bridge returns
  `{"outcome": "no_fit", "minimum", "options", …}` (contracts `plan-no-fit.json`, `estimate-no-fit.json`).
- **Kotlin contract change:** `cost.units.nights[].rooms` and `options[].rooms` may be present (explicit family
  rooms); `CostCalculator` must use them instead of `ceil(adults/2)` and compare `rooms × price` for the
  `cheaper_overnight` hint. `cost_recompute_cases.json` has 6 new `rooms_*` cases (45 in total).
- Alternatives may carry `breaksBudget: true`; a fitted trip carries `budgetFit`; `estimate` returns
  `budgetStatus` (`fits` | `small_overrun` | null) and `outcome`.
- A crew patch on a trip with explicit rooms → `INVALID_INPUT(crew, replan_required)`.
- G13 CEO case: 58 400 → **27 400 ₽** (fits, short ring). Probes: Москва → Волгоград 3+1 at 8 000 ₽ → no_fit,
  minimum 37 900 with shorten 20 800 / closer town 14 400 (`fits: false`) / raise to 38 000.

### S3-R2 CI
Runs 45–51: compile, smart cast, JVM clash and e2e fixes (see the commits). Run 52: the Coil size hang. Run 54:
G13 bundle counts in the Kotlin contract tests. Run 55: device parity count (G13 byte-equal on the phone). **Run 56
(40139317399) on 11e4e06: green**: main e2e 14 tests, process death × 2, real GPS. S3-1 fitted 27 400 ₽ in
4 217 ms; the city route took 79 ms on the emulator.

### Asks for the Architect
- `city_presets`: add the town `tz` (or `startAt` per preset), so the 5.10 caption matches the engine's start.
- Real data with Commons photos (ARCH-302 run): the sample names fail, so CI shows only the placeholder states.

## S3-R3 — Sprint 3, round R3 (branch dev/S3-R3 from main e2e1bd2)
Inputs merged: origin/des/S3-QA @ 536869f (R2 visual QA, pending copy into the deck, IME / stop-menu / highlight
specs; `tools/sync_design_tokens.py` run: `color.overlay.returnFlash`, `motion.returnToItem.holdMs`).

### R2 gaps closed
- **5.9 C2 mini sign** in the card title row: `BottomSheet(leading = …)`; the row's RoadSign at 0.7 (shared
  `Modifier.scaled`), bars the §21 bar sign (walk cards now carry the stop kind as the tag).
- **TalkBack focus back to the row** (5.9 §5): the Road / walk rows are `focusable()` with a `FocusRequester`;
  after the scroll restore the returned row requests focus. Compose then sends TYPE_VIEW_FOCUSED and TalkBack
  follows it. e2e S3-3 and the D-7 journey assert `SemanticsProperties.Focused` on the row.
- **D-7 «Сообщить об ошибке» (local)**:
  - Entry points: the stop menu item (3), the row's TalkBack custom action and card C10 (not on hotel cards,
    since the hotel is fictional).
  - The sheet has 4 radio rows, a comment (NaviInput look, ≤ 280) and «ОТПРАВИТЬ», disabled until a reason is
    picked.
  - Decision: there is no feedback endpoint, so a report is appended to `files/reports/queue.json`
    (`ReportDto`, schema 1, the newest 200, `sent = false`), written by the flow's one writer.
  - Toast «Спасибо, проверим» online, «Отправим, когда появится сеть» offline. Event `feedback_sent` goes to
    logcat (`VerstEvent`).
  - Ask for the Architect: a feedback endpoint (or a `report` call that keeps the queue on the engine side).
- **Waybill e2e shot** `62b-waybill-ceo-levers`, scrolled to the lever lines.
- **Real Commons photos before the data run.** `CommonsPhotos` is a Kotlin port of `catalogue/photos.py`, with a
  parity unit test on the Python output. The debug panel «Настоящие фото Commons» replaces each card's image
  with 5 real files in turn, covering landscape JPEG, portrait JPEG, SVG→PNG and transparent PNG.
  e2e `r3RealCommonsPhotosOnTheCards` opens 5 cards online (CI has internet) and requires ≥ 3 loaded
  (screens 80-commons-0…4).

### S3-QA findings (Android side)
- P1-01 Navigator with the IME (5.12 §5):
  - Fixed: the header with «GPS ●», the focused field and the helper line. Only the list scrolls, starting
    at the top on a new query; the «Найти адрес» row comes first and «© OpenStreetMap» sits under the address
    rows.
  - The other field collapses to a 28 dp line (tap ОТКУДА = edit it).
  - «Моё местоположение» moves into the list while ОТКУДА is being typed.
  - Autofocus: КУДА after a hand-picked ОТКУДА, not after a GPS fix (`focusToField`).
- P1-02: `walk_shorter` when the engine walk is ≥ 30 min shorter than `input.durationMin`.
  `WalkRouteDto.shorterReason` / `startsTomorrow` are ready for the Architect's fields; until then «tomorrow»
  comes from `startAt` + `tz`.
- P1-03: free walk footer «Бесплатно · вход везде свободный».
- P1-04: the city plate breaks only at a space or after a hyphen (U+200B after «-», `LineBreak.Heading`,
  `Hyphens.None`). The plate grows to 120 dp on the measured longest piece, then the text scales to 80 %.
  The sign column is `widthIn(min = 68)`.
- P1-05: no credit under a placeholder. The hotel note is `card_hotel_fictional_nophoto` until the area photo is
  on screen. The engine description of a fictional place («Демо: вымышленная гостиница») is not shown.
- P1-07: `overlay.returnFlash` held 400 ms, then an 800 ms fade. Under reduced motion it is static for 400 ms.
- Stop menu per components §22:
  - `ActionItem` rows (min-h 52, pressed `dash.pressed`) with 1 dp `dash.control` dividers.
  - The hand-off item is omitted for fuel / rest stops and for stops without coordinates.
- P2-01: walk km without a trailing zero («≈ 6 км»).
- P2-06: the fixture shots are consistent (small overrun ≈ 3 %; only a dearer alternative breaks the budget;
  NO_CITY starts at «Толбухино»).
- P2-08: HOURS_UNVERIFIED is a muted line, and only when a stop really has default hours.
- 5.10 caption (P0-01, app side): `WalkStart` follows the engine windows (day 09:00 / museums 10:00 → end by
  22:00, drinks 18:00 → end by 23:00, else tomorrow) in the town zone. It prefers a preset `startAt` when the
  presets carry one. Decision: the zone is Moscow until `city_presets.town.tz` lands.
- `strings_pending_copy.xml` now holds only `debug_real_photos` (the new debug label, for the Designer). Every R2
  key reads from the deck.
## S3-QA engine round (Architect, on main e2e1bd2)
- **P0-01 walk start** (ADR-0013 "Daytime windows"): `city_route` → `startAt` (town local time), `startsTomorrow`,
  `startNoteRu`; `city_presets` → `town.tz`, `now` (engine local), and per preset `startAt` + `startsTomorrow`.
  Use these for `city_caption_meta_tomorrow` / `walk_header_tomorrow`; never the device clock. `geo_nearest` and
  every `town` object now carry `tz`. Contracts `city_presets-late.json`, `city_route-tomorrow.json`.
- **P1-02 shorter walk:** `shorter` (null or `{reason: places|budget, requestedMin, actualMin, messageRu}`) and
  `requestedDurationMin`; contract `city_route-shorter.json` (8 h museums in Ярославль → 5 ч 30 мин).
- **P1-06 no-lodging plate:** the `NO_LODGING` warning is one sentence per night and no longer repeats the
  nearest hotel; the overnight stop's `note` («Ближайшая подходящая: …, N км») is the second line of the same
  plate. A substitute is named only within `NEAREST_MAX_KM = 60` km along the route of the night stop (the
  320 km «Волжский откос» case now names none). G01–G13 unchanged.
- **Data run:** `data.yml` now also requests 50 random `Special:FilePath` card URLs (plus 400/500/960 px for
  comparison) and fails under 95 % (`tools/data/check_photos.py`, `report/photos_check.json`).

### S3-R3: Architect S3-QA engine round merged (arch/sprint-3 @ 7795e5f)
- **Caption (P0-01).** It uses the engine's per-preset `startAt` + `startsTomorrow` from `city_presets`, for
  ready presets at their default duration, so it never reads the device clock. A custom walk, or a changed
  duration, uses `WalkStart` (the same windows) in `town.tz`.
- **Walk header.** «Завтра: …» compares the `startAt` date with today in `tz`, so a saved walk reopened the next
  day reads «Старт …». The engine's `startsTomorrow` is used only without a start time.
- **Shorter walk (P1-02).** The engine's `shorter` decides. `reason = places` shows the deck `walk_shorter` with
  the chip's whole hours; another reason shows the engine's `messageRu`.
  Ask for the Designer: `walk_chip_duration` is `%d ч`, so «5 ч 30 мин» shows as «6 ч». A string parameter
  would allow «5,5 ч».
- **No-lodging plate (P1-06).** One plate per night. The `NO_LODGING` sentence is followed by the night's
  `note` («Ближайшая подходящая: …») as a second line (`road.warning.nearest`). Duplicate plates are dropped.

### S3-R3 CI
- Runs 58–63 fixed, in order:
  - a split `private set`, and a qualified BoxScope extension call;
  - an NBSP assert;
  - the card report without a place id, and the Navigator list getting no height above a ≈ 400 dp emulator
    IME (fix: no back link while typing, tighter panel);
  - a cross-module smart cast, and a duplicate SHORTER_THAN_ASKED plate.
- Run 64 attempt 1: RealGpsTest timed out waiting for the emulator's `geo fix` («LocationOracle: no location»).
  Nothing in R3 touches that path, and run 61 passed it. **Attempt 2 (40143628282-2) on d202218: green**:
  main e2e 16 tests, process death × 2, real GPS.
- Real Commons: 5 of 5 cards loaded on CI (landscape crop, portrait, the SVG coat of arms in contain mode,
  Example.jpg, the flag as a hotel area photo).
- Ask for the Designer: the Пермь synthetic route shows three identical «Не нашли ночёвку…» plates (one per
  night). A day prefix (a key such as `road_warning_day` «Ночь {n}: …») would tell them apart.
## ARCH-302 — real catalogue (M3)
- `verst_planner/resources/catalogue_*.json.gz` = `wd-20261025-r7.1`: **1 114 towns, 11 817 POIs (9 608 with a
  photo), 3 284 bars**, 0.67 MB. It replaces the sample, so `russia_v1` (the app's `DefaultWorld`) is the real
  country now. G01–G13 run on the fixture worlds and are unchanged.
- Contracts v2 were regenerated from the real data (ids are Wikidata Q-ids / OSM `n…`/`w…`). On `russia_v1`
  the CEO case gives 26 300 ₽ (fits; G13 on the fixture world stays 27 400 ₽).
- Every `town` object carries `tz`; `city_presets` gives `now`, `startAt` and `startsTomorrow` (S3-QA above).
- Photo URLs: 50/50 resolve at 800/400 px in CI. Expect real photos on cards; the placeholder states remain for
  the ~19 % of POIs without a P18 image and for offline use.
- Rebuilding: `data.yml` (push to `data-request`) → `bot/data-<n>` (catalogue + report) and `bot/raw-<n>` (raw
  responses). The builder is rerunnable in the sandbox from `bot/raw-<n>` (see ADR-0012 As-built).
- Timings (sandbox desktop): engine import 133 ms, `load_catalogue` 206 ms, plan Москва → Екатеринбург 557 ms,
  СПб → Сочи 406 ms, `city_route` 4 h in Казань 63 ms, `geo_search` 2 ms. A phone is about 5× slower.

## S3-R4 — Sprint 3, round R4 (branch dev/S3-R4 from main 6c071d5)
Inputs merged:
- arch/sprint-3 @ 0539a1e: the real catalogue wd-20261025-r7.1 (1 114 towns, 11 817 POIs, 9 608 with Commons
  photos, 3 284 bars), with the v2 contracts regenerated. Backend, contracts and data.yml are taken exactly as the
  Architect's tree; backend `make check`: 408 tests OK.
- des/S3-QA2 @ 9f92c56: `walk_chip_duration_text`, `road_night_prefix`, `debug_real_photos`.
  `strings_pending_copy.xml` is now empty.

### Copy
- Walk chip «3,5 ч», and the `walk_shorter` note in the same half-hour format.
- «Ночь N: не нашли …» when more than one night has a NO_LODGING plate. The substitute from the night's note
  stays as the plate's second line.

### Real catalogue fixes
- The walk / preset screenshot tests read availability and the hand-off part count from the contracts. The real
  Ярославль walk is split into 2 parts, and «По рюмочным» is unavailable there now.
- The shorter-walk shot checks every walk contract against the engine's `shorter`.
- PhotoFrame: «contain» now needs real transparency (a 9 × 9 pixel sample), not just an alpha channel. The opaque
  PNG collage of Ярославль (the hotel area photo) now crops like every other photo.
- Walk part buttons: «Открыть Яндекс Карты в браузере» on line 1 and «Часть 1 из 2» on line 2 (was clipped).

### Startup (S3-R4)
- Run 70, catalogue at boot: «ready» took 3.7 s in the startup test and 7.6 s on the first launch after install
  (Python 1.8 s, import 3.2 s, catalogue 2.0 s).
- Over the 3 s line, so the engine now reports «ready» after the fixture worlds + self-check. The catalogue and
  a second self-check (for its time zones) load right after on the `verst-python` thread. Every engine call is a
  suspending call on that one thread, so the first answers queue behind the catalogue and the Windshield shows
  its shimmer meanwhile.
- Run 71 (emulator):

  | Launch | Ready | Catalogue (background) |
  | --- | --- | --- |
  | First after install | 4.2 s (Python extraction alone 3.0 s) | 0.6 s |
  | Startup test | 2.8 s | 1.4 s |
  | Later boots | 0.8–1.8 s | 0.5–0.9 s |

  Plan Золотое кольцо took 4.0 s, a walk 0.25 s and the CEO plan 4.2 s.
- `EngineStartupTest` records `readyMs` and `catalogueMs`, and asserts ready ≤ 5 s and catalogue ≤ 3 s.

### Journeys on the real catalogue (e2e)
- S3-1: the CEO case is 26 300 ₽ (fits).
- R4 search (`geo_search`, offline): Екатеринбург, Владивосток, Казань, Сочи and Мышкин (pop. 5 647) are all
  the first row.
- R4 cards: real catalogue photos with author and licence, debug override off. 6 of 7 Golden Ring sights loaded;
  Музей шоколада has no photo, so it shows «Фото пока нет».
- R4 walks:
  - Казань «Обзорный»: 5.7 km, 10 stops, free.
  - СПб «Музейный»: Эрмитаж, Кунсткамера, Меншиковский дворец, 6 ч.
  - СПб «Пивной»: 18+ gate, 18:00, shorter 3,5 ч of 4.
- The walk journeys choose presets through the flow with an adults-only crew. The plate tap is covered by S3-4.
- logcat ring 16 MB: the 19-test main run outgrew the default buffer and hid one failure's logs.

### Asks
- Architect:
  - Commons `author` fields can be whole sentences («This photo was taken by Anton Zelenov. Please credit
    this…»); the credit line ellipsizes them. A cleanup in the data build would help.
  - The СПб «Музейный» walk is 3 stops in 6 h, which is plausible (long dwells), for a look.

## Release S3 engine polish (arch/release-s3 from main be0a266)
- **Photo credits** (`build_catalogue.clean_author`): Commons «Artist» → a short name (≤ 40 chars, ≤ 4 words):
  no HTML, URLs, e-mails, «This photo was taken by …», «Original uploader was …», «Own work», camera
  locations, licences or timestamps; otherwise `author: null` and the label stays «Фото: Wikimedia Commons ·
  <licence>». Before: 191 of 3 503 credits were sentence-like or > 40 chars (max 60, cut mid-word); after: 0
  of 3 354 (15 without author). `test_credits_are_short_names` checks the whole catalogue.
- **Museum walks** («Музейный»): a museum gets 50 min × pace, a big one (≥ 40 sitelinks) a flat 90 min with
  the stop note «Большой музей: за 1 ч 30 мин — только главное»; up to 5 museums and at most 2 short sights
  (churches, monuments, squares) between them. 6 h: СПб 3 → 5 stops (Русский музей, Эрмитаж, Кунсткамера, Спас
  на Крови, Невский); Москва 3 → 5, Казань 3 → 5, Ярославль 3 → 5; 4 h: 2 → 4 everywhere.
- **Open-data notice (S3-FINAL P1-2)**: `UNVERIFIED_PLACES` reads «Места — из открытых данных: часы и цены
  уточняйте» and carries `"level": "info"` (5.5 §9: the info line, not a yellow plate). Warnings without
  `level` are warnings.
- **Area photos (S3-FINAL P1-4, 5.9 §3)**: `meta.areaBlock` lists the files that may not be «Фото района»:
  collages/montages/maps/flags/coats of arms by file name or by a category that says what the file is
  («Montages of Ufa», «Flags of …»), non-JPEG/TIFF/WebP, < 800 px wide, aspect > 2.5. The hotel card uses the
  town photo, else the best square/embankment/viewpoint/park photo of the town, else none (city placeholder).
  **971 of 1 116 towns keep an area photo** (943 own, 28 fallback; was 1 085 incl. collages such as
  «Yarolslav colage.png» → now «Red Square in Yaroslavl 01.jpg», Казань → «Freedom Square, Kazan»).
  Sizes and categories come from `data-photos.yml` (bot/photos-1; also a step of `data.yml`).
- Catalogue `wd-20261025-r7.2` (rebuilt from bot/raw-7 + bot/photos-1): 0.676 MB. G01–G13 byte-identical.
- `test_cancel_from_other_thread` pinned to the case clock (it failed on main once the system date passed
  G03's start).

## S3-RELEASE (branch dev/S3-RELEASE from main be0a266)
Inputs merged:
- des/S3-FINAL @ fe8cd87: final QA, no P0; specs 5.5 §9, 5.9 §3, 5.12 §5 and components §22 updated; no
  token change.
- arch/release-s3 @ b5b23c2: short photo credits, museum walks with 4–5 stops, open-data `level: info`,
  single-photograph area photos, catalogue r7.2. Backend taken exactly as the Architect's tree; `make check` OK.

### S3-FINAL P1 (Android)
- P1-01: a GPS fix (gps → On) clears focus and hides the IME together. The IME being up is the typing layout
  even without a focused field (header + field fixed), so the panel never collapses to an empty bar.
- P1-02:
  - `UNVERIFIED_PLACES`, and every warning with `level: "info"`, is a muted info line (`info` 14 + `type.body.sm`
    `text.muted` + «О данных») under the intro.
  - With a synthetic route both notes share one line: `route_approx_open_data`.
  - Yellow plates are left for warnings about this trip.
- P1-03: the report sheet has no autofocus, so the IME stays down until the comment is tapped. The comment +
  «ОТПРАВИТЬ» then follow the IME inset (`BringIntoViewRequester`, re-run on every inset change).
- P1-04 (area photos) is the Architect's. With r7.2, Ярославль «У Стрелки» shows a single street photograph.

### P2 done
- NBSP before «—» in the responsible line.
- No per-row «Часы работы уточняйте» when every stop has default hours (the top line says it once).
- Theatre → museum pictogram, church / cathedral → the monastery pictogram (sign and placeholder).
- Card descriptions that only repeat the kind line («площадь в г. Иваново») are hidden; others are capitalised
  and end with a full stop.
- A credit without a usable author reads «Фото: Wikimedia Commons · <licence>».
- Left as is: P2-05 (two hand-off parts on 4–6 h walks, «acceptable for release») and P2-06 (bar plate
  instead of the frame).

### Tests made independent of the regenerated data
- V2ContractsTest: licences, walk hand-off parts, preset availability, and the optional area photo.
- The engine-shorter shot sets a shorter result on the contract walk (r7.2 museum walks fill the asked time).
- The responsible-line shot expects the NBSP.

### New e2e checks
- **Offline-cached photo** (`r5OfflineCachedPhotoStillShows`):
  - Coil's memory + disk caches are cleared first.
  - A real photo is seen online (Троице-Сергиева лавра), then the memory cache is cleared and the app goes
    offline.
  - The same card still shows the photo from the 64 MB disk cache (screen 95).
  - An unseen sight with a photo URL (Ростовский кремль) shows «Фото загрузится, когда будет интернет» (96).
- **Report sheet:**
  - 84: the sheet as opened, with the IME down and all four reasons + the button visible.
  - 84b: after a tap in the comment, with the button above the IME.

## Sprint 4 engine (arch/s4-engine from main cf8f335) — contract changes for the Developer
API v3 is additive (`mobile.API_VERSION = 3`; the contracts stay in `docs/contracts/v2/`, 38 files).
- **Trip stops:** `kmDriven` (driven km from the trip start, detours included) and `kmLeft`; the last stop has
  `kmDriven == trip.km`. Rest and fuel rows have `amenities` (wc, cafe_at_fuel, playground, walk, view, parking,
  ev_charger, 24h). A second roadside break of a day reads only «Перерыв 15 минут.».
- **Hand-off (car):** `order = ["maps", "navigatorNext", "web"]`; `parts[0].links.navigatorNext` (the next point
  only) and `parts[0].next`; `links.navigator` (the whole day) stays for a signed build. `options.signing =
  {"client": id}` adds `&client=` to the app links and returns `toSign` (sign each string with SHA256withRSA,
  Base64, URL-encode, append `&signature=`).
- **Moods:** `mood: "fun"` «Весело и познавательно» (interesting stops in the rest slots, ≤ 15 min detour, for the
  crew; reason «Весело и познавательно: …»). The UI shows «Спокойно» (`calm`), «Весело и познавательно»
  (`fun`), «Только доехать» (`just_drive`); `more_stops` stays accepted for saved trips.
- **Parking:** a «Парковки» cost line (`key: "parking"`) with per-stop `breakdown` and
  `cost.units.parking[] = {stopId, name, rubPerHour, hours, rub, source}` (`rub` null = unknown). Present only
  in `russia_v1`. CostCalculator: see «M6 answers» §3 below (superseded).
- **Walks:** `crew.dog`; children never block a drink walk (`CHILD_BARS` warning); `DOG_INDOOR` warning and
  stop `noteRu`; `crewNotesRu`; preset `dog_walk` «Прогулка с собакой»; `durationMin: null` = «без ограничения»
  (`unlimited: true`, no `arriveAt/departAt/endAt/durationMin`, ≤ 12 stops); every stop has `hours: {todayRu,
  openNow, source}`; `interestsWidened`; `shorter.reason` gains `reach`; `NOT_ENOUGH_POIS.suggestions[]` with
  `clearExclude` / `durationMin` (null = unlimited) / `preset` and `stops` — each solved, never the current
  value. The app still resets `exclude` on any parameter change (docs/bugs/s4-walk-filters.md a).
- **POI card:** `poi_details` gains `extractRu`, `extractSource {key, nameRu, licence}`, `cardLevel` 1–4,
  `quality`, `fee`, `website`; OSM hours replace the default hours text.
- **Rules (russia_v1 only):** open-data quality threshold, no sights within 12 km of a million-city centre
  unless the trip starts/ends/stays there, ≤ 1 religious per 3 sights a day, no same kind twice in a row,
  ≤ 30 % religious per trip, no second sight within 0.4 km of one already in the day (Красная площадь and
  the Mausoleum); МКАД/ЦКАД in the routing graph (ЦКАД tolls not priced yet).
- G01–G13 are byte-identical; G14–G17 (tests/golden/cases_s4) are rule checks on the real catalogue.

### M6 answers to the Developer's S4 questions (dev/S4 @ feb8b70)
Contracts: `docs/contracts/v2/` (38 files, new `plan-moscow-parking.json`); cost cases:
`tests/contract/cost_recompute_cases.json` (52, 7 `parking_*`).

**1. Walks** (`city_route`)
- Unlimited: send `durationMin: null`. Accepted since M4 (dac11bb); M0 rejected it. Result: `unlimited: true`,
  `durationMin: null`, `endAt: null`, stops `arriveAt/departAt: null`, ≤ 12 stops; `requestedDurationMin` echoes
  the request. See `city_route-unlimited.json`.
- Dog walk: `preset: "dog_walk"` (title «Прогулка с собакой», outdoor kinds only) and `crew.dog: true` on any
  preset. A dog with an indoor stop gives the `DOG_INDOOR` warning and the stop `noteRu`. The input echo now has
  `crew.dog`. See `city_route-dog-walk.json` and `city_route-museums-with-dog.json`.
- Today's hours per stop: `stops[].hours = {todayRu, openNow, source}`. `todayRu` is «10:00–18:00», «24 часа»
  or «Сегодня закрыто». `source` is `curated` | `osm` | `default`; with `default`, show «часы уточняйте».
- NOT_ENOUGH suggestions: `error.suggestions[]`, at most 3. Each one was solved before it is offered, and none
  repeats the current value. Fields: `clearExclude: true` | `durationMin` (int or null = unlimited) |
  `preset`, plus `stops` (the stop count it gives) and `titleRu` (the chip text: «Вернуть убранные места»,
  «На 6 ч», «Без ограничения по времени», «Обзорная прогулка»…). Apply the fields; leave the rest of the form
  as it is. See `city_route-error-suggestions.json` (a beer walk in Миасс).
- Stale-result key: `result.requestKey`, also `error.requestKey` on NOT_ENOUGH_POIS. It is 16 hex digits over
  the normalised request (world, start, town, preset, duration, sorted interests, pace, budget, return,
  explicit `startAt`, crew incl. dog, adultConfirmed, exclude). The clock is not in it. Keep the key of the
  last request you sent and drop any answer whose key differs; equal keys mean the same request.

**2. Stop categories, parking, rest amenities, why, photo** (trip stops of `plan` / `replace_stop` /
`patch_cost`, added in the bridge, also on `alternatives[].stop`)
- `kind` stays the stop type (sight/rest/food/fuel/overnight/…). **`poiKind` is confirmed**: on sight stops
  only. It is the same vocabulary as `poi_details.poiKind` and `geo_search` rows (museum, kremlin, monastery,
  temple, park, viewpoint, embankment, square, monument, theatre, zoo, nature, interactive, playground,
  attraction…). The generic catalogue «attraction» is narrowed to the ADR-0015 category where the name or tags
  allow it.
- `parking` on sight stops: `{rub, rubPerHour, hours, source, zoneRu, whereRu, sundayRu, freeRu}` or null
  (no parking data: fixture worlds). The names are yours:
  - `zoneRu`: the zone or the evidence, e.g. «Москва: платная зона до 2 км от центра, 380 ₽/ч с 08:00 до
    21:00, ночью 200 ₽/ч», «Платная парковка по данным OpenStreetMap», «Платных зон рядом нет».
  - `whereRu`: where the car stands.
  - `sundayRu`: the Sunday and holiday rule; zones only, else null.
  - `freeRu`: why it is free at this arrival («Бесплатно: воскресенье» / праздничный день / ночью / вне
    платных зон), or null when paid.
  The sheet texts are on the stop, not in `cost.units.parking[]`. Those units stay numeric
  (`{stopId, name, rubPerHour, hours, rub, source}`, `source` zone | osm | unknown | free) because they are
  the CostCalculator input. See `plan-moscow-parking.json` (the Kremlin, 380 ₽).
- `amenities` on rest/fuel rows: unchanged since M3.
- `whyRu` on sight stops and in `poi_details`: one line, or null for curated sights and when the data is
  silent. Parts are joined with « · »: «Объект культурного наследия», «Советует Викигид», «Статьи в N языковых
  разделах Википедии».
- Photo source: `photoSource` on sight stops, and `poi_details.image.source`. Values: `p18` (the item's own
  image), `wikipedia` (the article image), `osm` (the `wikimedia_commons` tag), `geosearch` (a Commons photo
  taken near the place), `area` (the hotel card's area photo). For `geosearch`, `image.labelRu` already says
  «Фото поблизости: Wikimedia Commons · автор…».

**3. Cost parity** (`cost/recompute.py`, rule 5 of `tools/gen_cost_contract.py`)
- Parking is inside the subtotal, so it is inside the reserve base and the budget check. **Confirmed.**
- A replaced stop takes the alternative's own parking. **Your assumption is now the rule.** The alternative's
  `units` carry `parkingRub` (null = unknown price), `parkingRubPerHour`, `parkingHours` and `parkingSource`,
  only when the trip has parking data. CostCalculator:
  1. Remove the replaced stop's `ParkingUnit`.
  2. If `parkingSource` is present, put `{stopId: <replaced stop>, name: alt.name, rubPerHour, hours, rub,
     source}` in its place. If the replaced stop had no unit (a rest stop replaced by a sight), append it.
  3. The line is Σ known `rub`.
  The engine's `replace_stop` bakes the same thing into the units. `alternatives[].deltaRub` includes Δ
  parking, and it stays in after a crew change. Cases: `parking_replaced_stop` (no `parkingSource` → none),
  `parking_replaced_by_alt` (460), `parking_alt_unknown` (60), `parking_rest_replaced_by_sight` (900),
  `parking_reserve_budget`.
- The other stops' parking is not re-priced after a replace, even when their arrival moves. That matches
  tickets and keeps the offline recompute exact.

### Sprint 4 data (catalogue wd-20261025-r7.3: run-7 raw files plus `bot/extras-1`)
- **Shipped data:** 19 675 POIs. 8.3 k are Wikidata items; the rest are OSM-only, of which ≤ 6 playgrounds per
  town. There are 3 284 bars and 1 114 towns. The catalogue is 1.05 MB, and 1.29 MB with the worlds and
  resources, against the 2.5 MB limit.
- **Card levels:** 4 = 258, 3 ≈ 4.8 k, 2 ≈ 3.9 k, 1 ≈ 11.2 k (mostly OSM playgrounds and parks).
- **Extracts:** 4.7 k from Wikipedia, 0.55 k from Wikidata, 0.35 k from OSM. Wikivoyage listings name only
  136 items.
- **Photo sources:** p18 8.2 k; geosearch only 39. A nearby Commons photo is used only when its title shares
  the place's own words (two words when the name has two or more) and its class word. The looser match put
  «улица Шевченко» on «Памятник Тарасу Шевченко».
- **Builder excludes:**
  - names that are not sights: estate parts («Ограда…», «Главный дом…»), cafés, bare «Особняк», addresses
    ending in a house number;
  - POIs whose «(Город)» is more than 40 km away from their coordinates;
  - OSM names without Cyrillic or that are generic, and minor natural features;
  - websites that are map-service redirects.
- **Engine, open-data world only:**
  - The corridor keeps the best sights by quality, plus up to 4 more per 10 km within a 15-minute detour,
    for the fun stops.
  - The fun mood ranks the widened rest window together with the narrow one.
  - A playground is never a fun stop without a child.
  - Churches are never used as rest breaks.
  - A view of a cathedral is a viewpoint, not a temple.
- **Known limit:** the M-12 and M-4 trips get few sights and fun stops. The motorways bypass the towns:
  Vladimir, Гороховец and Козьмодемьянск are 20–60 min away, and the quality bar is 0.40. On M-11
  (Москва → СПб) the fun stops do appear. G17 therefore runs on M-11.

### M8: the tiered detour budget (Manager's decision on the M-12 / M-4 sparsity; open-data world only)
- **Detour budget for sights.** The quality bar stays at 0.40.
  - q ≥ 0.70: up to 45 min, at most 1 such sight per day.
  - 0.55 ≤ q < 0.70: up to 25 min.
  - Below 0.55: the old rule, a detour of at most 10 km.
  - Curated sights use their rating on the same scale (3.6 → 0, 4.9 → 1).
  - The order is now quality first, with the detour costing about 0.15 per 45 min.
- **Million-city centres.** A q ≥ 0.70 sight within the 45-minute budget may be a transit stop in a
  million-city centre. Moscow and St Petersburg (≥ 4 M) never are, because the detour model cannot see their
  centre traffic. The Фрязино ring still never touches Красная площадь.
- **Sight order and the lunch.** Secular sights are chosen first over the whole trip; religious ones follow
  while the trip stays ≤ 30 % religious. A sight that only pushes the lunch out of its window gets the lunch
  re-planned.
- **Fun stops.** When nothing is within 15 min in the rest window, a stop up to 30 min away is allowed.
- **Stop text.** Every sight with a detour ≥ 10 min ends with «Крюк ≈ N мин.» (rounded to 5). Detours count
  inside the day limit as before.
- **Rest planner fix.** It no longer inserts the same roadside break up to 200 times when the break cannot
  shorten a gap (a break point inside a long detour). This was only seen on the day-budget copy.
- **G14 (Фрязино → Екатеринбург, child, 600 km/day):**
  - Day 1: Владимир, Золотые ворота (крюк ≈ 35 мин).
  - Day 4: Екатеринбург.
  - 1 playground in the trip.
  - **Days 2–3 cannot have a quality sight inside the pace.** Day 2 is 480 km: Козьмодемьянск (q 0.61,
    24 min) needs 99 min, and only about 45 min are free; Нижний is 59 min off the road. Day 3 is 552 km and
    has no eligible sight at all: Сарапул's best is q 0.53 at 46 min, and the road passes neither Казань nor
    Елабуга.
- **G18 (Москва → Казань by M-12):** 8 sights, 7 of them with q ≥ 0.40.
  - In Moscow: the Kremlin, Измайловский парк.
  - On the road: Покрова на Нерли (крюк ≈ 30 мин) and Глухово.
  - In Казань: the Kremlin cathedral, Храм всех религий, Иске Таш.
  - Нижний is out of reach: 55–60 min off M-12, beyond 45.
