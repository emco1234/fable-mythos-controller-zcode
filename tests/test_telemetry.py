"""Tests for telemetry.py — anonymized telemetry."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import telemetry
from telemetry import make_record, record


class TestTelemetry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "events.jsonl"
        self._old = os.environ.get("RELIABILITY_TELEMETRY")
        os.environ["RELIABILITY_TELEMETRY"] = "1"

    def tearDown(self):
        if self._old is None:
            os.environ.pop("RELIABILITY_TELEMETRY", None)
        else:
            os.environ["RELIABILITY_TELEMETRY"] = self._old
        self.tmp.cleanup()

    def test_disabled_no_op(self):
        os.environ["RELIABILITY_TELEMETRY"] = "0"
        rec = make_record(task_id="t1", risk_tier="complex", status="VERIFIED",
                          agent_dispatch_count=3, repair_rounds_used=0,
                          tokens_total=1000, latency_total_ms=5000)
        record(rec, path=self.path)
        self.assertFalse(self.path.exists())

    def test_anonymization_hashes_task_id(self):
        rec = make_record(task_id="user-supplied-sensitive-id", risk_tier="critical",
                          status="VERIFIED", agent_dispatch_count=5,
                          repair_rounds_used=0, tokens_total=0, latency_total_ms=0)
        record(rec, path=self.path)
        line = self.path.read_text(encoding="utf-8").strip()
        data = json.loads(line)
        self.assertNotIn("user-supplied-sensitive-id", line)
        self.assertEqual(len(data["task_id_hash"]), 8)

    def test_no_prompt_or_path_leak(self):
        rec = make_record(task_id="t", risk_tier="complex", status="BLOCKED",
                          agent_dispatch_count=2, repair_rounds_used=1,
                          tokens_total=0, latency_total_ms=0,
                          failure_mode="TEST_FAILURE")
        record(rec, path=self.path)
        line = self.path.read_text(encoding="utf-8")
        self.assertNotIn("/Users/", line)
        self.assertNotIn("password", line.lower())

    def test_multiple_records_appended(self):
        for i in range(3):
            record(make_record(task_id=f"t{i}", risk_tier="normal",
                              status="VERIFIED", agent_dispatch_count=1,
                              repair_rounds_used=0, tokens_total=0,
                              latency_total_ms=0), path=self.path)
        lines = self.path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 3)


if __name__ == "__main__":
    unittest.main()