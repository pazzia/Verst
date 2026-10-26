"""ADR-0019: unknown facts are never read as convenient defaults (ADR-0018 §10 E-1…E-6)."""

import copy
import dataclasses
import unittest
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from tests.helpers import make_ctx, make_place, trip
from tests.unit.test_corridor import StubPlaces, _ll, at, two_class_route
from tests.unit.test_fake_world import mini
from tests.unit.test_fuel import corridor as fuel_corridor
from tests.unit.test_fuel import ctx_inp, days_for, fuel_stops, station
from verst_planner.adapters.catalogue.world import poi_ticket
from verst_planner.adapters.fake import FakeWorld
from verst_planner.catalogue import CatPoi
from verst_planner.config import PlannerConfig
from verst_planner.cost.model import CostInput, NightInput, RegionKm, SightInput, build_units
from verst_planner.cost.recompute import recompute
from verst_planner.domain import codec
from verst_planner.domain.enums import CostKey, FuelType, PlaceType, RoadClass, Source, StopKind, Tag
from verst_planner.domain.facts import (
    UNRATED_RANK,
    Fact,
    Known,
    breakfast_confirmed,
    confirmed_free,
    fuel_state,
    hours_known,
    rank_rating,
    tag_state,
    ticket_known,
    ticket_prices,
)
from verst_planner.domain.model import (
    AltUnits,
    Candidate,
    CostOverrides,
    Crew,
    LatLon,
    PlannedStop,
    RegionPrice,
    Vehicle,
)
from verst_planner.pipeline.assemble import render_stop, unknown_facts, unknown_line
from verst_planner.pipeline.corridor import build_corridor
from verst_planner.pipeline.fuel import plan_fuel
from verst_planner.pipeline.resolve import normalize_input
from verst_planner.pipeline.sights import effective_quality, is_paid, sight_score
from verst_planner.pipeline.timeline import Slot

CFG = PlannerConfig.default()
MSK = ZoneInfo("Europe/Moscow")


def sight_cand(**kw: Any) -> Candidate:
    return Candidate(make_place("s", PlaceType.SIGHT, **kw), 10.0, 0.2, 0.5, 0, RoadClass.TRUNK, "RU-MOS")


class FactsTest(unittest.TestCase):
    def test_rank_rating(self) -> None:
        """E-5: an unrated place ranks below every rated one, never as a real 3.0."""
        self.assertEqual(rank_rating(make_place(rating_internal=None)), UNRATED_RANK)
        self.assertEqual(rank_rating(make_place(rating_internal=3.0)), 3.0)
        self.assertLess(UNRATED_RANK, 0.1)

    def test_hours_known(self) -> None:
        """E-1: no hours = unknown; `24/7` or the `24h` tag = known."""
        self.assertFalse(hours_known(make_place(opening_hours=None)))
        self.assertTrue(hours_known(make_place(opening_hours="24/7")))
        self.assertTrue(hours_known(make_place(type=PlaceType.FUEL, tags={Tag.H24})))

    def test_tickets(self) -> None:
        """E-2: unknown ≠ free; `free_entry` and 0 ₽ are free; the child price falls back to the adult one."""
        unknown, free_tag, zero = (
            make_place(),
            make_place(tags={Tag.FREE_ENTRY}),
            make_place(ticket_adult_rub=0),
        )
        paid = make_place(ticket_adult_rub=400)
        self.assertEqual(
            [ticket_known(p) for p in (unknown, free_tag, zero, paid)], [False, True, True, True]
        )
        self.assertEqual(
            [confirmed_free(p) for p in (unknown, free_tag, zero, paid)], [False, True, True, False]
        )
        self.assertEqual(ticket_prices(unknown), (0, 0))
        self.assertEqual(ticket_prices(paid), (400, 400))
        self.assertEqual(ticket_prices(make_place(ticket_adult_rub=400, ticket_child_rub=150)), (400, 150))

    def test_breakfast(self) -> None:
        """E-3: only a confirmed breakfast counts as included."""
        self.assertEqual(
            [breakfast_confirmed(make_place(breakfast_included=b)) for b in (None, False, True)],
            [False, False, True],
        )

    def test_tri_states(self) -> None:
        """E-4 / E-6: yes, no and unknown are three different answers."""
        p = make_place(tags={Tag.WC}, tags_no=frozenset({Tag.DOGS_ALLOWED}))
        self.assertEqual(tag_state(p, Tag.WC), Known.YES)
        self.assertEqual(tag_state(p, Tag.DOGS_ALLOWED), Known.NO)
        self.assertEqual(tag_state(p, Tag.PARKING), Known.UNKNOWN)
        f = make_place(
            type=PlaceType.FUEL, fuel_kinds=frozenset({FuelType.AI95}), fuel_kinds_no=frozenset({FuelType.DT})
        )
        self.assertEqual(fuel_state(f, FuelType.AI95), Known.YES)
        self.assertEqual(fuel_state(f, FuelType.DT), Known.NO)
        self.assertEqual(fuel_state(f, FuelType.AI92), Known.UNKNOWN)


class RankingTest(unittest.TestCase):
    def test_unrated_ranks_below_rated(self) -> None:
        """E-5: an unrated sight scores below a rated 3.0 one with the same tags (was equal before)."""
        ctx, _ = make_ctx()
        inp = normalize_input(trip(), ctx)
        rated, unrated = sight_cand(rating_internal=3.0), sight_cand(rating_internal=None)
        self.assertLess(sight_score(unrated, inp), sight_score(rated, inp))
        self.assertEqual(effective_quality(unrated.place), 0.0)

    def test_free_sights_lever_keeps_only_confirmed_free(self) -> None:
        """E-2: the «бесплатные места» lever (ADR-0011) does not keep a sight whose price is unknown."""
        ctx, _ = make_ctx()
        inp = normalize_input(trip(), ctx)
        self.assertTrue(is_paid(sight_cand(), inp))
        self.assertFalse(is_paid(sight_cand(tags={Tag.FREE_ENTRY}), inp))
        self.assertFalse(is_paid(sight_cand(ticket_adult_rub=0), inp))
        self.assertTrue(is_paid(sight_cand(ticket_adult_rub=300), inp))


class FuelTest(unittest.TestCase):
    def test_station_without_the_fuel_is_skipped(self) -> None:
        """E-4: a station known not to sell the car's fuel never reaches the corridor; unknown ones do."""
        r = two_class_route()
        no = make_place(
            "f_no", PlaceType.FUEL, *_ll(at(r, 70, 0.5)), fuel_kinds_no=frozenset({FuelType.AI95})
        )
        unknown = make_place("f_unknown", PlaceType.FUEL, *_ll(at(r, 75, 0.5)))
        dt_no = make_place(
            "f_dt_no", PlaceType.FUEL, *_ll(at(r, 80, 0.5)), fuel_kinds_no=frozenset({FuelType.DT})
        )
        ctx, _ = make_ctx()
        ctx.ports.places = StubPlaces([no, unknown, dt_no], [])
        corridor = build_corridor(r, normalize_input(trip(), ctx), ctx)
        self.assertEqual([c.place.id for c in corridor.fuel], ["f_unknown", "f_dt_no"])

    def test_confirmed_fuel_ranks_first(self) -> None:
        """E-4: in the window, a station confirmed to sell АИ-95 beats a better-equipped unknown one."""
        ctx, inp = ctx_inp()
        sure = station("f_sure", 530)
        sure = dataclasses.replace(
            sure, place=dataclasses.replace(sure.place, fuel_kinds=frozenset({FuelType.AI95}))
        )
        cor = fuel_corridor(900, [station("f_best", 505, {Tag.CAFE_AT_FUEL, Tag.H24, Tag.WC}), sure])
        days = days_for(900, [])
        plan_fuel(days, cor, inp, ctx)  # type: ignore[arg-type]
        self.assertEqual([s.place.id for s in fuel_stops(days) if s.place], ["f_sure"])


class StopFactsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx, _ = make_ctx()
        self.inp = normalize_input(trip(crew=Crew(2, 0, True)), self.ctx)

    def stop(self, kind: StopKind, place: Any) -> PlannedStop:
        return PlannedStop(kind, 10.0, place.name_ru, place.point, place=place, region_code="RU-MOS")

    def test_sight_hours_ticket_dogs(self) -> None:
        s = self.stop(StopKind.SIGHT, make_place())
        facts = unknown_facts(s, self.inp)
        self.assertEqual(facts, (Fact.HOURS, Fact.TICKET, Fact.DOGS))
        # the ticket is named by the cost texts, not by the row line
        self.assertEqual(
            unknown_line(facts, self.inp), "Не проверено: часы работы, пускают ли с собакой — уточните"
        )
        known = make_place(opening_hours="24/7", tags={Tag.FREE_ENTRY, Tag.DOGS_ALLOWED})
        self.assertEqual(unknown_facts(self.stop(StopKind.SIGHT, known), self.inp), ())
        no_dogs = make_place(
            opening_hours="24/7", tags={Tag.FREE_ENTRY}, tags_no=frozenset({Tag.DOGS_ALLOWED})
        )
        self.assertEqual(unknown_facts(self.stop(StopKind.SIGHT, no_dogs), self.inp), ())

    def test_single_fact_lines(self) -> None:
        self.assertEqual(unknown_line((Fact.HOURS,), self.inp), "Часы не известны — уточните")
        self.assertEqual(unknown_line((Fact.DOGS,), self.inp), "Пускают ли с собакой — не проверено")
        self.assertIsNone(unknown_line((Fact.TICKET,), self.inp))
        self.assertIsNone(unknown_line((), self.inp))

    def test_fuel_stop(self) -> None:
        f = make_place(type=PlaceType.FUEL, tags={Tag.H24})
        facts = unknown_facts(self.stop(StopKind.FUEL, f), self.inp)
        self.assertEqual(facts, (Fact.FUEL,))
        self.assertEqual(unknown_line(facts, self.inp), "Есть ли АИ-95 — не проверено")
        diesel = dataclasses.replace(self.inp, vehicle=Vehicle(8.0, FuelType.DT))
        self.assertEqual(unknown_line(facts, diesel), "Есть ли ДТ — не проверено")
        both = unknown_facts(self.stop(StopKind.FUEL, make_place(type=PlaceType.FUEL)), self.inp)
        self.assertEqual(unknown_line(both, self.inp), "Не проверено: часы работы, есть ли АИ-95 — уточните")
        sure = make_place(type=PlaceType.FUEL, opening_hours="24/7", fuel_kinds=frozenset({FuelType.AI95}))
        self.assertEqual(unknown_facts(self.stop(StopKind.FUEL, sure), self.inp), ())

    def test_no_hours_claim_for_rest_and_overnight(self) -> None:
        """E-1: open-air rest areas and hotels (confirmed by the booking) get no hours line."""
        self.assertEqual(
            unknown_facts(self.stop(StopKind.REST, make_place(type=PlaceType.REST)), self.inp), ()
        )
        hotel = make_place(type=PlaceType.LODGING)
        self.assertEqual(unknown_facts(self.stop(StopKind.OVERNIGHT, hotel), self.inp), ())
        anchor = PlannedStop(StopKind.START, 0.0, "старт", LatLon(56, 38))
        self.assertEqual(unknown_facts(anchor, self.inp), ())

    def test_render_and_codec(self) -> None:
        """Curated places get the row line; open data keeps only its marker; both carry the fact keys."""
        slot = Slot(
            datetime(2026, 10, 24, 10, 0, tzinfo=MSK), datetime(2026, 10, 24, 11, 0, tzinfo=MSK), 60.0
        )
        curated = render_stop(self.stop(StopKind.SIGHT, make_place()), slot, 1, 1, 2, 10, self.inp, self.ctx)
        self.assertEqual(curated.unknown_facts, ("hours", "ticket", "dogs"))
        self.assertIsNotNone(curated.unknown_ru)
        osm = render_stop(
            self.stop(StopKind.SIGHT, make_place(source=Source.OSM)), slot, 1, 1, 2, 10, self.inp, self.ctx
        )
        self.assertEqual(osm.unknown_facts, ("hours", "ticket", "dogs"))
        self.assertIsNone(osm.unknown_ru)
        j = codec.stop_to_json(curated)
        self.assertEqual(j["unknownFacts"], ["hours", "ticket", "dogs"])
        back = codec.stop_from_json(j)
        self.assertEqual((back.unknown_facts, back.unknown_ru), (curated.unknown_facts, curated.unknown_ru))
        known = render_stop(
            self.stop(
                StopKind.SIGHT, make_place(opening_hours="24/7", tags={Tag.FREE_ENTRY, Tag.DOGS_ALLOWED})
            ),
            slot,
            1,
            1,
            2,
            10,
            self.inp,
            self.ctx,
        )
        self.assertNotIn("unknownFacts", codec.stop_to_json(known))  # other stops keep their bytes
        old = {k: v for k, v in j.items() if k not in ("unknownFacts", "unknownRu")}
        self.assertEqual(codec.stop_from_json(old).unknown_facts, ())  # trips saved before ADR-0019


def cost_input(sights: tuple[SightInput, ...] = (), hotel: Any = None) -> CostInput:
    price = RegionPrice("RU-MOS", FuelType.AI95, Decimal("62.00"), date(2026, 10, 1))
    nights: tuple[NightInput, ...] = ()
    if hotel is not None:
        nights = (NightInput("d1s05", 1, "Ярославль", hotel, (hotel,), 4000, 900),)
    return CostInput(
        regions=(RegionKm("RU-MOS", "Московская область", 100.0, price),),
        tolls=(),
        nights=nights,
        days=(),
        sights=sights,
        defaults_as_of=date(2026, 10, 1),
    )


class CostTest(unittest.TestCase):
    def setUp(self) -> None:
        ctx, _ = make_ctx()
        self.inp = normalize_input(trip(), ctx)

    def tickets(self, *places: Any) -> Any:
        sights = tuple(SightInput(f"d1s0{i + 2}", p) for i, p in enumerate(places))
        return build_units(cost_input(sights), self.inp, CFG)

    def test_unknown_ticket_named_not_free(self) -> None:
        """E-2: 0 ₽ in the sums, named in the line, and the total says it leaves the ticket out."""
        units = self.tickets(make_place("u", name_ru="Усадьба"))
        self.assertEqual([(t.adult_rub, t.known) for t in units.tickets], [(0, False)])
        res = recompute(units, self.inp.crew, True, None)
        line = next(x for x in res.lines if x.key is CostKey.TICKETS)
        self.assertEqual((line.rub, line.formula_ru), (0, "1 место — цена билета неизвестна"))
        self.assertEqual(res.total_note_ru, "Без билетов в 1 место — цена неизвестна")

    def test_paid_and_unknown(self) -> None:
        units = self.tickets(make_place("p", ticket_adult_rub=300), make_place("u"), make_place("v"))
        res = recompute(units, self.inp.crew, True, None)
        line = next(x for x in res.lines if x.key is CostKey.TICKETS)
        self.assertEqual(line.rub, 600)
        self.assertTrue(line.formula_ru.endswith(" + ещё 2 — цена билета неизвестна"), line.formula_ru)
        self.assertEqual(len(line.breakdown), 1)  # only the priced place has a ₽ row
        self.assertEqual(res.total_note_ru, "Без билетов в 2 места — цена неизвестна")

    def test_free_only_is_free(self) -> None:
        res = recompute(self.tickets(make_place("f", tags={Tag.FREE_ENTRY})), self.inp.crew, True, None)
        self.assertEqual(next(x for x in res.lines if x.key is CostKey.TICKETS).formula_ru, "вход свободный")
        self.assertIsNone(res.total_note_ru)

    def test_replace_brings_its_unknown_ticket(self) -> None:
        """E-2 offline: an alternative sight with an unknown price replaces a paid one → named, not free."""
        units = self.tickets(make_place("p", ticket_adult_rub=300))
        alt = AltUnits(0.0, "RU-MOS", None, 0, 0, "Усадьба", "u", ticket_known=False)
        res = recompute(units, self.inp.crew, True, None, CostOverrides(replaced={"d1s02": alt}))
        self.assertEqual(res.total_note_ru, "Без билетов в 1 место — цена неизвестна")
        j = codec.alt_units_to_json(alt)
        self.assertIs(j["ticketKnown"], False)
        self.assertFalse(codec.alt_units_from_json(j).ticket_known)
        self.assertNotIn("ticketKnown", codec.alt_units_to_json(dataclasses.replace(alt, ticket_known=True)))

    def test_unknown_breakfast_is_costed(self) -> None:
        """E-3: a hotel without a confirmed breakfast gets the morning meal in the food line."""
        for flag, bf in ((None, False), (False, False), (True, True)):
            with self.subTest(flag=flag):
                hotel = make_place("h", PlaceType.LODGING, price_night_rub=4000, breakfast_included=flag)
                units = build_units(cost_input(hotel=hotel), self.inp, CFG)
                self.assertEqual(units.nights[0].breakfast_included, bf)
                self.assertEqual(units.nights[0].options[0].breakfast_included, bf)
                res = recompute(units, self.inp.crew, True, None)
                food = next(x for x in res.lines if x.key is CostKey.FOOD)
                self.assertEqual(food.rub, 0 if bf else 2 * 540)  # 2 adults × 0.6 × 900

    def test_codec_units_and_cost(self) -> None:
        units = self.tickets(make_place("u"))
        res = recompute(units, self.inp.crew, True, None)
        j = codec.cost_to_json(res)
        self.assertIs(j["units"]["tickets"][0]["known"], False)
        self.assertEqual(j["totalNoteRu"], res.total_note_ru)
        back = codec.cost_from_json(j)
        self.assertEqual((back.total_note_ru, back.units.tickets[0].known), (res.total_note_ru, False))
        # a unit without the breakfast flag (older JSON) never claims the breakfast
        night = codec.units_to_json(
            build_units(cost_input(hotel=make_place("h", PlaceType.LODGING)), self.inp, CFG)
        )
        stripped = copy.deepcopy(night)
        del stripped["nights"][0]["options"][0]["breakfastIncluded"]
        self.assertFalse(codec.units_from_json(stripped).nights[0].options[0].breakfast_included)
        self.assertNotIn(
            "totalNoteRu", codec.cost_to_json(recompute(self.tickets(), self.inp.crew, True, None))
        )


class AdapterTest(unittest.TestCase):
    def test_fixture_world_tri_states(self) -> None:
        """The fixture loader reads absent rating / breakfast as unknown and the new tri-state keys."""
        d = mini()
        p = d["places"][0]
        p.pop("rating", None)
        p.pop("breakfastIncluded", None)
        p.update({"tagsNo": ["dogs_allowed"], "fuelKinds": ["ai95"], "fuelKindsNo": ["dt"]})
        w = FakeWorld.from_dict(d)
        place = w.places[p["id"]]
        self.assertIsNone(place.rating_internal)
        self.assertIsNone(place.breakfast_included)
        self.assertEqual(place.tags_no, frozenset({Tag.DOGS_ALLOWED}))
        self.assertEqual(
            (place.fuel_kinds, place.fuel_kinds_no), (frozenset({FuelType.AI95}), frozenset({FuelType.DT}))
        )
        for key, bad, expect in (("tagsNo", ["cats"], "tagsNo[0]"), ("fuelKinds", ["ai100"], "fuelKinds")):
            with self.subTest(key=key):
                d2 = mini()
                d2["places"][0][key] = bad
                with self.assertRaises(ValueError) as cm:
                    FakeWorld.from_dict(d2)
                self.assertIn(expect, str(cm.exception))

    def test_catalogue_ticket_rule(self) -> None:
        """E-2: OSM fee=no is free, a kind default is an estimate, a free kind is free; else unknown."""

        def poi(kind: str, fee: bool | None) -> CatPoi:
            return CatPoi("Q1", "Место", None, kind, LatLon(56.0, 38.0), "Q2", 0, False, None, None, fee=fee)

        self.assertEqual(poi_ticket(poi("attraction", False)), (None, True))
        self.assertEqual(poi_ticket(poi("museum", None)), ((400, 200), False))
        self.assertEqual(poi_ticket(poi("museum", True)), ((400, 200), False))
        self.assertEqual(poi_ticket(poi("park", None)), (None, True))
        self.assertEqual(poi_ticket(poi("park", True)), (None, False))
        self.assertEqual(poi_ticket(poi("attraction", None)), (None, False))


if __name__ == "__main__":
    unittest.main()
