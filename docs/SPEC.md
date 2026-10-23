# Verst — MVP Technical Specification

Oct 23, 2026 · @DMITRII

## 1. Overview

Verst («Верста») is an Android app that plans a road trip across Russia in seconds: from any point to any point, or a ready-made trip near the user's start, tuned to the crew, a comfortable daily mileage and a budget, with the full cost calculation always visible. The MVP implements design variant 5 «За рулём» ("Behind the wheel"), rated 5/5 by the CEO: the whole UI is the view from the driver's seat.

### Problem

- Generic AI planners invent routes: they do not check opening hours, real driving times, or whether a hotel accepts dogs.
- Map apps (Yandex, 2GIS) navigate but do not plan a multi-day trip around a family, a pet, a pace and a budget.
- The closest Russian competitor tested by the CEO (Trippi, Moscow–Perm) hung for 10 minutes with no result, had an English-only UI and required registration before showing anything.

### MVP goals

1. Build a usable multi-day car route from any address A to any address B in Russia in under 10 seconds (p95), with no registration.
2. Offer curated ready-made trips within 300 and 700 km of the user's start (launch region: Moscow).
3. Place overnight stops by the user's daily mileage, shifted to the best nearby town (the core differentiator).
4. Show a transparent cost breakdown with formulas: fuel, tolls, lodging, food, tickets, 10% reserve.
5. Earn affiliate revenue from hotel and excursion bookings.
6. Work offline once a trip is saved.

### Success metrics for the MVP (first 3 months after release)

| Metric | Target | How measured |
| --- | --- | --- |
| Time to first route (install → route shown) | median < 90 s | analytics funnel |
| Plan request success rate | ≥ 95% | backend logs |
| Plan latency | p95 < 10 s | backend metrics |
| Users who build ≥ 1 route | ≥ 60% of installs | analytics |
| Affiliate click-through on overnight stops | ≥ 8% of built trips | analytics + partner reports |
| Cost estimate error vs real receipts | ≤ 15% on 3 test trips | manual test drives |
| Crash-free sessions | ≥ 99.5% | crash reporting |

### Glossary

| Term | Meaning |
| --- | --- |
| Trip | One planned journey: start, destination, vias, crew, rules, days, stops, cost |
| Ready route | A curated trip template anchored to an origin city (e.g. Golden Ring from Moscow) |
| Stop | A point on the trip: start, sight, food, fuel, rest, overnight, finish |
| Leg / day | The part of a trip driven in one day, ending at an overnight stop or the finish |
| Daily mileage | The user's comfortable km per day (150–900) |
| Crew | Adults, children and a dog travelling together |
| Corridor | The area within N km of the route polyline where stops may be picked |
| Place DB | Verst's own curated database of places with family/dog/parking tags |
| Trip Pro | The paid tier (scope in section 14) |

## 2. MVP scope

The MVP is a native Android app with a Russian-only UI, a small backend and a curated place database for the Moscow launch region; turn-by-turn navigation is handed off to Yandex Navigator or 2GIS.

### In scope

| Area | Included in MVP |
| --- | --- |
| Platform | Android 8.0+ (API 26+), phones only, portrait; distributed via RuStore |
| Language | UI in Russian only; code, comments and this spec in English |
| Account | None. Anonymous device ID; first route with zero sign-up |
| Start point | Current location (with permission) or any typed address |
| Destination | Any city, address, place or map point in Russia (free search) + optional vias (up to 3) |
| Ready routes | Curated trips near the start: 10–15 for Moscow at launch, shown on the overhead sign |
| Trip parameters | Crew (adults, children, dog, front passenger), daily mileage, budget, fuel consumption, start date and time |
| Route engine | Day split, overnight town shift, fuel/food/rest/sight stops, schedule, alternatives per stop |
| Cost | Fuel, tolls, lodging, food, tickets, 10% reserve toggle, per person, vs budget, formula per line |
| Booking | Affiliate deep links to Yandex Travel (hotels) and Tripster (excursions) via Travelpayouts |
| Offline | Saved trips fully readable offline; share as text and deep link |
| Hand-off | "Open in navigator" per day/leg: Yandex Navigator, Yandex Maps, 2GIS deep links |
| Analytics | AppMetrica events + crash reporting |
| Admin | Web admin for curators to add/verify places and ready routes |

### Out of scope (later versions)

- iOS, tablets, landscape, dark/light theme switch (the design is dark by nature).
- Own turn-by-turn navigation and in-app interactive map (an in-app map may come in v1.1).
- User accounts, cloud sync between devices, social features, reviews written by users.
- Payments inside the app (Trip Pro billing) — MVP ships a Pro waitlist, see section 14.
- Live hotel prices and availability inside the app — the app shows an estimate and links out.
- Trips outside Russia; non-car transport; EV charging planning.
- Push notifications, widgets, Android Auto.

### Assumptions

- Launch region: Moscow and routes up to \~1,000 km from it; free search works for all Russia but places outside curated regions come only from external POI data and are marked "не проверено" (not verified).
- One car per trip; vehicle class 1 (passenger car) for tolls.
- Prices are regional averages refreshed monthly; the UI always labels totals as an estimate.

## 3. Users and user stories

The primary user is a family driver planning a 1–4 day trip by car; every story below must work without registration.

### Personas

| Persona | Situation | What they need from Verst |
| --- | --- | --- |
| Family driver (primary) | 2 adults, 1–2 children, often a dog; weekend or holiday trip from a big city | Safe pace, kid-friendly food, dog-friendly hotels, a cost they can trust |
| Couple on a weekend | 2 adults, flexible budget, wants sights and good food | Ready routes nearby, interesting stops, quick booking |
| Long-haul driver | 1–2 adults, 800–1,500 km to a destination | Fast route, fuel and rest stops, one overnight at a good town |

### User stories and acceptance criteria

| ID | As a… | I want to… | Acceptance criteria |
| --- | --- | --- | --- |
| US-01 | new user | see ready trips near me right after install | Windshield shows ≥ 3 ready routes within 300 km of the detected or default start (Moscow) within 2 s of launch; no sign-up |
| US-02 | user | plan a trip from any address to any address | Navigator accepts city, street address, place name or map pin; suggestions appear ≤ 500 ms after typing 2+ characters; works for any point in Russia |
| US-03 | user | add places to visit on the way | Up to 3 vias; order can be changed; route recalculates |
| US-04 | parent | say who is in the car | Crew editor supports 1–7 adults, 0–5 children, dog yes/no; child seats affect stop choice (kid menu, playgrounds) |
| US-05 | dog owner | only see dog-friendly overnights | When dog = yes, overnight candidates without the `dogs_allowed` tag are excluded; if none exist, the app says so and offers the nearest alternative |
| US-06 | driver | set my comfortable km per day | 150–900 km in 50 km steps; day split never exceeds the limit by more than 5% |
| US-07 | user | set a budget | Budget presets 20k / 30k / 40k / 60k / 80k / no limit; the cost screen shows remaining or overspend |
| US-08 | user | see why an overnight town was picked | Each overnight shows a one-sentence reason (e.g. "30 km earlier: more dog-friendly hotels") and the candidates considered |
| US-09 | user | replace a stop I don't like | Each replaceable stop offers 2–3 alternatives in the same time window; cost and schedule update instantly |
| US-10 | user | see the full cost with formulas | Every cost line shows its formula; reserve 10% toggles; totals update ≤ 100 ms |
| US-11 | user | book the hotel | "Забронировать" opens Yandex Travel with city, dates and guests prefilled through an affiliate link |
| US-12 | user | use the trip with no signal | A saved trip opens offline with all stops, times, costs and reasons; booking and navigation buttons explain they need internet |
| US-13 | user | drive the route | "Open in navigator" opens the current day in Yandex Navigator / Yandex Maps / 2GIS with stops as waypoints |
| US-14 | user | share the trip | Share sends a text summary + deep link; recipients without the app get the text |

## 4. Information architecture and navigation

The app is one forward path with no tab bar: the user moves from the windshield to the itinerary and out to partner apps, and comes back with the system back gesture.

&#91;embedded content: navigation map · 7 screens + partner apps\]

The Road ahead screen is also the hub for a saved trip: "Мои поездки" on the Windshield opens a saved trip directly there, and long-press on any stop opens the day in an external navigator.

| Screen | Entry points | Exits |
| --- | --- | --- |
| 5.1 Windshield | App launch | Navigator, Instruments (ready route or mirror), Мои поездки → Road ahead |
| 5.2 Navigator | Windshield | Instruments, map picker (modal) |
| 5.3 Instruments | Windshield, Navigator | Drive |
| 5.4 Drive | Instruments | Road ahead (auto), back cancels |
| 5.5 Road ahead | Drive, saved trip | Waybill, Exit, external navigator, share |
| 5.6 Waybill | Road ahead | Share, save, Trip Pro waitlist |
| 5.7 Exit to overnight | Road ahead hotel row | Partner booking (external) |

## 5. Screen-by-screen specification

Seven screens implement design v5 exactly as on the [design canvas](https://claude.ai/artifact/26v1hYwKc7yqnnrTxCs1KS), page "Вариант 5 · За рулём"; the canvas is the visual source of truth, this section is the behavioural one. All copy below is the Russian UI text.

### 5.1 Windshield («Лобовое стекло») — home

**Purpose:** show ready trips near the start and the entry to free search.

**Layout (top to bottom):**

1. Windshield scene, 0–540 dp: flat posterised sunset sky bands, horizon with hills, a 3D road receding to the horizon with animated centre dashes, roadside posts flying past, A-pillars and roof liner framing the edges.
2. Rear-view mirror, top centre: shows the crew silhouettes (adults, child, dog) and the label "2 взр · 1 реб · пёс". Tap → Instruments (5.3).
3. Overhead blue sign (GOST blue, white inner border) titled "РЯДОМ С ВАМИ · ИЗ <ГОРОД>" with 4 rows: arrow, ready-route name, km. Footer "ещё N маршрутов в радиусе 300 км ↓" opens the full list (bottom sheet, same sign style).
4. Dashboard, 520 dp to bottom: navigator screen with "Куда угодно" search entry and "ВЫ: <город>"; below it the selected route caption and the round red-ringed "ПОЕХАЛИ" start button.

**Behaviour:**

- On launch, resolve the start: last used start → coarse location (if permission granted) → Moscow default. Location permission is requested only when the user taps "ВЫ: <город>" or on first launch with a one-line rationale; denial is fine.
- Ready routes: `GET /v1/ready-routes?lat&lon&limit=20`, sorted by distance from start; first 4 on the sign. Arrow direction = bearing from start to the route's first destination, snapped to 8 directions.
- Tapping a row selects it (yellow arrow and text); the caption updates; "ПОЕХАЛИ" → Instruments with the ready route preloaded.
- Tapping the navigator → Navigator (5.2).

**States:** loading (sign rows as shimmering blank plates, ≤ 2 s), offline (sign shows ready routes cached from the last session; if none, "Нет сети — готовые маршруты появятся, когда будет интернет" and the navigator still works for saved trips), no ready routes near start (sign shows "Рядом пока нет готовых маршрутов" and the navigator is highlighted).

**Saved trips:** if the user has saved trips, a small "Мои поездки" plate on the dashboard opens a list (bottom sheet) of saved trips.

### 5.2 Navigator («Навигатор») — any A → any B

**Purpose:** free search for start, destination and vias anywhere in Russia.

- Fields: ОТКУДА (default: current start, "изменить"), КУДА (focused on open), "+ заехать по пути" (max 3 vias, drag to reorder, × to remove), "точка на карте" (opens a full-screen map picker, MapLibre, single pin).
- Suggestions: `GET /v1/geocode/suggest?q&lat&lon` after 2 characters, debounce 250 ms, up to 6 results. Each row: type badge (Г city · У street · М place), name, region, distance from start.
- Recent searches (local, last 10) shown when the field is empty.
- Bottom: route caption "\<A> → \<B>" + distance (straight-line until planned) and "ПОЕХАЛИ" → Instruments.
- Validation: A and B must differ by ≥ 20 km road distance, otherwise show "Слишком близко для поездки на машине"; B must be reachable by car (routing error → "Не нашли дорогу на машине до этой точки").

### 5.3 Instruments («Приборы») — crew, pace, budget

- **Mirror (crew):** back row of 3 seats; tap cycles empty → adult → child → empty; dog in the boot toggles on tap (wagging animation when on); front passenger chip "Рядом с вами: взрослый / никого". Driver is always 1 adult. Limits: up to 7 adults total, 5 children.
- **Odometer (daily km):** 4-digit mechanical counter, − / + in 50 km steps, 150–900, default 300 for trips < 800 km and 500 otherwise. Below: "≈ X ч Y мин за рулём" and "N дней".
- **Fuel gauge (budget):** needle E→F, presets 20 000 / 30 000 / 40 000 / 60 000 / 80 000 / "не важно".
- **Settings (secondary, gear icon on the dashboard):** fuel consumption (default 8.0 l/100 km, 4–20), fuel type (АИ-92 / АИ-95 / ДТ), tank volume (default 50 l), start date (default next Saturday) and start time (default 08:00), "избегать платных дорог" toggle.
- **Mood (optional chips):** "Спокойно, с детьми" · "Побольше остановок" · "Просто доехать" — maps to stop density (section 7).
- "ПОЕХАЛИ" → Drive (5.4) and calls `POST /v1/trips/plan`.
- All values persist locally as the user's defaults for the next trip.

### 5.4 Drive («Поехали») — plan in progress

- Windshield with accelerating road; road signs for the future stops fly toward the viewer as soon as the server streams them.
- Navigator panel shows real progress steps streamed from the backend (SSE): "Делим путь на N дней", "Ищем отели, куда пустят с собакой", "Сверяем часы работы", "Считаем бензин".
- A progress bar fills by stage. On success → "Дорога готова — смотреть знаки" (auto-advance after 1 s).
- Timeout: 20 s → "Строим дольше обычного…" with "Подождать" / "Упростить маршрут" (drops sights). Error → plain message + "Попробовать ещё раз". The user can go back at any time; the request is cancelled.

### 5.5 Road ahead («Дорога впереди») — the itinerary

- Header: overhead sign with trip name and km; chips: days · nights, crew, km/day.
- Left: a vertical road with a moving car marker; each stop is a GOST-styled road sign mounted on a post with a row of text:
  - city entrance sign (white, black border) for start/finish/towns;
  - brown tourist sign for sights;
  - blue service signs for fuel (7.3), food (7.7), rest area (7.11), hotel (7.12).
- Row text: "через N км" (from previous stop), arrival time, name, one-line note, tags (с собакой, детское меню, парковка), cost, actions.
- Day headers: "День 1 · 265 км · ≈ 4 ч за рулём".
- Actions: "заменить" (bottom sheet with 2–3 alternatives, each with Δ time and Δ cost; choose → schedule and cost recompute locally from the alternatives payload, then `POST /v1/trips/{id}/stops/{stopId}/replace` to confirm); hotel rows → "Выбрать отель →" (Exit, 5.7); long-press any stop → "Открыть в навигаторе отсюда".
- Footer button: "ПУТЕВОЙ ЛИСТ · ≈ 34 500 ₽" → Waybill (5.6). Secondary: "Сохранить офлайн", "Открыть день в навигаторе", "Поделиться".

### 5.6 Waybill («Путевой лист») — cost

- A form-styled sheet: route, crew, mileage; a table "СТАТЬЯ И РАСЧЁТ | ₽" with one row per cost category and the formula in handwriting style; reserve 10% checkbox; ИТОГО; "Выдано" (budget) and "Остаток" (remaining, red if negative); stamp animation "ВЕРСТА · В ПУТЬ ГОТОВЫ".
- Footnote: "Пример расчёта: цены средние по трассе, точные — при бронировании" (wording becomes "Расчёт" once real data is wired).
- Tapping a row expands its breakdown (e.g. fuel by region, hotel per night).
- Buttons: "Сохранить офлайн", "Отправить экипажу" (share sheet with text summary).

### 5.7 Exit to overnight («Съезд к ночёвке»)

- Dusk windshield with an exit sign "<Город> · центр" + hotel sign and distance; blinking turn signal.
- Navigator panel: "НОЧЁВКА k ИЗ n · КМ x · время", town name, the reason sentence, 2–3 hotel options (name or district, tags, price per night for the crew), radio selection.
- "Забронировать ночь" → affiliate deep link (section 10) with check-in/out dates, guests and the hotel or city prefilled; on return to the app, ask "Забронировали?" (yes → mark booked locally).

### Common rules for all screens

- Back: system back and a top-left text back link; no bottom navigation bar.
- Touch targets ≥ 44 dp; all interactive sign rows are buttons with content descriptions.
- Every animation has a reduced-motion fallback (static frame) when the system "remove animations" setting is on.
- Numbers use thin-space thousands separators ("34 500 ₽"), "≈" for estimates, 24-hour time.

## 6. Design system

The app is a single dark visual world (the car interior at dusk); there is no light theme in the MVP. Tokens below are the only allowed colours and type styles in code.

### Colour tokens

| Token | Hex | Use |
| --- | --- | --- |
| `dash` | #141416 | App background, dashboard |
| `dash.raised` | #161618 | Dashboard surface |
| `dash.control` | #232327 / #2A2A2E | Bezels, buttons, odometer frame |
| `text.primary` | #F4F4F0 | Main text on dark |
| `text.secondary` | #B9B9C0 | Secondary text |
| `text.muted` | #8C8C93 | Labels, captions (min 11 sp) |
| `sign.blue` | #1E4FA3 | GOST blue road signs, overhead sign |
| `sign.brown` | #6B3E26 | Tourist (sight) signs |
| `sign.white` | #F4F4F0 | City sign, sign borders, pictogram plates |
| `accent.yellow` | #FFD23F | Selection, primary actions, prices |
| `accent.red` | #D8402B | Start button ring |
| `signal.green` | #6FD18A | Turn signal only |
| `navi.screen` | #0B1218 | Navigator display |
| `navi.field` | #16222C, border #2B3D4D | Inputs on the navigator |
| `navi.label` | #7FA6D9 / #8FA4B8 | Navigator labels |
| `sky.1…5` | #2B2850, #4E3768, #8E4A6B, #D9655A, #F29A5E | Sunset bands (top → horizon) |
| `sun` | #FFD99A | Sun disc |
| `ground` / `road` | #2C3A33 / #3A3A3F | Fields / asphalt |
| `paper` | #EEF2F4, lines #9FB0BE, ink #1B3FA0, stamp #5B3FA0 | Waybill form |

Contrast: all text pairs must meet WCAG AA (4.5:1 for body, 3:1 for ≥ 18 sp bold). Yellow text is used only on dark backgrounds.

### Typography

| Style | Font | Size / weight | Use |
| --- | --- | --- | --- |
| Display | IBM Plex Sans Condensed | 28 sp / 700 | Screen titles |
| Sign | IBM Plex Sans Condensed | 18–20 sp / 600–700, tabular numbers | Road signs, distances |
| Title | IBM Plex Sans Condensed | 17–22 sp / 700 | Stop names, totals |
| Body | IBM Plex Sans Condensed | 13–15 sp / 400–500 | Notes, descriptions |
| Label | IBM Plex Sans Condensed | 11 sp / 600, letter-spacing 0.08 em, uppercase | Section labels |
| Odometer | IBM Plex Mono | 22 sp / 600 | Odometer digits |
| Handwriting | Marck Script | 15–26 sp | Waybill values only |

Fonts are bundled in the APK (OFL licence), not downloaded at runtime. Cyrillic glyph coverage is required.

### Components

| Component | Spec |
| --- | --- |
| `OverheadSign` | Blue plate, 4 dp outer padding, 2 dp white inner border, radius 9/6 dp; rows = buttons ≥ 42 dp high with arrow icon, name, km |
| `RoadSign` | Variants: `city` (white, 3 dp black border + 2 dp white outline), `tourist` (brown, white border, white pictogram), `service` (blue frame, white square, black pictogram: fuel, food, rest, hotel) |
| `Mirror` | Rounded rect radius 22–40 dp, 3–5 dp bezel, reflection bands, crew silhouettes, seat buttons |
| `Odometer` | 4 digit drums 24×34 dp, last drum inverted (white), roll animation 300 ms on change |
| `FuelGauge` | Arc 180°, E (red) to F, needle with spring animation (stiffness 300, damping 0.6) |
| `StartButton` | 92 dp outer bezel, 76 dp face, 3 dp red ring, pulsing ring 1.8 s |
| `NaviPanel` | 6 dp bezel #232327, radius 16 dp, inner padding 12 dp |
| `Windshield` | Sky bands, sun, hills, 3D road, posts, A-pillars; drawn on Canvas |
| `WaybillSheet` | Paper card with clipboard clip, form grid, stamp |

### Motion

| Animation | Spec |
| --- | --- |
| Lane dashes | Scroll speed 160 dp per 0.9 s at idle; 0.45 s on the Drive screen |
| Roadside posts | Scale 0.3 → 2.2 along a perspective path, 2.6 s ease-in, two posts offset by 1.3 s |
| Flying signs (Drive) | Scale 0.12 → 1.7, translate toward the screen edge, 3.6 s, staggered 1.2 s |
| Selection | 200 ms colour cross-fade |
| Stamp | Scale 2.4 → 1.0 with overshoot, 500 ms, delay 1 s |
| Turn signal | 0.9 s blink, 55% on |

All continuous animations pause when the screen is not visible and when "Remove animations" is on. Target 60 fps on a mid-range device (e.g. Samsung Galaxy A34).

## 7. Route engine

The engine is deterministic: it plans on top of a car routing service and the curated Place DB, with no LLM in the MVP planning path, so the same input always gives the same trip and every choice can be explained.

### 7.1 Input

| Field | Type | Rules |
| --- | --- | --- |
| `origin` | point + label | Required |
| `destination` | point + label | Required unless `readyRouteId` is set |
| `vias` | list of points, ≤ 3 | Visited in the given order |
| `readyRouteId` | string | Uses the template's ordered points, nights hint and curated stops |
| `roundTrip` | bool | Return to origin; default true for ready routes, false otherwise |
| `crew` | `{adults 1–7, children 0–5, dog bool}` | Driver counted in adults |
| `dailyKm` | int 150–900 | Step 50 |
| `budget` | int or null | RUB |
| `vehicle` | `{consumption l/100km, fuel type, tank l}` | Defaults 8.0 / АИ-95 / 50 |
| `startAt` | local datetime | Default next Saturday 08:00 |
| `mood` | `calm` · `more_stops` · `just_drive` | Default `calm` when children > 0 |
| `avoidTolls` | bool | Default false |

### 7.2 Pipeline

1. **Resolve points.** Snap each point to the nearest drivable road (≤ 2 km); fail with `UNREACHABLE` otherwise.
2. **Base route.** Request a car route A → vias → B (→ A if round trip) from the routing service with `avoidTolls`. Keep the polyline, per-segment distance and duration, and road references (e.g. М-4, Р-22).
3. **Corridor.** Build a corridor of 15 km either side of the polyline (5 km on motorways for fuel/rest; 25 km for overnight towns). Pre-fetch Place DB candidates in the corridor with their distance along the route (`kmAt`) and detour time.
4. **Day split.** Days N = ceil(total km / dailyKm). Target end of day d = d × total / N (an even split, never above dailyKm). For ready routes, use the template's suggested nights when they fit the user's dailyKm ±10%.
5. **Overnight choice (the differentiator).** For each day boundary, consider towns with ≥ 1 lodging that passes crew filters, positioned between 70% and 105% of the day's target km. Score each and pick the maximum; ties → closer to target.
6. **Fuel stops.** Usable range = tank × 0.8 / consumption × 100. Walk along the route; when remaining range < 20% of tank range, insert the best fuel station in the next 40 km, preferring stations that coincide (≤ 2 km) with another planned stop.
7. **Rest stops.** Insert a break every R hours of driving: `calm` 2 h, `more_stops` 1.5 h, `just_drive` 3 h; rest areas, playgrounds (if children) or a short sight; dog = yes adds a dog-walk tag preference.
8. **Meals.** Lunch window 12:00–14:30, dinner at the overnight town; prefer places tagged `kids_menu` when children > 0.
9. **Sights.** Fill remaining daily time budget (max 9 h on the road incl. stops for `calm`, 10 h otherwise) with the highest-rated sights within the corridor whose opening hours cover the arrival time; `just_drive` adds none except the destination.
10. **Schedule.** Compute arrival/departure for each stop from routing durations + dwell times; re-run steps 6–9 once if a day exceeds its time budget, dropping lowest-score sights first.
11. **Alternatives.** For every replaceable stop, keep the next 2–3 candidates that fit the same time window ±45 min, with Δ time and Δ cost.
12. **Cost.** Run the cost model (section 8).
13. **Explain.** Generate reason strings from templates (7.5).

### 7.3 Overnight score

```latex
S = 3\cdot H_{fit} + 2\cdot Q_{town} + 1.5\cdot E_{evening} - 2\cdot\frac{|km - km_{target}|}{100} - 1\cdot\frac{detour_{min}}{15}
```

H fit = number of lodgings passing crew filters (dog, family room, parking), capped at 5. Q town = curated town quality 0–3. E evening = 1 if the town has an evening sight or walk open after arrival. Coefficients are config values, tuned on test trips.

### 7.4 Dwell times (defaults, config)

| Stop type | Minutes |
| --- | --- |
| Coffee / WC | 15 |
| Fuel | 10 (15 with coffee) |
| Rest area / dog walk | 20 |
| Lunch | 60 |
| Sight | curated per place, default 60 |
| Overnight | until next day's start (default 09:00) |

### 7.5 Explanations

Every overnight and every inserted stop carries a short Russian reason built from templates, e.g. "На 30 км раньше вашего предела: здесь больше отелей, куда пускают с собакой" or "Заправиться с вечера, чтобы утром сразу ехать". Templates live in backend config, not in code.

### 7.6 Ready routes near the start

- A ready route = curated template: origin hub (city), ordered points, suggested nights, curated stops, cover image key, tags, typical km and days.
- Shown when the user's start is within 50 km of the hub; distance shown = template km from the hub.
- Rings: "на выходные" ≤ 300 km one way, "на 3–4 дня" ≤ 700 km.
- Launch set (Moscow hub): Золотое кольцо, Ярославль, Суздаль · Владимир, Тула · Ясная Поляна, Тверь · Торжок, Рязань · Константиново, Калуга · Таруса, Нижний Новгород → Казань, Великий Новгород, Карелия (≈1,000 km) — final list to be confirmed by the CEO.

### 7.7 Performance

Plan p95 < 10 s for ≤ 1,500 km, streamed in stages (SSE events `stage`, `stop`, `done`, `error`). Routing results are cached by rounded coordinates for 24 h.

## 8. Cost model

Every total shown in the app is the sum of six lines, each computed server-side with its formula string returned to the client, so the Waybill can display exactly how a number was produced.

| Line | Formula | Data source |
| --- | --- | --- |
| Fuel | Σ over regions crossed: km in region × consumption / 100 × price(region, fuel type) | Regional average fuel prices table, refreshed monthly |
| Tolls | Σ toll segments on the route × tariff(segment, class 1, time of day) | Toll tariff table maintained by curators (М-1, М-3, М-4, М-11, М-12 and others) |
| Lodging | Σ nights × chosen hotel price for the crew (rooms = ceil(adults / 2), children share) | Place DB price per night; partner price shown at booking |
| Food | people × meals × average check(place or region) | Place DB average check; regional default by town size |
| Tickets | Σ sights × (adults × adult price + children × child price) | Place DB ticket prices; 0 for free sights |
| Reserve | 10% of the sum above, toggleable, on by default | Constant in config |

```latex
Total = Fuel + Tolls + Lodging + Food + Tickets + Reserve
```

### Rules

- Meals per day: breakfast at the hotel is assumed included unless the hotel says otherwise; lunch and dinner on the road; first day starts after breakfast at home.
- Children under 7 count as 0.5 for food; under 18 use child ticket prices when they exist.
- Rounding: lines to the nearest 10 ₽; total to the nearest 100 ₽; prefix "≈".
- Per person = total / (adults + children), rounded to 100 ₽.
- Budget check: remaining = budget − total; negative → red "перерасход" and a hint (cheaper overnight, fewer sights, "Просто доехать").
- Replacing a stop or changing the crew recomputes only the affected lines on the device using the returned unit prices; the server recomputes on save.
- Freshness: each line carries `asOf`; the UI shows "цены на <месяц год>" in the Waybill footnote.

### Accuracy target

The estimate must be within 15% of real receipts on three test trips before release (section 17). Fuel and lodging dominate the error; they are checked first.

## 9. Data model and Place DB

The curated Place DB is the product's moat: tags like "dogs allowed" or "kids menu" are not in open data, so they are collected and verified by curators and stored in PostgreSQL + PostGIS.

### Entities

| Entity | Key fields |
| --- | --- |
| `place` | id (uuid), type (`sight` · `food` · `fuel` · `rest` · `lodging` · `town`), name\_ru, geom (point, SRID 4326), address, region\_code, town\_id, opening\_hours (OSM syntax), dwell\_min, avg\_check\_rub, price\_night\_rub, ticket\_adult\_rub, ticket\_child\_rub, rating\_internal (0–5), tags\[\], description\_ru (≤ 280 chars), photo\_keys\[\], partner\_ids (yandex\_travel\_id, tripster\_id), source (`curated` · `osm` · `partner`), verified\_at, verified\_by, status (`draft` · `live` · `hidden`) |
| `town` | id, name\_ru, geom, region\_code, population, quality (0–3), evening\_walk (bool), lodging\_count\_cache |
| `ready_route` | id, hub\_town\_id, title\_ru, subtitle\_ru, points (ordered place/town ids), suggested\_nights\[\], km\_total, days\_min, days\_max, tags\[\], cover\_key, sort, status |
| `region_price` | region\_code, fuel\_type, price\_rub, as\_of |
| `toll_segment` | id, road\_ref, geom (linestring), tariff\_day\_rub, tariff\_night\_rub, vehicle\_class, as\_of |
| `trip` | id, device\_id, input (jsonb), result (jsonb: days, stops, cost, reasons), created\_at, saved (bool), share\_slug |
| `trip_stop` | trip\_id, seq, day, place\_id, kind, arrive\_at, depart\_at, km\_from\_prev, km\_at, cost\_rub, reason\_ru, alternatives (jsonb) |
| `device` | id (uuid), created\_at, app\_version, locale, last\_seen\_at — no personal data |
| `feedback` | id, device\_id, trip\_id, place\_id, kind (`closed` · `wrong_tag` · `price` · `other`), text, created\_at |

### Tags (closed list, MVP)

`dogs_allowed`, `kids_menu`, `playground`, `family_room`, `parking`, `parking_guarded`, `ev_charger`, `wc`, `cafe_at_fuel`, `24h`, `view`, `walk`, `museum`, `kremlin`, `monastery`, `evening`, `free_entry`, `cash_only`.

### Curation workflow

1. Import OSM POIs for the corridor of each ready route (fuel, food, lodging, tourism) into `draft`.
2. Curator verifies each place by phone/site/maps reviews: hours, prices, tags; sets `live`, `verified_at`.
3. Places not verified in 180 days are flagged for re-check; user `feedback` with `closed` hides a place after 2 reports until re-verified.
4. Launch target: all stops of the 10 Moscow ready routes verified, plus ≥ 300 live places on the main corridors (М-4, М-7, М-8, М-10/М-11, М-12, Р-22, М-2).

### Outside curated regions

Free-search trips outside curated corridors use OSM places only; such stops show the label "не проверено" and the reason "По открытым данным". Lodging without dog info is never shown as dog-friendly.

## 10. Third-party integrations

The MVP runs routing and search on a self-hosted OpenStreetMap stack and hands navigation off to installed apps, because Yandex MapKit's free tier stops at 1,000 daily users and excludes offline maps ([Yandex MapKit licensing](https://yandex.ru/dev/commercial/doc/ru/concepts/mapkit)).

| Need | MVP choice | Why | Fallback / later |
| --- | --- | --- | --- |
| Car routing | GraphHopper (self-hosted, OSM Russia extract, car profile, `toll` and `avoid` support) | No per-request fees, returns road refs and toll flags, custom models | OSRM; Yandex Router API if quality issues |
| Search / geocoding (any address) | Photon (self-hosted, OSM, Russian language) for suggest + reverse geocoding | Free, fast typeahead, covers all of Russia | Yandex Geocoder / Search API (commercial) |
| Map picker ("точка на карте") | MapLibre Native Android + self-hosted vector tiles (Planetiler from OSM) | No DAU fees; offline packs possible later | Yandex MapKit commercial licence |
| Turn-by-turn navigation | Deep links to Yandex Navigator, Yandex Maps, 2GIS with waypoints | No navigation to build; users already trust these apps | — |
| Hotels | Yandex Travel via Travelpayouts: 8% of hotel bookings in Russia, 30-day cookie, confirmed 2 days after checkout ([offer](https://www.travelpayouts.com/ru/offers/yandex-travel-partnerskaya-programma)) | Russian inventory, dog filter on their side | Ostrovok via Travelpayouts |
| Excursions | Tripster via Travelpayouts (commission rate to be re-checked at integration) | Guided tours in Golden Ring towns | Sputnik8 |
| Fuel prices | Monthly regional averages entered by curators from fuel-chain price pages | Rosstat's weekly regional fuel bulletin is being discontinued in its current form ([Novaya Gazeta Europe](https://novayagazeta.eu/articles/2026/06/30/vlasti-reshili-skryt-dannye-o-roste-tsen-na-toplivo-news)) | Rosstat EMISS data if published |
| Toll tariffs | Curated `toll_segment` table + OSM `toll=yes` tags to detect segments | Tariffs change by time of day and season | Avtodor data feed if available |
| Analytics / crashes | AppMetrica SDK (Yandex) | Works in Russia, free, crash reports included | — |

### Integration rules

- All partner links are built server-side (`GET /v1/links/hotel`) so markers and parameters can change without an app release.
- Affiliate links open in the external browser or the partner app, never in a WebView (cookie attribution).
- Deep link formats for Yandex Navigator / Yandex Maps / 2GIS are kept in remote config; the app checks which apps are installed and shows only those.
- Every external call has a timeout (routing 6 s, geocoding 1.5 s) and a cached fallback.

## 11. Architecture and tech stack

A native Kotlin app talks to one Python backend; the backend owns planning and calls self-hosted OpenStreetMap services, and everything runs on servers in Russia.

&#91;embedded content: system architecture · phone, backend, map services, partners\]

The app loads map-picker tiles straight from the tile server; all other traffic goes through the API, so providers can change without an app release.

### Stack

| Layer | Choice | Notes |
| --- | --- | --- |
| Android language / UI | Kotlin 2.x, Jetpack Compose (custom components, Canvas for the windshield scene) | No Material look; Material3 only for accessibility primitives |
| Architecture | Single activity, Compose Navigation, MVVM + unidirectional state, Hilt DI | One ViewModel per screen; shared `TripRepository` |
| Network | Retrofit + OkHttp + kotlinx.serialization; OkHttp SSE for planning | Timeouts per section 10 |
| Local storage | Room (trips, cache), DataStore (defaults) | Migrations tested in CI |
| Map picker | MapLibre Native Android | Single pin, no routing on the map in MVP |
| Analytics | AppMetrica SDK | Crash reports included |
| Build / release | Gradle, signed AAB/APK, RuStore Console | minSdk 26, targetSdk latest |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 + GeoAlchemy2, Alembic | Planner as a pure-Python package with no web dependencies (testable) |
| Data | PostgreSQL 16 + PostGIS 3.4, Redis 7 | Daily backups, 14-day retention |
| Map services | GraphHopper (Docker, Russia OSM extract, weekly rebuild), Photon (Russia index), Planetiler tiles | Separate VM with 32 GB RAM |
| Admin | Directus on the same PostgreSQL (separate schema access) | Map field for geometry, roles for curators |
| Infra | Docker Compose on 2 VMs (Yandex Cloud or Selectel), Nginx, Let's Encrypt, GitHub Actions CI | IaC later |
| Monitoring | Prometheus + Grafana, Sentry-compatible error tracking self-hosted (GlitchTip), Telegram alerts |  |

### Repository layout

```
verst/
  android/        # Gradle project, :app, :core-ui, :data, :feature-*
  backend/
    api/          # FastAPI app
    planner/      # pure Python engine + golden-trip tests
    migrations/   # Alembic
  infra/          # docker-compose, nginx, map services build scripts
  admin/          # Directus config and schema snapshot
  docs/           # this spec, ADRs
```

## 12. Backend API

A versioned REST + JSON API under `https://api.verst.app/v1` (domain to be confirmed), authenticated by an anonymous device token, with Server-Sent Events for trip planning progress.

### Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/v1/devices` | Register an install → `{deviceId, token}` (no personal data) |
| GET | `/v1/config` | Remote config: deep-link templates, copy templates, feature flags, min app version |
| GET | `/v1/ready-routes?lat&lon&limit` | Ready routes near a start, sorted by distance |
| GET | `/v1/ready-routes/{id}` | Template detail |
| GET | `/v1/geocode/suggest?q&lat&lon&limit` | Typeahead: cities, streets, places |
| GET | `/v1/geocode/reverse?lat&lon` | Point → label |
| POST | `/v1/trips/plan` | Plan a trip (body = section 7.1 input); `Accept: text/event-stream` streams progress |
| GET | `/v1/trips/{id}` | Full trip result |
| POST | `/v1/trips/{id}/stops/{stopId}/replace` | Body `{alternativeId}` → updated days, stops, cost |
| PATCH | `/v1/trips/{id}` | Change crew, budget, reserve toggle, hotel choice → recomputed cost |
| POST | `/v1/trips/{id}/save` | Mark saved; returns `shareSlug` |
| GET | `/v1/links/hotel?tripId&stopId&placeId` | Affiliate URL with dates and guests |
| GET | `/v1/links/navigator?tripId&day&app` | Deep link for Yandex Navigator / Yandex Maps / 2GIS |
| POST | `/v1/feedback` | Report closed place, wrong tag, wrong price |
| GET | `/s/{shareSlug}` | Public web page with the trip text (for recipients without the app) |

### Plan response (abridged)

```json
{
  "id": "trp_7f3c",
  "title": "Золотое кольцо",
  "km": 745, "days": 3, "nights": 2,
  "daysList": [
    {"day": 1, "km": 265, "driveMin": 245,
     "stops": [
       {"id": "s1", "kind": "sight", "sign": "tourist", "placeId": "pl_lavra",
        "name": "Троице-Сергиева лавра", "arriveAt": "2026-11-07T09:15", "departAt": "2026-11-07T10:45",
        "kmFromPrev": 70, "kmAt": 70, "tags": ["free_entry"], "costRub": 0,
        "reason": "Полтора часа на лавру, собака ждёт с одним из взрослых",
        "verified": true, "alternatives": [{"id": "alt1", "name": "…", "deltaMin": 10, "deltaRub": 300}]}
     ]}
  ],
  "cost": {"lines": [{"key": "fuel", "rub": 3720, "formula": "745 км × 8 л/100 × 62 ₽", "asOf": "2026-10"}],
           "reserveOn": true, "totalRub": 34500, "perPersonRub": 11500, "budgetRub": 40000, "remainingRub": 5500},
  "reasons": {"overnights": [{"day": 1, "town": "Ярославль", "text": "…", "candidates": ["Ростов", "Ярославль"]}]}
}
```

### SSE events on `/v1/trips/plan`

`stage` `{key: split|lodging|hours|fuel|cost, text}` · `stop` `{day, stop}` (for the flying signs) · `done` `{tripId}` · `error` `{code, message}`.

### Errors

| HTTP | `code` | UI message (ru) |
| --- | --- | --- |
| 400 | `INVALID_INPUT` | "Проверьте параметры поездки" |
| 404 | `UNREACHABLE` | "Не нашли дорогу на машине до этой точки" |
| 422 | `TOO_SHORT` | "Слишком близко для поездки на машине" |
| 422 | `NO_LODGING` | "Не нашли ночёвку с вашими условиями — показали ближайшую подходящую" (warning, trip still returned) |
| 429 | `RATE_LIMITED` | "Слишком много запросов, подождите минуту" |
| 503 | `UPSTREAM` | "Сервис маршрутов временно недоступен" |

Rate limit: 30 plan requests per device per hour. All times are local to the stop (Europe/Moscow etc.) in ISO 8601 without offset plus a `tz` field per day.

## 13. Offline mode and persistence

A saved trip must work with zero signal on the road: everything needed to read it is stored on the device in Room (SQLite), and only booking, navigation hand-off and re-planning need the internet.

| Data | Stored locally | Refresh |
| --- | --- | --- |
| Saved trips (full JSON result incl. alternatives and cost unit prices) | Yes, until deleted | Re-fetched when opened online if older than 24 h ("Обновить цены") |
| Last trip in progress (not saved) | Yes, 1 slot | Overwritten by the next plan |
| Ready routes near the last start | Yes, last 20 | On launch when online |
| User defaults (crew, km/day, budget, vehicle) | DataStore | On change |
| Recent searches | Last 10 | On search |
| Remote config | Last version | On launch |
| Map tiles for the picker | Not in MVP | v1.1 offline packs |

### Behaviour without a network

- The app starts on the Windshield with cached ready routes and a "Нет сети" plate on the navigator.
- Saved trips open fully: stops, times, reasons, cost, formulas; replacing a stop works if its alternatives were cached.
- Booking and "Открыть в навигаторе" show "Нужен интернет" (navigator apps may still work offline on their own side).
- Analytics events are queued (max 500) and sent later.
- Share works as plain text.

### Storage limits

Up to 50 saved trips; a trip JSON is expected to be < 200 KB. The app warns at 45 trips.

## 14. Monetization in the MVP

The MVP earns only through affiliate bookings and measures demand for Trip Pro with a waitlist; no in-app payments ship in the first release.

| Stream | MVP implementation |
| --- | --- |
| Hotel affiliate | "Забронировать ночь" → Yandex Travel link via Travelpayouts with marker `verst_app`, sub-id = trip id + stop id for attribution |
| Excursions affiliate | Sights with a `tripster_id` show "Экскурсия от 1 900 ₽" → Tripster link via Travelpayouts |
| Trip Pro (waitlist) | A "Поездка Pro" plate on the Waybill: unlimited saved trips, PDF export, re-plan on the road, offline map packs; tap → short form "Хочу Pro" (no payment), counted as demand |
| Promo placements | Not in MVP; data model keeps `place.sponsored = false` for later |

Revenue reporting: weekly import of Travelpayouts statistics into the admin (manual CSV in MVP), joined to analytics by sub-id.

## 15. Analytics

AppMetrica records the funnel from install to booking click; every event carries `device_id`, `app_version` and `trip_id` when one exists, and never personal data or precise location.

| Event | Parameters | Answers |
| --- | --- | --- |
| `app_open` | cold/warm, offline | Retention |
| `ready_route_shown` | count, start\_city | Coverage of ready routes |
| `ready_route_selected` | route\_id, rank | Which templates attract |
| `search_started` / `search_selected` | query\_len, result\_type, rank | Free-search usage, quality |
| `params_changed` | field, value bucket | Crew, pace, budget mix |
| `plan_requested` | km bucket, days, dog, children, mood | Demand shape |
| `plan_succeeded` / `plan_failed` | latency\_ms, error code | Speed and reliability |
| `stop_replaced` | kind, rank of alternative | Engine quality |
| `waybill_opened` | total bucket, over\_budget | Cost interest |
| `reserve_toggled` | on/off | Trust in reserve |
| `hotel_link_clicked` | stop\_id, price bucket | Revenue funnel |
| `excursion_link_clicked` | place\_id | Revenue funnel |
| `navigator_opened` | app, day | Real usage on the road |
| `trip_saved` / `trip_shared` | channel | Value and virality |
| `pro_waitlist_joined` | source | Pro demand |
| `feedback_sent` | kind | Data quality |

Key funnel: install → plan\_succeeded → waybill\_opened → hotel\_link\_clicked. Dashboards: daily funnel, plan latency p50/p95, error codes, top routes.

## 16. Non-functional requirements

The app must feel instant, never lose a saved trip, and collect no personal data beyond an anonymous install ID.

| Area | Requirement |
| --- | --- |
| Startup | Cold start to interactive Windshield ≤ 2.0 s on a mid-range phone (Samsung Galaxy A34 class) |
| Rendering | 60 fps for scene animations; no frame > 32 ms during scrolling of the itinerary |
| Plan latency | p50 ≤ 5 s, p95 ≤ 10 s for trips ≤ 1,500 km; first SSE stage ≤ 1 s |
| Typeahead | Suggestions ≤ 500 ms p95 on 4G |
| APK size | ≤ 30 MB (fonts bundled, no map tiles) |
| Availability | API 99.5% monthly; planned maintenance at night Moscow time |
| Reliability | Crash-free sessions ≥ 99.5%; saved trips survive app updates (Room migrations tested) |
| Security | HTTPS only (TLS 1.2+), certificate pinning off in MVP; device token rotated on reinstall; rate limiting per device and IP; no secrets in the APK beyond public keys |
| Privacy (152-FZ) | No personal data collected in MVP (no name, phone, e-mail, account). Location is used on the device and sent only as trip start coordinates, rounded to 3 decimals in logs. Servers and backups hosted in Russia. Privacy policy and terms in Russian, linked from settings and the RuStore page |
| Permissions | Location (optional, coarse first), internet. No contacts, camera, storage |
| Accessibility | Content descriptions on all sign buttons, TalkBack reads a stop as "Через 70 км, 09:15, Троице-Сергиева лавра"; font scale up to 130% without clipping; reduced-motion support |
| Localization | Russian only; all strings in resources; plural rules via ICU (день/дня/дней) |
| Compatibility | Android 8.0–16, screens 360–480 dp wide |
| Observability | Structured JSON logs, request IDs, metrics (latency, error rate, upstream timeouts), alerts to Telegram |

## 17. QA and acceptance

The MVP is accepted when every user story in section 3 passes on real devices and three real test drives confirm the route and the cost.

### Test layers

| Layer | What | Tooling |
| --- | --- | --- |
| Unit (backend) | Day split, overnight score, fuel insertion, schedule, cost formulas, rounding | pytest, ≥ 85% coverage of the engine package |
| Golden trips | 20 fixed inputs (Moscow → Yaroslavl, Golden Ring, Moscow → Volgograd 500 km/day with dog, Kazan → Perm, St Petersburg → Vyborg…) with expected days, overnight towns and cost ±5% | Snapshot tests in CI |
| API contract | Every endpoint, errors, SSE stream | OpenAPI schema tests |
| Unit (Android) | ViewModels, cost recompute, offline repository | JUnit, Turbine |
| UI | Each screen's states (loading, offline, error, empty), navigation | Compose UI tests, screenshot tests (Paparazzi) against the canvas |
| Devices | 4 phones: budget (Android 8–9), mid-range (A34), Xiaomi (MIUI/HyperOS), Pixel | Manual checklist |
| Field test | 3 real trips: one day trip ≤ 300 km, one 2-day trip with an overnight, one Golden Ring | Compare plan vs reality: times ±20%, cost ±15%, all stops open |

### Release acceptance checklist

- [ ] US-01 … US-14 pass on all 4 devices
- [ ] p95 plan latency ≤ 10 s on golden trips against production backend
- [ ] All 10 Moscow ready routes plan without warnings; every stop verified in the Place DB
- [ ] Dog = yes never yields an overnight without `dogs_allowed`
- [ ] Cost error ≤ 15% on the 3 field trips
- [ ] Saved trip opens in airplane mode with all data
- [ ] Affiliate clicks appear in Travelpayouts statistics with correct sub-ids
- [ ] Navigator hand-off opens the right day in Yandex Navigator and 2GIS
- [ ] Crash-free ≥ 99.5% over a 1-week closed beta (≥ 30 testers)
- [ ] Privacy policy published; RuStore listing approved

## 18. Delivery plan

The MVP takes about 12 weeks: backend, place curation and Android run in parallel from week 3, and the last 3 weeks are beta and field trips.

&#91;embedded content: MVP delivery plan · 8 workstreams, 12 weeks\]

The week estimates assume Claude writes the code and the CEO reviews builds and curates places part-time; place curation is the item most likely to stretch.

| Milestone | Deliverable | Done when |
| --- | --- | --- |
| M1 Foundations (W1–W2) | Repos, CI, 2 VMs, GraphHopper + Photon running on the Russia extract | A route Moscow → Yaroslavl and a typeahead for "Яро" answer from our servers |
| M2 Engine alpha (W3–W7) | Planner with day split, overnight score, stops, schedule; golden trips | 20 golden trips pass in CI |
| M3 Data ready (W2–W8) | Directus admin, OSM import, 10 Moscow ready routes verified | Every ready-route stop is `live` with `verified_at` |
| M4 API complete (W4–W8) | All endpoints of section 12, SSE, cost model, partner links | OpenAPI contract tests green |
| M5 App feature-complete (W3–W9) | 7 screens per canvas, states, accessibility | Screenshot tests match the canvas; US-01 to US-14 pass on emulator |
| M6 Hardening (W8–W10) | Offline, analytics, crash reporting, performance | NFR table in section 16 met on 4 devices |
| M7 Beta (W10–W12) | Closed beta ≥ 30 testers, 3 field trips | Release checklist in section 17 complete |
| M8 Release (end of W12) | RuStore publication | App live, privacy policy published |

### Definition of done (every task)

- Code reviewed, tests added, CI green, no new lint warnings.
- Screen matches the canvas within 4 dp and uses only design tokens.
- Russian copy checked; analytics events from section 15 fire.
- Works offline where section 13 says it should.

## 19. Risks and open questions

The biggest risk is data, not code: the route is only as good as the verified places on it, so curation capacity decides how fast regions open.

### Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Place data goes stale (closed cafes, wrong hours) | Trust lost on the first trip | Verified-at dates, 180-day re-check, "Сообщить об ошибке" on every stop, hide after 2 reports |
| OSM routing/geocoding quality worse than Yandex in some areas | Wrong addresses, odd routes | Golden-trip tests; switch provider behind an interface; Yandex APIs as paid fallback |
| Fuel price source disappears (Rosstat bulletin change) | Fuel estimate drifts | Monthly curator update from chain price pages; label "цены на <месяц>" |
| Affiliate attribution lost on mobile | No revenue data | External browser only, sub-ids, monthly reconciliation |
| Server cost of self-hosted GraphHopper + Photon for all of Russia | Higher hosting bill | Start with one 16–32 GB RAM VM; Russia extract only; cache routes |
| Overnight towns with no dog-friendly lodging | Broken promise | Engine falls back with an explicit warning (`NO_LODGING`) |
| RuStore review delays | Late launch | Submit a closed test build 2 weeks before launch |

### Decisions needed from the CEO

- [ ] Confirm the brand name "Верста" and register the domain and RuStore developer account
- [ ] Confirm the 10 Moscow ready routes in 7.6
- [ ] Who verifies places at launch (CEO, a hired curator, or both) and the weekly hours available
- [ ] Hosting provider in Russia (Yandex Cloud or Selectel) and monthly budget
- [ ] Travelpayouts account and partner marker; legal entity for payouts (self-employed / IP)
- [ ] Trip Pro: waitlist only in MVP, or paid in v1.1 at what price
- [ ] Whether "Пример расчёта" stays in the UI until the 3 field trips confirm accuracy
