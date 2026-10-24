# Verst — Component specification (design v5 «За рулём»)

Version 1.0.0 · 2026-10-23 · Owner: Designer
Source of truth for visuals: `docs/design-canvas/*.dc.html`. Source of truth for values: `design/tokens.json` (mirrored 1:1 in `DesignTokens.kt`). Every colour, type style, radius, stroke, shadow and motion named here is a token path. Write it in Kotlin as `DesignTokens.<path>`, for example `color.sign.blue` → `DesignTokens.color.sign.blue`.

## 0. Conventions used in every spec

| Rule | Value |
| --- | --- |
| Unit mapping | 1 CSS px in the mockups = 1 dp; font px = sp. Measured in headless Chromium from the mockup DOM |
| Reference frame | 390 × 844 dp. This is the app window **below the status bar and above the gesture/navigation bar**. Scenes and dashboards draw edge-to-edge behind both bars (see 0.2) |
| Coordinates | `x, y` = top-left of the element's **visual** box in screen dp; `w × h` = visual size |
| Touch box | If a visual box is < 44 dp in either axis, its **touch box** is 44 dp in that axis, centred on the visual box. Implement it with a 44 dp layout box that draws the smaller visual centred inside, so layout positions shift by ≤ 4 dp (within tolerance) |
| Line height | IBM Plex Sans Condensed "normal" line height = 1.3 × size (ascender 1025 + descender 275 per 1000 em). All `type.*` tokens carry explicit line heights; `includeFontPadding = false`, `LineHeightStyle(Center, Trim.None)` |
| Numbers | Thousands separator U+202F (narrow no-break space): «34 500». Between number and unit, U+00A0: «745 км», «6 000 ₽». «≈» + U+00A0 before estimates. 24-hour time «08:00». Tabular figures (`tnum`) wherever `type.*` says so |
| Uppercase | Uppercase labels are written in uppercase in string resources (not with `textTransform`), so TalkBack reads words, not letters. The letter-spacing comes from the token |
| Focus | Keyboard/D-pad focus ring: 2 dp `color.overlay.focus`, 2 dp outside the visual box, following its corner radius + 2 |
| Pressed | Every pressable has a pressed state within 1 frame. No ripple anywhere (no Material look): use `indication = null` and draw the pressed state described per component |
| Disabled | Glyph/text `color.text.disabled`. Fill stays, no alpha fades. `Modifier.semantics { disabled() }` |
| Reduced motion | `LocalReducedMotion` (true when `Settings.Global.ANIMATOR_DURATION_SCALE == 0f` or the accessibility "Remove animations" setting is on). Every animated component documents its static frame |
| Font scale | Up to 130 %: text containers have **min** heights, never fixed heights; single-line names ellipsize, notes wrap. Visual boxes listed below are at 100 % |

### 0.1 Compose drawing approach (general)

- **Canvas** (`Modifier.drawWithCache` + `onDrawBehind`) for anything decorative or scene-like: sky, sun, hills, road, posts, pillars, liner, mirror glass and silhouettes, sign plates and borders, pictograms, gauges, stamp. Build `Path`s once in `drawWithCache`. The draw lambda reads animated values through `State` so only the draw phase is invalidated (no recomposition per frame).
- **Composables** (`Box`/`Row`/`Column` + `BasicText`) for text and every interactive element, so semantics, focus and font scaling work.
- SVG pictograms are converted once to `ImageVector` (`androidx.compose.ui.graphics.vector.PathParser`) from the path data in §17 and drawn with `rememberVectorPainter`. The stroke width comes from `stroke.icon.*`, with round caps and joins.
- No `androidx.compose.material*` imports in `:core-ui` except `material3` accessibility primitives, if any are ever needed.

### 0.2 System bars

- Status bar: transparent, light icons. The scene behind it is filled with the colour of the topmost scene element at that x: `color.interior.liner` on scene screens (Windshield, Drive, Exit), `color.sky.band1` on strip screens (Navigator, Instruments, Road ahead), `color.dash.raised` on Waybill.
- Navigation bar: transparent, light icons; filled by the dashboard colour of the screen (`color.dash.base` or `color.dash.raised`).
- Bottom-pinned elements (start buttons, CTAs, footers) sit at their mockup distance above the **navigation bar inset**.

---

## 1. OverheadSign

GOST blue gantry sign. Two sizes are used:

| Variant | Where | Outer padding | Outer radius | Inner border | Inner radius | Shadow |
| --- | --- | --- | --- | --- | --- | --- |
| `OverheadSign.List` | Windshield 5.1, "ещё N маршрутов" sheet | 4 | `radius.r9` | `stroke.w2` `color.sign.white` | `radius.r6` | `shadow.signLg` |
| `OverheadSign.Title` | Road ahead 5.5 header | 3 | `radius.r7` | `stroke.w2` `color.sign.white` | `radius.r5` | `shadow.signMd` |

Plate fill `color.sign.blue`. The plate is a `Box` with a Canvas background: an outer rounded rect, then the inner border as a stroked rounded rect inset by the outer padding + 1 dp (the stroke centre).

### 1.1 `OverheadSign.List` anatomy (Windshield values)

```
┌ outer plate 350 wide, x 20, y 84, h 234 ────────────────────────┐
│┌ inner border (2) ─────────────────────────────────────────────┐│
││ header  РЯДОМ С ВАМИ · ИЗ МОСКВЫ                         КМ   ││  18 (14 text + 4)
││ row     [↗22] Золотое кольцо                             745  ││  44
││ row     [↑22] Ярославль                                  265  ││  44
││ row     [↗22] Суздаль · Владимир                         220  ││  44
││ row     [↓22] Тула · Ясная Поляна                        200  ││  44
││ footer  ещё 14 маршрутов в радиусе 300 км ↓                    ││  18 visual / 44 touch
│└───────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

| Part | Spec |
| --- | --- |
| Content inset | Inner border inner edge + padding 6 / 6 / 4 (top / sides / bottom). Content box x 32…358 (326 wide) |
| Header | Padding 0 6 4. Left: «РЯДОМ С ВАМИ · ИЗ <ГОРОД>» (town in the genitive, uppercase), right: «КМ». `type.label.md`, `color.sign.blueText`. Not focusable (`heading()` semantics on the left text) |
| Row | Visual 326 × **44** (mockup 42, raised to the 44 touch minimum, see OI-05). Padding 0 6; arrow 22 × 22 at x+6, vertically centred; gap 10; name `type.sign.lg`, flex 1, single line, ellipsis; km `type.sign.lg` right-aligned, tabular, ends 6 dp from the content edge. Row radius `radius.r4` |
| Footer | «ещё N маршрутов в радиусе 300 км ↓» (plural: маршрут / маршрута / маршрутов; hidden when N = 0), `type.caption.md`, `color.sign.blueText`, padding 3 6 1 (mockup). Visual height 18.3. Touch box 44: from the footer top down 44 dp; the part below the plate falls over the decorative scene, which has no touch targets |
| Total | 12 (top) + 18 + 4 × 44 + 18 + 10 (bottom) = **234** → y 84…318 (mockup 84…310; +8 dp from the 44 dp rows, documented in OI-05) |

**Row states**

| State | Background | Arrow + text | Transition |
| --- | --- | --- | --- |
| default | transparent | `color.sign.white` | — |
| pressed | `color.sign.bluePressed` | unchanged | immediate |
| selected | `color.sign.blueSelected` (AA fix, OI-01) | `color.accent.yellow` | `motion.selection` (200 ms colour cross-fade on background, arrow and text) |
| selected + pressed | `color.sign.bluePressed` | `color.accent.yellow` | immediate |
| disabled | n/a (rows are never disabled) | | |
| loading | Row replaced by a placeholder: arrow slot = 22 × 22 plate `radius.r4`; name plate 60 % of the name width × 14, `radius.r4`; km plate 30 × 14. Fill `color.sign.plate`, shimmer `color.sign.plateHighlight` (§16) | | `motion.shimmer` |
| offline (cached rows) | Rows as default. Header right text «КМ» is replaced by the `OfflinePlate` content: offline icon 11 × 11 + «НЕТ СЕТИ», `type.label.md`, `color.sign.blueText` (red text fails on blue, so blue-text is used here) | as default | — |

**TalkBack**

- Row: role Button, `stateDescription` «выбран» / none. Content description: «<Name>, <km> километров, <direction>. <meta>». Example: «Золотое кольцо, 745 километров, на северо-восток. 3 дня, 8 городов, по кругу». Directions: на север / на северо-восток / на восток / на юго-восток / на юг / на юго-запад / на запад / на северо-запад. Click label (`onClickLabel`): «выбрать маршрут».
- Footer: role Button, «Ещё 14 маршрутов в радиусе 300 километров. Открыть список».
- Header: heading «Рядом с вами, из Москвы».

**Compose approach:** the plate, border and shadow on Canvas (`drawWithCache`; the shadow is a blurred rounded-rect drawn with `Paint.asFrameworkPaint().setShadowLayer(18dp, 0, 8dp, black@35%)` under the plate). Rows are a `Column` of `Row` composables with `Modifier.selectable(selected, role = Role.Button)`. Arrows are `ImageVector`s from §17.1 with stroke `stroke.icon.sign` (3 dp).

### 1.2 `OverheadSign.Title` anatomy (Road ahead)

x 20, y 56, w 350, h 49. Inner border padding 6 10. Row: arrow 20 × 20 (`stroke.icon.sign`, `color.sign.white`), gap 8, trip name `type.sign.xl`, flex 1, single line, ellipsis; km `type.sign.xl` right-aligned. No states (not interactive). TalkBack: heading «<Trip name>, <km> километров».

---

## 2. RoadSign

Itinerary sign mounted next to the vertical road (Road ahead), also used on the flying signs (Drive) and the replace sheet. Drawn on Canvas inside a fixed-size `Box`; the text inside the city variant is a `BasicText` overlay.

### 2.1 Variants and exact geometry (Road ahead size)

| Variant | Stop kinds | Visual box | Construction |
| --- | --- | --- | --- |
| `city` | start, finish, town | 64 × min 40 (68 × min 44 including the white outline) | Plate `color.sign.white`, border `stroke.w3` `color.sign.black` (inside), outline `stroke.w2` `color.sign.white` **outside** the border, radius `radius.r4`. Text: town name in uppercase, `type.sign.city`, `color.text.onLight`, centred, padding 3 2, up to 3 lines, no ellipsis (the sign grows vertically) |
| `tourist` | sight | 56 × 56 | Plate `color.sign.brown`, radius `radius.r5`; inner border inset 3, `stroke.w2` `color.sign.white`, radius `radius.r3`; pictogram 30 × 30 centred, stroke `stroke.icon.thin`, `color.sign.white` |
| `service` | fuel, food, rest, hotel | 50 × 62 | Plate `color.sign.blue`, radius `radius.r4`, padding 5; white square 40 × 40 `color.sign.white`, radius `radius.r2`, at (5, 5); pictogram 28 × 28 centred in it, stroke `stroke.icon.pictogram`, `color.sign.black`; gap 4; bar 22 × 3 `color.sign.white`, radius `radius.r2`, centred at y 49 |

GOST references: fuel = 7.3, food = 7.7, rest area = 7.11, hotel = 7.12 (pictogram «гостиница или мотель»). The tourist sign follows the brown 6.x tourist style.

### 2.2 Flying-sign size (Drive)

| Variant | Box | Construction |
| --- | --- | --- |
| `direction` (blue, town + km) | 156 × 53.5 (content-sized) | Plate `color.sign.blue`, radius `radius.r6`, padding 3; inner border `stroke.w2` white, radius `radius.r4`, padding 6 8; name `type.sign.md` (up to 2 lines, break at the space nearest the middle), gap 8, km `type.sign.lgBold` right |
| `tourist` | 156 × 51.4 | Plate `color.sign.brown`, as above; pictogram 26 × 26 white `stroke.icon.thin`; gap 8; name `type.sign.sm`, 2 lines |
| `service` | 156 × 50 | Plate `color.sign.blue`; padding 5 8 in the border; pictogram plate 30 × 30 white `radius.r2` with pictogram 22 × 22 black `stroke.icon.pictogram`; gap 8; text `type.sign.sm`, 2 lines: «<Town>» / «<kind word>» (ночёвка, заправка, обед, отдых) |

Width 150 + 2 × 3 padding = 156 for all flying signs. Height hugs the content.

### 2.3 States

Signs themselves are not interactive. The **row** that holds them is (§2.5). Sign-level visual states:

| State | Visual |
| --- | --- |
| default | as above |
| unverified («не проверено») | The sign is drawn identically, so the sign language stays honest; the row shows the «не проверено» marker (§2.5) |
| booked (hotel) | Hotel service sign gets a 14 dp yellow badge at the top-right corner (centre at +46, +4) with a black check (§17.4 `check`, stroke 2) |
| loading | Placeholder: same outer box, fill `color.dash.controlAlt`, radius as the variant, shimmer `color.dash.outline` |

### 2.4 TalkBack

Signs are `clearAndSetSemantics {}` (decorative); the row speaks for them (§2.5).

### 2.5 Stop row (`StopRow`) — the row that carries a RoadSign

Grid: column A 0…72 (road + connector), column B 72…140 (sign, centred), column C 140…374 (text; padding-left 4 → text 144…374, 230 wide). Row padding: top 8, bottom 12, right 16.

| Part | Spec |
| --- | --- |
| Connector stub | 14 × 3 at x 60, y row top + 38, `color.interior.pole` |
| Line 1 | Left: «старт» / «через N км» (+ « · не проверено» when `verified = false`); right: arrival «09:15». `type.body.sm`, `color.text.muted`, tabular. Height 15.6 |
| Name | gap 3; `type.title.md`, `color.text.primary`; wraps up to 2 lines, then ellipsis |
| Note | gap 3; `type.body.md`, `color.text.note`; wraps, no limit |
| Excursion (NEW, only if the sight has `tripster_id`) | gap 3; link «Экскурсия от 1 900 ₽ ↗» `type.body.mdStrong`, `color.navi.label`; visual height 20, touch 44 |
| Actions line | gap 3 + margin 2; left: cost `type.body.mdStrong`, `color.accent.yellow` («вход свободный», «≈ 1 800 ₽», «0 ₽»); right: action button (§2.6). The line is omitted when there is no cost and no action (city rows) |

Row states: default transparent; pressed (long-press in progress) `color.dash.pressed`; offline — action buttons show their offline state (§2.6).

TalkBack, one node per row (merge descendants, exclude the action buttons, which stay separately focusable):
«<через 70 км | Старт>, <09:15>, <Троице-Сергиева лавра>. <note>. <cost>.»
SPEC 16 example: «Через 70 км, 09:15, Троице-Сергиева лавра». The kind is prefixed for service rows: «Заправка: АЗС перед Ярославлем», «Обед: …», «Отдых: …», «Ночёвка: Ярославль». Custom accessibility actions (replace long-press for TalkBack): «Открыть в навигаторе отсюда», «Заменить», «Сообщить об ошибке».

### 2.6 Row action buttons

| Button | Visual | Text | States |
| --- | --- | --- | --- |
| `SwapButton` «заменить» | h 36 (touch 44), padding 0 10, radius `radius.r8`, border `stroke.w1` `color.dash.outline`, transparent | `type.body.smStrong` `color.text.secondary` | pressed: fill `color.dash.pressed`; loading (replace confirming): text replaced by 3 dots 4 dp `color.text.secondary`, blinking in sequence 300 ms; offline without cached alternatives: text `color.text.disabled`, tap shows toast «Нужен интернет» |
| `HotelButton` «Выбрать отель →» | h 36 (touch 44), padding 0 12, radius `radius.r8`, fill `color.sign.blue` | `type.body.mdStrong` `color.text.primary` | pressed: `color.sign.bluePressed`; booked: text «Забронировано ✓» (check drawn, §17.4); offline: enabled (the Exit screen is readable offline) |

TalkBack: «Заменить: <name>» (mockup aria-label), «Выбрать отель в <town>».

---

## 3. Mirror

### 3.1 `Mirror.Small` (Windshield; read-only crew summary)

| Part | x, y (screen) | Size | Spec |
| --- | --- | --- | --- |
| Stem | 191, 8 | 8 × 10 | `color.dash.controlAlt` |
| Body | 120, 18 | 150 × 44 | Rounded rect `radius.r22`, bezel `stroke.w3` `color.dash.controlAlt` (inside), glass `color.mirror.glass`. Clip all content to the inner rounded rect (x 123…267, y 21…59, radius 19) |
| Reflected sky | 123, 21 | 144 × 20 | `color.sky.band2` |
| Reflected ground | 123, 41 | 144 × 22 (clipped to 18) | `color.scene.groundDay` |
| Adult silhouette 1 | box 141, 33 | 26 × 26 | Head circle d 12 at (148, 33); body 24 × 12 at (142, 46), top corners radius 10, bottom square. Fill `color.mirror.glass` |
| Child silhouette | box 183, 39 | 20 × 20 | Head d 9 at (188.5, 39); body 18 × 10 at (184, 49), top radius 8 |
| Adult silhouette 2 | box 217, 33 | 26 × 26 | as adult 1 at (224, 33) / (218, 46) |
| Dog | body 245, 41 | 14 × 12 | radius 6 6 4 4; ears 4 × 6 radius 2 at (254, 38) rotated −20° and (246, 38) rotated +20° (pivot = ear centre) |
| Glare | box 103, 11 | 60 × 70 | `color.mirror.glare` (white 8 %), rotated 25° about its centre (133, 46), clipped to the glass |
| Caption | centred at x 195, y 65 | h 14.3 | crew summary «2 взр · 1 реб · пёс», `type.caption.strong`, `color.mirror.label`, shadow `shadow.mirrorText` |

**Silhouette layout rule (data-driven).** The silhouettes show the actual crew, read left to right in the glass. Slots are centred at x = 154, 193, 230 (the mockup centres). The adults (excluding the driver, max 3 shown) fill from the outer slots inward, children take the remaining slots, and the dog is always at the right if present. More than 3 passengers: the 3 slots show the first 3, and the caption carries the full count.

Caption copy: «<A> взр» + « · <C> реб» if C > 0 + « · пёс» if dog. Driver-only: «1 взр».

States: default; pressed — the whole group translates +1 dp in y; offline — no change. Animation: `motion.mirrorSway` (±1.5° about the top centre of the stem, (195, 8)). Reduced motion: 0°.

Touch: the whole group x 120…270, y 8…78 (150 × 70) is one button. TalkBack (mockup aria-label): «Экипаж в зеркале: 2 взрослых, 1 ребёнок, собака. Изменить». The spoken form uses full words.

Compose: one `Canvas` 150 × 56 for stem + body, and a `BasicText` caption below; `Modifier.clickable(role = Role.Button)`; `graphicsLayer { rotationZ = sway; transformOrigin = TransformOrigin(0.5f, 0f) }`.

### 3.2 `Mirror.Large` (Instruments; crew editor)

| Part | x, y | Size | Spec |
| --- | --- | --- | --- |
| Stem | 180, 0 (extends behind the status bar) | 30 × 58 | `color.dash.controlAlt` |
| Body | 20, 54 | 350 × 174 | radius `radius.r40`, bezel `stroke.w5` `color.dash.controlAlt`, glass `color.mirror.glass`, shadow `shadow.mirror`. Inner content 340 × 164 at (25, 59), clip radius 35 |
| Reflected sky | 25, 59 | 340 × 54 | `color.sky.band2` |
| Reflected ground | 25, 113 | 340 × 22 | `color.scene.groundDay` |
| Reflected road | 160, 113 | 70 × 22 | Trapezoid: top x 188…202, bottom x 160…230, `color.scene.road` |
| Back bench | 25, 139 | 340 × 84 | `color.dash.bench` |
| Seats | 41 / 146.3 / 251.7, 145 | 97.3 × 68 each, gap 8 | §3.3 |
| Dog button | 283, 85 | 56 × 52 | §3.4 |

### 3.3 Seat button (`SeatButton`)

Shape: rounded rect radius 14 14 6 6 (`radius.r14` top, `radius.r6` bottom), border `stroke.w2`. Content: a column aligned to the bottom, padding-bottom 4, gap 2: silhouette (if filled) and label `type.caption.strong`.

| State | Fill | Border | Silhouette | Label (copy, colour) |
| --- | --- | --- | --- | --- |
| empty | transparent | dashed 2 (dash 6, gap 4) `color.dash.outlineDashed` | none | «свободно», `color.text.seatEmpty` (AA fix, OI-02) |
| adult | `color.dash.outline` | solid `color.dash.outline` | head d 22 + body 44 × 22 (top radius 22), gap 2, `color.crew.adult` | «взрослый», `color.text.primary` |
| child | `color.dash.outline` | solid `color.dash.outline` | head d 16 + body 32 × 16 (top radius 16), gap 2, `color.crew.child` | «ребёнок», `color.text.primary` |
| pressed | as the current state, content translated +1 dp in y | | | |
| disabled (limit reached, NEW) | as empty | dashed `color.dash.outlineDashed` | none | «нет мест», `color.text.disabled`; tap → toast «В машине до 8 человек вместе с вами» (decisions.md OI-07: adults + children ≤ 8, adults ≥ 1) |

Cycle on tap: empty → adult → child → empty (skipping a state that would exceed a limit). State changes cross-fade fill, border and silhouette over `motion.selection`.

TalkBack (mockup aria-label pattern): «<Левое | Среднее | Правое> кресло: <свободно | взрослый | ребёнок>. Нажмите, чтобы изменить». For the third row (OI-07): «Третий ряд, левое кресло: …». After a change, announce the new crew summary through the polite live region (§ screen 5.3).

### 3.4 Dog button (`DogToggle`)

Box 56 × 52, transparent. The dog body is a 32 × 26 rounded rect (radius 14 14 10 10) at (+12, +14) of the box. The ears are 9 × 14 rounded rects (radius 5) positioned **relative to the body's top-left** (mockup `left: 6px; top: -6px` / `right: 6px`): (+6, −6) rotated −18° and (+17, −6) rotated +18°, pivot at the ear centre — at 390 × 844 the body is (295, 99) and the ears are at (301, 93) and (312, 93), overlapping the body top by 8 dp. (Corrected in the slice-2 review: «(+41, −6)» was box-relative and detached the ears.) Label centred at the bottom (−2 dp), `type.caption.bold` (11 sp; mockup 10 sp, OI-03).

| State | Body | Ears | Label | Motion |
| --- | --- | --- | --- | --- |
| on | fill `color.crew.dog` | fill `color.crew.dog` | «пёс», `color.text.primary` | `motion.dogWag` (±6°, pivot bottom centre of the body) |
| off | dashed 2 `color.text.muted`, no fill | hidden | «+ пёс», `color.text.secondary` | none |
| pressed | translate +1 dp y | | | |

TalkBack (mockup): on — «Собака едет. Нажмите, чтобы убрать»; off — «Собаки нет. Нажмите, чтобы взять». Role Switch, `toggleableState`.

---

## 4. Odometer

Well content (Instruments). Frame 113 × 42, fill `color.dash.odometerFrame`, radius `radius.r6`, padding 4, gap 3. Four drums 24 × 34 (`size.drumW` × `size.drumH`), radius `radius.r3`; drums 1–3 fill `color.dash.face`, digit `color.text.primary`; drum 4 fill `color.sign.white`, digit `color.text.onLight`. Digit style `type.odometer`, centred. The value is zero-padded to 4 digits («0300»).

Roll animation `motion.odometerRoll`: only drums whose digit changes animate. Increase: the old digit moves up out of the drum (0 → −34 dp) while the new digit moves in from +34 → 0; decrease: the reverse. The drum clips its content. Reduced motion: instant swap.

States: default; at minimum 150 / maximum 900 → the matching key is disabled (§5); loading — not applicable.

TalkBack: the frame is one node, `liveRegion = Polite`: «300 километров в день» (mockup aria-label «{{km}} километров в день»). Not focusable separately from the well heading.

Compose: `Row` of 4 `Box(size 24×34).clipToBounds()`, each with an `AnimatedContent(targetState = digit, transitionSpec = slideInVertically + slideOutVertically, 300 ms, easing.decelerate)`.

## 5. Key (− / +) — `StepperKey`

52 × 44 (`size.keyW` × `size.keyH`), radius `radius.r10`, fill `color.dash.controlAlt`, inner bottom edge `shadow.key` (a 3 dp band of `color.dash.keyShadow` clipped to the shape). Glyph «−» (U+2212) / «+», `type.button.glyph`, `color.text.primary`.

| State | Spec |
| --- | --- |
| pressed | content and shape translate +1 dp y; inset shadow `shadow.keyPressed` (2 dp) |
| disabled | glyph `color.text.disabled`, no inset shadow, no press |
| long-press | auto-repeat after 400 ms, every 150 ms |

TalkBack (mockup): «Меньше на 50 км» / «Больше на 50 км»; «Уменьшить бюджет» / «Увеличить бюджет». Disabled: «… — недоступно» is added by the `disabled()` semantics.

## 6. FuelGauge

Box 130 × 62 (`size.gaugeW` × `size.gaugeH`), Canvas. Arc centre (65, 58), radius 53.

| Part | Spec |
| --- | --- |
| Track | Path `M12 58 A53 53 0 0 1 118 58`, stroke 8, butt caps, `color.dash.controlAlt` |
| E zone | Path `M12 58 A53 53 0 0 1 30 18` (180° → 131.2°, 48.8° sweep), stroke 8, `color.accent.red` |
| Letter E | baseline-left at **(20, 56)** — inside the arc, clear of the 8 dp track (the mockup's (8, 46) sits on the red E zone and disappears; final review), drawn **above** the track, `type.caption.bold`, `color.accent.redText` (AA fix, OI-02); copy `instruments_gauge_empty` |
| Letter F | baseline-left at **(103, 56)**, drawn above the track, `type.caption.bold`, `color.text.primary`; copy `instruments_gauge_full` |
| Needle | 4 × 48 rounded rect (radius 2) `color.accent.yellow`; its bottom centre sits at the pivot (65, 58); rotation −90° (E) … +90° (F) |
| Hub | circle d 16 `color.sign.white`, centre (65, 60) |

Value mapping (6 presets): index i ∈ 0…5 → angle −90 + 36·i: 20 000 → −90°, 30 000 → −54°, 40 000 → −18°, 60 000 → +18°, 80 000 → +54°, «не важно» → +90°.
Motion: `motion.needle` (spring, stiffness 300, damping ratio 0.6; Compose `spring(0.6f, 300f)`). Reduced motion: snap.
Value text under the gauge: «до 40 000 ₽» or «не важно», `type.title.lgNum`, `color.text.primary`.
TalkBack: one node, role Image, «Бюджет до 40 000 рублей» / «Бюджет не важен», live region Polite.

## 7. StartButton

Three sizes, same construction: bezel circle `color.dash.control`, face circle `color.dash.face`, ring `stroke.w3` `color.accent.red` drawn **inside** the face edge, power icon (§17.3 `power`, stroke `stroke.icon.ui`, `color.text.primary`), gap 2, label «ПОЕХАЛИ».

| Size | Bezel | Face | Icon | Label style | Screens |
| --- | --- | --- | --- | --- | --- |
| L | 100 (`size.startLOuter`) | 82 | 20 | `type.button.startLabel` | Instruments |
| M | 92 (`size.startMOuter`) | 76 | 18 | `type.button.startLabel` | Windshield |
| S | 86 (`size.startSOuter`) | 70 | 16 | `type.button.startLabelSm` | Navigator |

Pulse: `motion.startPulse`. A filled circle of radius (bezel/2 + spread) in `color.accent.redPulse`; spread 0 → 16 dp (14 dp on S), alpha 0.55 → 0, drawn behind the bezel. Reduced motion: no pulse, static 0 spread.

| State | Spec |
| --- | --- |
| default | pulse running |
| pressed | face + label scale 0.96 (`motion.startPress`), pulse continues |
| disabled (Navigator before B is chosen; Instruments while the crew is invalid) | no pulse; ring `color.dash.outlineDashed`; icon and label `color.text.disabled` |
| loading (Navigator validating A/B road distance, ≤ 1.5 s) | the ring is drawn as a 90° arc rotating 360°/900 ms linear; label «ЖДЁМ» |
| offline (Instruments, Navigator) | enabled; tap leads to the Drive offline state (5.4) — the button cannot know the outcome in advance |

TalkBack (mockup): Windshield «Поехали: <route name>»; Navigator «Поехали»; Instruments «Поехали». Role Button. Disabled: «Поехали — сначала выберите, куда».

## 8. NaviPanel (navigator screen)

Bezel `color.dash.control`, screen `color.navi.screen`.

| Use | Box | Bezel | Radius | Padding | Gap |
| --- | --- | --- | --- | --- | --- |
| Windshield entry | 18, 542, 354 × 134 | `stroke.w6` | `radius.r16` | 10 12 | 8 |
| Navigator | 14, 188, 362 × 516 | `stroke.w7` | `radius.r18` | 12 | 10 |
| Drive | 18, 562, 354 × 186 | `stroke.w6` | `radius.r16` | 12 14 | 8 |
| Exit | 14, 464, 362 × 282 | `stroke.w6` | `radius.r16` | 12 | 8 |

The bezel is drawn inside the box. The screen radius = outer radius − bezel. Header row: left/right labels `type.label.md`, `color.navi.label`.

Sub-components:

| Name | Spec |
| --- | --- |
| `NaviField` (static, Windshield) | 318 × 48, radius `radius.r10`, fill `color.navi.field`, border `stroke.w1` `color.navi.fieldBorder`, padding 0 12; search icon 18 (`stroke.icon.ui`, `color.accent.yellow`); gap 10; title `type.field.md` `color.text.primary`; sub `type.body.sm` `color.navi.labelSecondary` |
| `NaviInput` (editable, Navigator КУДА) | min-h 56 (52 + 2 × 2 border), border `stroke.w2` `color.navi.fieldBorder`, focused → `color.accent.yellow`; 12 × 12 square marker radius 3 `color.accent.yellow`; caption `type.caption.md` `color.navi.labelSecondary`; value `type.field.lg` `color.text.primary`; placeholder «Начните вводить» `color.navi.hint`; cursor 2 dp `color.accent.yellow`; trailing clear «×» 44 × 44 touch (icon 16, `color.navi.labelSecondary`) once the field has text (NEW) |
| `NaviValueField` (ОТКУДА) | min-h 50, border `stroke.w1`; ring marker d 12 with 3 dp `color.navi.label` stroke; caption + value as above (`type.field.md`); trailing «изменить» button 36 h (touch 44), padding 0 10, radius `radius.r8`, border `stroke.w1` `color.navi.fieldBorder`, `type.body.smStrong` `color.navi.label` |
| `SuggestionRow` | min-h 52, padding 6 12, fill `color.navi.list` (selected `color.navi.listSelected`), divider 1 `color.navi.divider`; badge 26 × 26 `radius.r6`: Г = `color.sign.blue`, У = `color.navi.fieldBorder`, М = `color.sign.brown`, letter `type.badge` `color.text.primary`; gap 10; name `type.list.title`; sub `type.body.sm` `color.navi.labelSecondary`; km `type.body.mdTight` `color.navi.text`, tabular |
| `DashedButton` | min-h 44, radius `radius.r10`, dashed border 1 (dash 4, gap 3) `color.navi.dashed`, `type.body.mdStrong`; text `color.accent.yellow` (primary) or `color.navi.label` (secondary) |
| `NaviChip` | visual height 36 (mockup 25 with padding 5 10; raised per OI-09), padding 0 12, touch 44, radius `radius.r14`, fill `color.navi.field`, `type.body.sm` `color.navi.text`; pressed fill `color.navi.listSelected`; single horizontally scrolling row, gap 8 |
| `ProgressBar` | h 4, radius 2, track `color.navi.divider`, fill `color.accent.yellow` |
| `StepLine` | `type.body.step`; done: check (§17.4, 10 × 10, stroke 2.4, `color.accent.yellow`) + gap 8 + text `color.text.primary`; active (NEW): ring d 10 stroke 2 `color.navi.label` + text `color.text.secondary` + animated «…»; appear `motion.stepAppear` |
| `HotelOption` | §12 |

TalkBack: the Windshield panel is one Button: «Навигатор. Куда угодно: город, адрес или точка на карте, по всей России». Suggestion rows: «<name>, <sub>, <km> километров», role Button, selected state «выбрано».

## 9. Windshield scene (`WindshieldScene`)

One Canvas per screen, parameterised by a `SceneSpec` (values per screen in each screen file). Draw order (back to front):

1. **Sky bands** — rectangles full width, flat colours (no gradients), `color.sky.band1…5` / `color.sky.night`.
2. **Celestial** — sun disc `color.scene.sun` (day/dusk), or moon (crescent: disc `color.scene.moon`, minus a disc of the sky colour offset +12, −6) and stars `color.scene.star` (night).
3. **Hills** — path (Windshield only) `M0 28 L40 18 L80 24 L130 12 L170 22 L200 16 L250 26 L300 14 L350 24 L390 18 L390 40 L0 40 Z`, translated to y 272, fill `color.sky.hills`. Scale x by width/390 on other widths.
4. **Ground** — rect from the horizon to the scene bottom, `color.scene.groundDay` / `color.scene.groundNight`.
5. **Road** — the 3D road (§9.1).
6. **Headlight** (Exit only) — trapezoid, `color.scene.headlight`.
7. **Roadside posts** — §9.2.
8. **Gantry legs / sign pole** — rects `color.interior.pole`.
9. **Flying signs** (Drive) — §2.2, as composables over the Canvas, under step 10.
10. **Roof liner** — path `M0 0 H W V2 A(W/2) 14 0 0 1 (W/2) 16 A(W/2) 14 0 0 1 0 2 Z` (Windshield/Drive/Exit, 16 high). Strip screens use height 14 with a 12 curve. Fill `color.interior.liner`.
11. **A-pillars** — left polygon (0,0) (24,0) (9.6,H) (0,H); right polygon (W−24,0) (W,0) (W,H) (W−9.6,H); H = scene height; `color.interior.liner`.

All scene Canvas content has `clearAndSetSemantics {}` (decorative, mockup `aria-hidden`).

### 9.1 3D road — exact projection

The mockups use CSS 3D (`perspective P`, plane rotated `rotateX(θ)` about its bottom edge, `perspective-origin 50% 0%` of the road container). Reproduce it with the closed-form projection below (no 3D API needed):

For a point on the road plane at distance **d** (dp, from the near edge, 0 ≤ d ≤ L) and lateral offset **x** from the road centre:

```
s       = P / (P + d · sin θ)
screenX = cx + x · s                      cx = screen width / 2
screenY = top + (H − d · cos θ) · s       top/H = road container top and height
```

Straight lines stay straight under this projection, so every element is a quad from 4 projected corners:

- asphalt: |x| ≤ W/2 − edge, `color.scene.road` / `color.scene.roadNight`
- edge lines: W/2 − edge ≤ |x| ≤ W/2, `color.scene.roadEdge` / `color.scene.roadEdgeNight`
- lane dashes: |x| ≤ lane/2, `color.scene.roadEdge` (white even at night, as in the mockup)
- clip everything to the ground rect (y ≥ horizon)

Dash pattern: measured from the **far** end of the plane, u = L − d. Dash k covers u ∈ [phase + k·period, phase + k·period + dash]. `phase` runs 0 → period during one cycle (dashes travel toward the viewer).

| Screen | top | H | P | θ | W | L | edge | lane | dash / period | cycle | far end y (clip) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Windshield | 300 | 240 | 210 | 76° | 230 | 1000 | 6 | 8 | 70 / 160 | `motion.lane.idle` 900 ms | 299.66 → clipped at 300 |
| Navigator | 104 | 46 | 120 | 80° | 160 | 600 | 4 | 6 | 70 / 160 | `motion.lane.navi` 1400 ms | 94.2 → clipped at 104 |
| Drive | 300 | 260 | 210 | 76° | 240 | 1000 | 6 | 8 | 70 / 160 | `motion.lane.drive` 450 ms | 303.2 |
| Exit | 240 | 190 | 200 | 76° | 230 | 900 | 6 | 8 | 70 / 160 | `motion.lane.exit` 1600 ms | 234.8 → clipped at 240 |

Check values (Windshield), road half-width at screen y: 540 → 115; 447.6 → 78.7; 383.3 → 53.4; 325.1 → 30.5; 300 → 20.5. Visual QA tolerance on these points: ±1 dp.

Static frame (reduced motion): phase = 0.

### 9.2 Roadside posts

Post: 6 × 18 rect `color.scene.roadEdge` with a 5 dp top cap `color.dash.base` (reflector band). Two posts per scene, mirrored.

| Screen | Right post start box | Left post start box | Motion |
| --- | --- | --- | --- |
| Windshield | (236, 302) | (148, 302) | `motion.post.idle`: translate (±150, +260), scale 0.3 → 2.2 about the post centre, alpha 0 → 1 over the first 10 %, 2600 ms `easing.postIn`, left post offset 1300 ms |
| Drive | (212, 300) | (172, 300) | `motion.post.drive`: translate (±170, +230), scale 0.2 → 2.4, 1100 ms `easing.rushIn`, offset 550 ms |

Posts are clipped to the scene. Reduced motion: posts hidden (alpha 0), because a static post mid-flight looks like a defect.

### 9.3 Gantry legs (Windshield)

Two rects 8 wide at x 34 and 348 (on other widths: x = 34 and W − 42), `color.interior.pole`, from **top = min(286, plate bottom − 4)** to **y 386** (the ground line of the legs). With 4 rows the plate ends at 318, so the top is 286 (100 high, as the mockup); with fewer rows or the message states the legs start 4 dp under the plate edge, so they never float below a shorter sign (slice-2 review: with 3 rows the plate ends at 256 and 286 left a 30 dp gap).

## 10. Dashboard surface (`Dashboard`)

Path: `M0 (T+R) A(W/2) R 0 0 1 (W/2) T A(W/2) R 0 0 1 W (T+R) V bottom H0 Z`, T = top, R = curve height. Rim: the same path translated −2 dp in y, filled `color.dash.control` and drawn first (`shadow.dashRim`).

| Screen | Top T | Curve R | Fill |
| --- | --- | --- | --- |
| Windshield | 520 | 34 | `color.dash.raised` |
| Navigator | 132 | 30 | `color.dash.raised` |
| Instruments (cap only, 40 high) | 104 | 30 | `color.dash.raised`, no rim |
| Drive | 540 | 34 | `color.dash.raised` |
| Road ahead (cap only, 40 high) | 110 | 30 | `color.dash.raised`, no rim |
| Exit | 410 | 34 | `color.dash.raised` |

## 11. WaybillSheet

Paper card (Waybill 5.6). Composable layout on a Canvas background.

| Part | Spec |
| --- | --- |
| Sheet | x 14, y 64, w 362, h content (mockup 555). Fill `color.paper.sheet`, radius `radius.r4`, shadow `shadow.paper`, padding 26 16 14 |
| Clip | 120 × 30 centred, top −14 (y 50), radius `radius.r8`, fill `color.paper.clip`, inner bottom edge `shadow.clip`. Decorative |
| Header | Left column: «ФОРМА ПОЕЗДКИ · ВЕРСТА» `type.paper.header` `color.paper.label`; «ПУТЕВОЙ ЛИСТ» `type.paper.title` `color.paper.text`; «легкового автомобиля» `type.paper.sub` `color.paper.text`. Right, bottom-aligned: «№ » `type.paper.label` `color.paper.label` + number `type.hand.lg` `color.paper.ink` (saved trip ordinal, 3 digits, «001»). Rule 2 dp `color.paper.text` under it, padding-bottom 6 |
| Form grid | margin-top 8; columns 92 / rest; row gap 4; baseline alignment. Label `type.paper.label` `color.paper.label`; value `type.hand.md` `color.paper.ink` with a 1 dp underline `color.paper.lines` (drawn under each line box, so wrapped values get a line per text line) |
| Table | margin-top 10; outer border 1.5 `color.paper.text`; columns rest / 70; vertical rule 1 `color.paper.text`. Header row: «СТАТЬЯ И РАСЧЁТ» / «₽», `type.paper.tableHead` `color.paper.label`, padding 3 6, bottom rule 1.5 |
| Cost line (`CostLine`) | padding 3 6; name `type.paper.body` `color.paper.text`; formula `type.hand.sm` `color.paper.ink`; sum `type.hand.md` `color.paper.ink`, right-aligned, vertically centred; bottom rule 1 `color.paper.lines`. Min height 44 (mockup 41.3, OI-05). Chevron 10 × 6 (§17.4 `chevronDown`) `color.paper.label` after the name; rotates 180° when expanded (`motion.selection`) |
| Expanded breakdown (NEW) | Below the line, inside the same cell: rows indented 12, each min-h 22: label `type.paper.label` `color.paper.text` + value `type.hand.sm` `color.paper.ink` right-aligned in the ₽ column. Expand/collapse: height animates with `motion.bottomSheetIn` (300 ms, `easing.decelerate`) on expand and `motion.bottomSheetOut` (200 ms, `easing.accelerate`) on collapse; only one line is expanded at a time |
| Reserve row (`ReserveSwitch`) | min-h 44; checkbox 18 × 18, border 1.5 `color.paper.text`, check = hand-drawn path (§17.4 `checkHand`) stroke 2 `color.paper.ink`; gap 8; «Резерв 10%» `type.paper.body`; sub «на пробки и «давай заедем»» `type.paper.label` `color.paper.label`; sum `type.hand.md` or «—» when off; bottom rule 1.5 |
| Total row | columns rest / 100; «ИТОГО» `type.paper.total` padding 6; «≈ 30 500» `type.hand.xl` `color.paper.ink`, padding 4 6 |
| Issued / left | margin-top 8; 2 columns, gap 10; label `type.paper.label` `color.paper.label`; value `type.hand.md` `color.paper.ink` (left: `color.paper.inkRed` when negative) with underline 1 `color.paper.lines` |
| Footnote | margin-top 6; `type.paper.label` `color.paper.label` |
| Stamp | §11.1 |

### 11.1 Stamp

Circle 94 × 94 (88 + 2 × 3 border) at right 12, bottom −30 relative to the sheet (mockup x 270, y 555). Ring 3 dp `color.paper.stamp`; inner ring 1 dp `color.paper.stamp` at 3–4 dp inside the outer ring (gap filled with `color.paper.sheet`). Text centred, three lines: «ВЕРСТА» `type.stamp.sm`, «В ПУТЬ» `type.stamp.lg`, «ГОТОВЫ» `type.stamp.sm`, `color.paper.stamp`. Whole stamp rotated −14°, alpha 0.85. Motion `motion.stamp`; reduced motion: final frame (scale 1, alpha 0.85). Decorative: `clearAndSetSemantics {}`. Its meaning is announced once in the screen-level announcement (5.6).

### 11.2 Handwriting

Marck Script is used **only** for values the "driver wrote by hand": number, form values, formulas, sums, total, issued/left, the reserve check. Printed labels are always IBM Plex Sans Condensed. Glyphs missing from Marck Script (✓, ₽, ≈, −) are drawn as paths or taken from Plex (OI-12).

### 11.3 TalkBack

- Cost line: role Button, «<name>, <sum> рублей. Расчёт: <formula>. <Раскрыть | Свернуть> подробности». Formula symbols are spoken: «×» → «умножить на», «/100» → «на сто», «+» → «плюс».
- Reserve: role Switch, «Резерв 10 процентов, на пробки и «давай заедем», <sum> рублей», checked state.
- Total: heading «Итого примерно 30 500 рублей».
- Issued/left: «Выдано 40 000 рублей. Остаток примерно 5 500 рублей» / «Перерасход 2 300 рублей».

## 12. ExitSign and HotelOption

### 12.1 ExitSign (Exit 5.7)

Plate x 162, y 92, 198 × 110: `color.sign.blue`, padding 4, radius `radius.r8`, shadow `shadow.exitSign`; inner border `stroke.w2` white radius `radius.r5`, padding 8 10, column gap 6.
Row 1: «<Town>» `type.sign.xlTight` + line break + «центр» `type.sign.mdSub`, `color.sign.white`; right: exit arrow (§17.1 `downRight`) 30 × 30, `stroke.icon.sign`, white.
Row 2: plate 34 × 34 `color.sign.white` radius `radius.r2` with the hotel pictogram 24 × 24 (`stroke.icon.pictogram`, `color.sign.black`); gap 8; distance «800 м» `type.sign.lgBold`.
Pole 6 × 100 at (314, 196) `color.interior.pole` (drawn by the scene, under the sign).
Motion `motion.exitNear` (origin 30 % / 100 % of the sign). Reduced motion: final frame.
TalkBack: role Image, «Указатель: съезд на <Ярославль>, центр, гостиница через <800 метров>» (mockup).
Distance: from the motorway exit to the selected hotel, rounded to 100 m below 1 km («800 м»), or to 0.1 km above («1,2 км»).

### 12.2 HotelOption

Button, w 326 (panel content width), min-h 60, radius `radius.r10`, padding 8 12, gap 12.

| Part | Spec |
| --- | --- |
| Radio | d 18; ring 2 `color.navi.radio` (unselected) / `color.accent.yellow` (selected); selected adds a dot d 6 `color.accent.yellow` with a 4 dp `color.navi.screen` gap |
| Name | `type.title.sm` `color.text.primary`, single line, ellipsis |
| Tags | `type.body.sm` `color.navi.labelSecondary`, wraps to 2 lines max |
| Price | `type.title.sm` `color.accent.yellow`, no wrap, right; «≈ 6 000 ₽» per night for the crew |

| State | Fill | Border |
| --- | --- | --- |
| default | transparent | `stroke.w1` `color.navi.fieldBorder` |
| selected | `color.navi.field` | `stroke.w1` `color.accent.yellow` |
| pressed | `color.navi.listSelected` | as current |
| booked (NEW) | as selected | as selected; price replaced by «забронировано» `type.body.smStrong` `color.accent.yellow` |
| loading | 2 placeholder rows: radio ring, name plate 140 × 14, tags plate 200 × 10, price plate 56 × 14; fill `color.navi.field`, shimmer `color.navi.listSelected` |

TalkBack: role RadioButton, «<name>, <tags>, примерно <6 000> рублей за ночь», selected state. Group: `selectableGroup()`.

## 13. Chips

| Chip | Visual | Text | States | TalkBack |
| --- | --- | --- | --- | --- |
| `InfoChip` (Road ahead header) | padding 4 9 (h 23), radius `radius.r12`, fill `color.dash.controlAlt` | `type.body.smStrong` `color.text.primary` | static | read as text in order |
| `FrontSeatChip` (Instruments) | min-h 44 (mockup 40, OI-05), padding 0 12, radius `radius.r20` → 22 at 44 h, border `stroke.w1` | `type.body.mdStrong`, one line | on: fill + border `color.sign.white`, text `color.text.onLight`, «Рядом с вами: взрослый»; off: transparent, border `color.dash.outlineDashed`, text `color.text.secondary`, «Рядом с вами: никого»; pressed: +1 dp y | Switch, «Рядом с вами: взрослый» / «…: никого» |
| `MoodChip` (NEW, Instruments) | min-h 44, padding 0 14, radius 22, border `stroke.w1` | `type.body.mdStrong` | unselected: transparent, border `color.dash.outlineDashed`, text `color.text.secondary`; selected: fill `color.sign.white`, text `color.text.onLight`; single-select | RadioButton «Настроение: Спокойно, с детьми», selected |
| `NaviChip` | §8 | | | Button «Найти: Петербург → Выборг» |
| `PlateToast` (NEW) | §16 | | | |

## 14. BackLink

Row: back arrow (§17.1 `left`) 14 × 14, `stroke.icon.back`, gap 6, label `type.body.mdTight`. Visual height 32 (`size.backLinkH`), touch 44, width hugs the content (min 44).

| Context | Colour (arrow + text) |
| --- | --- |
| On the dashboard (Navigator, Waybill, Exit) | `color.text.muted` |
| On a sky strip (Instruments, Road ahead, Drive) | `color.mirror.label` |

States: pressed → text/arrow `color.text.primary`; focus ring per §0.
Copy = the destination: «К лобовому» (to Windshield), «<Trip name>» (Instruments → back, mockup), «Приборы», «Дорога впереди», «Отменить» (Drive, NEW).
TalkBack: «Назад: <label>», role Button. System back does the same action.

## 15. CTA buttons

| Name | Box | Fill | Content | Pressed | Disabled / offline |
| --- | --- | --- | --- | --- | --- |
| `PrimaryCta` (Drive) | full width − 36, h 58, radius `radius.r12`, padding 0 18 | `color.accent.yellow` | `type.cta.md` `color.text.onLight` + arrow (§17.1 `right`) 22, `stroke.icon.cta` | `color.accent.yellowPressed` | n/a |
| `BookCta` (Exit) | full width − 28, h 60 | `color.accent.yellow` | title `type.cta.lg`, sub `type.body.smMedium`, both `color.text.onLight`; arrow `upRight` 22 | `color.accent.yellowPressed` | offline: fill `color.dash.control`, title `color.text.secondary`, sub «Нужен интернет» `color.accent.redText`, arrow hidden; tap → toast «Нужен интернет» |
| `WaybillCta` (Road ahead) | full width − 32, h 64 | `color.sign.white` | label `type.body.smStrong` `color.text.onLightMuted`, amount `type.amount` `color.text.onLight`, arrow `right` 22 | fill `color.text.secondary` | loading total: amount plate 120 × 18 `color.dash.outline` shimmer |
| `SecondaryButton` (Waybill) | h 56, radius `radius.r12` | `color.dash.control`, border `stroke.w1` `color.dash.outline` | `type.button.md` `color.text.primary` | fill `color.dash.pressed` | saved: text «Сохранено ✓»; disabled: text `color.text.disabled` |
| `YellowButton` (Waybill) | h 56, radius `radius.r12` | `color.accent.yellow` | `type.cta.sm` `color.text.onLight` | `color.accent.yellowPressed` | — |

TalkBack: label = visible text; Book CTA adds «, откроется Яндекс Путешествия». The Waybill CTA reads «Путевой лист, сколько стоит: примерно 30 500 рублей».

## 16. Shared overlays (NEW, used by missing states)

| Component | Spec |
| --- | --- |
| `BottomSheet` | Fill `color.dash.raised`, top radius `radius.r16`, rim 2 dp `color.dash.control` along the top edge; handle 36 × 4 radius 2 `color.dash.outline`, 8 dp from the top; content padding 8 20 24. Scrim `color.overlay.scrim`. Enter `motion.bottomSheetIn` (slide from the bottom + scrim fade), exit `motion.bottomSheetOut`. Max height 88 % of the window. Drag-to-dismiss threshold 25 % of the height or fling > 1200 dp/s. TalkBack: pane title = sheet title; a «Закрыть» button (44 × 44, §17.4 `close`) at the top-right is always present for TalkBack/keyboard |
| `SignSheet` | A `BottomSheet` whose content sits on an `OverheadSign.List` plate (full width − 28), for lists of ready routes |
| `PlateToast` | Bottom-centred, 16 dp above the bottom-pinned element of the screen, and **never over interactive content or the caption**. Anchors per screen (final review F-02): Windshield — bottom edge 16 dp above the dashboard crest (y 504 at 844; `dashTop − 16` on other heights); Road ahead — 16 dp above the Waybill footer (740); Exit — 16 dp above the Book CTA; Waybill — 16 dp above the buttons; Navigator / Instruments — 16 dp above the caption row. One line of text + action stays **44 dp** high (no extra vertical padding); max width window − 32; min-h 44, padding 10 16, radius `radius.r10`, fill `color.dash.control`, border `stroke.w1` `color.dash.outline`; text `type.body.mdTight` `color.text.primary`; optional action `type.body.mdStrong` `color.accent.yellow`. 3 s, 6 s with an action. Live region Polite |
| `NaviDialog` | Centred card, w = window − 48, `NaviPanel` look (bezel 6, radius 16); title `type.title.lg`, body `type.body.md` `color.navi.text`; buttons: primary `PrimaryCta` style h 48, secondary `DashedButton` h 48; scrim `color.overlay.scrim`. TalkBack: dialog pane title |
| `Shimmer` | A 90 dp wide band of the highlight colour with linear 0→1→0 alpha across its width, moving left → right across the placeholder bounds in `motion.shimmer` (1200 ms linear). Reduced motion: static base colour |
| `OfflinePlate` | Inside the navi header row, right side: offline icon (§17.4 `offline`, 11 × 11) + «НЕТ СЕТИ», `type.label.md` `color.accent.redText` |

## 17. Vector data (24 × 24 viewBox unless stated; stroke, round caps and joins, no fill unless stated)

### 17.1 Arrows (direction arrows on signs, `stroke.icon.sign` = 3; snap ready-route bearing to these 8)

| Name | Bearing | Path |
| --- | --- | --- |
| `up` | N 0° | `M12 20V4M5 11l7-7 7 7` |
| `upRight` | NE 45° | `M7 17L17 7M9 7h8v8` |
| `right` | E 90° | `M4 12h16M13 5l7 7-7 7` |
| `downRight` | SE 135° | `M7 7l10 10M17 9v8H9` |
| `down` | S 180° | `M12 4v16M5 13l7 7 7-7` |
| `downLeft` | SW 225° | `M17 7L7 17M15 17H7V9` |
| `left` | W 270° | `M20 12H4M11 5l-7 7 7 7` |
| `upLeft` | NW 315° | `M17 17L7 7M15 7H7v8` |

Mockup sources: `up`, `upRight`, `down`, `downLeft` (Windshield); `right` (CTA arrows), `left` (back links), `downRight` (exit sign). `upLeft` is derived by mirroring `upRight`. The same paths are used at 14–30 dp with the stroke from `stroke.icon.*` (back 2.5, CTA 2.6, sign 3).

### 17.2 Pictograms

Deliverable form: `design/icons/*.svg` (stroke-free, generated by `design/tools/gen_icons.py`); naming, the extended tourist set and the tag mapping are in `design/signs.md` §1, which supersedes the `church`/`nature` names below.


| Name | Stroke | Path |
| --- | --- | --- |
| `fuel` (7.3) | 2.2 black on white | `M4 20V5a1 1 0 0 1 1-1h7a1 1 0 0 1 1 1v15M3 20h11M5 9h7M13 8l3 2v7a1.5 1.5 0 0 0 3 0V9l-3-3` |
| `food` (7.7) | 2.2 | `M7 3v8a2 2 0 0 0 2 2v8M5 3v5M9 3v5M16 21V3c2.5 1 4 3.5 4 7h-4` |
| `rest` (7.11) | 2.2 | `M12 3l-5 8h3l-4 6h12l-4-6h3zM12 17v4` |
| `hotel` (7.12) | 2.2 | `M3 18V8M3 14h18v4M21 14v-2a3 3 0 0 0-3-3h-7v5` + circle cx 7 cy 11 r 2 |
| `church` (tourist: kremlin, monastery, church) | 2 white on brown | `M12 2v3M10.5 3.5h3M8 21V12l4-4 4 4v9M5 21h14M10 21v-4a2 2 0 0 1 4 0v4` |
| `museum` (NEW, tourist, OI-14) | 2 | `M3 21h18M4 10h16M12 3l9 5H3zM6 10v8M10 10v8M14 10v8M18 10v8M4 18h16` |
| `nature` (NEW, tourist: view, walk) | 2 | `M3 19l6-9 4 5 3-4 5 8z` |

### 17.3 UI icons from the mockups

| Name | Spec |
| --- | --- |
| `search` | circle cx 11 cy 11 r 7 + `M20 20l-3.5-3.5`, stroke 2.4, `color.accent.yellow` |
| `locate` | `M3 11l18-8-8 18-2-8z`, **filled** `color.navi.label` |
| `power` | `M12 3v8M6.3 6.6a8 8 0 1 0 11.4 0`, stroke 2.4 |
| `turn` | `M14 5l7 7-7 7v-4H3V9h11z`, **filled** `color.signal.green` |

### 17.4 New icons (same 24 grid, stroke 2 unless stated)

| Name | Path |
| --- | --- |
| `check` | `M5 12.5l4.5 4.5L19 7` (stroke 2.4) |
| `checkHand` | `M5 13c1.5 1 3 2.6 4 4.5 2.5-5 6-9.5 10-12.5` (stroke 2, ink, hand-drawn look) |
| `close` | `M6 6l12 12M18 6L6 18` |
| `gear` | circle cx 12 cy 12 r 3 + circle cx 12 cy 12 r 6.5 + `M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1` |
| `bookmark` | `M6 3h12v18l-6-4-6 4z` |
| `share` | `M12 15V3M7 8l5-5 5 5M5 13v7h14v-7` |
| `download` | `M12 3v12M7 10l5 5 5-5M5 21h14` |
| `offline` | `M2 8.5a15 15 0 0 1 20 0M5.5 12a10 10 0 0 1 13 0M9 15.5a5 5 0 0 1 6 0M12 19h.01M3 3l18 18` |
| `pin` | `M12 21s-7-6.2-7-12a7 7 0 0 1 14 0c0 5.8-7 12-7 12z` + circle cx 12 cy 9 r 2.5 |
| `dragHandle` | `M5 9h14M5 15h14` |
| `chevronDown` | `M6 9l6 6 6-6` |
| `external` | = `upRight` (stroke 2.4) |
| `navigator` | `M12 2l7 19-7-4-7 4z` (filled) |
| `clock` | circle cx 12 cy 12 r 9 + `M12 7v5l3 2` |

Text glyphs «→ ↓ ↑ · ≈ № ₽ « »» are set in IBM Plex Sans Condensed; «✓» and «●» are drawn (`check`, a 6 dp circle) because their coverage in the bundled fonts is not guaranteed (OI-12).

### 17.5 Sprint 3 icons and pictograms (24 grid; pictograms use `stroke.icon.pictogram` / `thin` as §17.2)

| Name | Path | Use |
| --- | --- | --- |
| `walker` | circle cx 13 cy 4.5 r 2 (filled) + `M9.5 21l2.5-6.5 2.5 2V21M12 14.5l1-5-3.5 1.5L8 14M13 9.5l2.5 3 3 1` | pedestrian-zone sign 5.33 on the walk title plate, the «По городу» plate, ПОШЛИ, walk hand-off |
| `footprint` | `M8 4c1.7 0 2.5 2 2.5 4.5S9.7 13 8 13s-2.5-2-2.5-4.5S6.3 4 8 4zM7 15h2v3H7z` (filled; the right foot mirrored, offset +8, +6) | moving footprints in `WalkColumn` |
| `museum` | `M3 9l9-5 9 5M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18` | «Музейный» plate (= §17.2 museum) |
| `glass` | `M7 4h10l-1.2 9.5a3.8 3.8 0 0 1-7.6 0zM12 17v3M8.5 20h7` | рюмочная / bar sign and plate |
| `mug` | `M6 7h9v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1zM15 10h2.5a2 2 0 0 1 0 4H15M8 4c.5 1 1.5 1 2 0s1.5-1 2 0` | pub / craft sign, «Пивной» plate |
| `binoculars` | circle cx 7 cy 15 r 3.5 + circle cx 17 cy 15 r 3.5 + `M9 7l-2 4.5M15 7l2 4.5M10.5 14h3` | «Обзорный» plate |
| `locateCross` | circle cx 12 cy 12 r 7 + `M12 2v3M12 19v3M2 12h3M19 12h3` + circle cx 12 cy 12 r 2 (filled) | GPS start, rationale sheet |
| `info` | circle cx 12 cy 12 r 9 + `M12 11v6M12 7.5h.01` | «Расстояния приблизительные» line |
| `photoNone` | `M4 6h16v12H4zM4 15l4-4 4 4 3-3 5 5M3 3l18 18` | (fallback icon inside the city placeholder only) |

## 18. `PhotoFrame` — the uniform place photo (5.9, ADR-0012 §6)

The CEO's rule: every card looks the same, whatever Wikimedia Commons returns (landscape, portrait, tiny, panorama, an SVG rasterised by Commons, a PNG with transparency, or nothing). The frame is fixed; the image adapts to it.

| Part | Spec |
| --- | --- |
| Frame | width = content width (350 at 390; L20/R20), **fixed aspect 3 : 2** (`size.photoW` × `size.photoH` = 350 × 233), radius `radius.r12`, clipped; fill `color.photo.mat`; hairline `stroke.w1` `color.photo.border` drawn **over** the image |
| Request | `Special:FilePath/<file>?width=800` (cards; 400 for any list thumbnail). Commons rasterises SVG/TIFF/PDF, so the app only decodes JPEG/PNG. Coil with the 64 MB disk cache (ADR-0012) — nothing is bundled in the APK |
| Fit: crop (default) | `ContentScale.Crop`; landscape and square (h/w ≤ 1.05) → centre; portrait (h/w > 1.05) → `BiasAlignment(0f, -0.35f)` (domes and towers keep their tops) |
| Fit: contain on the mat | when the decoded image is < 320 px wide or < 200 px tall, its aspect is outside 0.45 … 3.2, or it has transparency (`hasAlpha`, e.g. coats of arms / plans rasterised from SVG): `ContentScale.Fit` inside a 12 dp inset on `color.photo.mat`, never upscaled above 2 ×, no scrim. Decided from the decoded size **before** the first draw, so the frame never re-lays out |
| Scrim | crop mode only: bottom gradient 56 dp, `color.photo.scrim` 0 → 0.62, under the credit |
| Credit | always when an image is shown. Crop: on the scrim, bottom-left, padding 10 12 8, 1 line, the author part ellipsizes: `card_photo_credit` «Фото: Wikimedia Commons · Анна П. · CC BY-SA 4.0» (`card_photo_credit_short` without credits), `type.photo.credit` `color.photo.credit`. Contain: the same line **under** the frame (gap 4) in `color.text.muted`. Hotels: `card_photo_area` «Фото района: Ярославль · Wikimedia Commons». The line is a link to the file page (`image.page`), touch full width × 44; TalkBack `cd_card_credit` |
| Area plate (hotels) | top-left 10 / 10: h 22, padding 0 8, radius `radius.r4`, fill `color.photo.scrim` (0.62), `card_area_plate` «ФОТО РАЙОНА» `type.photo.label` `color.photo.credit`. Mandatory with every hotel photo |
| Placeholder illustrations (7) | see §18.1. Shown while loading (with the shimmer), offline (`card_photo_offline`), on HTTP error / 10 s timeout (`card_photo_error`) and for files without a free licence or no file (`card_photo_none`). The text sits under the illustration, centred at 78 % of the frame height, `type.body.sm` `color.text.muted`. The frame has the same size in every state |
| Loaded | `motion.photoFadeIn` 250 ms over the placeholder |

### 18.1 Placeholder illustrations (vector, drawn in the frame, no bitmap)

Each placeholder is a flat «sign-language» vignette in two tones on its own mat, centred at 42 % of the frame height, 96 × 64 dp, strokes 3 dp, no text inside. Kind → illustration (engine `poiKind`):

| Placeholder | Mat (`color.photo.*`) | Drawing (`color.photo.ink` lines, `color.photo.accent` fills) |
| --- | --- | --- |
| `museum` | `phMuseum` | a portico: pediment triangle, 4 columns (`museum` pictogram scaled), step line |
| `church` (church, monastery, kremlin) | `phChurch` | a church: body square, drum, onion dome (accent), cross |
| `park` (park, garden) | `phPark` | three round trees of different sizes on a ground line, a bench |
| `monument` (monument, memorial, square) | `phMonument` | a plinth with a standing figure silhouette |
| `view` (viewpoint, embankment) | `phView` | a river line with two hills behind and a railing in front |
| `bar` (bar, ryumochnaya, pub, craft) | `phBar` | a counter line with the `glass` and `mug` shapes |
| `city` (towns, hotel areas, anything else) | `phCity` | a row of three facades with windows (as `CityScene` facades) |

## 19. Card sheet (5.9)

`BottomSheet` (§16), content padding 8 20 24, content-sized, max 88 %. Order:

1. Title row: mini sign of the kind at 0.7 scale (tourist 39 × 39; hotel / bar service 35 × 43); gap 12; name `type.title.lg`, up to 2 lines; close 44 × 44.
2. Kind line (4 below): `type.body.sm` `color.text.muted`.
3. `PhotoFrame` (12 below).
4. Hotel note (6 below, hotels only).
5. Description (12 below): `type.body.md` `color.text.note`, ≤ 6 lines then «ещё».
6. Facts (8 below): `type.body.sm` `color.text.secondary`.
7. Actions (16 below): one full-width `SecondaryButton` h 56 — «Выбрать отель» / «Заменить» / «Убрать эту точку».
8. Report text button (4 below).
9. Bar cards: the OSM line.

The action block stays pinned at the bottom when the body scrolls.

## 20. Budget-fit components (5.8, ADR-0011)

| Component | Spec |
| --- | --- |
| `LimitSign` | 96 × 96 circle `color.sign.white`, red ring 10 dp `color.accent.red`, 2 dp white outline outside, `shadow.signMd`; the budget `type.sign.lgBold` `color.text.onLight` centred, auto-shrink to 15 sp for ≥ 7 characters. Decorative (`clearAndSetSemantics`) |
| `BudgetOverPlate` | fill `color.budget.overFill`, border `stroke.w1` `color.budget.overBorder`, radius `radius.r10`, padding 12; label `type.label.md` `color.accent.redText`; amount `type.amount` `color.text.primary` |
| `BudgetOption` | button row min-h 64, fill `color.navi.field`, border `stroke.w1` `color.navi.fieldBorder`, radius `radius.r10`, padding 10 12, gap 8 between rows; title `type.title.sm` `color.text.primary`, sub `type.body.sm` `color.navi.labelSecondary`, chevron `right` 14 stroke 2.5 `color.navi.label` on the right. Pressed `color.navi.listSelected` |
| Fit badge (Road footer) | after «ПУТЕВОЙ ЛИСТ ·»: `check` 12 stroke 2.4 `color.text.onLightMuted` + `budget_fit_badge` `type.body.smStrong` `color.text.onLightMuted`; small overrun: `TightDot` + `budget_tight_badge` |
| `TightDot` | 8 dp circle `color.budget.tight` (yellow; never yellow text on white) |
| Lever lines (Waybill) | under the total row: heading + 1 line per lever, min-h 22, label `type.paper.label` `color.paper.text`, amount `type.hand.sm` `color.paper.ink` in the ₽ column |
| `breaksBudget` mark (D-6) | 6 dp `color.accent.red` dot before the delta + `budget_alt_breaks` `type.body.sm` `color.accent.redText` |

## 21. City components (5.10, 5.11)

| Component | Spec |
| --- | --- |
| `CityScene` (strip, decorative) | sky `color.city.sky`; far roof line `color.city.facadeC` polyline `M0 112 L34 112 L34 96 L80 96 L80 106 L128 106 L128 88 L150 80 L172 88 L172 104 L230 104 L230 92 L270 92 L270 108 L318 108 L318 94 L390 94 V200 H0 Z`; middle facades `color.city.facadeB`, 5 blocks (x 0–70, 70–150, 150–236, 236–318, 318–390) from y 124 / 132 alternating; near facades `color.city.facadeA` from y 140 with windows 10 × 14 every 22 dp in rows at y 150 and 172 (≈ 60 % lit `color.city.window`, by a fixed index pattern, the rest `color.city.windowOff`); pavement `color.city.sidewalk` 186–200 with joints `color.city.joint` every 24 dp; kerb 3 dp `color.city.curb` at the bottom edge; lamps at x 56 / 196 / 336 — pole 3 × 52 `color.interior.pole` from y 134, head 14 × 6 `color.city.lamp`, glow d 36 `color.city.lampGlow` (`motion.lamps`). No roof liner, no pillars. 5.11 crops it to 132 |
| `StreetPlate` | x 20, y 44, w hug (≤ 280) × `size.streetPlateH` 64; `color.sign.blue`, radius `radius.r6`, padding 4, inner border `stroke.w2` `color.sign.white` radius `radius.r4`, content padding 6 12; line 1 `type.street.kind` `color.sign.blueText` «пешком · Ярославль»; line 2 the street `type.street.name` `color.sign.white`. House square 44 × 44 to its right (gap 6), same construction, number `type.street.name` |
| `PresetPlate` | w (content − 10) / 2, h `size.presetH` 76, `color.sign.brown`, radius `radius.r5`, inner border `stroke.w2` `color.sign.white` inset 3 radius `radius.r3`, padding 10 12; pictogram 24 white top-left; name `type.title.sm` `color.sign.white` bottom-left; sub `type.body.sm` `color.mirror.label`. 18+: white circle 22 top-right with «18+» `type.caption.bold` `color.text.onLight`. Selected: 2 dp `color.accent.yellow` outline 2 dp outside + `check` 16 yellow top-right (the badge moves left 26). Disabled: content alpha 0.45. «Свой маршрут»: transparent fill, dashed 2 dp `color.sign.white` border |
| `ParamChips` | `MoodChip` look (§13), h 44, padding 0 14, radius 22; single-select (duration, pace, budget) or multi (interests); rows wrap, gap 8 |
| Start button (walk) | M size with `walker` and `city_go` «ПОШЛИ»; ring `color.accent.red` |
| `WalkColumn` | x 14–60: pavement `color.city.sidewalk`; kerbs 2 dp `color.city.curb` at x 14–16 and 58–60; joints 1 dp `color.city.joint` every 24 dp + a centre joint at x 37; a pair of `footprint` 10 × 16 `color.city.footprint` moving down 48 dp / 1800 ms (`motion.footsteps`, global phase); reduced motion: one pair at the top of the visible column. Connectors as §2.5 |
| `WalkTitleSign` | `OverheadSign.Title` with the pedestrian-zone pictogram (white square 28 + `walker` 22 black, GOST 5.33 look) in place of the arrow. Walk titles run longer than trip names, so the name wraps to 2 lines (`type.sign.xlTight`, then ellipsis) and the sign height is a minimum (49), not fixed |
| Bar sign | `service` RoadSign with `glass` (bar, рюмочная) or `mug` (pub, craft) |

## 22. Hand-off menus (5.13, ADR-0014)

| Control | Spec |
| --- | --- |
| Day menu | small `BottomSheet`: title «День N» `type.title.lg`; one `HandoffItem` |
| Stop menu (D-5) | first item `HandoffItem` `handoff_from_stop`, then the existing items |
| `HandoffItem` | min-h 64, padding 10 0; `navigator` 22 (car) / `walker` 22 (walk) `color.accent.yellow` at the left, gap 12; title `type.list.title` `color.text.primary`; target line `type.body.sm` `color.text.muted` (`handoff_navigator` / `handoff_maps_car` / `handoff_web`); truncated line `type.body.sm` `color.accent.yellow`; chevron `upRight` 16 `color.text.secondary` (it leaves the app) |
| Walk button | `SecondaryButton` full width h 48 (5.11 L3a), `walker` 18 + `handoff_maps_walk` / `handoff_web`; parts: one button per part with `handoff_part` |

## 23. `AgeGateDialog` (5.10)

`NaviDialog` (§16): `age_gate_title`, `age_gate_body`, primary `YellowButton` `age_gate_yes` «Да, мне есть 18», secondary `age_gate_no` «Нет». Shown **every time** an alcohol preset or the «бары» interest is chosen (not remembered, DEV-306); «Нет» sends no request. No birthday input; nothing leaves the phone.
