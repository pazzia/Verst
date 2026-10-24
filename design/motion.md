# Verst — Motion specification

Version 1.1.0 · 2026-10-24 (§2.3 added) · Tokens: `motion.*` in `tokens.json` / `DesignTokens.motion`

## 1. Easing tokens

| Token | cubic-bezier | Compose | Source |
| --- | --- | --- | --- |
| `easing.linear` | (0, 0, 1, 1) | `LinearEasing` | CSS `linear` |
| `easing.standard` | (0.25, 0.1, 0.25, 1) | `CubicBezierEasing(0.25f, 0.1f, 0.25f, 1f)` | CSS `ease` (default for the mockups' `transition`) |
| `easing.easeOut` | (0, 0, 0.58, 1) | `CubicBezierEasing(0f, 0f, 0.58f, 1f)` | CSS `ease-out`. **Not** `LinearOutSlowInEasing` (0, 0, 0.2, 1) |
| `easing.easeInOut` | (0.42, 0, 0.58, 1) | `CubicBezierEasing(0.42f, 0f, 0.58f, 1f)` | CSS `ease-in-out`. **Not** `FastOutSlowInEasing` (0.4, 0, 0.2, 1) |
| `easing.postIn` | (0.55, 0, 1, 0.45) | `CubicBezierEasing(0.55f, 0f, 1f, 0.45f)` | Windshield posts |
| `easing.rushIn` | (0.6, 0, 1, 0.5) | `CubicBezierEasing(0.6f, 0f, 1f, 0.5f)` | Drive posts, flying signs |
| `easing.overshoot` | (0.3, 1.4, 0.5, 1) | `CubicBezierEasing(0.3f, 1.4f, 0.5f, 1f)` | Stamp |
| `easing.decelerate` | (0.2, 0.8, 0.3, 1) | `CubicBezierEasing(0.2f, 0.8f, 0.3f, 1f)` | Waybill sheet, exit sign; reused for entries |
| `easing.accelerate` | (0.4, 0, 1, 1) | `CubicBezierEasing(0.4f, 0f, 1f, 1f)` | NEW: exits (sheet out) |

CSS keyframe rule, important for parity: a `animation-timing-function` applies **per keyframe segment**. Compose `keyframes { value at t using easing }` applies the easing to the segment that starts at that keyframe, which is the same behaviour. Always attach the easing to every keyframe.

## 2. Animation catalogue

Columns: property, from → to, duration, easing, loop, Compose implementation, reduced-motion static frame. "Clock" = the shared scene clock (§5).

### 2.1 Continuous loops

| Token | Screen | Property | From → to | Duration | Easing | Loop | Compose | Reduced motion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `lane.idle` | 5.1 | dash phase (road plane units) | 0 → 160 dp | 900 ms | linear | restart, ∞ | clock: `phase = (t % 900) / 900 * 160` | phase 0 |
| `lane.navi` | 5.2 | dash phase | 0 → 160 | 1400 ms | linear | ∞ | clock | phase 0 |
| `lane.drive` | 5.4 | dash phase | 0 → 160 | 450 ms | linear | ∞ | clock; period ramps (§3) | phase 0 |
| `lane.exit` | 5.7 | dash phase | 0 → 160 | 1600 ms | linear | ∞ | clock | phase 0 |
| `lane.itinerary` | 5.5 | dash offset (flat) | 0 → 64 dp | 2200 ms | linear | ∞ | clock | 0 |
| `post.idle` | 5.1 | translate, scale (about centre), alpha | (0,0) s 0.3 α 0 → (±150, 260) s 2.2; α 0 → 1 over 0–10 % | 2600 ms; left post offset 1300 ms | translate/scale: `postIn` over 0–100 %; alpha: `postIn` over 0–10 %, then held 1 | ∞ | clock: `p = ((t + offset) % 2600) / 2600`; `e = postIn.transform(p)` | hidden |
| `post.drive` | 5.4 | as above | (0,0) s 0.2 → (±170, 230) s 2.4 | 1100 ms; offset 550 | `rushIn` | ∞ | clock | hidden |
| `flyingSign` | 5.4 | translate (centre), scale, alpha | centre (195, 250) s 0.12 α 0 → (+230 or −230, +40) s 1.7; α 0 → 1 over 0–15 % | 3600 ms per sign; ≥ 1200 ms between spawns | `rushIn` | per sign once (repeats only for the demo fixture) | per-sign `Animatable` launched on the `stop` event | latest sign static at spawn point, scale 1 |
| `startPulse` | 5.1–5.3 | ring spread, alpha | spread 0 → 16 dp (14 on S), α 0.55 → 0 | 1800 ms | `easeOut` | restart ∞ | `rememberInfiniteTransition().animateFloat(0f, 1f, infiniteRepeatable(tween(1800, easing = easeOut)))` drives spread + alpha | none |
| `mirrorSway` | 5.1 | rotationZ about the stem top | −1.5° → +1.5° → −1.5° | 4000 ms (2000 each way) | `easeInOut` per half | ∞ | `infiniteRepeatable(tween(2000, easing = easeInOut), RepeatMode.Reverse)` from −1.5f to 1.5f | 0° |
| `dogWag` | 5.3 | rotationZ about the body bottom centre | −6° ↔ +6° | 1200 ms (600 each way) | `easeInOut` | ∞ while dog = on | as sway, `tween(600)` | 0° |
| `twinkle` | 5.7 | star alpha | 0.3 → 1 → 0.3 | 2400 ms; delays 0 / 800 / 1600 | `easeInOut` per half | ∞ | `tween(1200)` Reverse, `StartOffset(delay)` | α 1 |
| `turnSignal` | 5.7 | alpha | 1 for 0–495 ms, 0.15 for 495–900 ms | 900 ms | step (CSS `steps(1)`) | ∞ | clock: `alpha = if (t % 900 < 495) 1f else 0.15f` | α 1 |
| `carMarker` | 5.5 | y within the visible road | viewport top → bottom | `visibleRoadHeight / 124 dp/s` | linear | restart ∞ | clock | at the top |
| `caret` | 5.2 | cursor alpha | 1 / 0 | 1000 ms (500 / 500) | step | ∞ | native `BasicTextField` cursor (`cursorBrush = SolidColor(accent.yellow)`), which blinks 500 / 500 | steady (Compose cursor obeys the animator scale) |
| `shimmer` | loading | highlight band x | −90 dp → bounds width | 1200 ms | linear | ∞ | `infiniteRepeatable(tween(1200, easing = LinearEasing))` + `drawWithCache` gradient brush | flat base fill |
| Navigator "no routes" border pulse | 5.1 §4.7 | border alpha | 1 → 0.4 → 1 | 2 × 1200 ms | `easeInOut` | 2 times, then solid | `repeatable(2, tween(600), Reverse)` ×2 | solid |
| Start loading arc | components §7 | arc start angle | 0 → 360° | 900 ms | linear | ∞ while loading | infinite transition | static 90° arc at 0° |
| Book CTA spinner | 5.7 | arc start angle | 0 → 360° | 900 ms | linear | ∞ while loading | infinite transition | static arc |

### 2.2 One-shot animations

| Token | Where | Property | From → to | Duration / delay | Easing | Compose | Reduced motion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `selection` | sign rows, seats, chips, suggestions, hotel options, chevron | background, content colour, border colour, chevron rotation | state A → B | 200 ms | `standard` | `animateColorAsState(target, tween(200, easing = standard))` | instant |
| `startPress` | start buttons | face + label scale | 1 → 0.96 → 1 | 120 ms down, 120 ms up | `standard` | `animateFloatAsState` on `isPressed` | none (state colour only) |
| Key / seat / chip press | keys, seats, chips | translationY | 0 → 1 dp | immediate (0 ms) | — | `graphicsLayer { translationY = if (pressed) 1.dp.toPx() else 0f }` | same (not motion) |
| `odometerRoll` | odometer drums | digit translationY | old 0 → ∓34 dp, new ±34 → 0 | 300 ms | `decelerate` | `AnimatedContent` with `slideInVertically/slideOutVertically(tween(300, easing = decelerate))` | instant swap |
| `needle` | fuel gauge | rotation | current → −90 + 36·i ° | spring: stiffness 300, damping ratio 0.6 (settles in ≈ 520 ms) | spring | `animateFloatAsState(angle, spring(dampingRatio = 0.6f, stiffness = 300f))` | snap |
| `stepAppear` | Drive step lines | alpha, translationX | 0, −6 dp → 1, 0 | 350 ms; lines ≥ 400 ms apart | `easeOut` | `AnimatedVisibility(fadeIn(tween(350, easing = easeOut)) + slideInHorizontally { -6.dp })` | instant |
| `progress` | Drive bar | width fraction | previous → stage / 5 | 400 ms | `easeInOut` | `animateFloatAsState` | instant |
| `ctaAppear` | Drive CTA | alpha, translationX | 0, −6 → 1, 0 | 350 ms; auto-advance 1000 ms after it ends | `easeOut` | as `stepAppear` | instant; auto-advance kept |
| `stamp` | Waybill | scale, alpha (rotation fixed −14°) | keyframes: 0 ms s 2.4 α 0 → 300 ms s 0.92 α 0.9 → 500 ms s 1.0 α 0.85 | 500 ms, delay 1000 ms | `overshoot` on each segment | `keyframes { durationMillis = 500; 2.4f at 0 using overshoot; 0.92f at 300 using overshoot; 1f at 500 }` + same for alpha; `delayMillis = 1000` | final frame |
| `sheetSlide` | Waybill sheet entry | translationY, alpha | 40 dp, 0 → 0, 1 | 600 ms | `decelerate` | `Animatable` on first composition | at rest |
| `exitNear` | Exit sign entry | scale, translation, alpha (pivot 30 % / 100 %) | s 0.7, (−21, −14) dp, α 0.6 → s 1, (0, 0), α 1 | 2200 ms | `decelerate` | `Animatable` + `graphicsLayer { transformOrigin = TransformOrigin(0.3f, 1f) }` | final frame |
| `bottomSheetIn` | sheets, line expand | sheet translationY, scrim alpha; expand height | 100 % → 0; 0 → 0.6 | 300 ms | `decelerate` | `AnimatedVisibility(slideInVertically { it } + fadeIn)` for the sheet, `animateContentSize(tween(300, easing = decelerate))` for expand | instant |
| `bottomSheetOut` | sheets, line collapse | reverse | | 200 ms | `accelerate` | | instant |
| Row flash after replace | Road ahead | row background | `dash.pressed` → transparent | 1200 ms | `easeOut` | `animateColorAsState` | none |
| Seat/value cross-fade | Waybill handwritten values | alpha | old → new | 200 ms | `standard` | `Crossfade(tween(200))` | instant |
| Toast in / out | `PlateToast` | alpha, translationY | 0, 8 dp → 1, 0 | 200 ms in / 150 ms out | `decelerate` / `accelerate` | `AnimatedVisibility` | instant |

### 2.3 Tokens added in the slice-2 review (2026-10-24)

These one-shots were described in the screen files but had no token. They are now in `tokens.json` / `DesignTokens.motion`, so the Developer writes no literal (TokenLiteralsTest).

| Token | Where | Property | From → to | Duration | Easing | Compose | Reduced motion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `toastIn` / `toastOut` | `PlateToast` (save, replace, delete, booked) | alpha, translationY | in: 0, 8 dp → 1, 0; out: reverse | 200 ms in, 150 ms out; visible `showMs` 3000, `showWithActionMs` 6000 | `decelerate` / `accelerate` | `AnimatedVisibility(fadeIn(tween(200, easing = decelerate)) + slideInVertically { 8.dp }, …)`; the timer pauses while TalkBack focus is on the toast | instant; durations unchanged |
| `dialogIn` / `dialogOut` | `NaviDialog` («Забронировали?», delete trip, 50-trip limit) | scrim alpha 0 → `scrimAlpha` 0.6; card scale 0.96 → 1 and alpha 0 → 1 (pivot centre) | | 200 ms in, 150 ms out | `decelerate` / `accelerate` | `AnimatedVisibility` with `scaleIn(initialScale = 0.96f) + fadeIn` | instant |
| `captionFade` | 5.2 caption + start row while the IME is open | alpha | 1 ↔ 0 | 150 ms | `standard` | `AnimatedVisibility(fadeIn/fadeOut(tween(150)))`; layout height kept until the fade ends | instant |
| `laneSlowDown` | 5.4 error / offline | lane period | 450 → 900 ms | 800 ms | `decelerate` | interpolate the **period**, keep the phase continuous (as `screen.launch` ramp, reversed) | phase 0 |
| `rowFlash` | 5.5 row after replace | row background | `color.dash.pressed` → transparent | 1200 ms | `easeOut` | `animateColorAsState` started once per replace | none |
| `valueCrossfade` | 5.6 handwritten values, 5.5 footer amount after replace / reserve | alpha | old → new | 200 ms | `standard` | `Crossfade(tween(200))` | instant |
| `fieldPulse` | 5.1 no-routes navi field border | border alpha | 1 → 0.4 → 1, twice (`totalMs` 2400), then solid | 1200 ms per cycle | `easeInOut` | `repeatable(4, tween(600, easing = easeInOut), RepeatMode.Reverse)` on first display only | solid |
| `spinner` | 5.7 Book CTA (production), components §7 start loading | arc start angle, 270° sweep (`sweepDeg`) | 0 → 360° | 900 ms | `linear` | `rememberInfiniteTransition` | static arc at 0° |
| `loadingDots` | `SwapButton` loading (components §2.6) | 3 dots 4 dp (`dotDp`), alpha 1 for one 300 ms step each | dot 1 → 2 → 3 | 900 ms cycle, `stepMs` 300 | step | clock: `active = (t / 300) % 3` | three dots at alpha 1 |
| `rowRemove` | D-1 row after «Удалить» | height → 0, alpha → 0 | | 250 ms | `accelerate` | `AnimatedVisibility(shrinkVertically + fadeOut)`; «Вернуть» re-inserts with `bottomSheetIn` timing | instant |

Exit screen order (5.7 §6, unchanged): `screen.overlay` cross-fade + `exitNear` from t = 0; `MockPartnerSheet` = `bottomSheetIn` / `bottomSheetOut`; then «Забронировали?» = `dialogIn`. While the sheet or dialog is open, the Exit loops (lanes, twinkle, turn signal) pause (§4.3) and resume in phase.

Mockup-only: Panel.dc.html animates the needle with `transition: transform .5s cubic-bezier(.3,1.5,.5,1)`. SPEC 6 sets a spring (stiffness 300, damping 0.6) for the app. The spring wins; QA compares the settle time (500 ± 50 ms) and the overshoot (≤ 10°), not the curve.

## 3. Screen transitions (NEW — the mockups have none)

All forward transitions run in a single `AnimatedContent`/`NavHost` with the specs below. Back runs the reverse with `motion.screen.back` (300 ms `decelerate`) unless stated. Predictive back (Android 14+): the reverse transition is scrubbed by the back-gesture progress (`PredictiveBackHandler`); on cancel it springs back (`spring(stiffness = 400f)`).

| Token | From → to | Choreography | Duration / easing |
| --- | --- | --- | --- |
| `screen.zoomToNavi` | 5.1 → 5.2 | "Lean to the navigator": shared bounds — the Windshield navi panel (18, 542, 354 × 134) morphs into the Navigator panel (14, 188, 362 × 516); the dashboard top moves 520 → 132; the scene is clipped to the strip (its bands cross-fade to the strip bands over the first 50 %); the overhead sign, mirror and caption fade out over the first 150 ms; the КУДА field appears at 60 %, then gets focus and the IME at 100 % | 450 ms, `decelerate` (`SharedTransitionLayout` + `Modifier.sharedBounds`) |
| `screen.lookAtMirror` | 5.1 / 5.2 → 5.3 | "Look in the mirror": shared bounds — the small mirror (120, 18, 150 × 44) morphs into the large mirror (20, 54, 350 × 174); the stem 8 × 10 → 30 × 58; silhouettes cross-fade to seats; the rest cross-fades (out 0–150 ms, in 150–400 ms). From 5.2 there is no small mirror: the large mirror grows from the top centre (scale 0.43 → 1, pivot (0.5, 0)) | 400 ms, `decelerate` |
| `screen.launch` | 5.3 → 5.4 | Cross-fade 300 ms; the Drive lane period starts at 900 ms and reaches 450 ms by t = 800 (linear interpolation of the period, phase continuous) | 300 ms, `standard`; ramp 800 ms |
| `screen.arrive` | 5.4 → 5.5, 5.1 → 5.5 (saved trip) | "Pull over to the road": the Drive scene translates up by (560 − 132) and fades to the strip; the Road-ahead list enters from +40 dp with alpha 0 → 1 | 450 ms, `decelerate` |
| `screen.overlay` | 5.5 → 5.6, 5.5 → 5.7, 5.2 → map picker | Cross-fade 300 ms; then the destination's own entry animation (`sheetSlide` or `exitNear`) starts at t = 0 of the destination | 300 ms, `standard` |
| `screen.back` | any reverse | Reverse of the forward choreography | 300 ms, `decelerate` |

Reduced motion: transitions are instant cuts (no cross-fade), and shared-bounds morphs are disabled.

## 4. Loop and pause rules

1. **Lifecycle:** every continuous loop runs only while the screen's `Lifecycle` is at least `RESUMED`. On `onPause`, the clock stops and the phase is held, so the loop resumes from the same frame (no jump).
2. **Visibility:** a loop runs only while its composable is in the composition and on screen. Road ahead draws one road section for the whole scrolled `Column` (DEV-SLICE-2 deviation from `LazyColumn`, accepted): the lane and the car are drawn only for the **visible** y range (`clipRect` to the viewport from `ScrollState.value`), so off-screen dashes cost nothing and the phase stays global.
3. **Overlays:** when a bottom sheet or dialog covers the scene (scrim visible), the scene loops (lanes, posts, sway, twinkle, turn signal, start pulse) pause. Shimmer and spinners inside the overlay run.
4. **Reduced motion:** `LocalReducedMotion = true` when `Settings.Global.TRANSITION_ANIMATION_SCALE == 0f` or `ANIMATOR_DURATION_SCALE == 0f` (the "Remove animations" switch sets both). All loops stop and show the static frames in §2. One-shots jump to their final state. State colour changes remain (they are not motion).
5. **Power saver:** when `PowerManager.isPowerSaveMode` is true, the scene loops stop (static frames, as for reduced motion), while one-shots keep running. Proposed; OI-31 asks the Manager to confirm.
6. **TalkBack:** loops keep running (they are decorative) but Drive's auto-advance is disabled (5.4 §4.1).
7. **Drive streaming:** flying signs spawn only for received `stop` events; at most 3 signs are in flight; extra events queue. After `done`, no new signs spawn.

## 5. Implementation: one scene clock per screen

```kotlin
@Composable
fun rememberSceneClock(running: Boolean): State<Long> {
    val time = remember { mutableLongStateOf(0L) }
    LaunchedEffect(running) {
        if (!running) return@LaunchedEffect
        var last = withFrameMillis { it }
        while (true) {
            withFrameMillis { now -> time.longValue += (now - last); last = now }
        }
    }
    return time
}
// running = lifecycleResumed && !reducedMotion && !overlayOpen && !powerSave
```

The scene Canvas reads `clock.value` **inside the draw lambda only** (`drawWithCache { onDrawBehind { val t = clock.value; … } }`), so a frame invalidates the draw phase and never recomposes. All phases (dashes, posts, twinkle, turn signal, car) are pure functions of `t`, so they stay in sync and survive pause/resume.

## 6. Frame budget

| Item | Budget (Samsung Galaxy A34 class, 60 Hz) |
| --- | --- |
| Frame | 16.6 ms total; UI thread ≤ 8 ms; RenderThread ≤ 8 ms |
| Scene draw (Windshield, all layers) | ≤ 4 ms UI thread; ≤ 120 draw ops |
| Recompositions caused by loops | 0 per frame (checked with the Layout Inspector recomposition counts) |
| Allocations in draw lambdas | 0 (paths built in `drawWithCache`, reused with `Path.rewind()`; no `Brush` creation per frame) |
| Road ahead scroll | no frame > 32 ms (SPEC 16); target ≤ 16.6 ms at the 90th percentile |
| Drive | ≤ 3 flying signs + 2 posts + road: ≤ 6 ms UI thread |
| Overdraw | ≤ 3× anywhere on the scene (checked with "Debug GPU overdraw"); the root background is not drawn under the scene Canvas (the scene covers it) |
| Measurement | Macrobenchmark `FrameTimingMetric` per screen, 10 s idle + 10 s scroll; JankStats in beta builds |

High-refresh displays (90/120 Hz): loops are time-based, so speed is unchanged; the budget scales to 11.1 / 8.3 ms per frame, and on devices that miss it the app requests 60 Hz for the scene screens (`Window.setFrameRate(60f)` via `Surface.setFrameRate`, API 30+).

### 2.4 Sprint 3 tokens (5.8–5.13; ADR-0011…0014)

| Token | Where | Property | From → to | Duration | Easing | Compose | Reduced motion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `photoFadeIn` | `PhotoFrame` | image alpha over the mat | 0 → 1 | 250 ms | `standard` | `animateFloatAsState` on load success | instant |
| `returnToItem` | 5.5 / 5.11 after a card, Exit, booking or hand-off | scroll position + row background | jump (0 ms) to the saved offset; row background `color.overlay.returnFlash` (yellow 14 %) held `holdMs` 400, then → transparent over the remaining 800 ms (S3-QA: `dash.pressed` was invisible on `dash.raised`, contrast 1.05:1) | 0 + `highlightMs` 1200 | `easeOut` (fade part) | `LazyListState.scrollToItem(index, offset)` / `ScrollState.scrollTo(y)` + `animateColorAsState` | jump; the flash is shown static for 400 ms, then removed without a fade |
| `footsteps` | `WalkColumn` (5.11) | footprint pair y | 0 → `periodDp` 48 | 1800 ms | `linear` | scene clock, global phase | one pair at the top |
| `lamps` | `CityScene` | glow alpha | 0.7 ↔ 1 | 3200 ms (1600 each way), offsets 0 / 1100 / 2200 | `easeInOut` | clock | alpha 1 |
| `limitSignIn` | 5.8 no-fit screen | the round limit sign: scale 0.8 → 1, alpha 0 → 1 (pivot centre), with `screen.arrive` | | 400 ms | `decelerate` | `Animatable` on first composition | final frame |

Card sheet, day / stop hand-off menus and the custom-walk sheet: `bottomSheetIn` / `bottomSheetOut`; the 18+ dialog: `dialogIn` / `dialogOut`; hand-off and location toasts: `toastIn` / `toastOut`; walk building: `shimmer` on the caption + the start-button loading arc (`spinner`). Scene loops (lamps, footsteps) pause under sheets and dialogs (§4.3).
