import unittest
from typing import Any

from tests.helpers import line_north, make_ctx, make_place, make_route, make_town, trip
from verst_planner.adapters.fake.world import offset_local
from verst_planner.domain.enums import OvernightFallback, PlaceType, Source, Tag, WarningCode
from verst_planner.domain.model import Candidate, Crew, NormalizedInput, RoadClass, TownCandidate
from verst_planner.geo.index import PolylineIndex
from verst_planner.pipeline import Corridor, PlanContext
from verst_planner.pipeline.day_split import DaySplit
from verst_planner.pipeline.overnight import _Scorer, choose_overnights, h_fit, passes, rank_hotels
from verst_planner.pipeline.resolve import normalize_input
from verst_planner.pipeline.timeline import Profile

ROUTE = make_route(line_north(50.0, 38.0, 600), speed_kmh=80, cum_km=[float(i) for i in range(601)])


def lodging(
    pid: str,
    town_id: str,
    tags: set[Tag],
    km: float,
    detour_min: int = 0,
    price: int = 4000,
    source: Source = Source.CURATED,
    rating: float = 4.0,
) -> Candidate:
    pt = offset_local(ROUTE.points[round(km)], 0.3, 0.0)
    p = make_place(
        pid,
        PlaceType.LODGING,
        pt.lat,
        pt.lon,
        tags,
        town_id=town_id,
        price_night_rub=price,
        source=source,
        rating_internal=rating,
    )
    return Candidate(p, km, 0.3, 0.78, detour_min, RoadClass.TRUNK, "RU-MOS")


def town(
    tid: str, km: float, lodgings: list[Candidate], quality: int = 1, evening: bool = False
) -> TownCandidate:
    pt = ROUTE.points[round(km)]
    t = make_town(tid, pt.lat, pt.lon, name_ru=f"Город {tid}", quality=quality, evening_walk=evening)
    return TownCandidate(t, km, 0.0, 0, lodgings)


def corridor(towns: list[TownCandidate]) -> Corridor:
    lodgings = sorted((h for t in towns for h in t.lodgings), key=lambda c: (c.km_at, c.place.id))
    return Corridor(
        ROUTE, PolylineIndex(ROUTE), [], [], [], [], lodgings, sorted(towns, key=lambda t: t.km_at)
    )


def setup(crew: Crew | None = None, daily: int = 300, **kw: Any) -> tuple[PlanContext, NormalizedInput]:
    ctx, _ = make_ctx()
    return ctx, normalize_input(trip(crew=crew or Crew(2, 0, False), daily_km=daily, **kw), ctx)


def split(n: int) -> DaySplit:
    return DaySplit(n, ROUTE.km_total, False, [])


DOG = Crew(2, 0, True)


class ScoreTest(unittest.TestCase):
    def test_score_formula(self) -> None:
        ctx, inp = setup()
        hs = [lodging(f"h{i}", "t1", {Tag.PARKING}, 330, detour_min=15) for i in range(4)]
        tc = town("t1", 330, hs, quality=2, evening=True)
        scorer = _Scorer(corridor([tc]), inp, ctx, Profile.from_route(ROUTE, 1.1))
        st = scorer.score(tc, target=300, prev_km=0, day=1)
        self.assertEqual((st.h_fit, st.q_town, st.e_evening, st.detour_min), (4.0, 2, 1, 15))
        self.assertAlmostEqual(st.score, 3 * 4 + 2 * 2 + 1.5 * 1 - 2 * 0.3 - 1 * 1, places=6)
        self.assertAlmostEqual(st.score, 15.9, places=6)

    def test_h_cap_and_parking_weight(self) -> None:
        ctx, _ = setup()
        seven = [lodging(f"p{i}", "t", {Tag.PARKING_GUARDED}, 300) for i in range(7)]
        self.assertEqual(h_fit(seven, ctx), 5.0)
        two = [lodging("n1", "t", set(), 300), lodging("n2", "t", set(), 300)]
        self.assertEqual(h_fit(two, ctx), 1.0)

    def test_evening_sight_counts(self) -> None:
        ctx, inp = setup()
        tc = town("t1", 300, [lodging("h", "t1", set(), 300)])
        sight_pt = ROUTE.points[300]
        sight = make_place(
            "s_eve",
            PlaceType.SIGHT,
            sight_pt.lat,
            sight_pt.lon,
            {Tag.EVENING},
            town_id="t1",
            opening_hours="Mo-Su 18:00-23:00",
        )
        cor = corridor([tc])
        cor.sights = [Candidate(sight, 300, 0.0, 0.0, 0, RoadClass.TRUNK, "RU-MOS")]
        scorer = _Scorer(cor, inp, ctx, Profile.from_route(ROUTE, 1.1))
        # start 08:00 + 300 km at 80 km/h × 1.1 (247.5 min) + 150 min allowance → 14:37; +60 min → closed
        self.assertEqual(scorer.score(tc, 300, 0, 1).e_evening, 0)
        cor.sights[0].place = make_place(
            "s_eve",
            PlaceType.SIGHT,
            sight_pt.lat,
            sight_pt.lon,
            {Tag.EVENING},
            town_id="t1",
            opening_hours="Mo-Su 15:00-23:00",
        )
        ctx._hours.clear()
        self.assertEqual(scorer.score(tc, 300, 0, 1).e_evening, 1)


class FiltersTest(unittest.TestCase):
    def test_osm_lodging_never_dog_friendly(self) -> None:
        ctx, _ = setup()
        osm_plain = lodging("o1", "t", {Tag.PARKING}, 300, source=Source.OSM)
        osm_tagged = lodging("o2", "t", {Tag.DOGS_ALLOWED}, 300, source=Source.OSM)
        self.assertFalse(passes(osm_plain, DOG, ctx))
        self.assertTrue(passes(osm_tagged, DOG, ctx))
        self.assertTrue(passes(osm_plain, Crew(2, 0, False), ctx))

    def test_family_room_and_price(self) -> None:
        ctx, _ = setup()
        plain = lodging("p", "t", set(), 300)
        family = lodging("f", "t", {Tag.FAMILY_ROOM}, 300)
        self.assertFalse(passes(plain, Crew(2, 1, False), ctx))  # 3 people → family room
        self.assertTrue(passes(family, Crew(2, 1, False), ctx))
        self.assertTrue(passes(plain, Crew(1, 1, False), ctx))  # only 2 people
        no_price = make_place("np", PlaceType.LODGING, 50.0, 38.0, set(), price_night_rub=None)
        self.assertFalse(
            passes(Candidate(no_price, 1, 0, 0, 0, RoadClass.TRUNK, "RU-MOS"), Crew(1, 0, False), ctx)
        )

    def test_hotel_rank(self) -> None:
        tc = town("t", 300, [])
        cheap = lodging("a_cheap", "t", set(), 300, price=3000, rating=4.0)
        guarded = lodging("b_guarded", "t", {Tag.PARKING_GUARDED}, 300, price=6000, rating=4.0)
        self.assertEqual([h.place.id for h in rank_hotels([cheap, guarded], tc)], ["b_guarded", "a_cheap"])


class ChoiceTest(unittest.TestCase):
    def test_on_target_pick(self) -> None:
        ctx, inp = setup()  # 600 km, 300/day → T = 300, window [285, 315]
        towns = [
            town("t_near", 290, [lodging("h1", "t_near", {Tag.PARKING}, 290)]),
            town("t_out", 250, [lodging("h2", "t_out", {Tag.PARKING}, 250)] * 1, quality=3),
        ]
        res = choose_overnights(split(2), corridor(towns), inp, ctx)
        self.assertEqual(len(res.choices), 1)
        c = res.choices[0]
        self.assertEqual((c.town.id if c.town else None, c.fallback), ("t_near", OvernightFallback.NONE))
        self.assertEqual(res.warnings, [])
        self.assertEqual([s.town.id for s in c.considered], ["t_near"])
        self.assertEqual(c.hotel.place.id if c.hotel else None, "h1")

    def test_tie_closer_to_target(self) -> None:
        ctx, inp = setup()  # T = 300 exactly (the route is 600 km)
        # S_far = 3 + 2 − 2·10/100 − 0/15 = 4.8 ; S_near = 3 + 2 − 0 − 3/15 = 4.8 → tie → closer to target
        far = town("t_a", 310, [lodging("ha", "t_a", {Tag.PARKING}, 310, detour_min=0)])
        near = town("t_b", 300, [lodging("hb", "t_b", {Tag.PARKING}, 300, detour_min=3)])
        res = choose_overnights(split(2), corridor([far, near]), inp, ctx)
        scores = sorted(round(s.score, 9) for s in res.choices[0].considered)
        self.assertEqual(scores[0], scores[1])
        self.assertEqual(res.choices[0].town.id if res.choices[0].town else None, "t_b")
        # equal score and distance → smaller town id
        x = town("t_y", 300, [lodging("hy", "t_y", {Tag.PARKING}, 300)])
        y = town("t_x", 300, [lodging("hx", "t_x", {Tag.PARKING}, 300)])
        res = choose_overnights(split(2), corridor([x, y]), inp, ctx)
        self.assertEqual(res.choices[0].town.id if res.choices[0].town else None, "t_x")

    def test_dog_filter_excludes(self) -> None:
        ctx, inp = setup(DOG)
        towns = [town("t_nodog", 300, [lodging("h_nodog", "t_nodog", {Tag.PARKING}, 300)], quality=3)]
        res = choose_overnights(split(2), corridor(towns), inp, ctx)
        c = res.choices[0]
        self.assertIn(c.fallback, (OvernightFallback.WIDENED, OvernightFallback.NO_HOTEL))
        self.assertIsNone(c.hotel)
        self.assertEqual(c.hotel_options, [])
        self.assertEqual([w.code for w in res.warnings], [WarningCode.NO_LODGING])

    def test_fallback_widened_warns(self) -> None:
        ctx2, inp2 = setup(DOG, daily=450)
        # 600 km, 450/day: N=2, seg 300, window [max(210, 127.5), min(315, 472.5)] = [210, 315];
        # widened [max(120, 127.5), min(390, 472.5)] = [127.5, 390] → 440 is outside both; 380 is widened only
        towns = [town("t_w", 380, [lodging("h_w", "t_w", {Tag.DOGS_ALLOWED}, 380)])]
        res = choose_overnights(split(2), corridor(towns), inp2, ctx2)
        c = res.choices[0]
        self.assertEqual(c.fallback, OvernightFallback.WIDENED)
        self.assertEqual(c.hotel.place.id if c.hotel else None, "h_w")
        self.assertEqual(len(res.warnings), 1)
        self.assertEqual((res.warnings[0].code, res.warnings[0].day), (WarningCode.NO_LODGING, 1))
        self.assertTrue(res.warnings[0].detail.startswith("widened"))

    def test_fallback_extra_day(self) -> None:
        ctx, inp = setup(daily=300)
        # N = 2 needs a town in [285, 315]: none. N + 1 = 3: windows [140, 210] then [~, ~]
        towns = [
            town("t1", 200, [lodging("h1", "t1", set(), 200)]),
            town("t2", 400, [lodging("h2", "t2", set(), 400)]),
        ]
        res = choose_overnights(split(2), corridor(towns), inp, ctx)
        self.assertEqual(res.n_days, 3)
        self.assertEqual([c.town.id if c.town else None for c in res.choices], ["t1", "t2"])
        self.assertIn(OvernightFallback.EXTRA_DAY, [c.fallback for c in res.choices])
        self.assertEqual([w.detail for w in res.warnings], ["extra_day"])

    def test_fallback_no_hotel_with_nearest(self) -> None:
        ctx, inp = setup(DOG)
        towns = [
            town("t_mid", 300, [lodging("h_mid", "t_mid", {Tag.PARKING}, 300)], quality=2),
            town("t_dog", 100, [lodging("h_dog", "t_dog", {Tag.DOGS_ALLOWED}, 100)]),
        ]
        res = choose_overnights(split(2), corridor(towns), inp, ctx)
        self.assertEqual(res.n_days, 2)
        c = res.choices[0]
        self.assertEqual((c.town.id if c.town else None, c.fallback), ("t_mid", OvernightFallback.NO_HOTEL))
        self.assertIsNone(c.hotel)
        self.assertEqual(c.nearest.place.id if c.nearest else None, "h_dog")
        w = res.warnings[-1]
        self.assertIn("Ближайшая подходящая: ", w.message_ru)
        self.assertIn("Город t_dog, 200 км от ночёвки", w.message_ru)
        self.assertIn("nearest=h_dog", w.detail)

    def test_no_town_road_point(self) -> None:
        ctx, inp = setup(DOG)
        res = choose_overnights(split(2), corridor([]), inp, ctx)
        c = res.choices[0]
        self.assertIsNone(c.town)
        self.assertAlmostEqual(c.km_at, 300, delta=1e-6)
        self.assertTrue(c.name_ru)
        self.assertIsNone(c.nearest)


if __name__ == "__main__":
    unittest.main()
