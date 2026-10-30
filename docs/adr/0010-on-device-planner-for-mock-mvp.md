# ADR-0010: The real planner runs on the phone (Chaquopy) for the mock MVP

Status: Accepted (Architect) · Date: 2026-10-24 · Refs: CEO decision for Sprint 2; ADR-0002, ADR-0004, ADR-0009; architecture §5.2, §7.3, §11, §16.11.4; `docs/architecture-android-mvp.md`

## Context

CEO, Sprint 2: "Everything on mocks for now. I need a fully finished solution to test on my phone — as an Android APK." There are no servers and no real maps. The app must work end to end on the phone, offline, in design v5 «За рулём», on the fixture worlds `central_russia_v1` (41 towns, 426 places, 3 ready routes from Moscow) and `edge_cases_v1`.

The phone must support:

1. Any origin → destination among the fixture towns and places: free search, up to 3 vias.
2. The ready routes near Moscow.
3. Crew, daily km, budget, mood, car settings, avoid tolls.
4. Stop replacement with alternatives.
5. Offline cost recompute. The contract is `backend/planner/tests/contract/cost_recompute_cases.json`, with the rules in A§7.3 and A§16.11.4.
6. Saved trips that work offline.
7. Share text.

Constraints:

- The sandbox cannot download dependencies. Android code is compiled only on GitHub Actions (`ubuntu-24.04`, JDK, Android SDK, internet).
- Every compile error costs one CI round-trip. We can read check-run annotations and git branches from here, but not job logs.

The engine has been tested in Sprint 1: 9 031 lines of stdlib-only Python, 273 tests, 12 golden trips. Measured in the sandbox (CPython 3.13, x86-64 desktop):

| Step | Time |
| --- | --- |
| Import | 135 ms |
| World load | 9 ms |
| Plan (golden trips) | 17–43 ms |

A private plan JSON (with `engineState`) is ≤ 146 KB.

## Options

| Criterion | (a) Chaquopy: CPython in the APK, planner unchanged | (b) Kotlin port of the planner | (c) Precomputed plans as JSON |
| --- | --- | --- | --- |
| Fidelity to the tested engine | **Identical code.** Proven on the emulator by a golden parity test: on-device JSON byte-equal to `tests/golden/snapshots/*.json` | New code, about 7–8 k lines. The 273 tests and 12 goldens must be re-implemented. Drift risk on every rule (A§16 has 12 amendment sections) | Exact for the cases that were generated, impossible for any other input |
| Requirement coverage (1–7 above) | All | All, after weeks | Fails 1 and 3. 41 towns give 1 640 ordered pairs × crew × 16 km steps × 6 budgets × 3 moods × tolls, plus vias. Only a demo matrix is possible. Replacing a stop outside the matrix is impossible |
| Effort | About 1 d (bridge + Gradle + spike); the rest is UI work that every option needs | 15–25 d, before any UI | 2–3 d for a generator and a lookup UI, plus the CEO testing a fake |
| Compile risk without local builds | Low code risk: about 250 lines of Kotlin bridge. Main risk: Gradle-plugin compatibility. It is isolated in DEV-101 and visible on day 1–2 | Very high: thousands of lines of Kotlin compiled only on CI | Low |
| APK size | +22–30 MB for 2 ABIs (runtime + stdlib + planner). Estimated total 35–45 MB, budget 60 MB | +~0.5 MB | +5–50 MB of JSON, depending on the matrix |
| Cold start | Python start + import + worlds in the background: estimated 1.0–2.5 s on a mid-range phone, +1–2 s on the first launch after install. UI is drawn from frame 1; the engine is not needed for the first frame | none | none |
| Plan latency | Estimated 0.2–0.6 s for 1 000 km (5–10× desktop). Hidden inside the Drive timeline, which is longer by design (5.4 §6) | ~0.1 s | 0 |
| Long-term value | The bridge sits behind the same `PlannerGateway` port that the HTTP client will implement. Removed with the server; nothing else is thrown away | Thrown away when the server plans (SPEC: server-side planning). Only cost/share, which (a) also builds, survive | Thrown away |
| Licence | MIT since Chaquopy 12 (2022); OFL fonts and the PSF licence for CPython | — | — |

Also considered and rejected:

- **(d) Official CPython-for-Android builds (PEP 738, CPython 3.13+) with hand-written Gradle/NDK glue.** Same runtime as (a) without a maintained plugin; more CI-only glue code.
- **(e) BeeWare Briefcase.** It generates its own app shell, and the UI must be our Compose.
- **(f) Pyodide in a WebView.** WASM start of 3–6 s, 20+ MB, a JS bridge, and a WebView in a native app.

## Decision

**(a) Chaquopy.** Gradle plugin `com.chaquo.python` **16.0.0**, Python **3.12** (matches `requires-python >= 3.12`), ABIs `arm64-v8a` (phones) and `x86_64` (CI emulator), pip package `tzdata==2025.2` (see Risks).

How it works:

- `backend/planner` is a Chaquopy Python source directory, used as is. Fixture worlds are Android assets from `backend/planner/fixtures/worlds`, passed to Python as strings.
- A new stdlib-only composition root `verst_planner/mobile.py` is the only API the app calls (JSON strings in and out, never raises). It is tested in the sandbox like `cli.py`.
- The engine acts as an **in-process mock server** behind the Kotlin port `PlannerGateway`. It plans, suggests, lists ready routes, replaces stops, patches cost and renders share text.
- Kotlin owns the UI, storage, pacing of progress events and the local cost recompute. `CostCalculator` is a port of `cost/recompute.py`, verified on the JVM against the 39 contract cases. This is the production design of A§11.4 (local patch first, then the "server" result overwrites it), so nothing is mock-only except the gateway implementation.

Hand-offs in the mock build (no partner accounts, no servers):

| Action | Mock behaviour | Why |
| --- | --- | --- |
| «в навигатор ↗», «Открыть в навигаторе отсюда» | **Real deep links**: Yandex Navigator `yandexnavi://build_route_on_map?lat_to=…&lon_to=…`, Yandex Maps `yandexmaps://maps.yandex.ru/?rtext=…~…&rtt=auto`, 2GIS `dgis://2gis.ru/routeSearch/rsType/car/to/{lon},{lat}`. The chooser lists installed apps only; with none installed, it opens `https://yandex.ru/maps/?rtext=…&rtt=auto` in the browser | Harmless: fixture coordinates are real town coordinates (places are offset by a few km). The CEO can feel the hand-off |
| «Забронировать ночь» (5.7), excursion links | **In-app mock partner sheet** (`MockPartnerSheet`): partner name, hotel, dates and price, the text «Демо: здесь откроется Яндекс Путешествия», and «Вернуться в Версту». Closing it triggers the real «Забронировали?» flow → booked state on 5.5 | The fixture hotels are fictional. A real URL would land on an empty partner search and look broken. The return flow is the part worth testing |
| Pro waitlist, «Сообщить об ошибке» | Stored locally; the success copy is unchanged | No backend |
| «Поделиться» | Android share sheet with the engine's share text (no slug link) | Real and harmless |
| «точка на карте», location | Map picker not built. The button shows the plate «Карта появится в следующей сборке — пока найдите место поиском» (DES-104). No location permission; the origin defaults to Москва and is changed through search | No real maps (CEO). A GPS fix outside the fixture worlds cannot be routed (`UNREACHABLE`) |

## Consequences

- The phone runs exactly the engine that the Manager accepted. Every golden trip is re-checked **on the emulator** in each CI run (`EngineParityTest`), so on-device behaviour is part of the build, not a hope.
- Planner changes needed for the device:
  - zip-safe resource loading (today `Path(__file__)` → `NotADirectoryError` when imported from an archive, reproduced in the sandbox);
  - a `mobile.py` bridge;
  - a `tzdata` self-check.
  All are DEV-110…112, all verifiable in the sandbox.
- The APK is 35–45 MB instead of ~12 MB. That is acceptable for a sideloaded demo, but not for the RuStore release, which talks to the server and drops Chaquopy (A§11 unchanged).
- Two cost implementations (Python reference, Kotlin port) are kept equal by the shared contract file (ADR-0009). This was already the plan of record.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Chaquopy 16.0.0 incompatible with AGP 8.11.1 / Gradle 8.14.3 | DEV-101 is the second task of the sprint. Fallback catalog B (AGP 8.7.3, compileSdk/targetSdk 35) is pre-written in `architecture-android-mvp.md` §3. A switch is one PR |
| `zoneinfo` cannot find tz data on Android: Android's tz database is not in the layout `zoneinfo` reads | pip `tzdata` (pure Python; `zoneinfo` uses it automatically, so no planner import changes and the layering test stays green). `mobile.init()` resolves `Europe/Moscow` and `Europe/Volgograd` and fails with code `TZDATA_MISSING` otherwise. Asserted on the emulator |
| `importlib.resources` not supported by Chaquopy's asset importer | DEV-110 adds a `__file__` fallback. If both fail on the emulator, flip `extractPackages("verst_planner")` (one line, documented in §6.1) |
| Cold start slower than estimated on the CEO's phone | Python starts on a background thread at process start; the UI never waits for it except on the Windshield ready routes (shimmer, 5.1 §4.3). The ready routes are cached in a file after the first success. Timings are shown in the debug panel and recorded by CI (`e2e/timings.json`) |
| Phone is 32-bit only (`armeabi-v7a`) | Not supported by this build (install fails with "no native libraries"). The CEO confirms his model before DEV-100 is accepted; adding `armeabi-v7a` costs ~+12 MB |

## Must be re-verified when CI first runs (DEV-100/101 acceptance)

- Chaquopy licence is MIT (`LICENSE.txt` in github.com/chaquo/chaquopy); 16.0.0 resolves from Maven Central; Python 3.12 runtime artifacts resolve.
- Chaquopy works with the pinned AGP; Kotlin DSL `chaquopy { defaultConfig { version = "3.12" } }` is accepted.
- The first CI run prints the effective versions into `ci-logs` (`raw-logs/toolchain.log.gz`, Gradle dependency resolution). The Architect updates the version table in `architecture-android-mvp.md` §3 with the result.

## Fallback if (a) fails in DEV-101

Trigger: DEV-101 is not green after 3 CI iterations, or the parity test shows a difference that cannot be explained.

- First, switch to catalog B.
- If that also fails: **(c)-lite**. A CI step runs `python3 -m verst_planner.mobile export-demo` and bundles plans for: the 3 ready routes; Moscow → each of the 40 other towns at daily km 300/500; crews 1/2/2+1+dog; mood default. That is (40 + 3) × 2 × 3 ≈ 260 plans: ≈ 15 MB of JSON, ≈ 2 MB compressed in the APK.
- Search is then limited to those pairs, and replacement uses each plan's pre-built `dayPatch` alternatives (already offline-exact, A§16.6).
- The UI work is unaffected, because both implement `PlannerGateway`.
