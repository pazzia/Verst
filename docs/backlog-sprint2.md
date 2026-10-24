# Verst — Sprint 2 backlog: mock MVP on the CEO's phone

Sprint: 2 (3 weeks, starts 2026-10-26) · Owner: Architect · Acceptance: Manager · Visual acceptance: Designer

**Goal.** The CEO installs one APK from a GitHub Release on his phone and uses the whole app offline on mock data: any route between fixture towns, the ready routes near Moscow, crew/km/budget/mood, replace a stop, the Waybill with offline recompute, saved trips, share. The app is in design v5 «За рулём», and the real planner runs on the device.

References:

- `docs/adr/0010-on-device-planner-for-mock-mvp.md` (ADR-0010);
- `docs/architecture-android-mvp.md`, cited as M§n;
- `docs/architecture.md`, cited as A§n;
- `design/` (screens, components, copy-ru, motion, signs, visual-qa-checklist);
- `tools/ci/`;
- `.github/workflows/android.yml`.

## Rules for every task

- **Code is compiled only on GitHub Actions.** The Developer pushes work to branch `dev/<task-id>` (e.g. `dev/DEV-103`); the `android` workflow runs on every push to `dev/**` (no release). The Manager merges to `main` after acceptance; that triggers the release `mvp-mock-<n>`. Nobody force-pushes `main`.
- **Evidence comes from the sandbox only**, with these commands:
  - `bash tools/ci/ci_status.sh <branch-or-sha> --wait` prints the run, the jobs, the failed steps, every check-run annotation, and `ci-logs` `runs/<run>-<attempt>/summary.md`;
  - `git fetch origin +ci-logs:refs/remotes/origin/ci-logs --depth=1`, then `git show origin/ci-logs:runs/<run>/…` or `git archive origin/ci-logs runs/<run> | tar -x -C /tmp/ci` for PNGs.

  "Run R" below means the run that `ci_status.sh` reports for the task's final commit.
- Android Definition of Done, in addition to each task's own criteria:
  - **Build and tests:** `ci_status.sh dev/<task>` exits 0. Jobs `build` and `e2e` are `success`; `release` and `ci-logs` are `skipped` and `success` respectively on `dev/**`. The annotation list has no `failure` entries. `summary.json` `details.build.junit.failures == 0`. `details.build.lint.Error` is absent or 0.
  - **Size:** `runs/<R>/build/apk.json` `mb ≤ 60`.
  - **Code hygiene:** `grep -rnE 'TODO|FIXME|TBD' android | grep -vE '(DEV|DES)-1[0-9]{2}'` prints nothing. No `Color(0x`/numeric `.sp`/`tween(<n>` outside `DesignTokens.kt`: `TokenLiteralsTest` is green and its allow-list is empty from DEV-120 on.
  - **Notes:** the Developer appends to `docs/dev-notes.md` (section "Sprint 2") the files touched, the run number(s), and every deviation from M§/A§ with its reason.
- Python Definition of Done is the same as Sprint 1: unittest OK, `ruff`, `mypy --strict`, no non-stdlib imports, `make coverage-planner` ≥ 85 %.
- User-visible strings come only from `strings.xml` (generated from `design/copy-ru.md`, DES-101) or from engine JSON. Missing copy is requested from the Designer, never invented.

## Order and dependencies

```
Day 1-2 (de-risk)   DEV-100 ─┬─▶ DEV-101 ─▶ DEV-102
                    DEV-110 ─┤      ▲
                    DEV-111 ─┘──────┘          DES-100 (fonts, needs Actions) ─┐
                                                DES-101, DES-102, DES-103 ─────┤
Day 3-5 (base)      DEV-112 ─▶ DEV-104 ────────────────────────────────────────┤
                    DEV-101 + DES-100..102 ─▶ DEV-103 ─▶ DEV-105 ─▶ DEV-108     │
                    DEV-101 ─▶ DEV-106 ─▶ DEV-107                              │
Day 6-13 (screens)  DEV-120 → DEV-121 → DEV-122 → DEV-123 → DEV-124 → DEV-125 → DEV-126 (in this order; each needs 103-108)
                    DES-104 before DEV-120 · DES-105, DES-106 before the first DES-11x
                    DES-110..116: one per screen, right after its DEV task is merged
Day 14-15 (finish)  DEV-127 ─▶ DEV-130 ─▶ DEV-131 (QA fixes) ─▶ CEO build
```

| ID | Title | Owner | Depends on | Estimate |
| --- | --- | --- | --- | --- |
| DEV-100 | Hello Compose APK through the whole CI → Release pipeline | Developer | — | 1 d |
| DEV-101 | Chaquopy spike: the real engine on the emulator, golden parity | Developer | 100, 110, 111 | 1 d |
| DEV-102 | Diagnostics drill (planted Kotlin error, failing test, Python exception) | Developer | 101 | 0.25 d |
| DEV-110 | Planner: zip-safe resource loading | Developer | — | 0.25 d |
| DEV-111 | Planner: `verst_planner/mobile.py` app-facing API | Developer | 110 | 1 d |
| DEV-112 | Planner: Kotlin contract exports (replace, patch) | Developer | 111 | 0.5 d |
| DEV-113 | Planner: S2-01 golden tie hygiene (carry-over, optional) | Developer | — | 0.25 d |
| DEV-103 | Project structure: 3 modules, tokens, fonts, strings, icons, theme, navigation skeleton, rule tests | Developer | 101, DES-100…102 | 1 d |
| DEV-104 | `:core-model`: DTOs, `CostCalculator`, `TripEditor`, `RuFormat`, contract tests | Developer | 100, 112 | 1.5 d |
| DEV-105 | Screenshot harness: sizes, font scale, frozen clock, golden fixtures | Developer | 103 | 0.5 d |
| DEV-106 | Engine host and `ChaquopyPlannerGateway` | Developer | 101, 104 | 1 d |
| DEV-107 | Storage, defaults, caches, connectivity, links, mock partner | Developer | 104, 106 | 0.75 d |
| DEV-108 | `:core-ui` components and `WindshieldScene` | Developer | 105 | 2 d |
| DEV-120 | 5.1 Windshield (+ D-1 «Мои поездки», full list sheet) | Developer | 106–108, DES-104 | 1 d |
| DEV-121 | 5.2 Navigator | Developer | 120 | 1 d |
| DEV-122 | 5.3 Instruments + D-4 settings sheet | Developer | 120 | 1 d |
| DEV-123 | 5.4 Drive + `DrivePacer` | Developer | 122 | 1 d |
| DEV-124 | 5.5 Road ahead + D-5, D-6, D-7, D-11, save/share, navigator hand-off | Developer | 123 | 1.5 d |
| DEV-125 | 5.6 Waybill + D-9 Pro | Developer | 124 | 1 d |
| DEV-126 | 5.7 Exit + MockPartnerSheet + D-10 | Developer | 124 | 0.75 d |
| DEV-127 | Debug panel and simulations | Developer | 120–126 | 0.5 d |
| DEV-130 | Emulator journey, budgets, CEO install notes | Developer | 127 | 1 d |
| DEV-131 | Visual-QA fix round (timeboxed) | Developer | DES-110…116 | 1.5 d |
| DES-100 | Fonts into the repo + glyph verification | Designer | Actions working | 0.25 d |
| DES-101 | `gen_strings.py`: copy deck → `strings.xml` + `plurals.xml` | Designer | — | 0.5 d |
| DES-102 | `gen_vectors.py`: icons → VectorDrawables | Designer | — | 0.25 d |
| DES-103 | Launcher icon and app label | Designer | — | 0.25 d |
| DES-104 | Mock-specific copy and specs | Designer | — | 0.5 d |
| DES-105 | Reference renders of the canvases (formerly DES-005) | Designer | DES-100 | 0.5 d |
| DES-106 | `qa_sample.py` + per-screen sample points | Designer | — | 1 d |
| DES-110…116 | Visual QA per screen on CI screenshots (5.1 … 5.7) | Designer | DEV-120…126 | 0.25–0.5 d each |
| DES-117 | On-device QA on the emulator journey and the CEO's phone | Designer | DEV-130 | 0.5 d |

Total: Developer ≈ 19.5 d, Designer ≈ 6.5 d. With one Developer the sprint is 3 weeks. **The first CEO-installable build** is the end of DEV-100 (hello screen). The first useful build is after DEV-124 (≈ day 11): plan → Road ahead.

---

## Phase 0 — de-risk the toolchain

### DEV-100 — Hello Compose APK through the whole CI → Release pipeline

**Description.** The smallest app that exercises every link of the pipeline before any feature work. No Chaquopy, no fonts, no `DesignTokens.kt`.

- Gradle project per M§2, M§3, with all 3 modules:
  - `:core-model` has one class `BuildInfo` and one JUnit test;
  - `:core-ui` has `HelloTheme` with the colour `#141416` as a local constant (allow-listed in this task only);
  - `:app` has `MainActivity` showing «Верста» (system font) and «Сборка <n> · <sha7>» on `#141416`, edge-to-edge, portrait.
- Build type `demo` and `testBuildType = "demo"` (M§3.3).
- Committed `android/app/demo.keystore`, generated with the exact `keytool` command of M§3.4.
- Gradle wrapper 8.14.3, generated offline: `cd android && gradle wrapper --gradle-version 8.14.3 --offline`.
- One Robolectric screenshot test using the `Screenshot` helper (M§0, M§11). It writes `screenshots/hello/default@390x844.png` via `View.draw` on the activity's decor view into a software `Bitmap`. If that comes out blank, use `onRoot().captureToImage()`; record which one worked.
- One instrumented test `app.verst.e2e.HelloSmokeTest`. It launches the activity, asserts the text, and writes `files/e2e/screens/01-hello.png` via `UiAutomation.takeScreenshot()` into `getExternalFilesDir(null)/e2e`.
- `planner.yml`: `runs-on: ubuntu-24.04`.
- Commit `.github/workflows/android.yml`, `fonts.yml` and `tools/ci/*` as written by the Architect (fix only what CI proves wrong; record every fix in dev-notes).

**Files.**

- `android/**`: settings, build scripts, `libs.versions.toml` Catalog A verbatim from M§3.2, wrapper, `gradle.properties`, keystore, the 3 modules;
- `.github/workflows/*.yml`;
- `tools/ci/*`.

**Acceptance.**

1. `bash tools/ci/ci_status.sh dev/DEV-100 --wait` → exit 0. All four jobs ran; `release` was skipped on `dev/**`.
2. Merge to `main` (Manager); the run on main publishes the release. Then:
   - `gh api repos/pazzia/Verst/releases --jq '.[] | select(.tag_name|test("^mvp-mock-")) | {tag_name, prerelease, assets: [.assets[] | {name, size}]}'` lists `mvp-mock-<n>` (prerelease true, assets `verst-mvp-mock-<n>.apk` > 1 000 000 bytes and `.sha256`) and `mvp-mock-latest` with `verst-mock-latest.apk`;
   - `curl -sI -H "Authorization: Bearer $(gh auth token)" https://api.github.com/repos/pazzia/Verst/releases/tags/mvp-mock-latest` → 200.
3. `git show origin/ci-logs:runs/<R>/summary.json`:
   - `"conclusion": "success"`;
   - `details.build.apk.abis == []` (no native code yet);
   - `details.e2e.instrument.passed ≥ 1`.
   `runs/<R>/e2e/am-start.txt` contains `TotalTime:`.
4. The PNG `runs/<R>/screenshots/hello/default@390x844.png` is 1170 × 2532. `python3 -c "from PIL import Image; im=Image.open('/tmp/ci/runs/<R>/screenshots/hello/default@390x844.png'); print(im.size, im.getpixel((20,1200)))"` → `(1170, 2532) (20, 20, 22, 255)` (= `#141416`). The text region is not uniform, which shows that text rendered.
5. `runs/<R>/e2e/screens/01-hello.png` exists and shows the text (the Manager opens it with the Read tool).
6. **Two consecutive releases install over each other.** The CEO installs `mvp-mock-<n>`, then `mvp-mock-<n+1>` (an empty commit to `android/` triggers it), with no uninstall prompt. The CEO confirms in chat with his phone model (arm64 check, ADR-0010).
7. `git -C /home/claude/verst ls-files android/app/demo.keystore` prints the file. `keytool -list -keystore android/app/demo.keystore -storepass verstdemo` shows alias `verst-demo`.
8. dev-notes record:
   - the effective versions from `raw-logs/toolchain.log.gz`;
   - the time of the first (cold) and second (warm) runs per job (from the jobs API `started_at`/`completed_at`).

### DEV-110 — Planner: zip-safe resource loading

**Description.** Chaquopy imports app Python code from an archive in the APK, so `Path(__file__)…open()` fails. This is reproduced in the sandbox: importing `verst_planner` from a zip raises `NotADirectoryError …/vp.zip/verst_planner/resources/planner_config.json`.

- Replace the file reads in `config.py`, `explain/ru.py` and `explain/templates.py` with one helper, `verst_planner/resources/__init__.py: read_text(name) -> str`. It uses `importlib.resources.files("verst_planner.resources").joinpath(name).read_text("utf-8")`, with a fallback to `Path(__file__).parent / name` if `files()` raises.
- `RESOURCES` (used by `cli.export-config`) keeps working.
- Stdlib only.

**Files.** `verst_planner/resources/__init__.py` (new), `config.py`, `explain/ru.py`, `explain/templates.py`, `cli.py` (if needed); `tests/unit/test_packaging.py` (new).

**Acceptance.** `cd backend/planner && python3 -m unittest tests.unit.test_packaging -v` → OK, including:

- `test_import_from_zip`: in a subprocess `python3 -I`, with `sys.path = [<tmp>/vp.zip]` built from `verst_planner/**` without `__pycache__`, `PlannerConfig.from_dict({})`, `ReasonTemplates.default()` and `ru.text("…")` work, and G02 plans with `snapshot_text(plan)` equal to `tests/golden/snapshots/G02_golden_ring.json`;
- `test_no_file_reads_outside_helper`: an AST scan shows no `open(`/`.open(`/`read_text(` under `verst_planner/` outside `resources/__init__.py`, `cli.py` and `adapters/fake/world.py` (`FakeWorld.load`).

Full DoD (all 273+ tests green, golden snapshots unchanged byte for byte, `git diff --stat backend/planner/tests/golden/snapshots` is empty).

### DEV-111 — Planner: `verst_planner/mobile.py` app-facing API

**Description.** M§5.1 completely.

- All functions take and return JSON `str`, use the envelope, and never raise.
- `SystemClock`, the golden clock, and `ISO` clocks.
- A cancel registry under a lock.
- The listener is duck-typed (`onEvent(str)`); its exceptions are swallowed after the first and logged to stderr once.
- `golden_snapshot(case_json)` reproduces `tests/golden/test_golden.snapshot_text`. It does not import `tests` (the logic is duplicated: `json.dumps(codec.plan_to_json(plan, trip_id="trp_golden"), ensure_ascii=False, indent=2) + "\n"`).
- CLI: `python3 -m verst_planner.mobile selftest [--world PATH …]`.
- `tests/test_layering.py` treats `mobile` like `cli`: a composition root that may import every subpackage.

**Files.** `verst_planner/mobile.py`; `tests/unit/test_mobile.py`; `tests/test_layering.py`.

**Acceptance.**

- `cd backend/planner && python3 -m unittest tests.unit.test_mobile -v` → OK, with at least:
  - `test_envelope_ok_and_error` (every function returns parseable JSON with `ok`);
  - `test_never_raises` (garbage input to every function → `ok:false`, code `INVALID_INPUT` or `INTERNAL`);
  - `test_load_world_both`;
  - `test_selfcheck_tz` (keys `Europe/Moscow`, `Europe/Volgograd` true);
  - `test_suggest_yaro` (first result «Ярославль», kind `city`, subtitle «город · Ярославская область»);
  - `test_popular_excludes_origin`;
  - `test_ready_routes_moscow` (3 ids in `(kmSign, sort)` order with `bearing8` set);
  - `test_ready_routes_kazan_empty`;
  - `test_plan_events_order` (first event `stage/split` 0.05; the last stage before the result is `cost`);
  - `test_plan_matches_golden_all` (for every golden case with a snapshot: `golden_snapshot(case)` == the file bytes);
  - `test_plan_errors` (G09 → `UNREACHABLE` with `pointIndex`, G10 → `TOO_SHORT`);
  - `test_cancel_from_other_thread` (a listener blocks after the first event; `cancel(id)` from another thread → `CANCELLED`);
  - `test_replace_roundtrip` (`replace_stop` on G02's first alternative == `Planner.replace_stop` result JSON);
  - `test_patch_cost_reserve_and_hotel`;
  - `test_share_text_matches_contract` (G02 == `docs/contracts/share-text/G02.json` text);
  - `test_listener_exception_swallowed`.
- `python3 -m verst_planner.mobile selftest` prints one `OK <function> <ms>` line per function per world and exits 0.
- Full Python DoD; coverage of `mobile.py` ≥ 90 % (`tools/stdlib_coverage.py`).

### DEV-101 — Chaquopy spike: the real engine on the emulator, golden parity

**Description.**

- Add the Chaquopy plugin, Python 3.12, `tzdata==2025.2`, `srcDir(backend/planner)`, the world assets and the androidTest golden assets (M§3.3).
- A minimal `EngineHost` per M§5.2: start, load worlds, selfcheck, timings.
- The hello screen shows «Движок <engineVersion> · <totalMs> мс» once ready, or the error code.
- Instrumented tests:
  - `EngineStartupTest` (status Ready within 15 s; writes `files/e2e/timings.json`);
  - `EngineParityTest` (M§5.3).
- If the plugin fails with Catalog A, apply Catalog B (M§3.1) and record it. If `importlib.resources` fails on the device, enable `extractPackages("verst_planner")` and record it.

**Acceptance.**

1. `ci_status.sh dev/DEV-101 --wait` → exit 0.
2. `runs/<R>/e2e/parity.json` lists the 10 snapshot cases, all `"equal": true`, and G09/G10 with their error codes.
3. `runs/<R>/e2e/timings.json` has `pythonStartMs`, `importMs`, `worldsMs`, `selfcheckMs`, `totalMs`. `totalMs ≤ 8000` (hard) and ≤ 4000 (target; a miss is recorded, not failed).
4. `runs/<R>/build/apk.json`: `abis == ["arm64-v8a", "x86_64"]` and `mb ≤ 60`. Its `largestEntries` are copied into dev-notes.
5. The dev-notes record:
   - the Chaquopy licence file seen (`LICENSE.txt` of the plugin jar or the GitHub repo) and the plugin, runtime and Python versions resolved;
   - the Architect then updates M§3.1 "effective versions".
6. The CEO installs the release from main and reads the engine line on his phone. Its `totalMs` is recorded in dev-notes as the first real-device number.

### DEV-102 — Diagnostics drill

**Description.** Prove that every failure class is diagnosable from the sandbox.

- On branch `ci-drill`, from DEV-101, plant:
  - (a) a Kotlin unresolved reference in `MainActivity.kt`;
  - then (b) a failing JUnit assertion;
  - then (c) `raise RuntimeError("drill")` inside `mobile.selftest` called by `EngineStartupTest`.
- Push each one separately and diagnose each.
- Delete the branch afterwards.

**Acceptance.** For each of (a), (b), (c), `ci_status.sh ci-drill` shows:

- (a) an annotation `android/app/src/main/kotlin/app/verst/MainActivity.kt:<line>` with `Unresolved reference`;
- (b) an annotation `Test failed: <Class>` with the expected/actual message;
- (c) an annotation `Runtime exception on emulator` containing `RuntimeError: drill`, and `runs/<R>/e2e/tracebacks.txt` with the Python traceback.

The three run numbers and the annotation text are in dev-notes. Any gap found becomes a fix in `tools/ci/diagnose.py` within this task.

### DEV-112 — Planner: Kotlin contract exports

**Description.** Expected outputs for the Kotlin `TripEditor`/`CostCalculator` that the JVM tests read.

- `tools/gen_mobile_contracts.py` writes `docs/contracts/replace/<case>__<stopId>__<altId>.json` for every alternative of every golden trip with a snapshot: `{"before": public trip, "stopId", "altId", "after": public trip from replace_stop}`.
- It also writes `docs/contracts/patch/<case>__<kind>.json` for reserve off, a hotel choice for each night with ≥ 2 options, and budget «не важно».
- A byte-for-byte regeneration test, as in A§16.10.

**Acceptance.**

- `cd backend/planner && python3 -m unittest tests.unit.test_mobile_contracts -v` → OK (the regenerated output equals the committed files).
- `ls docs/contracts/replace | wc -l` ≥ 40.
- `ls docs/contracts/patch | wc -l` ≥ 12.

### DEV-113 — S2-01 golden tie hygiene (optional, carry-over A§16.12)

As specified in A§16.12 S2-01. It has no Android impact. Do it only if Phase 0 is done early.

---

## Phase 1 — foundations

### DEV-103 — Project structure, design assets, theme, navigation skeleton, rule tests

**Description.**

- Modules and packages per M§4.
- `DesignTokens.kt` copied verbatim, with `tools/sync_design.sh` and `DesignTokensInSyncTest`.
- Fonts from DES-100, strings from DES-101, vectors from DES-102, launcher icon from DES-103.
- `VerstTheme` (CompositionLocals; no Material).
- `AppContainer`.
- `VerstNavHost` with the 7 routes plus `DebugRoute` (M§7). Each screen is a placeholder `XScreen` showing its title from strings and a back link; system back equals the back link.
- `PackageRulesTest` and `TokenLiteralsTest` (M§4); the allow-list holds only the placeholder screens.
- `robolectric.properties` (`sdk=35`).

**Acceptance.**

- `ci_status.sh dev/DEV-103` → exit 0.
- `runs/<R>/build/summary.json`: `junit.tests` includes `DesignTokensInSyncTest`, `PackageRulesTest`, `TokenLiteralsTest`, `NavigationBackTest`. The last one is a Robolectric test that walks Windshield → Navigator → Instruments → Drive → Road → Waybill → back ×5 and asserts each route, using the system back.
- `NegativeRulesTest` proves the scanners detect a planted violation: it scans an in-memory fixture, not the repo.
- `git diff --no-index design/DesignTokens.kt android/core-ui/src/main/kotlin/app/verst/core/ui/theme/DesignTokens.kt` prints nothing.
- The emulator screenshot `e2e/screens/01-*.png` shows the placeholder Windshield title in IBM Plex Sans Condensed. The Designer confirms the face (G-03).

### DEV-104 — `:core-model`: DTOs, CostCalculator, TripEditor, RuFormat

**Description.** M§4 `:core-model` row.

- `CostCalculator.recompute(units, crew, reserveOn, budgetRub, overrides)` is a line-by-line port of `cost/recompute.py` including A§16.11.4 rules 1–5. It uses `java.math.BigDecimal` with `RoundingMode.HALF_UP`, never `Double`, for money.
- `TripEditor.applyAlternative` (dayPatch verbatim, A§16.6) and `withHotel`.
- `RuFormat`: U+202F thousands separator, U+00A0 before `₽`/`км`, decimal comma, and plural rules matching `explain/ru.py`.
- JSON: `Json { ignoreUnknownKeys = true; explicitNulls = false; encodeDefaults = true }`.

**Acceptance.**

- `ci_status.sh dev/DEV-104` → exit 0, with `runs/<R>/build/summary.json` showing these tests green:
  - `CostCalculatorContractTest`: 39 cases, each a separate test name `case_<name>`, so failures annotate per case;
  - `CostCalculatorPerfTest`: 10 000 recomputes of the G06 units, median < 5 ms each;
  - `DtoContractTest`: all snapshots + `plan-response.example.json`;
  - `TripEditorReplaceContractTest`: every `docs/contracts/replace/*.json`. `after` equals `applyAlternative(before)` on every stop's `arriveAt`, `departAt`, `kmFromPrev`, `seq` and `id`, and equals `CostCalculator` on `cost.totalRub` and the 6 lines;
  - `PatchContractTest`: every `docs/contracts/patch/*.json`;
  - `RuFormatTest`: `34500` → «34 500 ₽» with U+202F/U+00A0; `plural(1,2,5,21,111)` for день/дня/дней.
- `CostCalculator.kt` has no `Double` arithmetic on money: `grep -n "toDouble\|Double" …/cost/CostCalculator.kt` prints only lines in the `fuel km` path, which is a float in the units by contract.

### DEV-105 — Screenshot harness

**Description.**

- `app.verst.testing.Screenshot` (shared by `:core-ui` and `:app` tests through a `testFixtures`-free copy in each, or a small `:core-ui` test-jar; record the choice).
- It captures at density 3.0 for sizes `390x844` (default), `360x640` and `480x900`, and with font scale 1.3 (`-fs130`). The path is `$verst.screenshots.dir/<screen>/<state>@<w>x<h>[-fs130].png`.
- `FixedSceneClock(ms)` comes through `LocalSceneClock`.
- `GoldenFixtures` loads the golden snapshots into `TripDto`.
- A reduced-motion switch for tests.

**Acceptance.**

- `runs/<R>/screenshots/theme/` contains `palette@390x844.png`: swatches of every `DesignTokens.color` leaf, in token order, labelled.
- DES-106 `qa_sample.py` checks every swatch centre against `tokens.json` with 0 difference: `python3 design/tools/qa_sample.py /tmp/ci/runs/<R>/screenshots theme` → `PASS theme 0 failures`.

### DEV-106 — Engine host and `ChaquopyPlannerGateway`

**Description.**

- M§5.2 completely: `EngineHost` status flow, `PythonThread`, `ChaquopyPlannerGateway`.
- Every method of `PlannerGateway`, the event decoding to `PlanStreamEvent`, cancel on `awaitClose`, `EngineResult` errors mapped from the envelope, and the `VerstEngine` logs.
- Debug knobs `debug_world`, `debug_clock`, `debug_slow_plan_s`, `debug_force_error` are read from `DefaultsRepository`. The defaults implementation may be in-memory until DEV-107.

**Acceptance.** `ci_status.sh dev/DEV-106` → exit 0, with the emulator tests `GatewayTest` green:

- `plan` G02 emits ≥ 5 `Stage` and ≥ 10 `Stop` events, then `Done` with 3 days;
- `cancel` during `plan` (collector cancelled after the first event) → no `Done`, and the engine returns `CANCELLED`, visible in logcat `VerstEngine`;
- `suggest("Яро")` first is «Ярославль»;
- `readyRoutes(Москва)` returns 3;
- `replaceStop` on G02 changes the stop id's `placeId`;
- `patchCost(reserveOn=false)` lowers the total by the reserve line;
- calling `plan` twice concurrently serializes (both complete);
- no Python call on the main thread: StrictMode `detectCustomSlowCalls` plus a `check(Looper.myLooper() != Looper.getMainLooper())` in `PythonThread`, and the test asserts no violation.

### DEV-107 — Storage, defaults, caches, connectivity, links, mock partner

**Description.**

- M§6: `FileTripStore` (`AtomicFile`, last slot, saved ≤ 50, warn at 45, schema 1, unknown schema skipped), `DataStoreDefaults` (M§6.2 keys and defaults from A§11.6), `ReadyRouteCache`, `RecentSearchStore`.
- `SimulatedConnectivity`.
- `AndroidLinkLauncher`: navigator intents per ADR-0010, with `<queries>` for the 3 packages and a browser fallback; URLs built by a pure `NavigatorLinks` in `:core-model`, unit-tested.
- `MockPartner` (data for the sheet).

**Acceptance.** Robolectric tests:

- `FileTripStoreTest`: round trip; atomic write survives a simulated crash (temp file left behind → old content still readable); the 51st save is refused with `LimitReached`; warning from 45.
- `DefaultsTest`: values persist across a new DataStore instance (I-19).
- `NavigatorLinksTest`: exact URL strings for Yandex Navigator, Yandex Maps, 2GIS and the web fallback, with Moscow → Ярославль coordinates.
- `RecentSearchStoreTest`: ≤ 10, dedup.

### DEV-108 — `:core-ui` components and `WindshieldScene`

**Description.**

- Every component of components.md §1–16 as stateless composables taking tokens only.
- `RoadSignPainter` shared by `RoadSign` and the flying signs (A§11.9).
- `WindshieldScene` + `SceneSpec` per screen (5.1, 5.2 strip, 5.3 strip, 5.4, 5.5 strip, 5.7 night).
- `RoadProjection` (components §9.1).
- `rememberSceneClock` and the running rules (motion.md §4–5).
- `rememberReducedMotion` (ANIMATOR_DURATION_SCALE, power save).
- Focus ring (G-08) and pressed states (G-02).

**Acceptance.**

- `RoadProjectionTest`: the W-03 check points within ±0.01 dp, and the N-01/D-02/E-02 half-widths.
- `SceneNoRecompositionTest`: 60 frames of the clock advance cause 0 recompositions of the scene composable (recomposition counter), and the draw lambda runs 60 times.
- `ComponentSemanticsTest`: every interactive component has a touch target ≥ 44 × 44 dp (G-09).
- Component screenshots `screenshots/components/<name>/<state>@390x844.png` cover:
  - RoadSign: all variants of components §2.1 and signs.md §2;
  - OverheadSign: list and title;
  - Mirror: small with 1 adult, with 2 adults + 1 child + dog, and with 4 adults; large;
  - SeatButton: 3 states;
  - DogToggle: on and off;
  - Odometer: 300 and 900;
  - FuelGauge: i = 0…5;
  - StartButton: S, M, L, disabled;
  - NaviPanel, WaybillSheet, Stamp, ExitSign, HotelOption: selected and unselected;
  - Chips, BackLink, CTAs, BottomSheet, NaviDialog, Plate, Shimmer.

  The scene screenshots `screenshots/scene/<spec>@390x844.png` are taken at clock 0 and 450 ms.
- DES-106 points for components pass.

---

## Phase 2 — screens

Common acceptance for DEV-120…126:

- (1) Every state in M§8.2 for the screen exists as a PNG in `runs/<R>/screenshots/<screen>/`, at all 3 sizes for `default` and at `-fs130`.
- (2) A Robolectric `XScreenSemanticsTest` asserts the screen's TalkBack strings from `screens/5.x §7` character for character (G-14, W-31/N-19/I-20/D-14/R-18/P-16/E-10) and touch targets ≥ 44 dp.
- (3) The reducer/ViewModel unit tests cover every intent.
- (4) The emulator journey screenshot for the screen exists in `e2e/screens/`.
- (5) `python3 design/tools/qa_sample.py /tmp/ci/runs/<R>/screenshots <screen>` → `PASS`.
- (6) The task's Designer QA (DES-11x) is opened right after the merge.

| Task | Screen specifics (beyond the common acceptance) |
| --- | --- |
| **DEV-120** 5.1 Windshield | Ready routes from `gateway.readyRoutes(origin)`. Shimmer until `EngineStatus.Ready`, never shown for < 300 ms; the cached list is shown at once (W-22). Row selection, 200 ms cross-fade (W-13). Arrow from `bearing8` (W-15). Mirror crew from defaults (W-09). «ВЫ: <origin>» → Navigator(focus FROM) (W-18). «Мои поездки» plate and D-1 sheet only with ≥ 1 saved trip (W-27). Full list sheet (W-29). States `no-routes` (origin Казань), `engine-failed`. Test: `WindshieldViewModelTest.originKazanShowsNoRoutes` |
| **DEV-121** 5.2 Navigator | `suggest` with debounce 250 ms, `distinctUntilChanged`, `mapLatest`; skeleton after 250 ms; ≤ 6 rows (N-09). Badges Г/М (towns/places; no streets in the fixtures). «НЕДАВНО» from `RecentSearchStore`, «ЧАСТО ИЩУТ» from `popular` when empty (OI-04). Vias insert/reorder/remove, max 3 (N-17), including TalkBack actions. Validation: `TOO_SHORT`/`UNREACHABLE` are only known after planning; the screen shows N-15 copy when Drive returns those codes and the user comes back (`PlanSession.lastError`). «точка на карте» → plate (DES-104). GPS indicator per DES-104. Test: `NavigatorViewModelTest.debounceCancelsStale` |
| **DEV-122** 5.3 Instruments + D-4 | Seat cycle, limits ≤ 8 people incl. third row (I-05, I-17, OI-07); odometer 150–900 step 50 with the roll only on changed drums (I-10); budget presets and «не важно»; gauge spring (I-13); mood chips with no default chip for adults-only (OI-08); D-4 settings sheet (consumption, fuel type, tank, start time, avoid tolls); defaults persisted (I-19). Estimates «≈ X ч Y мин» and days per A§11.11. The settings sheet footer shows the build line; a 2 s long-press opens `DebugRoute`. ПОЕХАЛИ → `PlanSession.start(request)` → Drive |
| **DEV-123** 5.4 Drive | `DrivePacer` (M§8.3) as a pure function with unit tests: step spacing ≥ 400 ms, bar monotone, ≤ 3 signs in flight, ≥ 1 200 ms spacing, CTA only after the last step, auto-advance 1 000 ms off under TalkBack. Error mapping per M§9 and 5.4 §4.4. Slow state at 20 s, using `debug_slow_plan_s` in tests. «Упростить маршрут» re-plans with `simplify = true`. Back cancels the plan (D-13; the test asserts the engine got `cancel`). Done → Road with `popUpTo(Drive, inclusive)`; the trip is saved to the last slot |
| **DEV-124** 5.5 Road ahead + D-5/D-6/D-7/D-11 | `LazyColumn` keyed by stop id; road column continuous while scrolling (R-05); car marker (R-06); row heights per 5.5 §2.3 (R-08); signs per kind (R-09…R-11); notes, cost (R-12); «заменить» → D-6 sheet listing `alternatives` with Δ min / Δ ₽ and `alternativesNote` when < 2. Pick → `TripEditor` + `CostCalculator` immediately, then `gateway.replaceStop` overwrites (M§6.3). Long-press menu D-5: navigator from here (installed apps only), Заменить, Сообщить об ошибке (D-7, local). «в навигатор ↗» per day. Save (limits 45/50, toasts) and share (Android share sheet with the engine share text). Footer total with the over-budget colour (R-14, R-16). `NO_LODGING` plate (G05 fixture). Booked row «Забронировано ✓». Test: `RoadViewModelTest.replaceAppliesLocallyThenEngine` (local total == engine total for G02's first alternative) |
| **DEV-125** 5.6 Waybill + D-9 | The sheet with Marck Script values, printed labels (P-05, P-07); 6 lines with formulas from engine JSON; expand one line at a time (P-09); reserve toggle → `CostCalculator` ≤ 100 ms (P-08), then `patchCost`; the «—» states; over budget + hints (P-10); stamp once per trip (P-11, `local.stampShown`); entry animation (P-12); Pro plate and sheet with local join (P-13, D-9). The `reference` screenshot uses `WaybillUiState.reference()` and must show exactly 3 720 / 0 / 12 000 / 9 000 / 3 000 / 2 770 / ≈ 30 500 / ≈ 9 500 (P-15) |
| **DEV-126** 5.7 Exit + D-10 | Night scene, turn signal and exit-sign entry (E-01…E-05); hotel options from `hotelOptions`, select → local recompute + `patchCost {hotelChoice}`; «Забронировать ночь» → `MockPartnerSheet` (DES-104 spec); on its dismissal the «Забронировали?» `NaviDialog` → `local.bookedStops`, booked state on 5.7 and 5.5. Offline variant through `SimulatedConnectivity` (E-08) |

### DEV-127 — Debug panel and simulations

**Description.**

- `feature.debug` per M§9: world switch (re-plans nothing; origin reset to the world's largest town); clock system/golden; offline; slow plan; force error; engine timings; parity mismatch counter; «Сбросить данные» (deletes trips and DataStore after a confirm).
- Plain styled list using `VerstTheme` text styles; not part of visual QA.

**Acceptance.** `DebugPanelTest` (Robolectric):

- switching to `edge_cases_v1` makes `suggest("Глух")` return «Глухово»;
- planning Тестовск → Глухово shows the `UNREACHABLE` Drive error (screenshot `screenshots/5.4-drive/error-unreachable-real@390x844.png` from the real flow with a fake gateway replaying the engine envelope);
- offline toggling switches the 5.1 header to «НЕТ СЕТИ».

---

## Phase 3 — finish

### DEV-130 — Emulator journey, budgets, CEO install notes

**Description.**

- `MockJourneyTest` exactly as in M§11 (11 steps, each with a screenshot `e2e/screens/NN-<name>.png`).
- Budgets enforced in CI (M§13): APK, cold start (parse `am-start.txt` `TotalTime` in `run_e2e.sh` → fail > 3 000 ms), engine ready (`timings.json` > 8 000 ms → fail), parity mismatches 0.
- Russian release notes list what works and how to reach the edge world.
- README section "Демо-сборка на телефоне" (English heading, Russian steps for the CEO).

**Acceptance.**

- On main: `ci_status.sh main --wait` → exit 0.
- `runs/<R>/e2e/instrument.txt` contains `OK (` with ≥ 14 tests.
- `runs/<R>/e2e/screens/` has ≥ 11 journey PNGs.
- `runs/<R>/summary.json` `details.e2e` shows `instrument.failed == 0`.
- `timings.json` and `am-start.txt` are within the hard limits.
- `gh api repos/pazzia/Verst/releases/tags/mvp-mock-latest --jq '.assets[].name'` → `verst-mock-latest.apk`.
- The CEO runs the same 11 steps on his phone from the release notes and replies "работает" or a list of failures. Failures become DEV-131 items.

### DEV-131 — Visual-QA fix round (timeboxed 1.5 d)

**Description.** Fix every DES-110…117 failure in priority order: copy (G-14) → colour (exact hex) → geometry (±4 dp, ±1 dp road/signs) → motion. Anything not fixed within the timebox is listed in dev-notes with the Designer's consent and goes to Sprint 3.

**Acceptance.** For each screen, the Designer's sign-off row in `design/visual-qa-checklist.md` §9 reads `Pass` with the build number, or `Pass with deferrals` with the deferred item ids accepted by the Manager.

---

## Designer tasks

### DES-100 — Fonts into the repo + glyph verification

**Description.**

- Trigger `.github/workflows/fonts.yml` with `git push origin HEAD:fonts-request` from the sandbox, or ask the CEO to press "Run workflow".
- The workflow pushes `bot/fonts-<n>`.
- Verify the result in the sandbox with fontTools (available locally), then hand it to the Manager to merge.

**Acceptance.**

- `git fetch origin bot/fonts-<n>`.
- `git show FETCH_HEAD:android/fonts.lock` lists 6 files, each with `missingGlyphs: []`.
- For each file `f`, `git show FETCH_HEAD:android/core-ui/src/main/res/font/$f.ttf | sha256sum` equals the lock.
- `python3 -c "from fontTools.ttLib import TTFont; …"` prints `usWeightClass` 400/500/600/700/600/400 for the six files in M§10.2 order. A variable-font instancing note (if any) is recorded in `design/decisions.md`.
- 3 OFL texts exist under `android/core-ui/src/main/assets/licenses/`.

### DES-101 — `design/tools/gen_strings.py`

**Description.** Parse every `| \`key\` | text |` table row of `design/copy-ru.md` §1–10 and §9 plurals. Write `android/core-ui/src/main/res/values/strings.xml` and `plurals.xml`:

- `{name}` → positional `%n$s`/`%n$d` in order of appearance (the deck states the order);
- XML escape and Android escape `'` → `\'`, `"` → `\"`, `@`/`?` at the start;
- keep U+202F, U+00A0, «», ё literally;
- `[plural: key]` references are kept as comments.

Engine keys (§11, §12) are skipped. Plural keys in §9 have exactly 4 ICU quantities.

**Acceptance.**

- `python3 design/tools/gen_strings.py --check` exits 0 when the outputs are current, and 1 with a diff otherwise.
- `python3 -c "import xml.dom.minidom as m; m.parse('android/core-ui/src/main/res/values/strings.xml'); m.parse('android/core-ui/src/main/res/values/plurals.xml')"` passes.
- The key count equals the deck count printed by the script (≈ 450).
- No key is duplicated.
- `grep -c 'U+' strings.xml` is 0 (real characters, not escapes).

### DES-102 — `design/tools/gen_vectors.py`

**Description.** Convert `design/icons/*.svg` into `android/core-ui/src/main/res/drawable/ic_<name>.xml`: `android:width/height="24dp"`, `viewportWidth/Height="24"`, one `<path android:fillColor="#FF141416" android:pathData="…"/>`, nonZero.

**Acceptance.**

- `--check` mode as in DES-101.
- 21 files, all well-formed XML.
- Each `pathData` equals the SVG `d` attribute after whitespace normalisation (the script asserts it).

### DES-103 — Launcher icon and app label

**Description.**

- An adaptive icon as vector XML (`mipmap-anydpi-v26/ic_launcher.xml` + `drawable/ic_launcher_foreground.xml` + background colour token), designed from the overhead-sign motif.
- App label «Верста». The demo build shows no «демо» in the label (the build line carries it; decided by Designer).
- Monochrome layer for themed icons.

**Acceptance.**

- The XML files are well-formed.
- Foreground fits the 66 dp safe zone: the script `design/tools/check_icon.py` computes the path bounds ≤ 66/108 of the viewport.
- A Robolectric render of the icon `screenshots/icon/launcher@390x844.png` (DEV-103 adds the test) is reviewed and signed in `design/decisions.md`.

### DES-104 — Mock-specific copy and specs

**Description.** Add to `design/copy-ru.md` (new §14 "Mock build", keys prefixed `mock_`/`engine_`), and to `design/open-issues.md` as D-13…D-16, specs using existing components only:

- D-13 `MockPartnerSheet`: title, partner line «Яндекс Путешествия · демо», hotel, dates, nights, price, the demo note, button «Вернуться в Версту»;
- D-14 map-unavailable plate for «точка на карте»;
- D-15 engine starting/failed states on 5.1: the failed plate copy and the retry;
- D-16 the build line in D-4 and the GPS indicator decision for the mock build. Recommended: hidden, since location is not used.

Also the toast `common_engine_error`, and the share text note («без ссылки в демо-сборке»: decide whether the share text gets a line or not).

**Acceptance.**

- Every key referenced in M§9 and in DEV-120…127 exists in `copy-ru.md`.
- `gen_strings.py --check` passes after regeneration.
- The Manager reads D-13…D-16 and records the decision in `design/decisions.md` "Round 3".

### DES-105 — Reference renders of the canvases (formerly DES-005, now unblocked)

**Description.** The sandbox has Playwright + Chromium (`/opt/pw-browsers`) and PIL. `design/tools/render_refs.py` opens each `docs/design-canvas/*.dc.html` and `design/states/*.dc.html` at 390 × 844 viewport, device scale factor 3:

- Google Fonts requests are intercepted and served from `android/core-ui/src/main/res/font/*.ttf` (after DES-100) with matching `@font-face` rules;
- animations are frozen at t = 0;
- each screen frame is cropped to `design/reference/<screen>/<state>@390x844.png`.

**Acceptance.**

- `python3 design/tools/render_refs.py --check` re-renders and compares with the committed PNGs: ≤ 0.1 % differing pixels per file.
- One PNG per canvas screen and per state file (7 + 13).

### DES-106 — `design/tools/qa_sample.py` + `design/qa/<screen>.json`

**Description.**

- A stdlib + PIL tool. For a run's screenshot folder and a screen, it loads `design/qa/<screen>.json` and evaluates each point:
  - **colour:** `{"item": "W-01", "state": "default", "size": "390x844", "x": 195, "y": 55, "hex": "#2B2850"}` — dp coordinates × 3, at least 2 px inside an edge, exact match, or ±1 per channel for alpha tokens;
  - **edge:** `{"item": "W-03", "kind": "edge", "y": 540, "expect_x": [80, 310], "tol_dp": 1}` — scans for the asphalt colour transition;
  - **region-nonuniform:** text present.
- It prints `PASS <screen> 0 failures`, or one line per failure in the checklist's reporting format `[screen] [item id] expected / actual / screenshot`, and exits 1 on failure.
- Point files are derived from the checklist §2–8 and the redlines in `design/screens/*.md`: at least 15 points per screen covering every colour item and every geometry item that is visible in a static frame. A `theme` file covers DEV-105's palette.

**Acceptance.**

- `python3 design/tools/qa_sample.py --self-test` passes. It renders a synthetic PNG with PIL with known colours/edges and checks the tool detects a 1 px shift and a 1-unit colour error.
- `design/qa/` has 8 files (theme + 7 screens).
- Every static-checkable item id of checklist §2–8 appears in at least one point; the tool prints the uncovered ids with `--coverage`, and the list must be empty or justified in the file's `notes`.

### DES-110…116 — Visual QA per screen on CI screenshots

DES-110 = 5.1 … DES-116 = 5.7, each right after the matching DEV task is merged to main.

**Method.**

1. `git fetch` ci-logs and extract the run's PNGs (rules above).
2. Run `qa_sample.py` for the screen.
3. Overlay-compare each state against `design/reference/` from DES-105 (PIL difference image, written to `design/qa/reports/<screen>-run<N>/diff-<state>.png`, not committed) for ±4 dp layout drift.
4. Read every state PNG with the Read tool against the screen file's copy and states, and the copy deck (G-14).
5. Check the items that need motion or semantics on their test evidence instead of a picture:
   - motion (W-04, W-05, D-02…D-04, R-05, E-05, P-11): clock-sequence screenshots at the frame times listed in the screen's §6, which DEV produces as `<state>-t<ms>`;
   - TalkBack and touch targets: the `XScreenSemanticsTest` result in `build/tests/failures.txt`.

**Acceptance.**

- A report `design/qa/reports/<screen>-run<N>.md` (committed) with one row per checklist item of §1 (global) and of the screen's section: `Pass` / `Fail` / `Device-only` / `N/A in mock`. Fail rows use `[screen] [item id] expected / actual / screenshot`.
- `N/A in mock` is allowed only for:
  - W-28 (location rationale);
  - N-18 (map picker);
  - D-13 network log (replaced by the engine-cancel test);
  - E-08 link spinner (no link creation).
- `Device-only` is allowed only for:
  - G-13 (Macrobenchmark, out of scope);
  - G-08 hardware keyboard on the phone;
  - R-17 scroll performance.
  These three go to DES-117.
- The sign-off row in `design/visual-qa-checklist.md` §9 is filled in.

### DES-117 — On-device QA (emulator journey + CEO phone)

**Description.**

- Review `e2e/screens/*.png` of the DEV-130 run: real engine, real fonts, real device rendering at 390 × 844 dp.
- Prepare a 10-item "what to look at" list in Russian for the CEO's phone session: motion smoothness of the scene, the sign fly-in, the stamp, the turn signal, scrolling Road ahead, font scale 130 % in system settings, the «Удалить анимации» setting.

**Acceptance.** A report `design/qa/reports/device-run<N>.md` with the G-11/G-12/G-13/R-17 observations and the CEO's answers.

---

## CEO prerequisites (blocking DEV-100 acceptance)

1. **GitHub Actions billing fixed** for `pazzia`. Private repos use billed minutes. Expected Sprint 2 usage is ≈ 25 min per full run × ~12 runs/day ≈ 300 min/day, about 6 000–8 000 min over the sprint. That exceeds the free 2 000–3 000 min/month, so set a spending limit (or budget) of at least **$60/month** for Actions. Alternatively make the repo public, which gives free minutes but exposes the code.
2. Repository settings → Actions → General:
   - "Allow all actions" (or allow `actions/*`, `gradle/actions/*`, `reactivecircus/android-emulator-runner`);
   - **Workflow permissions: "Read and write"**, needed for releases and the `ci-logs` branch.
   Branch protection, if any, must not block pushes to `ci-logs`, `dev/**`, `bot/**`, `fonts-request`.
3. Tell us the phone model (an arm64 check). On the phone:
   - log in to github.com in the browser, because the repo is private and release downloads need a session;
   - allow "Install unknown apps" for that browser.
4. No secrets are needed. The demo signing key is committed by design (ADR-0010, M§3.4); the RuStore key comes later.

## Sprint 2 exit criteria (Manager checklist)

- [ ] `mvp-mock-latest` installs on the CEO's phone over the previous build, and the CEO completed the 11 journey steps.
- [ ] Latest main run: `build`, `e2e` and `release` all `success`; `ci-logs` shows 0 extracted errors; parity 10/10 equal; budgets within hard limits.
- [ ] `CostCalculatorContractTest` 39/39, `TripEditorReplaceContractTest` ≥ 40/40.
- [ ] Planner: all tests green, `mobile.py` coverage ≥ 90 %, the layering test green, the golden snapshots unchanged.
- [ ] DES-110…117 reports exist; every checklist §9 row is `Pass` or `Pass with deferrals` accepted by the Manager.
- [ ] DEV-102 drill evidence in dev-notes (3 failure classes diagnosed from the sandbox).
- [ ] `docs/architecture-android-mvp.md` §3.1 updated with the effective versions.
