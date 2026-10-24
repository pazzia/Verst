# Verst — Sprint 3 backlog: budget that holds, real places and photos, all of Russia, city walks, navigator hand-off

Sprint: 3 · Owner: Architect · Acceptance: Manager · Visual acceptance: Designer · Base: `main` @ `5ca38d0` (CEO build mvp-mock-37)

**Goal.** The CEO plans a trip from his GPS position to any Russian town or address. The plan respects his budget, or says clearly that it cannot. Every sight and hotel opens a card with a real photo. He can build a walk inside a city (top sights, museums, bars) and hand any route to Яндекс Навигатор or Яндекс Карты. Everything except photos and addresses works offline.

References:

- ADR-0011 (budget fitting), ADR-0012 (open-data catalogue and images), ADR-0013 (city walking mode), ADR-0014 (navigator hand-off);
- `docs/architecture-android-mvp.md`, cited as M§n (§15 = Sprint 3, §5.4 = mobile API v2);
- `docs/backlog-sprint2.md` "Rules for every task" (still valid; differences below).

## Rules for every task (differences from Sprint 2)

- **Branches and roles:**
  - **Engine side (`backend/planner/**`, `tools/data/**`, `.github/workflows/data.yml`):** this sprint it is owned by the **Architect**, on branch `arch/sprint-3` (pushed often, never to `main`).
  - **Android:** the Developer works on `dev/<task-id>` branches.
  - **Designer:** `des/<task-id>`.
  - The Manager merges.
- **Contracts first.** The Developer builds against the JSON contract files in `docs/contracts/v2/` (ARCH-305) and the API spec in M§5.4, not against engine code. A change to a contract file is announced in `docs/dev-notes.md` under "Sprint 3 / contract changes".
- **Python DoD:** `make check` green; coverage `tools/stdlib_coverage.py --fail-under 95` (raised from 85); stdlib only inside `verst_planner/`. The data tools under `backend/planner/tools/data/` may import pymorphy3, but only in CI and only in `inflect.py`; everything else in `tools/data/` is stdlib and unit-tested in the sandbox on recorded samples.
- **Brand rule.** Real brand names are allowed only in `handoff_*` keys (ADR-0014). `tests/brand_allowlist.txt` lists the key patterns, and both deny-list tests honour it. Catalogue data is scanned too.
- **Golden trips** `G01–G12` on `central_russia_v1` must stay byte-identical, except with a written justification in dev-notes and Manager acceptance. New golden cases start at G13.
- **APK budget:** target ≤ 48 MB, hard limit 60 MB (unchanged). The catalogue data is ≤ 2.5 MB gzip (hard limit 4 MB, test-enforced).

## Order and dependencies

```
Week 1   ARCH-300 (ADRs, backlog, M§15/§5.4)  ──▶  everyone reads
         ARCH-302 data workflow ──(Actions run, bot/data-<n> merged by Manager)──▶ ARCH-303 catalogue world
         ARCH-301 budget fitter (fixtures only, independent of the catalogue)
         ARCH-305 API v2 + contract files (first cut on fixtures + sample catalogue) ──▶ DEV-30x integration
         DEV-300 network/permissions/images · DEV-301 location · DES-300…305 specs
Week 2   ARCH-304 walking solver + presets ── ARCH-306 hand-off ── ARCH-307 POI details
         DEV-302 search · DEV-303 budget UI · DEV-304 cards · DEV-305 focus · DEV-307 hand-off
Week 3   DEV-306 city mode · DEV-308 saved walks · DEV-309 e2e/budgets · DES-306 visual QA ─▶ DEV-310 fixes ─▶ CEO build
```

| ID | Title | Owner | Depends on | Estimate |
| --- | --- | --- | --- | --- |
| ARCH-300 | ADR-0011…0014, this backlog, M§15 and M§5.4 (API v2 spec) | Architect | — | 0.5 d |
| ARCH-301 | Engine: budget fitter (stage 12b), no-fit outcome with options, `breaksBudget`, explicit rooms in cost units + contract cases, G13 | Architect | — | 2 d |
| ARCH-302 | Data pipeline: `data.yml`, fetchers, `build_catalogue.py`, `inflect.py`, overrides, region tz table, samples + tests; first run → `bot/data-<n>` | Architect | — | 2 d |
| ARCH-303 | Engine: catalogue adapters, `russia_v1` world, `HybridRouting` + detour/speed calibration, synthetic services, `geo_search`/`geo_nearest`, invariants on `russia_v1` | Architect | 302 (sample catalogue first, real data when merged) | 2.5 d |
| ARCH-304 | Engine: `verst_planner/city/` walking solver, presets, gates, `city_presets`/`city_route`, samples | Architect | 303 | 2 d |
| ARCH-305 | `mobile.py` API v2 (`API_VERSION = 2`) + JSON contracts `docs/contracts/v2/` + selftest | Architect | 301, 303 (first cut early on fixtures) | 1 d |
| ARCH-306 | Engine: `handoff` point selection and links + tests | Architect | 305 | 0.5 d |
| ARCH-307 | Engine: `poi_details` (photos, credits, area photo for hotels, descriptions, hours/ticket flags) | Architect | 303 | 0.5 d |
| DEV-300 | Android: INTERNET/ACCESS_NETWORK_STATE, real connectivity, OkHttp + Coil, UA, 64 MB image cache, `PhotoFrame` component, data licences screen | Developer | ARCH-300 | 1 d |
| DEV-301 | Android: location (permission flow, `LocationManager`, `geo_nearest`, reverse address online), «Куда угодно» from GPS | Developer | 300, ARCH-305 | 1 d |
| DEV-302 | Android: Navigator search over the catalogue (`geo_search`) + Nominatim address search on explicit submit, ≤ 1 req/s, attribution, offline state | Developer | 300, ARCH-305 | 1.5 d |
| DEV-303 | Android: budget fit UI: fit badge and lever lines on Waybill/Road, no-fit screen with options, `breaksBudget` on alternatives, «Подогнать под бюджет»; `CostCalculator` explicit rooms + new contract cases | Developer | ARCH-301, 305, DES-300 | 2 d |
| DEV-304 | Android: POI card and hotel area card (sheet), photo + attribution + placeholders; only sights and hotels tappable | Developer | 300, ARCH-307, DES-301 | 1.5 d |
| DEV-305 | Android: Road ahead focus restore after a card/booking/hand-off (requirement 2.1), also across process death | Developer | 304 | 0.5 d |
| DEV-306 | Android: «По городу» flow: entry, presets, custom parameters, 18+ gate, result list, «Другой вариант», share | Developer | ARCH-304, 305, DES-302 | 2.5 d |
| DEV-307 | Android: hand-off (`<queries>`, navigator → maps → web), day menu + stop menu on Road ahead, walk hand-off, device check of vias | Developer | ARCH-306, DES-305 | 1 d |
| DEV-308 | Android: saved trips schema 2 (`kind: trip \| walk`, `budgetFit`), migration from schema 1 | Developer | 303, 306 | 0.5 d |
| DEV-309 | Android: e2e journeys S3-1…S3-6 (below), timings/budgets, APK size | Developer | 301…308 | 1 d |
| DEV-310 | Android: visual-QA fix round (timeboxed 1.5 d) | Developer | DES-306 | 1.5 d |
| DES-300 | Budget: fit badge, lever lines, no-fit screen, `breaksBudget` mark, copy | Designer | ARCH-300 | 1 d |
| DES-301 | Cards: POI card, hotel card («Фото района»), photo frame 3:2, 7 placeholder illustrations, attribution line, bar card with ODbL line | Designer | ARCH-300 | 1.5 d |
| DES-302 | «По городу»: entry on the Windshield, presets, custom parameters, 18+ dialog, responsible line, walk result, empty states (`NOT_ENOUGH_POIS`, `NO_CITY`) | Designer | ARCH-300 | 2 d |
| DES-303 | Location: rationale, denied, approximate vs precise, «ищем вас…», outside Russia | Designer | ARCH-300 | 0.5 d |
| DES-304 | Address search: offline/online states, «Найти адрес», OSM attribution, «расстояния приблизительные» line | Designer | ARCH-300 | 0.5 d |
| DES-305 | Hand-off: day menu, stop menu, walk button, truncated note; `handoff_*` copy keys (the only brand-bearing keys) | Designer | ARCH-300 | 0.5 d |
| DES-306 | Visual QA on CI screenshots + e2e screens | Designer | DEV-303…308 | 1.5 d |

---

## Architect (engine) tasks

### ARCH-301 — Budget fitter (ADR-0011)

**Description.**

- `pipeline/budget_fit.py`: `FitKnobs`, the ladder S0…S5, the tolerance, the outcome, the options search (≤ 8 extra plans).
- Knob plumbing into stages 5, 8 and 9 and `split_days` (all default off).
- Explicit `rooms` in `NightUnit`/`HotelPrice` and in `recompute` + codec, plus contract cases for explicit rooms.
- The fixture extension: `rr_golden_ring_short` (a hidden variant, `parentId`) and `familyPriceRub` where it matters.
- `breaksBudget` on alternatives.
- `Planner.plan` returns `TripPlan | NoFit`; `mobile` envelopes `outcome`.

**Acceptance.**

- `test_budget_fit`:
  - CEO case (Золотое кольцо, 4 adults + 1 child + dog, budget 30 000, golden clock): `total ≤ 31 500` with `budgetFit.status ∈ {fits, small_overrun}`, **or** `outcome = no_fit` with ≥ 2 options, each re-planned and fitting;
  - the same with budget 60 000: unchanged from S0 (no `budgetFit` key);
  - budget null: never fitted;
  - lever order and savings are monotonic;
  - determinism;
  - cancellation between steps.
- G01–G12 byte-identical. The new golden G13 is the CEO case.
- `cost_recompute_cases.json`: all old cases unchanged, ≥ 6 new rooms cases; DEV-112 bundles regenerated (additive fields only).
- Coverage ≥ 95 %.

### ARCH-302 — Open-data pipeline (ADR-0012 §1–3)

**Description.**

- `.github/workflows/data.yml`, triggered by `workflow_dispatch` or a push to `data-request`, writing `bot/data-<n>`.
- `tools/data/{fetch_wikidata.py, fetch_overpass.py, fetch_commons_meta.py, build_catalogue.py, inflect.py, name_overrides.tsv, region_tz.tsv}`.
- Recorded samples in `tests/data/samples/`.
- `catalogue.lock`.

**Acceptance.**

- In the sandbox:
  - `build_catalogue` on the samples gives a byte-identical output on re-run;
  - the deny-list filter, the caps, the columnar writer/reader round trip and the size test pass;
  - `inflect` with a stub morphology reproduces the 48 fixture forms through the override path.
- On Actions:
  - the run is green and `bot/data-<n>` has towns ≥ 1 000, POIs ≥ 10 000, bars ≥ 2 000, gzip ≤ 2.5 MB;
  - the lock lists the counts, the sources and the pymorphy3 version;
  - `test_inflect` 48/48 against the fixture forms.

### ARCH-303 — Catalogue world `russia_v1` (ADR-0012 §4–5)

**Description.**

- `adapters/catalogue/` (places, geocoding, region locator, prices, `HybridRouting`, synthetic services) and `tools/calibrate_detour.py` → `resources/detour_model.json`.
- `mobile.load_catalogue` at boot, plus `geo_search` and `geo_nearest`.
- `places_near` on both repositories.

**Acceptance.**

- `russia_v1` plans:
  - Москва → Пермь, Москва → Санкт-Петербург, Ярославль → Казань and an address point in Екатеринбург → Тюмень all plan;
  - invariants: no deny-listed names, every hotel is fictional and marked, stops within the corridor, synthetic routes flagged `route.synthetic`;
  - a Москва → Ярославль plan on `russia_v1` routes on the fixture graph (same km as `central_russia_v1`).
- Search:
  - `geo_search("Санкт")` → Санкт-Петербург first;
  - «Ниж» → Нижний Новгород before Нижнекамск by population;
  - `geo_nearest` at Ярославль station → Ярославль;
  - at 0, 0 → `insideRussia: false`.
- Catalogue load ≤ 800 ms on the emulator (`timings.json`). The detour model's error table is in ADR-0012 and in `detour_model.json`.

### ARCH-304 — Walking solver and presets (ADR-0013)

**Acceptance.**

- The unit tests listed in ADR-0013 "Tests";
- the brute-force quality check: ≥ 0.9 × optimum in ≥ 95 % of 200 seeds;
- a full solve < 50 ms on the desktop for 60 candidates;
- samples `docs/contracts/city/{yar_overview, yar_custom_parks_4h, spb_museums_6h, yar_ryumochnye}.json`.

### ARCH-305 — `mobile.py` API v2 and contracts (M§5.4)

**Acceptance.**

- Every function in M§5.4 is implemented, never raises, and the `selftest` covers them.
- `docs/contracts/v2/*.json` has one request/response example per function and outcome, generated by `tools/gen_mobile_contracts.py --v2`, byte-identical on re-run.
- `API_VERSION = 2`. The v1 calls keep their shapes (additive fields only).

### ARCH-306 — Hand-off (ADR-0014)

**Acceptance.** `test_handoff`:

- the car day with > 8 candidates → 8 vias, ordered, `truncated = true`;
- fuel and rest are excluded;
- `fromStopId` and `fromHere`;
- a walk with 13 points → 2 parts sharing the boundary point;
- exact link strings for G02 day 2 (contract file).

### ARCH-307 — POI details

**Acceptance.**

- `poi_details` for:
  - a catalogue POI: name, description, `image.card`/`image.thumb`/`image.page` URLs, credits;
  - a fixture sight: the image via `fixture_links`;
  - a synthetic hotel: `areaImage`, `areaLabelRu` «Фото района: …», `isFictional: true`;
  - a bar: `osmAttribution`;
  - fuel/rest: `NOT_FOUND`, which is not tappable anyway.
- Contract files.

---

## Developer (Android) tasks

### DEV-300 — Network, images, permissions

**Description.**

- Manifest: `INTERNET`, `ACCESS_NETWORK_STATE`.
- `NetworkConnectivity` (`ConnectivityManager` callback) replaces `SimulatedConnectivity`; the debug override is kept.
- OkHttp 4.12.0 with an interceptor setting `User-Agent: Verst/0.3 (Android; +https://github.com/pazzia/Verst)`.
- Coil 2.7.0 `ImageLoader` with a 64 MB disk cache in `cacheDir/images`.
- `PhotoFrame(url, kind, credit)`: 3:2, Crop, placeholder per kind, and an error/offline placeholder that never changes the frame size.
- «О данных» screen (Wikidata CC0, OSM ODbL, Commons per-file licences, «расстояния приблизительные»), reached from the debug/settings entry.

**Acceptance.**

- A Robolectric screenshot of `PhotoFrame` in the states loading, loaded (fake image), error and offline.
- `NetworkConnectivityTest` (shadowed callbacks).
- Merged manifest dump in CI shows exactly the 4 permissions from ADR-0012 §7 (location from DEV-301), and no `usesCleartextTraffic`.
- APK size in `apk.json`.

### DEV-301 — Location

**Description.**

- Coarse permission request with the DES-303 rationale; «Точнее» → fine.
- `LocationManager.getCurrentLocation` (API 30+) / `requestSingleUpdate` fallback, with a 10 s timeout.
- `geo_nearest` gives the origin town.
- When online, Nominatim reverse gives the address label (≤ 1/s shared bucket, DEV-302).
- Denied or timeout → the origin stays the last one (or Москва) with the plate from DES-303. Outside Russia → the DES-303 state.
- «Куда угодно» on the Windshield uses it.

**Acceptance.**

- Robolectric with `ShadowLocationManager`:
  - Ярославль coordinates → origin «Ярославль», label from a fake Nominatim (MockWebServer);
  - denied → the plate;
  - outside Russia → the state.
- e2e: emulator `geo fix` to Ярославль → Windshield «ВЫ: Ярославль».

### DEV-302 — Search: catalogue + addresses

**Description.**

- Typeahead from `geo_search` (offline) for towns and POIs, with name forms.
- «Найти адрес» (IME search action or button) → Nominatim `/search` (`countrycodes=ru`, `accept-language=ru`, `limit=5`), never per keystroke (ADR-0012 §5: policy).
- Rate limit: a token bucket of 1/s, plus a 24 h in-memory cache.
- «© OpenStreetMap» under the address results.
- Offline: the hint row from DES-304.

**Acceptance.** Robolectric + MockWebServer:

- typing «Санкт» issues 0 HTTP requests and shows Санкт-Петербург;
- submitting «Ярославль Советская 1» issues exactly 1 request with the UA header;
- two submits within 1 s → the second is delayed;
- offline → the hint, no request.

### DEV-303 — Budget fit UI

**Description.**

- `PlanResultDto.outcome`, `BudgetFitDto`, `NoFitDto`, `AlternativeDto.breaksBudget`.
- Waybill and Road footer show the fit badge and «Подогнали под бюджет: …» with the lever savings (DES-300).
- The no-fit screen replaces Road ahead: the minimum, the options (each opens Instruments with the option applied and re-plans), «Показать самый экономный вариант» (over-budget styling).
- Instruments shows `estimate.outcome` before ПОЕХАЛИ.
- Replace sheet marks `breaksBudget` rows.
- Waybill over-budget → «Подогнать под бюджет» (re-plan).
- `CostCalculator` explicit `rooms` + the new contract cases.

**Acceptance.**

- `CostCalculatorContractTest` passes all old cases plus the new ones.
- Screenshots: no-fit (CEO case contract), fitted Waybill, replace sheet with a flagged row.
- e2e S3-1.

### DEV-304 — POI and hotel cards

**Description.**

- On Road ahead and the walk result, only `sight` and `overnight` (hotel) rows and their road signs are tappable. Fuel and rest rows get no click semantics (requirement 2).
- A tap → `poi_details` → a bottom sheet card: `PhotoFrame`, name, kind line, description, hours/ticket notes («часы уточняйте», «цена примерная»), attribution.
- The hotel card uses the area photo with «Фото района: {город}» and the fictional-partner line.
- The bar card carries the ODbL line.

**Acceptance.**

- Robolectric: a fuel row has no `onClick` semantics; a sight row has one.
- Screenshots of the 4 card types (with fake images).
- e2e S3-2 (online emulator: the photo loads; then airplane mode: the placeholder).

### DEV-305 — Focus restore (requirement 2.1)

**Description.**

- When a card, booking (5.7 / mock partner) or hand-off opens from Road ahead (or the walk result), `VerstFlow` stores `focusStopId`.
- On return, the list scrolls so that row is visible (`bringIntoView`, the same offset as before) and TalkBack focus moves to it.
- Persisted in `last.json`, so it also survives process death.

**Acceptance.**

- `VerstFlowTest`: open the card of day 2 stop 5 → back → the scroll index is that row's.
- e2e S3-3: the same after Exit → mock partner → «Да» → back, and after `am kill`.

### DEV-306 — «По городу»

**Description.**

- Entry from the Windshield (DES-302); start = GPS (DEV-301) or a picked point.
- `city_presets` → preset chips; the custom sheet (2/4/6/8 h, interests, pace, budget, return to start).
- The 18+ dialog for alcohol presets (every time, not remembered).
- `city_route` (cancellable, shimmer).
- Result list with stop cards (DEV-304), the responsible line, «Другой вариант» (`exclude`), «Пешком в Яндекс Картах» (DEV-307), save/share.

**Acceptance.**

- Screenshots for each preset from the contract files.
- `NOT_ENOUGH_POIS` / `NO_CITY` states.
- The 18+ decline → no request.
- e2e S3-4.

### DEV-307 — Hand-off

**Description.**

- `<queries>` for `ru.yandex.yandexnavi` and `ru.yandex.yandexmaps`.
- `HandoffLauncher` tries navigator → maps → web (car) or maps → web (walk).
- Road ahead day-header menu «В навигатор: день N»; stop menu «Открыть в навигаторе отсюда».
- Walk button.
- The truncated note.
- The brand allow-list in `BrandDenyListTest` (`handoff_*` only).

**Acceptance.**

- Robolectric `ShadowPackageManager`: with the navigator installed → the navigator intent; maps only → maps; neither → browser with the exact web URL from the contract.
- On a real device, done by the Manager or the CEO with a checklist in `install-ceo.md`: the navigator opens with ≥ 2 vias. If not, the ADR-0014 fallback is recorded in dev-notes.

### DEV-308 — Saved trips schema 2

**Description.** `SavedTripDto.kind` (`trip` | `walk`), `walk` payload, `budgetFit`. Schema 1 files migrate in memory and are written back as 2 after a successful decode only (release review P1-1 rule kept). «Мои поездки» shows walks with a walking glyph.

**Acceptance.** `FileTripStoreTest` covers migration 1 → 2, an unknown schema 3 kept aside, and a walk round trip.

### DEV-309 — Journeys and budgets

**Journeys:**

| ID | Journey |
| --- | --- |
| S3-1 | CEO budget case → fitted ≤ 31 500, or the no-fit screen → the «Тула · Ясная Поляна» option → a plan that fits |
| S3-2 | Road ahead → sight card with a photo (online) → hotel card «Фото района» |
| S3-3 | Focus restore after the card and after booking, and after process death |
| S3-4 | `geo fix` Ярославль → «По городу» → Обзорный 4 h → result → «Пешком в Яндекс Картах» resolves to the web URL (no Yandex apps on the emulator) |
| S3-5 | Navigator «Пермь» (catalogue) → plan on a synthetic route with the «расстояния приблизительные» line |
| S3-6 | The address search on the online emulator against MockWebServer (no real Nominatim traffic from CI) |

**Budgets** (`budgets.json`): engine start incl. catalogue ≤ 5 000 ms; CEO-case plan incl. fitting ≤ 12 000 ms incl. Drive pacing; `city_route` ≤ 1 500 ms; APK ≤ 48 MB target.

---

## Designer tasks

DES-300 … DES-305 deliver screen specs, states and copy keys in `design/` (screens 5.8 «Не помещается в бюджет», 5.9 Card, 5.10 «По городу», 5.11 Walk result; components for `PhotoFrame`, placeholders, hand-off menu), as in Sprint 2. Copy rules:

- Brand names only in `handoff_*`.
- The responsible-drinking line is fixed copy: «Пейте умеренно, чередуйте с водой и едой. За руль — только трезвым.»
- «Фото района» is mandatory on hotel cards.

DES-306: visual QA as DES-110…116.

## Sprint 3 exit criteria (Manager checklist)

1. The CEO case fits (≤ 31 500 ₽) or shows the no-fit screen with working options.
2. Every sight and hotel opens a card with a photo or the placeholder; fuel and rest stops are not tappable; focus returns to the row.
3. GPS sets the origin; any Russian town and (online) any address can be a destination.
4. «По городу» offers the presets that the city supports; the alcohol presets ask for 18+.
5. Car → Яндекс Навигатор (or Карты/web); walk → Яндекс Карты pedestrian (or web).
6. Offline: everything except photos and addresses works.
7. `make check` green, coverage ≥ 95 %, G01–G12 unchanged, APK ≤ 60 MB (target 48), deny-list green with the hand-off allow-list.
