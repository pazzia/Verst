"""ADR-0014: hand-off point selection and link strings (ARCH-306)."""

from __future__ import annotations

import unittest
from typing import Any

from verst_planner import handoff as h


def stop(i: int, kind: str, lat: float, lon: float) -> dict[str, Any]:
    return {"id": f"d1s{i:02d}", "kind": kind, "name": f"{kind}{i}", "lat": lat, "lon": lon}


def trip(n_sights: int) -> dict[str, Any]:
    stops = [stop(1, "start", 55.0, 37.0)]
    for i in range(n_sights):
        stops.append(stop(2 + 2 * i, "sight", 55.1 + i / 100, 37.1))
        stops.append(stop(3 + 2 * i, "fuel" if i % 2 else "rest", 55.1 + i / 100, 37.2))
    stops.append(stop(99, "overnight", 56.0, 38.0))
    return {
        "daysList": [
            {"day": 1, "stops": stops},
            {"day": 2, "stops": [stop(1, "start", 56.0, 38.0), stop(2, "finish", 57.0, 39.0)]},
        ]
    }


class CarTest(unittest.TestCase):
    def test_day_links_exact(self) -> None:
        r = h.handoff(trip(1), {"mode": "car", "day": 1, "fromHere": False})
        part = r["parts"][0]
        self.assertEqual([p["role"] for p in part["points"]], ["origin", "via", "destination"])
        self.assertEqual(
            part["links"]["navigator"],
            "yandexnavi://build_route_on_map?lat_to=56.000000&lon_to=38.000000&lat_from=55.000000"
            "&lon_from=37.000000&lat_via_0=55.100000&lon_via_0=37.100000",
        )
        self.assertEqual(
            part["links"]["web"],
            "https://yandex.ru/maps/?rtext=55.000000,37.000000~55.100000,37.100000~56.000000,38.000000&rtt=auto",
        )
        self.assertTrue(part["links"]["maps"].startswith("yandexmaps://maps.yandex.ru/?rtext=55.000000"))
        self.assertFalse(r["truncated"])

    def test_from_here_and_fuel_rest_dropped(self) -> None:
        r = h.handoff(trip(2), {"mode": "car"})
        pts = r["parts"][0]["points"]
        self.assertEqual([p["nameRu"] for p in pts], ["sight2", "sight4", "overnight99"])
        self.assertTrue(r["parts"][0]["links"]["web"].startswith("https://yandex.ru/maps/?rtext=~55.1"))
        self.assertNotIn("lat_from", r["parts"][0]["links"]["navigator"])

    def test_truncated_to_eight_vias(self) -> None:
        r = h.handoff(trip(12), {"mode": "car", "day": 1})
        vias = [p for p in r["parts"][0]["points"] if p["role"] == "via"]
        self.assertEqual(len(vias), h.MAX_VIAS)
        self.assertTrue(r["truncated"])
        lats = [p["lat"] for p in vias]
        self.assertEqual(lats, sorted(lats))  # route order kept

    def test_v3_next_point_order_and_signing(self) -> None:
        """ADR-0015 §1: Карты takes the day, the Навигатор the next point; signing adds `client`."""
        r = h.handoff(trip(2), {"mode": "car", "day": 1, "fromHere": False})
        part = r["parts"][0]
        self.assertEqual(r["order"], ["maps", "navigatorNext", "web"])
        self.assertEqual(
            part["links"]["navigatorNext"],
            "yandexnavi://build_route_on_map?lat_to=55.100000&lon_to=37.100000",
        )
        self.assertEqual(part["next"]["nameRu"], "sight2")
        self.assertNotIn("toSign", part)
        signed = h.handoff(trip(2), {"mode": "car", "day": 1, "signing": {"client": "verst"}})["parts"][0]
        for k in ("navigator", "navigatorNext", "maps"):
            self.assertTrue(signed["links"][k].endswith("&client=verst"), k)
            self.assertEqual(signed["toSign"][k], signed["links"][k])
        self.assertNotIn("client", signed["links"]["web"])
        w = h.handoff(
            {
                "stops": [{"id": "w1", "lat": 55.0, "lon": 37.0, "nameRu": "a"}],
                "start": {"lat": 55.1, "lon": 37.1},
            },
            {"mode": "walk", "fromHere": False, "signing": {"client": "verst"}},
        )
        self.assertTrue(w["parts"][0]["links"]["maps"].endswith("&client=verst"))
        with self.assertRaises(h.HandoffError):
            h.handoff(trip(1), {"mode": "car", "signing": {}})

    def test_from_stop(self) -> None:
        r = h.handoff(trip(3), {"mode": "car", "fromStopId": "d1s04", "fromHere": False})
        pts = r["parts"][0]["points"]
        self.assertEqual(pts[0]["nameRu"], "sight4")
        self.assertEqual(pts[-1]["nameRu"], "overnight99")
        self.assertEqual(r["day"], 1)

    def test_errors(self) -> None:
        cases = [
            ({"daysList": []}, {"mode": "car"}, "route"),
            (trip(1), {"mode": "car", "day": 7}, "day"),
            (trip(1), {"mode": "car", "fromStopId": "nope"}, "fromStopId"),
            (trip(1), {"mode": "car", "fromStopId": "d1s99"}, "fromStopId"),
            (trip(1), {"mode": "car", "day": True}, "day"),
            (trip(1), {"mode": "car", "fromHere": "yes"}, "fromHere"),
            (trip(1), {"mode": "car", "fromStopId": 3}, "fromStopId"),
            (trip(1), {"mode": "boat"}, "mode"),
            ({}, {"mode": "walk"}, "route"),
        ]
        for route, opts, field in cases:
            with self.subTest(opts=opts), self.assertRaises(h.HandoffError) as e:
                h.handoff(route, opts)
            self.assertEqual(e.exception.field, field)


def walk_route(n: int) -> dict[str, Any]:
    return {
        "start": {"lat": 57.0, "lon": 39.0, "label": "старт"},
        "finish": {"lat": 57.0, "lon": 39.0, "label": "старт"},
        "stops": [
            {"id": f"w{i:02d}", "nameRu": f"s{i}", "lat": 57.0 + i / 1000, "lon": 39.0}
            for i in range(1, n + 1)
        ],
    }


class WalkTest(unittest.TestCase):
    def test_single_part_pedestrian(self) -> None:
        r = h.handoff(walk_route(4), {"mode": "walk", "fromHere": False})
        self.assertEqual(len(r["parts"]), 1)
        links = r["parts"][0]["links"]
        self.assertNotIn("navigator", links)
        self.assertTrue(links["maps"].endswith("&rtt=pd"))
        self.assertEqual(len(r["parts"][0]["points"]), 6)

    def test_long_walk_split_with_shared_boundary(self) -> None:
        r = h.handoff(walk_route(13), {"mode": "walk", "fromHere": False})  # 15 points
        self.assertEqual(len(r["parts"]), 2)
        a, b = r["parts"][0]["points"], r["parts"][1]["points"]
        self.assertEqual(len(a), h.MAX_WALK_POINTS)
        self.assertEqual(a[-1], b[0])
        self.assertEqual(len(a) + len(b) - 1, 15)

    def test_from_here_and_from_stop(self) -> None:
        r = h.handoff(walk_route(3), {"mode": "walk", "fromHere": True})
        self.assertEqual(r["parts"][0]["points"][0]["nameRu"], "s1")
        self.assertIn("rtext=~", r["parts"][0]["links"]["web"])
        r2 = h.handoff(walk_route(3), {"mode": "walk", "fromStopId": "w02", "fromHere": False})
        self.assertEqual(r2["parts"][0]["points"][0]["nameRu"], "s2")
        with self.assertRaises(h.HandoffError):
            h.handoff(walk_route(3), {"mode": "walk", "fromStopId": "w09"})
        with self.assertRaises(h.HandoffError):
            h.handoff({"stops": []}, {"mode": "walk", "fromHere": False})


if __name__ == "__main__":
    unittest.main()
