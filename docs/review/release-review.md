# Pre-release review of `main` @ `262103b` (CEO test build)

Reviewer: Architect · Date: 2026-10-24 · Scope: `android/**`, `backend/planner/verst_planner/mobile.py`,
`backend/planner/fixtures/worlds/*`, `docs/contracts/**`, `.github/workflows/android.yml` (release parts), checked
against `docs/architecture-android-mvp.md` (M§), ADR-0010, `docs/backlog-sprint2.md` (rules) and the DEV-SLICE,
DEV-SLICE-2 and DEV-SLICE-3 notes in `docs/dev-notes.md`.

Method: every P0 and P1 below was traced through the code path named in it. Nothing here was built or run: the
sandbox cannot build Android, and CI is the only build. Line numbers refer to `262103b`.

Severity:

- **P0**: must be fixed before the CEO build.
- **P1**: should be fixed before the CEO build, or shipped only with the Manager's explicit acceptance.
- **P2**: later.

## Summary

| # | Sev | Finding | Fix size |
| --- | --- | --- | --- |
| P0-1 | P0 | Real fuel brands (Лукойл, Роснефть, Газпромнефть, Татнефть, Башнефть, Нефтьмагистраль) name the 82 fictional fuel stops. They show on Drive, Road ahead and in the share text that leaves the phone. This breaks the Manager's rule "no real brand anywhere in the mock build" | fixture regeneration, ~0.5 d |
| P1-1 | P1 | Saved-trips writes are not serialized. An unreadable file is read as "no trips" and then overwritten. Either can wipe every saved trip | ~0.5 d |
| P1-2 | P1 | Process death loses the current trip and the screen stack. The unsaved last trip of M§6.1 (`last.json`) does not exist | ~1 d |
| P2-1 … P2-14 | P2 | listed below | — |

Checked and OK (details at the end): no Python on the main thread, cancellation, engine error mapping, the
`CostCalculator` algorithm against `recompute.py`, manifest/permissions/debuggable/cleartext, signing and
versioning, rotation and configuration changes.

---

## P0

### P0-1 Real brand names in the mock build (fuel stops and share text)

Where:

- `backend/planner/tools/gen_worlds.py:2885`: `FUEL_BRANDS = ["Лукойл", "Роснефть", "Газпромнефть", "Татнефть", "Башнефть", "Нефтьмагистраль"]`, used at `:2913` to name every fuel stop.
- `backend/planner/fixtures/worlds/central_russia_v1.json`: 82 places of type `fuel` named «Лукойл, М-8, 22 км» and so on.
- Rendered by:
  - `android/app/src/main/kotlin/app/verst/feature/road/RoadScreen.kt:346,362` (row and road sign);
  - `feature/drive/DriveScreen.kt:170` (flying signs);
  - the engine share text that `MainActivity.kt:78-81` sends unchanged.
- In the goldens: `docs/contracts/share-text/G02.json` («16:39 Лукойл, Р-132, 253 км»), G04, `plan-response.example.json` and `tests/golden/snapshots/G02_golden_ring.json`.

Failure scenario:

1. The CEO runs the first journey of `install-ceo.md`: Windshield → «Золотое кольцо».
2. Drive flies a «Лукойл» sign, and Road ahead day 2 lists «Лукойл, Р-132, 253 км» as a planned stop.
3. «Поделиться» sends the same line to a third party with a price total. Nothing marks it as demo data: `mock_share_note` («Посчитано в демо-сборке…», `core-ui/src/main/res/values/strings.xml:440`) exists but is never used.

These are real companies placed at invented locations. That is exactly what the rule in `design/copy-ru.md:681` ("no real brand anywhere in the mock build, Manager 2026-10-24") and OI-40 forbid. `dev-notes.md:952` says the rule holds, but the screenshot test only checks for «Яндекс».

Fix:

1. In `gen_worlds.py`, replace `FUEL_BRANDS` with neutral names, e.g. «АЗС, М-8, 22 км», or one fictional chain such as «Заправка "Верста"». Regenerate the worlds; the diff must touch only fuel names.
2. Regenerate the goldens, the DEV-112 bundles, `share-text/*`, `plan-response.example.json` and the Kotlin screenshot fixtures (`make check`).
3. In the mock build, append `mock_share_note` to the shared text in `MainActivity.share`.
4. Add a deny-list test: a Python test over both worlds plus the screenshot test over the rendered text. The list must cover the brands above, «Яндекс», «2ГИС» and «RuStore».

Trips already saved keep the old names. The CEO has none yet, so no migration is needed.

## P1

### P1-1 Saved-trips file: concurrent writers, and "unreadable" turns into "overwrite with empty"

Where:

- `android/app/src/main/kotlin/app/verst/nav/VerstFlow.kt:875-878`: `persist()` launches each write on `Dispatchers.IO`, which runs writes in parallel.
- Callers of `persist()`: `save()` at `:859-873`, the booking autosave at `:772-775`, `confirmDelete` at `:901-915`, `undoDelete` at `:917-925`. `clearSaved` at `:947-952` writes the same way.
- `android/app/src/main/kotlin/app/verst/data/TripStore.kt:28-37`: one `AtomicFile` per call.
- `core-model/.../SavedTrips.kt:44-52`: decode failure or an unknown `schema` returns `emptyList()`.
- `VerstFlow.kt:269-273`: the initial load maps any exception to an empty list as well.

Failure scenarios (each traced through `android.util.AtomicFile` on API 30+, where `startWrite` opens `saved.json.new` with truncate and `finishWrite` renames it):

1. **Interleaved bytes.** Two persists overlap, for example «Да, забронировали» on a saved trip (silent save) followed by «Вернуть» (a second save), or a delete followed by «Вернуть». Both coroutines open the same `.new` inode and write from offset 0. The first `finishWrite` renames it while the second writer is still writing into it. The second rename fails with only a log line. `saved.json` now holds mixed JSON.
2. **Wipe on the next start.** On the next launch `decode` fails and returns `[]`. The next save writes a one-trip file, and all earlier trips are gone for good.
3. **Lost update, even without interleaving.** The writes may finish out of order, so an older snapshot can land last. Example: delete, then «Вернуть»; the delete write finishes last; after a restart the trip has vanished although the UI showed it restored.
4. **Wipe from any unreadable file.** A future build that cannot read the file (new `schema`, a required field) gets `[]`, and the first save overwrites the file. M§6.1 promises "skipped and logged, no destructive migration".
5. **Save before the load finishes.** A save that runs before the initial load completes writes the in-memory list without the stored trips. This is unlikely today because a plan takes at least 2 s, but it is the same defect.
6. **Silent write failure.** `runCatching` at `:877` swallows write errors such as a full disk, while «Сохранено» is already shown.

Each overlap window is the encode and fsync time of the whole list: up to 50 trips × ≤ 146 KB, about 7 MB. The window is short, but the loss is total.

Fix:

1. One writer. Use a `Channel<List<SavedTripDto>>(CONFLATED)` consumed by one coroutine on `Dispatchers.IO.limitedParallelism(1)`, or a `Mutex` around encode + write, so the last snapshot always wins.
2. Accept no save or persist until the initial load has completed.
3. On a decode failure or unknown schema, rename the file to `saved.json.unreadable-<ts>`, log it, and keep it. Never overwrite a file you could not read.
4. Report a failed write (toast `common_storage_full_*`) instead of «Сохранено».
5. Add a Robolectric test: 20 concurrent saves, then the file decodes to the last snapshot.

### P1-2 Process death drops the trip on screen and the navigation stack

Where:

- `android/app/src/main/kotlin/app/verst/VerstApp.kt:18-24` (`VerstFlow` lives only in memory).
- `VerstFlow.kt:101` (`stack`) and `:159` (`result`).
- Nothing uses `onSaveInstanceState`, `rememberSaveable` or a file for the current trip (checked with grep).
- M§6.1 specifies `filesDir/trips/last.json`, "the one unsaved last trip slot (SPEC §13)". It is not built.

Failure scenario:

1. The CEO plans «Золотое кольцо» and is on Road ahead without saving.
2. He taps «Поделиться» and spends a minute in a messenger, or presses Home and opens the camera.
3. The process holds CPython, both worlds and Compose, so One UI is quick to kill it in the background.
4. On return the activity is recreated in a new process. He sees the Windshield with the engine shimmer, and the trip is gone. Any booking marks and replaced stops on an unsaved trip are lost too.

Configuration changes are not affected, because the state is app-scoped.

Fix:

1. After every plan, replace, cost patch or booking change, write `trips/last.json` through the single writer from P1-1. Content: `{schema, tripJson, shareText, name forms, bearing, booked, savedId}`.
2. In `MainActivity.onCreate`, when `savedInstanceState != null` and `last.json` exists, restore `result` and set the stack to `[Windshield, Road]`. Use `[Windshield, Waybill]` or `[…, Exit]` if the last route is kept in the `Bundle`.
3. Add the promised journey step M§11 step 8: HOME → `am kill app.verst.demo` → relaunch → Road ahead shows the same trip.

---

## P2

| # | Where | Scenario | Suggested fix |
| --- | --- | --- | --- |
| P2-1 | `VerstFlow.kt:672-681` (reserve), `:713-722` (hotel), `:786-790` `updateTrip` | A `patch_cost` reply always replaces `result`, even when another trip has been opened since. Example: Waybill toggle → back → back → open another saved trip before the engine answers. Then trip A's numbers show under trip B's `savedId`, and the next save or booking autosave writes them into B. The window is short (the engine answers in ~0.1–0.3 s) | Capture `tripSession` at the call and drop the reply if it changed |
| P2-2 | `SavedTrips.kt:12-32` (no `world`), `PlannerGateway.kt:55` (world defaults to central on every start), `VerstFlow.kt:230-241` | A trip saved in the edge world (debug panel) is reopened after a restart. Replace or patch then runs against `central_russia_v1` and fails with the `waybill_sync_failed` toast («Не удалось синхронизировать расчёт…») or a wrong place | Store `world` in `SavedTripDto` (M§6.1 already has it) and pass it on each call. Persist the debug world/clock, or mark them visibly as transient |
| P2-3 | `feature/debug/DebugScreen.kt:80`; `VerstFlow.kt:223-225` | The debug panel ships in the CEO build (2 s long-press). «Сбросить данные» deletes every saved trip with no confirmation. A forced error or 25 s slow plan stays on until it is switched back, so every plan "fails" | `NaviDialog` confirmation on reset. Show a small «ОТЛАДКА» plate on the Windshield while any override is active |
| P2-4 | `app/build.gradle.kts:162` | `demoImplementation(ui-test-manifest)` merges the library's `androidx.activity.ComponentActivity` declaration, which the library marks `exported="true"`, into the APK the CEO installs. It is an empty, launchable activity. Verify in the CI merged manifest | Run the Robolectric screen tests on `debug` (`testDebugUnitTest`), or remove the node in `src/demo/AndroidManifest.xml` with `tools:node="remove"` |
| P2-5 | `app/build.gradle.kts:22` | The CEO's APK carries `x86_64` native libraries for the emulator: about 12 MB of the 44 MB. Also, the `arm64-v8a` Chaquopy runtime is never executed in CI; the emulator is x86_64. The CEO's phone is the first arm64 run | Publish an arm64-only `verst-mock-latest.apk` (ABI split, or a property that drops x86_64 in the release job). Ask the CEO for the debug-panel timings line after the first launch |
| P2-6 | `core-ui/src/main/res/values/strings.xml:287-291` | `stopmenu_yandex_navi`, `stopmenu_yandex_maps`, `stopmenu_2gis`, `stopmenu_install` (RuStore) ship in the mock APK. They are unused and invisible, but anyone who unzips the APK can see them | Keep them out of the mock build until the navigator hand-off exists (P2-13), or accept them as production copy |
| P2-7 | `PlannerGateway.kt:82` → `mobile.py:340-356` | `popular` is called without `origin_id`, so the engine excludes the most populous town, not the origin. After «изменить» ОТКУДА → Ярославль, «ЧАСТО ИЩУТ» offers Ярославль (→ `TOO_SHORT`) and hides Москва | Pass the origin town id: the suggestion `id`, or add `id` to `reverse` |
| P2-8 | `mobile.py:467-468` `_input_key` | The split-km hint cache is keyed by world and input, not by clock. After a debug clock switch, Drive's «по ≈ N км» can come from the other clock's plan. With the system clock, an estimate and a plan on either side of the "next Saturday" boundary can also differ (≤ 1 occurrence per week) | Put `_CLOCK.now()` (or the resolved `startAt`) in the key, and clear `_TRIP_KM` in `set_clock` |
| P2-9 | `engine/EngineHost.kt:116-119` | `call()` blocks on `Future.get()`. Only `EngineParityTest` uses it today, but a future main-thread caller would freeze the UI (ANR) | Make it `@VisibleForTesting` and `check(Looper.myLooper() != Looper.getMainLooper())` |
| P2-10 | M§6.2 vs `app/build.gradle.kts` (no DataStore) | Crew, km/day, budget, mood and origin reset to defaults on every launch. The CEO re-enters his family each time | `DataStoreDefaults` with the M§6.2 keys |
| P2-11 | M§5.2 "parity guard" | The `VerstParity` log/count (local total vs engine total) is not built. `LocalCostBundleTest` covers the contract on the JVM, but a device-side drift would go unnoticed | Log and count when `CostApply` total ≠ engine total in `updateTrip`; show the count in the debug panel; assert 0 in e2e |
| P2-12 | backlog DoD, M§4 | `PackageRulesTest` and `TokenLiteralsTest` do not exist (grep). Numeric `.dp` literals are spread through the screens | Add both before the server-backed work; allow-list today's screens |
| P2-13 | ADR-0010 hand-off table, M§1, M§9 | Navigator deep links (`yandexnavi://`, `yandexmaps://`, `dgis://`, browser fallback) and the manifest `<queries>` are not built. ADR-0010 wanted the CEO to "feel the hand-off" | Manager decision: build the stop menu (5.5 D-5), or record it as out of the CEO build |
| P2-14 | `VerstFlow.kt:686`, `:862` | Every reserve toggle, hotel pick or replace (`LocalCost.parse`) and every save (`SavedTrips.entry`) parses the private trip JSON (≤ 146 KB) on the main thread. Each parse takes a few ms on a mid phone, which is fine for now | Keep a parsed `JsonObject` in `PlanResultDto`, or parse on `Dispatchers.Default` if jank shows up |

---

## Checked and OK

- **Main thread.** No Python runs on the main thread. Every engine call goes through `withContext(host.dispatcher)` onto `verst-python` (`PlannerGateway.kt:70-74`, `:121-134`). `callHere` refuses the main looper. `cancel` runs on `Dispatchers.Default`. The listener posts events to Main.
- **Cancellation.**
  - Leaving Drive cancels `planJob`. The watcher in `cancellable()` calls `mobile.cancel`, and the engine returns `CANCELLED`, which is handled silently.
  - A cancel that arrives before the call starts leaves a tombstone. Request ids are fresh UUIDs, so a tombstone never hits a later call.
  - Estimates are cancelled by `collectLatest` when the draft changes or the screen is left.
  - A coroutine cancelled while still queued for `verst-python` never runs its block.
- **Uncaught exceptions.** None can escape the app scope: `callHere` and `EngineJson.decode` never throw, and the store I/O is wrapped. Error codes:
  - `INVALID_INPUT` → Instruments;
  - `UNREACHABLE` / `TOO_SHORT` → Navigator caption;
  - every other code (including `TRIP_INCOMPATIBLE`, `NOT_FOUND`, `NO_WORLD`, `TZDATA_MISSING`, `ENGINE_START`) → `error_upstream` + retry, or the `waybill_sync_failed` toast with the previous trip restored.
- **Saved-trip compatibility.** `ENGINE_VERSION` has been `0.1.0` since Sprint 1, so saved trips are never `TRIP_INCOMPATIBLE`. Bump the minor version only together with a stored-trip migration.
- **`CostCalculator` vs `cost/recompute.py`.** The algorithm is the same:
  - rules 1–5, rooms = ⌈adults/2⌉, breakfast on the day after a night without one, ticket rule 4, reserve/total/per-person steps, hints;
  - the engine bakes earlier overrides into `units` (`engine.py:527-556`), so a single override per local edit matches.
  - On rounding: `roundTo` rounds twice (to 12 places, then to 0). Python rounds once, at 28 significant digits. The results can differ only for a quotient with more than 12 decimals within 5·10⁻¹³ of .5. Money values have ≤ 7 decimals, and per-person divides a multiple of 100 by ≤ 8, so this cannot happen.
- **Manifest and APK.**
  - Only the launcher activity is exported, apart from P2-4.
  - No `INTERNET` permission, so cleartext traffic is impossible. No location permission.
  - `allowBackup=false`.
  - The `demo` build type is not debuggable and has no R8.
  - It is signed with the committed demo key, so installs over earlier builds work. `versionCode = run_number` is monotonic.
- **Rotation and configuration changes.** The activity is locked to portrait. Configuration changes (split screen, dark mode, font scale) recreate the activity, but `VerstFlow` is app-scoped, so the state survives. Process death is the gap: P1-2.
- **Atomicity of a single write.** One `AtomicFile` write is crash-safe, and the file carries `schema: 1`. The defects are the concurrency and the read-failure policy in P1-1.

## Doc changes made with this review

`docs/architecture-android-mvp.md` is updated to match `262103b`:

- §11 «Contracts (Kotlin)» now describes the per-case bundles `docs/contracts/{replace,patch}/<case>.json.gz`.
- §5.1 now documents `estimate`, `estimate_points`, the name forms, `pricesMonthRu`/`pricesYear`, `exitDistanceM`, `apiVersion` and `TRIP_INCOMPATIBLE`.
- §5.2 now shows the current `PlannerGateway`.
- §6.1 now describes the single `saved.json`.
- §8.2 and §9: the engine estimate is the only source of km and days; booking uses the fictional partner; the navigator hand-off is not built.
