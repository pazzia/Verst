"""Acceptance 2026-10-28, block 1 «plan quality» (engine): the unit rules.

Traveller K1 (added sights), K3 (dog), V2 (raised daily km), M2 (last fuel); QA B-1 (tolls on approximate
routes), B-4 (time zones), B-6 (fuel rows), B-8 (strict input). The scenario-level checks on the real
catalogue are in `tests/golden/test_block1_acceptance.py`.
"""

import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import ClassVar

from tests.helpers import make_ctx, make_place, make_town, sample_normalized
from verst_planner.adapters.catalogue.tolls import CorridorTolls, TollCorridors
from verst_planner.config import PlannerConfig
from verst_planner.cost.recompute import split_rounded
from verst_planner.domain import codec
from verst_planner.domain.enums import PlaceType, RoadClass, Source, StopKind, Tag
from verst_planner.domain.errors import InvalidInput
from verst_planner.domain.model import (
    BudgetLever,
    Candidate,
    DayPlan,
    LatLon,
    PlannedStop,
    Route,
    RouteDetail,
    TollHit,
)
from verst_planner.explain.reasons import overnight_reason
from verst_planner.explain.templates import ReasonTemplates
from verst_planner.pipeline.sights import (
    dog_closed,
    in_home_zone,
    lever_free_ok,
    minor_open_data,
    near_day_ends,
)
from verst_planner.pipeline.timeline import TOWN_POOL, Profile, detour_halves, schedule_day

CFG = PlannerConfig.default()
OPEN = dict(quality=0.5, source=Source.OSM, card_level=3)


class DogRuleTest(unittest.TestCase):
    """K3: a dog crew gets no place closed to dogs by its type; an unknown policy is not guessed."""

    def test_closed_by_type(self) -> None:
        self.assertTrue(dog_closed(make_place(name_ru="Музей ложки", category="museum", **OPEN)))
        self.assertTrue(dog_closed(make_place(name_ru="Ростовский кремль", tags={Tag.KREMLIN, Tag.MUSEUM})))
        self.assertTrue(dog_closed(make_place(name_ru="ГУМ", category="attraction", **OPEN)))
        self.assertTrue(dog_closed(make_place(name_ru="Зоопарк", category="zoo", **OPEN)))
        # a kremlin or monastery with a ticket is a museum territory; a free one is a walk
        walls = make_place(
            name_ru="Городские валы", category="kremlin", tags={Tag.KREMLIN}, ticket_adult_rub=300
        )
        self.assertTrue(dog_closed(walls))
        self.assertFalse(
            dog_closed(make_place(name_ru="Троице-Сергиева лавра", tags={Tag.MONASTERY, Tag.FREE_ENTRY}))
        )

    def test_open_and_known_policies(self) -> None:
        self.assertFalse(dog_closed(make_place(name_ru="Парк Победы", category="park", **OPEN)))
        self.assertFalse(dog_closed(make_place(name_ru="Гуманитарный центр", category="attraction", **OPEN)))
        # ADR-0019 E-6: a confirmed «yes» passes even a museum, a confirmed «no» never passes
        self.assertFalse(dog_closed(make_place(name_ru="Музей", category="museum", tags={Tag.DOGS_ALLOWED})))
        self.assertTrue(
            dog_closed(
                make_place(name_ru="Набережная", category="embankment", tags_no=frozenset({Tag.DOGS_ALLOWED}))
            )
        )


class MinorSightTest(unittest.TestCase):
    """K1 (b): the «15-minute» open-data sight and the bare name are no road stops."""

    def test_short_low_quality(self) -> None:
        lenin = make_place(
            name_ru="Памятник В. И. Ленину в Глухово", dwell_min=15, **{**OPEN, "quality": 0.41}
        )
        self.assertTrue(minor_open_data(lenin, CFG))
        landmark = make_place(name_ru="Рабочий и колхозница", dwell_min=15, **{**OPEN, "quality": 0.70})
        self.assertFalse(minor_open_data(landmark, CFG))
        park = make_place(name_ru="Парк", dwell_min=40, **{**OPEN, "quality": 0.38})
        self.assertFalse(minor_open_data(park, CFG))

    def test_bare_name_and_curated(self) -> None:
        bare = make_place(name_ru="Усадьба", dwell_min=30, **{**OPEN, "card_level": 1})
        self.assertTrue(minor_open_data(bare, CFG))
        playground = make_place(
            name_ru="Детская площадка", category="playground", dwell_min=20, **{**OPEN, "card_level": 1}
        )
        self.assertFalse(minor_open_data(playground, CFG))
        self.assertFalse(minor_open_data(make_place(name_ru="Золотые ворота", dwell_min=15), CFG))  # curated


class LeverTest(unittest.TestCase):
    """K1 (c): `sights_free` keeps a curated free place or an open public space, not any free heritage."""

    def test_lever_free_ok(self) -> None:
        inp = sample_normalized()
        self.assertTrue(lever_free_ok(make_place(tags={Tag.FREE_ENTRY}), inp))
        heritage = make_place(name_ru="Здание театра", category="theatre", tags={Tag.FREE_ENTRY}, **OPEN)
        self.assertFalse(lever_free_ok(heritage, inp))
        park = make_place(name_ru="Парк", category="park", tags={Tag.FREE_ENTRY}, **OPEN)
        self.assertTrue(lever_free_ok(park, inp))
        self.assertFalse(lever_free_ok(make_place(category="park", ticket_adult_rub=200, **OPEN), inp))


class ZoneTest(unittest.TestCase):
    """K1 (a): the home zone and the ends of the day."""

    def test_home_zone(self) -> None:
        inp = sample_normalized()  # Москва → Ярославль
        vdnkh = make_place(lat=55.8263, lon=37.6377)
        self.assertTrue(in_home_zone(vdnkh, inp, CFG))
        self.assertFalse(in_home_zone(make_place(lat=56.31, lon=38.13), inp, CFG))  # Сергиев Посад, 70 km
        yaroslavl = make_place(lat=57.63, lon=39.88)
        self.assertFalse(in_home_zone(yaroslavl, inp, CFG))

    def test_day_ends(self) -> None:
        inp = sample_normalized()
        town = make_town("t_v", lat=56.13, lon=40.41)
        start = PlannedStop(StopKind.START, 0.0, "Москва", inp.origin.point)
        night = PlannedStop(StopKind.OVERNIGHT, 190.0, "Владимир", town.point, town=town)
        day1 = DayPlan(1, 0.0, 190.0, datetime(2026, 11, 7, 8, tzinfo=UTC), [start, night], "Europe/Moscow")
        near = make_place(lat=56.15, lon=40.30, **OPEN)
        self.assertTrue(near_day_ends(near, day1, inp, CFG))
        self.assertFalse(near_day_ends(make_place(lat=56.15, lon=40.30), day1, inp, CFG))  # curated stays
        start2 = PlannedStop(StopKind.START, 190.0, "Владимир", town.point, town=town)
        finish = PlannedStop(StopKind.FINISH, 450.0, "Ярославль", LatLon(57.63, 39.88))
        day2 = DayPlan(
            2, 190.0, 450.0, datetime(2026, 11, 8, 6, tzinfo=UTC), [start2, finish], "Europe/Moscow"
        )
        self.assertTrue(near_day_ends(near, day2, inp, CFG))  # on the way out of the overnight town
        far = make_place(lat=57.0, lon=40.0, **OPEN)
        self.assertFalse(near_day_ends(far, day2, inp, CFG))


class TownVisitTimingTest(unittest.TestCase):
    """V1: the first evening stop carries the drive into town; the hotel after it none."""

    def test_detour_halves(self) -> None:
        town = make_town()
        start = PlannedStop(StopKind.START, 0.0, "A", LatLon(56.0, 38.0))
        sight = PlannedStop(
            StopKind.SIGHT, 100.0, "Кремль", LatLon(56.9, 38.0), detour_min=10, pool=TOWN_POOL
        )
        night = PlannedStop(StopKind.OVERNIGHT, 100.0, "Город", town.point, town=town, detour_min=120)
        halves = detour_halves([start, sight, night])
        self.assertEqual(halves[1], (65.0, 5.0))
        self.assertEqual(halves[2], (0.0, 60.0))
        # the evening arrives in town after the approach, and the hotel within the town
        route_profile = Profile(tuple(float(k) for k in range(101)), tuple(float(k) for k in range(101)), 1.0)
        t0 = datetime(2026, 11, 7, 8, tzinfo=UTC)
        slots = schedule_day(
            DayPlan(1, 0.0, 100.0, t0, [start, sight, night], "Europe/Moscow"), route_profile
        )
        assert slots[1].arrive is not None and slots[2].arrive is not None
        self.assertEqual(slots[1].arrive, t0 + timedelta(minutes=100 + 65))
        self.assertEqual(slots[2].arrive - slots[1].arrive, timedelta(minutes=sight.dwell_min + 5))
        # without a town stop the overnight keeps the plain half (A§6.6)
        self.assertEqual(detour_halves([start, night])[1], (60.0, 60.0))


class FuelRowsTest(unittest.TestCase):
    """QA B-6: the fuel rows add up to the line."""

    def test_split_rounded(self) -> None:
        # docs/contracts/v2/plan-budget-fit.json: 4 regions, exact 2 714.02 → line 2 710 (rows were 2 720)
        exact = [Decimal("217.46"), Decimal("870.53"), Decimal("147.36"), Decimal("1478.67")]
        rows = split_rounded(exact, 10, 2710)
        self.assertEqual(sum(rows), 2710)
        for e, r in zip(exact, rows, strict=True):
            self.assertLess(abs(Decimal(r) - e), 10)
        self.assertEqual(split_rounded([Decimal(0), Decimal("75")], 10, 80), [0, 80])
        self.assertEqual(split_rounded([], 10, 0), [])


SPB_ROUTE_POINTS = (LatLon(55.7558, 37.6176), LatLon(59.93, 30.3))


def synthetic(a: LatLon, b: LatLon, km: float) -> Route:
    return Route(
        points=(a, b),
        cum_km=(0.0, km),
        cum_min=(0.0, km / 80 * 60),
        details=(RouteDetail(0, 1, RoadClass.PRIMARY, None, False),),
        waypoint_idx=(0, 1),
        snapped=(a, b),
        km_total=km,
        min_total=km / 80 * 60,
        synthetic=True,
    )


class _NoTolls:
    def segments_on_route(self, route: Route) -> list[TollHit]:
        return []


class CorridorTollsTest(unittest.TestCase):
    """QA B-1: an approximate route along a known toll road is priced from toll_rates.json, marked approx."""

    def setUp(self) -> None:
        self.tolls = CorridorTolls(_NoTolls(), TollCorridors.from_resources())

    def test_moscow_spb(self) -> None:
        hits = self.tolls.segments_on_route(synthetic(*SPB_ROUTE_POINTS, 890.0))
        self.assertEqual(len(hits), 1)
        seg = hits[0].segment
        self.assertEqual(seg.road_ref, "М-11")
        self.assertTrue(seg.approx)
        self.assertEqual(seg.tariff_day_rub, Decimal(4850))  # the whole road: toll_rates.json 950 + 3 900
        self.assertEqual(seg.tariff_weekend_rub, Decimal(5495))
        self.assertEqual((hits[0].km_from, hits[0].km_to), (0.0, 890.0))

    def test_partial_and_unknown(self) -> None:
        tver = self.tolls.segments_on_route(synthetic(SPB_ROUTE_POINTS[0], LatLon(56.858, 35.922), 180.0))
        self.assertEqual(tver[0].segment.road_ref, "М-11")
        self.assertLess(tver[0].segment.tariff_day_rub, Decimal(4850) / 3)
        ekb = synthetic(SPB_ROUTE_POINTS[0], LatLon(56.8389, 60.6057), 1800.0)
        self.assertEqual(self.tolls.segments_on_route(ekb), [])  # along no known corridor: not costed

    def test_real_geometry_goes_to_inner(self) -> None:
        r = synthetic(*SPB_ROUTE_POINTS, 890.0)
        import dataclasses

        self.assertEqual(self.tolls.segments_on_route(dataclasses.replace(r, synthetic=False)), [])


class StrictInputTest(unittest.TestCase):
    """QA B-8: the bridge rejects a wrong type as the server does («false» was true)."""

    BASE: ClassVar[dict[str, object]] = {
        "origin": {"lat": 55.75, "lon": 37.61},
        "destination": {"lat": 57.6, "lon": 39.9},
        "crew": {"adults": 2},
        "dailyKm": 300,
    }

    def reason(self, **patch: object) -> tuple[str, str]:
        d = {**self.BASE, **patch}
        with self.assertRaises(InvalidInput) as cm:
            codec.input_from_json(d)
        return cm.exception.field, cm.exception.reason

    def test_wrong_types(self) -> None:
        self.assertEqual(self.reason(roundTrip="false"), ("roundTrip", "wrong_type"))
        self.assertEqual(self.reason(reserveOn="false"), ("reserveOn", "wrong_type"))
        self.assertEqual(self.reason(simplify=1), ("simplify", "wrong_type"))
        self.assertEqual(self.reason(dailyKm="300"), ("dailyKm", "wrong_type"))
        self.assertEqual(self.reason(dailyKm=300.5), ("dailyKm", "wrong_type"))
        self.assertEqual(self.reason(budget="50000"), ("budget", "wrong_type"))
        self.assertEqual(self.reason(crew={"adults": True}), ("crew.adults", "wrong_type"))
        self.assertEqual(self.reason(origin={"lat": "55.7", "lon": 37.6}), ("origin.lat", "wrong_type"))
        self.assertEqual(
            self.reason(vehicle={"consumption": float("inf")}), ("vehicle.consumption", "wrong_type")
        )

    def test_valid_and_null_defaults(self) -> None:
        t = codec.input_from_json({**self.BASE, "roundTrip": False, "avoidTolls": None, "budget": None})
        self.assertFalse(t.round_trip)
        self.assertFalse(t.avoid_tolls)
        self.assertTrue(t.reserve_on)

    def test_bridge_errors(self) -> None:
        import json

        from tests.helpers import WORLDS
        from verst_planner import mobile

        mobile.load_world((WORLDS / "central_russia_v1.json").read_text("utf-8"))
        deep = json.loads(mobile.plan("central_russia_v1", "deep", "[" * 100_000, None))
        self.assertEqual(deep["error"]["code"], "INVALID_INPUT")
        inf = json.loads(mobile.plan("central_russia_v1", "inf", '{"dailyKm": Infinity}', None))
        self.assertEqual(inf["error"]["code"], "INVALID_INPUT")


class RaisedNormTest(unittest.TestCase):
    """V2: the overnight reason never calls the fitter's raised km «yours»."""

    def test_overnight_reason(self) -> None:
        import dataclasses

        from verst_planner.domain.enums import OvernightFallback
        from verst_planner.domain.model import OvernightChoice

        ctx, _f = make_ctx()
        town = make_town()
        hotel = Candidate(
            make_place("pl_h", PlaceType.LODGING), 300.0, 1.0, 2.6, 6, RoadClass.OTHER, "RU-MOS"
        )
        c = OvernightChoice(
            1, 300.0, town, town.point, "Город", hotel, [hotel], [], OvernightFallback.NONE, 0.0, 300.0
        )
        inp = dataclasses.replace(sample_normalized(), daily_km=350)
        t = ReasonTemplates.default()
        # no hotel → the no-hotel sentence; the cap sentence is what this test is about
        raised = overnight_reason(c, 340, inp, CFG, t, None, 300).text
        self.assertIn("Норму подняли до 350 км в день", raised)
        self.assertNotIn("Ваши 350", raised)
        mine = overnight_reason(c, 280, inp, CFG, t, None, 300).text
        self.assertIn("Ваши 300 км в день не превышены", mine)
        self.assertEqual(
            codec.lever_to_json(BudgetLever("fewer_nights", 5500, 350)),
            {"code": "fewer_nights", "savedRub": 5500, "dailyKm": 350},
        )
        self.assertEqual(
            codec.lever_to_json(BudgetLever("food_economy", 600)), {"code": "food_economy", "savedRub": 600}
        )
        self.assertIsNotNone(ctx)


if __name__ == "__main__":
    unittest.main()
