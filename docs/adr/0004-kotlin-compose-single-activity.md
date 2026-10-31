# ADR-0004: Native Android in Kotlin + Jetpack Compose, single activity, MVVM/UDF, Hilt, multi-module

Status: Accepted · Date: 2026-10-23 · Refs: SPEC §5, §6, §11, §13, §16; architecture §11

## Context
Design v5 «За рулём» is a fully custom illustrated UI (Canvas windshield scene, road signs, odometer, fuel gauge) with strict motion specs, 60 fps on mid-range devices, Russian-only, offline saved trips, Android 8.0+, distributed via RuStore (many devices without Google Play Services).

## Decision
Kotlin 2.2 + Jetpack Compose, one `MainActivity`, type-safe Navigation Compose, one `@HiltViewModel` per screen exposing `StateFlow<UiState>` + intents + effects (UDF). Gradle modules `:app`, `:core-ui`, `:core-model` (pure JVM), `:data`, and one `:feature-*` per screen; features never depend on each other. Room for trips/caches, DataStore for defaults, Retrofit 3 + OkHttp 5 (+ okhttp-sse) + kotlinx.serialization. No Google Play Services dependencies. Versions pinned in `libs.versions.toml` and re-verified when network is enabled.

## Consequences
- Canvas drawing with `drawWithCache` gives full control over the scene and reduced-motion fallbacks.
- `:core-model` holds pure logic (cost recompute, schedule shift, share text) testable on the JVM and shared contract fixtures with Python.
- The whole Android track is BLOCKED-ON-NETWORK in the sandbox (Gradle plugins, Android SDK).
- Multi-module adds Gradle boilerplate; mitigated by a convention plugin in `android/build-logic`.

## Alternatives
- **Flutter / React Native** — cross-platform not needed (iOS out of scope); custom Canvas animation and accessibility are more native in Compose.
- **Views + XML** — slower to build custom components, worse fit for the declarative state model.
- **Multiple activities** — complicates shared plan session and transitions.
