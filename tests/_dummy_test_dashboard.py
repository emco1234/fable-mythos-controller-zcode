"""Tests for memory.py — SQLite persistent task memory."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from memory import TaskMemory


class TestMemory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mem = TaskMemory(Path(self.tmp.name) / "memory.sqlite")

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_load_contract(self):
        self.mem.save_contract("task-1", "HEAD", "fix bug", "complex", "task_id: task-1")
        loaded = self.mem.load_contract("task-1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["task_id"], "task-1")
        self.assertEqual(loaded["goal"], "fix bug")
        self.assertEqual(loaded["risk_tier"], "complex")

    def test_load_contract_missing(self):
        self.assertIsNone(self.mem.load_contract("nope"))

    def test_ledger_append_and_load_ordering(self):
        self.mem.append_ledger("t", "AGENT_TRANSCRIPT", {"agent": "scout", "transcript": "/a"})
        self.mem.append_ledger("t", "FINDING", {"severity": "HIGH", "message": "x"})
        self.mem.append_ledger("t", "REPAIR_ATTEMPT", {"round": 1})
        entries = self.mem.load_ledger("t")
        self.assertEqual(len(entries), 3)
        self.assertEqual([e.sequence for e in entries], [1, 2, 3])
        self.assertEqual([e.kind for e in entries], ["AGENT_TRANSCRIPT", "FINDING", "REPAIR_ATTEMPT"])

    def test_report_latest(self):
        self.mem.save_report("t", "PARTIALLY_VERIFIED", {"foo": 1})
        self.mem.save_report("t", "VERIFIED", {"foo": 2})
        latest = self.mem.latest_report("t")
        self.assertEqual(latest["status"], "VERIFIED")
        self.assertEqual(latest["payload"], {"foo": 2})

    def test_budget_record_and_load(self):
        self.mem.record_budget("t", tokens=12345, latency_ms=67890, blocked_reason=None)
        loaded = self.mem.load_budget("t")
        self.assertEqual(loaded["tokens_used"], 12345)
        self.assertEqual(loaded["latency_ms"], 67890)

    def test_can_resume_only_for_non_terminal(self):
        self.mem.save_report("t", "VERIFIED", {})
        self.assertFalse(self.mem.can_resume("t"))
        self.mem.save_report("u", "PARTIALLY_VERIFIED", {})
        self.assertTrue(self.mem.can_resume("u"))


if __name__ == "__main__":
    unittest.main()