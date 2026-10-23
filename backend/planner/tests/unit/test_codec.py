import json
import unittest
from datetime import datetime

from tests.helpers import sample_normalized, sample_plan
from verst_planner.domain import codec
from verst_planner.domain.enums import FuelType, Mood
from verst_planner.domain.errors import InvalidInput
from verst_planner.domain.model import Crew, LatLon, PointInput, TripInput, Vehicle


class CodecTest(unittest.TestCase):
    def test_input_roundtrip(self) -> None:
        inp = TripInput(
            origin=PointInput(LatLon(55.7558, 37.6173), "Москва"),
            destination=PointInput(LatLon(48.708, 44.5133), "Волгоград", "pl_x", "t_volgograd"),
            vias=(PointInput(LatLon(52.7212, 41.4523), "Тамбов"),),
            ready_route_id=None,
            round_trip=None,
            crew=Crew(2, 1, True, (5,)),
            daily_km=500,
            budget_rub=60_000,
            vehicle=Vehicle(7.5, FuelType.DT, 60.0),
            start_at=datetime(2026, 10, 24, 7, 0),
            mood=Mood.CALM,
            avoid_tolls=True,
            reserve_on=False,
            simplify=True,
        )
        d = codec.input_to_json(inp)
        self.assertEqual(d["startAt"], "2026-10-24T07:00")
        self.assertEqual(d["vehicle"], {"consumption": 7.5, "fuelType": "dt", "tankL": 60.0})
        back = codec.input_from_json(json.loads(json.dumps(d)))
        self.assertEqual(back, inp)

    def test_input_minimal_defaults(self) -> None:
        inp = codec.input_from_json(
            {
                "origin": {"lat": 55.75, "lon": 37.61},
                "readyRouteId": "rr_x",
                "crew": {"adults": 2},
                "dailyKm": 300,
            }
        )
        self.assertIsNone(inp.destination)
        self.assertEqual(inp.vehicle, Vehicle())
        self.assertTrue(inp.reserve_on)
        self.assertIsNone(inp.mood)
        self.assertEqual(inp.crew, Crew(2, 0, False))

    def test_input_rejects_unknown_and_offsets(self) -> None:
        base = {"origin": {"lat": 55.75, "lon": 37.61}, "crew": {"adults": 2}, "dailyKm": 300}
        with self.assertRaises(InvalidInput) as cm:
            codec.input_from_json({**base, "foo": 1})
        self.assertEqual(cm.exception.field, "foo")
        with self.assertRaises(InvalidInput) as cm:
            codec.input_from_json({**base, "crew": {"adults": 2, "cats": 1}})
        self.assertEqual(cm.exception.field, "crew.cats")
        with self.assertRaises(InvalidInput):
            codec.input_from_json({**base, "startAt": "2026-10-24T07:00+03:00"})
        with self.assertRaises(InvalidInput):
            codec.input_from_json({**base, "mood": "fast"})
        with self.assertRaises(InvalidInput):
            codec.input_from_json({"crew": {"adults": 2}, "dailyKm": 300})

    def test_normalized_roundtrip(self) -> None:
        n = sample_normalized()
        d = codec.normalized_to_json(n)
        self.assertEqual((d["startAt"], d["tz"]), ("2026-10-24T08:00", "Europe/Moscow"))
        self.assertEqual(codec.normalized_from_json(d), n)

    def test_plan_roundtrip(self) -> None:
        plan = sample_plan()
        d = codec.plan_to_json(plan, public=False)
        text = json.dumps(d, ensure_ascii=False, sort_keys=True)
        back = codec.plan_from_json(json.loads(text))
        self.assertEqual(back, plan)
        self.assertEqual(
            json.dumps(codec.plan_to_json(back, public=False), ensure_ascii=False, sort_keys=True), text
        )

    def test_public_json_has_no_engine_state(self) -> None:
        plan = sample_plan()
        d = codec.plan_to_json(plan)
        self.assertNotIn("engineState", d)
        self.assertIn("engineState", codec.plan_to_json(plan, public=False))
        with self.assertRaises(ValueError):
            codec.plan_from_json(d)

    def test_wire_shape(self) -> None:
        d = codec.plan_to_json(sample_plan(), trip_id="trp_golden")
        for key in ("id", "title", "km", "days", "nights", "daysList", "cost", "reasons"):
            self.assertIn(key, d)
        self.assertEqual(d["id"], "trp_golden")
        stop = d["daysList"][0]["stops"][1]
        self.assertEqual(stop["arriveAt"], "2026-10-24T12:45")
        self.assertEqual(stop["kind"], "food")
        self.assertEqual(stop["tags"], ["kids_menu"])
        self.assertEqual(stop["alternatives"][0]["units"]["checkRub"], 700)
        units = d["cost"]["units"]
        self.assertEqual(units["fuel"]["regions"][0]["priceRub"], "61.20")
        self.assertEqual(units["reserveFrac"], "0.10")
        self.assertEqual(units["childFoodWeightUnder7"], "0.50")
        self.assertEqual(d["reasons"]["overnights"][0]["candidates"], ["Переславль-Залесский", "Ростов"])
        self.assertEqual(d["warnings"][0]["code"], "FUEL_GAP")
        self.assertEqual(d["cost"]["lines"][0]["key"], "fuel")


if __name__ == "__main__":
    unittest.main()
