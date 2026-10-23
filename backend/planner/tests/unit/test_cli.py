import io
import json
import tempfile
import unittest
from pathlib import Path

from tests.helpers import WORLDS
from verst_planner.cli import export_config_sql, main

INPUT = {
    "origin": {"lat": 55.7558, "lon": 37.6173, "label": "Москва"},
    "destination": {"lat": 57.6261, "lon": 39.8845, "label": "Ярославль"},
    "roundTrip": True,
    "crew": {"adults": 2, "children": 0, "dog": False},
    "dailyKm": 300,
    "startAt": "2026-10-24T08:00",
}


class CliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.input = Path(self.tmp.name) / "in.json"
        self.input.write_text(
            json.dumps({"clock": "2026-10-23T09:00:00+03:00", "input": INPUT}), encoding="utf-8"
        )

    def run_cli(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        code = main(list(args), out, err)
        return code, out.getvalue(), err.getvalue()

    def test_plan_prints_public_json_and_events(self) -> None:
        code, out, err = self.run_cli(
            "plan", "--world", str(WORLDS / "central_russia_v1.json"), "--input", str(self.input), "--events"
        )
        self.assertEqual(code, 0)
        plan = json.loads(out)
        self.assertEqual((plan["days"], plan["title"]), (2, "Москва → Ярославль → Москва"))
        self.assertNotIn("engineState", plan)
        self.assertIn("Ярославль", out)  # ensure_ascii=False
        events = [json.loads(line) for line in err.splitlines()]
        self.assertGreaterEqual(len(events), 5)
        self.assertEqual(events[0]["event"], "stage")
        self.assertEqual(events[-1]["event"], "stop")

    def test_plan_bare_input_and_out_file(self) -> None:
        bare = Path(self.tmp.name) / "bare.json"
        bare.write_text(json.dumps(INPUT), encoding="utf-8")
        target = Path(self.tmp.name) / "plan.json"
        code, out, err = self.run_cli(
            "plan",
            "--world",
            str(WORLDS / "central_russia_v1.json"),
            "--input",
            str(bare),
            "--clock",
            "2026-10-23T09:00:00+03:00",
            "--out",
            str(target),
        )
        self.assertEqual((code, out, err), (0, "", ""))
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["km"] > 500, True)

    def test_share(self) -> None:
        code, out, _ = self.run_cli(
            "share", "--world", str(WORLDS / "central_russia_v1.json"), "--input", str(self.input)
        )
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("Москва → Ярославль → Москва · "))
        self.assertIn("\nДень 2 · ", out)

    def test_export_config(self) -> None:
        sql = export_config_sql()
        self.assertIn("('planner', '", sql)
        self.assertIn("('reasons_ru', '", sql)
        self.assertEqual(sql.count("ON CONFLICT (key)"), 2)
        code, out, _ = self.run_cli("export-config")
        self.assertEqual((code, out), (0, sql))


if __name__ == "__main__":
    unittest.main()
