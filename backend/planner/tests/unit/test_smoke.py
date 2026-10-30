import re
import unittest

from verst_planner import ENGINE_VERSION


class SmokeTest(unittest.TestCase):
    def test_engine_version_is_semver(self) -> None:
        self.assertRegex(ENGINE_VERSION, re.compile(r"^\d+\.\d+\.\d+$"))


if __name__ == "__main__":
    unittest.main()
