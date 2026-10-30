# Sprint 3 — final release QA (Designer)

Build: main `be0a266` (dev/S3-R4 `f0533e1`), CI run 73 = 40160179825 (green; 161 screenshots). Sources: `ci-logs` → `runs/40160179825-1/e2e/screens/*` (60–62b CEO budget case, 63–68 cards and walks, 70–73, 80 real Commons frames, 83–86 reports, 90 search, 91 real photo cards, 92–94 walks) and `screenshots/**`. Checked against 5.8–5.13, the §8 sections of 5.1–5.5, components §17.5–§23, copy §15, and the S3-QA fixes.

Already known and being fixed by the Architect, so not repeated as findings: sentence-like photo credits («This photo was taken by Anton Zelenov. …», «… · Example · Wikimedia Commons»), and the short СПб museum walk (6 ч, ≈ 3 км).

Severity: **P0** wrong information on a CEO path or a broken journey · **P1** visible deviation or a confusing state, fix before release · **P2** polish.

## P0

None. CEO asks 1–4 work end to end on the real catalogue.

## P1

| # | Screen | Finding | Fix (spec changed) | Owner |
| --- | --- | --- | --- | --- |
| P1-01 | 5.2 GPS (e2e 48 `navigator-gps-on`) | The keyboard is up with no field focused. The Navigator panel shrinks to an empty ≈ 20 dp bar above the keyboard, so there is no header, no field and no results. This is the GPS path of CEO ask 3. | 5.12 §5.5: hide the keyboard and clear focus when a GPS fix sets ОТКУДА. If the keyboard is still up without a focused field, use the typing layout; the panel is never shorter than header + field. | Developer |
| P1-02 | 5.5 every real trip (e2e 70, 83, 85) | With the real catalogue every route opens with a yellow warning plate «Часть мест по открытым данным — не проверены». It reads as a problem with this trip, and the phrase is ungrammatical. | 5.5 §9: a muted info line like «Расстояния приблизительные», with «О данных». New text «Места — из открытых данных: часы и цены уточняйте». When both notes apply, one line: `route_approx_open_data`. Yellow plates are only for warnings about this trip. | Architect (`reasons.ru.json`), Developer (render) |
| P1-03 | D-7 report (e2e 84) | The report sheet opens with the keyboard up: the comment is autofocused, so 2 of 4 reasons and «ОТПРАВИТЬ» are hidden. | Components §22 `ReportSheet`: no autofocus; the keyboard comes up only on a tap in the comment, then the sheet scrolls so the comment and the button stay visible. | Developer |
| P1-04 | 5.9 hotel (e2e 65) | The hotel «фото района» is a Commons city **collage** (a 3 × 3 montage with its own white gutters). In the 3:2 crop it looks broken and unlike every other photo. | 5.9 §3: area photos are single photographs. Exclude collages/montages, maps, flags, coats of arms, panoramas > 3:1 and files < 800 px; otherwise use the `city` placeholder. | Architect (photo selection) |

## P2

| # | Screen | Finding | Suggestion |
| --- | --- | --- | --- |
| P2-01 | 5.11 (e2e 94) | The responsible line breaks before the dash: «За руль / — только трезвым». | Non-breaking space before «—» when rendering (the text itself is fixed copy). |
| P2-02 | 5.11 overview walks (`walk/free`, `tomorrow`) | Every row says «Часы работы уточняйте», under the line «Часы работы части мест взяты по умолчанию…». | Keep the top line, drop the per-row note when every stop has default hours. |
| P2-03 | 5.11 / 5.9 | Kind → pictogram: «Российский академический театр драмы» gets the monument sign; churches in museum walks get the museum sign. | Add a theatre kind → `museum` or a new `theatre` pictogram; churches → `church` (data/kind mapping). |
| P2-04 | 5.9 (e2e 91-3) | The Wikidata description «площадь в г. Иваново» just repeats the kind line, in lower case. | Hide descriptions that only repeat kind + town; capitalise the first letter and end with a full stop. |
| P2-05 | 5.11 (e2e 68, 92, 93, `shorter-engine`) | Ordinary 4–6 h walks get two hand-off buttons («Часть 1 из 2 / 2 из 2»), which pushes the column down by 66 dp. | Split only above the web limit actually hit; otherwise consider one button and a part chooser. Acceptable for release. |
| P2-06 | 5.9 bar (`card/bar`) | Bars (OSM) never have a photo, so every bar card is mostly an empty 3:2 placeholder. | Later: a short 3:1 bar plate instead of the full frame (frame rule exception for kinds with no photo source). |
| P2-07 | 5.9 offline (e2e 66) | Still «Фото пока нет» (the museum has no P18 photo, so this is correct). The offline copy was checked in `card/photo-states`. | Pick a POI with a photo for this e2e step. |

## Matches the spec

- **Budget (5.8)**:
  - CEO case: 30 000 ₽, 4 взр · 1 реб · пёс → «≈ 26 300 ₽ — подгоним под бюджет» → Road «✓ В БЮДЖЕТЕ ≈ 26 300 ₽» → Waybill lever lines «кафе попроще −3 600, бесплатные места −4 800, короткий вариант маршрута −24 200».
  - No-fit screen as `Budget.dc.html`.
  - Tight «ЧУТЬ БОЛЬШЕ: +1 100 ₽» (within tolerance), «ПЕРЕРАСХОД», and replace «не в бюджете» on a dearer option only.
- **Cards (5.9)**: real photos sit uniformly in the 3:2 frame (landscape crops; the portrait crop keeps the upper third; the SVG coat of arms and the tiny PNG are on the mat with the credit below). Further checks:
  - The scrim credit is legible on light skies.
  - «ФОТО РАЙОНА» label, mini sign in the title row, «Сообщить об ошибке».
  - Only sights and hotels are tappable.
  - The returned row flashes yellow 14 % (e2e 64, 85).
- **По городу (5.10/5.11)**:
  - Presets per city: Пивной in Ярославль/СПб, hidden where unsupported.
  - 18+ dialog each time, «не с детьми».
  - Daytime start in town time, «старт завтра в 09:00» / «Завтра: старт 09:00».
  - «Получилось 6,5 ч вместо 8 ч», «3,5 ч» chip, free walk «Бесплатно · вход везде свободный».
  - «САНКТ-» / «ПЕТЕРБУРГ» break, the responsible plate on drink walks only.
- **Location and search (5.12)**:
  - Header + field fixed while typing, «Мышкин», «Владивосток» and an address found with «© OpenStreetMap».
  - Rationale, «примерно, по сети», «Вы не в России».
- **Hand-off (5.13)**: day menu, stop menu with «Сообщить об ошибке», target line, truncated note, offline toast.
- **Night prefixes**: «Ночь 2: не нашли ночёвку…» / «Ночь 3: …» with the nearest hotel as the second line.
- **Copy**:
  - No English UI text. Remaining Latin is all proper names (Wikimedia Commons, OpenStreetMap, author names, the bar «Rocks») or the accepted «GPS», «PDF», «Pro».
  - «Яндекс» appears only in `handoff_*` (plus the unused deck keys).
  - `strings_pending_copy.xml` is empty.
