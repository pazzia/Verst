# Verst — Visual QA checklist (Designer's acceptance of the implemented UI)

Version 1.0.0 · 2026-10-23 · Use against every build that claims a screen is done (SPEC 18 "Definition of done"). Every item is Pass / Fail. A screen passes only when all its items pass. Failures go to the Manager as a list of `[screen] [item id] expected / actual / screenshot`.

## 0. Method and tolerances

| Aspect | Tolerance | How measured |
| --- | --- | --- |
| Position and size | ±4 dp against the screen redlines (SPEC 18); **±1 dp** for the road projection check points and sign borders | Paparazzi screenshots at 390 × 844 dp (density 3.0, 1170 × 2532 px) and at 360 × 640 and 480 × 900; overlay on the mockup render; the Layout Inspector for bounds |
| Colour | **Exact hex** for flat fills, text and strokes (0 difference in RGB). Alpha tokens: ±1 per channel after compositing | Pixel sampling on the screenshot at the points listed per screen, at least 2 px inside an edge (anti-aliasing excluded) |
| Typography | family and weight exact; size exact (sp); line height ±1 sp; letter-spacing exact; tabular figures where the token has `tnum` | Layout Inspector text attributes + overlay |
| Motion | duration ±1 frame (±17 ms); easing visually identical in a frame-by-frame comparison against the formula; loops in phase after pause/resume | `ComposeTestRule.mainClock` stepping (UI tests) + 60 fps screen recording |
| Accessibility | TalkBack strings exact (character for character, including «» and thin spaces); all touch targets ≥ 44 × 44 dp; contrast as in open-issues §2 | TalkBack on a device + Accessibility Scanner + `SemanticsNodeInteraction` assertions |
| Tokens | No colour, size, TextStyle or duration literal in UI code outside `DesignTokens.kt` | grep for `Color(0x`, `.sp`, `.dp` literals and `tween(` with numbers in `:feature-*` modules; must be zero |

## 1. Global items (every screen)

| ID | Item |
| --- | --- |
| G-01 | `DesignTokens.kt` equals the generated file (diff against the package version is empty) and `tokens.json` is unchanged |
| G-02 | No Material components or ripples visible; pressing any control shows only the pressed state from components.md |
| G-03 | Fonts: IBM Plex Sans Condensed (400/500/600/700), IBM Plex Mono 600, Marck Script 400 loaded from `res/font`; no download at runtime; Cyrillic renders without fallback glyphs (check «ё», «№», «₽», «≈», ««»») |
| G-04 | `includeFontPadding = false` on all text (text boxes match `lineHeightSp`) |
| G-05 | Number formatting: U+202F thousands («34 500»), U+00A0 before units, «≈» before estimates, 24-hour time |
| G-06 | Status and navigation bars transparent with light icons; the colour behind them matches components §0.2 |
| G-07 | System back performs the same action as the screen's back link; no bottom navigation bar anywhere |
| G-08 | Focus ring 2 dp `#FFD23F`, 2 dp offset, visible with keyboard/D-pad on every interactive element |
| G-09 | Touch targets ≥ 44 × 44 dp for every interactive element (Accessibility Scanner reports 0 issues) |
| G-10 | Font scale 130 %: no clipped or overlapping text on any screen at 390 × 844 and 360 × 640; single-line names ellipsize; notes wrap |
| G-11 | "Remove animations" on: every loop shows its static frame (motion.md §2), one-shots end state, screen transitions are cuts |
| G-12 | Loops pause on `onPause` and resume from the same phase; loops pause under bottom sheets and dialogs |
| G-13 | Performance: Macrobenchmark on a Galaxy A34-class device — 0 frames > 32 ms in a 10 s idle on each scene screen; P90 frame ≤ 16.6 ms; 0 recompositions per frame from loops |
| G-14 | All copy matches the screen files and the mockups exactly (Russian, punctuation, «ё») |
| G-15 | Width 480 dp: L/R-constrained elements stretch, centred elements stay centred, no element exceeds its constraint |

## 2. Screen 5.1 Windshield

| ID | Item | Expected |
| --- | --- | --- |
| W-01 | Sky band edges | y 110, 180, 235, 275, 300 (±1); colours #2B2850, #4E3768, #8E4A6B, #D9655A, #F29A5E sampled at x 195 mid-band (visible strips at x 5 or 380 where the sign covers) |
| W-02 | Hills | path vertices from components §9 at y 272 offset; colour #3C3346 |
| W-03 | Road projection | half-width (±1 dp) 115 at y 540, 78.7 at 447.6, 53.4 at 383.3, 30.5 at 325.1; asphalt #3A3A3F; edges 6 dp #F4F4F0 at the near end |
| W-04 | Lane dashes | 8 dp wide at the near end; period 160 / dash 70 in plane units; one cycle 900 ms |
| W-05 | Posts | start (236, 302) and (148, 302), 6 × 18 with a 5 dp #141416 cap; 2600 ms, the left one offset 1300 ms; end translation ±150 / +260, scale 2.2 |
| W-06 | Gantry legs | (34, 286) and (348, 286), 8 × 100, #55565C |
| W-07 | Liner and pillars | liner 16 high, curve 14; pillars 24 wide at the top, 9.6 at y 540; #0E0E10 |
| W-08 | Mirror | body (120, 18) 150 × 44, radius 22, bezel 3 #2A2A2E; stem (191, 8) 8 × 10; caption centred at y 65, 11 sp/600 #E9E2F2 with shadow; sway ±1.5° 4 s |
| W-09 | Mirror silhouettes match the crew (slot rule, components §3.1) for 1 adult; 2 adults + 1 child + dog; 4 adults |
| W-10 | Sign plate | (20, 84) 350 × 234; padding 4; border 2 #F4F4F0 inset; radii 9 / 6; shadow 0 8 18 black 35 % |
| W-11 | Sign header | y 96, 11 sp/600, 0.08 em, #D6E0F5; «РЯДОМ С ВАМИ · ИЗ МОСКВЫ» / «КМ» |
| W-12 | Rows | y 114 / 158 / 202 / 246, 44 high; arrow 22 at x 38; name x 70, 18 sp/600; km right edge 352, tabular |
| W-13 | Selected row | background #163B7A; arrow and text #FFD23F; 200 ms cross-fade |
| W-14 | Footer | y 290, 11 sp #D6E0F5, plural form correct for N = 1, 2, 5, 21 |
| W-15 | Arrow direction matches the 8-way bearing for each route |
| W-16 | Dashboard | top 520, curve 34, fill #161618, rim 2 dp #232327 |
| W-17 | Navi panel | (18, 542) 354 × 134, bezel 6 #232327, radius 16, screen #0B1218 |
| W-18 | «ВЫ: МОСКВА» is a separate button with a 44 dp touch box (y 542–586) not overlapping the field at y 586 |
| W-19 | Field | (36, 586) 318 × 48, #16222C, border 1 #2B3D4D, radius 10; icon yellow 18 |
| W-20 | Caption | x 22; label 11 sp #8C8C93; title 22 sp/700; meta 13 sp #B9B9C0; updates on selection |
| W-21 | Start button M | (278, 696) 92; face 76 #1C1C1F; ring 3 #D8402B; pulse 1.8 s to 16 dp |
| W-22 | Loading state: 4 shimmer rows, start disabled, never shown < 300 ms |
| W-23 | Offline with cache: «НЕТ СЕТИ» in the sign header and navi header; field sub-line changed |
| W-24 | Offline without cache: message «Нет сети — готовые маршруты появятся, когда будет интернет»; start disabled |
| W-25 | No routes: «Рядом пока нет готовых маршрутов»; field border yellow, 2 pulses |
| W-26 | Error: «Не получилось загрузить маршруты» + «Повторить» |
| W-27 | «Мои поездки» plate visible only with ≥ 1 saved trip; caption re-centred; sheet D-1 matches |
| W-28 | Location rationale toast on first launch only; denial toast copy exact |
| W-29 | Full-list sheet (§4.6): 56 dp rows, ring headers, selection moves the route to row 1 |
| W-30 | Short window 360 × 640: sign shows 2 rows; dashboard height 324 |
| W-31 | TalkBack order and strings = 5.1 §7 |

## 3. Screen 5.2 Navigator

| ID | Item | Expected |
| --- | --- | --- |
| N-01 | Strip bands at y 0/46/76/94/104; road P 120 θ 80° (half-width 80 at y 150, 43.9 at y 119.7) |
| N-02 | Dashboard top 132, curve 30 |
| N-03 | Back link «К лобовому» at (20, 148), 13 sp #8C8C93, touch 44 |
| N-04 | Panel (14, 188) 362 × 516 at 844; bezel 7, radius 18; content scrolls |
| N-05 | Header «НАВИГАТОР · ВСЯ РОССИЯ» / «GPS ●» at y 207 |
| N-06 | ОТКУДА field (33, 231) 324 × 50; «изменить» 36 high, touch 44 |
| N-07 | КУДА field (33, 291) 324 × 56; border 2 #2B3D4D → #FFD23F when focused; placeholder #768DA3; cursor yellow |
| N-08 | Suggestion rows 52 high at y 358 / 410 / 462 / 514; badges Г #1E4FA3, У #2B3D4D, М #6B3E26; selected row #1A2C3B |
| N-09 | Up to 6 suggestions; debounce 250 ms; skeleton after 250 ms |
| N-10 | Dashed buttons (33, 551) and (198, 551), 159 × 44, dashed #3A5266 |
| N-11 | Section label at y 605 in #768DA3; chips 36 high, single scrolling row |
| N-12 | Caption «Москва → Ярославль», meta with «≈»; start S (284, 732) 86 |
| N-13 | IME open: caption row hidden, panel above the IME; IME closed on pick |
| N-14 | No B: «Москва → ?», start disabled |
| N-15 | Validation copy in #E6604A: «Слишком близко для поездки на машине», «Не нашли дорогу на машине до этой точки» |
| N-16 | No results, error, offline blocks: copy and layout = 5.2 §3 |
| N-17 | Vias: insert, reorder (drag + TalkBack actions), remove, max 3 with «максимум 3 заезда» |
| N-18 | Map picker D-3: style colours, pin lift, states, CTA |
| N-19 | TalkBack = 5.2 §7 |

## 4. Screen 5.3 Instruments

| ID | Item | Expected |
| --- | --- | --- |
| I-01 | Strip bands y 0 / 60 / 90; cap at 104 curve 30 |
| I-02 | Back link at (16, 10) in #E9E2F2 with the trip title |
| I-03 | Mirror (20, 54) 350 × 174, radius 40, bezel 5, shadow 0 10 24 black 45 %; stem (180, 0) 30 × 58 |
| I-04 | Seats at x 41 / 146.3 / 251.7, y 145, 97.3 × 68; radius 14/14/6/6 |
| I-05 | Seat states: empty dashed #55555E + «свободно» #A0A0A7; adult #E9E2F2 silhouette 22/44×22; child #FFD23F 16/32×16; cycle order |
| I-06 | Dog (283, 85) 56 × 52; on #C99A5B + wag ±6° 1.2 s; off dashed #8C8C93 + «+ пёс» |
| I-07 | Front chip 44 high, radius 22; on white / off outline; copy exact |
| I-08 | Summary at y 276, 20 sp/700, plurals correct for 1, 2, 5 adults and 1, 2, 5 children |
| I-09 | Wells (14, 316) and (201, 316), 175 × 197, #0F0F11, border 4 #232327, radius 24 |
| I-10 | Odometer frame (45, 354) 113 × 42; drums 24 × 34, last drum white; digits Plex Mono 22/600; roll 300 ms only on changed drums |
| I-11 | Read-out lines and plurals; «мин» omitted when 0 |
| I-12 | Keys 52 × 44, #2A2A2E, inset 3 dp #0E0E10; disabled at 150 / 900 and at budget ends |
| I-13 | Gauge: track and E arc paths exact; needle angle −90 + 36·i; spring settles 500 ± 50 ms, overshoot ≤ 10° |
| I-14 | «E» #E6604A, «F» #F4F4F0, 11 sp/700 at (8, 46) / (114, 46) of the gauge |
| I-15 | Mood chips (y 529 label, 551 chips), settings plate (20, 659) 350 × 44 |
| I-16 | Caption at y 743; start L (270, 720) 100 |
| I-17 | Third row link and second bench (OI-07) if accepted |
| I-18 | Settings sheet D-4 |
| I-19 | Values persist after app restart |
| I-20 | TalkBack = 5.3 §7 |

## 5. Screen 5.4 Drive

| ID | Item | Expected |
| --- | --- | --- |
| D-01 | Bands 0 / 120 / 190 / 240 / 276 / 300; sun (161, 270) 68 centred |
| D-02 | Road P 210 θ 76° W 240 (half-width 120 at y 560); dash cycle 450 ms after the 800 ms ramp |
| D-03 | Posts start (212, 300) / (172, 300); 1100 ms, offset 550 |
| D-04 | Flying signs: spawn centre (195, 250), scale 0.12 → 1.7, ±230 / +40, 3600 ms, ≥ 1200 ms apart, alternating, ≤ 3 in flight; variants per components §2.2 |
| D-05 | Dashboard top 540; panel (18, 562) 354 × 186 |
| D-06 | Header «СТРОИМ ДОРОГУ · 745 КМ» / «3 ДНЯ» |
| D-07 | Bar (38, 602) 314 × 4; track #1E2E3A; fill per stage, 400 ms |
| D-08 | Step lines at y 616 / 640 / 664 / 688; check 10 dp yellow; text x 56; 350 ms appear, ≥ 400 ms apart |
| D-09 | CTA (18, 760) 354 × 58 yellow; auto-advance 1 s; none with TalkBack |
| D-10 | Slow state at 20 s: two buttons, copy exact |
| D-11 | Error codes: messages and CTAs = 5.4 §4.4; RATE_LIMITED countdown |
| D-12 | Offline state copy |
| D-13 | «Отменить» cancels the SSE request (verify in the network log) |
| D-14 | TalkBack = 5.4 §7 |

## 6. Screen 5.5 Road ahead

| ID | Item | Expected |
| --- | --- | --- |
| R-01 | Strip bands 0 / 50 / 84 / 110 / 132; cap at 110 above the scrolling list |
| R-02 | Back link (16, 18); toolbar buttons (290, 12) and (334, 12), 44 × 44 |
| R-03 | Title sign (20, 56) 350 × 49, padding 3, radius 7/5, 20 sp/700 |
| R-04 | «Дорога впереди» 28 sp/700 at y 150; chips at y 185.4, 23 high, #2A2A2E, radius 12; intro at y 216.4 |
| R-05 | Road column x 14–60, edges 3, lane 3, dash 32 / 64, 2200 ms; continuous across items while scrolling |
| R-06 | Car marker 14 × 22 yellow with black 2 dp border at x 39; 124 dp/s over the visible road |
| R-07 | Day header: «День 1» 15 sp/700 yellow; meta 12 sp #8C8C93; «в навигатор ↗» right edge 374 |
| R-08 | Row grid 72 / 68 / rest; padding 8 16 12 0; height formula (5.5 §2.3) for every row, ±1 dp |
| R-09 | City sign: 64 wide, border 3 #141416, outline 2 #F4F4F0, 11 sp/700 |
| R-10 | Tourist sign 56 × 56 #6B3E26, inner border 2 at inset 3, pictogram 30 |
| R-11 | Service sign 50 × 62 #1E4FA3, white square 40, pictogram 28 (fuel/food/rest/hotel paths exact), bar 22 × 3 |
| R-12 | Text column: line 1 12 sp #8C8C93; name 17 sp/700; note 13 sp/1.4 #C4C4CA; cost 13 sp/600 yellow |
| R-13 | «заменить» 36 high, border #3A3A42, 12 sp/600 #B9B9C0; «Выбрать отель →» 36 high #1E4FA3 |
| R-14 | Footer pinned (16, 756) 358 × 64 white; label 12 sp/600 #55565C; amount 22 sp/700; fade 24 dp above |
| R-15 | Long-press 500 ms → stop menu D-5; replace sheet D-6; report sheet D-7 |
| R-16 | States: prices plate, offline plate, NO_LODGING plate, over budget footer (#B3261E), saved toasts and 45/50 limits |
| R-17 | Scroll performance: no frame > 32 ms flinging through 3 days |
| R-18 | TalkBack row strings = 5.5 §7 (SPEC 16 example «Через 70 км, 09:15, Троице-Сергиева лавра»), custom actions present |

## 7. Screen 5.6 Waybill

| ID | Item | Expected |
| --- | --- | --- |
| P-01 | Back link (14, 14) |
| P-02 | Sheet (14, 64) 362 wide, #EEF2F4, radius 4, padding 26 16 14, shadow 0 10 26 black 50 % |
| P-03 | Clip (135, 50) 120 × 30 #8C8C93 with inset #5D5D63 |
| P-04 | Header texts and rule at y 146.9 (2 dp #22313D) |
| P-05 | Form grid y 156.9; label column 92; values in Marck Script 19 sp #1B3FA0 with 1 dp #9FB0BE underline per line |
| P-06 | Table at y 243.3; borders 1.5 / 1; 5 lines of 44 incl. «Платные дороги»; reserve 44; total 41 |
| P-07 | Handwriting only for values (11.2); printed labels #53687C |
| P-08 | Reserve toggle: totals recompute ≤ 100 ms; «—» when off |
| P-09 | Expand / collapse one line at a time; chevron rotation 200 ms |
| P-10 | Over budget: «Перерасход» + #B3261E value + hint line; no budget: «—» |
| P-11 | Stamp (270, 605.3) 94, rotation −14°, alpha 0.85, animation 500 ms after 1000 ms, first open only |
| P-12 | Sheet entry: 40 dp → 0, 600 ms decelerate |
| P-13 | Pro plate (14, 715) 362 × 44 dashed yellow; Pro sheet flow |
| P-14 | Buttons (14, 768) and (200, 768), 176 × 56; saved state |
| P-15 | Reference numbers 3 720 / 0 / 12 000 / 9 000 / 3 000 / 2 770 / ≈ 30 500 / ≈ 9 500 with the fixture (OI-06, D-16: 5 meals) |
| P-16 | TalkBack = 5.6 §7 (formula spoken in words) |

## 8. Screen 5.7 Exit

| ID | Item | Expected |
| --- | --- | --- |
| E-01 | Night bands 0 / 150 / 210 / 240; stars, moon crescent, town lights positions exact |
| E-02 | Road P 200 θ 76° (half-width 115 at y 430, 77.4 at y 351.6); asphalt #2E2E33; edges #D9D9D2 |
| E-03 | Headlight polygon and #FFECAA at 10 % |
| E-04 | Exit sign (162, 92) 198 × 110; arrow `downRight` 30; hotel plate 34; «800 м» 18 sp/700; near-animation 2200 ms from 0.7 |
| E-05 | Dashboard top 410; back link (20, 424); turn signal right 24 at y 430, blink 900 ms (on 495 ms) |
| E-06 | Panel (14, 464) 362 × 282; header, town 22 sp, reason 13 sp #B9C6D3 |
| E-07 | Hotel options at y 599.1 / 668.4; selected #16222C + yellow border + radio dot; unselected ring #5A7893 |
| E-08 | CTA (14, 760) 362 × 60; spinner while the link loads; offline variant |
| E-09 | Link opens outside the app (no WebView); return dialog «Забронировали?»; booked state on 5.5 |
| E-10 | TalkBack = 5.7 §7 |

## 9. Sign-off record

| Screen | Build | Date | Result | Failed items |
| --- | --- | --- | --- | --- |
| 5.1 | | | | |
| 5.2 | | | | |
| 5.3 | | | | |
| 5.4 | | | | |
| 5.5 | | | | |
| 5.6 | | | | |
| 5.7 | | | | |
