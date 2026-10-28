import json
import unittest
from datetime import time
from decimal import Decimal

from verst_planner.config import RESOURCES, PlannerConfig
from verst_planner.domain.enums import Mood


class ConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = PlannerConfig.default()

    def test_defaults_match_spec(self) -> None:
        c = self.cfg
        s = c.overnight_score
        self.assertEqual((s.w_h, s.w_q, s.w_e, s.w_km, s.w_detour), (3.0, 2.0, 1.5, 2.0, 1.0))
        self.assertEqual(s.h_cap, 5)
        self.assertEqual((s.h_no_parking_weight, s.family_room_min_people), (0.5, 3))
        self.assertEqual((c.split.window_lo, c.split.window_hi), (0.70, 1.05))
        self.assertEqual((c.split.hard_cap, c.split.widened_lo, c.split.widened_hi), (1.05, 0.40, 1.30))
        self.assertEqual((c.split.template_hi, c.split.template_lo), (1.05, 0.90))
        r = c.rest_interval_min
        self.assertEqual((r.calm, r.more_stops, r.just_drive), (120, 90, 180))
        self.assertEqual((c.fuel.usable_frac, c.fuel.lookahead_km), (0.8, 40))
        d = c.dwell_min
        self.assertEqual(
            (d.coffee, d.fuel, d.fuel_coffee, d.lunch, d.sight_default), (15, 10, 15, 60, 60)
        )
        # CEO 2026-10-29 «Как едем»: long breaks for «Спокойно»
        rd = c.rest_dwell_min
        self.assertEqual((rd.calm, rd.more_stops, rd.just_drive, rd.fun), (30, 20, 20, 20))
        self.assertEqual(d.via, 30)
        self.assertEqual(c.lunch_window, (time(12, 0), time(14, 30)))
        self.assertEqual(c.lunch_sweet_spot, (time(12, 30), time(13, 30)))
        b = c.day_budget_min
        # CEO 2026-10-29: «Только доехать» the longest day, «Спокойно» the shortest
        self.assertEqual((b.calm, b.more_stops, b.just_drive, b.fun), (540, 600, 720, 660))
        k = c.corridor_km
        self.assertEqual((k.sight, k.food, k.fuel, k.rest), (15, 15, 15, 15))
        self.assertEqual((k.fuel_motorway, k.rest_motorway, k.town, k.lodging_from_town), (5, 5, 25, 10))
        self.assertEqual((c.alternatives.window_min, c.alternatives.max), (45, 3))
        self.assertEqual(c.cost.reserve_frac, Decimal("0.10"))
        self.assertEqual((c.cost.line_step, c.cost.total_step), (10, 100))
        self.assertEqual(c.cost.child_food_weight_under7, Decimal("0.5"))
        self.assertEqual((c.cost.assumed_child_age, c.cost.breakfast_price_frac), (8, Decimal("0.6")))
        self.assertEqual(c.cost.dinner_last_day_after, time(19, 0))
        self.assertEqual(
            (c.snap_max_km, c.too_short_km, c.max_days, c.drive_time_factor), (2.0, 20.0, 14, 1.10)
        )
        self.assertEqual((c.day_start_first, c.day_start_next), (time(8, 0), time(9, 0)))
        self.assertEqual(c.detour.winding, 1.3)
        self.assertEqual((c.detour.speed_kmh, c.detour.access_min, c.detour.motorway_exit_min), (40, 2, 5))
        self.assertEqual(c.detour.on_road_km, 0.3)
        e = c.overnight_eta_allowance_min
        self.assertEqual((e.calm, e.more_stops, e.just_drive), (120, 150, 30))
        f = c.fuel
        self.assertEqual((f.start_frac, f.lookback_km, f.coincide_km), (1.0, 100, 2))
        self.assertEqual((f.evening_next_day_km, f.evening_window_km), (60, 40))
        self.assertEqual((f.skip_near_finish_frac, f.coffee_after_drive_min), (0.10, 60))
        rc = c.rest
        self.assertEqual((rc.window_before_min, rc.widen_before_min, rc.widen_after_min), (30, 60, 15))
        self.assertEqual((rc.min_remaining_drive_min, rc.break_min_dwell), (30, 15))
        self.assertEqual(c.sights.max_per_day.of(Mood.MORE_STOPS), 4)
        self.assertEqual(c.sights.min_score, 2.0)
        self.assertEqual(c.toll_night, (time(0, 0), time(6, 0)))

    def test_unknown_key_rejected(self) -> None:
        with self.assertRaises(ValueError) as cm:
            PlannerConfig.from_dict({"fuel": {"usable_frac": 0.7, "tank_magic": 1}})
        self.assertEqual(str(cm.exception), "unknown config key: fuel.tank_magic")
        with self.assertRaises(ValueError) as cm:
            PlannerConfig.from_dict({"nope": 1})
        self.assertEqual(str(cm.exception), "unknown config key: nope")
        with self.assertRaises(ValueError) as cm:
            PlannerConfig.from_dict({"sights": {"max_per_day": {"fast": 1}}})
        self.assertEqual(str(cm.exception), "unknown config key: sights.max_per_day.fast")

    def test_bad_types_rejected(self) -> None:
        for bad in (
            {"max_days": "x"},
            {"max_days": 1.5},
            {"lunch_window": ["12:00"]},
            {"day_start_next": "nine"},
            {"fuel": 3},
            {"max_days": True},
        ):
            with self.subTest(bad=json.dumps(bad)), self.assertRaises(ValueError):
                PlannerConfig.from_dict(bad)

    def test_partial_override(self) -> None:
        c = PlannerConfig.from_dict({"fuel": {"usable_frac": 0.7}, "day_budget_min": {"calm": 500}})
        self.assertEqual(c.fuel.usable_frac, 0.7)
        self.assertEqual(c.fuel.lookahead_km, 40)
        self.assertEqual(c.day_budget_min.calm, 500)
        self.assertEqual(c.day_budget_min.more_stops, 600)
        c2 = PlannerConfig.from_dict({"max_days": 10}, base=c)
        self.assertEqual((c2.max_days, c2.fuel.usable_frac, c2.day_budget_min.calm), (10, 0.7, 500))
        self.assertEqual(PlannerConfig.from_dict(self.cfg.to_dict()), self.cfg)

    def test_resource_matches_table_keys(self) -> None:
        with (RESOURCES / "planner_config.json").open(encoding="utf-8") as f:
            raw = json.load(f)
        self.assertEqual(set(raw), set(self.cfg.to_dict()))


if __name__ == "__main__":
    unittest.main()
