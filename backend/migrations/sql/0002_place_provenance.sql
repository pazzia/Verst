-- 0002 · ADR-0018 (DATA-01): Verst's own facts kept apart from OpenStreetMap.
--
-- * Verst places keep their own identity (core.place.id). Every value on core.place is our own observation,
--   backed by a row in core.evidence (who, when, how, which URL). No value is ever copied from OSM.
-- * OSM is referenced by id only, in core.place_osm_ref / core.town_osm_ref (osm_type + osm_id, nothing else).
--   The old core.place.osm_id and core.town.osm_id columns move there and are dropped.
-- * New curated facts: tri-state tags with conditions (core.place_tag), fuel kinds (core.place_fuel), photos with
--   author and licence (core.place_photo), roads and km posts (core.road, core.place_road, core.ready_route_road),
--   per-place verification log (core.place_check), pseudonymous curator ids (core.curator; no names, no e-mails).
-- * core.place.tags, photo_keys, verified_at and verified_by become caches computed from those tables by
--   triggers, so the engine/API contract of core.place is unchanged.
-- * DATA-04 KPI views: core.place_verified, core.kpi_verified_total, core.kpi_verified_by_route,
--   core.kpi_verified_by_corridor.
--
-- Convention (ADR-0008, as 0001): run once, inside the Alembic revision's transaction; reference rows are upserts.
-- Separation rules are enforced by backend/planner/tests/test_schema_separation.py (DDL parsing, stdlib).
-- Reverse: 0002_place_provenance.down.sql.

-- ---------------------------------------------------------------- 0. guard: no OSM-imported rows may exist
-- SPEC §9 step 1 (OSM import) is frozen (D-IR-08). If a database still holds imported rows, they are OSM data
-- inside our layer; a human decides (re-verify from independent sources or delete). The migration stops.
DO $guard$
BEGIN
  IF EXISTS (SELECT 1 FROM core.place WHERE source = 'osm') THEN
    RAISE EXCEPTION 'ADR-0018: % core.place rows have source = osm. Re-verify them from independent sources '
      '(set source = curated) or delete them, then rerun.', (SELECT count(*) FROM core.place WHERE source = 'osm');
  END IF;
  IF EXISTS (SELECT 1 FROM core.place WHERE osm_id !~ '^[nwr][1-9][0-9]{0,17}$')
     OR EXISTS (SELECT 1 FROM core.town WHERE osm_id !~ '^[nwr][1-9][0-9]{0,17}$') THEN
    RAISE EXCEPTION 'ADR-0018: osm_id values must look like n123 / w456 / r789 before they move to *_osm_ref';
  END IF;
END
$guard$;

-- ---------------------------------------------------------------- 1. curators (pseudonymous, 152-FZ)
-- One row per person or system that records facts. The id is all the database knows: the person behind
-- cur-NN is known only from the contract (outside the DB). Directus users map to it via a custom field.
CREATE TABLE core.curator (
  id          text PRIMARY KEY CHECK (id ~ '^(cur|sys|legacy)-[a-z0-9]{2,16}$'),   -- 'cur-01', 'sys-users'
  role        text NOT NULL CHECK (role IN ('curator','data_curator','lead','system','legacy')),
  active      boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT curator_system_prefix CHECK ((role = 'system') = (id LIKE 'sys-%')),
  CONSTRAINT curator_legacy_prefix CHECK ((role = 'legacy') = (id LIKE 'legacy-%'))
);
INSERT INTO core.curator (id, role) VALUES
  ('sys-users',   'system'),          -- DATA-03 answers of app users (anonymous devices)
  ('sys-partner', 'system'),          -- partner feeds under contract (ENG-03)
  ('legacy-0001', 'legacy')           -- verifications recorded before 0002 (who verified is not kept)
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------- 2. OSM by reference only
-- Exactly these columns. No name, no coordinates, no tags: OSM values stay in OSM (layer A, ODbL).
CREATE TABLE core.place_osm_ref (
  place_id      uuid PRIMARY KEY REFERENCES core.place(id) ON DELETE CASCADE,
  osm_type      text NOT NULL CHECK (osm_type IN ('node','way','relation')),
  osm_id        bigint NOT NULL CHECK (osm_id > 0),
  match_method  text NOT NULL CHECK (match_method IN ('curator_match','legacy_0001')),
  linked_at     timestamptz NOT NULL DEFAULT now(),
  linked_by     text NOT NULL REFERENCES core.curator(id),
  UNIQUE (osm_type, osm_id)
);
CREATE TABLE core.town_osm_ref (
  town_id       uuid PRIMARY KEY REFERENCES core.town(id) ON DELETE CASCADE,
  osm_type      text NOT NULL CHECK (osm_type IN ('node','way','relation')),
  osm_id        bigint NOT NULL CHECK (osm_id > 0),
  match_method  text NOT NULL CHECK (match_method IN ('curator_match','legacy_0001')),
  linked_at     timestamptz NOT NULL DEFAULT now(),
  linked_by     text NOT NULL REFERENCES core.curator(id),
  UNIQUE (osm_type, osm_id)
);

INSERT INTO core.place_osm_ref (place_id, osm_type, osm_id, match_method, linked_at, linked_by)
  SELECT id, CASE left(osm_id, 1) WHEN 'n' THEN 'node' WHEN 'w' THEN 'way' ELSE 'relation' END,
         substr(osm_id, 2)::bigint, 'legacy_0001', created_at, 'legacy-0001'
  FROM core.place WHERE osm_id IS NOT NULL;
INSERT INTO core.town_osm_ref (town_id, osm_type, osm_id, match_method, linked_at, linked_by)
  SELECT id, CASE left(osm_id, 1) WHEN 'n' THEN 'node' WHEN 'w' THEN 'way' ELSE 'relation' END,
         substr(osm_id, 2)::bigint, 'legacy_0001', created_at, 'legacy-0001'
  FROM core.town WHERE osm_id IS NOT NULL;
ALTER TABLE core.place DROP COLUMN osm_id;                                  -- with its UNIQUE index
ALTER TABLE core.town  DROP COLUMN osm_id;

-- ---------------------------------------------------------------- 3. verification log (one row per check)
-- core.place.verified_at / verified_by are computed from the latest 'pass' row (section 8).
CREATE TABLE core.place_check (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  place_id       uuid NOT NULL REFERENCES core.place(id) ON DELETE CASCADE,
  kind           text NOT NULL CHECK (kind IN ('full','recheck','audit','user_confirm','partner_feed','legacy')),
  result         text NOT NULL CHECK (result IN ('pass','fail','closed','unreachable','duplicate')),
  checked_at     timestamptz NOT NULL DEFAULT now(),
  checked_by     text NOT NULL REFERENCES core.curator(id),
  minutes_spent  smallint CHECK (minutes_spent BETWEEN 0 AND 600),         -- KPI K5 (work-plan §6), incl. no-answer calls
  note           text CHECK (length(note) <= 500),
  CONSTRAINT place_check_who CHECK (CASE kind
    WHEN 'legacy'       THEN checked_by LIKE 'legacy-%'
    WHEN 'user_confirm' THEN checked_by LIKE 'sys-%'
    WHEN 'partner_feed' THEN checked_by LIKE 'sys-%'
    ELSE checked_by LIKE 'cur-%' END),
  CONSTRAINT place_check_user_pass CHECK (kind <> 'user_confirm' OR result = 'pass')  -- «нет»/«закрыто» → app.feedback
);
CREATE INDEX place_check_pass_ix ON core.place_check (place_id, checked_at DESC) WHERE result = 'pass';

-- Verifications recorded before 0002 keep their date; the old verified_by text (a Directus e-mail or id) is dropped.
INSERT INTO core.place_check (place_id, kind, result, checked_at, checked_by, note)
  SELECT id, 'legacy', 'pass', verified_at, 'legacy-0001', 'verified before ADR-0018; no evidence recorded'
  FROM core.place WHERE verified_at IS NOT NULL;

-- ---------------------------------------------------------------- 4. evidence: one row per observed fact
-- Mirrors the curator sheet «Доказательства» (docs/curation/checklist.md §2.3). Append-only by convention
-- (Directus: curators insert, only `lead` may edit or delete). The property lists below must cover every fact
-- column of core.place / core.town (enforced by test_schema_separation.py).
CREATE TABLE core.evidence (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  place_id        uuid REFERENCES core.place(id) ON DELETE CASCADE,
  town_id         uuid REFERENCES core.town(id) ON DELETE CASCADE,
  property        text NOT NULL,
  qualifier       text CHECK (length(qualifier) <= 40),                    -- tag name · fuel kind · road ref
  observed_value  text CHECK (length(observed_value) <= 300),              -- in our words: 'да', 'условно: до 10 кг', '3 500 ₽ пт→сб 31.10'
  source_kind     text NOT NULL CHECK (source_kind IN ('call','site','visit','reviews','partner','user','registry','wikidata')),
  source_url      text CHECK (source_url ~ '^https?://' AND length(source_url) <= 500),
  source_detail   text CHECK (length(source_detail) <= 300),               -- business phone dialled + respondent's ROLE; review site + dates
  checked_at      date NOT NULL,
  checked_by      text NOT NULL REFERENCES core.curator(id),
  note            text CHECK (length(note) <= 500),
  created_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT evidence_one_subject CHECK (num_nonnulls(place_id, town_id) = 1),
  CONSTRAINT evidence_place_property CHECK (place_id IS NULL OR property IN (
    'type','name_ru','geom','address','town_id','opening_hours','dwell_min','avg_check_rub','price_night_rub',
    'breakfast_included','ticket_adult_rub','ticket_child_rub','rating_internal','description_ru',
    'yandex_travel_id','tripster_id','tag','fuel','road')),
  CONSTRAINT evidence_town_property CHECK (town_id IS NULL OR property IN (
    'name_ru','name_prep_ru','geom','population','quality','evening_walk')),
  CONSTRAINT evidence_qualifier CHECK ((property IN ('tag','fuel','road')) = (qualifier IS NOT NULL)),
  CONSTRAINT evidence_tag_known CHECK (property <> 'tag' OR qualifier = ANY (core.allowed_tags())),
  -- coordinates only from our own capture: GNSS on a visit, the venue's own site, a partner feed, Wikidata (CC0)
  -- or an official registry. Never from an OSM map, OSM data or an OSM-based geocoder (ADR-0018 §4, LEG-01 Q7).
  CONSTRAINT evidence_geom_source CHECK (property <> 'geom' OR source_kind IN ('visit','site','partner','registry','wikidata')),
  CONSTRAINT evidence_url_required CHECK (source_kind NOT IN ('site','partner','registry','wikidata') OR source_url IS NOT NULL),
  CONSTRAINT evidence_source_not_osm CHECK (source_url IS NULL OR source_url !~* '(openstreetmap|osm\.org|overpass|nominatim|geofabrik)'),
  CONSTRAINT evidence_not_legacy CHECK (checked_by NOT LIKE 'legacy-%')
);
CREATE INDEX evidence_place_ix ON core.evidence (place_id, property, qualifier) WHERE place_id IS NOT NULL;
CREATE INDEX evidence_town_ix  ON core.evidence (town_id, property) WHERE town_id IS NOT NULL;

-- ---------------------------------------------------------------- 5. tags: yes / no / unknown + conditions
CREATE FUNCTION core.tag_conditions() RETURNS text[] LANGUAGE sql IMMUTABLE AS $$
  SELECT ARRAY['surcharge','deposit','outside_only','size_limit','by_request','some_rooms','seasonal','limited_hours']
$$;
-- A 'yes' with one of these conditions is not promised to users: it does not reach core.place.tags
-- (checklist §2.4 «условно → тег не ставим»; CEO default work-plan §8 q3: «только мелкие собаки» is not dogs_allowed).
CREATE FUNCTION core.restrictive_tag_conditions() RETURNS text[] LANGUAGE sql IMMUTABLE AS $$
  SELECT ARRAY['size_limit','by_request','some_rooms','seasonal','limited_hours']
$$;

-- No row = not asked yet; 'unknown' = asked, could not find out (do not call again before the re-check).
CREATE TABLE core.place_tag (
  place_id      uuid NOT NULL REFERENCES core.place(id) ON DELETE CASCADE,
  tag           text NOT NULL CHECK (tag = ANY (core.allowed_tags())),
  state         text NOT NULL CHECK (state IN ('yes','no','unknown')),
  conditions    text[] NOT NULL DEFAULT '{}' CHECK (conditions <@ core.tag_conditions()),
  condition_ru  text CHECK (length(condition_ru) <= 200),                  -- 'до 10 кг, +1 000 ₽ в сутки'
  updated_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (place_id, tag),
  CONSTRAINT place_tag_conditions_on_yes CHECK (state = 'yes' OR (conditions = '{}' AND condition_ru IS NULL))
);
CREATE TRIGGER place_tag_touch BEFORE UPDATE ON core.place_tag FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();

INSERT INTO core.place_tag (place_id, tag, state)
  SELECT p.id, t.tag, 'yes' FROM core.place p CROSS JOIN LATERAL unnest(p.tags) AS t(tag)
  ON CONFLICT (place_id, tag) DO NOTHING;

-- ---------------------------------------------------------------- 6. fuel kinds at stations
CREATE FUNCTION core.fuel_kinds() RETURNS text[] LANGUAGE sql IMMUTABLE AS $$
  SELECT ARRAY['ai92','ai95','ai98','ai100','dt','lpg','cng']              -- ai92/ai95/dt = engine FuelType
$$;
ALTER TABLE core.place ADD CONSTRAINT place_id_type_key UNIQUE (id, type);   -- target of the typed FK below
CREATE TABLE core.place_fuel (
  place_id    uuid NOT NULL,
  place_type  text NOT NULL DEFAULT 'fuel' CHECK (place_type = 'fuel'),    -- only fuel stations; blocks a type change
  fuel_kind   text NOT NULL CHECK (fuel_kind = ANY (core.fuel_kinds())),
  state       text NOT NULL CHECK (state IN ('yes','no','unknown')),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (place_id, fuel_kind),
  FOREIGN KEY (place_id, place_type) REFERENCES core.place (id, type) ON DELETE CASCADE
);
CREATE TRIGGER place_fuel_touch BEFORE UPDATE ON core.place_fuel FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();

-- ---------------------------------------------------------------- 7. photos with author and licence
-- Allowed origins (checklist §5.3): our own photos (rights transferred by contract), Wikimedia Commons under a
-- free licence, venue photos with written permission. author_credit is shown under the photo as the licence
-- requires; for our own photos it is the brand («Верста»), not the employee's name.
CREATE TABLE core.place_photo (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  place_id       uuid NOT NULL REFERENCES core.place(id) ON DELETE CASCADE,
  seq            smallint NOT NULL DEFAULT 1 CHECK (seq BETWEEN 1 AND 20),
  file_key       text NOT NULL CHECK (length(file_key) BETWEEN 1 AND 300),   -- storage key, or Commons 'File:…'
  origin         text NOT NULL CHECK (origin IN ('own','commons','venue','legacy')),
  author_credit  text CHECK (length(author_credit) <= 200),
  licence        text CHECK (licence IN ('verst-owned','venue-permission','CC0-1.0','PDM-1.0',
                   'CC-BY-2.0','CC-BY-2.5','CC-BY-3.0','CC-BY-4.0','CC-BY-SA-2.0','CC-BY-SA-2.5','CC-BY-SA-3.0','CC-BY-SA-4.0')),
  source_url     text CHECK (source_url ~ '^https://' AND length(source_url) <= 500),   -- Commons file page
  rights_ref     text CHECK (length(rights_ref) <= 120),                    -- internal only: contract / letter no. and date
  taken_at       date,
  checked_at     date,
  checked_by     text REFERENCES core.curator(id),
  status         text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','live','hidden')),
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (place_id, seq),
  UNIQUE (place_id, file_key),
  CONSTRAINT place_photo_live_licensed CHECK (status <> 'live' OR (licence IS NOT NULL AND author_credit IS NOT NULL
                                                                   AND checked_at IS NOT NULL AND checked_by IS NOT NULL)),
  CONSTRAINT place_photo_commons CHECK (origin <> 'commons' OR status <> 'live'
                                        OR (source_url IS NOT NULL AND licence NOT IN ('verst-owned','venue-permission'))),
  CONSTRAINT place_photo_own     CHECK (origin <> 'own'   OR status <> 'live' OR (licence = 'verst-owned' AND rights_ref IS NOT NULL)),
  CONSTRAINT place_photo_venue   CHECK (origin <> 'venue' OR status <> 'live' OR (licence = 'venue-permission' AND rights_ref IS NOT NULL)),
  CONSTRAINT place_photo_legacy  CHECK (origin <> 'legacy' OR status <> 'live'),
  CONSTRAINT place_photo_source_not_osm CHECK (source_url IS NULL OR source_url !~* '(openstreetmap|osm\.org|overpass|nominatim|geofabrik)')
);
CREATE TRIGGER place_photo_touch BEFORE UPDATE ON core.place_photo FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();

-- photo_keys written before 0002 have no recorded licence: kept as drafts, not shown until a curator licenses them.
INSERT INTO core.place_photo (place_id, seq, file_key, origin, status)
  SELECT p.id, k.ord, k.file_key, 'legacy', 'draft'
  FROM core.place p CROSS JOIN LATERAL unnest(p.photo_keys) WITH ORDINALITY AS k(file_key, ord)
  WHERE k.ord <= 20
  ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------- 8. roads, km posts, route corridors (DATA-04)
-- Road numbers are official designations (federal list, Government Decree No. 928 of 17.11.2010), not OSM data.
CREATE TABLE core.road (
  ref         text PRIMARY KEY CHECK (length(ref) BETWEEN 2 AND 24),       -- 'М-8' (Cyrillic letters)
  name_ru     text NOT NULL CHECK (length(name_ru) BETWEEN 1 AND 80),
  kind        text NOT NULL CHECK (kind IN ('federal','regional','corridor')),   -- corridor = our group of regional roads
  sort        integer NOT NULL DEFAULT 100,
  CONSTRAINT road_federal_ref CHECK (kind <> 'federal' OR ref ~ '^[МРА]-[0-9]{1,3}$')    -- catches a Latin 'M'
);
INSERT INTO core.road (ref, name_ru, kind, sort) VALUES
  ('М-2',  'Крым',      'federal', 10),
  ('М-3',  'Украина',   'federal', 20),
  ('М-4',  'Дон',       'federal', 30),
  ('М-5',  'Урал',      'federal', 40),
  ('М-7',  'Волга',     'federal', 50),
  ('М-8',  'Холмогоры', 'federal', 60),
  ('М-10', 'Россия',    'federal', 70),
  ('М-11', 'Нева',      'federal', 80),
  ('М-12', 'Восток',    'federal', 90),
  ('Р-21', 'Кола',      'federal', 100),
  ('Р-22', 'Каспий',    'federal', 110)
ON CONFLICT (ref) DO NOTHING;

-- Where a place is on a road, as the curator observed it («Лукойл, М-8, 112 км, в сторону Ярославля»).
CREATE TABLE core.place_road (
  place_id   uuid NOT NULL REFERENCES core.place(id) ON DELETE CASCADE,
  road_ref   text NOT NULL REFERENCES core.road(ref) ON UPDATE CASCADE,
  km         numeric(5,1) CHECK (km >= 0),                                 -- roadside km post; NULL = in a town on the road
  direction  text NOT NULL DEFAULT 'unknown' CHECK (direction IN ('both','km_up','km_down','unknown')),
  PRIMARY KEY (place_id, road_ref)                                         -- km_up = carriageway where km posts increase
);
CREATE INDEX place_road_ref_ix ON core.place_road (road_ref, km);

-- Which stretches of which roads a ready route drives (its corridor for the KPI). Entered by `lead`.
CREATE TABLE core.ready_route_road (
  route_id  uuid NOT NULL REFERENCES core.ready_route(id) ON DELETE CASCADE,
  seq       smallint NOT NULL CHECK (seq >= 1),
  road_ref  text NOT NULL REFERENCES core.road(ref) ON UPDATE CASCADE,
  km_from   numeric(5,1) CHECK (km_from >= 0),                             -- NULL with km_to NULL = the whole road
  km_to     numeric(5,1),
  PRIMARY KEY (route_id, seq),
  CONSTRAINT ready_route_road_range CHECK ((km_from IS NULL) = (km_to IS NULL) AND (km_from IS NULL OR km_from <= km_to))
);

-- ---------------------------------------------------------------- 9. core.place: deprecations and new rules
-- verified_by: pseudonymous curator id (FK), never an e-mail. Pre-0002 values are replaced by 'legacy-0001'.
UPDATE core.place SET verified_by = CASE WHEN verified_at IS NULL THEN NULL ELSE 'legacy-0001' END;
ALTER TABLE core.place ADD CONSTRAINT place_verified_by_fkey FOREIGN KEY (verified_by) REFERENCES core.curator(id);

-- source: our place layer has no OSM rows any more ('osm' only ever meant an imported OSM object).
ALTER TABLE core.place DROP CONSTRAINT place_source_check;
ALTER TABLE core.place ADD CONSTRAINT place_source_check CHECK (source IN ('curated','partner'));
ALTER TABLE core.place DROP CONSTRAINT place_live_verified;
ALTER TABLE core.place ADD CONSTRAINT place_live_verified CHECK (status <> 'live' OR (verified_at IS NOT NULL AND verified_by IS NOT NULL));

-- breakfast: NULL = unknown (was NOT NULL DEFAULT true, which made unknown look «included»).
ALTER TABLE core.place ALTER COLUMN breakfast_included DROP DEFAULT;
ALTER TABLE core.place ALTER COLUMN breakfast_included DROP NOT NULL;

-- geom: a draft may wait for our own coordinates instead of borrowing OSM's; a live place must have them.
ALTER TABLE core.place ALTER COLUMN geom DROP NOT NULL;
ALTER TABLE core.place ADD CONSTRAINT place_live_geom CHECK (status <> 'live' OR geom IS NOT NULL);

-- ---------------------------------------------------------------- 10. computed columns and the evidence gate
CREATE FUNCTION core.place_tags_yes(p_id uuid) RETURNS text[] LANGUAGE sql STABLE AS $$
  SELECT COALESCE(array_agg(t.tag ORDER BY t.tag), '{}') FROM core.place_tag t
  WHERE t.place_id = p_id AND t.state = 'yes' AND NOT (t.conditions && core.restrictive_tag_conditions())
$$;
CREATE FUNCTION core.place_photo_keys_live(p_id uuid) RETURNS text[] LANGUAGE sql STABLE AS $$
  SELECT COALESCE(array_agg(ph.file_key ORDER BY ph.seq), '{}') FROM core.place_photo ph
  WHERE ph.place_id = p_id AND ph.status = 'live'
$$;

-- Evidence a curator must record before a place of this type goes live (checklist §1, «О» columns).
-- 'ticket' = ticket_adult_rub, or the tag free_entry. Tags, fuel kinds and roads: see place_missing_evidence.
CREATE FUNCTION core.required_evidence(place_type text) RETURNS text[] LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE place_type
    WHEN 'lodging' THEN ARRAY['name_ru','geom','address','town_id','opening_hours','price_night_rub','breakfast_included','rating_internal']
    WHEN 'food'    THEN ARRAY['name_ru','geom','address','opening_hours','avg_check_rub','rating_internal']
    WHEN 'fuel'    THEN ARRAY['name_ru','geom','opening_hours','fuel','road','rating_internal']
    WHEN 'rest'    THEN ARRAY['name_ru','geom','opening_hours','rating_internal']
    WHEN 'sight'   THEN ARRAY['name_ru','geom','address','opening_hours','dwell_min','ticket','description_ru','rating_internal']
    ELSE ARRAY['name_ru','geom'] END
$$;

-- What is still missing: required properties, plus every tag / fuel kind stated as yes or no, plus every road link.
CREATE FUNCTION core.place_missing_evidence(p_id uuid) RETURNS text[] LANGUAGE sql STABLE AS $$
  SELECT COALESCE(array_agg(m ORDER BY m), '{}') FROM (
    SELECT r AS m FROM core.place p CROSS JOIN LATERAL unnest(core.required_evidence(p.type)) AS r
    WHERE p.id = p_id AND NOT EXISTS (
      SELECT 1 FROM core.evidence e WHERE e.place_id = p.id
        AND (e.property = r OR (r = 'ticket' AND (e.property = 'ticket_adult_rub'
                                                  OR (e.property = 'tag' AND e.qualifier = 'free_entry')))))
    UNION ALL
    SELECT 'tag:' || t.tag FROM core.place_tag t
    WHERE t.place_id = p_id AND t.state IN ('yes','no') AND NOT EXISTS (
      SELECT 1 FROM core.evidence e WHERE e.place_id = p_id AND e.property = 'tag' AND e.qualifier = t.tag)
    UNION ALL
    SELECT 'fuel:' || f.fuel_kind FROM core.place_fuel f
    WHERE f.place_id = p_id AND f.state IN ('yes','no') AND NOT EXISTS (
      SELECT 1 FROM core.evidence e WHERE e.place_id = p_id AND e.property = 'fuel' AND e.qualifier = f.fuel_kind)
    UNION ALL
    SELECT 'road:' || pr.road_ref FROM core.place_road pr
    WHERE pr.place_id = p_id AND NOT EXISTS (
      SELECT 1 FROM core.evidence e WHERE e.place_id = p_id AND e.property = 'road' AND e.qualifier = pr.road_ref)
  ) x
$$;

-- tags, photo_keys, verified_at, verified_by are written only here: direct writes are overwritten.
CREATE FUNCTION core.place_derive() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE last_pass record;
BEGIN
  NEW.tags := core.place_tags_yes(NEW.id);
  NEW.photo_keys := core.place_photo_keys_live(NEW.id);
  SELECT c.checked_at, c.checked_by INTO last_pass FROM core.place_check c
    WHERE c.place_id = NEW.id AND c.result = 'pass' ORDER BY c.checked_at DESC, c.id LIMIT 1;
  NEW.verified_at := last_pass.checked_at;                                 -- NULL when there is no pass
  NEW.verified_by := last_pass.checked_by;
  RETURN NEW;
END $$;
CREATE TRIGGER place_derive BEFORE INSERT OR UPDATE ON core.place FOR EACH ROW EXECUTE FUNCTION core.place_derive();

-- «Факт без доказательства — не факт»: no transition to live, and no curator 'pass', while evidence is missing.
CREATE FUNCTION core.place_live_gate() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE missing text[];
BEGIN
  IF NEW.status = 'live' AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'live') THEN
    missing := core.place_missing_evidence(NEW.id);
    IF cardinality(missing) > 0 THEN
      RAISE EXCEPTION 'ADR-0018: place % cannot go live, evidence missing: %', NEW.id, array_to_string(missing, ', ')
        USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER place_live_gate BEFORE INSERT OR UPDATE OF status ON core.place
  FOR EACH ROW EXECUTE FUNCTION core.place_live_gate();

CREATE FUNCTION core.place_check_gate() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE missing text[];
BEGIN
  IF NEW.result = 'pass' AND NEW.kind IN ('full','recheck','audit') THEN
    missing := core.place_missing_evidence(NEW.place_id);
    IF cardinality(missing) > 0 THEN
      RAISE EXCEPTION 'ADR-0018: check of place % cannot pass, evidence missing: %', NEW.place_id,
        array_to_string(missing, ', ') USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER place_check_gate BEFORE INSERT ON core.place_check FOR EACH ROW EXECUTE FUNCTION core.place_check_gate();

-- A change in a child table recomputes the parent's cached columns (via place_derive).
CREATE FUNCTION core.place_child_changed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE core.place SET updated_at = now() WHERE id IN (NEW.place_id, OLD.place_id);   -- OLD/NEW are NULL when absent
  RETURN NULL;
END $$;
CREATE TRIGGER place_tag_changed   AFTER INSERT OR UPDATE OR DELETE ON core.place_tag
  FOR EACH ROW EXECUTE FUNCTION core.place_child_changed();
CREATE TRIGGER place_photo_changed AFTER INSERT OR UPDATE OR DELETE ON core.place_photo
  FOR EACH ROW EXECUTE FUNCTION core.place_child_changed();
CREATE TRIGGER place_check_changed AFTER INSERT OR UPDATE OR DELETE ON core.place_check
  FOR EACH ROW EXECUTE FUNCTION core.place_child_changed();

-- Bring every cache in line now (legacy photo_keys disappear until licensed; tags and dates are unchanged).
UPDATE core.place SET updated_at = updated_at;

-- New live rules (checklist §2.4, §4): validated for new and edited rows; existing rows are fixed when touched,
-- then `ALTER TABLE core.place VALIDATE CONSTRAINT …` (ADR-0018 §5).
ALTER TABLE core.place ADD CONSTRAINT place_live_hours CHECK (status <> 'live' OR opening_hours IS NOT NULL) NOT VALID;
ALTER TABLE core.place ADD CONSTRAINT place_live_ticket
  CHECK (type <> 'sight' OR status <> 'live' OR ticket_adult_rub IS NOT NULL OR 'free_entry' = ANY (tags)) NOT VALID;

-- ---------------------------------------------------------------- 11. views: curator queues and DATA-04 KPI
CREATE OR REPLACE VIEW core.place_recheck_due AS
  SELECT id, type, name_ru, region_code, verified_at FROM core.place
  WHERE status = 'live' AND verified_at < now() - interval '180 days';

CREATE VIEW core.place_evidence_missing AS
  SELECT p.id, p.type, p.status, p.name_ru, p.region_code, core.place_missing_evidence(p.id) AS missing
  FROM core.place p
  WHERE p.status <> 'hidden' AND cardinality(core.place_missing_evidence(p.id)) > 0;

-- Age buckets (work-plan §6 K4): fresh < 90 d, ageing 90–180 d, stale > 180 d (same edge as place_recheck_due).
CREATE FUNCTION core.verification_age_bucket(verified_at timestamptz, as_of timestamptz) RETURNS text
LANGUAGE sql STABLE AS $$
  SELECT CASE WHEN verified_at IS NULL THEN NULL
              WHEN verified_at < as_of - interval '180 days' THEN 'stale'
              WHEN verified_at < as_of - interval '90 days'  THEN 'ageing'
              ELSE 'fresh' END
$$;

-- A verified place (work-plan §6): live, last pass by a curator or a user/partner (not a pre-0002 record),
-- and no evidence missing.
CREATE VIEW core.place_verified AS
  SELECT p.id AS place_id, p.type, p.town_id, p.region_code, p.verified_at, p.verified_by,
         core.verification_age_bucket(p.verified_at, now()) AS age_bucket
  FROM core.place p
  WHERE p.status = 'live' AND p.verified_at IS NOT NULL AND p.verified_by NOT LIKE 'legacy-%'
    AND cardinality(core.place_missing_evidence(p.id)) = 0;

-- A place belongs to a route if it is a stop, lies in a night/via town of the route, or sits on a road stretch the
-- route drives (core.ready_route_road). The geometric 15 km corridor (work-plan §6 cond. 3) needs ENG-01 lines.
CREATE VIEW core.place_route_membership AS
  SELECT DISTINCT m.route_id, m.place_id FROM (
    SELECT rp.route_id, rp.place_id FROM core.ready_route_point rp WHERE rp.role = 'stop'
    UNION ALL
    SELECT rp.route_id, p.id FROM core.ready_route_point rp JOIN core.place p ON p.town_id = rp.town_id
    WHERE rp.role IN ('night','via')
    UNION ALL
    SELECT rr.route_id, pr.place_id FROM core.ready_route_road rr JOIN core.place_road pr ON pr.road_ref = rr.road_ref
    WHERE rr.km_from IS NULL OR pr.km BETWEEN rr.km_from AND rr.km_to
  ) m;

-- K1 + K4: all verified places, per type and in total (place_type = 'all').
CREATE VIEW core.kpi_verified_total AS
  SELECT CASE WHEN GROUPING(v.type) = 1 THEN 'all' ELSE v.type END AS place_type,
         count(*)                                         AS verified,
         count(*) FILTER (WHERE v.age_bucket = 'fresh')   AS fresh_lt_90d,
         count(*) FILTER (WHERE v.age_bucket = 'ageing')  AS ageing_90_180d,
         count(*) FILTER (WHERE v.age_bucket = 'stale')   AS stale_gt_180d
  FROM core.place_verified v
  GROUP BY ROLLUP (v.type);

-- K2 + K4 per ready route (every route listed, also with 0). A place on two routes counts in both.
CREATE VIEW core.kpi_verified_by_route AS
  SELECT r.id AS route_id, r.slug, r.title_ru, r.status AS route_status,
         CASE WHEN GROUPING(v.type) = 1 THEN 'all' ELSE v.type END AS place_type,
         count(v.place_id)                                AS verified,
         count(*) FILTER (WHERE v.age_bucket = 'fresh')   AS fresh_lt_90d,
         count(*) FILTER (WHERE v.age_bucket = 'ageing')  AS ageing_90_180d,
         count(*) FILTER (WHERE v.age_bucket = 'stale')   AS stale_gt_180d
  FROM core.ready_route r
  LEFT JOIN (core.place_route_membership m JOIN core.place_verified v ON v.place_id = m.place_id)
    ON m.route_id = r.id
  GROUP BY GROUPING SETS ((r.id, r.slug, r.title_ru, r.status), (r.id, r.slug, r.title_ru, r.status, v.type))
  HAVING GROUPING(v.type) = 1 OR v.type IS NOT NULL;

-- K2 + K4 per corridor (road). Places in towns without a road link are counted per route only.
CREATE VIEW core.kpi_verified_by_corridor AS
  SELECT rd.ref AS road_ref, rd.name_ru, rd.kind, rd.sort,
         CASE WHEN GROUPING(v.type) = 1 THEN 'all' ELSE v.type END AS place_type,
         count(v.place_id)                                AS verified,
         count(*) FILTER (WHERE v.age_bucket = 'fresh')   AS fresh_lt_90d,
         count(*) FILTER (WHERE v.age_bucket = 'ageing')  AS ageing_90_180d,
         count(*) FILTER (WHERE v.age_bucket = 'stale')   AS stale_gt_180d
  FROM core.road rd
  LEFT JOIN (core.place_road pr JOIN core.place_verified v ON v.place_id = pr.place_id) ON pr.road_ref = rd.ref
  GROUP BY GROUPING SETS ((rd.ref, rd.name_ru, rd.kind, rd.sort), (rd.ref, rd.name_ru, rd.kind, rd.sort, v.type))
  HAVING GROUPING(v.type) = 1 OR v.type IS NOT NULL;

-- ---------------------------------------------------------------- 12. documentation in the catalog
COMMENT ON TABLE core.curator IS 'ADR-0018: pseudonymous ids of curators and systems; no names, e-mails or phones (152-FZ).';
COMMENT ON TABLE core.place_osm_ref IS 'ADR-0018: optional link of a Verst place to an OSM object, by id only. Never copy OSM values.';
COMMENT ON TABLE core.town_osm_ref IS 'ADR-0018: optional link of a town to an OSM object, by id only.';
COMMENT ON TABLE core.evidence IS 'ADR-0018: one observed fact (property of a place or town), its source and date. Append-only.';
COMMENT ON TABLE core.place_check IS 'ADR-0018: verification log; the latest pass sets core.place.verified_at/verified_by.';
COMMENT ON TABLE core.place_tag IS 'ADR-0018: tag state yes/no/unknown with conditions; core.place.tags = unconditional yes.';
COMMENT ON TABLE core.place_fuel IS 'ADR-0018: fuel kinds sold at a fuel station (yes/no/unknown).';
COMMENT ON TABLE core.place_photo IS 'ADR-0018: photo with origin, author credit and licence; only live rows are shown.';
COMMENT ON TABLE core.road IS 'ADR-0018: roads and corridors for the DATA-04 KPI (official numbers, not OSM).';
COMMENT ON TABLE core.place_road IS 'ADR-0018: a place on a road at a km post, as observed by the curator.';
COMMENT ON TABLE core.ready_route_road IS 'ADR-0018: road stretches a ready route drives (route corridor for the KPI).';
COMMENT ON COLUMN core.place.tags IS 'Computed from core.place_tag (ADR-0018). Read-only in Directus.';
COMMENT ON COLUMN core.place.photo_keys IS 'Computed from live core.place_photo rows (ADR-0018). Read-only in Directus.';
COMMENT ON COLUMN core.place.verified_at IS 'Computed: latest pass in core.place_check (ADR-0018). Read-only in Directus.';
COMMENT ON COLUMN core.place.verified_by IS 'Computed: core.curator id of the latest pass (ADR-0018). Never an e-mail.';
COMMENT ON COLUMN core.place.breakfast_included IS 'NULL = unknown (ADR-0018). Engine adapters must not read NULL as true.';
COMMENT ON COLUMN core.place.source IS 'curated = Verst observation; partner = partner feed under contract. No OSM rows (ADR-0018).';
