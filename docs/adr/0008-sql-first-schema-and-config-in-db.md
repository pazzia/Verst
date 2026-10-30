# ADR-0008: SQL-first schema with PostGIS constraints; tunables and copy in `core.app_config`

Status: Accepted · Date: 2026-10-23 · Refs: SPEC §7.3, §7.5, §9, §10; architecture §5.4, §8.1, §9

## Context
Two writers (Directus and the API) share one database, curated data quality is the product's moat, and SPEC requires engine coefficients and reason templates to be configuration, not code.

## Decision
- The schema is written as plain SQL (`migrations/sql/NNNN_*.sql`) executed by Alembic revisions; invariants are enforced in the DB (CHECK on the closed tag list, live ⇒ verified, lodging price; triggers for lodging counts and auto-hide after 2 `closed` reports). Spatial queries use `geography` GiST indexes.
- Planner coefficients, reason templates, partner link templates, navigator deep-link templates, feature flags and Russian error copy live in `core.app_config` (jsonb rows), editable by the `lead` role in Directus; defaults ship in `verst_planner/resources/*.json` and are validated on load (unknown keys rejected).

## Consequences
- Data stays valid regardless of which tool writes it; tuning the overnight score or reasons needs no release.
- A bad config edit could change plans globally — mitigated by validation on save (API refuses to load an invalid config and keeps the last good one) and by golden trips run against the production config in staging.

## Alternatives
- ORM-generated migrations (autogenerate) — weak for PostGIS functional indexes and triggers.
- Config in environment/YAML files — requires deploys for tuning.
