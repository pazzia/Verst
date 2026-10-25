# ADR-0016: Real-time parking, and the offline and robustness rule for all online data

Status: **Proposed (Architect)** · design only · Date: 2026-10-25 · Branch `arch/sprint-4` · Refs: ADR-0015 §4
(static parking model), ADR-0012 (photos), ADR-0011 (budget fit) · Sources §6, cited as [P1]…

## 1. What the CEO asked

Show parking **cost and availability in real time** at each car stop, and make every online feature safe without a
connection.

## 2. Sources checked (2026-10-25)

| Source | Coverage | Fields | Real-time free spaces | Terms, key, cost | Usable by us? |
| --- | --- | --- | --- | --- | --- |
| **2GIS Places API** (`/3.0/items`, `type=parking`) | Russia; 2GIS city coverage | `capacity`, `is_paid`, `access`, `purpose`, `paving_type`, `level_count`, `for_trucks`, `is_incentive`; the sample response has `parking.congestion.spaces.{common,handicapped}.{free,total}` + `updated_datetime` [P1] | **Yes, where 2GIS has it** (the field exists; coverage is not documented — to be measured with the demo key) | key required; demo key = 1 000 requests in total; paid packages per month: 10 000 req = 6 700 ₽, 100 000 = 30 000 ₽, 1 M = 100 000 ₽; ≤ 600 req/min [P2]; storage/caching rules are in the licence at law.2gis.com (not verified here: must be read before signing) | **Yes — the only real-time source found.** No tariff field: prices still come from ADR-0015 |
| **Moscow: data.mos.ru / apidata.mos.ru** | Москва | dataset 623 «Платные парковки на улично-дорожной сети» (zones, tariffs, capacity, geometry) [P3] | **No** occupancy dataset found | free API key from apidata.mos.ru [P4]; open-data terms | **Yes, static**: zones and tariffs for ADR-0015 (CI, not real-time) |
| **Московский паркинг / «Парковки России»** (ГКУ АМПП) | Москва, СПб (others «со временем») [P5] | tariffs, capacity, payment; a «свободен/занят» estimate was planned since 2018 [P6]; real-time free spaces shown only for EV bays [P7] | Only inside their app | no public API found | **No** (a data partnership with АМПП is the only route) |
| **parking.spb.ru** (СПб) | СПб | zones, tariffs 100–360 ₽/h, 08:00–20:00 [P8] | No public data found | no public API found | **Static only** (tariff table, reviewed by hand) |
| **Казань, Екатеринбург, Нижний Новгород** municipal apps («Горпарковки», «Казанский паркинг 2.0») | each city | tariffs, zones, payment | none public [P9] | no public API found | **Static only** |
| **Яндекс** (Карты parking layer, MapKit, Geosearch) | many cities in the app | the app shows zones, prices, capacity, hours; payment in Москва only [P10] | not offered to third parties | Geosearch terms: results only «строго на фоне карты Яндекс Карты», caching ≤ 30 days [P11]; no parking API | **No** (confirmed: no third-party parking API; Geosearch would bind us to a Yandex basemap) |
| **Commercial aggregators** (Паркли/Parkly, Parkapp) | Москва, СПб | consumer apps (booking of commercial lots) [P12] | inside their apps | no public API found | **Only by partnership** |
| **OpenStreetMap** | Russia | `fee`, `capacity`, `parking`, `access`, `opening_hours`, `maxstay` [P13] | **No** (OSM has no live tags) | ODbL, already used | **Yes, static** (ADR-0015) |

**Conclusion:**
- **Prices** are static everywhere: municipal tariffs plus OSM `fee`. This is ADR-0015 §4, refreshed in CI.
- **Real-time availability** is available to a third party only through **2GIS**, and only for lots where 2GIS has
  occupancy data.
- Everything else is partnership-only.

## 3. Architecture

### Does real-time parking need a server? Yes — a very small one

- The 2GIS key is billed per request, so a key in the APK can be extracted and spent by anyone.
- Many users ask about the same lots, so a shared cache cuts the bill.
- A proxy also lets us change the provider without an app release.

**The smallest option:** one serverless function behind an API gateway (Yandex Cloud Functions + API Gateway,
Russian region).

- **Cost:**
  - Free tier per month: 1 M function invocations, 10 GB·h, 100 000 gateway requests [P14].
  - Beyond it: 18.97 ₽ per 1 M invocations, 6.48 ₽ per GB·h [P15], and 142.3 ₽ per 1 M gateway requests [P14].
  - So infrastructure is **≈ 0 ₽/month** at pilot scale and **< 300 ₽/month** at 1 M requests.
- **The real cost is 2GIS:**
  - pilot: **6 700 ₽/month** (10 000 req);
  - 1 000 daily active trips × 5 city stops ≈ 150 000 req/month, minus ~50 % from the shared cache ≈ 75 000 req →
    the 100 000 package, **30 000 ₽/month** [P2].

```
app ──HTTPS──▶ API Gateway ──▶ function  GET /v1/parking?lat=…&lon=…&r=400
                                    │  cache key: geohash-7 cell (≈150 m) + 5-min bucket
                                    ├─ hit  → return cached
                                    └─ miss → 2GIS items?type=parking&point=…&radius=400&fields=items.capacity,items.is_paid,…
                                              → normalise → cache (Object Storage / YDB, TTL 5 min) → return
```

- **Response (our format, provider-neutral):**
  `{"lots": [{"id", "name", "lat", "lon", "paid": true|false|null, "capacity", "free": 12|null, "updatedAt",
  "source": "2gis"}], "fetchedAt", "ttlSec": 300}`.
- **Proxy rules:**
  - It stores nothing beyond the TTL, which matches the conservative reading of the provider terms.
  - It adds the 2GIS attribution string to the response.
  - It rate-limits per device id (ADR-0007 anonymous auth) to 60 requests/hour.
- **App use:**
  - When the car is ≤ 30 min from a city stop, the Road-ahead card «Парковка» asks the proxy.
  - The Place card asks when it is opened.
  - The trip plan itself never waits for it. The engine stays offline and pure: real-time data is display-only and
    never changes the plan or the budget. The Waybill «Парковки» line stays the static estimate (ADR-0015).

### Display

- «Свободно ≈ 12 из 80 · 3 мин назад» when `free` is known;
- «Платная · ≈ 200 ₽/ч (тариф зоны)» from the static model;
- «Данных о местах нет» otherwise.

The age label is always shown when the data is older than 5 min. After 60 min, only the static info is shown.

### Fallback

The static tariff model from ADR-0015 is always present offline. Real-time is a layer on top: if it fails, the
card shows the static line, and nothing else changes.

## 4. Offline and robustness rule for ALL online data (cross-cutting, OR-1…OR-8)

This applies to photos, address search (Nominatim), parking, Wikipedia extracts, hand-off resolution and any
future source.

| Rule | Requirement |
| --- | --- |
| **OR-1 Timeouts** | connect 3 s, read 5 s, total 6 s per request (photos: 10 s total); one retry with 0.5–1.5 s jitter for idempotent GETs, not for 4xx; every call is cancelled when its screen closes |
| **OR-2 No error screens** | online data is optional: a failure never blocks a screen, a plan, a walk or a save; no dialogs; at most a muted inline line |
| **OR-3 Cache with age** | every response is cached with `fetchedAt`. Photos: disk LRU 100 MB, 30 days. Wikipedia extracts and addresses: 30 days. Parking: TTL 5 min, shown up to 60 min with its age. A cached value older than its TTL is shown with «N мин/ч/дн назад» |
| **OR-4 Minimal fallback** | without data, show what the offline catalogue has; if nothing, the copy «Уточним, когда будет интернет» (`online_pending`). Never «Ошибка» |
| **OR-5 Defensive parsing** | schema-checked decoding; unknown, missing or garbage fields become «нет данных»; a response over 1 MB or of the wrong content type is dropped; no exception escapes the data layer |
| **OR-6 Circuit breaker** | 3 failures within 60 s for a host → no calls to it for 5 min (the cached or offline value is shown); airplane mode or no network → no calls at all (`ConnectivityManager`) |
| **OR-7 No online data in the engine** | the Python engine never does I/O; online values are display-only or are passed in explicitly as input (e.g. the GPS origin) |
| **OR-8 Logging** | failures go to the debug panel counters (host, code, latency), never to the user |

### Tests (DEV acceptance, instrumentation with a mock server, e.g. OkHttp MockWebServer)

| Scenario | Expected |
| --- | --- |
| Airplane mode from launch | plan, walk, Road ahead, cards and save all work. Cards show offline data and «Уточним, когда будет интернет». No network call is made (the mock server sees 0 requests) |
| Slow network (2 s latency, 20 KB/s) | first screen within the offline time; online parts appear later or stay pending; no ANR; calls end at OR-1 limits |
| Server 500 / 503 / 429 | one retry (not for 429 within the breaker window), then the cached or offline value; no dialog |
| 200 with HTML, truncated JSON, wrong types, a 5 MB body | treated as no data; no crash; the debug counter increments |
| Network lost mid-request | cancelled, the cached value is kept |
| Cached parking 20 min old, then offline | «Свободно ≈ 12 из 80 · 20 мин назад» |
| Cached parking 2 h old | static line only |
| Breaker | after 3 failures, no requests to that host for 5 min (mock server count) |

Python tests stay network-free; a test asserts that the engine imports no network module (`urllib`, `http`,
`socket`) at runtime.

## 5. Decision summary and next steps

1. **Static parking prices** (ADR-0015 §4) ship first; they need no server.
2. **Real-time availability:** a 2GIS demo key (free, 1 000 requests) to **measure coverage** in Москва, СПб and
   Казань (the share of lots with `congestion.free`), and to read the 2GIS licence on caching and mobile use. Go
   only if coverage is useful (≥ 30 % of lots near our city stops).
3. **If go:** the serverless proxy in §3, a 10 000-request package for the pilot (6 700 ₽/month) and the provider
   behind our own format.
4. **The OR-1…OR-8 rule** applies now, to the photos and the address search, independent of parking.

**Risks:**
- 2GIS coverage may be low outside parking garages.
- The licence may forbid caching; then the cost scales with users.
- A server adds operations work: monitoring and the key.

**Mitigation:** the provider-neutral format, the static fallback, and an alert on cost (2GIS request counter).

## 6. Sources

- [P1] 2GIS Places API — Searching for objects (`type=parking`, parking fields, congestion sample): https://docs.2gis.com/en/api/search/places/reference/3.0/items · overview: https://docs.2gis.com/en/api/search/places/overview
- [P2] 2GIS Platform Manager — Prices (demo 1 000 requests, packages, 600/min): https://docs.2gis.com/en/platform-manager/subscription/pricing
- [P3] data.mos.ru — Платные парковки на улично-дорожной сети (dataset 623): https://data.mos.ru/datasets/623 · Платные парковки закрытого типа: https://data.mos.ru/opendata/7704786030-platnye-parkovki-zakrytogo-tipa
- [P4] API Портала открытых данных Москвы (key): https://apidata.mos.ru/ · wrapper README: https://github.com/grybakov/python-apidata-mos-ru
- [P5] mos.ru, 18.01.2023 — «Парковки России»: https://www.mos.ru/news/item/118867073/
- [P6] РИАМО, 17.09.2018 — АМПП: сервис «свободен/занят»: https://riamo.ru/news/transport/v-moskve-sozdadut-servis-po-otslezhivaniyu-zanyatosti-ulichnyh-parkovok-xl/
- [P7] mos.ru, 16.12.2022 — свободные места для электромобилей: https://www.mos.ru/news/item/117549073/
- [P8] Фонтанка, 26.12.2025 — тарифы СПб: https://www.fontanka.ru/2025/12/26/76192793/
- [P9] Вечерняя Казань — «Горпарковки»: https://www.evening-kazan.ru/obshhestvo/news/kazancam-rasskazali-ob-izmeneniyah-v-prilozhenii-gorparkovki
- [P10] Яндекс Карты — Справка: парковки: https://yandex.ru/support/m-maps/parking.html
- [P11] Яндекс — Условия использования API Геопоиска: https://yandex.ru/dev/tariffs/doc/ru/geosearch/terms/
- [P12] Паркли — App Store: https://apps.apple.com/app/id1530278550
- [P13] OSM Wiki — Tag:amenity=parking: https://wiki.openstreetmap.org/Tag:amenity=parking
- [P14] Yandex Cloud — free tier for serverless: https://yandex.cloud/ru/docs/billing/concepts/serverless-free-tier
- [P15] Yandex Cloud Functions — pricing: https://yandex.cloud/ru/docs/functions/pricing
- [P16] 2GIS — Moscow parking payment in the app (Jan 2026): https://kod.ru/2gis-parkovki-moskva
