# ADR-0014: Hand-off to Яндекс Навигатор (car) and Яндекс Карты (walking)

Status: Accepted (Architect) · Date: 2026-10-24 · Refs: CEO Sprint 3 requirement 4; Manager decision D7; ADR-0010 hand-off table (superseded for the navigator part); `docs/backlog-sprint3.md` ARCH-306, DEV-307, DES-305

## Context

The car route must open in Яндекс Навигатор. A walking route must open in Яндекс Карты in pedestrian mode. Without the app, the web version opens in the browser.

The mock build currently forbids every real brand name (OI-40, `tests/brand_denylist.txt`). D7 allows these names **only** in hand-off strings, while the mock booking stays fictional.

## Decision

### Points: the engine decides, the app launches

`handoff(world, route_json, options_json)` → `{mode, parts: [{index, points, links}], truncated}`.

- `route_json` is the private trip (car) or a `WalkRoute` (walk).
- `options_json` = `{"mode": "car" | "walk", "day": 2 | null, "fromStopId": "d2s03" | null, "fromHere": true}`.

**Car** (`mode = car`), per day:

- Points: from `fromStopId` (exclusive) to the day's end (the overnight, or the finish on the last day).
- Kinds kept: `sight`, `food`, `via`, `overnight`, `finish`. Fuel and rest stops are dropped; the navigator handles those live.
- The destination = the last point. Vias = the rest, **≤ 8**: if more, the kept vias are chosen by priority (fixed template stops > sights by score > food), preserving order, and `truncated = true`.
- The origin: `fromHere = true` → current position (no `lat_from`); else the `fromStopId` coordinates.
- No `day` → day 1, or the day of `fromStopId`.

**Walk** (`mode = walk`): start → stops → finish, ≤ 10 points per part. A longer route is split into consecutive parts that share their boundary point («Часть 1 из 2»).

### Links (built in the engine, so they are tested in Python and identical for every caller)

| Link | Template |
| --- | --- |
| `navigator` (car) | `yandexnavi://build_route_on_map?lat_to={lat}&lon_to={lon}[&lat_from=…&lon_from=…][&lat_via_0=…&lon_via_0=……]` |
| `maps` (car fallback / walk) | `yandexmaps://maps.yandex.ru/?rtext={lat1},{lon1}~{lat2},{lon2}~…&rtt=auto` (car) / `&rtt=pd` (walk). `fromHere` → `rtext` starts with `~` (current position) |
| `web` | `https://yandex.ru/maps/?rtext=…&rtt=auto\|pd` |

Coordinates are written with 6 decimals and `.` as the decimal separator, URL-encoded. Rules:

- **The app** (DEV-307) declares `<queries>` for `ru.yandex.yandexnavi` and `ru.yandex.yandexmaps`.
- **Car:** navigator → maps → web, whichever resolves first (`PackageManager.resolveActivity`).
- **Walk:** maps → web.
- **No chooser and no 2GIS** (the CEO named Яндекс only). An `ActivityNotFoundException` falls through to the next link.

### Brand allow-list

The real names are allowed only in this set of string keys, recorded in `backend/planner/tests/brand_allowlist.txt`:

```
handoff_*        (Android string keys)
handoff.*        (engine resource keys, if any)
```

- The Kotlin `BrandDenyListTest` and the Python `test_brands` skip exactly these keys, and still scan every other string, fixture, catalogue file, golden, contract and the share text.
- URIs are values in `handoff` results only, never in trips or snapshots. `test_brands` asserts the engine's other outputs contain no `yandex` substring.
- Copy keys (DES-305): `handoff_navigator` «Открыть в Яндекс Навигаторе», `handoff_maps_walk` «Пешком в Яндекс Картах», `handoff_web` «Открыть Яндекс Карты в браузере», `handoff_truncated` «Навигатор принимает до 8 промежуточных точек — взяли главные», `handoff_part` «Часть %1$d из %2$d».
- The mock booking keeps «Придорожная» (OI-40 unchanged).

### Where it appears

- **Road ahead:**
  - the day header menu «В навигатор: день N»;
  - the stop menu «Открыть в навигаторе отсюда» (5.5 D-5 `stopmenu_navigator`, now built), which calls `fromStopId`.
  - The stop-menu copy keys of the deck that name the brands are renamed into the `handoff_*` space by the Designer.
- **Walk result:** «Пешком в Яндекс Картах».

## Options rejected

- **Building URIs in Kotlin.** That would be two implementations, and Python is where the point selection lives and is tested.
- **A generic `geo:` intent chooser.** It loses the via points and the pedestrian mode.

## Risks

| Risk | Mitigation |
| --- | --- |
| Яндекс Навигатор may require a signed intent or ignore vias for unsigned callers | DEV-307 acceptance: on a real device with the navigator installed, the route shows ≥ 2 vias. If vias are ignored, the car hand-off uses `maps` with `rtt=auto` (it carries all points) and the navigator gets the day's destination only. Record the observation in dev-notes |
| Per-version parameter limits (vias, rtext points) | The caps (8 / 10) are conservative and live in `resources/handoff.json`, so they can change without a code change |
