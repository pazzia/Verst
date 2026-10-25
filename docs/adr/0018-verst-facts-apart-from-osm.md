# ADR-0018: Verst's own place facts, kept apart from OpenStreetMap (DATA-01)

Status: **Proposed (Architect)**, working default until the lawyer answers LEG-01 · Date: 2026-10-25 ·
Branch `ccr-013d3489-181fz2` · Refs: backlog DATA-01, DATA-04; Legal risk register R-02, R-07;
`docs/legal/lawyer-brief-odbl.md` §4–5; decisions D-IR-08, D-IR-13; `docs/curation/checklist.md`,
`docs/curation/work-plan.md` §6–7; ADR-0005 (Directus), ADR-0008 (SQL-first); SPEC §9.
Implements: `backend/migrations/sql/0002_place_provenance.sql` (+ `.down.sql`),
`backend/planner/tests/test_schema_separation.py`.

## 1. Context and constraints

- **ODbL.** SPEC §9 step 1 imports OSM POIs into `core.place`, and curators then extend them. That makes
  `core.place` a Derivative Database of OSM. Its results are shown publicly, so the whole table, with our tags,
  prices and checks, would fall under ODbL and its copy would have to be offered (brief §4.2). Step 1 is frozen
  (D-IR-08). Week-2 scope is «DATA-01: ADR + migration separating our facts from OSM (Legal variant R)» (D-IR-13).
- **What 0001 has.** `core.place.source IN ('curated','osm','partner')`. `core.place.osm_id` and
  `core.town.osm_id` exist «for import idempotency». «Live ⇒ verified» has an escape for `source = 'osm'`.
  `verified_by` holds a Directus e-mail (personal data, R-07).
- **What the Data Curator cannot record today** (work-plan §7): evidence per fact; «no» vs «unknown» for a tag;
  photo author and licence; the road and km post of a place (so no per-corridor KPI); fuel kinds at a station.
  Three defaults also mislead users: empty hours = always open, no ticket price = free, breakfast included by default.
- **Environment.** No database is deployed yet (DEV-B02), and Directus is not set up (`admin/` is empty). The
  sandbox has a PostgreSQL 16 server but no PostGIS. CI has no database. The app's engine reads the open-data
  catalogue, not `core.place`. The goldens must stay byte-identical this week, so the engine is not changed.

## 2. Decision: two layers, OSM by reference only

| Layer | What | Licence | Rule |
| --- | --- | --- | --- |
| **A: OSM layer** | OSM extract, the catalogue in the APK, routing graph, tiles, region boundaries (`core.region.geom`), toll lines (`core.toll_segment.geom`) | ODbL | Rebuilt whole from OSM. Never edited with our data. Offered under ODbL (D-IR-07). |
| **B: Verst layer** | Every table classed `verst` below | ours | Every value is our own observation, backed by a `core.evidence` row. **No value is taken from OSM**: not copied, not auto-filled, not offered as a suggestion. |
| **Link** | `core.place_osm_ref`, `core.town_osm_ref` | — | `osm_type` + `osm_id` and who linked them. Nothing else: no name, no coordinates, no tags. Optional. |

**Variant.** This is Legal's variant R, as the risk register's default R-02 applies it. A place keeps its own
identity (`core.place.id`), and the OSM link is optional. A place also has its own name and coordinates, which a
curator captures from independent sources (§4). This differs from the brief's strict R («name and coordinates stay
in A», §4.3 p. 5) in one way: a live place needs coordinates in the database for the engine and for the KPI. The
difference is the lawyer's question L1 (§11). Variant N («the type is ours entirely, no OSM link») needs no schema
change: the link table simply stays empty for those types.

**Table classes** (each table has exactly one; `test_schema_separation.py` `LAYER` holds the list and fails on an
unclassified table):

| Class | Tables |
| --- | --- |
| `verst` (layer B) | `core.place`, `core.town`, `core.ready_route`, `core.ready_route_point`, `core.region_price`, `core.curator`, `core.evidence`, `core.place_check`, `core.place_tag`, `core.place_fuel`, `core.place_photo`, `core.road`, `core.place_road`, `core.ready_route_road` |
| `osm_ref` | `core.place_osm_ref`, `core.town_osm_ref` |
| `open_reference` (layer A or public data, not part of the moat) | `core.region`, `core.toll_segment` |
| `config` / `runtime` | `core.app_config` / `app.device`, `app.trip`, `app.trip_stop`, `app.feedback`, `app.pro_waitlist` |

There is no OSM POI table in PostgreSQL. If ENG-04 ever needs one, it goes into a separate schema `osm`, is
classed `open_reference`, and no Verst table references it.

## 3. Data model (migration 0002)

| Table | Key columns | Rules |
| --- | --- | --- |
| `core.curator` | `id` (`cur-01`, `sys-users`, `sys-partner`, `legacy-0001`), `role`, `active` | No name, e-mail or phone (§6). |
| `core.evidence` | `place_id` or `town_id`, `property`, `qualifier`, `observed_value`, `source_kind`, `source_url`, `source_detail`, `checked_at`, `checked_by`, `note` | One row = one observed fact, the same as the curator sheet «Доказательства» (checklist §2.3). `property` comes from a closed list per subject, which covers every fact column (test R5). `qualifier` names the tag, fuel kind or road. `source_kind`: `call · site · visit · reviews · partner · user · registry · wikidata`. There is **no OSM kind**, and a CHECK rejects openstreetmap.org, Overpass, Nominatim and Geofabrik URLs. Append-only by convention. |
| `core.place_check` | `place_id`, `kind` (`full · recheck · audit · user_confirm · partner_feed · legacy`), `result` (`pass · fail · closed · unreachable · duplicate`), `checked_at`, `checked_by`, `minutes_spent` | The verification log. The latest `pass` sets `core.place.verified_at`/`verified_by`. A curator `pass` is refused while evidence is missing. `minutes_spent` feeds KPI K5. |
| `core.place_tag` | `place_id`, `tag`, `state` (`yes · no · unknown`), `conditions[]`, `condition_ru` | No row = not asked yet; `unknown` = asked, could not find out. Conditions are allowed only on `yes`. Non-restrictive: `surcharge`, `deposit`, `outside_only`. Restrictive: `size_limit`, `by_request`, `some_rooms`, `seasonal`, `limited_hours`. A `yes` with a restrictive condition is **not** promised to users. |
| `core.place_fuel` | `place_id`, `fuel_kind` (`ai92 · ai95 · ai98 · ai100 · dt · lpg · cng`), `state` | Only for `type = 'fuel'`: a typed FK to `core.place (id, type)` makes that structural. |
| `core.place_photo` | `file_key`, `origin` (`own · commons · venue · legacy`), `author_credit`, `licence`, `source_url`, `rights_ref`, `checked_*`, `status` | A live photo needs a licence, an author credit and a check. Commons needs the file URL and a free licence. Own and venue photos need a contract or letter reference (`rights_ref`, internal only). |
| `core.road` | `ref` (`М-8`), `name_ru`, `kind` (`federal · regional · corridor`) | Official numbers (Government Decree No. 928), not OSM `ref`. The 11 federal roads of the plan are seeded: М-2, М-3, М-4, М-5, М-7, М-8, М-10, М-11, М-12, Р-21, Р-22. A CHECK catches a Latin «M». |
| `core.place_road` | `place_id`, `road_ref`, `km`, `direction` (`both · km_up · km_down · unknown`) | Where the curator saw the place: «М-8, 112 км, в сторону Ярославля». |
| `core.ready_route_road` | `route_id`, `seq`, `road_ref`, `km_from`, `km_to` | Road stretches a ready route drives: its corridor for the KPI. |
| `core.place_osm_ref` / `core.town_osm_ref` | `place_id`/`town_id`, `osm_type`, `osm_id bigint`, `match_method`, `linked_at`, `linked_by` | Exactly these columns (test R2). |

**Computed columns.** `core.place.tags`, `photo_keys`, `verified_at` and `verified_by` are now caches, written
only by the trigger `place_derive`. It runs on every insert and update of a place and after any change in
`place_tag`, `place_photo` or `place_check`. A direct write is overwritten. Each column has one source of truth
and a cache that cannot drift. The engine/API contract of `core.place` keeps its column names.

- `tags` = tags with state `yes` and no restrictive condition.
- `photo_keys` = live photos, in `seq` order.
- `verified_at` / `verified_by` = the latest `pass`.

**Evidence gate.** `core.required_evidence(type)` encodes the «О» columns of checklist §1:

| Type | Required evidence |
| --- | --- |
| `lodging` | name, geom, address, town, hours, price, breakfast, rating |
| `food` | name, geom, address, hours, average check, rating |
| `fuel` | name, geom, hours, fuel kinds, road, rating |
| `rest` | name, geom, hours, rating |
| `sight` | name, geom, address, hours, dwell, ticket (or `free_entry`), description, rating |

On top of the list, every tag and fuel kind stated `yes`/`no`, and every road link, needs its own evidence row.
`core.place_missing_evidence(id)` returns what is still missing. The triggers `place_live_gate` (status → `live`)
and `place_check_gate` (curator `pass`) refuse while it is not empty. «Факт без доказательства — не факт.»

## 4. Coordinates, names and addresses: allowed sources (lawyer's default)

- **Name, address:** the sign, the official site, a call (checklist §5.1). Never OSM `name`/`addr:*`.
- **Coordinates** (`evidence_geom_source` CHECK):
  - `visit`: GNSS on site;
  - `site`: coordinates or a map pin that the venue or chain publishes itself;
  - `partner`: a contracted feed;
  - `registry`: an official register;
  - `wikidata`: CC0, for towns and sights.
- **Not allowed until LEG-01 answers:** OSM data; clicking on an OSM-based map (osm.org, our own tiles, the
  Directus map widget on an OSM basemap); our OSM-based geocoders (Photon, Nominatim). Yandex and 2GIS
  geocoders stay out because of their terms (R-02).
- A **draft may have no coordinates** (`geom` is now nullable). A live place must have them
  (`place_live_geom`). Nothing pushes a curator to borrow OSM coordinates just to save a draft.

## 5. What happens to the 0001 columns

| 0001 | After 0002 |
| --- | --- |
| `core.place.osm_id`, `core.town.osm_id` (text `n123`) | Moved to `*_osm_ref` (`osm_type`, `osm_id bigint`, `match_method = 'legacy_0001'`), then **dropped**. |
| `core.place.source` `'osm'` | **Removed** from the CHECK. The migration **aborts** if any `source = 'osm'` row exists. Such rows are OSM data inside layer B: a human re-verifies them from independent sources or deletes them. None should exist (D-IR-08; nothing is deployed). |
| `place_live_verified` (escape for `osm`) | `live ⇒ verified_at AND verified_by`, no escape. |
| `verified_at`, `verified_by` (Directus e-mail/id) | Computed from `core.place_check`. A pre-0002 date becomes a `legacy` check by `legacy-0001`. **The old `verified_by` text is discarded** (152-FZ). Legacy-verified places do not count as verified in the KPI until they are re-checked with evidence. |
| `tags[]` | Computed from `core.place_tag`. Backfill: each tag → `yes`, without evidence. Those places appear in `core.place_evidence_missing`. |
| `photo_keys[]` | Computed from live `core.place_photo`. Backfill: origin `legacy`, `draft`. **They are not shown until a curator records the licence.** |
| `breakfast_included NOT NULL DEFAULT true` | **Nullable, no default.** NULL = unknown. Old values are kept: a default cannot be told apart from a fact, and the evidence queue lists them. |
| `geom NOT NULL` | Nullable for non-live rows (§4). |
| — | New, `NOT VALID` (enforced on new and edited rows; existing rows are fixed when touched): `place_live_hours` (live ⇒ hours, `24/7` written explicitly) and `place_live_ticket` (live sight ⇒ adult ticket price or `free_entry`). Once `core.place_evidence_missing` is empty: `ALTER TABLE core.place VALIDATE CONSTRAINT place_live_hours, …` (one statement per constraint). |
| `core.place_recheck_due` | Same columns; the `source <> 'osm'` clause is dropped. |

Convention (ADR-0008, as in 0001): the file runs once, inside the Alembic revision's transaction. Reference rows
(curators `sys-*`/`legacy-0001`, the 11 roads) are idempotent upserts. `0002_place_provenance.down.sql` reverses
it for `alembic downgrade` (architecture §9.4). The reverse is lossy: evidence, checks, tag states, fuel kinds,
photo licences and roads are dropped, and NULL breakfast becomes `true` again. It refuses to run while a place has
no coordinates.

## 6. Personal data (152-FZ, R-07)

- `core.curator` holds a pseudonymous id and a role only. The CEO keeps the mapping id → person in the contract
  records, outside the database. In Directus, login e-mails stay in Directus' own `directus_users`, linked by a
  custom field `curator_id`. Every `*_by` column in a Verst table references `core.curator` (test R6).
- `evidence.source_detail` holds the business phone and the respondent's **role**. It never holds names or an
  owner's personal mobile (checklist §5.4). The column is free text: the 10 % audit checks it.
- `place_photo.author_credit` holds the Commons attribution that the licence requires. Our own photos are
  credited «Верста», not the employee. `rights_ref` is internal.
- `place_check.minutes_spent` is work-time data of a pseudonymous worker, used for KPI K5 only.

## 7. DATA-04 KPI

- **Verified place** (`core.place_verified`; work-plan §6): `live`, the last pass is not `legacy`, and **no
  evidence is missing**. This is stricter than «at least one evidence row», so a re-check without evidence does
  not count.
- **Age bucket** (`core.verification_age_bucket`): `fresh` < 90 d, `ageing` 90–180 d, `stale` > 180 d. The
  boundary is the same as `core.place_recheck_due`.
- **Route membership** (`core.place_route_membership`): a place belongs to a route if
  (1) it is a stop of the route,
  (2) its town is a `night`/`via` town of the route, or
  (3) it sits on a road stretch the route drives (`place_road.km` within `ready_route_road.km_from..km_to`).
  Rule 3 replaces work-plan §6 condition 3 (the 15 km geometric corridor) until ENG-01 provides route lines.
- **Views**, read-only collections in Directus:
  - `core.kpi_verified_total` (K1, K4);
  - `core.kpi_verified_by_route` (K2, K4; every route listed, also with 0);
  - `core.kpi_verified_by_corridor` (K2 by road, K4).

  Each view has the columns `place_type` (`all` or a type), `verified`, `fresh_lt_90d`, `ageing_90_180d` and
  `stale_gt_180d`. A place on two routes or two roads counts in each of them.

## 8. Enforcement

- **In the database:**
  - CHECK constraints: no `osm` source; no OSM URL; allowed coordinate sources; tag and condition lists; photo
    licence; curator id format; `who` per check kind;
  - the typed FK for fuel;
  - triggers: `place_derive`, `place_live_gate`, `place_check_gate`;
  - the migration guard.
- **In CI** (`backend/planner/tests/test_schema_separation.py`, stdlib, normal `unittest discover` path):
  - the test parses `0001`…`NNNN` (not `.down.sql`) into a schema model and applies rules R1–R7 from data in
    the file: `LAYER`, `OSM_REF_COLUMNS`, `ALLOWED_COORDINATES`, `OSM_KEYS` + `ALLOWED_OSM_KEY_NAMES`,
    `ALLOWED_JSON`, `OSM_SOURCE_VALUES`, `STRUCTURAL`/`DERIVED`;
  - it proves that it bites: the same rules flag 0001 (`osm_id`, `'osm'` source, `verified_by`), and 13 injected
    violations;
  - the parser **fails closed**: a DDL form it does not know raises an error, it is never skipped;
  - `planner.yml` now also runs on pushes that touch `backend/migrations/**`.
- **What the test cannot see:** a value copied by hand into a legitimate column (for example an OSM address
  typed into `address`). The evidence gate and the audit cover that. The brief's value-matching check («no value
  of B equals A») needs layer A in the database. It is a follow-up for ENG-04 if layer A ever lands in PostgreSQL.

## 9. Consequences

**Curator workflow.** The sheet maps 1:1:

| Sheet / decision | Database |
| --- | --- |
| «Места» | `core.place` + `place_tag` + `place_fuel` + `place_road` |
| «Доказательства» | `core.evidence` |
| decision, `verified_at`/`by`, `minutes_spent` | `core.place_check` |
| tag «да» | `yes` |
| tag «нет» | `no` |
| tag «неизвестно» | `unknown` |
| tag «условно» | `yes` + a restrictive condition + `condition_ru` |

The «dogs: small only» default (work-plan §8 q3) is therefore data, not a curator's judgement call.

The steps for one place:
1. Create a draft from an independent source, with no OSM values; coordinates may come later.
2. Record tag and fuel states.
3. Record one evidence row per fact.
4. Record the check (`full`, `pass`, minutes).
5. Set `live`. Steps 4 and 5 are refused with the list of missing evidence.

A re-check adds evidence rows and a `recheck`. The 180-day queue (`place_recheck_due`) is unchanged.
`core.place_evidence_missing` is the curator's to-do list.

**Directus (ADR-0005, architecture §9.5).**
- Register the new tables and views.
- Make `tags`, `photo_keys`, `verified_at` and `verified_by` read-only.
- Replace the flow «stamp `verified_at/by` on status → live» with an action «Проверено» that inserts a
  `place_check` row with the user's `curator_id`.
- `curator`: insert on evidence. `lead`: update and delete on evidence, and the OSM links.
- The map interface on `geom` must not be a coordinate source while §4 stands. Curators type lat/lon, or the
  widget gets a non-OSM basemap after LEG-01.

**API/engine (ENG-04).**
- `core.place` reads as before.
- The DB adapter must map `breakfast_included IS NULL` to «not included». It must not add `true` back.
- The adapter must not fill a missing B value from layer A per property (brief §4.3 p. 6, single source per
  type × property).

**Docs.** DATA-01 acceptance also asks for a schema note in `docs/architecture.md` §9.2. The Manager integrates
it; §9.2 currently embeds 0001 verbatim and stays valid as 0001.

## 10. Engine follow-ups (not changed this week; goldens must stay identical)

| # | Misleading default | Where | Proposed fix |
| --- | --- | --- | --- |
| E-1 | Empty hours = always open | `verst_planner/pipeline/__init__.py:121-124` (`hours()` returns None = «always open»); checklist §4 | Unknown ≠ open. `None` means «hours unknown»: prefer stops with known hours in the same window, keep an unknown-hours stop only as a fallback, with the reason «часы не проверены». The DB side is done (`place_live_hours`); the risk remains for open-data places. |
| E-2 | No ticket price = free | `pipeline/sights.py:271-275` (`is_paid`: `not p.ticket_adult_rub` → free) | Unknown ≠ free. `None` → cost line «билет ≈ N ₽ (оценка)» from a per-category config default; `0` stays free. Budget fit counts the estimate. |
| E-3 | Breakfast included by default | `domain/model.py:183, 429` (`breakfast_included: bool = True`); `domain/codec.py:655` and `adapters/fake/world.py:358` (`.get("breakfastIncluded", True)`) | `bool \| None`, and `None` costs breakfast as not included (conservative), with the note «завтрак не подтверждён». The DB stores NULL now. Until the engine type changes, the ENG-04 adapter maps NULL → `False`. |
| E-4 | Every station sells every fuel | `pipeline/fuel.py:86` (any `corridor.fuel`); `domain/enums.py:56` `FuelType` | `Place.fuel_kinds` from `core.place_fuel`. Skip stations with `state = 'no'` for the vehicle's fuel; rank `unknown` below `yes`. Checklist §3.3 («нет АИ-95 → не выпускаем») can then be relaxed. |
| E-5 | Rating 3.0 by default | DB default `rating_internal 3.0`; `adapters/fake/world.py:351` | The DB side is done: rating is required evidence for every type. No engine change. |
| E-6 | «No» and «unknown» look the same | `tags: frozenset[Tag]` | Carry the tri-state to the card copy: «с собакой не пускают» vs «не проверено». DATA-03 asks about `unknown` tags first. |

Each fix changes plans, so each needs regenerated goldens and its own review. They are not part of DATA-01.

## 11. Open for the lawyer (LEG-01; add to brief §5)

- **L1:** Variant R as applied here: our own identity, plus our own independently captured name and coordinates,
  plus an optional OSM id link. Is the brief's strict form (name and coordinates only in A) required?
  Do our own values that coincide with OSM values count as copies? (Brief Q5, Q7.)
- **L2:** Coordinate sources (§4). Is geocoding each curated address with our own OSM-based Photon a
  non-substantial geocoding result, given that it is systematic over hundreds of places (Geocoding guideline)?
  May a curator read the venue's own map pin? May a curator click on an OSM-based map?
- **L3:** OSM as a candidate list and the curator's «match» to an OSM object by looking at the map (brief Q7;
  legal-talk 2019 without consensus).
- **L4:** Sights × hours and sights × fee. The brief's matrix puts both in layer A for open-data sights, but
  checklist §3.5 makes curators record them (B) for curated sights. That mixes sources within one type × property
  across Russia (brief §4.3 p. 6). Recommended default: B for these pairs across Russia once ENG-04 serves curated
  sights. The catalogue then drops OSM `opening_hours`/`fee` for sights (≈ 290 / 106 sights lose them; with E-1
  they show «часы не проверены»).
- **L5:** Are pseudonymous curator ids personal data (likely yes)? Is the contract a sufficient legal basis? Do
  we need the employee photographer's consent for the credit «Верста» (right of authorship, Civil Code art. 1265)?

## 12. Open questions, each with the default applied

1. **Throughput without coordinates** (Data Curator, CEO). Many small hotels publish only an address. Default:
   `site` covers a venue's own coordinates or map pin; otherwise the place stays a draft until a visit or a partner
   feed. The share of places this blocks is measured in the W3 test task. If it is above 20 %, escalate L2.
2. **Restrictive tag conditions.** Default as encoded (`size_limit`, `by_request`, `some_rooms`, `seasonal`,
   `limited_hours`). Changing it means editing one function, with no data migration.
3. **Corridor membership.** Default: road km ranges. Switch to the geometric 15 km corridor when ENG-01 stores
   route lines (needs PostGIS; a new view, same KPI columns).
4. **Corridor list.** Default: all 11 roads seeded. М-4 and Р-22 show 0 until a route uses them (work-plan §8 q2).
   `lead` adds regional roads and `corridor` groups (e.g. the Golden Ring regional roads).
5. **Partner places** (ENG-03, after LEG-02). Default: no exemption. A partner-fed lodging also needs a curator's
   rating and a `pass` before it goes live. `sys-partner` records the partner's facts as evidence.
6. **User confirmations** (DATA-03). Default: a `user_confirm` refreshes `verified_at` (SPEC). The KPI still
   requires complete evidence, so a user confirmation alone does not make a legacy place «verified».

## 13. Options considered

- **One table with per-column source flags** (0001 + flags): rejected. OSM values would still sit next to ours
  in one table, which is the R-02 problem itself.
- **Brief's strict R** (no name or coordinates in B; geometry from layer A at query time): rejected for now. The
  engine and the KPI need a coordinate for every live place, and the database would depend on layer A at runtime.
  The lawyer may still require it (L1). It would then be a new migration, with no change to the evidence model.
- **Generic fact table** (brief sketch `place_fact(subject, property, value)` as the only store): rejected. It
  loses the typed CHECKs and the engine/API contract. We keep typed current values plus an evidence log.
- **A separate `verst` schema:** rejected. It changes Directus and the API for no extra safety. The
  classification is enforced by the test.

## 14. Verification (2026-10-25)

- `cd backend/planner && python3 -m unittest discover` → all tests OK, including 6 new ones in
  `tests/test_schema_separation.py`. The goldens are unchanged (`git status backend/planner/tests/golden` is clean).
- **Dry run on a real PostgreSQL 16.15** (sandbox server; no PostGIS, so `geometry`/`geography` were shimmed as
  domains over `point` for the dry run only):
  - 0001 + seeds + 0002 apply;
  - legacy rows migrate: OSM ids moved, e-mail dropped, tags kept, unlicensed photos hidden;
  - the guard aborts on a `source = 'osm'` row;
  - 29 behavioural checks pass (18 expected rejections, 11 assertions): gates, OSM URL refused, typed fuel FK,
    tag projection, photo licence, KPI views, feedback auto-hide;
  - `up → down` leaves a schema whose sorted `pg_dump -s` equals 0001's, and `up` applies again.

  Details are in `docs/dev-notes.md` § Investor-readiness / DATA-01.
