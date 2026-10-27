"""SPIKE-01 unit tests: provider selection, corridor search, stop choice (no network).

    python3 -m unittest discover -s tools/spike01 -p 'test_*.py'
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dynamic_plan  # noqa: E402
import poi_index  # noqa: E402
from poi_index import Index, Poi  # noqa: E402
from selector import ProviderSelector  # noqa: E402

MANIFEST = json.loads((Path(__file__).resolve().parent / "providers.json").read_text(encoding="utf-8"))


class SelectorTest(unittest.TestCase):
    def test_open_data_is_the_fallback_when_no_vendor_is_licensed(self) -> None:
        sel = ProviderSelector(MANIFEST, env={})
        self.assertEqual(sel.pick("place_search", "RU").provider, "open_index")
        reasons = {c.provider: c.reason for c in sel.chain("place_search", "RU")}
        self.assertEqual(reasons["yandex_geosearch"], "needs a ru legal entity")
        self.assertNotIn("google_places", reasons)  # excluded in RU: no billing for Russian companies

    def test_a_licensed_configured_vendor_wins_by_country_priority(self) -> None:
        m = json.loads(json.dumps(MANIFEST))
        m["deployment"]["entities"] = ["ru"]
        sel = ProviderSelector(m, env={"SPIKE_YANDEX_GEOSEARCH_KEY": "k"})
        self.assertEqual(sel.pick("place_search", "RU").provider, "yandex_geosearch")
        sel.unhealthy.add("yandex_geosearch")
        self.assertEqual(sel.pick("place_search", "RU").provider, "open_index")

    def test_budget_cap_drops_a_vendor(self) -> None:
        m = json.loads(json.dumps(MANIFEST))
        m["deployment"]["entities"] = ["foreign"]
        sel = ProviderSelector(m, env={"SPIKE_GOOGLE_PLACES_KEY": "k"}, budgets_rub={"google_places": 1000})
        self.assertEqual(sel.pick("place_details", "ID").provider, "google_places")
        sel.spent_rub["google_places"] = 1000
        self.assertEqual(sel.pick("place_details", "ID").provider, "open_index")

    def test_routing_is_configured_per_country(self) -> None:
        sel = ProviderSelector(MANIFEST, env={"SPIKE_GH_URL_ID": "http://127.0.0.1:8990"})
        self.assertEqual(sel.pick("routing", "ID").provider, "graphhopper_osm")
        with self.assertRaises(LookupError):
            sel.pick("routing", "RU")

    def test_cost_simulation_prices_the_best_vendor_ignoring_licences(self) -> None:
        sel = ProviderSelector(MANIFEST, env={})
        self.assertEqual(sel.would_pick_if_licensed("place_search", "RU")["id"], "yandex_geosearch")
        self.assertEqual(sel.would_pick_if_licensed("place_search", "ID")["id"], "google_places")
        g = sel.provider("google_places")
        self.assertAlmostEqual(sel.call_cost_rub(g, "search", 1000), 0.032 * 85 * 1000)


class IndexTest(unittest.TestCase):
    def test_classify_skips_ordinary_churches_and_keeps_notable_ones(self) -> None:
        self.assertIsNone(poi_index.classify({"amenity": "place_of_worship"}))
        self.assertEqual(poi_index.classify({"amenity": "place_of_worship", "wikidata": "Q1"}), "temple")
        self.assertEqual(poi_index.classify({"tourism": "museum"}), "museum")
        self.assertEqual(poi_index.classify({"natural": "waterfall"}), "waterfall")

    def test_build_reads_geojsonseq_with_any_geometry(self) -> None:
        lines = [
            json.dumps({"type": "Feature", "id": "n1", "geometry": {"type": "Point", "coordinates": [37.0, 55.0]},
                        "properties": {"tourism": "museum", "name": "Музей", "opening_hours": "10:00-18:00"}}),
            json.dumps({"type": "Feature", "id": "w2", "geometry": {"type": "Polygon", "coordinates": [[[37.0, 55.0], [37.2, 55.0], [37.2, 55.2], [37.0, 55.0]]]},
                        "properties": {"natural": "beach", "name": "Пляж", "dog": "no"}}),
            json.dumps({"type": "Feature", "id": "n3", "geometry": {"type": "Point", "coordinates": [37.0, 55.0]},
                        "properties": {"tourism": "museum"}}),  # no name
        ]
        pois = list(poi_index.build(lines, "ru"))
        self.assertEqual([p.name for p in pois], ["Музей", "Пляж"])
        self.assertEqual(pois[0].hours, "10:00-18:00")
        self.assertEqual(pois[1].dog, "no")

    def test_corridor_finds_places_near_the_line_with_their_km(self) -> None:
        line = [(55.0, 37.0 + i * 0.01) for i in range(101)]  # ~64 km east
        idx = Index([
            Poi("a", "near", "museum", 55.02, 37.30),   # ~2.2 km off, ~19 km along
            Poi("b", "far", "museum", 55.30, 37.30),    # ~33 km off
            Poi("c", "end", "zoo", 55.0, 37.99),
        ])
        hits = idx.corridor(line, 10)
        self.assertEqual([h.poi.id for h in hits], ["a", "c"])
        self.assertAlmostEqual(hits[0].km_at, 19.2, delta=0.5)
        self.assertAlmostEqual(hits[0].lateral_km, 2.2, delta=0.1)


class ChooseTest(unittest.TestCase):
    def profile(self, **kw: object) -> dict:
        p = {"crew": {"adults": 2, "children": [7], "pets": None}, "dailyKm": 500, "level": "comfort",
             "density": 2, "interests": {"history": 1.0, "kids": 1.0, "religion": 0.3}}
        p.update(kw)
        return p

    def hits(self) -> list:
        mk = lambda i, kind, km, sl=10, dog=None: poi_index.Hit(Poi(i, i, kind, 0, 0, "Q1", sl, None, dog), km, 1.0)  # noqa: E731
        return [mk("t1", "temple", 50), mk("t2", "temple", 100), mk("t3", "temple", 150),
                mk("m1", "museum", 200, 2), mk("z1", "zoo", 300, 30, "no")]

    def test_religious_cap_and_spacing(self) -> None:
        chosen, stats = dynamic_plan.choose(self.hits(), self.profile(density=3), 400)
        kinds = [c["kind"] for c in chosen]
        self.assertEqual(stats["days"], 1)
        self.assertEqual(kinds.count("temple"), 1)
        self.assertIn("zoo", kinds)

    def test_one_stop_per_kind_a_day_when_there_is_a_choice(self) -> None:
        mk = lambda i, kind, km: poi_index.Hit(Poi(i, i, kind, 0, 0, "Q1", 30), km, 1.0)  # noqa: E731
        hits = [mk("z1", "zoo", 10), mk("z2", "zoo", 200), mk("m1", "museum", 300)]
        chosen, _ = dynamic_plan.choose(hits, self.profile(density=2), 400)
        self.assertEqual(sorted(c["kind"] for c in chosen), ["museum", "zoo"])

    def test_dog_bans_exclude_and_unknown_is_flagged(self) -> None:
        p = self.profile(crew={"adults": 2, "children": [], "pets": {"dog": "medium"}})
        chosen, stats = dynamic_plan.choose(self.hits(), p, 400)
        self.assertNotIn("zoo", [c["kind"] for c in chosen])
        self.assertEqual(stats["excluded"].get("dogs not allowed"), 1)
        self.assertTrue(all(c["note"] == "dog policy not verified" for c in chosen))


if __name__ == "__main__":
    unittest.main()
