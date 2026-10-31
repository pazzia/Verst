# Sprint 4 — visual QA (Designer)

Build: dev/S4 `4058edd`, CI run 114 = 40211108864 (green, real `russia_v1` data). Sources: `ci-logs` → `runs/40211108864-1/e2e/screens/*` (100–153: airplane mode, slow/broken network, real-data journeys Фрязино ring, Москва → Тула, Москва → СПб fun, Фрязино → Екатеринбург, Москва → Казань, walks in Ярославль/Казань/Фрязино, card levels) and `screenshots/{road,waybill,handoff,instruments,city,walk,card}/*`. Checked against des/sprint-4 `a405594`: 5.1 §9, 5.3 §9, 5.5 §10–§10.9, 5.6 §9, 5.9 §9, 5.10 §10, 5.11 §10, 5.13 §5, components §24–§31, copy §16, and the S4 mockups.

Already known and with the Architect, not repeated: wrong category labels (Покрова на Нерли = ВИД, Золотые ворота = МУЗЕЙ; also seen: Ипатьевский = ПАРК, Плещеево озеро = КРЕМЛЬ, Коломенское = ПРИРОДА, Беседка = МУЗЕЙ/ПАМЯТНИК, Эрмитаж-Выборг = ПАРК/МУЗЕЙ), unnamed playground fun stops («Разминка · Детская площадка»), the bare «Остановка у дороги», extract punctuation («в Покрове .», «хозяйства , в»).

Severity: **P0** wrong information on a CEO path or a broken journey · **P1** visible deviation from an approved spec / CEO ask, fix before the CEO build · **P2** polish.

## P0

None. All journeys finish; no error screens (airplane mode, slow, HTTP 500 and garbage answers all keep the screen); no English UI text; «Яндекс» only in hand-off.

## P1

| # | Screen | Finding | Fix | Owner |
| --- | --- | --- | --- | --- |
| P1-01 | 5.5 rows, day headers (`road/s4-rows`, e2e 121, 150, 153) | **Food and rest-area rows have no P part** (Трапезная у кремля, Кафе «Привал», every «Площадка отдыха»): only «≈ 2 100 ₽» / «0 ₽». The CEO asked for parking on every stop where you leave the car. Knock-on: day 1 header says «P ≈ 600 ₽» although it has an unknown stop, while the Waybill says «+ ещё 4 без данных» and lists only one «?». | Every left-the-car stop gets a P part, «P ?» when unknown; day header «≈ N ₽ + ?» when the day has an unknown; Waybill breakdown lists every unknown stop (5.5 §10.10). | Developer (+ Architect if food/rest stops lack a `parking` object) |
| P1-02 | 5.12 address search (e2e 105, 107, 108) | «уточним при интернете» is shown **online**: while a slow request is still running, after HTTP 500 and after an unreadable answer. It tells a connected user to wait for the internet. | Slow → the «Ищем адрес…» spinner (5.12) / shimmer after 300 ms; error → new `addr_failed` «Не получилось найти адрес — попробуйте ещё раз» (generic `online_failed`). `online_later` only when offline (5.5 §10.9). | Developer |
| P1-03 | 5.5 costs line (e2e 121, 122, `road/s4-rows`) | «заменить» and «Выбрать отель →» drop to their own line under the costs whenever «вход свободный · P бесплатно» or a hotel cost is long, which re-adds the line the declutter removed. | Action pinned right on the first costs line; the P part wraps under the price instead (5.5 §10.10). | Developer |
| P1-04 | 5.5 parking sheet, unknown (`road/s4-parking-unknown`) | The «?» sheet says «≈ — цена примерная. Сумма уже в путевом листе и в бюджете», which is false for an unknown tariff. | `road_parking_note_unknown` for «P ?». | Developer |
| P1-05 | 5.9 card level 4 / OSM-only (e2e 148, `card/s4-osm-only`) | Places known only from OSM show no «Данные о месте: © участники OpenStreetMap» line. That is the ODbL attribution (5.9 §9), so it is a licence issue, not polish. | Show the source line whenever the place's data comes from OSM, at every level. | Developer |

## P2

| # | Screen | Finding | Suggestion |
| --- | --- | --- | --- |
| P2-01 | 5.5 / 5.9 signs | The brown-sign pictogram does not follow the kind: parks and «Канал имени Москвы» get the walker, a museum card's mini sign is an obelisk while its illustration is the museum, the playground illustration is a building | Map pictogram from `kind` (one table for row sign, mini sign and illustration) |
| P2-02 | 5.11 rows (`walk/untimed`, `walk/dog-warning`) | «сегодня 10:00–18:00 · открыто» next to «Часы работы уточняйте»; «Часы работы уточняйте С собакой внутрь нельзя.» (missing full stop) | Drop the per-row «уточняйте» when hours are known; join note parts with «. » |
| P2-03 | 5.5 top (e2e 130) | Three info lines before the first row (approx distances, km-post legend, open-data legend) | One line: «Расстояния приблизительные · ⚬ открытые данные · О данных», km legend second |
| P2-04 | 5.5 hotel row (e2e 132) | The night note is clamped at 2 lines mid-sentence («Ваши 500…») | Engine: shorter hotel reasons (≤ 90 chars) |
| P2-05 | 5.13 sheet (e2e 42) | «Установить из магазина приложений» sits as a right column squeezing the Навигатор text | Put it as the note line under the sub (components §30) |
| P2-06 | 5.9 offline uncached (e2e 96, 66) | Uses the Sprint 3 grey placeholder, while online cards without photo use the S4 category illustration | Use the category illustration + `card_photo_offline` caption |
| P2-07 | 5.11 untimed (e2e 141) | Two hand-off buttons for one walk (known from S3) | as S3 P2-05 |

## Matches the approved design

- **Km posts and car:** posts on the right edge, the car in the left lane; no overlap in any screenshot (checked every post in `road/s4-rows`, e2e 120–153). The car reads clearly on the asphalt.
- **Costs line** with the inline P where present; parking sheet (Коломенское: zone, tariff, Sunday rule, where); day header P totals; footer «из них парковки ≈ 1 500 ₽ / бесплатно».
- **Category tags** and «Разминка 30 мин» tags render as specified (labels aside).
- **Hand-off chooser:** day tabs + «До след.», Карты «весь день» first unsigned, Навигатор «не установлен» dimmed, explanation, «Запомнить выбор».
- **Waybill «Парковки»:** line, formula «5 стоянок + ещё 4 без данных», expandable breakdown, counted in ИТОГО.
- **Moods:** «Спокойно / Весело и познавательно / Только доехать» cards, crew line under the fun card.
- **По городу:** big entry plate on the Windshield; start field, crew cells, dog preset first with the dog, 18+ only «Вам есть 18?», child + beer warning (no block), «без ограничения» with no times and hours pills, live filters with «Пересобираем прогулку…», dog warnings with actions, «Для 8 ч рядом мало мест» with engine suggestions, free footer.
- **Cards levels 1–4:** photo + Wikipedia text; category illustration with text; illustration + «фото пока нет» only without text.
- **Offline:** airplane-mode road, card, waybill and walk work; address search offline hint; no banners, no freshness labels.

## Spec changes in this round

5.5 §10.9 (`online_later` offline only; `online_failed`), §10.10 (action pinned, P part on every left-the-car stop, unknown note); copy `online_failed`, `addr_failed`, `road_parking_note_unknown`. This branch is fast-forwarded to des/sprint-4 `a405594` (not yet on main) so the review sits next to the specs it checks.
