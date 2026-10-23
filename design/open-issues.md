# Verst — Open issues in design v5 and designed missing states

Version 1.0.0 · 2026-10-23 · Owner: Designer
Status keys: **DECIDE** = the Manager (or CEO) must choose; **FIXED** = resolved in this package, listed so the change is visible against the approved mockups; **INFO** = no change needed, recorded for QA.

## 1. Summary of decisions needed

| ID | Question | Designer's recommendation |
| --- | --- | --- |
| OI-01 / OI-02 | Accept 7 colour changes to the approved mockups so that all text passes WCAG AA | Accept (all are tiny shifts; table §2) |
| OI-04 | «НЕДАВНО ИСКАЛИ ДРУГИЕ» shows other users' searches; SPEC says local recents only | Local «НЕДАВНО ИСКАЛИ» + curated «ЧАСТО ИЩУТ» from remote config when empty |
| OI-05 | 44 dp touch targets make the Windshield sign 8 dp taller and several controls 2–4 dp taller than the mockup | Accept |
| OI-06 | The Waybill mockup has no tolls line and its fuel line does not match its own formula | Add «Платные дороги»; set the demo fuel price to 62,40 ₽ so every approved figure (3 720, ≈ 34 500) stays; total rounding = half up |
| OI-07 | The mirror has 3 back seats, SPEC allows 7 adults + 5 children | «+ третий ряд» link adds a second bench |
| OI-08 | Default mood when there are no children | `more_stops` is the server default; nothing pre-selected in the UI |
| OI-14 | Only one tourist pictogram (church) exists | Add museum and nature pictograms (in components §17.2) |
| OI-23 | Suggestion distances before planning are straight-line | Show «≈ 265 км» |
| OI-25 | Drive auto-advance with TalkBack on | No auto-advance with TalkBack |
| OI-26 | The Road ahead mockup lacks «Сохранить офлайн», «Поделиться», «Открыть день в навигаторе» and pins the Waybill button to the page bottom | Header toolbar (save, share) + day-header link + pinned footer |
| OI-30 | The mockup tag «машина под окном» is not in the closed tag list | Use «охраняемая парковка» (tag `parking_guarded`) |
| OI-31 | Stop scene loops in Battery Saver | Yes |
| OI-33 | «ВЫ: МОСКВА» is nested inside the navigator button in the mockup | Separate button; the field moves down 6 dp |

## 2. Contrast (WCAG 2.2 AA) — every text pair in the 7 mockups was measured

Measured with the WCAG relative-luminance formula on the exact hex values (semi-transparent fills resolved against their backdrop). 4.5:1 for text < 18.66 sp bold / < 24 sp; 3:1 for larger text and for UI-component indicators (1.4.11).

| # | Screen · element | Mockup pair | Ratio | Needs | Replacement token | New ratio |
| --- | --- | --- | --- | --- | --- | --- |
| OI-01 | 5.1 selected sign row, yellow 18 sp/600 | #FFD23F on rgba(255,255,255,.14) over #1E4FA3 = #3E68B0 | **3.82** | 4.5 | background `color.sign.blueSelected` #163B7A (a darker plate reads as "lit" in the dark scene; white text on it 9.81) | 7.49 |
| OI-02a | 5.2 input placeholder «Начните вводить» 18 sp/600 | #5F7487 on #16222C | **3.34** | 4.5 | `color.navi.hint` #768DA3 | 4.70 |
| OI-02b | 5.2 label «НЕДАВНО ИСКАЛИ ДРУГИЕ» 11 sp | #5F7487 on #0B1218 | **3.89** | 4.5 | `color.navi.hint` #768DA3 | 5.48 |
| OI-02c | 5.3 empty-seat label «свободно» 11 sp | #8C8C93 on #2A2A30 | **4.27** | 4.5 | `color.text.seatEmpty` #A0A0A7 | 5.49 |
| OI-02d | 5.3 gauge letter «E» 11 sp/700 | #D8402B on #0F0F11 | **4.27** | 4.5 | `color.accent.redText` #E6604A (the arc stays #D8402B) | 5.60 |
| OI-02e | 5.6 printed labels (Маршрут, Экипаж, ₽ header, footnote…) 10–11 sp | #5B7186 on #EEF2F4 | **4.49** | 4.5 | `color.paper.label` #53687C | 5.12 |
| OI-02f | 5.6 overspend (not in the mockup; SPEC says red) | #D8402B on #EEF2F4 | **3.98** | 4.5 | `color.paper.inkRed` #B3261E (also 5.93 on #F4F4F0 for the Road-ahead footer) | 5.80 |
| OI-02g | 5.7 unselected radio ring (non-text indicator) | #3A5266 on #0B1218 | **2.31** | 3.0 | `color.navi.radio` #5A7893 | 4.08 (3.50 on #16222C) |

All other pairs pass; the lowest passing ones (QA keeps them exact): «через 70 км» #8C8C93 on #161618 = 5.41; selected suggestion sub #8FA4B8 on #1A2C3B = 5.57; mirror caption on band 1 = 10.92; dog «+ пёс» #B9B9C0 on ground = 6.12; Drive CTA #141416 on #FFD23F = 12.74; stamp #5B3FA0 at 0.85 alpha = #715AAD on paper = 4.95 (decorative anyway).
New-state pairs designed here: `color.accent.redText` on #0B1218 5.51, on #161618 5.28, on #232327 4.58; `color.navi.label` on #232327 6.23; `color.text.disabled` #6C6C74 on #161618 3.47 (disabled controls are exempt).

**INFO OI-32.** The «поворотник» label (5.7) blinks down to 15 % alpha. It is decorative (hidden from TalkBack, duplicated by the icon) and exempt as incidental text; no change.

## 3. Mockup issues and fixes

| ID | Status | Issue | Fix in this package |
| --- | --- | --- | --- |
| OI-03 | FIXED | Text below the 11 sp minimum (SPEC 6): dog label 10 sp (5.3), Waybill «ФОРМА ПОЕЗДКИ · ВЕРСТА», table header, footnote 10 sp (5.6) | Raised to 11 sp (`type.caption.bold`, `type.paper.*`). The stamp's 10 sp words stay (decorative) |
| OI-05 | DECIDE | Touch targets < 44 dp: sign rows 42; back links 32; «заменить», «Выбрать отель →», «изменить» 36; front chip 40; Waybill cost lines 41.3; navigator chips 25; sign footer 18 | Visuals raised where it does not change the look: sign rows 44 (+8 dp to the sign), front chip 44, cost lines 44. Others keep their visual size with a 44 dp touch box (components §0). The Windshield navigator field moves down 6 (OI-33) |
| OI-04 | DECIDE | «НЕДАВНО ИСКАЛИ ДРУГИЕ» shows other people's searches, which SPEC 5.2 does not define (it defines local recents) and which could leak trips | Local recents first; when empty, curated «ЧАСТО ИЩУТ» chips from `/v1/config` |
| OI-06 | DECIDE | SPEC 8 has 6 lines (fuel, tolls, lodging, food, tickets, reserve); the mockup has no tolls. Also 745 × 8 / 100 × 62 = 3 695 → 3 700, not 3 720, and the total becomes ≈ 34 400, not ≈ 34 500 (the Road-ahead footer and the windshield copy use 34 500) | Add the «Платные дороги» line (0 when none, formula «нет платных участков»). Correct the demo/fixture numbers everywhere to 3 700 / ≈ 34 400, or change the demo price to 62,40 ₽ (745 × 0,08 × 62,40 = 3 719 → 3 720) and keep ≈ 34 500 — the second option keeps all approved copy. Recommended: price 62,40 ₽ |
| OI-07 | DECIDE | Crew limits 7 adults / 5 children cannot be entered with 3 back seats + front | «+ третий ряд» link adds a second bench of 3 seats (5.3 §3). Max capacity in the UI: driver + front + 6 = 8 seats, so 7 + 5 = 12 cannot all be seated; the limit check uses seats. SPEC should change the limits to «up to 8 people»; until then the UI caps at 8 |
| OI-08 | DECIDE | SPEC 7.1 sets the default mood only for children > 0 | Nothing pre-selected without children; `mood` omitted; server default `more_stops` proposed |
| OI-09 | FIXED | Navigator chips are 25 dp tall in two wrapped rows — not tappable at 44 dp without overlap | One horizontally scrolling row, chip height 36, touch 44 |
| OI-10 | FIXED | Mockups are fixed at 390 × 844; SPEC 16 requires 360–480 dp widths and font scale 130 % | Anchor rules per screen (each screen file §1): L/R insets stretch, dashboards bottom-anchored, scenes scale by k, overhead-sign row count adapts, inner scroll regions; min heights everywhere |
| OI-11 | FIXED | Drive mockup uses «~250 км» (SPEC uses «≈») and a time-based progress bar | «≈»; the bar is driven by SSE stages (5.4 §3) |
| OI-12 | FIXED | Glyph coverage: «✓», «●», «↗» are not guaranteed in IBM Plex Sans Condensed; Marck Script has no «₽», «≈», «✓» | Drawn as vectors (components §17.4); «≈» and «₽» in handwritten values are set in Plex Sans Condensed at the same size and in ink colour (the mixing is invisible at 19 sp). The font subsets must include Latin + Cyrillic + «₽ ≈ № → ↓ ↑ · « » — U+202F U+00A0» |
| OI-13 | FIXED | Exit mockup links directly to `https://travel.yandex.ru` | The link is built by `GET /v1/links/hotel` (SPEC 10) and opened outside the app; the «Забронировали?» return dialog is designed (5.7 §4) |
| OI-14 | DECIDE | Only a church/kremlin pictogram exists for tourist signs | Added `museum` and `nature` (components §17.2). Mapping: `kremlin`, `monastery` → church; `museum` → museum; `view`, `walk` → nature; anything else → church. Recommended: accept |
| OI-15 | INFO | Root background differs per mockup: #141416 (Wind, Navi, Drive, Exit) vs #161618 (Panel, Signs, Waybill) | Kept as designed: `color.dash.base` vs `color.dash.raised`, stated per screen |
| OI-16 | FIXED | Mockups use `:hover` (rows #1C1C20, links #FFE27A) — there is no hover on touch | Mapped to pressed states (`color.dash.pressed`, `color.accent.yellowPressed`) |
| OI-17 | FIXED | Mockup font loads differ (Plex Mono 500 in Wind, 500 + 600 in Panel; odometer uses 600) | Bundle Plex Sans Condensed 400/500/600/700, Plex Mono 600, Marck Script 400 (6 files, ≈ 1.1 MB subset) |
| OI-18 | INFO | Windshield: the sun (y 266–334) is fully covered by the overhead sign (ends 310 in the mockup, 318 here) and the ground. It appears only when the sign shows 2 rows on short windows | Keep it in the scene (it shows on short screens and in the sign's loading/empty states, where the plate is shorter) |
| OI-19 | FIXED | The share text is not designed | Template D-11 below |
| OI-20 | FIXED | No «Мои поездки» plate or list in the mockups (SPEC 5.1) | 5.1 §4.4 + D-1 |
| OI-21 | FIXED | Navigator panel uses `overflow: hidden`, so 6 suggestions + recents are cut off | The panel content scrolls (5.2 §1) |
| OI-22 | FIXED | The Navigator mockup ignores the keyboard, which is open on entry (КУДА focused) | IME behaviour in 5.2 §1 |
| OI-23 | DECIDE | Suggestion and caption distances before planning are straight-line (SPEC 5.2) but the mockup shows «265 км» (a road distance) | Prefix «≈» before planning |
| OI-24 | FIXED | Drive has no back affordance in the mockup; SPEC says the user can go back at any time | «Отменить» back link on the sky (5.4 B1) |
| OI-25 | DECIDE | Auto-advance after 1 s moves TalkBack users without warning | No auto-advance when TalkBack is on |
| OI-26 | DECIDE | Road ahead: secondary actions missing; Waybill button at the end of a 1980 dp page | Toolbar save/share (T1, T2), day link «в навигатор ↗», pinned footer with fade (5.5) |
| OI-27 | FIXED | Road-ahead back label «Приборы» is wrong when opened from «Мои поездки» | «К лобовому» in that case |
| OI-28 | FIXED | The car marker moves across the full page (CSS `top: 0 → 100%`), which a lazy list cannot measure | Moves across the visible road at the same speed (124 dp/s) |
| OI-29 | INFO | SPEC 5.5 lists tags as a row element; the mockup writes them into the note | Kept as the mockup (tags inside the sentence, generated by the server) |
| OI-30 | DECIDE | «машина под окном» is not a closed-list tag | «охраняемая парковка» |
| OI-31 | DECIDE | Battery Saver behaviour is not specified | Scene loops stop; one-shots run (motion.md §4.5) |
| OI-33 | DECIDE | The mockup nests «ВЫ: МОСКВА» inside the navigator link, but SPEC 5.1 gives it its own action (location permission). Nested touch targets are not allowed | Separate button with a 44 dp touch box; the field below moves from y 580 to 586 so the touch boxes do not overlap |
| OI-34 | FIXED | The Exit sign's distance format is not defined | «800 м» below 1 km (to 100 m), «1,2 км» above (components §12.1) |
| OI-35 | FIXED | SPEC «Settings (gear icon on the dashboard)» has no place in the Instruments mockup, nor do the mood chips | Mood chips N1–N2 and the «Машина и выезд» plate N3 in the empty band y 529–703 (5.3) + sheet D-4 |
| OI-36 | FIXED | MapLibre draws labels from server-side SDF glyphs, not from the APK fonts, so the map would fall back to Noto Sans | Generate PBF glyph ranges (Latin + Cyrillic) for IBM Plex Sans Condensed 400/600 on the Planetiler/tile server and reference them in the style JSON |
| OI-37 | DECIDE | The engine share text (architecture §8.2) has no dates, crew line or per-person amount; the earlier design draft had them | Ship the engine format now (D-11 updated); add `share.dates` / `share.crew` / `share.per_person` to `strings.ru.json` in a later sprint if wanted |
| OI-38 | DECIDE | Engine cost-line titles differ from the approved Waybill (copy-ru.md §13 R-1) | Developer changes `strings.ru.json`: «Питание», «Резерв {pct}%», «Бензин {fuel_type}», reserve sub-line without «10%» |

## 4. Designed missing states and screens

All of these use only existing tokens and components.

### D-1 «Мои поездки» (saved trips) — `BottomSheet`

```
┌─────────────────── ▬ ───────────────────┐
│ Мои поездки                         [×]  │ type.title.lg
│ 3 сохранённые · открываются без сети     │ type.body.sm text.secondary
│┌────────────────────────────────────────┐│
││ ↗ Золотое кольцо              ≈ 30 500 ₽ ││ row min-h 64, fill dash.controlAlt, radius 10
││   7–9 ноября · 3 дня · 2 взр · 1 реб · пёс│ type.body.sm text.secondary
│└────────────────────────────────────────┘│ gap 8
││ ↑ Москва → Ярославль          ≈ 18 200 ₽ ││
││   14 ноября · 1 день · 2 взр              ││
│└────────────────────────────────────────┘│
└──────────────────────────────────────────┘
```
- Row: padding 10 12; arrow 18 (bearing of the trip, `stroke.icon.sign`, `color.sign.white`) in a 32 × 32 `color.sign.blue` plate, radius 4; name `type.title.sm`; amount `type.body.mdStrong` `color.accent.yellow`; meta line below. Pressed `color.dash.pressed`.
- Tap → Road ahead (5.5, back label «К лобовому»).
- Delete: long-press or TalkBack action «Удалить» → `NaviDialog` «Удалить поездку «Золотое кольцо»?» / «Она пропадёт с этого телефона» / primary «Удалить» (yellow) / secondary «Оставить». After deleting: toast «Поездка удалена» + «Вернуть» (6 s).
- At ≥ 45 trips: a line under the subtitle «Сохранено 45 из 50 — удалите старые, чтобы освободить место» in `color.accent.redText`.
- Order: by start date, upcoming first, then past (past rows show meta in `color.text.muted`).
- TalkBack: pane «Мои поездки»; row «Золотое кольцо, 7–9 ноября, 3 дня, примерно 30 500 рублей. Открыть».

### D-2 Location rationale and denial — 5.1 §4.9.

### D-3 Map picker («точка на карте») — full-screen modal over 5.2

```
┌──────────────────────────────────────────┐
│ ← Отмена                    [⊕] [моё место]│ top bar h 56 on dash.base, back link muted
├──────────────────────────────────────────┤
│                                          │
│           MapLibre, dark style           │
│                  ▼ pin                   │ pin centred (tip at the map centre)
│                                          │
│                              [+]         │ zoom keys 44 × 44 StepperKey style
│                              [−]         │ right 14, vertically centred
├──────────────────────────────────────────┤
│┌ NaviPanel ─────────────────────────────┐│ L14/R14, bottom 24
││ ТОЧКА НА КАРТЕ                          ││ type.label.md navi.label
││ Ростов Великий, ул. Ленинская           ││ type.title.lg (loading: «Ищем адрес…»)
││ Ярославская область · ≈ 190 км от вас   ││ type.body.sm navi.labelSecondary
││ [ Выбрать эту точку               → ]   ││ PrimaryCta h 52
│└─────────────────────────────────────────┘│
└──────────────────────────────────────────┘
```
- Map style (custom MapLibre style JSON using tokens): background/land `color.navi.screen`, water `color.navi.list`, parks `color.scene.groundNight`, roads `color.navi.fieldBorder` (motorways `color.navi.dashed`), labels `color.navi.text` with a halo of `color.navi.screen`; label font IBM Plex Sans Condensed served as PBF glyphs by the tile server (OI-36).
- Pin: `pin` icon 36 × 36, fill `color.accent.yellow`, stroke 2 `color.text.onLight`, shadow `shadow.signMd`; while the map moves it lifts 8 dp (150 ms, `easing.decelerate`) and the panel title shows «…»; on idle (300 ms after the camera stops) → `GET /v1/geocode/reverse`.
- «моё место»: 44 × 44 key with the `locate` icon; moves the camera to the device location (permission flow as 5.1 §4.9).
- States: loading address «Ищем адрес…» (CTA enabled — the coordinates are enough); reverse failure «Точка на карте» + coordinates «57.1856, 39.4146» (CTA enabled); outside Russia «Сюда маршрут не строим — только по России» (CTA disabled); offline: map area `color.navi.screen` with offline icon 24 + «Карта работает только с интернетом» centred, CTA disabled.
- TalkBack: the map is a single node «Карта. Двигайте карту, чтобы поставить точку»; after each idle, the address is announced politely; zoom keys «Приблизить» / «Отдалить».
- Transition: `motion.screen.overlay`; «Выбрать эту точку» returns to 5.2 with КУДА (or the active via / ОТКУДА) set.

### D-4 «Машина и выезд» (settings) — `BottomSheet` from 5.3

```
Машина и выезд                                    [×]
РАСХОД, Л НА 100 КМ        [−]  8,0  [+]          StepperKey 52×44; value type.title.lgNum
ТОПЛИВО                    [АИ-92][АИ-95][ДТ]      segmented, each min 72×44
БАК, Л                     [−]  50   [+]
ВЫЕЗД                      сб 7 · вс 8 · пн 9 …    day chips, horizontal scroll (14 days)
                           [−] 08:00 [+]           step 30 min, 00:00–23:30
Избегать платных дорог                    [ ●  ]   switch 52×32
Политика конфиденциальности ↗                      type.body.sm navi.label (external browser)
[ ГОТОВО ]                                         YellowButton h 56
```
- Labels `type.label.md` `color.text.muted`; rows min-h 56, dividers 1 `color.dash.control`.
- Ranges: consumption 4,0–20,0 step 0,5 (decimal comma); tank 20–120 step 5 (SPEC gives only the default 50 — range proposed); start date default next Saturday, time default 08:00.
- Segmented: track `color.dash.controlAlt` radius 10; selected segment fill `color.sign.white`, text `color.text.onLight`; others `color.text.secondary`; `type.body.mdStrong`.
- Day chips: `MoodChip` style, content «сб 7»; today «сегодня».
- Switch: track 52 × 32 radius 16, off `color.dash.controlAlt` + thumb 24 `color.text.secondary`; on `color.accent.yellow` + thumb `color.text.onLight`; thumb moves 20 dp in 200 ms `standard`. TalkBack Switch «Избегать платных дорог».
- Values persist on change; «Готово» closes the sheet. The plate N3 summary updates: «АИ-95 · 8,0 л · сб 08:00».

### D-5 Stop menu and navigator chooser — `BottomSheet` from 5.5

```
Троице-Сергиева лавра                            [×]
Через 70 км · 09:15
ОТКРЫТЬ В НАВИГАТОРЕ ОТСЮДА
[▲ Яндекс Навигатор                         ↗]     rows min-h 52, only installed apps
[▲ Яндекс Карты                             ↗]
[▲ 2ГИС                                     ↗]
────────────────────────────────────────────
[ Заменить ]                                       only for replaceable stops
[ Сообщить об ошибке ]
```
- App rows: `navigator` icon 20 `color.navi.label` (we do not draw partner logos — no brand marks), name `type.list.title`, `external` icon 16. Pressed `color.dash.pressed`.
- None installed: one row «Навигатор не установлен» + link «Установить Яндекс Навигатор из RuStore» (`color.accent.yellow`).
- Offline: app rows disabled, sub-line «Нужен интернет».
- The day link «в навигатор ↗» opens the same sheet with title «День 1 в навигаторе» and only the app rows.
- The chosen app is remembered: next time the sheet marks it «последний раз».

### D-6 Replace stop — `BottomSheet` from «заменить»

```
Заменить: Обед · Переславль-Залесский            [×]
Варианты в то же время, ± 45 минут
(●) Кафе у Плещеева озера            сейчас        HotelOption-style radio rows on dash.controlAlt
    есть детское меню · парковка                   radio ring text.secondary / selected yellow
( ) Трапезная у монастыря        +10 мин · +300 ₽
    детское меню · можно с собакой
( ) Столовая на трассе           −15 мин · −600 ₽
    парковка · быстро
[ ЗАМЕНИТЬ ]                                       YellowButton h 56, disabled until another row is selected
Оставить как есть                                  text button 44, text.secondary
```
- Each alternative row shows the mini sign of its kind at 0.7 scale (service 35 × 43) at the left, a name `type.title.sm`, tags `type.body.sm` `color.text.secondary`, and the delta `type.body.mdStrong` `color.text.primary` (no colour coding: green is reserved for the turn signal; the signs «+»/«−» carry the meaning).
- After «Заменить»: the sheet closes, the row updates, a row flash plays, toast «Заменили. Путевой лист: ≈ 30 800 ₽» + «Вернуть» (6 s). Server confirm failure: toast «Замену сохраним на сервере, когда появится сеть».
- No alternatives (offline, not cached): the «заменить» button is disabled (components §2.6).

### D-7 Report an error — `BottomSheet` from D-5

```
Что не так с местом?                             [×]
( ) Закрыто или не работает
( ) Неверно: с собакой, детское меню, парковка
( ) Другая цена
( ) Другое
[ Комментарий, если хотите        ]                 NaviInput style, optional, max 280
[ ОТПРАВИТЬ ]                                       YellowButton, disabled until a reason is chosen
```
Success toast «Спасибо, проверим». Offline: «Отправим, когда появится сеть» (queued). Event `feedback_sent`.

### D-8 Offline Windshield — 5.1 §4.5 (with and without cache).

### D-9 Trip Pro waitlist — 5.6 §4.

### D-10 «Забронировали?» — 5.7 §4.

### D-11 Share text (SPEC US-14)
The format is the engine contract (architecture §8.2, `strings.ru.json` `share.*`), so the app and the server produce identical text offline:
```
Золотое кольцо · 745 км · 3 дня
День 1 · 265 км
08:00 Москва
09:15 Троице-Сергиева лавра
12:00 Обед · Переславль-Залесский
14:30 Ростовский кремль
15:50 АЗС перед Ярославлем
16:30 Ночёвка · Ярославль
…
Итого ≈ 30 500 ₽ на 3 чел.
https://verst.app/s/<slug>
```
Plain text; thin spaces are replaced by normal spaces for messengers that strip U+202F. (Supersedes the earlier draft with dates, crew line and per-person amount; those can be added to `share.*` later if the Manager wants them — OI-37.)

### D-12 Loading, empty and error states per screen
Defined in each screen file §4 (5.1 loading / empty / offline / error; 5.2 suggestions loading / no results / error / offline; 5.4 slow / warning / error codes / offline; 5.5 price refresh / offline / warning / storage full; 5.6 over budget / no budget / saved / sync failure; 5.7 link loading / error / offline / booked).
