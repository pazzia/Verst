# ADR-0012: Offline catalogue of Russian towns and POIs from open data, photos from Wikimedia Commons

Status: Accepted (Architect) · Date: 2026-10-24 · Refs: CEO Sprint 3 requirements 2, 3, 3.1; Manager decisions D2, D4/D5, D8; ADR-0010; `docs/backlog-sprint3.md` ARCH-302/303/307, DEV-300…305

## Context

The mock build knows 41 towns and 426 hand-made places, all in central Russia (`central_russia_v1`). The CEO wants:

- any city and any address («сейчас даже крупных городов нет»);
- GPS as the origin;
- a small real photo on every sight and hotel card.

The build must keep working offline, except for photos and addresses (D8). No images go into the APK (D2). This sandbox has no internet; GitHub Actions does.

## Decisions (D2, D4/D5, D8 made concrete)

### 1. Data pipeline: CI fetches, a bot branch commits, the Manager merges

The pipeline mirrors `fonts.yml`.

- The workflow `.github/workflows/data.yml` runs on `workflow_dispatch` or on a push to `data-request`.
- Runner: `ubuntu-24.04`, Python 3.12, `pip install pymorphy3==2.0.2 pymorphy3-dicts-ru==2.4.417150.4580142`. Fetchers use `urllib` with retries.
- Steps:

| Step | Script (`backend/planner/tools/data/`) | Source | Notes |
| --- | --- | --- | --- |
| towns | `fetch_wikidata.py towns` | Wikidata SPARQL (`query.wikidata.org`) | Items with P31 = Q7930989 (город России), P17 = Q159, with P625. Fields: P1082 population (latest by P585), P131 up to the federal subject and its P300 ISO 3166-2 code, P18 image, ru label |
| POIs | `fetch_wikidata.py pois` | Wikidata SPARQL, chunked per region | `wikibase:around` the town centre. Radius by population: 2 km (< 20 k), 4 km (< 100 k), 6 km (< 1 M), 10 km (≥ 1 M), 15 km (Москва, Санкт-Петербург). P31/P279* ∈ {tourist attraction Q570116, museum Q33506, monument Q4989906, memorial Q5003624, park Q22698, garden Q1107656, viewpoint Q6017969, church building Q16970, monastery Q44613, kremlin Q12035, castle Q23413, architectural landmark Q2319498, square Q174782, embankment Q1501717}. Fields: ru label (required), ru description, P625, sitelinks count, P18, P1435 (heritage) |
| bars | `fetch_overpass.py` | OSM Overpass (`overpass-api.de`) | Towns ≥ 100 000 people plus tourist towns (fixture towns and the top 60 by POI sitelinks). `amenity ∈ {bar, pub, biergarten}`, `craft = brewery` with a name, or `name ~ "рюмочн"` (case-insensitive). Dropped: features with `brand` or `brand:wikidata` (chains), no `name`, or a name that hits `tests/brand_denylist.txt`. Fields: osm type+id, name, lat, lon, kind (`ryumochnaya` if the name matches, `pub`/`craft` for pub/brewery/microbrewery, else `bar`), `opening_hours` (kept only if `verst_planner.hours.parse` accepts it). 1 request per city, 2 s apart |
| photo credits | `fetch_commons_meta.py` | Commons API `action=query&prop=imageinfo&iiprop=extmetadata`, 50 titles per request | For the selected images only. `Artist` (HTML stripped, ≤ 60 chars), `LicenseShortName`, `LicenseUrl`. Files without a free licence (missing or «Fair use») are dropped from the record |
| build | `build_catalogue.py` | the raw JSON above, archived as a workflow artifact (never committed) | A pure function of the raw files: dedupe, inflect, rank, cap, deny-list filter, write. Unit-tested in the sandbox on recorded samples (`tests/data/samples/`) |

- The Wikidata class ids above were written from memory, so the fetcher's first query checks them: it fetches each class's ru/en label and fails the run on a mismatch with the expected keyword table in `fetch_wikidata.py`. Corrected ids are then fixed in that table, not here.
- All requests send `User-Agent: VerstDataBot/0.3 (+https://github.com/pazzia/Verst; data pipeline)` (Wikimedia and OSM policies).
- The output is pushed to `bot/data-<run_number>`: `verst_planner/resources/catalogue/*.json.gz` + `catalogue.lock`. The lock records the source query timestamps, counts, sha256 and the pymorphy3 version. The Manager merges.

### 2. Name forms (nominative / genitive / prepositional)

- `tools/data/inflect.py` uses pymorphy3 in CI only; the engine never imports it.
- Rules:
  - each word of a town name is parsed, preferring `Geox` nouns and `ADJF`;
  - nouns and agreeing adjectives are inflected to `gent`/`loct`;
  - hyphenated names: the parts before a preposition part are inflected («Ростов-на-Дону» → «Ростова-на-Дону», «Ростове-на-Дону»);
  - indeclinable or foreign names keep the nominative («Сочи»);
  - capitalisation is preserved.
- `tools/data/name_overrides.tsv` (committed, hand-maintained) wins. The 48 fixture `nameGenRu`/`namePrepRu` forms win over both and double as the test oracle: `test_inflect` requires 48/48 matches before override.
- Prepositions «в/во» and «из/изо» stay with the app copy.

### 3. Catalogue format: compact, columnar, gzip, inside the Python package

The files live in `backend/planner/verst_planner/resources/catalogue/`. They are shipped by `stagePlannerSources` and loaded by Python through the zip-safe resource loader (DEV-110). There is no Kotlin change and no extra asset.

```jsonc
// towns.json.gz — one object of parallel columns (compresses ~3× better than rows)
{"v": 1, "builtAt": "2026-10-25", "n": 1117,
 "id":   ["Q649", …],            // Wikidata id = town id in the catalogue world (fixture towns keep "t_*" ids, mapped below)
 "name": ["Москва", …], "gen": ["Москвы", …], "prep": ["Москве", …],
 "lat":  [557558, …], "lon": [376173, …],            // degrees × 10⁴ as ints (≈ 11 m)
 "pop":  [13000000, …], "region": [0, …],            // index into "regions"
 "image": ["Moscow July 2011-16.jpg" | null, …], "imgCredit": [3 | null, …],   // index into credits.json.gz
 "regions": [{"code": "RU-MOW", "nameRu": "Москва", "tz": "Europe/Moscow"}, …]}
// pois.json.gz — same layout: id (Q…), name, desc, kind (index into "kinds"), lat, lon, town (index), sitelinks,
//                heritage (0/1), image, imgCredit
// bars.json.gz — id ("n123"/"w456"), name, kind, lat, lon, town, hours (OSM string | null)
// credits.json.gz — [{"author": "…", "licence": "CC BY-SA 4.0", "url": "…"}]  (deduplicated)
// fixture_links.json.gz — fixture town/place id → Wikidata id + image (matched in CI: same kind, ≤ 1.5 km, name similarity)
```

- **Caps per town** (by sitelinks, then id): 120 POIs (≥ 1 M people), 50 (≥ 100 k), 40 (tourist towns), 12 (others); bars ≤ 60 per city.
- **Size budget** (asserted by `test_catalogue_size`): ≤ 2.5 MB of gzip in total, hard limit 4 MB. Estimate: ≈ 1 100 towns at 40 KB; ≈ 20 000 POIs at ≈ 1.3 MB; ≈ 6 000 bars at ≈ 0.25 MB; credits ≈ 0.4 MB.
- **Load** at engine start after the worlds, recorded as `catalogueMs` in `EngineTimings`. Budget ≤ 800 ms on the emulator. The spatial index (0.1° grid buckets) is built lazily on the first corridor or city query.
- **Licences:**
  - Wikidata is CC0.
  - The OSM-derived `bars.json.gz` is a derived database under ODbL, with «© участники OpenStreetMap» shown in the app's «О данных» screen and on every bar card.
  - Commons files keep their own licences (credits).
  - `assets/licences/data.txt` documents all three.

### 4. The catalogue world `russia_v1` (engine)

There is a new adapter package, `verst_planner/adapters/catalogue/`. It is stdlib only and implements the existing ports, so no stage changes.

- **World composition:** `russia_v1` = the fixture world `central_russia_v1` (unchanged, authoritative for its towns, places, roads, tolls, prices and ready routes) **+** catalogue towns **+** catalogue POIs and bars **+** synthetic services.
  - Fixture towns and places are linked to Wikidata ids through `fixture_links`.
  - A catalogue item linked to a fixture item is dropped in favour of the fixture one, which gets the image.
- **Golden trips and contracts keep running on `central_russia_v1`** and do not change. `edge_cases_v1` is unchanged. The app's default world becomes `russia_v1`.
- **Catalogue POI → `Place` mapping:**

| Catalogue field | `Place` field |
| --- | --- |
| kind | `PlaceType.SIGHT` + tags (`museum`, `monastery`, `walk`, `view`, `park` → `walk` + `playground` only if «детск» is in the name, `monument`, `heritage`) |
| — | `source = WIKIDATA`, `verified = False` (the existing `UNVERIFIED_PLACES` warning applies) |
| sitelinks | `rating = 3.6 + 1.3 · min(1, log10(1 + sitelinks) / log10(1 + 150))` |
| kind | `dwell_min` by kind: museum 75 (90 if sitelinks ≥ 40), monastery/kremlin 60, church 20, monument/square 15, park/garden 40, viewpoint/embankment 20 |
| kind | opening hours: museums `Tu-Su 10:00-18:00`; churches `Mo-Su 08:00-20:00`; others always open; all flagged «часы уточняйте» |
| kind | tickets: museums 400 adult / 200 child (default price, marked `defaultPrice`); kremlin/monastery 300/150; everything else free |

- **Synthetic services** for catalogue towns, deterministic and seeded by the town id:
  - **Hotels:** 3 fictional hotels per town, named from a fixed fictional list («Тихий двор», «Старый город», «У реки», …), never a real brand.
    - Prices = `lodging_default_night(population)` × [0.8, 1.0, 1.3], rounded to 100.
    - Tags: `parking` on all, `family_room` on two (`family_price_rub` = 1.4 × price), `dogs_allowed` on one, `breakfast_included` on one.
    - Rating 4.1–4.6.
  - **Food:** 2 fictional cafes (a «Столовая …» at the economy check and a «Кафе …» at the default check).
  - **Fuel and rest:** generic «АЗС у трассы, {km} км» / «Площадка отдыха, {km} км», placed along synthetic routes every 40–60 km. They are created by the routing adapter as route-attached places.
  - **Area photo:** synthetic hotels carry no photo of their own. Their card uses the town image (or the top POI image of the town), labelled «Фото района: {город}», never as the hotel (D2).
- **Routing (`HybridRouting`):**
  - When **all** request points snap to the fixture road graph (≤ 2 km), it routes on the graph exactly as today.
  - Otherwise the **whole** route is synthetic, so a trip never mixes two models. A synthetic route is a great-circle polyline sampled every 1 km between consecutive points, with:
    - **km** = `haversine × f(h)`. `f` is piecewise linear in the straight-line distance `h`, calibrated on the fixture graph by `tools/calibrate_detour.py` (ARCH-303), which writes `resources/detour_model.json`. Fixture medians measured for this ADR over 818 town pairs: 1.09 (h < 100 km), 1.22 (100–300), 1.31 (300–600), 1.39 (≥ 600). Constant-factor error: MAPE 18 %, p90 36 %. The fixture graph is sparse (47 edges, everything meets at Москва), so the real road network will usually be **shorter**; the ADR accepts this mock error and documents it in the app's «О данных» screen («расстояния приблизительные»). Real routing comes with the servers (A§5.3.1).
    - **minutes** = km / `v(h)`, with the speed curve calibrated the same way on the fixture graph (≈ 60–75 km/h). `road_class = primary`, `road_ref = None`, no tolls.
    - The corridor uses the same 1 km profile, so stages 3–12 run unchanged.
  - **Reachability:** a point farther than 60 km from any catalogue town → `UNREACHABLE` (pointIndex). That is the offline "outside the road network" check.
- **Regions, time zones, prices:**
  - `RegionLocator` = the region of the nearest catalogue town (exact for fixture points; ±1 region near borders, documented).
  - The tz comes from the static table `tools/data/region_tz.tsv` (89 subjects), written by hand and reviewed.
  - Fuel prices: fixture region prices where present, else the RU price. Toll segments: fixture only.

### 5. Geocoding: offline towns and POIs, online addresses (Nominatim)

- **Offline (engine):** `geo_search(world, q, near, limit)` returns towns (all of Russia, ranked by prefix match → population → distance), POIs (prefix match, popularity) and the fixture places, with name forms. This replaces `suggest`, which stays as an alias.
- **Online (app, DEV-302):** Nominatim `https://nominatim.openstreetmap.org/search?format=jsonv2&countrycodes=ru&accept-language=ru&limit=5&addressdetails=1&q=…` and `/reverse`.
  - Sent with the app UA `Verst/0.3 (Android; +https://github.com/pazzia/Verst)`, **≤ 1 request/s** (a global token bucket in the app), with «© OpenStreetMap» shown under the results.
  - **Deviation from "debounced typing", forced by the Nominatim usage policy, which forbids client-side autocomplete:** address search is sent only on an explicit «Найти адрес» action (IME search or button), never per keystroke. Towns and POIs autocomplete offline from the catalogue as the user types. Offline → «Адреса ищутся только с интернетом — города и места доступны».
  - The engine receives an address as a plain point (`{lat, lon, label}`).
- **GPS (DEV-301):**
  - Android `LocationManager` (network + GPS providers, no Google Play services). Coarse permission first; fine is requested only when the user taps «Точнее».
  - `geo_nearest(world, lat, lon)` returns the nearest catalogue town, its distance and `insideRussia` (nearest town ≤ 60 km). The origin label is the reverse-geocoded address when online, else «{город} (по GPS)».

### 6. Photos (D2)

- **Source:** each POI and town carries a Commons file name (P18).
- **URL:** the app loads `https://commons.wikimedia.org/wiki/Special:FilePath/{urlencoded file}?width={w}` with w = 800 for cards and 400 for list thumbnails. The endpoint redirects to `upload.wikimedia.org` and rasterises SVG, TIFF and PDF to PNG/JPEG, so the app only ever decodes JPEG or PNG. `poi_details` returns both URLs and the file page `https://commons.wikimedia.org/wiki/File:{file}`.
- **Loader (DEV-300):** Coil `io.coil-kt:coil-compose:2.7.0` on OkHttp 4.12.0, with the app UA, redirects followed, a **64 MB disk cache** (`cacheDir/images`) and a 15 % memory cache.
- **Uniform card style:**
  - The image sits in a fixed 3:2 frame with `ContentScale.Crop`, the corner radius from the tokens, and a 1 dp hairline.
  - Placeholder illustrations per kind (museum, church, park, monument, view, bar, city; DES-301) are shown while loading, offline, on HTTP errors and for files without a free licence.
  - The frame never changes size, so the layout never jumps.
- **Attribution line:** «Фото: Wikimedia Commons · {author} · {licence}»; tapping it opens the file page in the browser. Without credits: «Фото: Wikimedia Commons». Hotels: «Фото района: {город} · Wikimedia Commons».

### 7. Network and permissions (D8)

- **Manifest additions:** `INTERNET`, `ACCESS_NETWORK_STATE`, `ACCESS_COARSE_LOCATION`, `ACCESS_FINE_LOCATION`.
- Cleartext stays off (the targetSdk default). There is no `usesCleartextTraffic` and no network security config exception.
- The real `ConnectivityManager` replaces `SimulatedConnectivity`; the debug override is kept.
- Everything except photos and addresses works offline.

## Options rejected

- **Bundled photos.** Forbidden by D2, and 20 000 thumbnails would be ~200 MB.
- **Wikipedia page images API (`pageimages`).** A second id space and per-language coverage; P18 is canonical and language-neutral.
- **The OSM extract as the town source.** OSM `place=city|town` does not encode the legal town status; Wikidata Q7930989 does (≈ 1 117 items), with population and P300 regions.
- **pymorphy3 on the device.** Adds 15+ MB of dictionaries. Precomputed forms cost ~30 KB.
- **On-device routing (OSRM/GraphHopper extract).** Hundreds of MB for Russia; that belongs to the server-backed build (ADR-0001).

## Consequences

- The app plans between any two Russian towns or addresses offline, with approximate distances. That is stated in the UI.
- Sights everywhere come from Wikidata, with real photos; hotels and cafes outside the fixture area are fictional, which keeps the mock booking honest.
- `russia_v1` plans are not goldens. They get invariants (no stop farther than the corridor radius, no hotel without a photo label, no deny-listed name) and a few snapshot smoke cases with the golden clock (ARCH-303).
- The deny-list scan grows to the catalogue files (`test_brands`).
- **Sizes:** APK +≈ 2.5 MB (catalogue) +≈ 1.5 MB (Coil + OkHttp, no R8). Target ≤ 48 MB, hard limit unchanged at 60 MB.

## Risks

| Risk | Mitigation |
| --- | --- |
| A Wikidata SPARQL timeout on large regions | Chunked per region and per class group, with 3 retries and exponential back-off; the run fails loudly and the previous catalogue stays on main |
| Wrong inflections | The 48-form oracle, an override table, and the nominative fallback in copy («из Москвы» style copy only when a form exists) |
| An image is a poor fit (wrong building, interior) | Ranking keeps P18, which is curated by the Wikidata community. The card has «Сообщить об ошибке» (stored locally, as today) |
| Commons / Nominatim rate limits | Commons thumbnails are cached (64 MB); Nominatim gets explicit-submit only, ≤ 1/s, and a 24 h in-memory result cache |
| The synthetic-distance error is noticeable to the CEO | The «расстояния приблизительные» line on Road ahead for synthetic routes (`route.synthetic = true` in the trip); fixture-area routes stay exact |
