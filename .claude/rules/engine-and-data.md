---
paths:
  - "backend/planner/**"
  - "tools/data/**"
  - "data/**"
---

# Engine and data rules

- **Never invent data** (ADR-0019, CEO).
  - A missing fact stays missing: `None` / `noData`, shown as «нет данных», counted as unknown, never as
    free, open or a default.
  - An estimate is marked as an estimate (`verified: false`, `approx…`).
- **Sources.** Every external number (tolls, prices, rates, border rules) carries a source URL and the date it
  was seen. Unconfirmed facts are marked "unverified".
- **Licences.** OSM data is ODbL (share-alike, attribution in the catalogue README); Wikidata is CC0; Wikipedia
  extracts are CC BY-SA with a link; Commons photos only with free licences (no GFDL-only).
- **Pure standard library** in `verst_planner` (it runs on the phone through Chaquopy).
- **Checks:** `make check` (ruff 110, `mypy --strict`, unittest). When engine output changes, regenerate
  contracts (`cd backend/planner && python3 tools/gen_api_contracts.py`) and goldens only on purpose
  (`make golden-update`).
- **Data builds** run in GitHub Actions (the sandbox cannot reach OSM, Wikidata or Geofabrik).
  - Publish to orphan `bot/*` branches.
  - Never commit raw extracts or PBF files.
