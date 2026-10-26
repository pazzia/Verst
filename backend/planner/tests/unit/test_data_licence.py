"""ODbL package (CEO D-IR-07; docs/legal/risk-register.md R-01, R-09, R-10).

The notice the APK ships, the free copy of the catalogue with the licence text, the «О данных» copy and the
release notes say the same thing and point at the same places as the catalogue's own `meta.licence`
(`tools/data/build_catalogue.py`)."""

from __future__ import annotations

import hashlib
import re
import unittest
import xml.etree.ElementTree as ET

from tests.helpers import PLANNER_ROOT
from tests.unit.test_catalogue import builder

REPO = PLANNER_ROOT.parents[1]
ANDROID = REPO / "android"
NOTICE = ANDROID / "core-ui" / "src" / "main" / "assets" / "licenses" / "data.txt"
COPY_DIR = REPO / "data" / "catalogue"
# Open Data Commons' own plain-text ODbL 1.0 (opendatacommons.org/licenses/odbl/odbl-10.txt, from the
# site's source github.com/okfn/opendatacommons.org content/licenses/odbl/odbl-10.txt), fetched 2026-10-25.
# It matches SPDX ODbL-1.0.txt word for word except the title line, «-» vs «–» after the defined terms and
# SPDX's typo «4.74».
ODBL_TEXT_SHA256 = "607680718977f6f6c9607972afd98f208573f19251315ed1362a8589b51beaf5"


def android_strings() -> dict[str, str]:
    root = ET.parse(ANDROID / "core-ui" / "src" / "main" / "res" / "values" / "strings.xml").getroot()
    return {e.attrib["name"]: "".join(e.itertext()) for e in root.iter("string")}


class DataLicenceTest(unittest.TestCase):
    b = builder()

    def test_notice_file_in_the_apk(self) -> None:
        """ODbL 4.2: the notice with the licence URI, the OSM copyright page, every source, the free copy."""
        text = NOTICE.read_text("utf-8")
        for needle in (
            "© участники OpenStreetMap, данные доступны по лицензии",
            "Open Database License (ODbL) 1.0",
            "© OpenStreetMap contributors",
            self.b.ODBL_URI,
            self.b.OSM_COPYRIGHT_URI,
            self.b.CC0_URI,
            self.b.CC_BY_SA_4_URI,
            self.b.CATALOGUE_COPY_URI,
            "тексты сокращены",
            "the texts are abridged",
            "Derivative Database of OpenStreetMap",
            "производная база данных OpenStreetMap",
            "Wikimedia Commons",
            "GFDL",
        ):
            self.assertIn(needle, text)
        self.assertTrue(text.endswith("\n") and "\r" not in text)

    def test_app_links_match_the_catalogue(self) -> None:
        """The «О данных» links (RoadScreen.kt `DataLicence`) are the catalogue's URIs; the asset exists."""
        kt = (ANDROID / "app/src/main/kotlin/app/verst/feature/road/RoadScreen.kt").read_text("utf-8")
        consts = dict(re.findall(r'const val (\w+) = "([^"]+)"', kt))
        self.assertEqual(consts["CATALOGUE_COPY"], self.b.CATALOGUE_COPY_URI)
        self.assertEqual(consts["ODBL"], self.b.ODBL_URI)
        self.assertEqual(consts["OSM_COPYRIGHT"], self.b.OSM_COPYRIGHT_URI)
        self.assertEqual(ANDROID / "core-ui/src/main/assets" / consts["NOTICE_ASSET"], NOTICE)

    def test_free_copy_in_the_repository(self) -> None:
        """ODbL 4.6: the copy URI is this repository's `data/catalogue/`; it has the full licence text and its
        README's relative links (catalogue files, lock, ADR, licence) all resolve."""
        self.assertTrue(self.b.CATALOGUE_COPY_URI.endswith("/tree/main/data/catalogue"))
        licence = (COPY_DIR / "LICENSE-ODbL.txt").read_bytes()
        self.assertEqual(hashlib.sha256(licence).hexdigest(), ODBL_TEXT_SHA256)
        self.assertIn(b"4.6 Access to Derivative Databases.", licence)
        readme = (COPY_DIR / "README.md").read_text("utf-8")
        links = re.findall(r"\]\((?!https?://|#)([^)]+)\)", readme)
        self.assertGreaterEqual(len(links), 6)
        for link in links:
            with self.subTest(link=link):
                self.assertTrue((COPY_DIR / link).resolve().exists(), link)
        for name in ("catalogue_meta", "catalogue_towns", "catalogue_pois", "catalogue_bars"):
            self.assertIn(f"backend/planner/verst_planner/resources/{name}.json.gz", readme)
        for needle in (self.b.ODBL_URI, self.b.OSM_COPYRIGHT_URI, "тексты сокращены", "abridged", "GFDL"):
            self.assertIn(needle, readme)
        root = (REPO / "README.md").read_text("utf-8")
        self.assertIn("data/catalogue/README.md", root)

    def test_about_data_and_card_copy(self) -> None:
        """Lawyer brief appendix B: «О данных» names ODbL and the free copy, keeps the demo line; the extract
        credit names CC BY-SA 4.0 and the abridgement (R-09)."""
        s = android_strings()
        body = s["about_data_body"]
        for needle in (
            "© участники OpenStreetMap, данные доступны по лицензии ODbL 1.0",
            "производная база данных OpenStreetMap",
            "копию можно скачать бесплатно",
            "CC BY-SA 4.0",
            "тексты сокращены",
            "Wikidata (CC0)",
            "в демо-сборке вымышленные",
        ):
            self.assertIn(needle, body)
        for key in ("card_desc_wikipedia", "card_desc_wikivoyage"):
            self.assertIn("текст сокращён", s[key])
            self.assertTrue(s[key].endswith("· CC BY-SA 4.0"), s[key])
        for key in ("about_data_copy", "about_data_odbl", "about_data_osm"):
            self.assertTrue(s[key].strip(), key)
        for key in ("about_data_notice", "about_data_notice_hide"):
            self.assertTrue(s[key].strip(), key)

    def test_release_notes_link_the_copy(self) -> None:
        workflow = (REPO / ".github" / "workflows" / "android.yml").read_text("utf-8")
        self.assertIn("/tree/${{ github.sha }}/data/catalogue", workflow)


if __name__ == "__main__":
    unittest.main()
