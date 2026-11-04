"""Plan-quality checks on the real catalogue (audit 04.11): rules that held on the fixture worlds and must
hold on the OSM stops too."""

from __future__ import annotations

import json
import unittest
from typing import Any

from tests.unit.test_mobile import call, load_worlds
from verst_planner import mobile

R = "russia_v1"
MSK = {"lat": 55.7558, "lon": 37.6173, "label": "Москва"}
SPB = {"lat": 59.9386, "lon": 30.3141, "label": "Санкт-Петербург"}


def stops(r: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for d in r["trip"]["daysList"] for s in d["stops"]]


class RealPlansTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_worlds()
        call(mobile.set_clock("golden"))
        call(mobile.load_catalogue())

    @classmethod
    def tearDownClass(cls) -> None:
        call(mobile.set_clock("system"))

    def test_no_playground_for_adults(self) -> None:
        """M9: an open-data playground is a break only for a child, the extended rest window included
        (Москва → Санкт-Петербург, day 3 offered «Детская площадка, Малая Вишера» to two adults)."""
        inp = {"origin": MSK, "destination": SPB, "crew": {"adults": 2}, "dailyKm": 400}
        r = call(mobile.plan(R, "adults-spb", json.dumps(inp), None))
        names = [s["name"] for s in stops(r)]
        self.assertFalse([n for n in names if n.startswith("Детская площадка")], names)


if __name__ == "__main__":
    unittest.main()
