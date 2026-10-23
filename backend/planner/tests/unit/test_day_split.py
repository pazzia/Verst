import random
import unittest

from tests.helpers import make_ctx, trip
from verst_planner.pipeline.base_route import build_base_route
from verst_planner.pipeline.corridor import build_corridor
from verst_planner.pipeline.day_split import n_days_for, split_days, template_fits
from verst_planner.pipeline.overnight import windows
from verst_planner.pipeline.resolve import normalize_input, resolve_points


class DaySplitTest(unittest.TestCase):
    def test_n_days(self) -> None:
        self.assertEqual(n_days_for(530, 300), 2)
        self.assertEqual(n_days_for(745, 300), 3)
        self.assertEqual(n_days_for(300, 300), 1)
        self.assertEqual(n_days_for(301, 300), 2)
        self.assertEqual(n_days_for(25, 300), 1)

    def test_window_bounds_property(self) -> None:
        ctx, _ = make_ctx()
        rng = random.Random(7)
        for _case in range(200):
            total = rng.uniform(100, 2500)
            daily = rng.randrange(150, 901, 50)
            n = n_days_for(total, daily)
            prev = 0.0
            for d in range(1, n):
                _t, lo, hi, lo2, hi2 = windows(prev, total, n, d, daily, ctx)
                with self.subTest(total=round(total, 1), daily=daily, day=d):
                    self.assertLessEqual(lo, hi + 1e-6)
                    self.assertLessEqual(lo2, lo + 1e-9)
                    self.assertGreaterEqual(hi2, hi - 1e-9)
                # adversarial picks: always at a window edge
                nxt = rng.choice((lo, hi, rng.uniform(lo, hi)))
                self.assertLessEqual(nxt - prev, 1.05 * daily + 1e-6)
                prev = nxt
            self.assertLessEqual(total - prev, 1.05 * daily + 1e-6)

    def _golden(self, daily_km: int) -> tuple[object, object, object, object]:
        ctx, _ = make_ctx()
        inp = normalize_input(trip(destination=None, ready_route_id="rr_golden_ring", daily_km=daily_km), ctx)
        pts = resolve_points(inp, ctx)
        route = build_base_route(pts, inp, ctx)
        corridor = build_corridor(route, inp, ctx)
        return ctx, inp, route, corridor

    def test_template_used_when_fits(self) -> None:
        ctx, inp, route, corridor = self._golden(300)
        assert ctx.ready_route is not None  # type: ignore[attr-defined]
        split = split_days(route, corridor, inp, ctx.ready_route, ctx)  # type: ignore[arg-type,attr-defined]
        self.assertTrue(split.fixed)
        self.assertEqual(split.n_days, 3)
        self.assertEqual([t.town.id for t in split.nights], ["t_yaroslavl", "t_suzdal"])
        self.assertEqual([round(t.km_at) for t in split.nights], [263, 523])

    def test_template_rejected_when_day_over_105pct(self) -> None:
        ctx, inp, route, corridor = self._golden(200)
        rr = ctx.ready_route  # type: ignore[attr-defined]
        self.assertFalse(template_fits(rr, corridor, inp, ctx))  # type: ignore[arg-type]
        split = split_days(route, corridor, inp, rr, ctx)  # type: ignore[arg-type]
        self.assertFalse(split.fixed)
        self.assertEqual(split.n_days, 4)  # ceil(745 / 200)

    def test_template_rejected_when_too_few_days_allowed(self) -> None:
        # 600 km/day: every template day fits, but 3 days > ceil(745 / 540) = 2
        ctx, inp, _route, corridor = self._golden(600)
        self.assertFalse(template_fits(ctx.ready_route, corridor, inp, ctx))  # type: ignore[arg-type,attr-defined]


if __name__ == "__main__":
    unittest.main()
