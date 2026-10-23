# ADR-0001: Self-hosted OpenStreetMap stack (GraphHopper, Photon, Planetiler/martin) instead of Yandex APIs

Status: Accepted · Date: 2026-10-23 · Refs: SPEC §10, §11, §19; architecture §1, §5.3, §12

## Context
Verst needs car routing with road refs and toll flags, typeahead geocoding for all of Russia and map tiles for the "точка на карте" picker. Yandex MapKit's free tier stops at 1,000 daily users and excludes offline maps; Yandex Router/Geocoder are paid per request. Plans call routing once per plan (plus replans), suggest ~5–10 times per search.

## Decision
Run GraphHopper (car profile, custom model for `avoidTolls`, path details `road_class`, `street_ref`, `toll`), Photon (Russia index, `lang=ru`) and vector tiles (Planetiler → MBTiles served by martin) on our own VM-B (8 vCPU / 32 GB) in Russia, rebuilt weekly from the Geofabrik Russia extract. The planner depends on them only via `RoutingPort` / `GeocodingPort`; the API wraps them in `CachedRouting` (Redis, 24 h). Turn-by-turn is handed off to Yandex Navigator / Yandex Maps / 2GIS via deep links.

## Consequences
- No per-request or DAU fees; predictable hosting cost (~1 large VM + a weekly ephemeral build VM).
- We own operations: weekly rebuild pipeline, monitoring, 6 s / 1.5 s timeouts with `UPSTREAM` fallback.
- OSM quality can be worse than Yandex in places (addresses, small roads) — mitigated by golden trips in "real mode" nightly and a provider switch behind the ports.
- Nothing of this can be verified in the current sandbox (images and extracts need network); the engine is verified with fake adapters.

## Alternatives
- **Yandex MapKit / Router / Geocoder** — best Russian data, but DAU cap and per-request pricing; kept as paid fallback adapters.
- **OSRM** instead of GraphHopper — faster, but per-request custom models (avoid tolls) require separate profiles/graphs and toll path details are weaker. Fallback only.
- **Nominatim** instead of Photon — no real typeahead; too slow for ≤ 500 ms suggestions.
- **2GIS API** — commercial, city-centric coverage.
