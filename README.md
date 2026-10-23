# Verst («Верста»)

Verst is an Android road-trip planner for Russia. It builds a multi-day car trip from any A to any B, or picks a ready-made trip near the start. It places overnight stops by the driver's daily mileage, shifting each one to the best nearby town, and shows the full cost with formulas. The UI is Russian-only. Code and docs are in English.

## Repository

| Path | What |
| --- | --- |
| `docs/SPEC.md` | Approved MVP specification (behaviour source of truth) |
| `docs/design-canvas/` | Approved UI design v5 «За рулём» (7 screens, HTML mockups) |
| `docs/architecture.md` | Architecture: containers, planner design and algorithms, DB schema, API, Android, infra, testing |
| `docs/adr/` | Architecture decision records |
| `docs/backlog-sprint1.md` | Sprint 1 tasks with acceptance criteria |
| `backend/planner/` | `verst_planner`: the pure-Python route and cost engine (stdlib only), fake adapters, fixture worlds, golden trips |
| `backend/api/` | FastAPI service (Sprint 2, needs package registry access) |
| `backend/migrations/` | PostgreSQL 16 + PostGIS schema (SQL-first, Alembic) |
| `android/` | Kotlin + Jetpack Compose app (needs Gradle/Android SDK access) |
| `infra/`, `admin/` | Docker Compose, nginx, map-service build scripts; Directus admin config |

## Requirements

- Python 3.12+. That is all the planner needs: it has no third-party dependencies.
- Optional: `ruff` and `mypy` for linting and type checks.
- The API, database, map services and Android app need network access to package registries. See `docs/architecture.md` §14 for what can be built now and what needs that access.

## Run the tests

```sh
# all planner tests (unit, contract, golden trips, layering)
cd backend/planner && python3 -m unittest discover -v

# the same from the repo root
python3 -m unittest discover -s backend/planner -t backend/planner

# golden trips only
cd backend/planner && python3 -m unittest tests.golden.test_golden -v

# lint, types, tests, coverage (≥ 85 %)
make check
make coverage-planner
```

Regenerate golden snapshots after an intended engine change, then review the diff before committing:

```sh
make golden-update
```

## Plan a trip from the command line

```sh
cd backend/planner
python3 -m verst_planner.cli plan \
  --world fixtures/worlds/central_russia_v1.json \
  --input tests/golden/cases/G02_golden_ring.json --events
```

This prints the plan JSON in the API response shape. With `--events`, it also writes progress events to stderr, one JSON line per event.
