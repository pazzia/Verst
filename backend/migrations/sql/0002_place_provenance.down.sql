-- 0002 reverse (Alembic downgrade; architecture §9.4 runs `downgrade -1 && upgrade head` in CI).
-- Lossy by design: evidence, checks, tag states and conditions, fuel kinds, photo licences and roads are dropped.
-- osm_id moves back from *_osm_ref; tags / photo_keys / verified_at keep their last computed values.
-- verified_by keeps the curator id (0001 typed it as free text). Refuses to run if a place has no coordinates.

DO $guard$
BEGIN
  IF EXISTS (SELECT 1 FROM core.place WHERE geom IS NULL) THEN
    RAISE EXCEPTION '0002 down: % places have no coordinates (0001 requires geom NOT NULL); delete or locate them first',
      (SELECT count(*) FROM core.place WHERE geom IS NULL);
  END IF;
END
$guard$;

DROP VIEW core.kpi_verified_by_corridor;
DROP VIEW core.kpi_verified_by_route;
DROP VIEW core.kpi_verified_total;
DROP VIEW core.place_route_membership;
DROP VIEW core.place_verified;
DROP VIEW core.place_evidence_missing;
DROP FUNCTION core.verification_age_bucket(timestamptz, timestamptz);
CREATE OR REPLACE VIEW core.place_recheck_due AS
  SELECT id, type, name_ru, region_code, verified_at FROM core.place
  WHERE status = 'live' AND source <> 'osm' AND verified_at < now() - interval '180 days';

DROP TRIGGER place_tag_changed ON core.place_tag;
DROP TRIGGER place_photo_changed ON core.place_photo;
DROP TRIGGER place_check_changed ON core.place_check;
DROP TRIGGER place_check_gate ON core.place_check;
DROP TRIGGER place_live_gate ON core.place;
DROP TRIGGER place_derive ON core.place;
DROP FUNCTION core.place_child_changed();
DROP FUNCTION core.place_check_gate();
DROP FUNCTION core.place_live_gate();
DROP FUNCTION core.place_derive();
DROP FUNCTION core.place_missing_evidence(uuid);
DROP FUNCTION core.required_evidence(text);
DROP FUNCTION core.place_photo_keys_live(uuid);
DROP FUNCTION core.place_tags_yes(uuid);

ALTER TABLE core.place DROP CONSTRAINT place_live_ticket;
ALTER TABLE core.place DROP CONSTRAINT place_live_hours;
ALTER TABLE core.place DROP CONSTRAINT place_live_geom;
ALTER TABLE core.place ALTER COLUMN geom SET NOT NULL;
UPDATE core.place SET breakfast_included = true WHERE breakfast_included IS NULL;   -- 0001 had no «unknown»
ALTER TABLE core.place ALTER COLUMN breakfast_included SET DEFAULT true;
ALTER TABLE core.place ALTER COLUMN breakfast_included SET NOT NULL;
ALTER TABLE core.place DROP CONSTRAINT place_live_verified;
ALTER TABLE core.place ADD CONSTRAINT place_live_verified CHECK (status <> 'live' OR source = 'osm' OR verified_at IS NOT NULL);
ALTER TABLE core.place DROP CONSTRAINT place_source_check;
ALTER TABLE core.place ADD CONSTRAINT place_source_check CHECK (source IN ('curated','osm','partner'));
ALTER TABLE core.place DROP CONSTRAINT place_verified_by_fkey;

DROP TABLE core.ready_route_road;
DROP TABLE core.place_road;
DROP TABLE core.road;
DROP TABLE core.place_photo;
DROP TABLE core.place_fuel;
ALTER TABLE core.place DROP CONSTRAINT place_id_type_key;
DROP FUNCTION core.fuel_kinds();
DROP TABLE core.place_tag;
DROP FUNCTION core.restrictive_tag_conditions();
DROP FUNCTION core.tag_conditions();
DROP TABLE core.evidence;
DROP TABLE core.place_check;

ALTER TABLE core.place ADD COLUMN osm_id text UNIQUE;
ALTER TABLE core.town  ADD COLUMN osm_id text UNIQUE;
UPDATE core.place p SET osm_id = left(r.osm_type, 1) || r.osm_id FROM core.place_osm_ref r WHERE r.place_id = p.id;
UPDATE core.town t  SET osm_id = left(r.osm_type, 1) || r.osm_id FROM core.town_osm_ref r WHERE r.town_id = t.id;
DROP TABLE core.place_osm_ref;
DROP TABLE core.town_osm_ref;
DROP TABLE core.curator;

COMMENT ON COLUMN core.place.tags IS NULL;
COMMENT ON COLUMN core.place.photo_keys IS NULL;
COMMENT ON COLUMN core.place.verified_at IS NULL;
COMMENT ON COLUMN core.place.verified_by IS NULL;
COMMENT ON COLUMN core.place.breakfast_included IS NULL;
COMMENT ON COLUMN core.place.source IS NULL;
