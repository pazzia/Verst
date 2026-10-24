"""DEV-110: the planner works when imported from a zip archive (Chaquopy imports app code from the APK)."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.helpers import PLANNER_ROOT

PKG = PLANNER_ROOT / "verst_planner"
ALLOWED_READERS = {
    PKG / "resources" / "__init__.py",
    PKG / "cli.py",
    PKG / "adapters" / "fake" / "world.py",  # FakeWorld.load(path)
}

CHILD = r"""
import json, sys
from datetime import datetime
sys.path[:] = [sys.argv[1]] + [p for p in sys.path if "site-packages" not in p and p != ""]
import verst_planner
assert verst_planner.__file__.startswith(sys.argv[1]), verst_planner.__file__
from verst_planner.config import PlannerConfig
from verst_planner.explain import ru
from verst_planner.explain.templates import ReasonTemplates
from verst_planner.adapters.fake import FakeWorld, build_fakes
from verst_planner.domain import codec
from verst_planner.engine import Planner
PlannerConfig.from_dict({})
ReasonTemplates.default()
assert ru.text("label.map_point") == "Точка на карте"
case = json.loads(open(sys.argv[2], encoding="utf-8").read())
f = build_fakes(FakeWorld.load(sys.argv[3]), datetime.fromisoformat(case["clock"]))
cfg = PlannerConfig.from_dict(case.get("config") or {})
planner = Planner(routing=f.routing, places=f.places, prices=f.prices, tolls=f.tolls, regions=f.regions,
                  geocoding=f.geocoding, clock=f.clock, config=cfg, templates=ReasonTemplates.default())
plan = planner.plan(codec.input_from_json(case["input"]))
out = codec.plan_to_json(plan, trip_id="trp_golden")
sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
# Sprint 3: the gzip catalogue and the road model load from the archive too (ADR-0012 §3)
from verst_planner.catalogue import load_packaged
from verst_planner.adapters.catalogue import road_model
assert load_packaged().towns and road_model().ratio(100.0) > 1.0
"""


def build_zip(dest: Path) -> Path:
    out = dest / "vp.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(PKG.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                z.write(f, f.relative_to(PKG.parent).as_posix())
    return out


class PackagingTest(unittest.TestCase):
    def test_import_from_zip(self) -> None:
        case = next((PLANNER_ROOT / "tests" / "golden" / "cases").glob("G02_*.json"))
        snapshot = next((PLANNER_ROOT / "tests" / "golden" / "snapshots").glob("G02_*.json"))
        world = PLANNER_ROOT / "fixtures" / "worlds" / f"{json.loads(case.read_text('utf-8'))['world']}.json"
        with tempfile.TemporaryDirectory() as tmp:
            archive = build_zip(Path(tmp))
            res = subprocess.run(
                [sys.executable, "-I", "-c", CHILD, str(archive), str(case), str(world)],
                capture_output=True,
                timeout=120,
                cwd=tmp,
            )
        self.assertEqual(res.returncode, 0, res.stderr.decode("utf-8", "replace"))
        self.assertEqual(res.stdout.decode("utf-8"), snapshot.read_text("utf-8"))

    def test_no_file_reads_outside_helper(self) -> None:
        offenders = []
        for path in sorted(PKG.rglob("*.py")):
            if path in ALLOWED_READERS:
                continue
            for node in ast.walk(ast.parse(path.read_text("utf-8"))):
                if isinstance(node, ast.Call):
                    f = node.func
                    name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
                    helper = (
                        isinstance(f, ast.Attribute)
                        and isinstance(f.value, ast.Name)
                        and f.value.id == "resources"
                    )
                    if name in ("open", "read_text", "read_bytes") and not helper:
                        offenders.append(f"{path.relative_to(PKG.parent)}:{node.lineno} {name}(")
        self.assertEqual(offenders, [])

    def test_resources_helper(self) -> None:
        from verst_planner import resources

        self.assertEqual(json.loads(resources.read_text("planner_config.json"))["max_days"], 14)
        self.assertTrue((resources.DIR / "reasons.ru.json").is_file())


if __name__ == "__main__":
    unittest.main()
