# ADR-0013: «По городу» — walking routes inside one city (orienteering solver)

Status: Accepted (Architect) · Date: 2026-10-24 · Refs: CEO Sprint 3 requirements 3.2, 3.2.1; Manager decision D6; ADR-0012 (catalogue); `docs/backlog-sprint3.md` ARCH-304, DEV-306, DES-302

## Context

The CEO is in Ярославль and wants a walk built from his wishes, not a car trip. The modes he named are:

- Обзорный: the top sights;
- Музейный: Санкт-Петербург and similar cities;
- «По рюмочным»;
- «Пивной»;
- a custom selection by parameters.

D6 fixes the following:

- walking only;
- custom parameters: duration 2/4/6/8 h, interests (история, архитектура, музеи, парки, еда, бары, виды), pace, budget, and the start at GPS or a chosen point;
- alcohol presets: an 18+ confirmation, a responsible-drinking line, no car;
- an orienteering solver: maximise score within the time budget; walking distance = haversine × factor; a reasonable dwell model; return to start optional.

## Decision

### Engine module

`verst_planner/city/` is a new package, stdlib only, independent of the car pipeline:

- `model.py`: `WalkInput`, `WalkStop`, `WalkRoute`;
- `pool.py`: candidates from the catalogue + fixture places;
- `score.py`;
- `solver.py`: the orienteering solver;
- `presets.py`.

It reads places through `PlaceRepository.places_near(point, radius_km, kinds)`, a new port method implemented by both the fake and the catalogue adapters.

### Input (`city_route(world, request_id, input_json)`)

```jsonc
{"start": {"lat": 57.6261, "lon": 39.8845, "label": "Ярославль, Советская пл."},   // GPS, an address or a town centre
 "townId": "Q…" | null,            // optional; else the nearest catalogue town of start
 "preset": "overview" | "museums" | "ryumochnye" | "beer" | "custom",
 "durationMin": 120 | 240 | 360 | 480,
 "interests": ["history", "architecture", "museums", "parks", "food", "bars", "views"],   // custom only
 "pace": "slow" | "normal" | "fast",
 "budgetRub": 3000 | null,            // per whole group, tickets + food/drinks
 "returnToStart": true,
 "startAt": "2026-10-25T11:00" | null,   // local time; null = now rounded up to 15 min (engine clock)
 "crew": {"adults": 2, "children": 0},
 "adultConfirmed": false,             // required true for ryumochnye / beer, else INVALID_INPUT(field=adultConfirmed, reason=required)
 "exclude": ["Q…", "n…"]}         // «другой вариант» / «убрать эту точку»
```

- Children with an alcohol preset → `INVALID_INPUT(field = preset, reason = children)`.
- A start farther than 15 km from any catalogue town → `NO_CITY` (a new code).

### Pool and scores

**Candidates.**

- Catalogue POIs, bars and fixture places of the kinds the preset allows, within radius `R = min(0.45 · v · T, R_max)` of the start. Here `v` is the walking speed, `T` the duration, and `R_max` = 3 km (2 h), 4 (4 h), 5 (6 h), 6 (8 h).
- The pool keeps the top 60 candidates by base score (ties → id).

**Popularity `p ∈ [0, 1]`.**

- catalogue: `log1p(sitelinks) / log1p(max sitelinks in the pool)`;
- fixture places: `(rating − 3.5) / 1.5` clipped to [0, 1];
- bars: 0.5, + 0.2 if `opening_hours` is known, + 0.2 for `ryumochnaya` in «По рюмочным».

**Interest weights `w(kind)`**: from `presets.py` (table below). For a custom route, `w` = max over the chosen interests, 0.15 for kinds outside them, and 0 for bars unless «бары» is chosen.

**Score** = `100 · p · w(kind) + 10 · heritage`. A diversity rule: the third stop of the same kind scores × 0.6, and each further one × 0.6 again.

| Preset | Kinds and weights | Gate (else hidden) | Defaults |
| --- | --- | --- | --- |
| Обзорный `overview` | sights, kremlin, monastery, church 1.0; monument, square, embankment, viewpoint 0.9; museum 0.6 (dwell capped 45 min); park 0.6 | ≥ 4 candidates | 4 h, normal |
| Музейный `museums` | museum 1.0; heritage sight 0.3 | ≥ 3 museums in R(6 h) | 6 h, slow; ≤ 4 museums |
| «По рюмочным» `ryumochnye` | ryumochnaya 1.0, bar 0.5, pub 0.3, food 0.2 (one snack stop) | ≥ 3 ryumochnye in R(4 h); 18+ | 4 h; ≤ 5 drink stops |
| «Пивной» `beer` | craft 1.0, pub 0.9, bar 0.5, food 0.2 | ≥ 3 pub/craft in R(4 h); 18+ | 4 h; ≤ 5 drink stops |
| Свой маршрут `custom` | from interests | ≥ 2 candidates | as chosen |

**Walking model.**

- Distance = `haversine × 1.30`. Street-network circuity in Russian city centres is typically 1.2–1.4; the expected error is ± 15 %, and the screen says «≈». It is documented in `resources/walk_model.json` together with the speeds.
- Speed: slow 3.5, normal 4.5, fast 5.5 km/h.
- A single leg ≤ 2.5 km; longer pairs are never adjacent.

**Dwell (min)**, scaled by pace (slow × 1.25, fast × 0.8):

| Kind | Dwell |
| --- | --- |
| museum | 75 (90 if sitelinks ≥ 40, 45 in Обзорный) |
| kremlin, monastery | 50 |
| church | 20 |
| monument, square | 10 |
| viewpoint, embankment | 15 |
| park, garden | 35 |
| food | 45 |
| bar, pub, craft | 40 |
| ryumochnaya | 25 |

**Opening hours.**

- OSM `opening_hours` is parsed with `verst_planner.hours`.
- Wikidata museums default to `Tu-Su 10:00-18:00`, churches to `08:00-20:00`, bars without hours to `Mo-Su 16:00-02:00`; everything else is always open.
- Every default is flagged `hoursVerified: false` → «часы уточняйте».

**Costs.**

- museum tickets as ADR-0012 §4;
- drinks per person per stop: ryumochnaya 300, pub/craft 600, bar 500 ₽;
- food 600 ₽.

The whole group is counted. If `budgetRub` is set, the solver treats it as a second knapsack constraint.

### Solver (deterministic; ≤ 60 candidates, so O(n²) per pass)

```
route = [start] (+ finish = start if returnToStart else open end)
repeat:                                   # 1. greedy insertion
    best = argmax over unvisited c, positions i of  Δscore(c) / (Δwalk_min + dwell(c))
           subject to: time windows (arrive within hours, leave before close), total ≤ T, cost ≤ budget,
                       leg ≤ 2.5 km, preset caps (≤ 4 museums, ≤ 5 drink stops)
    if none: break; insert best
2-opt on the sequence (minimise walking, keep feasibility)  # 2.
improve: for each stop s, for each unvisited c: replace s by c at the best position if score rises and feasible;
         then try inserting again; stop when a full pass changes nothing or after 200 moves        # 3.
ties → lower walking minutes, then id
```

- Fewer than 2 stops → `NOT_ENOUGH_POIS` (a new code; `field` = `preset`). The app offers a longer duration or another preset.
- Runs in < 50 ms on the desktop for 60 candidates and is cancellable between passes.

`ENGINE_VERSION` stays `0.1.0` this sprint. Every change is additive and old trips decode, so saved Sprint 2 trips never become `TRIP_INCOMPATIBLE` and the golden snapshots keep their `engineVersion`. `mobile.API_VERSION` becomes 2.

### Output (`WalkRoute` JSON; contract files `docs/contracts/v2/city_route-*.json`)

```jsonc
{"kind": "walk", "engineVersion": "<ENGINE_VERSION>", "id": "wlk_<uuid>", "titleRu": "Ярославль: обзорная прогулка",
 "townId": "Q…", "townName": "Ярославль", "townPrep": "Ярославле", "preset": "overview",
 "startAt": "2026-10-25T11:00", "endAt": "2026-10-25T14:52", "tz": "Europe/Moscow",
 "walkKm": 5.8, "walkMin": 78, "durationMin": 232, "returnToStart": true,
 "start": {"lat": …, "lon": …, "label": "…"}, "finish": {…},
 "stops": [{"id": "w01", "poiId": "Q…", "kind": "kremlin", "nameRu": "Спасо-Преображенский монастырь",
            "lat": …, "lon": …, "arriveAt": "…", "departAt": "…", "dwellMin": 50,
            "walkKmFromPrev": 0.9, "walkMinFromPrev": 13, "costRub": 600, "hoursVerified": false,
            "noteRu": "Часы работы уточняйте", "hasPhoto": true}],
 "cost": {"totalRub": 2400, "lines": [{"key": "tickets", "rub": 1200}, {"key": "food", "rub": 1200}], "budgetRub": 3000},
 "warnings": [{"code": "HOURS_UNVERIFIED", "messageRu": "…"}],
 "responsibleNoteRu": null | "Пейте умеренно, чередуйте с водой и едой. За руль — только трезвым.",
 "polyline": [[lat, lon], …],          // straight segments start → stops → finish (no street geometry offline)
 "input": { …the normalised input… }}
```

The walk is self-contained, so the app saves it as a trip of kind `walk` (`SavedTripDto` schema 2, DEV-308). There is no `engineState`: «другой вариант» re-runs `city_route` with `exclude`.

### App flow (DEV-306, DES-302)

- **Entry:** Windshield → «По городу». The start is GPS (ADR-0012 §5) or a chosen point.
- **Presets:** from `city_presets(world, lat, lon)` → `[{preset, available, count, defaultDurationMin, adultOnly}]`. Unavailable presets are not shown.
- **Alcohol presets:** an 18+ dialog every time. The «Пейте умеренно…» line is on the result and in the share text. There is no car hand-off; walking hand-off only (ADR-0014).
- **Result:** a list screen in the v5 visual language, with a stop card (ADR-0012 photos), «Пешком в Яндекс Картах», «Сохранить», «Поделиться» and «Другой вариант».

## Options rejected

- **An exact orienteering ILP.** No solver on the device; n ≤ 60 does not need it, and determinism matters more for tests.
- **Reusing the car pipeline with walking speeds.** The corridor, day-split and fuel concepts do not apply; it would distort A§6.
- **Street-network walking.** No offline street graph (ADR-0012).

## Tests (ARCH-304)

- Unit tests:
  - feasibility (hours, caps, leg length, budget);
  - determinism (same input → byte-identical JSON);
  - `exclude`;
  - gates;
  - 18+ and children errors;
  - the solver against brute force on 9-candidate random pools: its score must be ≥ 0.9 × the optimum, in ≥ 95 % of 200 seeds.
- Golden-like samples on `russia_v1` with the golden clock: Ярославль overview/custom/«По рюмочным» and Санкт-Петербург museums, plus the error cases. They are contract files `docs/contracts/v2/city_route-*.json`, regenerated together with the catalogue (`tools/gen_api_contracts.py`).

## As built (ARCH-304, `arch/sprint-3`)

- **Code:** `verst_planner/city/{presets,walk,route}.py`; the bridge (`mobile.city_presets` / `city_route`) builds the candidates from `places_near` (sights) and the catalogue bar grid.
- **Solver additions:**
  - Two constructions, Δscore/Δmin and plain Δscore, each followed by 2-opt, single replacements and drop-and-refill; the better result is kept.
  - A visit may wait up to 60 min for opening (5-min steps).
  - Lower-bound pruning: travel + dwell − the current waiting time.
- **Default start times (superseded by S3-QA P0-01, below):** drink walks start at 18:00 at the earliest, museum walks at 10:00, others at now rounded up to 15 min.
- **Daytime windows (S3-QA P0-01, spec 5.11 §9), in the town's local time** (`tz` of the town's region): day walks 09:00 → end by 22:00 (museum walks open at 10:00), drink walks (beer, рюмочные, custom with «бары») 18:00 → end by 23:00. `start = now rounded up to 15 min`; before the opening → the opening today; later than `closing − duration` → the opening **tomorrow** with `startsTomorrow: true` and `startNoteRu` «Сегодня уже поздно — старт завтра в 09:00». A walk longer than its window starts at the opening. An explicit `startAt` is kept as given. `city_presets` returns the same rule per preset (`startAt`, `startsTomorrow`), the town `tz` and the engine's local `now`, so the 5.10 caption and the 5.11 header always agree (`walk.planned_start`).
- **Shorter than asked (S3-QA P1-02):** a walk ≥ 30 min shorter than `durationMin` carries `shorter: {reason, requestedMin, actualMin, messageRu}` and a `SHORTER_THAN_ASKED` warning. `reason` is `budget` when a set budget is ≥ 80 % spent, else `places` («Получилось 2 ч 30 мин вместо 4 ч — больше открытых мест рядом нет»; the actual duration rounded to 15 min). The result also echoes `requestedDurationMin`.
- **Meal stop:** the «еда» interest (custom, ≥ 4 h) adds one meal stop of 45 min (× pace) near the midpoint, at the previous stop's place, not tappable. It is not a fictional cafe in a real city.
- **Measured** on the sandbox desktop, 60 candidates: 9 ms (2 h), 27 ms (4 h), 165 ms (8 h). Brute force: ≥ 0.9 × optimum in ≥ 190 of 200 random 8-candidate pools.
- **Errors:** `NOT_ENOUGH_POIS` (`field = preset`), `NO_CITY`, `INVALID_INPUT` (`adultConfirmed` / `preset` children), `CANCELLED` through `cancel(request_id)`.
