# ADR-0017: Real road routing with self-hosted GraphHopper 11, and how the phone gets real routes

Status: **Proposed (Architect)** · Date: 2026-10-25 · Backlog: ENG-01 (week 2 slice), prepares ENG-02 and ENG-04 ·
Refs: SPEC §7.2, §7.7, §10, §11, §16; ADR-0001, ADR-0002, ADR-0010, ADR-0012 §4, ADR-0016 §4; A§5.3.1;
risk register R-07 · Sources in §9, cited as [S1]…

## 1. Context and constraints

- ENG-01 acceptance: Москва → Ярославль, Москва → Казань and the Golden Ring within **3 %** of Яндекс Карты road
  km; plan p95 ≤ 10 s for ≤ 1 500 km (SPEC §16); no trip shown to a beta user is `route.synthetic`.
- Today every route outside the 47-edge fixture graph is synthetic: straight legs × a calibrated factor
  (`HybridRouting`, ADR-0012 §4; MAPE 18 %, p90 36 %).
- SPEC §10 and ADR-0001 already chose a self-hosted OSM router; this ADR re-checks the choice against the current
  releases and fixes the details the adapter needs.
- **Environment.** This sandbox reaches Maven Central and Docker Hub, but not Geofabrik (403), so no real Russian
  graph can be built here. GitHub Actions runners have internet (public repository: 4 vCPU, 16 GB RAM, 14 GB SSD
  [S19]). There is no VM yet; the provider and size are the CEO's decision (SPEC §11, §8 below).
- The planner package is stdlib-only and its ports are synchronous (ADR-0002). The phone runs the same engine
  offline through Chaquopy (ADR-0010). ADR-0016 OR-7: the on-device engine never does network I/O.

## 2. Options

| Criterion (our need) | **GraphHopper 11.0** | OSRM (v5/v6) | Valhalla |
| --- | --- | --- | --- |
| Licence | Apache-2.0 [S7] | BSD-2-Clause [S9] | MIT [S13] |
| Car profile | bundled `car.json` custom model; avoids private roads since 11.0 [S5] | `car.lua`, compiled into the data at extract time [S11] | `auto` costing, per request [S14] |
| Toll flag per segment of the answer | path detail `toll` = `no`/`hgv`/`all` per interval of points [S1, S3] (measured: §6) | only `classes: ["toll", …]` on intersections when `steps=true` [S10] | `toll` per maneuver, `has_toll` per trip [S14] |
| Avoid tolls | custom model `toll == ALL` → priority; per profile (CH) or per request (LM) [S3] | `exclude=toll` (class must be `excludable` in the profile) [S10, S11] | `use_tolls` 0…1 per request, "not guaranteed" [S14] |
| Road ref (М-4) per segment | path detail `street_ref` per interval [S1] (measured: §6) | `ref` only on route steps (`steps=true`) [S10] | street names/refs per maneuver |
| Distance and time per segment | path details `distance`, `time`, `leg_distance` | `annotations=distance,duration` per coordinate [S10] | per maneuver |
| Memory, planet | import ~60 GB, CH with turn costs ~120 GB, LM ~80 GB (2022, 415 M edges) [S4] | car ~123 GiB RAM, ~300 GB disk (v5.26, planet 2021) [S12] | tile-based; not measured here |
| Memory, Russia (~5 % of the planet by PBF: 4.2 GB of 87.1 GB [S18]) | estimate 3–6 GB graph for 2 CH profiles without turn costs, server heap 8–10 GB; CI measures it (§6) | estimate ~6 GB | — |
| Docker | no official image (community image from `master` only) [S6]; we build one from the Maven jar (§3) | `ghcr.io/project-osrm/osrm-backend` [S26] | images under `ghcr.io/valhalla` [S27] |
| Per-request flexibility later | custom models (needs LM) | none without a re-extract | full |

**Why not OSRM:** it is the fastest and lightest, but toll and ref data come only through turn-by-turn steps and
intersection classes, so we would rebuild per-segment road class, ref and toll from steps (A§5.3.1 needs all
three on every segment for the corridor, fuel and toll stages), and every routing change means a re-extract.
**Why not Valhalla:** flexible and light, but tolls are per maneuver and `use_tolls` is a preference, not a rule;
nothing in our needs requires per-request costing now. Both stay fallbacks behind `RoutingPort`.

## 3. Decision

**GraphHopper 11.0** (released 2025-10-14 [S5]; 11.1 of 2026-09-29 and 12.0-pre2 exist on Maven Central [S8]
and are taken after one green CI run each), configured in `infra/routing/config.yml`:

| Setting | Value | Why |
| --- | --- | --- |
| Profiles | `car` = `car.json`; `car_avoid_tolls` = `car.json` + `custom_models/avoid_tolls.json` (`toll == ALL` → priority ×0.01) | Avoid tolls is a server-side custom model on its own CH profile: one parameter per request, millisecond queries, flat memory per request. ×0.01 priority = ×100 cost, the same soft rule as `FakeRouting.TOLL_AVOID_FACTOR` (a toll road is still used when nothing else exists) |
| Speed mode | `profiles_ch` for both; `profiles_lm: []` | A per-request `custom_model` would need `ch.disable=true` and an LM preparation [S1, S4]; not needed now (deviation from A§5.3.1, which planned per-request custom models) |
| Turn costs | off | CH with turn costs is ~5× the preparation [S4]; navigation is handed off to Yandex Navigator / 2GIS. Revisit if beta city legs look wrong |
| Encoded values | `car_access, car_average_speed, road_access` (car.json) + `road_class, road_class_link, road_environment, toll, max_speed` | `road_class`, `toll` are needed as path details; `street_ref`, `distance`, `time`, `leg_distance` are built in |
| Snap radius | `index.max_region_search: 8` | The default (4) gives up at ~1.2–1.4 km; SPEC §7.2 snaps up to 2 km. With 8 GraphHopper snaps to ~3 km and the **adapter** enforces 2 km (§4) |
| `routing.timeout_ms` | 5 000 | Ends a runaway query before the adapter's 6 s |
| Ignored highways | footway, construction, cycleway, path, steps, pedestrian, bridleway, proposed | Car-only graph; `track` kept (sights at the end of dirt roads) |
| Request log | off | GET query strings carry coordinates (R-07); the adapter uses POST |

**Extract.** The maps VM serves **all of Russia** (Geofabrik `russia-latest`, weekly). A Central-FD-only start is
not enough: Казань is in the Volga FD, and two of the ten launch ready routes (Великий Новгород, Карелия;
SPEC §7.6) are in the Northwestern FD; ENG-02's М-11, М-4 and М-1 tolls leave the Central FD too. CI uses
**Central + Volga** merged with `osmium merge` (it covers all ENG-01 trips and fits a standard runner), with a
same-timestamp check because osmium only de-duplicates snapshots of the same moment [S16, S17].

**Packaging.** We build `infra/routing/Dockerfile` from `eclipse-temurin:21.0.12_8-jre-noble` and the Maven Central
jar with a pinned sha256 (b59c024a…3def, verified in this sandbox against Maven's published SHA-1 4cba3d3b…). The
image runs as uid 10001; `docker-compose.yml` publishes 8989 on the private address only (`GH_BIND`).

## 4. The adapter: `verst_planner.adapters.graphhopper`

**Location.** Inside the stdlib-only planner package, not `verst_api.adapters` as ADR-0002 planned: `verst_api`
does not exist yet, the planner CI tests it with stdlib `unittest`, and the CI check composes it with the real
engine. It is not wired into any composition root (`mobile`, `cli`, `engine`); a test asserts this. ENG-04 may
move it; the import path is the only thing that changes.

| Part | Rule |
| --- | --- |
| `GraphHopperSettings.from_env` | `VERST_GRAPHHOPPER_URL` (required, `http(s)://host[:port][/path]`), `VERST_GRAPHHOPPER_TIMEOUT_S` (default 6, SPEC §10) |
| Request | `POST {url}/route`: `profile` = `car` or `car_avoid_tolls`, `points` `[lon, lat]`, `snap_preventions: [motorway, tunnel, bridge, ferry]`, `points_encoded: false`, `instructions: false`, `calc_points: true`, `details: [road_class, toll, street_ref, distance, time, leg_distance]` |
| Budget | 6 s for the whole call: connect + read bounded by the socket timeout, the body by a deadline check; one retry only on a refused connection and only with ≥ 0.5 s left (A§5.3.1) |
| `points` | GeoJSON coordinates → `LatLon` |
| `cum_km`, `cum_min` | each `distance` / `time` interval spread over its segments in proportion to their length; sums equal `paths[0].distance` / `time`. Missing or malformed details → the path totals spread the same way |
| Densify | GraphHopper drops the inner vertices of straight edges (a 16 km motorway arrives as one segment); points are inserted so no segment exceeds 1 km road distance, the vertex spacing the engine's stages were built on (Fake/HybridRouting) |
| `details` | cut at every boundary of `road_class`, `street_ref`, `toll`; merged when (class, ref, toll) repeat. `motorway/trunk/primary/secondary` → `RoadClass`, everything else and `null` → `OTHER`; `toll == "all"` → `True` (`hgv` is free for a car); `street_ref` → first ref of `"М-10, Е105"`, Latin route letter → Cyrillic (`M-10` → `М-10`, `P`/`R` → `Р`, `A` → `А`) |
| `waypoint_idx` | from `leg_distance` interval ends (exact); fallback: nearest point to each snapped waypoint, searched forward |
| `snapped` | `snapped_waypoints`; a waypoint farther than 2 km from its request point → `Unreachable(i, snap_km)` (SPEC §7.2) |
| Errors | 400 `PointNotFoundException` / `PointOutOfBoundsException` → `Unreachable(point_index)`; `ConnectionNotFoundException` → the legs are routed one by one to name the first unreachable point (`Unreachable(i + 1)`, the FakeRouting convention); timeout, network error, 5xx, any other 4xx (unknown profile or detail = a deployment error, logged as ERROR), non-JSON or malformed 200 → `UpstreamUnavailable("graphhopper")` |
| Logs (R-07) | logger `verst_planner.adapters.graphhopper`; coordinates rounded to 2 decimals (~1 km), never the polyline; decimal numbers in GraphHopper's messages are rounded before logging |

Caching (`CachedRouting`, Redis 24 h, A§5.3.1) belongs to ENG-04 and wraps this adapter unchanged.

## 5. How the phone gets real routes (the offline rule)

1. **Real routes come only from our server.** The phone never calls GraphHopper (private network, ADR-0001), and
   the on-device engine never does network I/O (ADR-0016 OR-7).
2. **Online plan (beta and production flavours), ENG-04:** the engine exposes `route_points(input)` (the points the
   base-route stage will request: resolved origin, vias, ready-route points, return leg; pure, no I/O). Kotlin
   sends them to verst-api `POST /v1/route {points, avoidTolls}`; the server answers from
   `CachedRouting(GraphHopperRouting)` with the `Route` JSON; Kotlin calls `plan(input, route)`, and a
   `PrefetchedRouting` adapter returns that route when the request points are equal. The trip is real
   (`synthetic = false`). Server-side planning (the web planner, ENG-06) uses `GraphHopperRouting` in process.
3. **No connection or a routing failure** (6 s timeout, 5xx, the OR-6 breaker open):
   - demo flavour: `HybridRouting` as today, labelled (`approxDistances`, «расстояния приблизительные»);
   - beta flavour: **no synthetic trip by default**. The plan screen shows «Маршрут построим, когда появится
     интернет» (OR-4). A remote-config flag `allowSyntheticOffline` (default **off** for the closed beta) allows
     the labelled synthetic plan; such a trip is never saved as final and is re-planned when the connection
     returns. This makes the acceptance "no beta trip is synthetic" true by construction and measurable (an
     analytics event `route_synthetic_shown`, ENG-05).
4. **`Unreachable` from the server is an answer, not an outage:** the app shows `UNREACHABLE` for that point;
   it does not fall back to the road model.
5. **Saved trips** keep their real polyline and work offline; stop replacement and cost patches need no routing
   (A§6.11). Card estimates before planning («≈ 265 км») may stay on the road model, always with «≈».

## 6. Verification

Done in this sandbox (dev-notes "Investor-readiness / ENG-01" lists the commands):

- **Real GraphHopper 11.0** (the Maven jar, sha-checked) imported and served a synthetic mini map
  (`infra/routing/dev/make_mini_osm.py`) with this `config.yml`, unchanged. The 12 unit-test fixtures are its
  real responses (`record_fixtures.sh`; request bodies built by the adapter itself). Observed and now relied on:
  values are lower-case; a link carries its road's class; two refs arrive as `"М-10, Е105"`; a via point appears
  once in `points` and `leg_distance` marks it; straight edges arrive as one segment; with the default
  `max_region_search` a point 1.45 km off the road is "Cannot find point", with 8 it snaps at 2.55 km;
  `prepare.min_network_size` given as `-Ddw.…` is ignored (the flat key in the file wins), while
  `datareader.file` and `graph.location` overrides work; the server loads an existing graph when the PBF is absent.
- The Docker image (with the jar copied in instead of downloaded, because this sandbox's TLS proxy breaks curl
  inside the build) ran under `docker compose`, became `healthy`, ran as uid 10001 and answered the adapter.
- `check_routes.py` ran end to end against a stub that serves `HybridRouting` routes in GraphHopper's format: 4
  routes and 3 full plans on `russia_v1` (61–145 ms per plan on the sandbox).

Only CI and the VM can verify (`.github/workflows/routing.yml`, manual):

- the real km for the four reference trips, the refs (М-8, М-12, М-7, Р-132) and the toll km on М-12;
- routing latency (gate p95 ≤ 1 s per call) and full-plan latency with real routes (gate p95 ≤ 10 s);
- import time, graph size and server RSS for the VM sizing (`build.json`, `memory.txt`);
- the merge of two extracts, the Geofabrik download and the cache.

**Reference km.** `infra/routing/references.json` holds published figures, not Яндекс Карты measurements:
Москва → Ярославль 265 km by М-8 (265–270) [S20]; Москва → Казань 810 km, the length of М-12 [S21, S22] (city
centre to centre is a little longer: М-12 does not enter Казань); without tolls by М-7 815–825 km [S23]; the
Golden Ring loop 775 km = 75 + 75 + 65 + 60 + 85 + 105 + 95 + 35 + 180 by legs, other sources 770–780 [S24, S25].
Until a person builds the same trips in Яндекс Карты from the same points and fills `yandexKm`, the check gates at
±7 % of the published figure and prints UNCONFIRMED; with `yandexKm` it gates at the 3 % acceptance.

## 7. Consequences

- Goldens stay byte-identical: they test the engine on the fixture world through `FakeRouting` (ADR-0002) and
  are not re-baselined to real roads. The ENG-01 item "golden trips re-baselined" is met instead by updating the
  ready-route templates' `kmTotal`/`kmSign` (e.g. Золотое кольцо 745 → the measured value) from the CI report,
  with the justification in the commit (week 3).
- A GraphHopper route has thousands of points (densified to ≤ 1 km); the engine handled them in the stub run
  (~0.15 s for the Golden Ring plan). The real numbers come from CI.
- The APK carries 26 KB of unused adapter source until ENG-04 decides where it lives.
- Operations: a weekly import (30–90 min estimated for Russia), a private-network-only service, and the RAM of
  §8. Upgrades are a jar pin + sha + one CI run.
- Risks: OSM toll tagging may be incomplete (the CI gate on М-12 toll km shows it; ENG-02 keeps the curated
  `toll_segment` table as the tariff source); OSM refs may be missing on some segments (they are display data,
  never a planning input).

## 8. Open questions for the CEO (defaults applied in the files)

| Question | Recommended default |
| --- | --- |
| Provider | Yandex Cloud, region ru-central1 (Moscow), or Selectel Moscow; both are in Russia (R-07). Default in the docs: Yandex Cloud |
| Size of the maps VM | SPEC §11: 8 vCPU / 32 GB / 200 GB SSD for GraphHopper (Russia) + Photon (R-11) + tiles; it rebuilds without downtime. Minimum for GraphHopper alone: 4 vCPU / 16 GB / 60 GB with night-time rebuild downtime |
| Budget | price both sizes in the providers' calculators before ordering; I could not verify a current per-hour rate for a 100 % vCPU from public pages |
| Extract on the VM | all of Russia, weekly (Sunday night) |
| Who confirms the 3 % | a person builds the 4 trips in Яндекс Карты from the points in `references.json` and fills `yandexKm` + date |

## 9. Sources (checked 2026-10-25)

- [S1] GraphHopper 11.0 Web API: https://github.com/graphhopper/graphhopper/blob/11.0/docs/web/api-doc.md
- [S2] GraphHopper 11.0 config example: https://github.com/graphhopper/graphhopper/blob/11.0/config-example.yml
- [S3] GraphHopper 11.0 custom models (`toll`: MISSING, NO, HGV, ALL; priority): https://github.com/graphhopper/graphhopper/blob/11.0/docs/core/custom-models.md
- [S4] GraphHopper 11.0 deploy guide (memory, import vs server, ParallelGC): https://github.com/graphhopper/graphhopper/blob/11.0/docs/core/deploy.md
- [S5] GraphHopper changelog (11.0, 2025-10-14): https://github.com/graphhopper/graphhopper/blob/master/CHANGELOG.md
- [S6] GraphHopper 11.0 README (Java ≥ 17, Docker): https://github.com/graphhopper/graphhopper/blob/11.0/README.md
- [S7] GraphHopper licence (Apache-2.0): https://github.com/graphhopper/graphhopper/blob/11.0/LICENSE.txt
- [S8] Maven Central `graphhopper-web`: https://repo1.maven.org/maven2/com/graphhopper/graphhopper-web/
- [S9] OSRM licence (BSD-2-Clause): https://github.com/Project-OSRM/osrm-backend/blob/master/LICENSE.TXT
- [S10] OSRM HTTP API (`exclude`, `annotations`, step `ref`, intersection `classes`): https://github.com/Project-OSRM/osrm-backend/blob/master/docs/http.md
- [S11] OSRM car profile (`excludable` toll): https://github.com/Project-OSRM/osrm-backend/blob/master/profiles/car.lua
- [S12] OSRM disk and memory requirements: https://github.com/Project-OSRM/osrm-backend/wiki/Disk-and-Memory-Requirements
- [S13] Valhalla licence (MIT): https://github.com/valhalla/valhalla/blob/master/COPYING
- [S14] Valhalla API reference (`use_tolls`, `has_toll`, maneuver `toll`): https://github.com/valhalla/valhalla/blob/d5338866e66759f8afa6f9b500e825eb818427a8/docs/docs/api/turn-by-turn/api-reference.md
- [S15] Geofabrik Russia extracts (daily, ODbL, Volga FD ~665 MB): https://download.geofabrik.de/russia.html
- [S16] osmium-merge(1): https://manpages.debian.org/trixie-backports/osmium-tool/osmium-merge.1.en.html
- [S17] osmium-fileinfo (`header.option.osmosis_replication_timestamp`): https://docs.osmcode.org/osmium/latest/osmium-fileinfo.html
- [S18] OSM wiki, Planet.osm (87.1 GB PBF on 2026-07-01): https://wiki.openstreetmap.org/wiki/Planet
- [S19] GitHub-hosted runners: https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- [S20] Москва — Ярославль: https://tonkosti.ru/Журнал/Расстояние_между_Москвой_и_Ярославлем
- [S21] М-12, 810 км: https://www.cian.ru/stati-trassa-m-12-337066/
- [S22] «Республика Татарстан», 810 км по М-12 (PDF): https://rt-online.ru/wp-content/uploads/2024/05/rt-060-01c.pdf
- [S23] Москва — Казань по М-7: https://tonkosti.ru/Журнал/Расстояние_между_Москвой_и_Казанью
- [S24] Золотое кольцо на машине, участки и 775 км: https://auto.mail.ru/article/97700-poyezdka-po-zolotomu-koltsu-na-mashine/
- [S25] Золотое кольцо на машине, 770–780 км: https://www.kp.ru/russia/goroda-zolotogo-koltsa-rossii/poezdka-na-mashine/
- [S26] OSRM README (Docker): https://github.com/Project-OSRM/osrm-backend/blob/master/README.md
- [S27] Valhalla README (Docker): https://github.com/valhalla/valhalla/blob/master/README.md

The distance sources [S20]–[S25] were read through search-engine excerpts: tonkosti.ru, ru.wikipedia.org and
geofabrik.de are not reachable from this sandbox. They are references for a person to confirm in Яндекс Карты,
not acceptance values.

## Amendment (2026-10-26): toll expressway speed

The first `routing.yml` run on real data (Central + Volga, run 40349692421) routed Москва → Казань over М-7 even with
tolls allowed (803 km, 692 min). The diagnosis run (40353574860) showed why:

- М-12 is in the graph and routable: forced through a point in Чувашия, the route used 582 km of М-12.
- Its time was no better, though: Москва → that point took 616 km in 529 min, about 70 km/h.
- Most of М-12 is mapped as `highway=trunk` + `toll=yes` + `motorroad=yes` + `maxspeed=RU:rural`.
- GraphHopper only parses numeric `maxspeed`, so these edges get the trunk default of 70 km/h, the same as the old
  М-7 through towns.

**Decision.** Both profiles use `custom_models/verst_car.json` instead of the bundled `car.json`. It is the same model
plus one rule: `road_class == TRUNK && toll == ALL` is limited to 100 km/h (the motorway default, 110 × 0.9), and a
numeric sign still limits it to `max_speed × 0.9`.

**Not chosen.** `max_speed_calculator` + urban density would fix legal defaults for all roads. It costs a slower
import, and the speeds it sets cannot raise `car_average_speed` without the same kind of rule. Revisit with the
VAL-05 field trips, which measure minutes.

