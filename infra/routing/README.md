# Routing: self-hosted GraphHopper (ENG-01, ADR-0017)

GraphHopper 11.0 with two car profiles over a Geofabrik Russia extract, used by the planner through
`verst_planner.adapters.graphhopper.GraphHopperRouting` (`RoutingPort`). Nothing here is wired into the app yet
(ADR-0017 §5).

| File | What |
| --- | --- |
| `config.yml` | GraphHopper config: profiles `car` and `car_avoid_tolls` (CH), encoded values for path details, snap radius |
| `custom_models/verst_car.json` | The bundled `car.json` plus one rule: a toll trunk (М-12, ЦКАД) runs at the motorway default of 100 km/h, because `maxspeed=RU:rural` is not parsed and such roads otherwise fall back to the 70 km/h trunk default |
| `custom_models/avoid_tolls.json` | `toll == ALL` → priority ×0.01 |
| `build_graph.sh` | Download the extract (Central + Volga, Central, or Russia), merge, import, write `build.json` |
| `Dockerfile`, `docker-compose.yml` | The server and the weekly build on the maps VM |
| `check_routes.py`, `references.json` | The ENG-01 integration check: reference trips, full plans, recordings |
| `dev/make_mini_osm.py`, `dev/record_fixtures.sh` | A synthetic mini map and the recorder of the adapter's unit-test fixtures |

## Pinned versions

| Item | Pin | Source |
| --- | --- | --- |
| GraphHopper | `graphhopper-web` **11.0** (2025-10-14), sha256 `b59c024a…3def` | [Maven Central](https://repo1.maven.org/maven2/com/graphhopper/graphhopper-web/11.0/), [CHANGELOG](https://github.com/graphhopper/graphhopper/blob/master/CHANGELOG.md). 11.1 (2026-09-29) exists; upgrade after one CI run on it |
| Java | Temurin 21 (CI: `actions/setup-java`; image: `eclipse-temurin:21.0.12_8-jre-noble`) | GraphHopper needs Java ≥ 17 ([README 11.0](https://github.com/graphhopper/graphhopper/blob/11.0/README.md#installation)) |
| Docker image | built here; upstream has only a community image built daily from `master` | [README 11.0 "Docker"](https://github.com/graphhopper/graphhopper/blob/11.0/README.md#docker) |

## Run it locally on the mini map (no internet beyond Maven Central)

```bash
curl -fLO https://repo1.maven.org/maven2/com/graphhopper/graphhopper-web/11.0/graphhopper-web-11.0.jar
infra/routing/dev/record_fixtures.sh ./graphhopper-web-11.0.jar /tmp/gh-fixtures   # imports, serves, records
```

`record_fixtures.sh` with no second argument rewrites `backend/planner/tests/data/graphhopper/`; the request
bodies come from the adapter (`request_body`), so the fixtures always match what it sends.

## Run it on the maps VM

```bash
sudo install -d -o 10001 /srv/verst/routing                          # the image runs as uid 10001
cd infra/routing && docker compose build
docker compose --profile build run --rm build central+volga /data/next 10g   # ~1.7 GB download + import
sudo mv /srv/verst/routing/next /srv/verst/routing/current
GH_BIND=<private IP> GH_JAVA_OPTS="-Xmx6g -Xms6g" docker compose up -d graphhopper
curl -fs http://<private IP>:8989/health      # "OK"; then point verst-api at VERST_GRAPHHOPPER_URL=http://<private IP>:8989
```

- **Never publish 8989 on a public interface.** GraphHopper has no authentication; only verst-api talks to it
  (ADR-0001). The request log is off in `config.yml` (R-07: GET query strings carry coordinates).
- **Weekly rebuild** (SPEC §11): build into `/data/next` while `/data/current` serves, then
  `docker compose stop graphhopper && mv current previous && mv next current && docker compose up -d graphhopper`.
  The server loads a built graph in minutes, not the hour an import takes. On a VM too small to import and
  serve at once (see Sizing), stop the server first and accept the night-time downtime, or import on the CI
  runner and copy `graph-cache/` over.
- **Overrides.** Only `datareader.file` and `graph.location` are passed as `-Ddw.graphhopper.*`; both were checked
  to take effect. `prepare.min_network_size` passed that way was ignored (Dropwizard splits the key at the dot, the
  file holds it flat), so change other keys in `config.yml`.

## Sizing

### Measured: the graph on disk (MMAP) instead of the heap — routing.yml runs 4 and 5, 27.10.2026

The same Central + Volga graph (822 MB of files), the same load (`load_test.py`: 400 random town pairs, 8
threads, 4 vCPU) and the same route/plan checks (`check_routes.py`):

| Server | Memory | Routes/s | Latency p50 / p95 / p99 | Checks |
| --- | --- | ---: | ---: | --- |
| `RAM_STORE`, `-Xmx6g` (the heap holds the graph) | RSS 1.77 GB (anon 1.8 GB) | 65.8 | 124 / 223 / 251 ms | all pass |
| `MMAP`, `-Xmx1g`, whole process capped at 1.5 GB, cold start after `drop_caches` | RSS 0.82 GB (anon 438 MB + mapped files 406 MB); cgroup peak **960 MB** with the page cache (file 515 MB) | 59.8 | 137 / 232 / 301 ms | all pass |

MMAP costs 8–9 % of throughput and needs a third of the memory; the kernel keeps the hot part of the graph in
the page cache and reads the rest from the SSD, so a small VM degrades on rare routes instead of failing.
**Decision (D-IR-21):** the VMs serve with `graph.dataaccess.default_type: MMAP` and a 1 GB heap; the graph is
built in CI (16 GB runner) and copied to the VM, never imported there. For the whole of Russia expect ~3× the
files (PBF 4.2 GB vs 1.66 GB): ~2.5 GB on disk, ~1 GB heap + whatever page cache the VM has.

The memory does not grow with users: one graph serves every request. Users cost CPU: ~60 routes/s per 4 vCPU
(≈ 5 M routes a day), and a plan needs one route; the planner itself (~1 s CPU per plan) is the first thing to
scale out, by running more API processes against the same GraphHopper.

### Import (unchanged: CI only)


What is known:

- Planet (May 2022, 415 M edges): base import ~60 GB RAM in ~3 h; CH for car **with** turn costs ~120 GB,
  ~25 h; LM ~80 GB ([deploy.md 11.0](https://github.com/graphhopper/graphhopper/blob/11.0/docs/core/deploy.md)).
- Russia extract: 4.2 GB PBF (ADR-0012 as-built, data run 7, 2026-10-25); the planet PBF is 87.1 GB
  (2026-07-01, [OSM wiki "Planet.osm"](https://wiki.openstreetmap.org/wiki/Planet)), so Russia is ~5 % of the
  planet. The Volga district is ~665 MB ([Geofabrik Russia](https://download.geofabrik.de/russia.html));
  Central's size is printed by the CI log.
- With `RAM_STORE` (`config.yml`) the whole graph lives on the JVM heap.

Estimate (scaled by PBF size from the planet figures; **to be replaced by the CI numbers**: `build.json`
`graphBytes`, `importSeconds`, and the server RSS in `memory.txt` of the `routing-recordings` artifact):

| Region | Import heap | Graph (2 CH profiles, no turn costs) | Server heap | Import time (4 vCPU) |
| --- | --- | --- | --- | --- |
| Central + Volga | 10 GB is ample (~2–3 GB expected) | ~1.5–3 GB | 6 GB | 15–40 min |
| Russia | 12 GB (~4–6 GB expected) | ~3–6 GB | 8–10 GB | 30–90 min |

- The CI runner (public repository: 4 vCPU, 16 GB RAM, 14 GB SSD,
  [GitHub docs](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)) imports with
  `-Xmx10g` (12g for Russia, after freeing preinstalled SDKs for disk) and serves with 6 GB (10 GB) once the
  import JVM has exited. The import uses `-XX:+UseParallelGC` and the `import` command, as deploy.md advises.
- Maps VM: SPEC §11 plans 8 vCPU / 32 GB / 200 GB for GraphHopper + Photon + tiles. GraphHopper for all of
  Russia needs ~10 GB of that while serving and ~12 GB more while importing, so the 32 GB VM can rebuild without
  downtime. A 4 vCPU / 16 GB VM serves Russia but must stop the server to rebuild.

## Knobs (deliberately off this week)

- **Turn costs / turn restrictions** (`turn_costs` in the profile): correct no-left-turn handling in cities,
  ~5x the CH preparation (deploy.md). Navigation is handed off to Yandex Navigator / 2GIS, so the effect on our
  km and minutes is small; revisit if the beta reports implausible city legs.
- **Per-request custom models** (`ch.disable=true` + `profiles_lm`): needed only for request-time weighting
  (e.g. "avoid unpaved"). Costs an extra LM preparation (planet: ~80 GB and ~4 h, deploy.md).
- **`max_speed_calculator` / urban density**: country speed defaults; slower import. The km gate does not need
  them; the minutes are checked against Яндекс Карты in VAL-05 field trips. One narrow substitute is on:
  `verst_car.json` drives toll trunks at 100 km/h, because without it М-12 ties with М-7 (both 70 km/h) and
  Москва → Казань never takes М-12 (first real-data run, Oct 26, 2026).

## CI

`.github/workflows/routing.yml` (manual: Actions → routing → Run workflow, or
`gh workflow run routing.yml -f region=central+volga`): build or restore the graph, start the server, run the
adapter tests and `check_routes.py`, upload `routing-recordings` (report.md/json, recordings/*.json,
build.json, memory.txt, server.log). The graph is cached by GraphHopper version, region, config hash and
Geofabrik date; a re-run restores the newest graph of the same version, region and config unless `rebuild`.
