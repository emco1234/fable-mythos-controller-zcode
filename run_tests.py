#!/usr/bin/env python3
"""Run all tests in tests/. Idempotent: re-runs produce the same result."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(Path(__file__).resolve().parent / "tests"),
                            pattern="test_*.py",
                            top_level_dir=str(Path(__file__).resolve().parent))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)