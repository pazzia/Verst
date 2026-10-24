"""Release review P0-1: no real brand anywhere in the mock build.

Scans every string of both fixture worlds, the engine resources, the golden snapshots and contract files
(incl. the shared text) and the Android strings the app actually references (`R.string.<key>` in Kotlin
sources). The rendered screens and the merged APK resources are checked on the Kotlin side with the same
deny-list file.
"""

from __future__ import annotations

import gzip
import json
import re
import unittest
from collections.abc import Iterator
from typing import Any

from tests.helpers import PLANNER_ROOT, WORLDS

REPO = PLANNER_ROOT.parents[1]
DENY = [
    line.strip()
    for line in (PLANNER_ROOT / "tests" / "brand_denylist.txt").read_text("utf-8").splitlines()
    if line.strip() and not line.startswith("#")
]


def strings(node: Any) -> Iterator[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        # Values only: keys are field names (e.g. `yandexTravelId`, a production link id), never shown.
        for v in node.values():
            yield from strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from strings(v)


def hits(texts: Iterator[str]) -> list[str]:
    out = []
    for t in texts:
        low = t.lower()
        out += [f"{b!r} in {t[:80]!r}" for b in DENY if b.lower() in low]
    return out


class BrandDenyListTest(unittest.TestCase):
    def test_denylist_loaded(self) -> None:
        self.assertIn("Лукойл", DENY)
        self.assertIn("Яндекс", DENY)
        self.assertTrue(hits(iter(["АЗС Лукойл, М-8"])))  # the matcher works

    def test_fixture_worlds(self) -> None:
        for name in ("central_russia_v1", "edge_cases_v1"):
            with self.subTest(name):
                self.assertEqual(hits(strings(json.loads((WORLDS / f"{name}.json").read_text("utf-8")))), [])

    def test_engine_resources_goldens_and_contracts(self) -> None:
        files = list((PLANNER_ROOT / "verst_planner" / "resources").glob("*.json"))
        files += list((PLANNER_ROOT / "tests" / "golden").rglob("*.json"))
        files += [p for p in (REPO / "docs" / "contracts").rglob("*.json")]
        self.assertGreater(len(files), 20)
        for f in files:
            with self.subTest(f.name):
                self.assertEqual(hits(strings(json.loads(f.read_text("utf-8")))), [])
        bundles = list((REPO / "docs" / "contracts").rglob("*.json.gz"))
        self.assertGreater(len(bundles), 10)
        for f in bundles:
            with self.subTest(f.name):
                self.assertEqual(hits(strings(json.loads(gzip.decompress(f.read_bytes())))), [])

    def test_android_strings_the_app_uses(self) -> None:
        android = REPO / "android"
        xml = (android / "core-ui/src/main/res/values/strings.xml").read_text("utf-8")
        values = dict(re.findall(r'<string name="([a-z0-9_]+)"[^>]*>(.*?)</string>', xml, re.S))
        used: set[str] = set()
        for kt in android.rglob("src/main/**/*.kt"):
            used |= set(re.findall(r"R\.string\.([a-z0-9_]+)", kt.read_text("utf-8")))
        self.assertGreater(len(used), 100)
        self.assertEqual(hits(iter(values[k] for k in sorted(used) if k in values)), [])
