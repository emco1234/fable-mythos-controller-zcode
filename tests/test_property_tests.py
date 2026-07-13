"""Tests for property_tests.py — framework detection."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from property_tests import _detect_framework


class TestPropertyTestDetection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wt = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_detects_hypothesis(self):
        (self.wt / "pyproject.toml").write_text("[tool.hypothesis]\n", encoding="utf-8")
        self.assertEqual(_detect_framework(self.wt), "hypothesis")

    def test_detects_hypothesis_via_requirements(self):
        (self.wt / "requirements.txt").write_text("hypothesis>=6.0\n", encoding="utf-8")
        self.assertEqual(_detect_framework(self.wt), "hypothesis")

    def test_detects_fast_check(self):
        (self.wt / "package.json").write_text('{"devDependencies": {"fast-check": "^3.0"}}', encoding="utf-8")
        self.assertEqual(_detect_framework(self.wt), "fast-check")

    def test_detects_proptest(self):
        (self.wt / "Cargo.toml").write_text('[dev-dependencies]\nproptest = "1"\n', encoding="utf-8")
        self.assertEqual(_detect_framework(self.wt), "proptest")

    def test_unknown_when_nothing_matches(self):
        self.assertEqual(_detect_framework(self.wt), "unknown")


if __name__ == "__main__":
    unittest.main()