"""Tests for repair.py — structured repair loops."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from repair import RepairFinding, RepairLoop, RepairDisposition


class TestRepairLoop(unittest.TestCase):
    def test_initial_state(self):
        loop = RepairLoop(max_rounds=3)
        self.assertEqual(loop.round, 0)
        self.assertEqual(len(loop.findings), 0)
        self.assertEqual(loop.unresolved(), [])

    def test_add_finding_assigns_round(self):
        loop = RepairLoop()
        loop.add(RepairFinding(id="F1", severity="HIGH", message="x"))
        self.assertEqual(loop.findings[0].repair_round, 0)

    def test_next_round_caps_at_max(self):
        loop = RepairLoop(max_rounds=2)
        self.assertTrue(loop.next_round())  # round becomes 1
        self.assertTrue(loop.next_round())  # round becomes 2
        self.assertFalse(loop.next_round())  # already at max

    def test_unresolved_excludes_fixed(self):
        loop = RepairLoop()
        loop.add(RepairFinding(id="F1", severity="HIGH", message="x", disposition=RepairDisposition.FIXED))
        loop.add(RepairFinding(id="F2", severity="MEDIUM", message="y", disposition=None))
        self.assertEqual(len(loop.unresolved()), 1)
        self.assertEqual(loop.unresolved()[0].id, "F2")

    def test_render_for_lead_with_no_findings(self):
        loop = RepairLoop()
        out = loop.render_for_lead()
        self.assertIn("(no findings", out)

    def test_render_for_lead_with_findings(self):
        loop = RepairLoop(round=1, max_rounds=3)
        loop.add(RepairFinding(id="F1", severity="HIGH", message="x failed", location="file.py:42", fix_suggestion="add test"))
        out = loop.render_for_lead()
        self.assertIn("REPAIR LOOP round 2/3", out)
        self.assertIn("[F1]", out)
        self.assertIn("HIGH @ file.py:42", out)
        self.assertIn("Suggested fix: add test", out)

    def test_to_json_roundtrip(self):
        loop = RepairLoop(max_rounds=5)
        loop.add(RepairFinding(id="F1", severity="CRITICAL", message="x"))
        j = loop.to_json()
        import json
        data = json.loads(j)
        self.assertEqual(data["max_rounds"], 5)
        self.assertEqual(data["findings"][0]["id"], "F1")
        self.assertEqual(data["findings"][0]["severity"], "CRITICAL")


if __name__ == "__main__":
    unittest.main()