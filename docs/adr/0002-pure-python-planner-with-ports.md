# ADR-0002: Planner as a pure-Python package with ports and fake adapters

Status: Accepted · Date: 2026-10-23 · Refs: SPEC §7, §8, §11, §17; architecture §3–§7, §13

## Context
The route engine is the product's core and must be deterministic and explainable (SPEC §7). It needs routing, place, price and toll data, but those services are not available in the current sandbox (package registries blocked, no map services). Tests (unit ≥ 85 %, 20 golden trips) must run fast in CI and here, now.

## Decision
`backend/planner` is the package `verst_planner` with **zero third-party dependencies** (stdlib only, Python ≥ 3.12, verified on 3.13). It defines:
- domain types as frozen stdlib dataclasses and `StrEnum`s;
- ports as `typing.Protocol`: `RoutingPort`, `GeocodingPort`, `PlaceRepository`, `PriceRepository`, `TollRepository`, `RegionLocator`, `Clock`;
- the 13-stage pipeline as pure functions, a `Planner` facade, `ProgressSink` / `CancelToken` for streaming and cancellation;
- in-repo fake adapters driven by JSON "world" fixtures (synthetic road graphs for Central Russia and edge cases).
Tests use stdlib `unittest`; an AST-based test forbids non-stdlib imports. Real adapters (GraphHopper, Photon, PostGIS) live in `verst_api.adapters`.

## Consequences
- The complete engine, cost model and golden trips are built and verified in Sprint 1 without network access.
- The API is a thin shell; switching routing provider is an adapter change.
- No pydantic in the engine means a small hand-written codec (`domain/codec.py`) and a contract test that the API's pydantic schemas accept every golden snapshot.
- Ports are synchronous; the API runs the planner in a worker thread (fine: planner CPU < 300 ms, I/O bounded by timeouts).
- Fake worlds must be curated with care (plausible distances ±5 %) — golden numbers are only as good as the fixtures; nightly real-mode runs report drift.

## Alternatives
- **Engine inside FastAPI services with SQLAlchemy queries** — untestable here, couples planning to I/O.
- **pydantic models in the engine** — pydantic is available, but it would be the only dependency and makes the engine harder to embed (e.g., batch tools); kept at the API boundary.
- **pytest** — preferred tooling (SPEC §17) but not installable now; `unittest` tests run under pytest unchanged later.
