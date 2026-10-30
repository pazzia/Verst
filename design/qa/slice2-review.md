# DEV-SLICE-2 visual QA — Designer review

Build: `main` = `efe955d` (DEV-SLICE-2: one km source, Waybill 5.6, replace stop, saved trips + «Мои поездки», fonts wired, 22 P1 fixes). Screenshots: `ci-logs` run `40095303435-1` (Robolectric 390 × 844 / 360 × 640, emulator e2e 01–19, ≈ 390 × 640 dp). Method as `slice-review.md`: `qa_sample.py` points, colour-run scans at density 3, visual read against the screen files. Tolerance ±4 dp, exact hex.

**Summary: P0 0 · P1 11 · P2 12.** Of the 22 slice-1 P1s, **21 are fixed**; S-21 (Road ahead rhythm) is only partly fixed (N-07). The fonts are visibly in: Verst Sans Narrow has Cyrillic everywhere, the odometer uses Plex Mono, and the Waybill handwriting is Marck Script.

## 1. Re-verification of slice-1 P1s

| ID | Item | Result | Evidence |
| --- | --- | --- | --- |
| S-02 | Status / nav bars | **fixed** | e2e: light icons on `#2B2850` (strip screens) and `#0E0E10` (Drive/Windshield) |
| S-03 | Dashboard crest | **fixed** | Windshield rim 518–520 at x 195; Drive ≈ 538; Navigator and Road caps on the arcs |
| S-04 / S-18 | Road projection | **fixed** | W-03 and D-02 check points pass (±1 dp) |
| S-05 | Hills polyline | **fixed** | W-01/W-02 pass |
| S-06 | Gantry legs | fixed as specced → new N-01 (the spec was incomplete) | legs at x 34 / 348, y 286–386 |
| S-07 / S-08 | Mirror glass, slots, dog | **fixed** | reflected sky/ground, glass cut-outs, dog at the right |
| S-09 | No-routes field border | **fixed** | W-25 passes |
| S-10 / S-11 | Navigator road; panel at 188 | **fixed** | panel top 188, ОТКУДА 50 |
| S-12 | Odometer 4 drums | **fixed** | «0300», last drum white |
| S-13 | Equal wells | **fixed** (equal); position → N-04 | |
| S-14 | Gauge strokes | **fixed**; letters E/F missing → N-06 | |
| S-15 | Dog toggle | fixed as specced → N-05 (spec error, corrected) | |
| S-16 | Dashed empty seat | **fixed** | |
| S-17 | Drive bands | **fixed** | edges 120 / 190 / 240 / 276 |
| S-19 | Road bands | **fixed** | R-01 passes |
| S-20 | Continuous lanes | **fixed** | |
| S-21 | Road vertical rhythm | **partly** → N-07 | |
| S-22 | Footer arrow + per-person | **fixed** | |
| S-23 | Genitive | **fixed** (48-town map); engine field → open-issues OI-39 | |

## 2. P1 — noticeably off-spec

| ID | Screen | What is wrong | Expected value / token |
| --- | --- | --- | --- |
| N-01 | 5.1 | With 3 rows the sign plate ends at y 256, but the gantry legs start at 286, so they float 30 dp below the sign | **Spec corrected** (components §9.3, 5.1 S13/S14): leg top = **min(286, plate bottom − 4)**, bottom y 386, 8 wide at x 34 / W − 42, `color.interior.pole` `#55565C`. With 3 rows: 252–386 |
| N-02 | 5.1 «Мои поездки» | The plate is at y 748–784; the caption column is not centred on the start button | 5.1 §4.4: column = label / title / meta / 8 / plate (101.2 total), centred on the start button centre y 742 → label top 691.4, plate **757–793** (h 36, touch 753–797) |
| N-03 | D-1 sheet | Trip dates show as «07.11» / «24.10» | New keys `common_month_gen_01…12`, `common_date_day` «31 октября», `common_date_range_month` «7–9 ноября», `common_date_range` «30 октября – 2 ноября», `common_date_with_year` (only when the year ≠ current year). Meta = `trips_row_meta` «7–9 ноября · 3 дня · 2 взр · 1 реб · пёс» |
| N-04 | 5.3 | The wells are inset 20 dp (x 20–189 and 201–370, 169 wide) and start at y 332. The front chip is at 238, the summary glyphs at ≈ 296 | Wells **L14 / R14**: (14, 322) and (201, 322), **175 × 197**, column gap 12. **Spec corrected** (5.3 H2 overlapped the mirror by 2 dp): chip H2 at **232**, summary H3 **282**, wells **322**, mood **535 / 557 / 609**, settings plate **665**. Checklist I-08/09/15 and QA points updated |
| N-05 | 5.3 dog | The ears float 6 dp above the body (x 289 / 324, y ≈ 80–93) | **Spec corrected** (components §3.4, mockup `left/right: 6px; top: -6px` of the body): ears relative to the **body**: (+6, −6) at −18° and (+17, −6) at +18°, so at 390 × 844 ears at (301, 93) and (312, 93), 9 × 14, radius 5, `color.crew.dog` |
| N-06 | 5.3 gauge | The letters E / F are missing | New keys `instruments_gauge_empty` «E», `instruments_gauge_full` «F»: `type.caption.bold`, E `color.accent.redText` baseline-left (8, 46), F `color.text.primary` (114, 46) of the gauge box (components §6) |
| N-07 | 5.5 | Everything after the title is ≈ 7–8 dp low. Chips 192.7–215.7 (spec 185.4–208.4), road column top **276** (268.4), row-1 city sign **313.7** (305.9), connector 343.7 (335.9) | 5.5 §2.2: L2 chips at title bottom + 6 = **185.4**, L3 intro 216.4, road column 268.4, row 1 297.9, sign top = row + 8. The title text box is probably taller than 29.4 (`type.display` 28 sp, line height 29.4 must be applied with `LineHeightStyle(Center, Trim.None)` and `includeFontPadding = false`) |
| N-08 | D-6 replace sheet | No mini signs on the rows; the rows are transparent with an outline | **D-6 updated:** rows min-h 64, fill `color.dash.controlAlt`, radius `radius.r10`, padding 10 12, gap 8; selected = border 1 `color.accent.yellow`. The mini sign of the stop's kind at 0.7 scale (service 35 × 43, tourist 39 × 39) sits between the radio and the name. The current stop is selected on open |
| N-09 | 5.6 | The saved button reads «Сохранено √»: the deck had «✓» as a character, which Verst Sans Narrow lacks, so it fell back to «√» | **Deck fixed:** `waybill_saved` «Сохранено», `road_booked` «Забронировано», `pro_plate_joined` «Поездка Pro · вы в списке». The check is drawn: §17.4 `check` 16 × 16, stroke 2, the text colour, gap 6 after the text |
| N-10 | 5.4 | The Drive panel header says «265 КМ», but the stage line says «Делим путь на 1 день по ≈ 263 км» (base route without detours) | One km source again: the engine's `split` stage text must use the trip km (265) or omit the number. Engine template, Developer |
| N-11 | 5.6 | The sheet top is at 70 and the clip at 56–84 | Sheet (14, **64**), clip (135, **50**) 120 × 30, 14 dp above the sheet top (components §11) |

## 3. P2 — polish and scope

| ID | Screen | Item | Expected |
| --- | --- | --- | --- |
| N-12 | 5.1 | Navi panel bottom at 669 (S-24 carried over) | 676 (134 high) |
| N-13 | D-6 | The CTA reads «ЗАМЕНИТЬ» with an arrow and is 58 high | `replace_confirm` «Заменить», `YellowButton` h 56, `type.cta.sm`, no arrow (D-6 ASCII corrected) |
| N-14 | D-6 | «+4 мин · 0 ₽» | Zero parts dropped: `replace_delta_min` «+4 мин» (`_rub`, `_none` likewise); `replace_delta` now has `{min_sign}` and `{rub_sign}` |
| N-15 | `PlateToast` with an action | 63 dp high | min-h 44, padding 10 16; one line «Заменили. Путевой лист: ≈ 4 400 ₽ · Вернуть» stays 44 |
| N-16 | 5.6 | The total row's value column is ≈ 151 wide | Columns rest / **100** (P8h) |
| N-17 | 5.6 | The total and left show «₽», but issued does not | Values as P8h/P9: «≈ 30 500», «40 000», «≈ 9 500» without «₽» (the table header carries «₽») — all three the same |
| N-18 | 5.6 | The route value «Золотое кольцо» | P7a: «Москва — Золотое кольцо — Москва» (origin — route — return for a ring) |
| N-19 | 5.6 | «≈ / ₽ / −» inside the handwritten formulas: Marck Script has no «₽» or «−», so Android falls back to the system font | OI-12: set «₽», «−» and «✓»-like symbols in Verst Sans Narrow at the same size in `color.paper.ink` (`SpanStyle(fontFamily = plexSansCondensed)`) |
| N-20 | 5.4 screenshot | The `t1500` fake stream still says «745 КМ» for the ring | Fixture = 761 (engine estimate), so screenshots match the device |
| N-21 | 5.3 | The hint wraps at 390 too | Accepted: spec H1 now allows 2 lines at every width |
| N-22 | scope | Waybill stamp + `sheetSlide` + Pro plate; Navigator dashed buttons (D-14); 5.3 settings plate (N3); 5.5 day «в навигатор ↗» link; car marker | Not built yet. Motion tokens are now complete (motion.md §2.3) |
| N-23 | 5.1 / 5.5 | Save / delete / 50-limit / undo flows | Copy is now in the deck: `trips_delete_*`, `trips_delete_action`, `trips_deleted` + `common_undo`, `cd_trips_deleted`, `trips_limit_reached_*`, `common_dialog_cancel`, `trips_past` |

## 4. Passes worth noting

- Windshield «Мои поездки · 2» plate style (36 h, outline, bookmark).
- D-1 sheet: top 596 with a 2 dp rim, rows 64 / gap 8, 32 dp blue arrow plate, yellow amounts with U+202F.
- Navigator too-short message in `color.accent.redText`.
- Mood chips, dashed seats.
- Waybill: grid, table borders, chevrons, expanded breakdown (labels in Plex, values in hand), «Перерасход» in ink red + hint, reserve off «—».
- Replace: «сейчас» row, mixed-sign deltas, disabled CTA until a change.
- Road toolbar: save turns yellow when saved; «К лобовому» back label from a saved trip.
- km is consistent: 265 / 761 on every screen except N-10.
