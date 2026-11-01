"""Trips abroad, wave 1 (CEO 29.10): the server-only world `world_v1` = `russia_v1` + the catalogues abroad.

The phone never loads this world (the APK has no `backend/planner/abroad/`); the code ships with the package
but runs only when the server calls `mobile.load_abroad`. Modules:

* `rules` — the curated tables `resources/abroad_rules.json` and `resources/border_crossings.json`, copied
  from `docs/plan/abroad-wave1-sources.md` (every fact with its URL, all «не проверено»);
* `catalogues` — the per-country catalogues `abroad/<cc>/catalogue_*.json.gz` read from a directory;
* `locator` — which supported country a point is in (the nearest catalogue town within 60 km; Crimea is
  Russia);
* `routing` — Russian legs keep the world's routing, a leg that touches abroad is the road model;
* `world` — the composed world, its ports and the `BorderPort` (point checks, crossings);
* `money` — fuel and fees abroad in the local currency, converted with the Bank of Russia rate if present;
* `planner` — `AbroadPlanner`: a trip inside Russia goes to the Russian planner unchanged, a trip abroad is
  planned with border stops and the `abroad` block.
"""
