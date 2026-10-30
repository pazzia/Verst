# Sprint 3 R2 — visual QA (Designer)

Build: main `e2e1bd2` (dev/S3-R2 `11e4e06`), CI run 40139317399 (green). Sources: `ci-logs` → `runs/40139317399-1/e2e/screens/` 40–50 (R1) and 60–73 (R2), and `screenshots/{budget,card,city,walk,road,waybill,navigator}/*@390x844`. Checked against 5.8–5.13, the §8 Sprint 3 sections of 5.1–5.5, components §17.5–§23 and copy §15.

Photos: the M1 sample catalogue names files that do not exist on Commons, so only the placeholder, error and credit states could be checked. Loaded crops/contain, the scrim credit on real images and the portrait/tiny/SVG cases are **re-checked after the ARCH-302 data run**.

Severity: **P0** wrong information on a CEO path or a broken journey (fix before the demo) · **P1** visible deviation from the spec or a confusing state (fix this sprint) · **P2** polish, fixtures, not built yet.

## P0

| # | Screen | Finding | Fix | Owner |
| --- | --- | --- | --- | --- |
| P0-01 | 5.10 / 5.11 (e2e 67, 68) | The walk starts **at night**: «Старт 01:45 · финиш ≈ 04:04», while the 5.10 caption says «старт 22:45». Two problems: a walk is planned for hours when everything is closed, and the caption and the result disagree (device clock vs the engine's `startAt`). | 5.11 §9: daytime window (day walks 09:00 → end by 22:00, drink walks 18:00 → end by 23:00), otherwise next day at the opening with `city_caption_meta_tomorrow` / `walk_header_tomorrow`; caption = engine `startAt` in the town tz (needs `tz` in `city_presets`, the Developer's open ask). | Architect (rule + tz), Developer (caption, copy) |

## P1

| # | Screen | Finding | Fix | Owner |
| --- | --- | --- | --- | --- |
| P1-01 | 5.2 / 5.12 (e2e 48, 72, 73) | With the IME up the Navigator header «НАВИГАТОР · ВСЯ РОССИЯ / GPS ●» and the field scroll out of view (72 shows only «Найти адрес «Советская 1»» over skeleton rows; 48 shows rows only). This is the Developer's question. | 5.12 §5: fixed header + focused field + helper, only the result list scrolls; the other field collapses to one line; autofocus rule. | Developer |
| P1-02 | 5.10 → 5.11 (`walk/ryumochnye`, e2e 68) | The preset plate promises «4 ч», the result is 2 ч with no explanation. | Show the real duration and `walk_shorter` «Получилось 2 ч вместо 4 ч — больше открытых мест рядом нет» (5.11 §9). | Developer |
| P1-03 | 5.11 (e2e 68) | Footer «≈ 0 ₽ на всех · ≈ 0 ₽ на человека». | `walk_footer_free` «Бесплатно» + `walk_footer_free_sub` «вход везде свободный», no per-person line. | Developer |
| P1-04 | 5.11 (`walk/museums-spb`) | The city sign breaks inside the word: «САНКТ-ПЕТЕРБУ / РГ». | Components §2 `RoadSign` city: breaks only at a space or after a hyphen («САНКТ-» / «ПЕТЕРБУРГ»), then the plate grows, then 80 % text. Applies to Road ahead too. | Developer |
| P1-05 | 5.9 hotel (e2e 65) | The photo failed («Фото не загрузилось»), but the card still shows the credit «Фото района: Ярославль · Wikimedia Commons» and «на фото район, а не она», so the credit names a photo that isn't there. «Демо: вымышленная гостиница» repeats the fictional note among the facts. | 5.9 §3: no credit while the frame is a placeholder; use `card_hotel_fictional_nophoto`; drop the facts line. | Developer |
| P1-06 | 5.5 (e2e 70, Пермь) | Two no-lodging plates; the second repeats the first sentence and adds «Ближайшая подходящая: Волжский откос, Нижний Новгород, 320 км от ночёвки», so «ближайшая подходящая» appears twice. A night 320 km away also reads like a bug. | One plate per night: the general sentence once, then the hotel as a second line. Check the 320 km substitute on the synthetic route (should it be offered at all?). | Architect (notes), Developer (merge) |
| P1-07 | 5.5 / 5.11 (e2e 41, 64) | No visible «returned row» highlight: `dash.pressed` #1C1C20 on `dash.raised` #161618 has 1.05:1 contrast. The spec choice was wrong, not the build. | New token `color.overlay.returnFlash` (yellow 14 %, R1's provisional colour) and `motion.returnToItem.holdMs` 400 (then an 800 ms fade); motion.md, 5.9 §5. **Run `tools/sync_design_tokens.py`.** | Developer |

## P2

| # | Screen | Finding | Fix |
| --- | --- | --- | --- |
| P2-01 | 5.11 | «≈ 6,0 км», «≈ 7,0 км» on the title sign and chips | no trailing zero: «≈ 6 км» |
| P2-02 | 5.9 | The title row has no mini sign (known: not built) | §19 title row |
| P2-03 | 5.5 / 5.9 | «Сообщить об ошибке» (D-7) not built; the stop menu for a sight without a swap shows one item (e2e 43): acceptable | components §22 stop menu |
| P2-04 | 5.9 offline (e2e 66) | Shows «Фото пока нет»; if this POI has an image URL, offline must show `card_photo_offline` «Фото загрузится, когда будет интернет». Verify with real data | — |
| P2-05 | 5.12 (e2e 73) | «© OpenStreetMap» not visible above the IME | in the list right under the last row (5.12 §5) |
| P2-06 | fixtures | `road/tight-badge` «ЧУТЬ БОЛЬШЕ: +1 800 ₽» on 33 800 is outside the 5 % tolerance if the budget is 32 000; `road/replace-breaks-budget` marks a −20 ₽ alternative «не в бюджете»; `city/no-city` shows a start at «Советская пл., 1» with «Рядом нет города». The screens are right, but the fixtures contradict the rules, and the CEO reads these PNGs | make the fixtures consistent |
| P2-07 | sample data | «Церковь Ильи Пророка» has the kind «музей» (museum placeholder instead of church); «Рюмочная (пример)…»; «Волжская набережная» and «Стрелка и Волжская набережная» in one walk | data run (ARCH-302) |
| P2-08 | 5.11 | The «Часы работы части мест взяты по умолчанию…» plate appears on every walk and pushes the column down | show it only when ≥ 1 stop has default hours; consider a one-line muted note instead of a plate |

## Matches the spec (no action)

- 5.8 no-fit (`budget/no-fit`) matches `Budget.dc.html` pixel for pixel in layout and copy. Fitted Waybill lever lines, «ПЕРЕРАСХОД» / «Подогнать под бюджет →», the Road footer «✓ В БЮДЖЕТЕ» / TightDot / «ПЕРЕРАСХОД», and the replace sheet «не в бюджете» are all fine.
- CEO case (e2e 60–62): «≈ 27 400 ₽ — подгоним под бюджет» → Road «✓ В БЮДЖЕТЕ ≈ 27 400 ₽» → the Waybill.
- 5.9: 3:2 frame, placeholders per kind, «ФОТО РАЙОНА» label, the bar ODbL line, only sights and hotels tappable.
- 5.10: street plate + house square, preset plates, 18+ badge, kids-blocked «не с детьми», the custom sheet, the 18+ dialog, NO_CITY / NOT_ENOUGH_POIS plates, building state.
- 5.11: the WalkTitleSign wraps to 2 lines, chips, ±15 % line, the responsible plate (drink presets only), the walking column, the cost plate.
- 5.12: rationale sheet, «примерно, по сети» + «Точнее», «GPS ●», address helper + «Найти адрес «…»», address rows with the «У» badge, the offline hint, «Вы не в России».
- 5.13: day menu, stop menu, target line per installed app, truncated note, offline toast anchored above the footer. Brand scan: «Яндекс» only in `handoff_*` (plus the unused deck keys).

## Copy delivered in this round

Deck keys replacing `strings_pending_copy.xml`: `card_per_night`, `navigator_type_address` (renamed from the unused `navigator_type_street`), `walk_distance_m`, `debug_mock_location`, `windshield_meta_round_trip`, `budget_option_cheaper_sub_over`. The R1 keys `navigator_location_deny`, `navigator_location_failed` and `stopmenu_web_fallback` were already mapped by R2 to `loc_manual`, `loc_timeout` and `handoff_web`, so they are retired. New keys for the findings: `card_hotel_fictional_nophoto`, `city_caption_meta_tomorrow`, `walk_header_tomorrow`, `walk_shorter`, `walk_footer_free`, `walk_footer_free_sub`. After these land, the Developer can empty `strings_pending_copy.xml`; its copies override the library while both exist.
