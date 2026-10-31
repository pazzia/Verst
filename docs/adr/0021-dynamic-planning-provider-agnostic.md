# ADR-0021: Dynamic server-side planning on provider-agnostic data sources

Status: **Proposed (Architect)**. The CEO approved the direction on 2026-10-27 (D-IR-18); the prototype (SPIKE-01) decides the details.
Date: 2026-10-27.
Refs:
- ADR-0010 (engine on the phone), ADR-0014/0015 (hand-off), ADR-0017 (GraphHopper), ADR-0018 (our facts apart from OSM), ADR-0019 (unknown is not a default), ADR-0020 (beta backend);
- `docs/research/google-maps-navigation.md`;
- backlog SOC-01…05.

## 1. Context

**The CEO's concept.** The user enters any two points, in any country, plus wishes:
- level, price and density;
- constraints: small children, pets.

Then the system:
- builds a road skeleton;
- looks for places along it in live map data;
- scores them against the questionnaire;
- re-routes through the best ones.

Good results are saved. The owner can publish a trip, and anyone can repeat it exactly, with no new search (SOC-02/03).

**What exists today.**
- **Planning is already dynamic.** The engine plans any A → B: overnights by pace, corridor detours, crew filters, cost with formulas.
- **The data is static.** Places come from a catalogue packaged in the APK: Russia only, open data, about 12 000 POIs, no ratings, prices or live hours.
- **Roads.** The phone uses a road model; real roads exist on the server (GraphHopper, ADR-0017, verified 2026-10-26).
- **Ports.** The engine reaches its data through ports (`verst_planner/ports.py`): `RoutingPort`, `GeocodingPort`, `PlaceRepository`, `PriceRepository`, `TollRepository`.

**Constraints that rule out "build everything on Google or Yandex".**

| Constraint | Detail |
| --- | --- |
| Terms of use | Google Places content must not be used with a non-Google map (Service Specific Terms §14.2). Lat/lng may be cached ≤ 30 days (§14.3); a place id may be stored indefinitely. Places UI Kit may be shown next to any map (§15.1). Yandex Geosearch results are meant for Yandex maps; storage needs the paid licence. |
| Cost per plan | Google Text/Nearby Search Pro ≈ $32 per 1 000, Place Details Enterprise ≈ $20 per 1 000 (third-party summaries of the 2026 price list). A 3-day trip needs ~30–40 searches and ~15 details, ≈ $1–2 per plan, before re-plans. Yandex Geosearch: free ≤ 500 requests a day; licence 226 200 ₽ a year for 1 000 a day, plus 390 ₽ per extra 1 000. Our revenue is ≈ 2.87 ₽ net per planned trip (BIZ-01). |
| Billing | Google Cloud does not accept new customers in Russia. A foreign entity is needed for Google outside Russia. |
| Lock-in and moat | If every place comes from Yandex, a Yandex price change or Алиса's own trip planner (the main platform threat) decides our fate. |

**CEO requirement (2026-10-27).** No binding to any one vendor. The provider of each capability is chosen per request.

## 2. Decision

### 2.1 Capabilities, not vendors

The engine depends only on capabilities. A provider is an adapter that implements one or more of them.

| Capability | Port | Examples of providers (adapters) |
| --- | --- | --- |
| Road routing | `RoutingPort` (exists) | GraphHopper on OSM (ours), road model (offline) |
| Geocoding / suggest | `GeocodingPort` (exists) | Open index (OSM/Wikidata), commercial geocoders |
| Place search in a corridor or area | `PlaceSearchPort` (new; `PlaceRepository` becomes one implementation) | Open place index (ours), commercial place search |
| Place enrichment (hours, rating, photos, price level) | `PlaceDetailsPort` (new) | Commercial place details, our verified facts |
| Lodging offers (price, availability, link) | `LodgingOffersPort` (new) | Affiliate partners (LEG-02) |
| Prices and tolls | `PriceRepository`, `TollRepository` (exist) | Our tables, regional sources |
| Preference parsing from free text | `PreferenceParserPort` (new, optional) | Any LLM; it never proposes places |
| Map display (client) | client capability `MapRenderer` | Our illustration, an open map, a vendor map component |
| Navigation hand-off (client) | `NaviTarget` list (ADR-0014) | Яндекс Навигатор / Карты, 2ГИС, Google Maps, Organic Maps |

### 2.2 Provider manifest: data, not code

Each deployment has `providers.json`. Keys live in server environment variables, never in the app or the repo. Per provider it records:

- `id`, `capabilities`, `coverage`: countries or ISO-3166-2 regions, or `world`.
- `licence`:
  - `storable`: the fields we may keep, and for how long (`ttlDays`; `forever` for ids);
  - `display`: one of `any_map` | `own_map_only` | `ui_kit`;
  - `attribution` text;
  - `needsEntity`: one of `ru` | `foreign` | `none`.
- `cost`:
  - `perCall` by method;
  - `freeQuota` per day and per month;
  - `monthlyBudget`: hard cap, beyond which the provider is skipped.
- `priority` per country, for each capability.
- Runtime state from the server: `health`, `p95Ms`, `spentThisMonth`.

### 2.3 Selection policy per request

For every capability and every trip segment (a trip may cross regions or countries), `ProviderSelector` works in four steps:

1. **Filter** by:
   - coverage of the segment;
   - licence fit with the intended use: content shown in our illustration needs `display: any_map`, otherwise the client must show the vendor's map or UI kit;
   - configured keys and an existing entity;
   - health;
   - remaining budget.
2. **Rank** by the country priority, then by cost, then by p95 latency.
3. **Call with a deadline.** On timeout or error, move to the next provider.
4. **Fallback.** The chain always ends in **open data plus our own facts**, which have no quota and no vendor. Offline, the phone uses its packaged catalogue.

The selection and its reasons are logged per plan, with no personal data: `provider`, `capability`, `reason`, `cost`.

### 2.4 One place model with provenance per field

- **Merging.** Candidates from different sources merge into one `Place`, matched by an external id (Wikidata, OSM, vendor id), or else by category + name similarity + ≤ 150 m.
- **Provenance.** Every field carries `source`, `fetchedAt`, `ttl` and `licence`.
- **Precedence.**
  - Our verified facts (ADR-0018) win.
  - Vendor fields are shown with their attribution.
  - Unknown stays «не проверено» (ADR-0019).

### 2.5 Storage follows the licence

- **Stored permanently:** open data, our facts, vendor place ids, and trips as stop references (provider, place id, our facts, coordinates as the licence allows).
- **Short-lived cache:** vendor fields such as hours, rating and photos, in memory or Redis, ≤ their TTL.
- **Opening a saved trip:** the stops and their order are replayed exactly (no new search), and the short-lived fields are re-fetched. This is how "repeat the route exactly" (SOC-02/03) stays within Google's and Yandex's terms.

### 2.6 Cost guard

- **The corridor search runs on the open place index.** Commercial search is used only for gaps: few candidates of a wanted kind in a stretch.
- **Enrichment covers the shortlist only:** ≤ N finalists, default 15, configurable.
- **Per-plan budget.** The default is ≤ 1 ₽ equivalent of commercial calls, to be revisited with BIZ-01. When it is spent, the plan finishes on open data and our facts.
- **Per-provider monthly cap.** When a provider reaches it, it drops out of selection automatically.
- **Metrics:** `verst_provider_calls_total{provider,capability}` and `verst_plan_cost_rub` (histogram).

### 2.7 Questionnaire → preference profile

The profile has a versioned schema (`profile v1`):

- crew: adults, children with ages, pets with size;
- budget; daily pace;
- comfort level; density (stops per day);
- interests (weights per category);
- constraints: avoid tolls or unpaved roads, mobility;
- free text.

Free text goes through the optional `PreferenceParserPort` into the same schema. A model only fills fields and explains choices. It never invents places: every stop comes from a source in §2.1.

### 2.8 Where planning runs

- **Online:** the server plans dynamically through the selector (`POST /v2/plan` with the profile). The response is the trip, plus provenance, plus attribution and display requirements for the client.
- **Offline:** the engine stays on the phone for saved trips and for planning with no network, on its packaged catalogue.
- **The same engine code** runs in both places. Only the adapters behind the ports differ.

### 2.9 Initial region matrix

This is configuration, not code. The SPIKE-01 numbers change it.

| Capability | Russia | Abroad (e.g. Indonesia / Bali) |
| --- | --- | --- |
| Routing | GraphHopper on OSM (Russia graph) | GraphHopper on OSM (country graphs) |
| Place search | Open index + our facts; Яндекс or 2ГИС for gaps, after the licence and LEG-02 | Open index; a commercial source for gaps (Google via a foreign entity, or another vendor assessed in the spike) |
| Enrichment | Яндекс or 2ГИС details (licence), our facts | Google Places UI Kit / details (foreign entity) or another vendor |
| Lodging | Affiliate partner after LEG-02 | Affiliate partner covering the country (to verify) |
| Navigation hand-off | Яндекс Навигатор / Карты, 2ГИС | Google Maps, Organic Maps; Яндекс where it covers |

## 3. Options rejected

- **One vendor for everything** (Google only, or Яндекс only):
  - $1–2 per plan against ≈ 3 ₽ of revenue;
  - storage bans break saved and shared trips;
  - no Google billing from Russia;
  - total lock-in.
- **Scraping maps or aggregators.** It breaks their terms and is fragile.
- **An LLM that writes the itinerary.** It invents places and hours, which is the failure we sell against.

## 4. Consequences

- **Packaged catalogue.** It becomes the offline cache. The server's open place index (DATA-05) replaces it as the online source and extends coverage beyond Russia.
- **UI.** Where a vendor requires its map (`own_map_only`), the client shows that vendor's map component for those places. The «За рулём» illustration stays for open data and our facts. This is a design task (DES-03).
- **Legal.** Each commercial provider needs a terms review, and a foreign entity is needed for Google abroad (LEG-03).
- **Unit economics.** BIZ-01 gains a cost per plan (BIZ-07).
- **Feature freeze until M2.** The prototype is research (SPIKE-01). Production work starts after M2, unless the CEO moves the freeze.

## 5. SPIKE-01 prototype (1–2 weeks)

**Goal.** Measure the dynamic pipeline before we rebuild around it.

**Scope.**
- `ProviderSelector` with a manifest.
- Open place index built for two corridors from OSM + Wikidata: Москва → Казань, and Денпасар → Убуд → Ловина (Bali).
- Corridor search, scoring by `profile v1`, re-routing through the stops on GraphHopper (Russia graph + Indonesia graph).
- One commercial enrichment adapter on a free quota, where our terms and billing allow it. Otherwise a recorded fixture.

**Measures.**

| Metric | Target or output |
| --- | --- |
| Stops worth stopping at | Share, per a manual rating by two people with the curator checklist, against today's catalogue |
| Stops with known hours | Share |
| Server plan time | p50 / p95, target ≤ 5 s |
| Commercial cost per plan | ₽ |
| Coverage gaps per kind | Table |

**Output.** A report in `docs/research/spike-01.md` and a go / no-go with the cost per plan.

## 6. Sources

- Google Maps Platform Service Specific Terms (modified 2026-10-15): https://cloud.google.com/maps-platform/terms/maps-service-terms (§14 Places API, §15 Places UI Kit).
- Google Places pricing, third-party summaries 2026: https://www.woosmap.com/blog/google-places-api-pricing, https://openplacesapi.com/blog/google-places-api-pricing.
- Яндекс API Поиска по организациям, product and tariffs: https://yandex.ru/maps-api/products/geosearch-api; docs: https://yandex.ru/maps-api/docs/geosearch-api/index.html.
- BIZ-01 revenue per trip: `docs/traction/unit-economics.md`.
