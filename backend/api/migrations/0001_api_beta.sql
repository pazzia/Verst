-- verst-api beta runtime schema (ENG-04, ADR-0020 §5). PostgreSQL 16, no extensions (gen_random_uuid is core).
--
-- Why a schema `api` and not `app` of backend/migrations/sql/0001_initial.sql: `app.*` references core.place /
-- core.ready_route by uuid and needs PostGIS; the beta engine reads the packaged catalogue whose ids are text
-- ("Q123", "osm_n1", "pl_…"), and the Place DB (ADR-0018) is not live yet. `app.*` stays the target once places
-- come from PostgreSQL (ADR-0020 §10).
--
-- R-07: no table holds an exact coordinate, a typed label, an IP address or a device identifier other than our
-- own random id. `trip.trip` is the privacy-reduced trip (verst_api.privacy.scrub_trip).

CREATE SCHEMA IF NOT EXISTS api;

CREATE TABLE api.device (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  token_hash    bytea NOT NULL UNIQUE CHECK (octet_length(token_hash) = 32),   -- sha256(token), ADR-0007
  app_version   text NOT NULL CHECK (length(app_version) BETWEEN 1 AND 32),
  locale        text NOT NULL DEFAULT 'ru-RU' CHECK (length(locale) BETWEEN 2 AND 16),
  created_at    timestamptz NOT NULL DEFAULT now(),
  last_seen_at  timestamptz NOT NULL DEFAULT now(),                           -- refreshed at most hourly
  revoked_at    timestamptz
);

CREATE TABLE api.trip (
  id              text PRIMARY KEY CHECK (id ~ '^trp_[0-9a-hjkmnp-tv-z]{12}$'),
  device_id       uuid NOT NULL REFERENCES api.device(id) ON DELETE CASCADE,
  content_hash    bytea NOT NULL CHECK (octet_length(content_hash) = 32),    -- sha256 of the stored trip
  share_slug      text NOT NULL UNIQUE CHECK (share_slug ~ '^[0-9a-hjkmnp-tv-z]{8}$'),
  title           text NOT NULL CHECK (length(title) BETWEEN 1 AND 300),
  start_town      text NOT NULL CHECK (length(start_town) BETWEEN 1 AND 120),
  km              integer NOT NULL CHECK (km >= 0),
  days            smallint NOT NULL CHECK (days >= 1),
  synthetic       boolean NOT NULL,                                          -- approxDistances (road model)
  engine_version  text NOT NULL CHECK (length(engine_version) <= 32),
  trip            jsonb NOT NULL,
  share_text      text NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (device_id, content_hash)                                           -- saving twice = one link
);
CREATE INDEX trip_device_ix ON api.trip (device_id, created_at DESC);

CREATE TABLE api.feedback (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id    uuid NOT NULL REFERENCES api.device(id) ON DELETE CASCADE,
  trip_id      text REFERENCES api.trip(id) ON DELETE SET NULL,
  place_id     text CHECK (length(place_id) BETWEEN 1 AND 64),               -- catalogue / fixture place id
  kind         text NOT NULL CHECK (kind IN ('closed','wrong_tag','price','other')),
  text         text CHECK (length(text) <= 1000),                            -- contacts masked; cleared after
  app_version  text CHECK (length(app_version) <= 32),                       --   VERST_FEEDBACK_TEXT_DAYS
  created_at   timestamptz NOT NULL DEFAULT now(),
  resolved_at  timestamptz
);
CREATE INDEX feedback_open_ix ON api.feedback (place_id, kind) WHERE resolved_at IS NULL;

-- Fixed-window rate-limit counters (ADR-0020 §6). `key` = bucket + ':' + device id or HMAC(IP); rows are
-- deleted two days after their window.
CREATE TABLE api.rate_counter (
  key           text NOT NULL CHECK (length(key) <= 80),
  window_start  timestamptz NOT NULL,
  hits          integer NOT NULL CHECK (hits >= 1),
  PRIMARY KEY (key, window_start)
);
CREATE INDEX rate_counter_window_ix ON api.rate_counter (window_start);
