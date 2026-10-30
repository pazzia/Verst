"""ARCH-301 / ADR-0011: the budget fitter (ladder, tolerance, no-fit options, alternative flags, rooms)."""

from __future__ import annotations

import json
import unittest
from typing import Any

from tests.unit.test_mobile import call, load_worlds
from verst_planner import fit, mobile
from verst_planner.domain.enums import PlaceStatus, PlaceType, Source, Tag
from verst_planner.domain.errors import PlanCancelled
from verst_planner.domain.model import Crew, LatLon, PartnerIds, Place
from verst_planner.domain.rooms import family_price, room_plan
from verst_planner.events import CancelToken

W = "central_russia_v1"
MOSCOW = {"lat": 55.7558, "lon": 37.6173, "label": "Москва"}
NN = {"lat": 56.3269, "lon": 44.0059, "label": "Нижний Новгород"}
VGG = {"lat": 48.708, "lon": 44.5133, "label": "Волгоград"}


def trip(dest: dict[str, Any] | None = None, rr: str | None = None, **kw: Any) -> str:
    d: dict[str, Any] = {"origin": MOSCOW, "crew": {"adults": 3, "children": 1, "dog": False}, "dailyKm": 300}
    d["startAt"] = "2026-11-07T08:00"
    if rr:
        d["readyRouteId"] = rr
    else:
        d["destination"] = dest or NN
    d.update(kw)
    return json.dumps(d)


def plan(inp: str) -> dict[str, Any]:
    result: dict[str, Any] = call(mobile.plan(W, "fit", inp, None))
    return result


class FitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_worlds()
        call(mobile.set_clock("golden"))

    @classmethod
    def tearDownClass(cls) -> None:
        call(mobile.set_clock("system"))

    def test_tolerance(self) -> None:
        self.assertEqual(fit.allowed_rub(30000), 31500)
        self.assertEqual(fit.allowed_rub(100000), 103000)  # capped at 3 000
        self.assertEqual(fit.allowed_rub(1000), 1050)

    def test_ceo_case_fits(self) -> None:
        r = plan(trip(rr="rr_golden_ring", crew={"adults": 4, "children": 1, "dog": True}, budget=30000))
        t = r["trip"]
        self.assertEqual(r["outcome"], "plan")
        self.assertLessEqual(t["cost"]["totalRub"], 31500)
        bf = t["budgetFit"]
        self.assertEqual(bf["status"], "fits")
        self.assertEqual(bf["variantOf"], "rr_golden_ring")
        self.assertEqual(bf["initialTotalRub"] - bf["totalRub"], sum(x["savedRub"] for x in bf["levers"]))
        est = call(
            mobile.estimate(
                W,
                "fit-e",
                trip(rr="rr_golden_ring", crew={"adults": 4, "children": 1, "dog": True}, budget=30000),
            )
        )
        self.assertEqual(
            (est["outcome"], est["budgetStatus"], est["totalRub"]), ("plan", "fits", t["cost"]["totalRub"])
        )

    def test_no_budget_and_within_budget_unchanged(self) -> None:
        plain = plan(trip())["trip"]
        self.assertNotIn("budgetFit", plain)
        roomy = plan(trip(budget=plain["cost"]["totalRub"] + 5000))["trip"]
        self.assertNotIn("budgetFit", roomy)
        self.assertEqual(roomy["cost"]["totalRub"], plain["cost"]["totalRub"])
        est = call(mobile.estimate(W, "fit-ok", trip(budget=plain["cost"]["totalRub"] + 5000)))
        self.assertEqual(est["budgetStatus"], "fits")
        self.assertIsNone(call(mobile.estimate(W, "fit-none", trip()))["budgetStatus"])

    def test_small_overrun_takes_the_earliest_step(self) -> None:
        plain = plan(trip())["trip"]["cost"]["totalRub"]
        cheap = plan(trip(budget=1000))  # no fit: its minimum tells the frugal total
        minimum = cheap["minimum"]["totalRub"]
        self.assertLess(minimum, plain)
        budget = minimum - 300  # not reachable, but within 5 % (and 3 000 ₽)
        r = plan(trip(budget=budget))
        bf = r["trip"]["budgetFit"]
        self.assertEqual(bf["status"], "small_overrun")
        self.assertLessEqual(r["trip"]["cost"]["totalRub"], fit.allowed_rub(budget))
        self.assertGreater(r["trip"]["cost"]["totalRub"], budget)

    def test_fewer_nights_lever(self) -> None:
        r = plan(trip(dailyKm=400, budget=9000))
        t = r["trip"]
        self.assertEqual(t["days"], 1)
        self.assertIn("fewer_nights", [x["code"] for x in t["budgetFit"]["levers"]])
        self.assertEqual(t["input"]["dailyKm"], 500)  # ≤ 1.3 x 400, rounded down to 50

    def test_no_fit_outcome_and_options(self) -> None:
        r = plan(trip(dest=VGG, budget=8000))
        self.assertEqual(r["outcome"], "no_fit")
        self.assertNotIn("trip", r)
        self.assertEqual(r["allowedRub"], 8400)
        self.assertIn("не помещается", r["textRu"])
        kinds = [o["kind"] for o in r["options"]]
        self.assertEqual(kinds[-1], "raise_budget")
        self.assertLessEqual(len(kinds), 3)
        raise_to = r["options"][-1]["budgetRub"]
        self.assertGreaterEqual(raise_to, r["minimum"]["totalRub"])
        self.assertEqual(raise_to % 1000, 0)
        cheaper = next(o for o in r["options"] if o["kind"] == "cheaper_route")
        self.assertIsNotNone(cheaper["destination"])
        self.assertLess(cheaper["totalRub"], r["minimum"]["totalRub"])
        est = call(mobile.estimate(W, "fit-nf", trip(dest=VGG, budget=8000)))
        self.assertEqual((est["outcome"], est["totalRub"]), ("no_fit", r["minimum"]["totalRub"]))
        fits = plan(trip(dest=VGG, budget=30000))
        shorten = next(o for o in fits["options"] if o["kind"] == "shorten")
        self.assertTrue(shorten["fits"])
        self.assertGreater(shorten["dailyKm"], 300)

    def test_ready_route_no_fit_offers_another_route(self) -> None:
        r = plan(trip(rr="rr_golden_ring", crew={"adults": 4, "children": 1, "dog": True}, budget=20000))
        self.assertEqual(r["outcome"], "no_fit")
        other = next(o for o in r["options"] if o["kind"] == "cheaper_route")
        self.assertIn(other["readyRouteId"], ("rr_tula_yasnaya", "rr_yaroslavl"))
        self.assertFalse(other["fits"])

    def test_breaks_budget_flags_and_replace_keeps_them(self) -> None:
        r = plan(trip(rr="rr_golden_ring", crew={"adults": 2, "children": 1, "dog": True}, budget=34000))
        t = r["trip"]
        alts = [a for d in t["daysList"] for s in d["stops"] for a in s["alternatives"]]
        flagged = [a for a in alts if a.get("breaksBudget")]
        self.assertTrue(alts)
        for a in flagged:
            self.assertGreater(t["cost"]["totalRub"] + a["deltaRub"], fit.allowed_rub(34000) - 200)
        stop = next(s for d in t["daysList"] for s in d["stops"] if s["alternatives"])
        after = call(
            mobile.replace_stop(
                W, json.dumps(t, ensure_ascii=False), stop["id"], stop["alternatives"][0]["id"]
            )
        )
        self.assertEqual(after["trip"]["input"]["budget"], 34000)

    def test_cancel_between_steps(self) -> None:
        tok = CancelToken()
        tok.cancel()

        class Env:
            def check_cancel(self) -> None:
                tok.check()

        with self.assertRaises(PlanCancelled):
            fit._try(Env(), None, fit.FRUGAL)  # type: ignore[arg-type]

    def test_fitted_plan_rejects_crew_patch(self) -> None:
        t = plan(trip(rr="rr_golden_ring", crew={"adults": 3, "children": 1, "dog": False}, budget=25000))
        trip_json = json.dumps(t.get("trip") or t["minimum"]["trip"], ensure_ascii=False)
        units = json.loads(trip_json)["cost"]["units"]
        explicit = any("rooms" in n or any("rooms" in o for o in n["options"]) for n in units["nights"])
        r = json.loads(mobile.patch_cost(W, trip_json, json.dumps({"crew": {"adults": 2, "children": 1}})))
        if explicit:
            self.assertEqual((r["ok"], r["error"]["reason"]), (False, "replan_required"))
        else:
            self.assertTrue(r["ok"])


def hotel(price: int, tags: frozenset[Tag], family: int | None = None) -> Place:
    return Place(
        id="h",
        type=PlaceType.LODGING,
        name_ru="Отель",
        point=LatLon(57.0, 39.0),
        address=None,
        region_code="RU-YAR",
        town_id=None,
        opening_hours=None,
        dwell_min=None,
        avg_check_rub=None,
        price_night_rub=price,
        ticket_adult_rub=None,
        ticket_child_rub=None,
        rating_internal=4.0,
        tags=tags,
        description_ru=None,
        partner_ids=PartnerIds(None, None),
        source=Source.CURATED,
        verified_at=None,
        status=PlaceStatus.LIVE,
        family_price_rub=family,
    )


class RoomPlanTest(unittest.TestCase):
    def test_family_rooms_only_when_cheaper(self) -> None:
        fam = hotel(5000, frozenset({Tag.FAMILY_ROOM}))
        three = Crew(3, 1, False)
        self.assertEqual(room_plan(fam, three, False), (2, 5000, False))
        self.assertEqual(room_plan(fam, three, True), (1, 7000, True))  # 1 x 7 000 < 2 x 5 000
        self.assertEqual(
            room_plan(fam, Crew(4, 1, False), True), (2, 5000, False)
        )  # 2 family rooms cost more
        self.assertEqual(room_plan(hotel(5000, frozenset()), three, True), (2, 5000, False))
        self.assertEqual(family_price(hotel(5000, frozenset({Tag.FAMILY_ROOM}), 6500)), 6500)
        self.assertEqual(room_plan(hotel(0, frozenset({Tag.FAMILY_ROOM})), three, True), (2, 0, False))


if __name__ == "__main__":
    unittest.main()
