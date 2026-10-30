"""ENG-02: weekend tariffs and `RoadRateTolls` (km x the road's rate on routes with real geometry)."""

from __future__ import annotations

import unittest
from datetime import date, datetime, time
from decimal import Decimal

from tests.helpers import make_ctx
from verst_planner.adapters.catalogue.tolls import RoadRateTolls, TollRates
from verst_planner.cost.formulas import toll_row
from verst_planner.cost.model import TollInput, toll_unit
from verst_planner.domain.enums import RoadClass
from verst_planner.domain.model import LatLon, Route, RouteDetail, TollHit, TollSegment

RATES = TollRates.from_dict(
    {
        "asOf": "2026-03-02",
        "roads": [
            {"ref": "М-11", "aliases": ["M-11"], "weekdayRubPerKm": "7.25", "weekendRubPerKm": "8.21"},
            {"ref": "М-12", "weekdayRubPerKm": "7.30", "weekendRubPerKm": None},
        ],
    }
)


def seg(sid: str, day: str, night: str, weekend: str | None = None) -> TollSegment:
    return TollSegment(
        sid, "М-4", sid, Decimal(day), Decimal(night), 1, time(0), time(6), date(2026, 3, 2),
        Decimal(weekend) if weekend else None,
    )


def route(details: list[tuple[int, int, str | None, bool]], km: list[float]) -> Route:
    pts = tuple(LatLon(55.0 + i * 0.01, 37.0) for i in range(len(km)))
    return Route(
        points=pts,
        cum_km=tuple(km),
        cum_min=tuple(k for k in km),
        details=tuple(RouteDetail(a, b, RoadClass.MOTORWAY, ref, toll) for a, b, ref, toll in details),
        waypoint_idx=(0, len(km) - 1),
        snapped=(pts[0], pts[-1]),
        km_total=km[-1],
        min_total=km[-1],
    )


class NoTolls:
    def segments_on_route(self, route: Route) -> list[TollHit]:
        return []


class Explicit:
    def __init__(self, *hits: TollHit) -> None:
        self.hits = list(hits)

    def segments_on_route(self, route: Route) -> list[TollHit]:
        return list(self.hits)


class WeekendTariffTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = make_ctx()[0].cfg

    def test_friday_to_sunday_take_the_weekend_tariff(self) -> None:
        hit = TollHit(seg("m4", "310", "310", "400"), 0, 56)
        thu, fri, sun = (datetime(2026, 10, d, 12) for d in (22, 23, 25))
        units = [toll_unit(TollInput(hit, t), self.cfg) for t in (thu, fri, sun)]
        got = [(u.rub, u.weekend, u.night) for u in units]
        self.assertEqual(got, [(310, False, False), (400, True, False), (400, True, False)])

    def test_no_night_discount_means_never_night(self) -> None:
        hit = TollHit(seg("m4", "310", "310", "400"), 0, 56)
        u = toll_unit(TollInput(hit, datetime(2026, 10, 23, 2, 0)), self.cfg)
        self.assertEqual((u.rub, u.night, u.weekend), (400, False, True))  # Fri 02:00: weekend, not night

    def test_a_night_discount_wins_over_the_weekend(self) -> None:
        hit = TollHit(seg("m11", "950", "740", "1295"), 15, 58)
        u = toll_unit(TollInput(hit, datetime(2026, 10, 24, 2, 0)), self.cfg)
        self.assertEqual((u.rub, u.night, u.weekend), (740, True, False))

    def test_the_breakdown_says_weekend(self) -> None:
        self.assertEqual(toll_row("М-4", False, 400, True).formula_ru, "М-4, в выходные")
        self.assertEqual(toll_row("М-4", False, 310).formula_ru, "М-4, днём")


class RoadRateTollsTest(unittest.TestCase):
    def test_a_toll_run_is_priced_per_km_of_its_road(self) -> None:
        details = [(0, 1, "М-8", False), (1, 3, "M-11;Е105", True), (3, 4, None, False)]
        r = route(details, [0, 20, 70, 120, 130])
        [h] = RoadRateTolls(NoTolls(), RATES).segments_on_route(r)
        self.assertEqual((h.segment.road_ref, h.km_from, h.km_to), ("М-11", 20, 120))
        self.assertEqual(h.segment.tariff_day_rub, Decimal(725))
        self.assertEqual(h.segment.tariff_weekend_rub, Decimal(821))
        self.assertEqual(h.segment.tariff_night_rub, h.segment.tariff_day_rub)
        self.assertEqual(h.segment.as_of, date(2026, 3, 2))

    def test_explicit_segments_are_not_counted_twice(self) -> None:
        r = route([(0, 2, "М-12", True)], [0, 100, 300])
        explicit = TollHit(seg("ts_m12_1", "1737", "1737"), 0, 182)
        hits = RoadRateTolls(Explicit(explicit), RATES).segments_on_route(r)
        self.assertEqual([h.segment.id for h in hits], ["ts_m12_1", "rate:М-12:182"])
        self.assertEqual(hits[1].segment.tariff_day_rub, Decimal(861))  # 118 km x 7.30 = 861.4
        self.assertIsNone(hits[1].segment.tariff_weekend_rub)

    def test_slivers_and_unknown_roads_are_not_costed(self) -> None:
        r = route([(0, 1, "М-12", True), (1, 2, "Р-22", True)], [0, 182.6, 250])
        explicit = TollHit(seg("ts_m12_1", "1737", "1737"), 0, 182)
        hits = RoadRateTolls(Explicit(explicit), RATES).segments_on_route(r)
        self.assertEqual([h.segment.id for h in hits], ["ts_m12_1"])

    def test_the_shipped_table_loads(self) -> None:
        rates = TollRates.from_resources()
        self.assertFalse(rates.verified)
        for ref in ("М-11", "M-12", "ЦКАД", "А-113", "М-4", "М-3", "М-1"):
            self.assertIsNotNone(rates.rate(ref), ref)
        self.assertIsNone(rates.rate("М-8"))


if __name__ == "__main__":
    unittest.main()
