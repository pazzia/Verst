import dataclasses
import unittest

from tests.helpers import make_place, sample_plan
from verst_planner.domain import errors
from verst_planner.domain.enums import (
    SIGN_BY_KIND,
    CostKey,
    FuelType,
    Meal,
    Mood,
    OvernightFallback,
    PlaceStatus,
    PlaceType,
    RoadClass,
    SignType,
    Source,
    StageKey,
    StopKind,
    Tag,
    WarningCode,
)
from verst_planner.domain.model import Crew, LatLon, Vehicle


class EnumTest(unittest.TestCase):
    def test_enum_wire_values(self) -> None:
        expected = {
            PlaceType: ["sight", "food", "fuel", "rest", "lodging"],
            Source: ["curated", "osm", "partner"],
            PlaceStatus: ["draft", "live", "hidden"],
            Mood: ["calm", "more_stops", "just_drive", "fun"],
            FuelType: ["ai92", "ai95", "dt"],
            RoadClass: ["motorway", "trunk", "primary", "secondary", "other"],
            StopKind: ["start", "sight", "food", "fuel", "rest", "overnight", "via", "finish"],
            SignType: ["city", "tourist", "fuel", "food", "rest", "hotel"],
            Meal: ["breakfast", "lunch", "dinner"],
            OvernightFallback: ["none", "template", "widened", "extra_day", "no_hotel"],
            WarningCode: [
                "NO_LODGING",
                "FUEL_GAP",
                "DAY_OVER_BUDGET",
                "TOLLS_UNAVOIDABLE",
                "UNVERIFIED_PLACES",
                "STOP_CLOSED",
            ],
            StageKey: ["split", "lodging", "hours", "fuel", "cost", "budget"],
            CostKey: ["fuel", "tolls", "lodging", "food", "tickets", "parking", "reserve"],
        }
        for enum_cls, values in expected.items():
            with self.subTest(enum=enum_cls.__name__):
                self.assertEqual([m.value for m in enum_cls], values)
        self.assertEqual(Tag.H24.value, "24h")

    def test_tag_list_is_closed(self) -> None:
        spec_tags = [
            "dogs_allowed",
            "kids_menu",
            "playground",
            "family_room",
            "parking",
            "parking_guarded",
            "ev_charger",
            "wc",
            "cafe_at_fuel",
            "24h",
            "view",
            "walk",
            "museum",
            "kremlin",
            "monastery",
            "evening",
            "free_entry",
            "cash_only",
        ]
        self.assertEqual(len(Tag), 18)
        self.assertEqual([t.value for t in Tag], spec_tags)

    def test_sign_mapping(self) -> None:
        self.assertEqual(set(SIGN_BY_KIND), set(StopKind))
        self.assertEqual(SIGN_BY_KIND[StopKind.OVERNIGHT], SignType.HOTEL)
        self.assertEqual(SIGN_BY_KIND[StopKind.VIA], SignType.CITY)


class ModelTest(unittest.TestCase):
    def test_models_frozen(self) -> None:
        place = make_place()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            place.name_ru = "x"  # type: ignore[misc]
        plan = sample_plan()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            plan.km = 1  # type: ignore[misc]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            plan.days_list[0].stops[0].kind = StopKind.FINISH  # type: ignore[misc]

    def test_slots(self) -> None:
        self.assertFalse(hasattr(LatLon(1.0, 2.0), "__dict__"))

    def test_crew_validation(self) -> None:
        for kwargs in (
            {"adults": 0, "children": 0, "dog": False},
            {"adults": 8, "children": 0, "dog": False},
            {"adults": 2, "children": 6, "dog": False},
            {"adults": 2, "children": 2, "dog": False, "child_ages": (5,)},
            {"adults": 2, "children": 1, "dog": False, "child_ages": (18,)},
        ):
            with (
                self.subTest(**{k: str(v) for k, v in kwargs.items()}),
                self.assertRaises(errors.InvalidInput),
            ):
                Crew(**kwargs)  # type: ignore[arg-type]
        self.assertEqual(Crew(7, 5, True).people, 12)
        self.assertEqual(Crew(1, 2, False, (3, 17)).child_ages, (3, 17))

    def test_vehicle_and_latlon_validation(self) -> None:
        with self.assertRaises(errors.InvalidInput):
            Vehicle(consumption_l_per_100km=3.9)
        with self.assertRaises(errors.InvalidInput):
            Vehicle(tank_l=151)
        with self.assertRaises(errors.InvalidInput):
            LatLon(91.0, 0.0)
        with self.assertRaises(errors.InvalidInput):
            LatLon(0.0, -181.0)

    def test_error_codes(self) -> None:
        self.assertEqual(errors.InvalidInput("f", "r").code, "INVALID_INPUT")
        self.assertEqual(errors.Unreachable(1).code, "UNREACHABLE")
        self.assertEqual(errors.TooShort(10.0).code, "TOO_SHORT")
        self.assertEqual(errors.UpstreamUnavailable("graphhopper").code, "UPSTREAM")
        self.assertEqual(errors.NotFound("trip", "x").code, "NOT_FOUND")
        self.assertEqual(errors.PlanCancelled().code, "CANCELLED")
        self.assertTrue(issubclass(errors.OpeningHoursParseError, ValueError))
        e = errors.Unreachable(2, 2.5)
        self.assertEqual((e.point_index, e.snap_km), (2, 2.5))
        self.assertEqual(errors.InvalidInput("crew.adults", "out_of_range").field, "crew.adults")


if __name__ == "__main__":
    unittest.main()
