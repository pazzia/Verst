# ADR-0015: Sprint 4 design note (CEO feedback on build 83)

Status: **Proposed (Architect)** · design only, no engine code until the mockups are approved · Date: 2026-10-25 ·
Branch `arch/sprint-4` from main `cf8f335` · Refs: ADR-0009 (money rounding), ADR-0011 (budget fitting), ADR-0012
(catalogue), ADR-0013 (city walking), ADR-0014 (hand-off, superseded in part by §1)

Every API change below is **additive** (`mobile.API_VERSION = 3`; v2 callers keep working: new keys are optional,
no key changes meaning). `ENGINE_VERSION` stays `0.1.0` unless a decision says otherwise, so saved trips stay
editable. G01–G13 remain byte-identical: the new behaviour is tested on `russia_v1` in new golden cases G14–G17.

Facts were checked on 2026-10-25; sources are listed at the end (§9) and cited as [S1]…

---

## 1. Navigator hand-off

### Findings

- **The real cause of «points don't reach the navigator» is a launch limit, not the URL.** Яндекс Навигатор counts
  URL launches per device over 24 hours. After **5** unsigned launches, the next links open «не приложение Яндекс
  Навигатор, а страницу Навигатора в мобильном браузере». Launches from the app icon, from Navigator below 2.40,
  bare `yandexnavi://` and **signed** URLs are not counted [S2]. A tester who taps «В навигатор» more than five
  times a day (as the CEO did with build 83) gets the browser page with no route from then on.
- **Vias are supported.** `build_route_on_map` takes `lat_from/lon_from` (optional, else the current position),
  `lat_to/lon_to` and `lat_via_N/lon_via_N` from 0. The docs say only «промежуточных точек … может быть несколько»
  and give no maximum [S1].
- **Signing.** Both apps document the same scheme [S3][S4]:
  - append `client=<id>`;
  - compute SHA-256 over the whole URL string (with `client`, without `signature`);
  - sign it with the RSA private key (PKCS#1 v1.5, i.e. `SHA256withRSA`);
  - Base64-encode the signature, URL-encode it, and append `&signature=…`.
  The key and the client id come from a form (`forms.yandex.ru/surveys/4902/` for Карты; the Навигатор page links
  its own form). One id covers all of a developer's apps. The pages mention no fee; the 2017 commercial
  limits [S9] concerned fleet use of the Navigator, not launching it.
- **Яндекс Карты** builds car, transit and pedestrian routes from `rtext=lat,lon~lat,lon~…&rtt=auto|mt|pd`, always
  with traffic [S5][S6].
  - **Points:** the docs give no maximum; the route-optimisation feature works for 4–10 points [S7].
  - **Turn-by-turn:** since December 2020 the Карты app has car guidance with voice («Навигатор» features inside
    Карты, while the Навигатор stays a separate app) [S8].
  - **Limits:** Карты has the same signing scheme, «чтобы пользователи … не сталкивались с ограничениями» [S4], so
    we assume the same counting.

### Decision

1. **Apply for a client id and key now** (Manager: one form, ~1–2 weeks expected; no cost stated). The app signs
   every hand-off link on the device with the key shipped in the APK, using `java.security.Signature
   ("SHA256withRSA")` as in Yandex's Android sample [S3]. The key is extractable from the APK. The only abuse
   possible is someone else's launches being counted against our id, which we accept for the MVP. A
   signing endpoint on our backend can replace it later; the URL format does not change.
2. **Until the key arrives (unsigned), the car day goes to Яндекс Карты**:
   - the main button is «Маршрут дня в Яндекс Картах»: all kept points (≤ 10 incl. start and finish), `rtt=auto`;
     the user taps «В путь» there for guidance;
   - a secondary action «В Навигатор — до следующей точки» sends only `lat_to/lon_to` of the next stop;
   - the copy warns once: «Без ключа Яндекс открывает приложение по ссылке 5 раз в сутки».
3. **With the key**: «В Навигатор: день N» sends the start, the destination and ≤ 8 vias (cap unchanged, in
   `resources/handoff.json`), signed. Карты stays the fallback when the Навигатор is not installed.

### Exact URL formats

| Link | Template |
| --- | --- |
| Навигатор, whole day | `yandexnavi://build_route_on_map?lat_from={lat}&lon_from={lon}&lat_to={lat}&lon_to={lon}&lat_via_0={lat}&lon_via_0={lon}…&client={id}&signature={sig}` (no `lat_from` = from here) |
| Навигатор, next point | `yandexnavi://build_route_on_map?lat_to={lat}&lon_to={lon}[&client=…&signature=…]` |
| Карты, car | `yandexmaps://maps.yandex.ru/?rtext={lat},{lon}~{lat},{lon}~…&rtt=auto[&client=…&signature=…]`; from here = `rtext=~{lat},{lon}~…` (empty first point; device-verified in DEV-307, not documented) |
| Web | `https://yandex.ru/maps/?rtext=…&rtt=auto` |

Coordinates use 6 decimals and `.` as the separator. `signature` is the last parameter and is computed over
everything before it.

### API (v3, additive)

- `handoff(..., options_json)` gains `"signing": {"client": "…"} | null`.
- The engine builds the **unsigned** URL with `client` and returns `parts[].links.navigatorUnsigned` (the string to
  sign). Kotlin signs it and appends `&signature=`. The private key never enters Python, so the engine stays pure
  and testable.
- `links.navigatorNext` is new; `links.maps` is unchanged.

**Size:** none. **Risks:**
- The form may be slow or refused. Mitigation: the unsigned Карты scheme above is fully usable.
- Карты may also cap points. Mitigation: ≤ 10, split into parts like walks.

**Acceptance:** on a device with both apps:
- 7 consecutive «В Навигатор» taps in a day (signed) all open the app with ≥ 2 vias;
- unsigned, the Карты day route shows every point and «В путь» starts guidance.

---

## 2. POI quality, exclusions, diversity, and the «Красная площадь» detour

### Findings (reproduced on `russia_v1`, catalogue `wd-20261025-r7.2`)

Фрязино → Екатеринбург (2 adults, 1 child) picks:
- «Школа» (Q115685137, km 162);
- «Зелёный Город» and «Можга» (settlements, filed as POIs);
- «Центральный стадион»;
- two plain merchant houses at Горбатов.

All of them passed only because the class tree includes «architectural landmark»/«tourist attraction» and the score
uses sitelinks alone.

### Quality score `q ∈ [0, 1]` (computed in CI, shipped as one byte)

```
q = 0.30·S + 0.15·H + 0.15·V + 0.10·T + 0.10·P + 0.05·D + 0.15·C
S = min(1, log10(1 + sitelinks) / log10(61))       Wikidata sitelinks (60+ = 1)
H = 1 federal / 0.6 regional / 0.3 local P1435      heritage designation
V = 1 if a ru Wikivoyage «see/do» listing names it (by wikidata= or name ≤ 300 m)
T = 1 if OSM tourism=attraction|museum|viewpoint|zoo|theme_park|gallery, or leisure=park|water_park|nature_reserve
P = 1 with a free Commons photo; D = 1 with a ru description (Wikidata/Wikipedia)
C = class bonus: 1 kremlin/museum/zoo/theatre/park/nature/viewpoint/embankment, 0.6 monastery/cathedral,
    0.3 other religious, 0.2 monument
```

**Thresholds:**
- a road-trip stop needs `q ≥ 0.40`, plus `q ≥ 0.55` for a detour over 10 km;
- a walk stop needs `q ≥ 0.25`;
- the existing popularity term in the sight score is replaced by `q`.

### Hard excludes (builder; never shipped)

- **Classes, with subclasses:** school (Q3914), university building, kindergarten, hospital, stadium (Q483110),
  sports venue, office or government building (Q16831714), town hall unless federal heritage, prison, factory,
  railway station unless heritage with ≥ 10 sitelinks, cemetery unless ≥ 10 sitelinks, residential house unless a
  Wikivoyage listing or ≥ 5 sitelinks.
- **Names:** a POI whose name equals a catalogue town name («Можга», «Зелёный Город»); «Школа…», «Здание…»,
  «Дом … (жилой)», «Администрация…».
- **Ordinary churches:** a church or chapel with no P1435 and < 3 sitelinks and no Wikivoyage listing.

### Whitelist of interesting categories (the POI kinds after Sprint 4)

`museum`, `kremlin`, `monastery`, `temple` (religious with status), `park`, `nature` (reserves, waterfalls, lakes,
rocks; OSM `natural=*` with a name and ≥ 1 sitelink or a Wikivoyage listing), `viewpoint`, `square`, `embankment`,
`theatre`, `zoo`, `interactive` (science centres, children's museums, planetariums, OSM `museum=children`,
`tourism=theme_park`), `playground` (OSM `leisure=playground`, walks and the fun mood only), `monument`.

### Diversity rules (pipeline/sights, then walks)

- Per day: religious stops ≤ ⌈n/3⌉ of the day's sights; never two of the same kind in a row; ≤ 2 monuments.
- Per trip: religious share ≤ 30 % of non-template sights. Template stops (Лавра, Ипатьевский) do not count, so
  the Golden Ring stays a Golden Ring.
- Implementation: a greedy penalty `-0.25·q` for a repeated kind and `-0.5·q` past the religious cap, applied
  before the existing day-budget fill. The caps live in `planner_config.json` (`diversity`).

### The «Красная площадь — через 50 км · не проверено» detour (Фрязино ring)

- **Not a detour: the route really runs through central Moscow.** Фрязино snaps to the graph node «Пушкино» (13.5
  km, the access-leg mode of HybridRouting). The fixture graph (46 nodes) has no МКАД or ЦКАД edges, so the leg
  Владимир (М-7) → Пушкино (М-8) goes through the `MSK` node. The corridor then offers Красная площадь and the
  Мавзолей at km 727 with a 0 km detour.
- «через 50 км» is the Road-ahead distance to the stop, and «не проверено» marks open-data hours.
- **Fix 1, routing (russia_v1 only, fixtures untouched):** a bypass layer of ~12 nodes and 16 edges for МКАД
  and ЦКАД around Москва, and КАД around Санкт-Петербург. It is composed into `russia_v1` like the catalogue, so
  radial-to-radial legs never pass the centre.
- **Fix 2, the transit rule:** no sight within 12 km of the centre of a city of ≥ 1 M people, unless that city is
  the origin, the destination, a via or the overnight. City centres at 10 km/h are a walk, not a road stop.

**Catalogue size:**
- Excludes remove ~1 800 of 11 817 POIs.
- New OSM kinds (nature, theatres, zoos, interactive) add ~6 000.
- The playground layer adds ~12 000 points, without names, photos or texts, kept only within 3 km of town
  centres: about +90 KB.
- `q` adds ~10 KB.
- Total ≈ 0.68 → **0.95 MB**.

**API v3:**
- Stop and POI objects gain `kind` (the whitelist kind) and `quality` (0–100).
- `poi_details` gains `whyRu` (e.g. «объект наследия федерального значения · есть в Викигиде»).

**Acceptance:**
- G14 Фрязино → Екатеринбург (child) and G15 Фрязино Золотое кольцо, on `russia_v1`:
  - no excluded class or name;
  - no stop named like a town;
  - religious share ≤ 30 % of non-template sights;
  - no two same-kind stops in a row;
  - G15 has no sight within 12 km of the Moscow centre.
- A catalogue test: no shipped POI has an excluded class.

---

## 3. Extra sources for descriptions and photos

| Source | Use | How (CI, offline) | Licence and attribution |
| --- | --- | --- | --- |
| ru Wikipedia REST `page/summary/{title}` (via the Wikidata ru sitelink) | 1–2 sentence description, the page image when P18 is missing | CI fetch, ≤ 200 req/min with our UA; store the first sentence ≤ 200 chars | CC BY-SA 4.0: «Описание: Википедия» + link on the card |
| ru Wikivoyage `ruwikivoyage-latest-pages-articles` dump | «see/do» listings: presence (→ V), short text, hours, price, wikidata | parse the dump in CI (no API load) | CC BY-SA: «Викигид» on the card |
| OSM (the Geofabrik extract we already download) | `description`, `image`, `wikimedia_commons`, `opening_hours`, `fee`, `charge`, `website` for POIs (joined by `wikidata=*` tag, else name ≤ 150 m) | `osmium tags-filter` + join | ODbL: «© OpenStreetMap» (already shown) |
| Commons `list=geosearch` (`gsnamespace=6`, radius ≤ 300 m) | a photo for a POI with none: the free JPEG ≥ 800 px nearest to the point whose title or categories name the POI | CI, batched | per file, as today (author ≤ 40 chars) |

- **Offline vs online:**
  - Offline: the catalogue holds the first sentence, hours, fee and website, plus the file name of the photo
    (the image itself loads online as today).
  - Online: the card may load the full summary from Wikipedia REST on open. It is cached for 30 days, keeps
    attribution, and falls back silently.
- **Thumbnails:** request standard Wikimedia thumbnail widths only (switch from 400/800 to **500/960**). Another
  trip-planning app was rate-limited (HTTP 429) for non-thumbnail image fetches; standard sizes are the documented
  remedy [S10].
- **Size:**
  - texts ≤ 200 chars for ~9 000 POIs: ≈ +350 KB gzip;
  - OSM hours and fees for ~6 000 POIs and bars: ≈ +60 KB.
- **Risks and acceptance:** see the summary. Acceptance: ≥ 85 % of G14/G15 sights have a description and ≥ 90 %
  a photo (today: 82 % photos, descriptions from Wikidata only).

---

## 4. Parking costs (car trips only)

### Model

```
parking(stop) = 0                          if the place is free (OSM fee=no, a Sunday or holiday in a free zone)
              | null (unknown)             if no zone and no OSM parking with fee/charge within 300 m
              | round10( tariff(zone, arriveAt) · ceil(dwell_min / 60) )
tariff: Москва day 08:00–21:00 / night; 80 ₽/h outside the Boulevard Ring … up to 600 ₽/h inside the Third Ring;
        Sundays and holidays free except the 380/450/600 ₽ zones [S11]
        Санкт-Петербург 08:00–20:00, 100–360 ₽/h by zone; per-minute after the first hour [S12]
        other cities: a reviewed table (Казань, Нижний Новгород, Екатеринбург, Ярославль, Сочи …) or OSM charge=
```

- **Data:**
  - city zones as simplified polygons with a tariff code (Москва: the parking.mos.ru / data.mos.ru paid-parking
    zones; СПб: the parking.spb.ru zones), with a hand-reviewed `parking_tariffs.tsv` (city, zone, day rate,
    night rate, free days, source, as-of);
  - OSM `amenity=parking` with `fee`/`charge` (≈ 20 000 points with a fee tag in Russia, kept within 1 km of POIs
    and town centres).
- Overnights: hotel parking stays a hotel fact, not a cost.
- **The data.mos.ru dataset id and licence are checked on the first CI run, like the Wikidata class ids** (I could
  not verify the dataset from here).

### Cost model and parity

- **Waybill line** `{"key": "parking", "title": "Парковки", "rub": Σ known, "formula": "3 стоянки · ≈ 2 ч 30 мин ·
  Москва, Ярославль", "unknownCount": 2}`. With unknowns the line reads «≈ 640 ₽ + ещё 2 места без данных».
  - Units: `cost.units.parking[] = {stopId, rubPerHour, hours, rub, source: "zone|osm|free|unknown"}`.
  - Rounding: half-up to 10 ₽ per stop (ADR-0009).
- **ADR-0011:** parking is part of the trip total and of the tolerance check. A new last lever, `parking_free`,
  prefers free or unknown-cost stops when the trip is over budget. The ladder order stays fixed; the new lever
  comes after `sights_free`.
- **Kotlin `CostCalculator`:** sums `units.parking[].rub` (integers already rounded), so parity is exact.
  `cost_recompute_cases.json` gains 4 parking cases.
- When a stop is replaced, its parking unit is recomputed in Python. A dwell change is a replan, as today.

**API v3:** the new cost line, `units.parking`, and stop `parking: {rubPerHour, rub, source} | null`.
**Size:** zones ~40 KB, OSM points ~120 KB gzip.
**Risks:**
- Tariffs change. Mitigation: `asOf` on the line and a yearly review.
- Dynamic pricing in Москва (0–800 ₽/h). Mitigation: we use the published zone rate and say «≈».

**Acceptance:**
- G16 Москва (Третьяковская) → Ярославль: the parking line > 0 and equals Σ units;
- the Kotlin/Python parity cases pass;
- a Sunday plan in a free Moscow zone costs 0.

---

## 5. «Весело и познавательно» and the moods

### Decision

The moods become:
- `calm` «Спокойно» — few stops and long breaks;
- `fun` «Весело и познавательно» — new, replaces `more_stops` «Побольше остановок»; v2 `more_stops` maps to `fun`;
- `just_drive` «Только доехать».

In `fun`, each rest slot (every 90 min of driving) is filled with **an interesting stop within the detour
budget**: ≤ 15 min one way and ≤ 20 km, 30–45 min dwell. Fuel and food slots stay as they are. The kinds depend on
the group:

| Group | Preferred kinds (score ×1.5) | Avoided |
| --- | --- | --- |
| child | `playground`, `interactive`, `zoo`, `park`, `nature`, `museum` (children/science) | `temple` ×0.5, long museums |
| dog | `park`, `nature`, `embankment`, `viewpoint` | indoor kinds (museum, theatre, interactive) |
| adults | `museum`, `viewpoint`, `kremlin`, `nature`, `square` | — |

- **Fallback chain:** an interesting stop → a rest area with facilities → a café or fuel stop with a WC → **one**
  roadside break per day. Later breaks that day are «Перерыв 15 мин» without the «площадки рядом нет» sentence,
  which fixes the duplicate rows.
- The reason text says why: «Ребёнку размяться: детская площадка у кремля, 6 мин от трассы».

**API v3:** `mood: "fun"`; stops gain `funFor: ["child"|"dog"|"adults"]`; the reason keys are `rest.fun.*`.
**Size:** none beyond §2.
**Risks:** longer days. Mitigation: the fun detours share the existing `day_budget_min` and drop first when it is
tight.
**Acceptance:**
- G17 Москва → Казань, `fun`, 2 adults + child + dog: every rest slot is an interesting stop or a rest area,
  ≥ 1 playground or interactive stop, no indoor-only stop as a dog walk, ≤ 1 roadside break row per day;
- G01–G13 unchanged (they use `calm`/`more_stops`/`just_drive` explicitly or by default, and `more_stops` keeps its
  old behaviour for `ENGINE_VERSION 0.1.0` trips).

---

## 6. City walking

### Decisions

- **Group input:** `crew: {adults, children, dog}`, independent of the car trip; the walk screen has its own
  group chips.
- **18+ by an age question only:** «Вам есть 18?» for drink presets and the «бары» interest. **Children never
  block**: the walk is built and carries the warning «Взрослый маршрут: в бары с детьми обычно не пускают».
- **Warnings:**
  - `DOG_INDOOR` («С собакой в музеи и бары обычно нельзя») per indoor stop;
  - `CHILD_BARS`.
  - With a dog, the presets list puts a new preset **«Прогулка с собакой»** first (parks, embankments, nature,
    viewpoints, squares; no indoor stops).
- **«Без ограничения» duration:** `durationMin: null`.
  - The engine returns the best ≤ 12 stops within R = 6 km in walking order, **without** arrival times.
  - Each stop carries today's hours `{"todayRu": "10:00–18:00", "openNow": true|null, "source": "osm|wikidata|
    default"}`, and the summary gives the total walking km and min.
- **Opening hours from OSM:** `opening_hours` joined in CI (§3), parsed by the existing `hours` module. Bars use the
  OSM hours we already keep. `hoursVerified` becomes `hoursSource`.

### The CEO's bugs — root causes (found in the app; the API gets two fixes)

1. **«Мало мест — Гулять 4 ч» when 4 h is selected.**
   - The suggestion is guessed by the app (`CityScreen`: the next value of `WalkDurations` after the current one),
     not by the engine.
   - It ignores why the walk failed: the preset gate (too few bars at any duration) or `exclude`. And the error
     plate stays on screen while the chips change, so it can show a duration that is already selected.
   - **API fix:** `NOT_ENOUGH_POIS` gains `suggestions: [{"durationMin": 360, "count": 7}, {"preset": "overview",
     "count": 12}, {"clearExclude": true}]`. The engine only returns options it has checked: each one differs from
     the request and finds ≥ the gate's minimum.
2. **Walks not rebuilding when filters change.**
   - `VerstFlow` keeps `walkExclude` (every stop of every «Другой вариант» and «Убрать») and clears it only in
     `openCity()`. After a filter change the next walk still excludes all the old stops. In small towns this gives
     a thin walk or `NOT_ENOUGH_POIS`.
   - Also, the chips only update state; nothing rebuilds the walk on 5.11.
   - **Fix:** the app resets `exclude` on any preset, duration, pace, interest or group change, and rebuilds when
     on 5.11 (debounced 400 ms).
   - **API help:** the walk result echoes `input` (it already does) and gains `requestKey` (a hash of the input), so
     the app can tell a stale result.

**API v3:**
- `city_route` input: `crew.dog`, `durationMin: null`, preset `dog_walk`.
- `city_route` output: `warnings[]` (`CHILD_BARS`, `DOG_INDOOR`), `stops[].hours`, `requestKey`.
- `NOT_ENOUGH_POIS.suggestions`.
- `city_presets`: the dog preset and `crew` in the input.

**Size:** the OSM hours in §3.
**Acceptance:**
- every suggestion of a `NOT_ENOUGH_POIS` differs from the request, and requesting it succeeds (a property test
  over 200 towns);
- a dog walk has no indoor stop;
- an unlimited walk has no `arriveAt` and every stop has `hours`;
- a child plus the beer preset gives a walk with `CHILD_BARS`, not an error.

---

## 7. Distance so far on Road ahead

- **Confirmed:** every stop has `kmAt` (route position from the trip start, detours excluded) and `kmFromPrev`
  (driven km from the previous stop, detours included). In Фрязино → Екатеринбург, the «Школа» stop has `kmAt` 162
  and `kmFromPrev` 164.
- **Decision:** «пройдено N км» shows the driven distance. v3 adds `kmDriven` per stop (Σ `kmFromPrev` from the
  trip start, rounded) and `kmLeft` (the trip's driven total − `kmDriven`). The engine computes both, so the app
  does no arithmetic and the waybill km and the stop km agree.
- **Acceptance:** for every stop, `kmDriven` = Σ `kmFromPrev`, and the last `kmDriven` equals the trip `km` ± 1.

---

## 8. Summary of size, versioning and risks

- **Catalogue:** 0.68 → ~1.75 MB gzip. That is §2 +0.27, §3 +0.41, §4 +0.16, §6 included in §3, plus the bypass
  nodes. APK data ≈ 2.0 MB, under the 2.5 MB budget.
- **Engine load time** grows ≈ 1.5× (≈ 300 ms on desktop). The background catalogue load is kept.
- **API:** v3 additive (§1–§7).
- **ENGINE_VERSION** goes to `0.2.0` only for `fun` and the diversity rules. Trips saved by 0.1.0 still patch with
  the 0.1.0 rules, and `more_stops` keeps its old meaning there.
- **New golden cases:** G14–G17 on `russia_v1`. G01–G13 unchanged.

## 9. Sources

- [S1] Яндекс Навигатор — Формат URL: https://yandex.ru/dev/navigator/doc/ru/concepts/navigator-url-params
- [S2] Яндекс Навигатор — Ограничения (5 переходов за 24 ч): https://yandex.ru/dev/navigator/doc/ru/concepts/navigator-commercial-use
- [S3] Яндекс Навигатор — Подпись ключом доступа: https://yandex.ru/dev/navigator/doc/ru/concepts/navigator-commercial-use-signature
- [S4] Яндекс Карты — Подпись URL-схемы ключом доступа: https://yandex.ru/dev/yandex-apps-launch/maps/doc/concepts/yandexmaps-commercial-use-signature.html
- [S5] Запуск Android-приложения Яндекс Карты: https://yandex.com/dev/yandex-apps-launch-maps/doc/ru/concepts/yandexmaps-android-app
- [S6] Запуск веб-версии Яндекс Карт: https://yandex.ru/dev/yandex-apps-launch/maps/doc/concepts/yandexmaps-web.html
- [S7] «Яндекс Карты» научились оптимизировать маршруты с несколькими пунктами (4–10 точек): https://rozetked.me/news/25065-yandeks-karty-nauchilis-optimizirovat-marshruty-s-neskol-kimi-punktami
- [S8] Kod.ru, 08.12.2020 — навигатор в Яндекс Картах: https://kod.ru/yandex-navigator-in-maps/
- [S9] Интерфакс, 2017 — платный Навигатор для коммерческих пользователей: https://www.interfax.ru/business/559722
- [S10] Wikimedia Phabricator T422872 (429s for a trip app; use standard thumbnail sizes): https://phabricator.wikimedia.org/T422872
- [S11] Парковочная политика Москвы в 2026 году (tariffs, free days; to be checked against parking.mos.ru): https://shop.renlife.ru/articles/parkovochnaya-politika-moskvy-v-2026
- [S12] Фонтанка, 26.12.2025 — тарифы платной парковки СПб: https://www.fontanka.ru/2025/12/26/76192793/
- [S13] Wikidata: Wikivoyage/Resources (listing templates and the wikidata field): https://www.wikidata.org/wiki/Wikidata:Wikivoyage/Resources
- [S14] Яндекс Клуб API Карт — передать маршрут в Навигатор (vias via `lat_via`): https://yandex.ru/blog/mapsapi/50779
