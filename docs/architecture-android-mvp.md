# Verst — Android mock MVP architecture (Sprint 2, extended for Sprint 3 in §15 and §5.4)

Status: **approved for Sprint 2**; §5.4 and §15 approved for Sprint 3 · Owner: Architect · Date: 2026-10-24 · Decision records: ADR-0010; Sprint 3: ADR-0011…0014, `docs/backlog-sprint3.md`
As-built sync: §1, §5.1, §5.2, §6, §8.2, §9 and §11 were updated to `main` @ `262103b` with the pre-release review `docs/review/release-review.md`. Where the build differs from the plan, the text says "as built" or "not built".
Scope: the CEO's phone build. The app runs end to end on mock data (fixture worlds) with the real planner on the device, in design v5 «За рулём», built and released only by GitHub Actions.

References:

- `docs/architecture.md`, cited as A§n. A§11 stays the target for the server-backed release.
- `docs/SPEC.md`.
- `design/`: `tokens.json`, `DesignTokens.kt`, `components.md`, `screens/5.1…5.7`, `states/`, `copy-ru.md`, `icons/`, `motion.md`, `signs.md`, `decisions.md`, `visual-qa-checklist.md`.
- `docs/backlog-sprint2.md`.

---

## 0. What differs from A§11 and why

Every simplification lowers the number of things that can fail on a CI-only toolchain. Every one sits behind an interface that the server-backed build will keep.

| A§11 (target) | Mock MVP | Reason | Way back |
| --- | --- | --- | --- |
| 11 Gradle modules | **3 modules**: `:core-model` (JVM), `:core-ui` (Android library), `:app` (screens, data and engine as packages) | Fewer build scripts and fewer inter-module visibility errors. Each extra module adds one more CI round-trip of risk and adds nothing on a single-developer build | Packages map 1:1 to the A§11.2 modules (§4); splitting is moving folders. Package rules are enforced by `PackageRulesTest` |
| Hilt + KSP | **Manual DI** (`AppContainer`, ViewModel factories) | KSP versions are coupled to the exact Kotlin version, and annotation-processing errors are opaque in CI logs | Hilt modules mirror `AppContainer` fields |
| Room | **JSON files** (`AtomicFile`) for trips + **Preferences DataStore** for defaults | ≤ 51 trip blobs, no queries, no pending ops (no server). Avoids KSP and schema export | `TripStore` interface stays; a Room implementation plus a one-time file importer come with the API |
| Retrofit, OkHttp, SSE | **None.** `ChaquopyPlannerGateway` implements `PlannerGateway` | No server (CEO) | `HttpPlannerGateway` implements the same port and emits the same `PlanStreamEvent`s |
| MapLibre map picker (D-3) | **Not built**; button shows a plate (DES-104) | No real maps (CEO) | — |
| AppMetrica | **None**; events logged to logcat tag `VerstAnalytics` | No accounts, no network | `Analytics` interface |
| Paparazzi | **Robolectric native-graphics screenshots** written by our own 60-line `Screenshot` helper; PNGs to `ci-logs` | Paparazzi pins layoutlib to compileSdk and lags AGP releases. Roborazzi adds a plugin and a version to verify. Robolectric renders with real Skia and real fonts | A Roborazzi/Paparazzi swap only changes the helper |
| detekt rule `NoColorLiteralOutsideTokens`, ktlint | **JVM source-scan tests** (`TokenLiteralsTest`, `PackageRulesTest`) | No extra Gradle plugins | — |
| `debug` / `release` build types | Adds a **`demo`** build type: release-like, not debuggable, no R8, signed with the committed demo key. **This is what the CEO installs** | Debuggable Compose apps run without ART ahead-of-time compilation and look janky. The CEO judges the motion of the scene. No R8 means no keep-rule risk around Chaquopy | `release` stays for the store build |

Unchanged from A§11: Kotlin + Compose, single activity, type-safe Navigation Compose, UDF/MVVM (A§11.4), `:core-model` as a pure JVM module with `CostCalculator`/`TripEditor` ported from Python (A§7.3, A§16.11.4), DataStore keys (A§11.6, a subset), `DesignTokens.kt` as the only place for literals (A§11.10), and the Canvas scene (A§11.9 + components §9 + motion §5).

---

## 1. Runtime overview

```
┌──────────────────────────── app.verst.demo (one process) ────────────────────────────────┐
│ MainActivity (Compose, edge-to-edge, portrait)                                            │
│   VerstNavHost ─▶ feature.* screens (stateless) ◀── ViewModels (StateFlow / intents)      │
│                          │                                                                │
│                          ▼  ports from :core-model                                        │
│   PlannerGateway   TripStore   DefaultsRepository   ReadyRouteRepository   LinkLauncher   │
│        │               │              │                     │                  │          │
│ ChaquopyPlanner   FileTripStore   DataStoreDefaults   EngineReadyRoutes   AndroidLink     │
│ Gateway               (filesDir/trips)                + file cache        Launcher +      │
│        │                                                                  MockPartner     │
│        ▼  single thread "verst-python" (cancel from any thread)                           │
│   EngineHost ── Python.start(AndroidPlatform) ── module verst_planner.mobile              │
│        │                         │                                                        │
│        │   assets/worlds/*.json ─┘  (backend/planner/fixtures/worlds, passed as strings)  │
│        ▼                                                                                  │
│   CPython 3.12 (Chaquopy) + verst_planner (backend/planner, unchanged except DEV-110)     │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

External:

- Sprint 3 (ADR-0014): hand-off to Яндекс Навигатор (car) and Яндекс Карты (walking), with a browser fallback.
- Booking: the in-app `MockPartnerSheet` with the fictional partner «Придорожная» (OI-40).
- Share: the Android share sheet.
- Sprint 3 (ADR-0012): Wikimedia Commons photos and Nominatim addresses, the only network uses.

---

## 2. Repository layout (new paths)

```
android/
  settings.gradle.kts  build.gradle.kts  gradle.properties
  gradle/libs.versions.toml  gradle/wrapper/{gradle-wrapper.jar, gradle-wrapper.properties}  gradlew  gradlew.bat
  fonts.lock                                  # written by .github/workflows/fonts.yml (DES-100)
  core-model/  build.gradle.kts  src/main/kotlin/app/verst/core/model/**  src/test/kotlin/**
  core-ui/     build.gradle.kts  src/main/kotlin/app/verst/core/ui/**
               src/main/res/{font,drawable,values}/  src/main/assets/licenses/  src/test/kotlin/**
  app/         build.gradle.kts  demo.keystore  src/main/AndroidManifest.xml
               src/main/kotlin/app/verst/**  src/main/res/{mipmap-anydpi-v26,drawable,values}/
               src/test/kotlin/**  (Robolectric: screens, screenshots, rules)
               src/androidTest/kotlin/app/verst/e2e/**  (emulator: journey, parity, timings)
backend/planner/verst_planner/mobile.py       # app-facing engine API (DEV-111), stdlib only
tools/ci/{diagnose.py, combine_run.py, ci_logs_index.py, publish_ci_logs.sh, run_e2e.sh, fetch_fonts.py}
.github/workflows/{android.yml, fonts.yml}    # planner.yml unchanged except runner pin (DEV-100)
design/tools/{gen_strings.py, gen_vectors.py, qa_sample.py}  design/qa/*.json   # Designer (DES-101/102/106)
```

---

## 3. Toolchain and version catalog

### 3.1 Pinned versions

- **Catalog A** is primary.
- **Catalog B** is the pre-agreed fallback if Chaquopy rejects AGP 8.11 (ADR-0010). Switching is one PR touching `libs.versions.toml` and `compileSdk`/`targetSdk`.
- All versions predate this document by well over 2 weeks. They are mutually compatible as far as the Architect knows them, and **each is re-verified by the first green CI run** (DEV-100/101). The Architect then records the effective versions here.

| Item | Catalog A | Catalog B | Notes |
| --- | --- | --- | --- |
| Gradle (wrapper) | 8.14.3 | 8.14.3 | Wrapper generated offline in the sandbox from `/opt/gradle-8.14.3` (verified: `gradle wrapper --gradle-version 8.14.3 --offline` works) |
| JDK | Temurin 17 (`actions/setup-java`) | 17 | `compilerOptions.jvmTarget = 17`. No `jvmToolchain()`, which would need toolchain auto-provisioning |
| AGP | 8.11.1 | 8.7.3 | AGP 8.11 needs Gradle ≥ 8.13 |
| compileSdk / targetSdk / minSdk | 36 / 36 / 26 | 35 / 35 / 26 | Chaquopy 16 needs minSdk ≥ 24 |
| Kotlin (android, jvm, compose, serialization plugins) | 2.2.0 | 2.2.0 | |
| Chaquopy (`com.chaquo.python`) | 16.0.0 | 16.0.0 | Python `version = "3.12"`; build Python 3.12 from `actions/setup-python` |
| pip `tzdata` | 2025.2 | 2025.2 | pure Python; used automatically by `zoneinfo` |
| Compose BOM | 2025.07.00 | 2025.07.00 | `ui`, `ui-graphics`, `ui-text`, `foundation`, `animation`, `ui-tooling-preview`, `ui-test-junit4`, `ui-test-manifest`. **No material3** (G-02) |
| androidx core-ktx | 1.16.0 | 1.16.0 | `AtomicFile`, `WindowCompat` |
| activity-compose | 1.10.1 | 1.10.1 | `enableEdgeToEdge`, `BackHandler` |
| lifecycle (runtime-compose, viewmodel-compose) | 2.9.1 | 2.9.1 | |
| navigation-compose | 2.9.1 | 2.9.1 | type-safe routes |
| datastore-preferences | 1.1.7 | 1.1.7 | |
| kotlinx-coroutines (android, test) | 1.10.2 | 1.10.2 | |
| kotlinx-serialization-json | 1.9.0 | 1.9.0 | |
| junit | 4.13.2 | 4.13.2 | |
| robolectric | 4.15.1 | 4.15.1 | tests pinned to `sdk = 35` (`robolectric.properties`) |
| androidx.test core / ext-junit / runner / rules | 1.6.1 / 1.2.1 / 1.6.2 / 1.6.1 | same | |
| Actions | checkout@v4, setup-java@v4, setup-python@v5, gradle/actions/setup-gradle@v4, upload/download-artifact@v4, cache@v4, reactivecircus/android-emulator-runner@v2 | same | runner pinned to `ubuntu-24.04`. The check-run annotation on run 40042983764 announces the `ubuntu-latest` → Ubuntu 26 migration from 2026-10-19 |

### 3.2 `android/gradle/libs.versions.toml` (Catalog A, verbatim)

```toml
[versions]
agp = "8.11.1"
kotlin = "2.2.0"
chaquopy = "16.0.0"
compose-bom = "2025.07.00"
core-ktx = "1.16.0"
activity-compose = "1.10.1"
lifecycle = "2.9.1"
navigation = "2.9.1"
datastore = "1.1.7"
coroutines = "1.10.2"
serialization = "1.9.0"
junit = "4.13.2"
robolectric = "4.15.1"
androidx-test-core = "1.6.1"
androidx-test-ext-junit = "1.2.1"
androidx-test-runner = "1.6.2"
androidx-test-rules = "1.6.1"

[libraries]
androidx-core-ktx = { module = "androidx.core:core-ktx", version.ref = "core-ktx" }
androidx-activity-compose = { module = "androidx.activity:activity-compose", version.ref = "activity-compose" }
androidx-lifecycle-runtime-compose = { module = "androidx.lifecycle:lifecycle-runtime-compose", version.ref = "lifecycle" }
androidx-lifecycle-viewmodel-compose = { module = "androidx.lifecycle:lifecycle-viewmodel-compose", version.ref = "lifecycle" }
androidx-navigation-compose = { module = "androidx.navigation:navigation-compose", version.ref = "navigation" }
androidx-datastore-preferences = { module = "androidx.datastore:datastore-preferences", version.ref = "datastore" }
compose-bom = { module = "androidx.compose:compose-bom", version.ref = "compose-bom" }
compose-ui = { module = "androidx.compose.ui:ui" }
compose-ui-graphics = { module = "androidx.compose.ui:ui-graphics" }
compose-ui-text = { module = "androidx.compose.ui:ui-text" }
compose-foundation = { module = "androidx.compose.foundation:foundation" }
compose-animation = { module = "androidx.compose.animation:animation" }
compose-ui-tooling-preview = { module = "androidx.compose.ui:ui-tooling-preview" }
compose-ui-tooling = { module = "androidx.compose.ui:ui-tooling" }
compose-ui-test-junit4 = { module = "androidx.compose.ui:ui-test-junit4" }
compose-ui-test-manifest = { module = "androidx.compose.ui:ui-test-manifest" }
kotlinx-coroutines-core = { module = "org.jetbrains.kotlinx:kotlinx-coroutines-core", version.ref = "coroutines" }
kotlinx-coroutines-android = { module = "org.jetbrains.kotlinx:kotlinx-coroutines-android", version.ref = "coroutines" }
kotlinx-coroutines-test = { module = "org.jetbrains.kotlinx:kotlinx-coroutines-test", version.ref = "coroutines" }
kotlinx-serialization-json = { module = "org.jetbrains.kotlinx:kotlinx-serialization-json", version.ref = "serialization" }
junit = { module = "junit:junit", version.ref = "junit" }
robolectric = { module = "org.robolectric:robolectric", version.ref = "robolectric" }
androidx-test-core = { module = "androidx.test:core", version.ref = "androidx-test-core" }
androidx-test-ext-junit = { module = "androidx.test.ext:junit", version.ref = "androidx-test-ext-junit" }
androidx-test-runner = { module = "androidx.test:runner", version.ref = "androidx-test-runner" }
androidx-test-rules = { module = "androidx.test:rules", version.ref = "androidx-test-rules" }

[plugins]
android-application = { id = "com.android.application", version.ref = "agp" }
android-library = { id = "com.android.library", version.ref = "agp" }
kotlin-android = { id = "org.jetbrains.kotlin.android", version.ref = "kotlin" }
kotlin-jvm = { id = "org.jetbrains.kotlin.jvm", version.ref = "kotlin" }
kotlin-compose = { id = "org.jetbrains.kotlin.plugin.compose", version.ref = "kotlin" }
kotlin-serialization = { id = "org.jetbrains.kotlin.plugin.serialization", version.ref = "kotlin" }
chaquopy = { id = "com.chaquo.python", version.ref = "chaquopy" }
```

Catalog B differs only in `agp = "8.7.3"`, plus `compileSdk = 35` and `targetSdk = 35` in the two Android modules.

### 3.3 Build scripts (normative fragments)

`settings.gradle.kts`:

```kotlin
pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.PREFER_SETTINGS)   // not FAIL_*: a plugin adding a repo must not break the build
    repositories { google(); mavenCentral() }
}
rootProject.name = "verst"
include(":core-model", ":core-ui", ":app")
```

`gradle.properties`:

```
org.gradle.jvmargs=-Xmx4g -Dfile.encoding=UTF-8
org.gradle.caching=true
org.gradle.parallel=true
android.useAndroidX=true
android.nonTransitiveRClass=true
kotlin.code.style=official
```

Configuration cache stays off: Chaquopy's support for it has not been verified.

`app/build.gradle.kts` (the parts that matter):

```kotlin
plugins { alias(libs.plugins.android.application); alias(libs.plugins.kotlin.android); alias(libs.plugins.kotlin.compose)
          alias(libs.plugins.kotlin.serialization); alias(libs.plugins.chaquopy) }
val repoRoot: File = rootDir.parentFile
val buildNumber = (System.getenv("VERST_BUILD_NUMBER") ?: "1").toInt()
android {
    namespace = "app.verst"; compileSdk = 36
    defaultConfig {
        applicationId = "app.verst"; minSdk = 26; targetSdk = 36
        versionCode = buildNumber; versionName = "0.2.$buildNumber-mock"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
        buildConfigField("String", "GIT_SHA", "\"${(System.getenv("VERST_GIT_SHA") ?: "local").take(12)}\"")
    }
    signingConfigs { create("demo") { storeFile = file("demo.keystore"); storePassword = "verstdemo"
                                      keyAlias = "verst-demo"; keyPassword = "verstdemo" } }
    buildTypes {
        create("demo") { initWith(getByName("release")); isDebuggable = false; isMinifyEnabled = false
                         applicationIdSuffix = ".demo"; signingConfig = signingConfigs.getByName("demo")
                         matchingFallbacks += listOf("release") }
        getByName("debug") { applicationIdSuffix = ".debug"; signingConfig = signingConfigs.getByName("demo") }
    }
    testBuildType = "demo"                                 // androidTest APK targets the APK the CEO installs
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    buildFeatures { compose = true; buildConfig = true }
    sourceSets {
        getByName("main") { assets.srcDir(repoRoot.resolve("backend/planner/fixtures")) }          // assets/worlds/*.json
        getByName("androidTest") { assets.srcDir(repoRoot.resolve("backend/planner/tests/golden")) } // cases/, snapshots/
    }
    testOptions { unitTests { isIncludeAndroidResources = true
        all { it.systemProperty("verst.repoRoot", repoRoot.absolutePath)
              it.systemProperty("verst.screenshots.dir", System.getenv("VERST_SCREENSHOTS_DIR")
                  ?: layout.buildDirectory.dir("outputs/screenshots").get().asFile.absolutePath)
              it.maxHeapSize = "3g" } } }
    lint { abortOnError = true; warningsAsErrors = false; xmlReport = true; sarifReport = true; checkReleaseBuilds = false }
}
kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }
chaquopy {
    defaultConfig {
        version = "3.12"
        pip { install("tzdata==2025.2") }
        // fallback switch (ADR-0010 risks): extractPackages("verst_planner")
    }
    sourceSets { getByName("main") { srcDir(repoRoot.resolve("backend/planner")) } }   // verst_planner/ + tests/ + tools/ (≈ 1 MB)
    // If Chaquopy rejects a non-package file there (e.g. byte-compiling tools/*.py), replace the line above with a
    // Sync task copying only backend/planner/verst_planner/** into build/generated/planner-python, srcDir() that,
    // and make every task whose name contains "Python" depend on it (record in dev-notes).
}
dependencies {
    implementation(project(":core-model")); implementation(project(":core-ui"))
    implementation(platform(libs.compose.bom)); implementation(libs.compose.ui); implementation(libs.compose.foundation)
    implementation(libs.compose.animation); implementation(libs.compose.ui.tooling.preview)
    implementation(libs.androidx.core.ktx); implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.compose); implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.navigation.compose); implementation(libs.androidx.datastore.preferences)
    implementation(libs.kotlinx.coroutines.android); implementation(libs.kotlinx.serialization.json)
    "demoImplementation"(libs.compose.ui.test.manifest); debugImplementation(libs.compose.ui.test.manifest)
    testImplementation(libs.junit); testImplementation(libs.robolectric); testImplementation(libs.androidx.test.core)
    testImplementation(platform(libs.compose.bom)); testImplementation(libs.compose.ui.test.junit4)
    testImplementation(libs.kotlinx.coroutines.test)
    androidTestImplementation(platform(libs.compose.bom)); androidTestImplementation(libs.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.test.ext.junit); androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.rules)
}
```

`ui-test-manifest` in `demo` adds one test `ComponentActivity` declaration to the demo APK. It is needed by Robolectric compose tests on the `demo` variant and is harmless.

- `core-ui/build.gradle.kts`: Android library, `namespace = "app.verst.core.ui"` (this is the namespace `DesignTokens.kt` imports: `app.verst.core.ui.R`). It carries Compose and the same `unitTests` block, with `debugImplementation(ui-test-manifest)`.
- `core-model/build.gradle.kts`: `kotlin("jvm")` + serialization, with `tasks.test { systemProperty("verst.repoRoot", rootDir.parentFile.absolutePath) }`.

### 3.4 Signing and versioning

- **`android/app/demo.keystore` is committed.** It is a PKCS12 file generated once in the sandbox (DEV-100):
  ```
  keytool -genkeypair -keystore android/app/demo.keystore -storetype PKCS12 -storepass verstdemo -keypass verstdemo \
          -alias verst-demo -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Verst Demo,O=Verst,C=RU"
  ```
  Same key on every CI run, so each new APK installs **over** the previous one and saved trips survive. It is a demo key with no store identity, so committing it is safe. The RuStore upload key will be a GitHub secret (A§12.4) and is never this one.
- `versionCode = github.run_number` (monotonic), `versionName = 0.2.<n>-mock`, `BuildConfig.GIT_SHA`.
- The settings sheet footer (D-4) reads «Сборка <n> · <sha7> · демо-данные». Exact copy: DES-104.

---

## 4. Modules, packages, dependency rules

| Module / package | Maps to A§11.2 | Contents |
| --- | --- | --- |
| `:core-model` `app.verst.core.model` | `:core-model` | `dto/`: `@Serializable` mirror of the plan JSON (`TripDto`, `DayDto`, `StopDto`, `AlternativeDto`, `StopTimeDto`, `HotelOptionDto`, `CostDto`, `CostLineDto`, `CostUnitsDto`, `AltUnitsDto`, `WarningDto`, `PlanEventDto`, `ReadyRouteDto`, `SuggestionDto`, `EngineErrorDto`). `engineState` is kept as an opaque `JsonElement`. `domain/`: `PlanRequest`, `Seats`, `BudgetPreset`, `Mood`, `FuelType`. `cost/CostCalculator` is the port of `cost/recompute.py`, including A§16.11.4. `trip/TripEditor` applies the alternative `dayPatch` and the hotel choice. `format/RuFormat` handles U+202F thousands, U+00A0 units and plurals (mirror of `explain/ru.py` for UI numbers only). `geo/Haversine`, `geo/Bearing8`. `ports/`: `PlannerGateway`, `TripStore`, `DefaultsRepository`, `ReadyRouteRepository`, `GeocodeRepository`, `LinkLauncher`, `Connectivity`, `Analytics`, `Clock` |
| `:core-ui` `app.verst.core.ui` | `:core-ui` | `theme/DesignTokens.kt`, a **byte-identical copy** of `design/DesignTokens.kt` (G-01, guarded by `DesignTokensInSyncTest`). `theme/VerstTheme.kt`. `scene/` holds `WindshieldScene`, `SceneSpec`, `RoadProjection`, `SceneClock`, `rememberSceneRunning`. `components/` holds every component in components.md §1–16: `OverheadSign`, `RoadSign` + `RoadSignPainter`, `StopRow`, `Mirror`, `SeatButton`, `DogToggle`, `Odometer`, `StepperKey`, `FuelGauge`, `StartButton`, `NaviPanel`, `Dashboard`, `WaybillSheet`, `Stamp`, `ExitSign`, `HotelOption`, `Chips`, `BackLink`, the CTA buttons, `BottomSheet` (foundation only), `NaviDialog`, `Plate`/`Toast`, `Shimmer`. `res/`: font (DES-100), drawable `ic_*` (DES-102), values `strings.xml` + `plurals.xml` (DES-101), `assets/licenses/` |
| `:app` `app.verst` | `:app` | `VerstApp` (creates `AppContainer`, starts `EngineHost`), `MainActivity`, `nav/` (`Routes.kt`, `VerstNavHost.kt`), `AppContainer.kt` |
| `app.verst.engine` | (`:data` network part) | `EngineHost`, `PythonThread`, `ChaquopyPlannerGateway`, `PlanEventListener` (Java-visible interface), `WorldAssets`, `EngineTimings` |
| `app.verst.data` | `:data` | `FileTripStore`, `DataStoreDefaults`, `ReadyRouteCache`, `RecentSearchStore`, `SimulatedConnectivity`, `AndroidLinkLauncher` (navigator intents, `<queries>`), `MockPartner` |
| `app.verst.feature.windshield` … `.exit`, `.trips`, `.debug` | `:feature-*` | One package per screen with the A§11.2 file set: `XScreen.kt` (stateless; `XUiState` + `(XIntent) -> Unit`), `XRoute.kt` (stateful wrapper), `XViewModel.kt`, `XUiState.kt`, `XIntent.kt`, `XEffect.kt`, `components/` |

Rules, enforced by `PackageRulesTest`, a JVM test that scans `import` lines of `app/src/main/kotlin`:

1. `feature.A` never imports `feature.B`.
2. `feature.*` never imports `app.verst.engine` or `app.verst.data`. It sees ports only, bound in `AppContainer`.
3. Only `app.verst.engine` imports `com.chaquo.python`.
4. `:core-model` has no Android imports. This holds by construction, because it is a JVM module.

`TokenLiteralsTest` fails on any of these in `app/src/main/kotlin/**` and in `core-ui/.../components|scene/**`:

- `Color(0x`;
- a numeric `.sp`;
- a numeric `.dp` outside `Modifier.offset`/`size` declarations taken from tokens;
- `tween(` with a numeric literal.

An allow-list holds the documented exceptions, and the list must be empty at sprint end.

---

## 5. On-device engine

### 5.1 Python side: `verst_planner/mobile.py` (DEV-111)

`mobile.py` is a stdlib-only composition root, like `cli.py`, and is allowed by the layering test to import everything. **Every public function takes and returns `str` (JSON) and never raises.** The envelope is:

```jsonc
{"ok": true,  "result": <payload>, "ms": 12}
{"ok": false, "error": {"code": "UNREACHABLE", "message": "<engine message or ''>", "field": null, "reason": null,
                        "pointIndex": 1, "detail": "<repr or traceback for INTERNAL>"}, "ms": 3}
```

Error codes:

- the `PlannerError.code` values: `INVALID_INPUT` with `field`/`reason`, `UNREACHABLE` with `pointIndex`, `TOO_SHORT` with `roadKm`, `NOT_FOUND`, `CANCELLED`, `UPSTREAM`;
- `INTERNAL`: any other exception, including a serialization failure. The traceback goes to `detail` and to stderr, which Chaquopy routes to logcat `python.stderr`;
- `NO_WORLD`;
- `TZDATA_MISSING`;
- `TRIP_INCOMPATIBLE`: a stored trip whose `engineVersion` differs in major.minor; `field` = `engineVersion`. A missing `engineVersion` is `INVALID_INPUT`.

`message` is diagnostic English. The app chooses its copy by `code` only. Arguments are decoded strictly: JSON booleans only, integers that are not booleans, strings where strings are expected. `API_VERSION = 1` is returned by `selfcheck` as `apiVersion`; additive changes keep it.

| Function | Payload | Notes |
| --- | --- | --- |
| `load_world(text)` | `{"id", "asOf", "towns": n, "places": n, "readyRoutes": n}` | `FakeWorld.from_dict(json.loads(text))` + `build_fakes`; one `Planner` per world, `config = PlannerConfig.from_dict({})` |
| `selfcheck()` | `{"engineVersion", "apiVersion": 1, "python": "3.12.x", "tz": {"Europe/Moscow": true, "Europe/Volgograd": true}, "resources": true, "worlds": [...]}` | `ZoneInfo` for every `tz` of every loaded region; config, templates and strings load. Fails with `TZDATA_MISSING` if a zone cannot be resolved |
| `set_clock(spec)` | `{"now": iso}` | `"system"` (default, aware UTC now), `"golden"` (`GOLDEN_CLOCK`), or an ISO datetime |
| `suggest(world, q, lat, lon, limit)` | `[{"kind": "city"\|"place", "name", "subtitle", "lat", "lon", "id", "nameGenRu", "namePrepRu"}]` | `FakeGeocoding.suggest`. `subtitle` follows A§5.3.2 («город · Ярославская область»). `id` = town/place id. `nameGenRu`/`namePrepRu` are the town's genitive/prepositional forms («Ярославля» / «Ярославле», fixture `towns[].nameGenRu`, OI-39), `null` for places. The app never inflects names itself |
| `popular(world, limit, origin_id=None)` | same shape | Towns by population, descending, for the «ЧАСТО ИЩУТ» chips (OI-04). They exclude `origin_id`, which defaults to the most populous town. The app does not pass the origin yet (review P2-7) |
| `reverse(world, lat, lon)` | `{"name", "subtitle", "nameGenRu", "namePrepRu"} \| null` | The nearest town within 30 km. The app takes the origin's genitive from it («ИЗ МОСКВЫ») |
| `ready_routes(world, lat, lon, radius_km, limit)` | `[{"id", "title", "subtitle", "kmTotal", "kmSign", "ring", "roundTrip", "daysMin", "daysMax", "tags", "hubTownId", "bearing8", "coverKey"}]` | A§6.12: hub within radius, sorted `(kmSign, sort)`. `bearing8` = `geo.bearing.bearing8(hub, first via)` |
| `plan(world, request_id, input_json, listener)` | `{"trip": <plan_to_json(plan, public=False)>, "shareText", "pricesMonthRu", "pricesYear", "townPrepRu": {townId: form}, "townGenRu": {townId: form}}` | `listener.onEvent(event_json)` is called per `PlanEvent` (`events.event_to_json`); listener errors are swallowed after the first one. The `CancelToken` is registered under `request_id`. N-10: the split stage text uses the trip km of an identical earlier `estimate` (a cache of 64, keyed by world + canonical input; it runs a quiet estimate on a miss), so «по ≈ N км» matches the header. `pricesMonthRu`/`pricesYear` feed the Waybill footnote. The name maps cover every stop town, so the plan codec and the goldens stay unchanged. Every hotel option carries `exitDistanceM` (OI-41: route → hotel lateral distance in m, 0 = unknown), used by the 5.7 exit sign |
| `estimate(world, request_id, input_json)` | `{"km", "days"}` | **The only source of trip km/days before Road ahead** (DEV-SLICE-2 P0): the engine's own plan of the same `TripInputDTO`, without events, so it equals the later `plan` exactly. It is cancellable like `plan`, and its errors are those of `plan` (`TOO_SHORT`/`UNREACHABLE` are known on the Navigator before planning) |
| `estimate_points(world, lat, lon, points_json)` | `[km \| null]` | Base-route km (stages 0–2) from the origin to each suggestion row. `null` = unreachable or outside Russia. Rows show «≈ 263 км»; the picked trip shows the estimate's «265 км» |
| `cancel(request_id)` | `{"cancelled": bool}` | thread-safe (lock); callable while `plan` runs on another thread |
| `replace_stop(world, trip_json, stop_id, alt_id)` | same as `plan` | `codec.plan_from_json` → `Planner.replace_stop`; `TRIP_INCOMPATIBLE` on an engine major.minor mismatch |
| `patch_cost(world, trip_json, patch_json)` | same as `plan` | `patch_json` = `{"crew"?, "budget"? (null = не важно), "reserveOn"?, "hotelChoice"?: {"stopId", "placeId"}}` → `CostPatch` |
| `share_text(trip_json)` | `str` | `explain.share.share_text` |
| `golden_snapshot(case_json)` | `str` | exact `tests/golden/test_golden.snapshot_text` output for a golden case (`world`, `clock`, `config`, `input`). Used by the emulator parity test |

The CLI gains `python3 -m verst_planner.mobile selftest`. It runs the whole API against both worlds and prints one line per function, so sandbox runs look like device runs.

### 5.2 Kotlin side

- **`EngineHost`** (singleton, created in `VerstApp.onCreate`):
  - Starts on the dedicated thread `verst-python`: `Python.start(AndroidPlatform(app))` → `getModule("verst_planner.mobile")` → `load_world` for `assets/worlds/central_russia_v1.json` and `edge_cases_v1.json` → `set_clock("system")` (as built, always; the debug panel switches to `golden` later) → `selfcheck`. `restart()` re-runs the boot after `Failed` (5.1 «Повторить»).
  - Exposes `status: StateFlow<EngineStatus>` = `Starting(phase)` | `Ready(EngineInfo)` | `Failed(code, detail)`.
  - `EngineInfo` carries the timings `pythonStartMs`, `importMs`, `worldsMs`, `selfcheckMs` and `totalMs`. They are logged under tag `VerstEngine` and shown in the debug panel.
- **`PythonThread`**: `Executors.newSingleThreadExecutor { Thread(it, "verst-python") }.asCoroutineDispatcher()`. Every call except `cancel` runs here, so calls are serialized and there is no GIL contention. `cancel` runs on `Dispatchers.Default`. Python never runs on the main thread.
- **`ChaquopyPlannerGateway : PlannerGateway`** (`app/src/main/kotlin/app/verst/engine/PlannerGateway.kt`). This is the interface as built in `262103b`; the M§5.2 draft had `Flow<PlanStreamEvent>` and `StoredTrip` arguments:
  ```kotlin
  interface PlannerGateway {
      var world: String                                                    // central_russia_v1 | edge_cases_v1 (debug panel, in memory)
      suspend fun readyRoutes(origin: GeoPoint): EngineResult<List<ReadyRouteDto>>          // radius 50 km, limit 20
      suspend fun suggest(query: String, near: GeoPoint?): EngineResult<List<SuggestionDto>>
      suspend fun popular(): EngineResult<List<SuggestionDto>>
      suspend fun reverse(point: GeoPoint): EngineResult<PlaceNameDto?>                     // name forms of the origin (OI-39)
      suspend fun estimate(requestId: String, request: PlanRequest): EngineResult<EstimateDto>   // the single km/days source
      suspend fun estimatePoints(origin: GeoPoint, points: List<GeoPoint>): EngineResult<List<Int?>>
      suspend fun plan(requestId: String, request: PlanRequest, onEvent: (PlanEventDto) -> Unit): EngineResult<PlanResultDto>
      suspend fun replaceStop(tripJson: String, stopId: String, altId: String): EngineResult<PlanResultDto>
      suspend fun patchCost(tripJson: String, patchJson: String): EngineResult<PlanResultDto>
      suspend fun setClock(spec: String): EngineResult<Unit>                                 // "system" | "golden"
  }
  ```
  - Every call first waits for `EngineStatus.Ready`, for at most 30 s. A failure or timeout becomes an `EngineResult.Err` with the start code (`ENGINE_START`, `NO_ENGINE`, …).
  - `PlanResultDto.tripJson` is the engine's private trip verbatim (with `engineState`). It is the input of every later engine call on that trip, and it is what gets saved.
  - `plan` and `estimate` run inside `cancellable(requestId)`. A sibling coroutine waits for the caller's cancellation and then calls `EngineHost.cancel` (`mobile.cancel`) on `Dispatchers.Default`, because the blocking call holds `verst-python`. So leaving Drive, or a newer draft (`collectLatest`), stops the engine run (D-13).
  - `PlanEventListener.onEvent` is called on `verst-python` and posts each decoded event to Main.
- **World and clock**: `gateway.world` (default `central_russia_v1`) and the clock are switched by the debug panel and are **not persisted**: a restart is central world + system clock. Saved trips do not record their world yet (review P2-2). The origin defaults to Москва (Тестовск in the edge world).
- **Parity guard** (planned, **not built** — review P2-11): after a local Kotlin recompute (§6.3), the engine result arrives; if `cost.totalRub` differs, log `VerstParity` and count it in the debug panel; the emulator journey asserts 0. Today parity is proven on the JVM only (`LocalCostBundleTest`, §11).

### 5.3 Fidelity proof on the device

`EngineParityTest` (androidTest) reads every `cases/*.json` with a snapshot from the androidTest assets and calls `golden_snapshot`. It asserts the text equals `snapshots/<case>.json` byte for byte, and writes `parity.json` (case → equal, ms). The 10 snapshot cases run in < 10 s on the emulator. The edge cases G09/G10 assert the error codes `UNREACHABLE` / `TOO_SHORT`.

### 5.4 Sprint 3: `mobile.py` API v2 (`API_VERSION = 2`; ADR-0011…0014)

v2 is additive. Every v1 function keeps its signature and payload, and gains only optional fields. Old saved trips stay valid: `ENGINE_VERSION` stays `0.1.0`, so they never become `TRIP_INCOMPATIBLE`. Each function below has request/response examples in `docs/contracts/v2/<function>[-<case>].json` (`{"request": {...}, "response": <envelope>}`), generated by `tools/gen_mobile_contracts.py --v2` (ARCH-305). The Developer builds the Kotlin DTOs against these files.

**Worlds.** `central_russia_v1` (goldens, unchanged), `edge_cases_v1` (unchanged), and **`russia_v1`** (ADR-0012 §4). `russia_v1` = the fixture world + the catalogue + synthetic services, with `HybridRouting`. It becomes the app's default world. The debug panel still offers all three.

**New error codes:**

| Code | Meaning |
| --- | --- |
| `NO_CATALOGUE` | The catalogue resources are missing or corrupt. Boot → `EngineStatus.Failed` |
| `NO_CITY` | A walk start farther than 15 km from any town |
| `NOT_ENOUGH_POIS` | A walk with < 2 feasible stops; `field = preset` |
| `INVALID_INPUT` | New reasons: `adultConfirmed/required`, `preset/children` |

| Function | Payload | Notes |
| --- | --- | --- |
| `load_catalogue()` | `{"version", "builtAt", "towns", "pois", "bars", "ms"}` | Called by `EngineHost` after both `load_world` calls. It composes `russia_v1`. Timing goes to `EngineTimings.catalogueMs` |
| `selfcheck()` | v1 + `"apiVersion": 2`, `"catalogue": {"version", "towns", "pois", "bars"}` | |
| `geo_search(world, q, lat, lon, limit, kinds)` | `[{"kind": "city"\|"poi"\|"place", "id", "name", "subtitle", "lat", "lon", "nameGenRu", "namePrepRu", "population", "regionRu", "poiKind", "hasPhoto"}]` | Offline typeahead (ADR-0012 §5). Towns rank by prefix → population → distance; POIs by prefix → popularity. `kinds` defaults to all three. `suggest` = `geo_search` with the v1 fields |
| `geo_nearest(world, lat, lon)` | `{"town": {"id", "name", "nameGenRu", "namePrepRu", "regionRu", "lat", "lon", "population"}, "distanceKm", "insideRussia"}` | GPS → origin town. `insideRussia` = the nearest town is ≤ 60 km away |
| `plan(…)` | v1 result + `"outcome": "plan"`. The trip may carry `budgetFit` (ADR-0011) and `"approxDistances": true` (synthetic route). Alternatives may carry `breaksBudget: true` | **or** `{"outcome": "no_fit", "budgetRub", "allowedRub", "minimum": {"totalRub", "levers", "trip", "shareText", …name maps}, "options": [...], "textRu"}` (ADR-0011). Stage events gain «Подбираем под бюджет: …» (key `budget`, progress 0.92) |
| `estimate(…)` | `{"km", "days", "outcome", "totalRub", "budgetStatus": "fits"\|"small_overrun"\|null}` | The same ladder as `plan`. For `no_fit`, `km`/`days` are those of the minimum |
| `patch_cost(…)` | v1 | Budget patches stay cost-only (no re-fit). Crew patches recompute the explicit `rooms` |
| `city_presets(world, lat, lon)` | `{"town": {…as geo_nearest}, "presets": [{"preset", "available", "count", "defaultDurationMin", "adultOnly", "titleRu"}]}` | Gates per ADR-0013. Unavailable presets are listed with `available: false` (the app hides them) |
| `city_route(world, request_id, input_json)` | `WalkRoute` (ADR-0013 "Output") | Cancellable by `cancel(request_id)`. Deterministic for a given input and clock |
| `poi_details(world, place_id)` | `{"id", "kind": "sight"\|"hotel"\|"bar", "poiKind", "nameRu", "descriptionRu", "townName", "lat", "lon", "image": {"card", "thumb", "page", "credit": {"author", "licence", "licenceUrl"}\|null, "isArea", "labelRu"}\|null, "hours": {"textRu", "verified"}\|null, "ticket": {"adultRub", "childRub", "estimate"}\|null, "isFictional", "attributionRu": [...], "wikidataId"}` | Sights, hotels and bars only. Fuel, rest, start and finish → `NOT_FOUND`; the app does not make them tappable. A synthetic hotel → `isFictional: true`, `image.isArea: true`, `labelRu` «Фото района: {город} · Wikimedia Commons» |
| `handoff(world, route_json, options_json)` | `{"mode": "car"\|"walk", "parts": [{"index", "points": [{"lat", "lon", "nameRu", "role"}], "links": {"navigator"?, "maps", "web"}}], "truncated"}` | ADR-0014. The links are the only engine output that contains a brand host name |

**Kotlin `PlannerGateway` additions:**

- `geoSearch`, `geoNearest`, `cityPresets`, `cityRoute(requestId, input)` (cancellable via the `cancellable()` watcher), `poiDetails`, `handoff`;
- `plan`/`estimate` decode `outcome`.

The boot sequence gains `load_catalogue` between the worlds and `set_clock`.


---

## 6. Data

### 6.1 Trips: `FileTripStore : TripStore`

**As built (`262103b`, DEV-SLICE-2/3):** one file holds the whole list.

```
filesDir/trips/saved.json           {"schema": 1, "trips": [SavedTripDto…]}: ≤ 50, warning from 45, upsert by id, written via android.util.AtomicFile
```

```jsonc
// SavedTripDto (core-model SavedTrips.kt)
{"id": "<uuid>", "savedAt": 1761300000000, "title": "Золотое кольцо", "km": 761, "days": 3, "totalRub": 33800,
 "startAt": "2026-11-07T08:00", "adults": 2, "children": 1, "dog": true, "bearing8": "NE",
 "shareText": "…", "pricesMonthRu": "октябрь", "pricesYear": "2026",
 "townPrepRu": {"t_yaroslavl": "Ярославле"}, "townGenRu": {"t_yaroslavl": "Ярославля"},
 "bookedHotels": {"d1s07": "pl_yar_hotel_2"},          // D-10: per overnight stop, the hotel marked «Забронировали»
 "trip": { /* plan_to_json(plan, public=False) verbatim: PlanResponse + engineState */ }}
```

- The trip JSON returned by the engine is authoritative. Everything else is list metadata or UI state that the engine does not own.
- An unknown `schema` or an unreadable file must be **kept aside and logged, never overwritten**. Today it is read as an empty list and overwritten on the next save. That is a P1 in `docs/review/release-review.md`, together with the unserialized writes; all writes must go through one writer.

**Still to build (review P1-2):** `filesDir/trips/last.json`, the one unsaved "last trip" slot (overwritten by the next plan; SPEC §13). It restores Road ahead after process death. Also still to build: `filesDir/cache/ready_routes.json` (last ready-route list per world and origin) and `recent_searches.json` (≤ 10). Splitting `saved.json` into `saved/<id>.json` files is optional; it would make one save cost one trip instead of the whole list.

### 6.2 Defaults: `DataStoreDefaults` (`verst_prefs`)

**Not built as of `262103b`** (review P2-10). The crew, km/day, budget, mood and origin reset on every launch, and the DataStore dependency is not in `:app`. This section is the target.

These keys are a subset of A§11.6, with the same names and defaults: `crew_back_seats`, `crew_front_passenger`, `crew_dog`, `crew_third_row`, `daily_km`, `daily_km_user_set`, `budget_preset`, `consumption`, `fuel_type`, `tank_l`, `start_time`, `avoid_tolls`, `mood`, `last_origin_id`/`_label`/`_lat`/`_lon`.

Debug-only keys:

- `debug_world` (`central_russia_v1`);
- `debug_clock` (`system` | `golden`);
- `debug_offline` (false);
- `debug_slow_plan_s` (0);
- `debug_force_error` (null | engine code).

Device token, location and onboarding keys are not used.

### 6.3 Offline edits (local first, engine second — A§11.4 flow with the engine as "server")

| Action | Immediately (pure Kotlin, ≤ 100 ms, P-08) | Then (engine, authoritative) |
| --- | --- | --- |
| Reserve toggle (5.6) | `LocalCost.reserve` → `CostCalculator.recompute(units, crew, reserveOn, budget)` → `CostApply` (numbers only; formula text stays the engine's) | `patch_cost {reserveOn}` → the whole trip is replaced |
| Hotel choice (5.7) | `LocalCost.hotel` (`hotelByStop`) → `CostApply` sets `selectedHotelId`, the stop cost and tags | `patch_cost {hotelChoice}`. The engine bakes the choice into `cost.units`, so the next local edit needs only its own override |
| Replace stop (5.5, D-6) | As built: **only the total** (`LocalCost.replace`, `replaced[stopId] = alt.units`, A§16.11.4 rules 1–5). The day's rows change when the engine answers. `TripEditor.applyAlternative` (the `dayPatch` applied locally) is not built | `replace_stop` → the new trip, with new alternatives for that day |
| Save / share | `TripStore.save`; share text from the current engine result | Every `plan`/`replace_stop`/`patch_cost` result carries its `shareText` |

As built, if the engine call fails, the **previous** trip is restored (not the local result) and the toast `waybill_sync_failed` is shown.

---

## 7. Navigation

These are type-safe routes, as in A§11.3, minus the map picker:

```kotlin
@Serializable data object WindshieldRoute
@Serializable data class NavigatorRoute(val focus: Field = Field.TO)
@Serializable data class InstrumentsRoute(val readyRouteId: String? = null)
@Serializable data object DriveRoute                       // PlanRequest held in PlanSession (in-memory singleton)
@Serializable data class RoadRoute(val tripId: String)      // "last" or a saved id
@Serializable data class WaybillRoute(val tripId: String)
@Serializable data class ExitRoute(val tripId: String, val stopId: String)
@Serializable data object DebugRoute                        // long-press 2 s on the build line of the settings sheet
```

Edges:

- Windshield → Navigator | Instruments(readyRouteId) | Road (saved trip from the «Мои поездки» sheet D-1).
- Navigator → Instruments.
- Instruments → Drive.
- Drive → Road with `popUpTo<DriveRoute> { inclusive = true }`.
- Road → Waybill | Exit | external.
- Exit → MockPartnerSheet → «Забронировали?».

System back equals the back link everywhere (G-07). Transitions follow motion.md §3, and are cuts under reduced motion.

---

## 8. Presentation

### 8.1 State management

This follows A§11.4 verbatim, except that ViewModels come from `viewModel { XViewModel(container.…) }` (lifecycle `viewModelFactory`/`initializer`) instead of Hilt.

- Pure reducers are unit-tested on the JVM.
- `PlanDraftStore` holds origin/destination/vias/readyRouteId between Navigator → Instruments → Drive.
- Defaults are written to DataStore on change (I-19).

### 8.2 Screens → design files → states → screenshot names

Screenshots are `screenshots/<screen>/<state>@<w>x<h>[-fs130].png`. They are rendered by Robolectric at density 3.0 (xxhdpi) under `@Config(qualifiers = "w<w>dp-h<h>dp-port-xxhdpi")`, with a frozen scene clock (§10.4). Default size 390 × 844; every `default` state is also captured at 360 × 640, at 480 × 900 and with font scale 1.3.

| Screen | Design | Package | States (screenshot `<state>`) | Data |
| --- | --- | --- | --- | --- |
| 5.1 Windshield | `screens/5.1-windshield.md`, `states/5.1-*`, D-1 | `feature.windshield`, `feature.trips` | `default`, `row2-selected`, `loading`, `offline-cached`, `offline-empty`, `no-routes`, `error`, `engine-starting`, `engine-failed`, `trips-plate`, `full-list-sheet`, `trips-sheet` | `ready_routes` for the origin; saved headers |
| 5.2 Navigator | `screens/5.2-navigator.md`, `states/5.2-*` | `feature.navigator` | `default-query-yaro`, `no-destination`, `destination-picked`, `no-results`, `outside-russia`, `too-short`, `unreachable`, `vias-3`, `map-unavailable-plate`, `popular-chips` | `suggest`, `popular`, `estimate_points` (row km «≈ N км»), `estimate` (caption km, `TOO_SHORT`/`UNREACHABLE` before planning) |
| 5.3 Instruments | `screens/5.3-instruments.md`, D-4 | `feature.instruments` | `default`, `crew-full`, `km-150`, `km-900`, `budget-any`, `mood-calm`, `third-row`, `settings-sheet` | `mobile.estimate` of the draft, 300 ms after it settles: the only km/days source, equal to the later plan (DEV-SLICE-2 P0). The straight line and its × 1.25 (A§11.11) are not used anywhere any more. A stale figure for the same road is shown while a new estimate runs; another road shows nothing |
| 5.4 Drive | `screens/5.4-drive.md`, `states/5.4-*` | `feature.drive` | `t1500` (2 steps, 2 signs), `t4000`, `done`, `slow`, `no-lodging`, `error-unreachable`, `error-too-short`, `error-invalid`, `error-internal`, `offline` | `plan` events, paced by §8.3 |
| 5.5 Road ahead | `screens/5.5-road-ahead.md`, `states/5.5-*`, D-5, D-6, D-7, D-11 | `feature.road` | `g02-top`, `g02-day2`, `no-lodging-over-budget` (G05), `offline`, `stop-menu`, `replace-sheet`, `replace-none-note`, `report-sheet`, `saved-toast`, `limit-45`, `booked-row` | stored trip |
| 5.6 Waybill | `screens/5.6-waybill.md`, `states/5.6-*`, D-9 | `feature.waybill` | `reference` (canvas fixture: 3 720 / 0 / 12 000 / 9 000 / 3 000 / 2 770 / ≈ 30 500, P-15), `g02`, `reserve-off`, `line-expanded`, `over-budget`, `no-budget`, `stamp-final`, `pro-sheet`, `pro-joined` | stored trip + `CostCalculator` |
| 5.7 Exit | `screens/5.7-exit.md`, `states/5.7-*`, D-10 | `feature.exit` | `default`, `three-options`, `no-lodging`, `offline`, `mock-partner-sheet`, `booked-dialog`, `booked` | stored trip; hotel options with `exitDistanceM` for the exit sign («800 м», «ночёвка» when 0); `townPrepRu` for «в Ярославле» |

Screenshot data comes from the golden snapshots, which the Robolectric tests read as resources from `backend/planner/tests/golden/snapshots`. The screens therefore show real engine output. Two hand-built fixtures match the canvases exactly: `WaybillUiState.reference()` and `WindshieldUiState.mockup()`.

### 8.3 Drive pacing

The engine finishes in ~0.2–0.6 s, but the Drive screen follows the 5.4 §6 timeline. `DrivePacer` is a pure function of `(events received, elapsed ms)` → visible steps/signs/progress, so it is unit-tested and screenshot-frozen. Its rules:

- The steps appear in the fixed order split → lodging → hours → fuel → cost, ≥ 400 ms apart.
- Each step is checked when a later key arrives.
- The bar never moves back.
- Flying signs come from `StopEvent`s: ≥ 1 200 ms apart, ≤ 3 in flight, at most the first 6 final stops plus the provisional overnights.
- `done` shows the CTA after the last step is visible.
- The CTA auto-advances after 1 000 ms, except with TalkBack on (OI-25).
- Debug `debug_slow_plan_s` holds `done` back, to show the Slow state at 20 s.

---

## 9. Mock-specific behaviour, offline and errors

| Topic | Behaviour |
| --- | --- |
| Network | Sprint 2: none. Sprint 3 (D8, ADR-0012 §7): `INTERNET` for Commons photos and Nominatim addresses only; a real `ConnectivityManager` connectivity, with the `debug_offline` override kept. Everything else works offline |
| Engine start | Windshield ready routes show the shimmer until `EngineStatus.Ready`. The cached list is shown at once if present (5.1 §4.3, ≤ 2 s; skeleton never < 300 ms). `Failed` → full-width plate `engine_failed_title` + `common_retry` (DES-104); retry restarts `EngineHost` |
| Engine errors in Drive | `UNREACHABLE`, `TOO_SHORT`, `INVALID_INPUT` → 5.4 §4.4 messages from copy-ru §10. `INTERNAL`/`TZDATA_MISSING`/`NO_WORLD` → `error_upstream` text with «Попробовать ещё раз» (the "server" is the engine). `CANCELLED` → silent back |
| Reachable errors on the phone | Edge world (debug panel), origin Тестовск: «Глухово» → `UNREACHABLE` (G09), «Ближний» → `TOO_SHORT` (G10), «Конечный» with the dog → `NO_LODGING` (G05), «Пустошь» with a 30 l tank → `FUEL_GAP` (G11), ready route «Тестовый марафон» calm → `DAY_OVER_BUDGET` (G12) |
| Booking / excursions | `MockPartnerSheet` with the fictional partner «Придорожная», the ДЕМО badge and «без оплаты». No real brand (OI-40; the ADR-0010 text «здесь откроется Яндекс Путешествия» is superseded). Closing the sheet → «Забронировали?» → `SavedTripDto.bookedHotels[stopId] = placeId` (one per night) |
| Navigator hand-off | Sprint 3, **ADR-0014** (supersedes the ADR-0010 table): the engine's `handoff` points and links; navigator → maps → web for a car, maps → web for a walk; `<queries>` for `ru.yandex.yandexnavi` and `ru.yandex.yandexmaps`. No 2GIS |
| Location | Sprint 3 (ADR-0012 §5, DEV-301): coarse permission first, fine on «Точнее». `geo_nearest` gives the origin town; when online, a Nominatim reverse gives the address. «ВЫ: <origin>» still opens Navigator with focus ОТКУДА |
| Debug panel (`feature.debug`) | Opened by a 2 s long-press on «НАВИГАТОР» on the Windshield (there is no D-4 settings sheet yet). Plain list, not part of visual QA: world, clock (system / golden), simulate offline, slow plan seconds, force engine error, engine timings, build/sha, «Сбросить данные». Parity mismatches are not shown yet (§5.2). Nothing is persisted |

---

## 10. Design system in code

### 10.1 Tokens

`design/DesignTokens.kt` is copied verbatim to `android/core-ui/src/main/kotlin/app/verst/core/ui/theme/DesignTokens.kt`. `DesignTokensInSyncTest` (`:core-ui` unit test) compares the bytes with `$verst.repoRoot/design/DesignTokens.kt` (G-01). `tools/sync_design.sh` (DEV-103) does the copy. The Designer changes only `design/tools/gen_tokens.py`.

### 10.2 Fonts: committed to the repo, fetched once by CI

- **Decision:** fonts are binary files **in the repo**, put there by `.github/workflows/fonts.yml`. That workflow is run by hand, fetches from `github.com/google/fonts` at a commit resolved and recorded at run time, and pushes branch `bot/fonts-<n>`. The Manager reviews `android/fonts.lock` and merges.
- **Alternative rejected:** downloading on every build. It adds a network dependency to every run, and the sandbox could never see or check the files.
- `tools/ci/fetch_fonts.py`:
  - prefers the static TTFs;
  - if only a variable font exists, cuts the static instance with `fontTools.varLib.instancer` and records `instancedAt` in the lock;
  - fails on any missing glyph of А–я Ё ё № ₽ ≈ « » — → · U+202F U+00A0 (G-03).
- Resource names are the ones `DesignTokens.kt` uses: `ibm_plex_sans_condensed_{regular,medium,semibold,bold}`, `ibm_plex_mono_semibold`, `marck_script_regular`.
- OFL texts go to `core-ui/src/main/assets/licenses/`.
- The sandbox verifies the lock (`sha256sum` vs `fonts.lock`) after `git fetch`.

### 10.3 Strings and icons (Designer generators, outputs committed)

- `design/tools/gen_strings.py` (DES-101) turns `design/copy-ru.md` into `core-ui/src/main/res/values/strings.xml` + `plurals.xml`. Keys are as in the deck, `{name}` → `%1$s`, apostrophes and quotes are escaped, and «ёлочки», U+202F and U+00A0 are kept literally.
- Engine-rendered text (reasons, stage texts, warnings, formulas, share) comes from the engine JSON. The app never duplicates it.
- `design/tools/gen_vectors.py` (DES-102) turns `design/icons/*.svg` (one nonzero path each) into `core-ui/src/main/res/drawable/ic_<name_with_underscores>.xml` VectorDrawables (24 dp, fill `#141416`, tinted at use; signs.md §3).

### 10.4 Scene and motion

- `WindshieldScene(spec: SceneSpec, clock: State<Long>)` draws components §9 in one Canvas with `drawWithCache`. It reads `clock.value` only inside `onDrawBehind` (motion.md §5), so a frame never recomposes. `RoadProjection` implements components §9.1 analytically and is unit-tested at the W-03 check points (±0.01 dp).
- `SceneClock` comes from `LocalSceneClock`. In production it is `rememberSceneClock(running)` with `running = resumed && !reducedMotion && !overlayOpen && !powerSave` (G-11, G-12, OI-31). Tests provide a fixed clock (`FixedSceneClock(1500)`), which is how screenshot states such as `t1500` are rendered.
- Reduced motion: `Settings.Global.ANIMATOR_DURATION_SCALE == 0f` or `PowerManager.isPowerSaveMode`, re-read on resume. Then the static frame is drawn at `phase = 0.35` (A§11.9).

---

## 11. Testing

| Layer | Where | Runs | What |
| --- | --- | --- | --- |
| Planner + bridge | `backend/planner/tests/**` incl. new `test_mobile.py`, `test_packaging.py` | sandbox + `planner.yml` | as Sprint 1, plus: zip import (the device importer's behaviour), bridge envelopes, listener, cancel, every function, both worlds |
| Contracts (Kotlin) | `:core-model` `src/test` | CI `:core-model:test` | `CostCalculatorContractTest`: all 39 cases of `backend/planner/tests/contract/cost_recompute_cases.json` (one test per case, `case_<name>`), exact on lines, subtotal, total, per person, remaining, overBudget, hintKeys and fuelFormulaKm, plus a 10 000-recompute perf check (< 5 ms each). **Engine bundles, one gzip file per golden case** (DEV-112, generator `backend/planner/tools/gen_mobile_contracts.py`, byte-identical on regeneration, read by `contract/Contracts.kt`): `docs/contracts/replace/<case>.json.gz` = `{"case", "before": <private trip>, "items": [{stopId, altId, afterDay, afterCost, afterKm}]}`, one item per alternative of every replaceable stop; and `docs/contracts/patch/<case>.json.gz` = `{"case", "before", "items": [{kind, patch, afterCost, afterInput, afterHotel}]}` (`reserve_off`, `budget_none`, `hotel_<stopId>`, …). Each covers 10 cases (G01–G08, G11, G12) with 129 replace + 25 patch items, ≈ 332 KB in total. `before` is stored once per case; the generator asserts that `before` plus an item rebuilds the engine's full output. `ContractFilesTest`: the bundles load, the counts match, ≤ 3 alternatives per stop. `LocalCostBundleTest`: for every item, the local `LocalCost` total and each line equal the engine's `afterCost`. `EngineJsonTest`: every golden snapshot decodes. Also in `docs/contracts/`, used by the Python tests: `share-text/G01…G08.json` (`{plan, text}`) and `plan-response.example.json`. Not built: `DtoContractTest` (re-encode without loss) and `TripEditorTest` (local `dayPatch` vs `afterDay`), because no local day editor exists (§6.3) |
| Unit (Android) | `:core-ui`, `:app` `src/test` (Robolectric, sdk 35, native graphics) | CI `testDebugUnitTest`/`testDemoUnitTest` | reducers, `DrivePacer`, `RoadProjection`, semantics (TalkBack strings exact, touch targets ≥ 44 dp via `assertTouchHeightIsAtLeast`), `DesignTokensInSyncTest`, `TokenLiteralsTest`, `PackageRulesTest`, FileTripStore round trip |
| Screenshots | `:core-ui` (components), `:app` (screens §8.2) | same task; PNG → `ci-logs` | about 90 PNGs per run |
| Emulator | `:app` `src/androidTest/app/verst/e2e` | CI job `e2e`, API 34 x86_64, 1170 × 2532 @ 480 dpi = 390 × 844 dp | `EngineParityTest` (§5.3); `EngineStartupTest` (status Ready, writes `timings.json`); `SliceJourneyTest` (planned as `MockJourneyTest`, below; it also writes `budgets.json`) |

`SliceJourneyTest` (planned name `MockJourneyTest`) runs on the real engine with the golden clock. Step 8 (kill and relaunch) is not covered yet; review P1-2. Each step is screenshotted to `files/e2e/screens/NN-name.png`:

1. Windshield shows 3 ready routes. Pick «Золотое кольцо».
2. Instruments: add a child and the dog. ПОЕХАЛИ.
3. Drive reaches done and auto-advances.
4. Road ahead: 3 days.
5. Replace the first replaceable stop; the alternative appears and the total changes.
6. Waybill: toggle reserve; the total is recomputed and equals the engine's.
7. Exit: pick the 2nd hotel, book in the mock sheet, answer «Да».
8. Save. Kill and relaunch the activity.
9. «Мои поездки» shows 1 trip; open it; the booked state is kept.
10. Navigator: «Каз» → Казань, Москва → Казань, plan. `NO_LODGING` is absent and the result has 2+ days.
11. Edge world (debug panel), Тестовск → «Глухово»: the `UNREACHABLE` message.

---

## 12. CI/CD (`.github/workflows/android.yml`)

### 12.1 Jobs

| Job | Runs when | Steps | Time (warm / cold) |
| --- | --- | --- | --- |
| `build` | push to main and PRs (path filter), `workflow_dispatch` | toolchain probe → `:app:assembleDemo :app:assembleDemoAndroidTest` → `:core-model:test :core-ui:testDebugUnitTest :app:testDemoUnitTest` (screenshots inside) → `:app:lintDemo :core-ui:lintDebug` → APK budget → upload `apks` → diagnostics → upload `diag-build` | 7 / 18 min |
| `e2e` | `build` green (dispatch input `run_e2e`) | KVM, cached AVD (API 34 google_apis x86_64), `tools/ci/run_e2e.sh` (install, `am start -W` cold start, `am instrument -e package app.verst.e2e`, pull `files/e2e`, logcat) → diagnostics → `diag-e2e` | 10 / 15 min |
| `release` | main, push or dispatch `release`, and `e2e` green (or dispatch `force_release`) | pre-release **`mvp-mock-<run_number>`** with `verst-mvp-mock-<n>.apk` + `.sha256` + Russian notes; then recreate **`mvp-mock-latest`** with `verst-mock-latest.apk`; prune to the 10 newest numbered | 1 min |
| `ci-logs` | always | merge `diag-*` artifacts → `tools/ci/combine_run.py` → `tools/ci/publish_ci_logs.sh` | 1 min |

- Caching: `gradle/actions/setup-gradle` (Gradle user home, dependencies, Robolectric android-all jars, Chaquopy's Maven artifacts; read-only off main) and `actions/cache` for the AVD.
- Concurrency: one run per ref, and a newer push cancels the older run (saves billed minutes).
- The CEO's stable link is `https://github.com/pazzia/Verst/releases/download/mvp-mock-latest/verst-mock-latest.apk`. The repo is private, so it needs the CEO logged in to GitHub in the phone browser.

### 12.2 Diagnosability without job logs

These checks were made from this sandbox on 2026-10-24:

- jobs/steps API: **readable**;
- check-run annotations API: **readable** (it returned the billing error);
- job logs: **blocked** (blob storage 403);
- releases API: readable.

So:

1. **Annotations.** `tools/ci/diagnose.py` prints `::error file=<repo-relative>,line=,col=,title=::msg` for:
   - Kotlin `e: file:///…kt:L:C`, javac errors and AAPT/resource errors;
   - Gradle `* What went wrong:` blocks (plugin/dependency resolution);
   - failing tests (file and line from the stack);
   - Android Lint errors;
   - emulator test failures, Python tracebacks and `FATAL EXCEPTION` from logcat;
   - the APK budget.

   Each diagnose step stays within GitHub's limit of 10 error annotations per step. Read them with:
   ```
   gh api repos/pazzia/Verst/actions/runs --jq '.workflow_runs[] | select(.name=="android") | {id,conclusion,head_sha}' | head
   gh api repos/pazzia/Verst/actions/runs/<run>/jobs --jq '.jobs[] | {name,conclusion,id,steps:[.steps[]|{name,conclusion}]}'
   gh api repos/pazzia/Verst/check-runs/<job id>/annotations
   ```
2. **Branch `ci-logs`.** It is a single orphan commit, force-pushed with a lease, with retention of 30 runs and PNGs for the newest 3:
   ```
   README.md  index.json  LATEST
   runs/<run_id>-<attempt>/
     summary.json  summary.md  errors.txt                  # whole run (combine_run.py)
     build/  summary.json summary.md errors.txt apk.json logs/<step>.log.txt (trimmed: error lines ±3 + last 400)
             raw-logs/<step>.log.gz  tests/failures.txt  lint/lint-errors.txt  test-reports.tgz
     screenshots/<screen>/<state>@<w>x<h>[-fs130].png
     e2e/    summary.* instrument.txt instrument-failures.txt tracebacks.txt logcat-filtered.txt logcat-full.txt.gz
             am-start.txt (TotalTime = cold start) timings.json parity.json screens/NN-*.png
     release/ notes.md release.json create.log
   ```
   Read it from the sandbox with:
   ```
   git fetch origin +ci-logs:refs/remotes/origin/ci-logs --depth=1
   R=$(git show origin/ci-logs:LATEST); git show origin/ci-logs:runs/$R/summary.md
   mkdir -p /tmp/ci && git archive origin/ci-logs runs/$R | tar -x -C /tmp/ci    # PNGs for Designer QA
   ```
3. **Drill.** DEV-102 plants a Kotlin error, a failing test and a Python exception on branch `ci-drill`. All three must be found from the sandbox by the commands above.

### 12.3 Planner workflow

`planner.yml` stays. DEV-100 pins its runner to `ubuntu-24.04`. Its path filter already covers `mobile.py`.

---

## 13. Budgets

| Budget | Target | Hard limit | Measured where |
| --- | --- | --- | --- |
| APK (demo, arm64-v8a + x86_64) | ≤ 45 MB | 60 MB (build fails) | `diagnose.py apk` → `build/apk.json` (largest entries listed) |
| Activity cold start to first frame (emulator) | ≤ 1.5 s | 3 s | `e2e/am-start.txt` `TotalTime` |
| Engine ready (emulator, first launch after install) | ≤ 4 s | 8 s | `e2e/timings.json` `totalMs` |
| Engine ready (CEO phone) | ≤ 3 s typical | — | debug panel, reported by the CEO |
| Plan G02 (emulator) | ≤ 1.0 s | 3 s | `parity.json` ms |
| Reserve toggle recompute | ≤ 5 ms in a JVM unit test | 100 ms (P-08) | `CostCalculatorPerfTest` |
| Scene frames | 0 recompositions per frame | — | Robolectric `RecompositionCounterTest` on WindshieldScene over 60 frames. Macrobenchmark (G-13) is out of scope for the mock build and stays in the A§11 plan |

---

## 14. Path to the server-backed build

Nothing in `feature.*`, `:core-ui` or `:core-model` changes. The server-backed build will:

- add `HttpPlannerGateway` (Retrofit/OkHttp/SSE, A§11.7) implementing `PlannerGateway`;
- add `RoomTripStore` implementing `TripStore`, with a one-time import of `filesDir/trips/**`;
- remove the Chaquopy plugin, `app.verst.engine` and the assets source sets;
- bring back Hilt by turning `AppContainer` fields into `@Provides`.

The 3 → 11 module split is a folder move, guarded by `PackageRulesTest`.

---

## 15. Sprint 3 (ADR-0011…0014, `docs/backlog-sprint3.md`)

### 15.1 What changes, by layer

| Layer | Change | ADR |
| --- | --- | --- |
| Engine `pipeline/budget_fit.py` | Stage 12b ladder (`FitKnobs`); no-fit outcome with verified options; `breaksBudget`; explicit `rooms` in cost units (shared contract) | 0011 |
| Engine `adapters/catalogue/` | `russia_v1`: catalogue towns/POIs/bars, synthetic fictional hotels/cafes/fuel/rest, `HybridRouting` (fixture graph or calibrated synthetic), nearest-town regions, `places_near` | 0012 |
| Engine `verst_planner/city/` | Walking orienteering solver, presets, gates, `WalkRoute` | 0013 |
| Engine `mobile.py` | API v2 (§5.4), handoff links, POI details | 0011–0014 |
| Data `tools/data/`, `.github/workflows/data.yml` | Wikidata/OSM/Commons fetch in CI → `bot/data-<n>` → `verst_planner/resources/catalogue/*.json.gz` (≤ 2.5 MB) | 0012 |
| `:app` `data.net` | OkHttp 4.12.0 (UA interceptor), Coil 2.7.0 (64 MB disk cache), `NetworkConnectivity`, `NominatimClient` (explicit submit, ≤ 1 req/s, 24 h cache) | 0012 |
| `:app` `data.location` | `LocationManager` single fix, permission flow | 0012 |
| `:app` features | `feature.card` (POI and hotel cards, `PhotoFrame`), `feature.budget` (no-fit screen), `feature.city` («По городу», walk result), hand-off menus on Road ahead, `HandoffLauncher` | 0011–0014 |
| `:core-model` | DTOs: `BudgetFitDto`, `NoFitDto`, `WalkRouteDto`, `PoiDetailsDto`, `HandoffDto`, `GeoHitDto`; `CostCalculator` explicit rooms; `SavedTripDto` schema 2 (`kind`) | 0011, 0013 |
| Manifest | `INTERNET`, `ACCESS_NETWORK_STATE`, `ACCESS_COARSE_LOCATION`, `ACCESS_FINE_LOCATION`; `<queries>` for `ru.yandex.yandexnavi` and `ru.yandex.yandexmaps` | 0012, 0014 |
| Tests | Deny-list with the `handoff_*` allow-list; the catalogue scanned; journeys S3-1…S3-6; contract files v2 | all |

### 15.2 Catalogue in the app process

The catalogue ships inside the Python package (`verst_planner/resources/catalogue/`), so `stagePlannerSources` carries it and there is no Kotlin asset code. Python reads it through the zip-safe resource loader at boot:

- decompression and parsing take about 300–600 ms on a mid-range phone, recorded as `catalogueMs`;
- the spatial grid is built lazily;
- memory is about +25 MB of Python objects. That is acceptable next to CPython; the column arrays are kept, not row objects.

Engine-ready budget: ≤ 5 s on the emulator (was 4 s).

### 15.3 Network use (the only two)

| Use | Endpoint | Rules |
| --- | --- | --- |
| Photos | `commons.wikimedia.org/wiki/Special:FilePath/<file>?width=800\|400` → redirect to `upload.wikimedia.org` | Coil with the UA, cached 64 MB; the placeholder when offline or failed; attribution line |
| Addresses | `nominatim.openstreetmap.org/search`, `/reverse` | Explicit submit only (the Nominatim policy forbids autocomplete), ≤ 1 req/s, `countrycodes=ru`, `accept-language=ru`, UA, «© OpenStreetMap», 24 h cache. CI tests use MockWebServer, never the real service |

### 15.4 Road ahead focus (requirement 2.1)

- `VerstFlow.focusStopId` is set when a card, the Exit/booking flow or a hand-off is opened from a row.
- Road ahead keeps a `LazyListState`/`ScrollState` per trip session in `VerstFlow` and restores it on return (`bringIntoView` of the row + TalkBack focus).
- `focusStopId` is written to `last.json` with the trip, so it survives process death.

### 15.5 Tappable rows (requirement 2)

| Row kind | Tappable | Opens |
| --- | --- | --- |
| `sight` | yes | POI card |
| `overnight` with a hotel | yes | Hotel card (area photo) + «Выбрать отель» as before |
| `food` | no | — (unchanged) |
| `fuel`, `rest`, `start`, `finish`, `via` | no | No click semantics |
| Walk stops (sights, museums, bars) | yes | POI or bar card |

