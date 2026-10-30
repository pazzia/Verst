# Final release QA — CEO test build (DES-117)

Build: `main` = `262103b` (DEV-SLICE-3: 5.7 Exit, hotel choice, «Придорожная» mock booking, CostCalculator, motion, trip delete/limit, debug panel). Screenshots: `ci-logs` run `40098236764-1` — emulator journey e2e 00–30 (≈ 390 × 640 dp, the CEO-phone class) and Robolectric 390 × 844 / 360 × 640 for 5.1–5.7, sheets, dialogs and toasts. Method as in `slice2-review.md`: `qa_sample.py` points, colour-run scans, a visual read against the screen files and the v5 canvases, a scan of the string resources and of the Kotlin string literals (read only), and contrast computed from the tokens.

Severity for this build: **P0** blocks the CEO build · **P1** visible to the CEO, fix before handing over · **P2** later.

## Verdict

**P0: none. P1: 4. P2: 13.** The build can go to the CEO once the four P1s are fixed; each is small and local.

Slice-2 P1s: **10 of 11 fixed**. N-07 (Road ahead rhythm, still ≈ +7 dp) is downgraded to P2: the offset is uniform and invisible without an overlay.

## 1. P1 — fix before handing over

| ID | Screen | What the CEO sees | Expected (spec updated where marked) |
| --- | --- | --- | --- |
| F-01 | 5.1 sign rows | «Золотое кольцо **745**», «Ярославль **263**», «Тула · Ясная Поляна 207» are template km, but after tapping, Instruments, Drive, Road ahead and the Waybill all say **761** / 265. This is the km-consistency issue again, on the first screen the CEO sees | **5.1 §3 updated:** the row km is the engine estimate (`mobile.estimate` for each ready route with the current origin, crew and pace), the same figure as Instruments. Show the template km only until the estimate arrives (≤ 1 s after engine start), then swap without animation. The live-region and TalkBack row strings use the same number |
| F-02 | 5.1 «Поездка удалена · Вернуть» (e2e 21); same component on 5.5 | The toast is 63 dp high and covers the caption meta and half of the ПОЕХАЛИ button | **components §16 updated:** one-line toast + action = **44 dp**. Anchors per screen: Windshield bottom edge = dashboard crest − 16 (y 504 at 844), Road ahead 740, Exit / Waybill 16 above the CTA, Navigator / Instruments 16 above the caption row. It never covers the caption or a button |
| F-03 | 5.7 NO_LODGING night without hotel options | «Забронировать ночь · демо-партнёр» is active although there is nothing to book | **5.7 §4 updated:** with `hotelOptions` empty the CTA takes the offline look (`color.dash.control`, title `color.text.secondary`, no arrow, not pressable) with the sub-line **`exit_book_none`** «нет вариантов с вашими условиями» (new key). The MockPartnerSheet is not reachable |
| F-04 | 5.7 at the 640 dp window (e2e 22) | Only one hotel fits; the second is fully hidden with no fade or peek, so the CEO does not see that there is a choice (the journey needed a scroll to reach «Волжская набережная») | **5.7 §1 updated:** scene minimum **260 dp** (was 300), so the second option fits at 640. On overflow, a 16 dp `color.navi.screen` fade at the panel's bottom edge, and the next option peeks by ≥ 20 dp. At 360 × 640 the same rule applies (today the second option is cut flat) |

## 2. Slice-2 P1 re-verification

| ID | Result |
| --- | --- |
| N-01 gantry legs | **fixed** — legs start at the plate bottom (256 with 3 rows) |
| N-02 «Мои поездки» plate | **fixed** — 757.3–793.3 |
| N-03 D-1 dates | **fixed** — «7–9 ноября», «24–25 октября» |
| N-04 Instruments block | **fixed** — wells x 14 / 201, top 322; chip 232–276; odometer frame +4 (in tolerance) |
| N-05 dog ears | **fixed** — attached to the body |
| N-06 gauge E/F | **added**, but E sits on the red E zone and is barely visible → P2 F-13 (spec moved inside the arc) |
| N-07 Road rhythm | **not fixed** (chips 192.7 vs 185.4, row-1 sign 313.7 vs 305.9) → P2 F-05 |
| N-08 replace rows | **fixed** — controlAlt rows, mini signs, «Заменить» without an arrow |
| N-09 drawn checks | **fixed** — «Забронировано ✓» on Road ahead is drawn |
| N-10 Drive stage km | **fixed** (engine) |
| N-11 Waybill sheet | **fixed** — sheet at 64, clip at 50 |

## 3. Screens 5.1–5.7, sheets, dialogs, toasts, errors (pass unless listed in §1 or §4)

- **5.1 Windshield:** default, loading, no-routes, engine-failed, saved-trips at 390 and 360, D-1 sheet, delete dialog, deleted toast (F-02); mirror reflection and crew slots.
- **5.2 Navigator:** query, picked, no-results, too-short / unreachable in `color.accent.redText` (e2e 30).
- **5.3 Instruments:** at 390 and 360.
- **5.4 Drive:** progress, done, error-internal and error-unreachable with «Приборы» back link (e2e 29).
- **5.5 Road ahead:** toolbar, save toast, replace sheet, replaced toast + «Вернуть», booked hotel row, 50-trip limit dialog.
- **5.6 Waybill:** default, line expanded, reserve off + over budget, budget «не важно», final stamp (−14°, alpha 0.85, right 12 / bottom −30 of the sheet).
- **5.7 Exit:**
  - night scene: bands 0/150/210/240, stars, moon, town lights, headlight, pole
  - exit sign (162, 92) 198 × 110 with «300 м» from the engine (`exitDistanceM`), «ночёвка» fallback in no-lodging
  - turn signal, header «НОЧЁВКА 1 ИЗ 2 · КМ 263 · 14:50», reason
  - hotel options, Book CTA (14, 760) 362 × 60 with «демо-партнёр, без оплаты»
  - MockPartnerSheet: title + «ДЕМО» badge, «Придорожная» — вымышленный партнёр · демо, card, note, «Вернуться в Версту»
  - «Забронировали?» dialog, booked state («забронировано», «Открыть бронирование»), offline («НЕТ СЕТИ», «Нужен интернет»)

## 4. P2 — later

| ID | Item | Note |
| --- | --- | --- |
| F-05 | Road ahead list +7 dp after the title (N-07) | Trim the `type.display` line box (29.4) or reduce L2's top gap |
| F-06 | 5.1 navi panel 669 (spec 676), S-24 / N-12 | |
| F-07 | Toast exit animation, screen transitions (motion.md §3), Drive lane ramp, car marker | Not built (dev notes); cuts look acceptable for the test |
| F-08 | 50-trip limit dialog secondary «Отменить» | Should be `common_dialog_cancel` «Отмена» («Отменить» is the Drive back link). NaviDialog secondary should be the dashed `DashedButton` (now solid outline) |
| F-09 | Waybill: total column ≈ 151 wide (spec 100); «₽» after total and left but not after issued; route value «Золотое кольцо» (spec «Москва — Золотое кольцо — Москва»); «₽ / −» in handwritten formulas fall back to the system font (OI-12: set in Verst Sans Narrow) | N-16…N-19 carried over |
| F-10 | Exit at 360 wide: the exit sign runs into the right A-pillar zone | Scale sign x by W / 390 or keep its right edge ≤ W − 30 |
| F-11 | `OfflinePlate` / «Нужен интернет» without the offline icon (11 / 12 dp) | components §16, §15 |
| F-12 | Thousands separator U+202F is 0.106 em in Verst Sans Narrow, so «6 000», «40 000» read almost as «6000» | Acceptable (the Russian norm allows 4-digit numbers unspaced); revisit with a 0.15–0.2 em custom space if the CEO remarks on it |
| F-13 | Gauge «E» drawn on the red zone | **components §6 updated:** E at (20, 56), F at (103, 56), above the track |
| F-14 | Robolectric `road/booked-row` does not scroll to the hotel row, so R-13 cannot be sampled | Harness: scroll to the overnight row before the capture |
| F-15 | Debug panel shows English identifiers (world ids, error codes, «python … ms») and «0 / 1» chips for on/off | Debug only (2 s long-press); fine for the CEO test |
| F-16 | TalkBack: 42 of 76 `cd_*` strings are not referenced (mirror, sign rows + directions, caption live region, Drive steps/progress, Road rows, Waybill heading, trips deleted…). Visible elements still have their text read | TalkBack audit was scoped out of the slices; do it before a public build |
| F-17 | Touch targets are **44 dp** (SPEC 18 / OI-05) — sign rows, chips, back links, keys 52 × 44, «изменить» / «заменить» 36 visual / 44 touch, toolbar 44 × 44. None are below 44. Android's guideline is 48 dp | Conscious spec deviation; for a public release raise the touch boxes to 48 (visuals unchanged, layout shifts ≤ 2 dp each) |

## 5. Copy, language, numbers, accessibility basics

- **English:** none in user-facing copy. Exceptions: «GPS» (hidden, D-16); «Pro», «PDF», «RuStore» (product terms, not shown in this build); the debug panel (F-15).
- **«Яндекс»:** not shown anywhere in the mock build. The production keys `exit_book_partner`, `cd_exit_book` and `stopmenu_yandex_*` exist in the resources, but no Kotlin code references them (`grep R.string.exit_book_partner` → 0). The Book CTA and TalkBack use `exit_book_partner_mock` / `cd_exit_book_mock`. Stop-menu navigator names are real installed apps (handoff), not shown in this build.
- **Plurals / genitives:** correct on every screen seen. Examples:
  - «3 дня · 2 ночи», «1 день», «1 ночь», «2 сохранённые», «3 взрослых · 1 ребёнок · собака»
  - «ИЗ МОСКВЫ», «в Ярославле», «7–9 ноября», «7 нояб. — 8 нояб.»
- **₽ spacing:** «≈ 6 000 ₽», «≈ 33 800 ₽», «до 40 000 ₽». Everywhere: «≈» + U+00A0, U+202F thousands, U+00A0 before «₽» / «км» / «мин» (see F-12 for the narrow-space look).
- **Contrast (WCAG AA ≥ 4.5 for text, from tokens):**
  - `text.muted` on `dash.raised` 5.41; `navi.label` on `navi.screen` 7.50; `navi.labelSecondary` on `navi.field` 6.29
  - `sign.blueText` on `sign.blue` 5.86; `accent.redText` on `dash.raised` 5.28
  - `paper.label` on paper 5.12; `paper.ink` 8.23; `paper.inkRed` 5.80
  - `text.onLightMuted` on white 6.63
  - The stamp `#715AAD` 4.95 is decorative.
  - Disabled labels are exempt.
  - The only weak pair is F-13 (red E on the red zone).
- **Content descriptions:** see F-16. Decorative scenes are `clearAndSetSemantics`, and the controls carry their visible text.

## 6. Spec changes in this branch

- 5.1 §3: row km from the engine estimate.
- components §16: toast anchors and height.
- components §6: E/F inside the arc.
- 5.7 §1: scene min 260, overflow fade + peek.
- 5.7 §4: no-options state.
- copy-ru: `exit_book_none` (strings.xml regenerated).
