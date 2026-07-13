"""Tests for compaction.py — context compaction with ledger invariant."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from compaction import compact, render_ledger_for_context


class TestCompaction(unittest.TestCase):
    def test_short_text_unchanged(self):
        text = "task_id: t1\ngoal: fix\n"
        r = compact(text, budget_lines=200)
        self.assertEqual(r.compacted_text, text)
        self.assertTrue(r.contract_preserved)

    def test_contract_preserved_after_compaction(self):
        contract_lines = "\n".join([
            "task_id: t-critical",
            "goal: ship feature X",
            "risk_tier: critical",
            "must:",
            "  - run all tests",
            "  - update docs",
            "must_not:",
            "  - skip linter",
            "acceptance_criteria:",
            "  - id: AC1",
        ])
        filler = "\n".join(["some filler reasoning line"] * 500)
        text = contract_lines + "\n" + filler + "\n" + ("tail line\n" * 30)
        r = compact(text, budget_lines=100, tail_lines=20)
        self.assertLessEqual(r.kept_lines, 200)
        self.assertTrue(r.contract_preserved)
        self.assertIn("task_id: t-critical", r.compacted_text)

    def test_ledger_block_preserved(self):
        text = "task_id: t1\n"
        ledger = (
            "--- BEGIN LEDGER ---\n"
            "[#1] AGENT_TRANSCRIPT: agent=scout\n"
            "[#2] FINDING: severity=HIGH\n"
            "--- END LEDGER ---\n"
        )
        filler = "\n".join(["x"] * 800)
        r = compact(text + ledger + filler + ("tail\n" * 30), budget_lines=80, tail_lines=15)
        self.assertIn("--- BEGIN LEDGER ---", r.compacted_text)
        self.assertIn("--- END LEDGER ---", r.compacted_text)
        self.assertGreaterEqual(r.ledger_entries_preserved, 2)

    def test_render_ledger_for_context(self):
        entries = [
            {"kind": "AGENT_TRANSCRIPT", "payload": {"agent": "scout"}},
            {"kind": "FINDING", "payload": {"severity": "HIGH", "message": "bug"}},
        ]
        rendered = render_ledger_for_context(entries)
        self.assertIn("--- BEGIN LEDGER ---", rendered)
        self.assertIn("AGENT_TRANSCRIPT", rendered)
        self.assertIn("FINDING", rendered)
        self.assertIn("--- END LEDGER ---", rendered)


if __name__ == "__main__":
    unittest.main()