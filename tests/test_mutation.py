"""Tests for mutation.py — mutation testing backend detection."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mutation import _detect_backend


class TestMutationDetection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wt = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_detects_mutmut_via_setup_cfg(self):
        (self.wt / "setup.cfg").write_text("[mutmut]\ntests_dir=tests/\n", encoding="utf-8")
        self.assertEqual(_detect_backend(self.wt), "mutmut")

    def test_detects_mutmut_via_pyproject(self):
        (self.wt / "pyproject.toml").write_text("[tool.mutmut]\nbackup=False\n", encoding="utf-8")
        self.assertEqual(_detect_backend(self.wt), "mutmut")

    def test_detects_stryker_via_conf(self):
        (self.wt / "stryker.conf.json").write_text('{"packageManager": "npm"}', encoding="utf-8")
        self.assertEqual(_detect_backend(self.wt), "stryker")

    def test_unknown_when_nothing_matches(self):
        self.assertEqual(_detect_backend(self.wt), "unknown")


if __name__ == "__main__":
    unittest.main()