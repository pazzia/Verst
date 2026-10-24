# DEV-SLICE visual QA — Designer review

Build: `main` = `ad7be27` (DEV-SLICE). Screenshots: `ci-logs` run `40083346786-1` (Robolectric 390 × 844 and 360 × 640, emulator e2e ≈ 390 × 640 dp). Method: `design/tools/qa_sample.py` against `design/qa/5.1…5.5.json`, column/row colour scans at density 3, and a visual read of every PNG against `design/screens/5.1–5.5`, `components.md` and the v5 canvases. Tolerances: `visual-qa-checklist.md` §0 (±4 dp layout, ±1 dp road check points, exact hex).

Priorities: **P0** broken (crash, unreadable, wrong data). **P1** noticeably off-spec (beyond tolerance, missing spec element, wrong colour). **P2** polish or scope cut to confirm.

Already logged and **not repeated** below: system fonts instead of Plex (DES-100; fonts now in this branch, see the end); km shown inconsistently (≈ 249 Navigator, ≈ 312 Instruments/Drive, 265 Road ahead). One more data point for that issue: «Золотое кольцо» is 745 on the Windshield sign and Instruments caption but **761** on the Road ahead title sign.

Not reviewed (slice scope, dev-notes item 4): Waybill, Exit, sheets, save/share, debug panel, all animation (lanes, pulse, posts, flying signs, shimmer, odometer roll, car marker), vias, map picker, TalkBack audit. Screenshots are static frames, so motion items (W-04/05/21 pulse, D-03/04, R-06 motion) are not judged.

## Summary

| Priority | Count | Status |
| --- | --- | --- |
| P0 | 1 | fixed in this branch (copy deck) |
| P1 | 22 | for the Developer (DEV-131) |
| P2 | 13 | 7 polish, 5 scope cuts to confirm, 1 tooling (fixed) |

Sampler: 5.1 13 failing points, 5.2 13, 5.3 16, 5.4 5, 5.5 7 (the rest of the points need states the slice does not render yet).

## P0 — broken

| ID | Screen | What is wrong | Expected | Status |
| --- | --- | --- | --- | --- |
| S-01 | 5.5 copy | `road_chip_days` generated as `%1$d %2$s · %3$d %4$d`. The 4th argument is the plural word «ночи», so `%4$d` throws `IllegalFormatConversionException` as soon as the key is used. The slice avoided it by building the chip by hand | `%1$d %2$s · %3$d %4$s`: day count, day word, night count, night word | **Fixed**: deck text is now `{d} {days} · {nights} {nights_word}`. `gen_strings.py` now fails when two integer placeholders are separated only by spaces, so this cannot come back. `strings.xml` regenerated. The Developer can now use `stringResource(R.string.road_chip_days, d, dayWord, n, nightWord)` |

## P1 — noticeably off-spec

### Global (every screen)

| ID | Screen | What is wrong | Expected value / token |
| --- | --- | --- | --- |
| S-02 | all (e2e) | The status bar is an opaque `#141416` / `#161618` band with **dark icons** (`#080809`). On the CEO's phone the clock and battery are invisible on the dark UI | Transparent status bar with light icons (`WindowInsetsControllerCompat.isAppearanceLightStatusBars = false`). The scene draws behind it, filled per components §0.2: `color.interior.liner` `#0E0E10` on Windshield and Drive, `color.sky.band1` `#2B2850` on Navigator, Instruments and Road ahead. Same for the navigation bar: light icons on `color.dash.raised` `#161618` |
| S-03 | 5.1, 5.2, 5.4, 5.5 | The dashboard crest is too low at the centre. The edges are right, so the curve is shallower than spec, probably a quadratic Bézier instead of the two elliptical arcs. Measured rim top at x 195: Windshield **532** (spec 518), Navigator **142.7** (130), Drive **552** (538), Road ahead cap **125** (110) | components §10 path `M0 (T+R) A(W/2) R 0 0 1 (W/2) T A(W/2) R 0 0 1 W (T+R)`. Use `Path.arcTo(Rect(0, T, W, T + 2R), 180°, 180°)`: an ellipse of half-width W/2 and half-height R, top at T. Rim = the same path at −2 dp. Check point W-16: `#232327` at (195, 519) |

### 5.1 Windshield

| ID | What is wrong | Expected value / token |
| --- | --- | --- |
| S-04 | The road projection is too narrow toward the horizon, and the edge lines have a constant width. Outer half-width is 72 at y 447.6 (spec 78.7) and 8.3 at y 300 (spec 20.5). Edge line is 3.3 dp everywhere (spec 6 dp at the near end, scaled by `s`). Drive has the same error (D-02: asphalt run x 125.7–264.3 at the first check row, spec from 117.0) | components §9.1 closed form, `s = P / (P + d·sinθ)`, `screenX = cx + x·s`, `screenY = top + (H − d·cosθ)·s`, with each element drawn as a quad of 4 projected corners: asphalt \|x\| ≤ W/2 − edge, edges W/2 − edge … W/2, lane \|x\| ≤ lane/2. Windshield P 210, θ 76°, W 230, edge 6, lane 8. Check points: half-width 115 @ 540, 78.7 @ 447.6, 53.4 @ 383.3, 30.5 @ 325.1, 20.5 @ 300 (±1 dp) |
| S-05 | Hills are smooth domes | Polyline from components §9 item 3: `M0 28 L40 18 L80 24 L130 12 L170 22 L200 16 L250 26 L300 14 L350 24 L390 18 L390 40 L0 40 Z`, translated to y 272, `color.sky.hills` `#3C3346`. Check: `#F29A5E` (band 5) at (60, 284), `#FFD99A` (sun) at (270, 280) in the no-routes state |
| S-06 | The gantry legs are missing | Two rects 8 × 100 at (34, 286) and (348, 286) (W − 42 on other widths), `color.interior.pole` `#55565C`, drawn under the sign (§9.3, W-06) |
| S-07 | The mirror glass is flat `#0D0D0F` with white/yellow figures. This is the Instruments look, not `Mirror.Small` | components §3.1: reflected sky `color.sky.band2` `#4E3768` at y 21–41 and reflected ground `color.scene.groundDay` `#2C3A33` at y 41–59 inside the clipped glass, glare `color.mirror.glare`. Silhouettes are **cut-outs in `color.mirror.glass`** on that reflection |
| S-08 | Mirror slots and dog. For «2 взр · 1 реб · пёс» the adult is at x 180 and the child at x 212, and **the dog is missing** although the caption says «пёс» | Slot centres x 154 / 193 / 230. Passenger adults fill from the outer slots inward, children take the remaining slots: adult at 154, child at 193. The dog is always drawn at the right: body 14 × 12 at (245, 41), radius 6 6 4 4, ears 4 × 6 at (246, 38) +20° and (254, 38) −20° (W-09) |
| S-09 | No-routes state: the navi field keeps the 1 dp `#2B3D4D` border | 5.1 §4.7: border `stroke.w2` `color.accent.yellow` `#FFD23F`, alpha pulsing 1 → 0.4 → 1 twice (2 × 1200 ms) on first display, then solid. A static frame is solid yellow (W-25 point (37, 610)) |

### 5.2 Navigator

| ID | What is wrong | Expected value / token |
| --- | --- | --- |
| S-10 | No road in the ground strip (y 104–150 is plain `#2C3A33`) | components §9.1 row "Navigator": container (0, 104, 390 × 46), P 120, θ 80°, W 160, L 600, edge 4, lane 6, clipped at 104; half-width 80 @ 150, 43.9 @ 119.7 (N-01) |
| S-11 | The panel and its content sit 12–18 dp low. Panel is 200–720 (spec 188–704). ОТКУДА is 56 high at y 243 (spec 50 at 231). КУДА is at y 309 (spec 291), the list at 375 (spec 357), the header glyphs at 222 (spec text box 207). The back link is about +8 | Panel (14, 188) 362 × 516, top 188 / bottom inset 140, bezel 7, padding 12, gap 10 (D3). `NaviValueField` **min-h 50** (D5) with caption + value at (68, 239) / (68, 253). Fixing S-03 alone does not move the panel: its top must be anchored at 188, not to the dashboard path |

### 5.3 Instruments

| ID | What is wrong | Expected value / token |
| --- | --- | --- |
| S-12 | The odometer has 3 drums «3 0 0» | components §4: **4 drums**, zero-padded «0300»; drums 24 × 34 at x 49 / 76 / 103 / 130, y 358; drums 1–3 `color.dash.face` `#1C1C1F` with `color.text.primary` digits; drum 4 `color.sign.white` `#F4F4F0` with `color.text.onLight` digit; frame (45, 354) 113 × 42 `color.dash.odometerFrame` (I-10) |
| S-13 | The wells have unequal heights: odometer 336.7–500.3 (164 high), budget 332–517 (185 high) | Both wells (14, 316) and (201, 316), **175 × 197**, `color.dash.well` `#0F0F11`, border 4 `#232327`, radius 24. Give them equal heights (`Modifier.height(IntrinsicSize.Max)` on the row, or a fixed 197) (I-09) |
| S-14 | The fuel gauge is too light: track ≈ 4.7 dp, needle ≈ 2.7 dp wide, hub ≈ 6 dp | components §6: track stroke **8** butt `color.dash.controlAlt` `#2A2A2E`; E arc stroke 8 `color.accent.red` `#D8402B`; needle **4 × 48** radius 2 `#FFD23F`, pivot (65, 58); hub **d 16** `#F4F4F0` centred at (65, 60); box 130 × 62 at (223.5, 352) (I-13) |
| S-15 | The dog toggle is a filled circle with the word inside: tan «пёс» when on, dark pill «+ пёс» when off | components §3.4: box 56 × 52 at (283, 85); body 32 × 26 radius 14 14 10 10 at (+12, +14); ears 9 × 14 radius 5 at (+6, −6) −18° and (+41, −6) +18°; label **below**, centred, `type.caption.bold` 11 sp. On: body and ears `color.crew.dog` `#C99A5B`, label «пёс» `color.text.primary`. Off: body dashed 2 `color.text.muted`, no ears, label «+ пёс» `color.text.secondary` (I-06) |
| S-16 | The empty seat border is a 1 dp solid `#55555E` | components §3.3 empty state: **dashed 2 dp (dash 6, gap 4)** `color.dash.outlineDashed` `#55555E`, transparent fill, label «свободно» `color.text.seatEmpty` (I-05) |

### 5.4 Drive

| ID | What is wrong | Expected value / token |
| --- | --- | --- |
| S-17 | The sky bands reuse the Windshield values: edges at 110 / 180 / 235 / 266 | 5.4 §2.1: band 1 0–120, band 2 120–190, band 3 190–240, band 4 240–276, band 5 276–300 (`#2B2850 #4E3768 #8E4A6B #D9655A #F29A5E`); sun (161, 270) 68 (D-01) |
| S-18 | Road projection | Same as S-04 with the Drive row: P 210, θ 76°, **W 240**, edge 6, lane 8, container (0, 300, 390 × 260); half-width 120 @ 560 (D-02) |

### 5.5 Road ahead

| ID | What is wrong | Expected value / token |
| --- | --- | --- |
| S-19 | The sky bands are wrong: band 1 0–59, band 3 59–99, band 4 99–132, and band 5 is missing | 5.5 S1–S4: band 1 0–50 `#2B2850`, band 3 50–84 `#8E4A6B`, band 4 84–110 `#D9655A`, **band 5 110–132 `#F29A5E`**; cap at 110 (R-01) |
| S-20 | The lane dashes in the road column restart in every list item, so stubs and doubled gaps appear at item boundaries | 5.5 §1: one global phase. Dash k covers u ∈ [phase + 64k, phase + 64k + 32] where u = **item top in list coordinates** + local y. Pass the item's absolute offset into each segment's draw so the segments join seamlessly (R-05) |
| S-21 | The vertical rhythm runs 8–13 dp low. The «Дорога впереди» glyphs are +9. Chips are at 194 (spec 185.4). The day-1 header glyphs are at ≈ 286 (header box 268.4–287.9). The row-1 city sign top is at **314** (spec 305.9) | 5.5 §2.2–2.3: L1 y 150, L2 y 185.4, L3 y 216.4, road column 268.4, day-1 header top = 268.4 (top margin **0** for day 1), header 19.5 + 10, row 1 top **297.9**, sign top = row top + 8, row height = 8 + max(sign, text) + 12 (R-08, ±1 dp) |
| S-22 | The Waybill footer has no arrow; «≈ 11 300 ₽ на человека» sits where the arrow should be | components §15 `WaybillCta`: arrow `right` 22 at (334, 777), stroke `stroke.icon.cta`, `color.text.onLight`. The per-person line is accepted as a design addition (new 5.5 **F3**): right edge 322, centred on the arrow, `type.body.smStrong` `color.text.onLightMuted`, copy key `road_waybill_per_person` (see Copy) |

### Copy

| ID | Screen | What is wrong | Expected |
| --- | --- | --- | --- |
| S-23 | 5.1 / 5.3 | `genitive()` is a two-entry map. Any other origin falls back to the nominative: «РЯДОМ С ВАМИ · ИЗ ТВЕРЬ», «из Тверь · 745 км по кругу» | Mock build: fine (the only origins are Москва and Тестовск). Before any other origin ships, the engine needs `name_gen_ru` (and `name_prep_ru`, already needed by `{town_prep}`) on towns. Requested from the Architect/Developer; until then, add every fixture origin to the map |

## P2 — polish and scope to confirm

| ID | Screen | Item | Expected |
| --- | --- | --- | --- |
| S-24 | 5.1 | The navi panel is 128.7 high (542–670.7) | 134 (542–676); hint D10 at y 642 + padding 10 + bezel 6 |
| S-25 | 5.1 loading | The sign header hides «КМ» | Keep «КМ»; only the rows become placeholders (§4.3) |
| S-26 | 5.2 | After a suggestion is picked, КУДА stays focused (yellow border, caret) | §4.2: IME closes and focus clears → border `color.navi.fieldBorder` `#2B3D4D`, no caret (`LocalFocusManager.clearFocus()`) |
| S-27 | 5.3 | No mirror stem; no reflected road | Stem (180, 0) 30 × 58 `color.dash.controlAlt` behind the body; road trapezoid top 188…202, bottom 160…230 at y 113–135 `color.scene.road` |
| S-28 | 5.3 | The keys have no inner bottom edge | `shadow.key`: 3 dp band `color.dash.keyShadow` `#0E0E10` clipped to the key (I-12) |
| S-29 | 5.3 | The 360-wide hint wraps to 2 lines | Accepted. Spec updated (H1): it wraps below 390 dp, centred on the chip |
| S-30 | 5.5 | The dashboard cap draws a 2 dp `#232327` rim | Cap without a rim (components §10, «no rim») |
| S-31 | 5.2 | Dashed buttons «+ заехать по пути» / «точка на карте» are missing (N-10), also the yellow-dashed «точка на карте» in no-results | Scope: vias and the map picker are cut. Confirm whether D-14 (the «карта появится в следующей версии» plate) is in the CEO build; if yes, the buttons should be shown |
| S-32 | 5.3 | Settings plate «Машина и выезд» (N3) is missing | Scope cut? (D-4 sheet not built) |
| S-33 | 5.5 | Day-header link «в навигатор ↗» is missing (R-07) | Scope cut? (navigator hand-off) |
| S-34 | 5.5 | Toolbar save/share (T1/T2), row buttons «заменить» / «Выбрать отель →» are missing | Scope cut (dev-notes 4) |
| S-35 | 5.5 | Car marker is missing (R-06) | Scope cut with the animations. Reduced-motion frame = marker at the top of the visible road, 14 × 22 at x 39 |
| S-36 | tooling | CI writes `screenshots/windshield/…`, but `qa_sample.py` read `screenshots/5.1-windshield/…`, so every point reported "missing" | Fixed: the sampler accepts both names |

## What passes

- **Windshield:** sign plate (20, 84), border inset, header and rows at 96 / 114 / 158 / 202, selected row `#163B7A` with yellow text and arrow, 3-row short window (W-30, checklist corrected: the formula gives 3 rows at 640, not 2), start button M geometry (bezel 696–788, face 76, ring 3 `#D8402B`), caption, loading placeholders, engine-failed and no-routes copy.
- **Navigator:** field colours and the КУДА focus border, suggestion row 52 and badge 26 `#1E4FA3`, no-results copy and block, caption «Москва → ?» / «Москва → Ярославль» with «≈ 249 км · город · Ярославская область», start S disabled/enabled.
- **Instruments:** mirror body (20, 54) 350 × 174 with reflected sky and ground, bench `#2A2A30`, seat silhouettes, front-seat chip, summary plurals, mood chips (selected white / unselected outline), caption.
- **Drive:** panel (18, 562) 354 × 186, header «СТРОИМ ДОРОГУ · 745 КМ» / «3 ДНЯ», progress bar at 602, step lines with check / active ring and «…», CTA (18, 760) 354 × 58, error layout and copy, «Отменить» → «Приборы».
- **Road ahead:** title sign, InfoChips, intro, road column x 14–60 with 3 dp edges, connector stubs, city / tourist / service signs, line-1 / name / note / cost styles, NO_LODGING plate, pinned footer (16, 756) 358 × 64 with fade.
- **Developer copy:** «≈ N ₽ на человека» has U+00A0 after «≈» and before «₽» and U+202F thousands. It is now deck key `road_waybill_per_person`: delete `slice_per_person` from `strings_slice.xml` and use the core-ui key. «ИЗ МОСКВЫ» is correct, uppercase in the resource as the deck requires.

## DES-100 fonts

Fonts: workflow run 40092704186 → `bot/fonts-4` (`530b43d`), fast-forwarded into this branch. All six files have `missingGlyphs: []` and sha256 equal to `android/fonts.lock`; `usWeightClass` is 400/500/600/700/600/400; the 3 OFL texts are under `assets/licenses/`. Wiring is the Developer's: `python3 tools/sync_design_tokens.py`, which turns on `DesignTokensInSyncTest` equality, then G-03 on the next screenshots. Two findings change what we ship:

1. **google/fonts' IBM Plex Sans Condensed (v1.3) has no Cyrillic.** Not one glyph in U+0400–04FF; the mockups' Cyrillic was rendered in a browser fallback. The npm packages `@ibm/plex-sans-condensed@2.0.0` and `@ibm/plex@6.4.1` contain no TTFs. IBM Plex Sans v3.201 on google/fonts is a `[wdth,wght]` variable font, wdth 75–100, with full Cyrillic. Its **wdth 75** instance matches the v1.3 Condensed Latin advances to 0.01 %, so we cut the four static weights there. Resource names are unchanged (`ibm_plex_sans_condensed_*`), so `DesignTokens.kt` needs no change. Recorded in `design/decisions.md` for the Manager's confirmation (the OFL Reserved Font Name question).
2. **Marck Script lacks «₽», «→», U+00A0 and U+202F; Plex Mono lacks U+202F.** This is OI-12 as decided: «₽» and «≈» in handwritten values are set in Plex. Spaces fall back per character and are invisible.
