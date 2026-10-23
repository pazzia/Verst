# ADR-0005: Directus as the curator admin on the same PostgreSQL

Status: Accepted · Date: 2026-10-23 · Refs: SPEC §9, §11, §14; architecture §9.1, §9.5

## Context
Curators (CEO + possibly one hire, part-time) must add and verify places, towns, ready routes, fuel prices and toll tariffs, with a map for geometry, roles, and an audit of who verified what. Building a custom admin would consume weeks of the 12-week plan.

## Decision
Run Directus 11 against the production database with its own role `directus`, its system tables in schema `directus`, CRUD rights on `core.*` curated tables and read rights on `app.feedback` / `app.pro_waitlist`. DDL is owned by Alembic; Directus only registers existing tables (`admin/directus/snapshot.yaml`). Business invariants (tag list, live ⇒ verified, lodging price) are enforced by DB CHECK constraints and triggers, not by Directus. A Directus flow stamps `verified_at/verified_by` on `status → live`. Roles: `curator`, `lead`, `viewer`.

## Consequences
- Admin available in days with map interfaces for points/lines.
- Two writers to `core`: the API never writes curated tables; Directus never touches `app` runtime tables except feedback resolution.
- Directus upgrades must be tested on staging; schema snapshot kept in git.
- Cache invalidation: the API caches config 60 s and fuel prices 10 min, acceptable for curator edits.

## Alternatives
- **Custom admin (FastAPI + React)** — full control, too expensive for MVP.
- **Django admin** — would add a second Python framework and ORM models duplicating the schema.
- **Strapi / NocoDB / Retool** — weaker PostGIS support or SaaS hosting outside Russia.
