"""Release review P0-1: no real brand anywhere in the mock build.

Scans every string of both fixture worlds, the engine resources, the golden snapshots and contract files
(incl. the shared text) and the Android strings the app actually references (`R.string.<key>` in Kotlin
sources). The rendered screens and the merged APK resources are checked on the Kotlin side with the same
deny-list file.
"""

from __future__ import annotations

import fnmatch
import gzip
import json
import re
import unittest
from collections.abc import Iterator
from typing import Any

from tests.helpers import PLANNER_ROOT, WORLDS

REPO = PLANNER_ROOT.parents[1]
# ADR-0014: Android keys that may name the hand-off apps (`android:<glob>` lines of brand_allowlist.txt).
ANDROID_ALLOW = [
    line.strip()[len("android:") :]
    for line in (PLANNER_ROOT / "tests" / "brand_allowlist.txt").read_text("utf-8").splitlines()
    if line.startswith("android:")
]
DENY = [
    line.strip()
    for line in (PLANNER_ROOT / "tests" / "brand_denylist.txt").read_text("utf-8").splitlines()
    if line.strip() and not line.startswith("#")
]


ALLOW = {
    tuple(line.strip()[len("json:") :].split("."))
    for line in (PLANNER_ROOT / "tests" / "brand_allowlist.txt").read_text("utf-8").splitlines()
    if line.startswith("json:")
}


def strings(node: Any, parent: str | None = None) -> Iterator[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        # Values only: keys are field names (e.g. `yandexTravelId`, a production link id), never shown.
        for k, v in node.items():
            if (parent, k) in ALLOW:
                continue  # ADR-0014 hand-off links (tests/brand_allowlist.txt)
            yield from strings(v, k)
    elif isinstance(node, list):
        for v in node:
            yield from strings(v, parent)


def starts_word(brand: str, text: str) -> bool:
    """HYG-01: a deny-list entry hits where it starts a word, case-insensitive: «Суточно», «в Суточно»,
    «Суточно.ру», «в Яндексе», «yandexmaps://» hit; «круглосуточно» and «посуточно» do not. «Starts a word»
    means not preceded by a letter (`str.isalpha` = Unicode category L*, so Cyrillic too). The right side
    stays open on purpose: whole-word matching would let inflections and compounds through. Same rule as
    `BrandDenyList.hits` on the Kotlin side (`(?<!\\p{L})`, IGNORE_CASE + UNICODE_CASE)."""
    pattern = "(?=" + re.escape(brand) + ")"  # look-ahead: every start, overlapping ones included
    return any(m.start() == 0 or not text[m.start() - 1].isalpha() for m in re.finditer(pattern, text, re.I))


def hits(texts: Iterator[str]) -> list[str]:
    out = []
    for t in texts:
        out += [f"{b!r} in {t[:80]!r}" for b in DENY if starts_word(b, t)]
    return out


class BrandDenyListTest(unittest.TestCase):
    def test_denylist_loaded(self) -> None:
        self.assertIn("Лукойл", DENY)
        self.assertIn("Яндекс", DENY)
        self.assertTrue(hits(iter(["АЗС Лукойл, М-8"])))  # the matcher works

    def test_matcher_brand_starts_a_word(self) -> None:
        """HYG-01 regression: «Суточно» (a booking brand) is not inside «круглосуточно» / «посуточно»."""
        for text in ("круглосуточно", "Открыто КРУГЛОСУТОЧНО", "Квартиры посуточно"):
            with self.subTest(text):
                self.assertEqual(hits(iter([text])), [])
        for text in ("Суточно", "суточно", "СУТОЧНО", "в Суточно", "Суточно.ру", "«Суточно»", "24Суточно"):
            with self.subTest(text):
                self.assertEqual(hits(iter([text])), [f"'Суточно' in {text!r}"])
        # Starts a word, right side open: inflections and compounds still hit.
        for text, brand in (
            ("в Яндексе", "Яндекс"),
            ("yandexmaps://build_route", "Yandex"),
            ("у Лукойла", "Лукойл"),
            ("Gazpromneft", "Gazprom"),
            ("https://www.booking.com/x", "Booking"),
            ("через2ГИС", None),  # preceded by a letter: not a word start
        ):
            with self.subTest(text):
                self.assertEqual(hits(iter([text])), [f"{brand!r} in {text!r}"] if brand else [])

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

    def test_catalogue_and_composed_world(self) -> None:
        """Every name in the packaged catalogue and in the composed `russia_v1` world (ADR-0012)."""
        from verst_planner.adapters.catalogue import compose
        from verst_planner.adapters.fake import FakeWorld
        from verst_planner.catalogue import FILES, load_gz, load_packaged
        from verst_planner.resources import read_bytes

        for name in FILES.values():
            with self.subTest(name):
                self.assertEqual(hits(strings(load_gz(read_bytes(name), name))), [])
        cw = compose(FakeWorld.load(WORLDS / "central_russia_v1.json"), load_packaged())
        self.assertEqual(hits(p.name_ru for p in cw.world.places.values()), [])
        self.assertEqual(hits(t.name_ru for t in cw.world.towns.values()), [])

    def test_allowlist_only_skips_handoff_links(self) -> None:
        doc = {"links": {"maps": "yandexmaps://x", "web": "https://yandex.ru/maps"}, "nameRu": "Яндекс"}
        self.assertEqual(len(hits(strings(doc))), 1)
        self.assertEqual(hits(strings({"other": {"maps": "Яндекс"}})), ["'Яндекс' in 'Яндекс'"])

    def test_android_strings_the_app_uses(self) -> None:
        android = REPO / "android"
        xml = (android / "core-ui/src/main/res/values/strings.xml").read_text("utf-8")
        values = dict(re.findall(r'<string name="([a-z0-9_]+)"[^>]*>(.*?)</string>', xml, re.S))
        used: set[str] = set()
        for kt in android.rglob("src/main/**/*.kt"):
            used |= set(re.findall(r"R\.string\.([a-z0-9_]+)", kt.read_text("utf-8")))
        self.assertGreater(len(used), 100)
        # ADR-0014: only `handoff_*` keys may name the external app.
        allowed = {k for k in used if any(fnmatch.fnmatchcase(k, g) for g in ANDROID_ALLOW)}
        self.assertTrue(allowed, "the app uses hand-off keys")
        self.assertTrue(all(k.startswith("handoff_") for k in allowed), allowed)
        self.assertEqual(hits(iter(values[k] for k in sorted(used - allowed) if k in values)), [])
