"""DEV-111: the app-facing engine API `verst_planner.mobile` (M§5.1)."""

from __future__ import annotations

import io
import json
import threading
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from typing import Any

from tests.helpers import PLANNER_ROOT, WORLDS
from verst_planner import mobile
from verst_planner.domain import codec

GOLDEN = PLANNER_ROOT / "tests" / "golden"
CONTRACTS = PLANNER_ROOT.parents[1] / "docs" / "contracts"
MOSCOW = (55.7558, 37.6173)
KAZAN = (55.7963, 49.1088)


def call(envelope: str) -> Any:
    body = json.loads(envelope)
    assert body["ok"], body
    return body["result"]


def fail(envelope: str) -> dict[str, Any]:
    body = json.loads(envelope)
    assert not body["ok"], body
    assert isinstance(body["ms"], int)
    err: dict[str, Any] = body["error"]
    return err


def case(cid: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(next((GOLDEN / "cases").glob(f"{cid}_*.json")).read_text("utf-8"))
    return data


def load_worlds() -> None:
    for name in ("central_russia_v1", "edge_cases_v1"):
        call(mobile.load_world((WORLDS / f"{name}.json").read_text("utf-8")))


class Recorder:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def onEvent(self, event_json: str) -> None:
        self.events.append(json.loads(event_json))


def golden_plan(cid: str) -> dict[str, Any]:
    c = case(cid)
    call(mobile.set_clock(c["clock"]))
    try:
        result: dict[str, Any] = call(mobile.plan(c["world"], f"t-{cid}", json.dumps(c["input"]), None))
    finally:
        call(mobile.set_clock("system"))
    return result


class MobileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_worlds()

    def test_envelope_ok_and_error(self) -> None:
        envelopes = [
            mobile.selfcheck(),
            mobile.set_clock("golden"),
            mobile.suggest("central_russia_v1", "Тул", None, None, 3),
            mobile.popular("central_russia_v1", 3),
            mobile.reverse("central_russia_v1", *MOSCOW),
            mobile.ready_routes("central_russia_v1", *MOSCOW, 50, 20),
            mobile.cancel("nothing"),
            mobile.suggest("nope_world", "Тул", None, None, 3),
            mobile.set_clock("system"),
        ]
        for e in envelopes:
            body = json.loads(e)
            self.assertIn(body["ok"], (True, False))
            self.assertIsInstance(body["ms"], int)
            self.assertIn("result" if body["ok"] else "error", body)
        self.assertEqual(fail(envelopes[7])["code"], "NO_WORLD")

    def test_never_raises(self) -> None:
        garbage = [None, "", "{", "[]", "42", '{"x": 1}', 17]
        calls = [
            lambda g: mobile.load_world(g),
            lambda g: mobile.set_clock(g),
            lambda g: mobile.suggest(g, g, g, g, g),
            lambda g: mobile.popular("central_russia_v1", g),
            lambda g: mobile.reverse("central_russia_v1", g, 1),
            lambda g: mobile.ready_routes("central_russia_v1", g, g, g, g),
            lambda g: mobile.plan("central_russia_v1", "g", g, None),
            lambda g: mobile.replace_stop("central_russia_v1", g, "s", "a"),
            lambda g: mobile.patch_cost("central_russia_v1", g, g),
            lambda g: mobile.share_text(g),
            lambda g: mobile.golden_snapshot(g),
        ]
        with redirect_stderr(io.StringIO()):
            for fn in calls:
                for g in garbage:
                    body = json.loads(fn(g))
                    if not body["ok"]:
                        self.assertIn(
                            body["error"]["code"], ("INVALID_INPUT", "INTERNAL", "NO_WORLD"), (fn, g, body)
                        )
        call(mobile.set_clock("system"))

    def test_load_world_both(self) -> None:
        central = call(mobile.load_world((WORLDS / "central_russia_v1.json").read_text("utf-8")))
        edge = call(mobile.load_world((WORLDS / "edge_cases_v1.json").read_text("utf-8")))
        self.assertEqual(
            (central["id"], central["towns"], central["readyRoutes"]), ("central_russia_v1", 41, 3)
        )
        self.assertEqual(central["places"], 426)
        self.assertEqual((edge["id"], edge["asOf"]), ("edge_cases_v1", "2026-10-01"))
        self.assertEqual(fail(mobile.load_world('{"id": "x"}'))["code"], "INVALID_INPUT")

    def test_selfcheck_tz(self) -> None:
        r = call(mobile.selfcheck())
        self.assertTrue(r["tz"]["Europe/Moscow"])
        self.assertTrue(r["tz"]["Europe/Volgograd"])
        self.assertTrue(r["resources"])
        self.assertEqual(r["python"].split(".")[0], "3")

    def test_suggest_yaro(self) -> None:
        r = call(mobile.suggest("central_russia_v1", "Яро", *MOSCOW, 6))
        self.assertEqual(
            (r[0]["name"], r[0]["kind"], r[0]["subtitle"], r[0]["id"]),
            ("Ярославль", "city", "город · Ярославская область", "t_yaroslavl"),
        )
        places = call(mobile.suggest("central_russia_v1", "лавра", *MOSCOW, 6))
        self.assertEqual(places[0]["kind"], "place")
        self.assertTrue(places[0]["subtitle"].startswith("место · "))
        self.assertEqual(call(mobile.suggest("central_russia_v1", "   ", None, None, 6)), [])

    def test_popular_excludes_origin(self) -> None:
        r = call(mobile.popular("central_russia_v1", 5))
        names = [x["name"] for x in r]
        self.assertEqual(len(names), 5)
        self.assertNotIn("Москва", names)
        self.assertEqual(names[0], "Казань")  # 1.3 M after Москва 13 M
        other = call(mobile.popular("central_russia_v1", 3, "t_kazan"))
        self.assertEqual(other[0]["name"], "Москва")

    def test_reverse(self) -> None:
        self.assertEqual(
            call(mobile.reverse("central_russia_v1", *MOSCOW)),
            {"name": "Москва", "subtitle": "город · Москва"},
        )
        self.assertIsNone(call(mobile.reverse("central_russia_v1", 60.0, 30.0)))

    def test_ready_routes_moscow(self) -> None:
        r = call(mobile.ready_routes("central_russia_v1", *MOSCOW, 50, 20))
        self.assertEqual(len(r), 3)
        from tests.helpers import _load_world

        rr = _load_world(str(WORLDS / "central_russia_v1.json")).ready_routes
        want = sorted(rr.values(), key=lambda x: (x.km_sign, x.sort, x.id))
        self.assertEqual([x["id"] for x in r], [x.id for x in want])
        self.assertTrue(all(x["bearing8"] in ("N", "NE", "E", "SE", "S", "SW", "W", "NW") for x in r))
        ring = next(x for x in r if x["id"] == "rr_golden_ring")
        self.assertEqual(ring["bearing8"], "NE")  # Москва → Сергиев Посад ≈ 27° (sector NE = [22.5, 67.5))
        tula = next(x for x in r if x["id"] == "rr_tula_yasnaya")
        self.assertEqual(tula["bearing8"], "S")

    def test_ready_routes_kazan_empty(self) -> None:
        self.assertEqual(call(mobile.ready_routes("central_russia_v1", *KAZAN, 50, 20)), [])

    def test_plan_events_order(self) -> None:
        c = case("G01")
        rec = Recorder()
        call(mobile.set_clock(c["clock"]))
        try:
            r = call(mobile.plan(c["world"], "ev", json.dumps(c["input"]), rec))
        finally:
            call(mobile.set_clock("system"))
        stages = [e for e in rec.events if e["event"] == "stage"]
        self.assertEqual((stages[0]["key"], stages[0]["progress"]), ("split", 0.05))
        self.assertEqual(stages[-1]["key"], "cost")
        stops = [e for e in rec.events if e["event"] == "stop" and not e["stop"]["provisional"]]
        self.assertEqual(len(stops), sum(len(d["stops"]) for d in r["trip"]["daysList"]))
        self.assertIn("engineState", r["trip"])
        self.assertTrue(r["shareText"].startswith("Москва → Ярославль"))

    def test_plan_matches_golden_all(self) -> None:
        checked = 0
        for path in sorted((GOLDEN / "cases").glob("G*.json")):
            snap = list((GOLDEN / "snapshots").glob(f"{path.stem}.json"))
            if not snap:
                continue
            text = call(mobile.golden_snapshot(path.read_text("utf-8")))
            with self.subTest(case=path.stem):
                self.assertEqual(text, snap[0].read_text("utf-8"))
            checked += 1
        self.assertEqual(checked, 10)

    def test_plan_errors(self) -> None:
        err = fail(mobile.golden_snapshot(json.dumps(case("G09"))))
        self.assertEqual((err["code"], err["pointIndex"]), ("UNREACHABLE", 1))
        self.assertEqual(fail(mobile.golden_snapshot(json.dumps(case("G10"))))["code"], "TOO_SHORT")
        bad = dict(case("G01")["input"], dailyKm=123)
        err = fail(mobile.plan("central_russia_v1", "bad", json.dumps(bad), None))
        self.assertEqual(
            (err["code"], err["field"], err["reason"]), ("INVALID_INPUT", "dailyKm", "out_of_range")
        )

    def test_cancel_from_other_thread(self) -> None:
        first = threading.Event()
        release = threading.Event()

        class Blocking:
            def onEvent(self, event_json: str) -> None:
                if not first.is_set():
                    first.set()
                    release.wait(10)

        c = case("G03")
        out: dict[str, str] = {}
        t = threading.Thread(
            target=lambda: out.setdefault(
                "r", mobile.plan(c["world"], "req-1", json.dumps(c["input"]), Blocking())
            )
        )
        t.start()
        self.assertTrue(first.wait(10))
        self.assertEqual(call(mobile.cancel("req-1")), {"cancelled": True})
        release.set()
        t.join(30)
        self.assertEqual(fail(out["r"])["code"], "CANCELLED")
        self.assertEqual(call(mobile.cancel("req-1")), {"cancelled": False})  # unregistered after the run

    def test_replace_roundtrip(self) -> None:
        from tests.golden.test_golden import load_case, run_case
        from tests.helpers import make_planner

        r = golden_plan("G02")
        trip = r["trip"]
        stop = next(s for d in trip["daysList"] for s in d["stops"] if s["alternatives"])
        alt = stop["alternatives"][0]
        got = call(mobile.replace_stop("central_russia_v1", json.dumps(trip), stop["id"], alt["id"]))
        plan, *_ = run_case(load_case(next((GOLDEN / "cases").glob("G02_*.json"))))
        planner, _ = make_planner()
        want = planner.replace_stop(plan, stop["id"], alt["id"])
        self.assertEqual(
            json.dumps(got["trip"], sort_keys=True, ensure_ascii=False),
            json.dumps(codec.plan_to_json(want, public=False), sort_keys=True, ensure_ascii=False),
        )
        err = fail(mobile.replace_stop("central_russia_v1", json.dumps(trip), "d9s99", alt["id"]))
        self.assertEqual(err["code"], "NOT_FOUND")

    def test_patch_cost_reserve_and_hotel(self) -> None:
        trip = golden_plan("G02")["trip"]
        off = call(mobile.patch_cost("central_russia_v1", json.dumps(trip), json.dumps({"reserveOn": False})))
        self.assertFalse(off["trip"]["cost"]["reserveOn"])
        self.assertLess(off["trip"]["cost"]["totalRub"], trip["cost"]["totalRub"])
        night = next(
            s for d in trip["daysList"] for s in d["stops"] if s["kind"] == "overnight" and s["hotelOptions"]
        )
        options = [h for h in night["hotelOptions"] if h["placeId"] != night["selectedHotelId"]]
        if options:
            patch = {"hotelChoice": {"stopId": night["id"], "placeId": options[0]["placeId"]}}
            got = call(mobile.patch_cost("central_russia_v1", json.dumps(trip), json.dumps(patch)))
            n2 = next(s for d in got["trip"]["daysList"] for s in d["stops"] if s["id"] == night["id"])
            self.assertEqual(n2["selectedHotelId"], options[0]["placeId"])
        nob = call(mobile.patch_cost("central_russia_v1", json.dumps(trip), json.dumps({"budget": None})))
        self.assertIsNone(nob["trip"]["cost"]["budgetRub"])
        crew = {"crew": {"adults": 3, "children": 1, "dog": True}}
        more = call(mobile.patch_cost("central_russia_v1", json.dumps(trip), json.dumps(crew)))
        self.assertGreater(more["trip"]["cost"]["totalRub"], trip["cost"]["totalRub"])
        err = fail(
            mobile.patch_cost("central_russia_v1", json.dumps(trip), json.dumps({"crew": {"adults": 2}}))
        )
        self.assertEqual((err["code"], err["reason"]), ("INVALID_INPUT", "replan_required"))
        self.assertEqual(
            fail(mobile.patch_cost("central_russia_v1", json.dumps(trip), '{"x": 1}'))["field"], "patch"
        )

    def test_share_text_matches_contract(self) -> None:
        trip = golden_plan("G02")["trip"]
        want = json.loads((CONTRACTS / "share-text" / "G02.json").read_text("utf-8"))["text"]
        self.assertEqual(call(mobile.share_text(json.dumps(trip))), want)

    def test_listener_exception_swallowed(self) -> None:
        calls: list[int] = []

        class Broken:
            def onEvent(self, event_json: str) -> None:
                calls.append(1)
                raise RuntimeError("listener bug")

        c = case("G08")
        err = io.StringIO()
        call(mobile.set_clock(c["clock"]))
        try:
            with redirect_stderr(err):
                r = call(mobile.plan(c["world"], "lx", json.dumps(c["input"]), Broken()))
        finally:
            call(mobile.set_clock("system"))
        self.assertGreater(len(calls), 3)  # still called for every event
        self.assertEqual(err.getvalue().count("listener failed"), 1)
        self.assertIn("trip", r)

    def test_set_clock(self) -> None:
        self.assertEqual(call(mobile.set_clock("golden"))["now"], "2026-10-23T06:00:00+00:00")
        self.assertEqual(fail(mobile.set_clock("2026-10-24T08:00"))["code"], "INVALID_INPUT")
        now = call(mobile.set_clock("system"))["now"]
        self.assertTrue(now.endswith("+00:00"))

    def test_internal_error_has_traceback(self) -> None:
        def boom() -> None:
            raise RuntimeError("drill")

        with redirect_stderr(io.StringIO()) as err:
            body = json.loads(mobile._envelope(boom))
        self.assertEqual(body["error"]["code"], "INTERNAL")
        self.assertIn("RuntimeError: drill", body["error"]["detail"])
        self.assertIn("RuntimeError: drill", err.getvalue())

    def test_selftest_cli(self) -> None:
        out = io.StringIO()
        texts = [(WORLDS / f"{n}.json").read_text("utf-8") for n in ("central_russia_v1", "edge_cases_v1")]
        self.assertEqual(mobile.selftest(texts, out), 0)
        lines = out.getvalue().splitlines()
        self.assertTrue(all(line.startswith("OK ") for line in lines))
        self.assertEqual(sum(1 for line in lines if line.startswith("OK plan ")), 2)
        self.assertEqual(mobile.selftest(['{"broken": 1}'], io.StringIO()), 1)

    def test_main_default_worlds(self) -> None:
        out = io.StringIO()
        from contextlib import redirect_stdout

        with redirect_stdout(out):
            self.assertEqual(mobile.main(["selftest"]), 0)
        self.assertIn("OK golden_snapshot", out.getvalue())
        self.assertTrue(all(Path(p).is_file() for p in mobile._default_world_paths()))


if __name__ == "__main__":
    unittest.main()
