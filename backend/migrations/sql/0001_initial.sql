CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS app;

-- Closed tag list (SPEC §9) as an immutable function so CHECK constraints stay readable
CREATE FUNCTION core.allowed_tags() RETURNS text[] LANGUAGE sql IMMUTABLE AS $$
  SELECT ARRAY['dogs_allowed','kids_menu','playground','family_room','parking','parking_guarded','ev_charger',
               'wc','cafe_at_fuel','24h','view','walk','museum','kremlin','monastery','evening','free_entry','cash_only']
$$;

CREATE FUNCTION core.touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at := now(); RETURN NEW; END $$;

-- Regions (federal subjects): fuel price key + time zone for local times
CREATE TABLE core.region (
  code        text PRIMARY KEY CHECK (code ~ '^RU(-[A-Z]{2,3})?$'),        -- ISO 3166-2:RU; 'RU' = national fallback
  name_ru     text NOT NULL,
  tz          text NOT NULL DEFAULT 'Europe/Moscow',                       -- IANA
  geom        geometry(MultiPolygon, 4326),                                -- NULL only for 'RU'
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX region_geom_gix ON core.region USING gist (geom);

CREATE TABLE core.town (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name_ru              text NOT NULL CHECK (length(name_ru) BETWEEN 1 AND 120),
  name_prep_ru         text,                                               -- «в Ярославле» form, for reasons
  geom                 geometry(Point, 4326) NOT NULL,
  region_code          text NOT NULL REFERENCES core.region(code),
  population           integer NOT NULL DEFAULT 0 CHECK (population >= 0),
  quality              smallint NOT NULL DEFAULT 0 CHECK (quality BETWEEN 0 AND 3),
  evening_walk         boolean NOT NULL DEFAULT false,
  lodging_count_cache  integer NOT NULL DEFAULT 0,
  osm_id               text UNIQUE,
  status               text NOT NULL DEFAULT 'live' CHECK (status IN ('draft','live','hidden')),
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX town_geom_gix  ON core.town USING gist (geom);
CREATE INDEX town_geog_gix  ON core.town USING gist ((geom::geography));
CREATE INDEX town_region_ix ON core.town (region_code);

CREATE TABLE core.place (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  type               text NOT NULL CHECK (type IN ('sight','food','fuel','rest','lodging','town')),
  name_ru            text NOT NULL CHECK (length(name_ru) BETWEEN 1 AND 160),
  geom               geometry(Point, 4326) NOT NULL,
  address            text,
  region_code        text NOT NULL REFERENCES core.region(code),
  town_id            uuid REFERENCES core.town(id) ON DELETE SET NULL,
  opening_hours      text,                                                 -- OSM syntax subset (§6.9)
  dwell_min          smallint CHECK (dwell_min BETWEEN 5 AND 480),
  avg_check_rub      integer CHECK (avg_check_rub >= 0),
  price_night_rub    integer CHECK (price_night_rub >= 0),                 -- per room per night
  breakfast_included boolean NOT NULL DEFAULT true,
  ticket_adult_rub   integer CHECK (ticket_adult_rub >= 0),
  ticket_child_rub   integer CHECK (ticket_child_rub >= 0),
  rating_internal    numeric(2,1) NOT NULL DEFAULT 3.0 CHECK (rating_internal BETWEEN 0 AND 5),
  tags               text[] NOT NULL DEFAULT '{}' CHECK (tags <@ core.allowed_tags()),
  description_ru     text CHECK (length(description_ru) <= 280),
  photo_keys         text[] NOT NULL DEFAULT '{}',
  yandex_travel_id   text,
  tripster_id        text,
  source             text NOT NULL CHECK (source IN ('curated','osm','partner')),
  osm_id             text UNIQUE,                                          -- 'n123' / 'w456'; import idempotency
  sponsored          boolean NOT NULL DEFAULT false,                       -- SPEC §14, always false in MVP
  verified_at        timestamptz,
  verified_by        text,                                                 -- Directus user email/id, curator only
  status             text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','live','hidden')),
  hidden_reason      text CHECK (hidden_reason IN ('feedback_closed','curator','duplicate')),
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT place_lodging_price CHECK (type <> 'lodging' OR status <> 'live' OR price_night_rub IS NOT NULL),
  CONSTRAINT place_live_verified CHECK (status <> 'live' OR source = 'osm' OR verified_at IS NOT NULL)
);
CREATE INDEX place_geom_gix      ON core.place USING gist (geom);
CREATE INDEX place_geog_live_gix ON core.place USING gist ((geom::geography)) WHERE status = 'live';
CREATE INDEX place_type_live_ix  ON core.place (type) WHERE status = 'live';
CREATE INDEX place_town_ix       ON core.place (town_id) WHERE type = 'lodging';
CREATE INDEX place_tags_gin      ON core.place USING gin (tags);
CREATE INDEX place_recheck_ix    ON core.place (verified_at) WHERE status = 'live';
CREATE TRIGGER place_touch BEFORE UPDATE ON core.place FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();
CREATE TRIGGER town_touch  BEFORE UPDATE ON core.town  FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();

-- lodging_count_cache maintenance
CREATE FUNCTION core.refresh_lodging_count() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE core.town t SET lodging_count_cache =
    (SELECT count(*) FROM core.place p WHERE p.town_id = t.id AND p.type = 'lodging' AND p.status = 'live')
  WHERE t.id IN (COALESCE(NEW.town_id, OLD.town_id), COALESCE(OLD.town_id, NEW.town_id));
  RETURN NULL;
END $$;
CREATE TRIGGER place_lodging_count AFTER INSERT OR UPDATE OF town_id, status, type OR DELETE ON core.place
  FOR EACH ROW EXECUTE FUNCTION core.refresh_lodging_count();

CREATE TABLE core.ready_route (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug          text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9-]{3,40}$'),   -- 'golden-ring'
  hub_town_id   uuid NOT NULL REFERENCES core.town(id),
  title_ru      text NOT NULL,
  subtitle_ru   text NOT NULL DEFAULT '',                                   -- «3 дня · 8 городов · по кругу»
  km_total      integer NOT NULL CHECK (km_total > 0),                      -- whole trip
  km_sign       integer NOT NULL CHECK (km_sign > 0),                       -- shown on the overhead sign (SPEC §7.6)
  ring          text NOT NULL CHECK (ring IN ('weekend','long')),
  round_trip    boolean NOT NULL DEFAULT true,
  days_min      smallint NOT NULL CHECK (days_min BETWEEN 1 AND 14),
  days_max      smallint NOT NULL CHECK (days_max BETWEEN 1 AND 14),
  tags          text[] NOT NULL DEFAULT '{}',
  cover_key     text,
  sort          integer NOT NULL DEFAULT 100,
  status        text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','live','hidden')),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CHECK (days_min <= days_max)
);
CREATE INDEX ready_route_hub_ix ON core.ready_route (hub_town_id) WHERE status = 'live';

-- SPEC "points (ordered place/town ids)" and "suggested_nights[]" normalised for FK integrity
CREATE TABLE core.ready_route_point (
  route_id   uuid NOT NULL REFERENCES core.ready_route(id) ON DELETE CASCADE,
  seq        smallint NOT NULL CHECK (seq >= 1),
  role       text NOT NULL CHECK (role IN ('via','stop','night')),
  town_id    uuid REFERENCES core.town(id),
  place_id   uuid REFERENCES core.place(id),
  PRIMARY KEY (route_id, seq),
  CHECK ((role = 'stop' AND place_id IS NOT NULL) OR (role IN ('via','night') AND town_id IS NOT NULL))
);

CREATE TABLE core.region_price (
  region_code  text NOT NULL REFERENCES core.region(code),
  fuel_type    text NOT NULL CHECK (fuel_type IN ('ai92','ai95','dt')),
  as_of        date NOT NULL,
  price_rub    numeric(6,2) NOT NULL CHECK (price_rub > 0 AND price_rub < 1000),
  source_note  text,
  PRIMARY KEY (region_code, fuel_type, as_of)
);

CREATE TABLE core.toll_segment (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  road_ref         text NOT NULL,                                          -- 'М-11'
  name_ru          text NOT NULL,                                          -- 'М-11, км 15–58'
  geom             geometry(LineString, 4326) NOT NULL,
  tariff_day_rub   numeric(8,2) NOT NULL CHECK (tariff_day_rub >= 0),
  tariff_night_rub numeric(8,2) NOT NULL CHECK (tariff_night_rub >= 0),
  night_from       time NOT NULL DEFAULT '00:00',
  night_to         time NOT NULL DEFAULT '06:00',
  vehicle_class    smallint NOT NULL DEFAULT 1 CHECK (vehicle_class BETWEEN 1 AND 4),
  as_of            date NOT NULL,
  status           text NOT NULL DEFAULT 'live' CHECK (status IN ('draft','live','hidden')),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX toll_segment_geog_gix ON core.toll_segment USING gist ((geom::geography)) WHERE status = 'live';

CREATE TABLE core.app_config (
  key         text PRIMARY KEY CHECK (key IN ('planner','reasons_ru','links','navigator_links','features',
                                               'min_app_version','copy_ru')),
  value       jsonb NOT NULL,
  updated_at  timestamptz NOT NULL DEFAULT now(),
  updated_by  text
);

-- ---------- runtime ----------
CREATE TABLE app.device (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  token_hash    bytea NOT NULL UNIQUE,                                     -- sha256(token)
  created_at    timestamptz NOT NULL DEFAULT now(),
  app_version   text NOT NULL CHECK (length(app_version) <= 32),
  locale        text NOT NULL DEFAULT 'ru-RU' CHECK (length(locale) <= 16),
  last_seen_at  timestamptz NOT NULL DEFAULT now(),
  revoked_at    timestamptz
);

CREATE TABLE app.trip (
  id              text PRIMARY KEY CHECK (id ~ '^trp_[0-9a-hjkmnp-tv-z]{12}$'),
  device_id       uuid NOT NULL REFERENCES app.device(id) ON DELETE CASCADE,
  input           jsonb NOT NULL,                                          -- normalised TripInput (camelCase)
  result          jsonb NOT NULL,                                          -- PlanResponse body (days, stops, cost, reasons)
  engine_state    jsonb NOT NULL,                                          -- EngineState, server-only
  engine_version  text NOT NULL,
  title_ru        text NOT NULL,
  km              integer NOT NULL,
  days            smallint NOT NULL,
  ready_route_id  uuid REFERENCES core.ready_route(id) ON DELETE SET NULL,
  has_warnings    boolean NOT NULL DEFAULT false,
  saved           boolean NOT NULL DEFAULT false,
  saved_at        timestamptz,
  share_slug      text UNIQUE CHECK (share_slug ~ '^[0-9a-hjkmnp-tv-z]{8}$'),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  CHECK (NOT saved OR (saved_at IS NOT NULL AND share_slug IS NOT NULL))
);
CREATE INDEX trip_device_ix  ON app.trip (device_id, created_at DESC);
CREATE INDEX trip_cleanup_ix ON app.trip (created_at) WHERE NOT saved;

CREATE TABLE app.trip_stop (
  trip_id       text NOT NULL REFERENCES app.trip(id) ON DELETE CASCADE,
  seq           smallint NOT NULL CHECK (seq >= 1),
  stop_id       text NOT NULL CHECK (stop_id ~ '^d[0-9]{1,2}s[0-9]{2}$'),
  day           smallint NOT NULL CHECK (day >= 1),
  place_id      uuid REFERENCES core.place(id) ON DELETE SET NULL,
  town_id       uuid REFERENCES core.town(id) ON DELETE SET NULL,
  kind          text NOT NULL CHECK (kind IN ('start','sight','food','fuel','rest','overnight','via','finish')),
  arrive_at     timestamp,                                                 -- local wall time of the stop
  depart_at     timestamp,
  tz            text NOT NULL,
  km_from_prev  integer NOT NULL CHECK (km_from_prev >= 0),
  km_at         integer NOT NULL CHECK (km_at >= 0),
  cost_rub      integer NOT NULL DEFAULT 0,
  reason_ru     text NOT NULL DEFAULT '',
  alternatives  jsonb NOT NULL DEFAULT '[]',
  PRIMARY KEY (trip_id, seq),
  UNIQUE (trip_id, stop_id)
);
CREATE INDEX trip_stop_place_ix ON app.trip_stop (place_id);

CREATE TABLE app.feedback (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id   uuid NOT NULL REFERENCES app.device(id) ON DELETE CASCADE,
  trip_id     text REFERENCES app.trip(id) ON DELETE SET NULL,
  place_id    uuid REFERENCES core.place(id) ON DELETE CASCADE,
  kind        text NOT NULL CHECK (kind IN ('closed','wrong_tag','price','other')),
  text        text CHECK (length(text) <= 1000),
  created_at  timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz
);
CREATE INDEX feedback_place_ix ON app.feedback (place_id, kind) WHERE resolved_at IS NULL;

-- SPEC §9 curation rule 3: hide a place after 2 'closed' reports (distinct devices) since its last verification
CREATE FUNCTION app.feedback_autohide() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  IF NEW.kind = 'closed' AND NEW.place_id IS NOT NULL THEN
    UPDATE core.place p SET status = 'hidden', hidden_reason = 'feedback_closed'
    WHERE p.id = NEW.place_id AND p.status = 'live'
      AND (SELECT count(DISTINCT f.device_id) FROM app.feedback f
           WHERE f.place_id = NEW.place_id AND f.kind = 'closed' AND f.resolved_at IS NULL
             AND f.created_at > COALESCE(p.verified_at, '-infinity')) >= 2;
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER feedback_autohide AFTER INSERT ON app.feedback FOR EACH ROW EXECUTE FUNCTION app.feedback_autohide();

CREATE TABLE app.pro_waitlist (
  device_id   uuid NOT NULL REFERENCES app.device(id) ON DELETE CASCADE,
  source      text NOT NULL CHECK (source IN ('waybill','settings','other')),
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (device_id)
);

-- Curator views (Directus): places due for re-check (SPEC §9 rule 3)
CREATE VIEW core.place_recheck_due AS
  SELECT id, type, name_ru, region_code, verified_at FROM core.place
  WHERE status = 'live' AND source <> 'osm' AND verified_at < now() - interval '180 days';
