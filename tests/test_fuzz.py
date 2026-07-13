"""Tests for fuzz.py — fuzzing backend detection."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fuzz import _detect_backend


class TestFuzzDetection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wt = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_detects_atheris_python(self):
        fuzz = self.wt / "fuzz"
        fuzz.mkdir()
        (fuzz / "fuzz_parser.py").write_text("# atheris target", encoding="utf-8")
        self.assertEqual(_detect_backend(self.wt), "atheris")

    def test_detects_cargo_fuzz(self):
        fuzz = self.wt / "fuzz"
        fuzz.mkdir()
        (fuzz / "fuzz_parser.rs").write_text("// cargo-fuzz target", encoding="utf-8")
        self.assertEqual(_detect_backend(self.wt), "cargo-fuzz")

    def test_unknown_when_no_fuzz_dir(self):
        self.assertEqual(_detect_backend(self.wt), "unknown")


if __name__ == "__main__":
    unittest.main()