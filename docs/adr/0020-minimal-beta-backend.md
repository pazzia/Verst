# ADR-0020: The minimal beta backend (ENG-04)

Status: **Proposed (Architect)** · Date: 2026-10-26 · Branch `ccr-013d3489-181fz2` · Backlog: ENG-04 (unblocks
ENG-05, ENG-06, DATA-02, DATA-03, BIZ-05) · Refs: SPEC §11, §12, §16; architecture §9, §10, §12; ADR-0003
(FastAPI), ADR-0006 (SSE), ADR-0007 (device auth), ADR-0008 (SQL-first), ADR-0017 (routing), ADR-0018 (Place DB);
risk register R-07. Implements: `backend/api/**`, `infra/api/**`, `.github/workflows/api.yml`.

## 1. Context and constraints

- **ENG-04:** "Minimal backend: plan API, ready routes, feedback, links; Docker Compose on one VM in Russia".
  Acceptance on the VM: ≥ 99 % monthly uptime and backups that restore. Audience: the closed beta (VAL-04,
  ≥ 100 families), not the public launch.
- **The engine already ships on the phone** (ADR-0010) and plans offline from the packaged open-data catalogue.
  What the phone cannot do alone: real road routes (ADR-0017 §5: `POST /v1/route` → `PrefetchedRouting`), share
  links that open for people without the app, place feedback for the curators, and partner links.
- **Data.** The Place DB (ADR-0018, `core.*`, PostGIS) is not populated yet (DATA-02 starts after this task);
  the engine's places are the catalogue's text ids (`Q123`, `osm_n1`, `pl_…`). The server therefore plans on the
  same data as the phone: `central_russia_v1` + the packaged catalogue = world `russia_v1`.
- **Engine shape.** `verst_planner` is stdlib-only with synchronous ports; its app-facing bridge
  (`verst_planner.mobile`) holds module state and is documented as single-threaded.
- **Privacy (R-07, Legal):** store trip coordinates rounded to ~1 km; a share link shows the town of the start,
  not the point; no personal data; servers and backups in Russia; logs with rounded coordinates.
- **No affiliate links before LEG-02** (legal entity, Travelpayouts account, 38-FZ labelling).
- **Environment.** This sandbox has PostgreSQL 16 server binaries (no PostGIS), PyPI, Docker (Docker Hub via a
  mirror only) and no GraphHopper graph of Russia; GitHub Actions has a `postgres:16` service and Docker Hub.

## 2. Scope: smallest backend that ships the beta

| In (beta) | Endpoint | Notes |
| --- | --- | --- |
| Device registration | `POST /v1/devices` | ADR-0007 unchanged: 32-byte token, only sha256 stored |
| Server plan (+ SSE progress) | `POST /v1/trips/plan` | GraphHopper routing, road model only as flagged fallback (§4); not persisted |
| Real route for the phone | `POST /v1/route` | ADR-0017 §5; never a road-model route |
| Ready routes near a point | `GET /v1/ready-routes?lat&lon&limit` | the bridge's `ready_routes` items, hub ≤ 50 km |
| Save trip + share link | `POST /v1/trips` → `{tripId, shareSlug, shareUrl}` | privacy-reduced copy (§5.3); idempotent; 50 per device |
| Unshare | `DELETE /v1/trips/{tripId}` | owner only |
| Shared trip | `GET /v1/shared/{slug}` (JSON), `GET /s/{slug}` (HTML) | public, town only, `noindex` |
| Feedback | `POST /v1/feedback {kind, placeId?, tripId?, text?}` | kinds of A§9 (`closed`, `wrong_tag`, `price`, `other`) |
| Partner link stub | `GET /v1/links/hotel?placeId&checkin&nights&adults&childrenAges` | plain Yandex Travel city search, `affiliate: false` (§2.1) |
| Ops | `GET /healthz`, `/readyz`, `/metrics` | `/readyz`, `/metrics` private (proxy answers 404) |

| Deferred | Why it can wait | Lands with |
| --- | --- | --- |
| `GET /v1/trips/{id}`, stop replace, cost patch on the server | the phone owns its trips and runs replace/patch on-device | ENG-06 (web planner) |
| Geocoding (`/v1/geocode/*`, Photon) | the app's search uses the catalogue + Nominatim today (R-11) | before the public release |
| `/v1/config` remote config, `/v1/pro-waitlist`, excursion/navigator links | app-side constants suffice for 100 families; navigator links are built on-device (ADR-0014) | BIZ-06, ENG-03 |
| Redis (route cache, sliding-window limits) | PostgreSQL counters and no cache are enough at beta load (§6) | when p95 or load says so |
| Place DB as the engine's source (`PgPlaceRepository`, PostGIS) | DATA-01/02 not live | after DATA-02 |
| Directus, Prometheus/Grafana, GlitchTip | curators read feedback with SQL for the beta; metrics are exposed, a scraper is a deploy-time choice | DATA-03 / after beta |
| Affiliate wrapper (Travelpayouts) | LEG-02 | ENG-03 |

### 2.1 Partner link stub

`GET /v1/links/hotel` resolves the place with the bridge's `poi_details` (400 `not_a_hotel` otherwise) and returns
`https://travel.yandex.ru/hotels/search/?text=<town>&checkinDate&checkoutDate&adults[&childrenAges]`,
`partner: "yandex_travel"`, `affiliate: false`. No marker, no wrapper, no hotel id (the catalogue's hotels are
fictional demo data until ENG-03). A test asserts no `tp.media`/`marker`/`sub_id` ever appears.

## 3. Engine hosting and contracts

- **One engine thread per process.** Every bridge call runs on `verst-engine`, a one-thread executor
  (`verst_api.engine.executor`), honouring the bridge's single-thread contract; uvicorn workers (processes,
  default 2) give parallelism. Cancellation uses the engine's `CancelToken` from the event loop.
- **Server planner.** At start the host loads the worlds through the bridge's public functions (`set_clock`,
  `load_world`, `load_catalogue`), then builds its own `Planner` over the `russia_v1` ports with the server
  routing (§4) and `mobile.OPEN_DATA_CONFIG`. A plan runs once (the bridge's `plan` runs a quiet second plan to
  compute a progress-text hint; the server does not pay that).
- **No forked shapes.** Results are rendered by the bridge's own functions, so the HTTP body is exactly the
  `result` of `docs/contracts/v2/plan-*.json`. Requests mirror `codec.input_from_json` key for key, strict
  about JSON types; value ranges are validated once, by the engine (its `INVALID_INPUT {field, reason}` is
  returned as is). Handlers return the engine JSON without re-serialising it; pydantic response models document
  it in OpenAPI and are validated against every v2 example in the tests.
- **Seams.** The bridge has no public "plan with this routing" entry point, so the host uses three internals:
  `mobile._WORLDS` (read only), `mobile._trip_result`, `mobile._no_fit_result`. They are resolved once at start
  (`engine._seams`, fails fast with a named error) and covered by the contract tests (server body ==
  `mobile.plan` body for every v2 plan example). Follow-up for the planner owner in §10.
- **Plan response.** 200 with `{"outcome": "plan" | "no_fit", …}` (ADR-0011 «не помещается» is an answer, not
  an error). Nothing is stored: saving is an explicit `POST /v1/trips`, the same call for server- and
  phone-planned trips.
- **SSE (ADR-0006), kept because it was cheap:** `Accept: text/event-stream` → `retry: 3000`, `stage`
  (`{key, text, progress}`) and `stop` (`{day, stop}`) events with increasing ids, `: ping` every 5 s, then
  `done` whose data is exactly the JSON body of the non-SSE call (the A§10.4 `done {tripId, trip}` has no
  `tripId` because a plan is not persisted), or `error {code, message, details}`. Client disconnect or the 25 s
  limit cancels the plan. Errors before the stream (auth, validation, rate limit) are plain HTTP errors.
- **Errors (A§10.6):** `{"error": {"code", "message" (ru), "details"}}`; codes `INVALID_INPUT` 400,
  `UNAUTHORIZED` 401, `NOT_FOUND`/`UNREACHABLE` 404, `LIMIT_REACHED` 409, `PAYLOAD_TOO_LARGE` 413, `TOO_SHORT`
  422, `RATE_LIMITED` 429 + `Retry-After`, `INTERNAL` 500 (nothing leaked), `UPSTREAM` 503 (GraphHopper down,
  plan timeout, routing not configured). A trip from another engine major.minor → 400 `{field: engineVersion,
  reason: incompatible}`.

## 4. Routing

| `VERST_ROUTING` | Server plan | `POST /v1/route` |
| --- | --- | --- |
| `graphhopper` (VM default) | `ServerRouting(GraphHopperRouting)`; GraphHopper down → 503 `UPSTREAM`, or, with `VERST_SYNTHETIC_FALLBACK=true`, the road model with `synthetic = true` (trip `approxDistances: true`, metric `verst_routing_fallback_total`) | the GraphHopper route; down → 503 |
| `road_model` (dev, tests, VM before the graph exists) | the engine's `HybridRouting`, flagged where synthetic, exactly as on the phone | 503 `routing_not_configured`: the phone applies its own offline rule (ADR-0017 §5.3), never a server-made synthetic route |

`Unreachable` from GraphHopper is an answer (404 `UNREACHABLE {pointIndex}`), never a reason to fall back.
`VERST_SYNTHETIC_FALLBACK` defaults to **false** so the acceptance "no beta trip is synthetic" holds by
construction; turning it on is an explicit ops decision (e.g. during a graph rebuild on a 16 GB VM).

### 4.2 `POST /v1/route` wire shape

Request `{"points": [[lat, lon], …] (2–30), "avoidTolls": false}`. Response (`verst_api.routing.route_to_json`):
`points` and `snapped` as `[lat, lon]` rounded to 6 decimals, `cumKm` (3 decimals), `cumMin` (2), `details`
`[{fromIdx, toIdx, roadClass, roadRef, toll}]`, `waypointIdx`, `kmTotal`, `minTotal`, `synthetic` — one field per
`domain.model.Route` field, so `PrefetchedRouting` decodes it without interpretation. The exact points go back to
the device that sent them and are neither stored nor logged. The codec moves to `verst_planner.domain.codec`
when the planner adds `PrefetchedRouting` (one source of truth for both directions).

## 5. Storage

### 5.1 PostgreSQL 16, schema `api` (not `app` of migration 0001)

`app.*` (A§9.2) references `core.place`/`core.ready_route` by uuid and lives next to PostGIS tables; the beta's
place ids are catalogue text ids and the Place DB is not live. The beta gets its own small schema, no
extensions (`gen_random_uuid()` is core): `api.device`, `api.trip` (privacy-reduced trip `jsonb`, share slug,
`content_hash` for idempotent saves, `km`/`days`/`synthetic` columns for KPIs), `api.feedback` (text place id),
`api.rate_counter`, `api.schema_migration`. `app.*` remains the target once the engine reads the Place DB;
moving the beta rows then is a one-off SQL copy (§10).

### 5.2 Migrations

SQL files `backend/api/migrations/NNNN_name.sql` + `.down.sql`, applied by a small runner
(`verst_api.db`, `python -m verst_api.db up|down N|status`), each file in a transaction, all under an advisory
lock so several workers can start together. **Deviation from ADR-0003 (Alembic):** for one SQL-first schema
(ADR-0008) Alembic adds a dependency and an env script and gives nothing the runner lacks; revisit when
autogenerate or branching migrations are needed.

### 5.3 Privacy reduction (R-07), `verst_api.privacy`

On `POST /v1/trips` the server stores and shares only:
1. user points (`input.origin`, `input.destination`, `input.vias`) labelled with their **town** (the engine's
   nearest catalogue town within 60 km, else «Точка на карте»);
2. start/finish/via stops that are user points (no `placeId`, no `townId`) renamed to that town;
3. every former label replaced by its town in every string (titles and reasons quote labels);
4. every `lat`/`lon` in the trip rounded to **2 decimals** (~1 km);
5. the share text recomputed by the engine from the reduced trip.

Exact coordinates exist only in memory during a request. Logs: route templates (never raw paths or query
strings), an 8-hex device tag, coordinates through `privacy.log_point` (2 decimals); uvicorn's and Caddy's
access logs are off; PostgreSQL logs no bind values. Feedback text: phones (≥ 7 digits) and e-mails masked
before storage, text cleared after 180 days (`VERST_FEEDBACK_TEXT_DAYS`, hourly job under an advisory lock).
IPs: only `HMAC-SHA256(VERST_RATE_KEY_SECRET, ip)[:16]` inside rate-limit keys, deleted after two days.
Residual risk: a modified client can upload arbitrary text in a trip; the page is escaped, CSP `default-src
'none'`, `noindex`, rate-limited, and a trip is deletable — moderation is out of beta scope.

### 5.4 Tests run on real PostgreSQL, not SQLite

The store uses `jsonb`, `ON CONFLICT … RETURNING`, advisory locks, `make_interval`, CHECK regexes and
`gen_random_uuid()`; a second dialect would test a database we do not ship. CI uses a `postgres:16.14` service
(`VERST_TEST_DATABASE_URL`, `VERST_TEST_REQUIRE_PG=1` makes a missing database a failure); locally the fixture
starts a throwaway cluster from the server binaries on a Unix socket (as `postgres` when run as root) and
removes it. PostGIS is not needed by the `api` schema.

## 6. Rate limits

Fixed windows counted in PostgreSQL (`INSERT … ON CONFLICT DO UPDATE … RETURNING hits`), shared by all
workers; no Redis. 429 `RATE_LIMITED {bucket, limit}` with `Retry-After` = seconds to the window end.
Unauthenticated requests are rejected before they count.

| Bucket | Limit (env) | Key |
| --- | --- | --- |
| plan | 30 / h (`VERST_RATE_PLAN_PER_HOUR`) | device |
| route | 60 / h | device |
| save | 20 / h; at most 50 saved trips (`LIMIT_REACHED`) | device |
| feedback | 10 / day | device |
| default (ready routes, links, delete) | 600 / h | device |
| register | 20 / h | HMAC(IP) |
| public (`/s/…`, `/v1/shared/…`) | 300 / h | HMAC(IP) |

Body size: 2 MB (Caddy `request_body` and the app's own limit, chunked bodies included → 413).

## 7. Deployment: one VM, Docker Compose (`infra/api`)

- `proxy`: **Caddy 2.11** with automatic HTTPS — deviation from A§12.1 (nginx + certbot): one container instead
  of two plus a renewal job; it flushes SSE, does not compress `text/event-stream`, hides `/metrics`, `/readyz`,
  `/docs`, `/openapi.json`, and replaces client `X-Forwarded-For`.
- `api`: `python:3.12.14-slim-trixie`, dependencies from `requirements.lock` with `--require-hashes`, uid 10002,
  read-only root filesystem, `no-new-privileges`, all capabilities dropped, not published; `uvicorn --workers 2
  --proxy-headers --no-access-log`; Prometheus multiprocess metrics in `/tmp` (tmpfs).
- `postgres:16.14-trixie` with a named volume; `backup`: `prodrigestivill/postgres-backup-local` daily 03:00 MSK,
  14 daily / 4 weekly / 3 monthly, `restore-drill.sh` restores the newest dump into a throwaway container.
- `graphhopper` (profile `routing`) extends `infra/routing/docker-compose.yml` with its port un-published.
- Configuration: environment only (`VERST_*`, `.env.example`, no secrets in the repo); `env=prod` refuses to start
  without a ≥ 32-char `VERST_RATE_KEY_SECRET`, an https `VERST_PUBLIC_BASE_URL` and the system clock.

## 8. Observability

JSON lines on stdout (`ts, level, logger, msg, request_id` + whitelisted fields); `X-Request-Id` echoed (8–64 safe
chars) or generated, and carried into the engine and GraphHopper adapter logs. Metrics:
`verst_http_requests_total{route,method,status}`, `verst_http_request_seconds{route}`,
`verst_plan_seconds{outcome}`, `verst_plan_synthetic_total`, `verst_routing_fallback_total`,
`verst_route_requests_total{outcome}`. `/readyz` reports database, engine, routing mode and catalogue version.

## 9. Tests (`backend/api/tests`, pytest + Starlette TestClient, no network)

Contract (server body == bridge body for every v2 plan example, == the committed file when the engine still
produces it, models accept every example, SSE sequence and `done` body, ready routes == bridge, OpenAPI path
set); auth (hash-only storage, malformed/unknown/revoked tokens, hourly `last_seen`); rate limits (per device,
per bucket, daily, per IP without storing the IP, unauthenticated not counted); privacy (DB holds no label or
exact coordinate, every stored coordinate ≤ 2 decimals, share page and shared JSON show the town only, log lines
carry no exact coordinates/labels/query strings/tokens, feedback masking and expiry); errors (engine and request
validation, UNREACHABLE/TOO_SHORT, 404/413 incl. chunked, 500 without leaks, timeout 503); routing (recorded real
GraphHopper 11 responses from `backend/planner/tests/data/graphhopper`, avoid-tolls, unreachable, not configured,
fallback flagged, no fallback on `Unreachable`); store (migrations up/down/up, constraints, limit, idempotent save,
foreign trip ids); SSE unit tests (disconnect cancels, heartbeat, time limit). CI: `.github/workflows/api.yml`.

## 10. Consequences and follow-ups

- The beta backend is one image and four containers; nothing in it needs PostGIS, Redis or Directus.
- **Planner owner (small):** expose `mobile.trip_result(plan, world_id)` / `mobile.no_fit_result(nf, world_id)`
  (public names for `_trip_result` / `_no_fit_result`) and a read-only `mobile.world_ports(world_id)`; the host
  then drops its seams. Add `route_points(input)` + `PrefetchedRouting` (ADR-0017 §5) and move `route_to_json` /
  `route_from_json` into `domain.codec`.
- **When the Place DB goes live:** copy `api.device/trip/feedback` into `app.*` (text place ids map through
  `core.place` external ids) or retire `app.*`; decide in that ADR.
- `api.feedback` has no auto-hide trigger (A§9.2 `feedback_autohide`): curators triage by SQL during the beta;
  DATA-03 adds the user-verification kinds and the trigger against the Place DB.
- Single-threaded engine per worker: a 25 s plan blocks that worker's other engine calls (ready routes, saves).
  At beta load (≤ 30 plans/h/device, ~100 devices) two workers are enough; raise `VERST_WORKERS` (≈ 60 MB each)
  before the public release, or move plans to a process pool.

## 11. Open questions (defaults applied)

| Question | Default applied |
| --- | --- |
| VM provider and size | Yandex Cloud ru-central1 (as ADR-0017). One VM 8 vCPU / 32 GB / 160 GB SSD runs API + Postgres + GraphHopper (Russia graph ~10 GB heap, rebuild without downtime). 4 vCPU / 16 GB works with a weekly 30–90 min routing gap (≈ 0.5 % of the month) |
| Domain | `api.verst.app` in the docs (A§10.1); set `VERST_DOMAIN` / `VERST_PUBLIC_BASE_URL` to whatever the CEO registers. Share links are `https://<domain>/s/<slug>` |
| TLS | Let's Encrypt via Caddy (HTTP-01 on port 80). If the domain sits behind a Russian CDN later, switch to its certificate |
| Off-site backup | Weekly copy to Yandex Object Storage (ru-central1), manual until the bucket exists |
| Uptime monitor | An external HTTPS check of `/healthz` every minute with a Telegram alert (any Russian monitoring SaaS); its monthly figure is the acceptance number |
| Synthetic fallback | Off (`VERST_SYNTHETIC_FALLBACK=false`) |
| Feedback text retention | 180 days, then cleared (rows kept for KPIs) |
| Shared trip retention | Until the device deletes it; revisit with the privacy policy (LEG-02) |

## 12. Options considered

- **Persist every plan (A§10.5)** — rejected for the beta: stores data nobody asked to keep (R-07) and does not
  cover phone-planned trips; explicit save serves both.
- **SQLite for tests / storage** — rejected: different SQL dialect and locking; PostgreSQL is what ships.
- **Redis for limits and route cache** — deferred: an extra service for load the beta does not have.
- **The bridge's `plan` function as is** — rejected: it plans twice for a new input and has no routing hook.
- **Calling the bridge from FastAPI's thread pool** — rejected: the bridge is single-threaded by contract.
- **nginx + certbot** — replaced by Caddy (§7).
