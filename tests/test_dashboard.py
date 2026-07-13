"""Tests for dashboard.py — telemetry aggregator."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dashboard import aggregate, render_markdown


class TestAggregate(unittest.TestCase):
    def test_aggregate_empty_path(self):
        with tempfile.TemporaryDirectory() as d:
            result = aggregate(Path(d) / "missing.jsonl")
            self.assertIn("error", result)

    def test_aggregate_basic(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "events.jsonl"
            lines = [
                {"risk_tier": "complex", "status": "VERIFIED",
                 "tokens_total": 1000, "latency_total_ms": 5000,
                 "repair_rounds_used": 0, "agent_dispatch_count": 3},
                {"risk_tier": "complex", "status": "BLOCKED",
                 "tokens_total": 2000, "latency_total_ms": 8000,
                 "repair_rounds_used": 2, "agent_dispatch_count": 4,
                 "failure_mode": "TEST_FAILURE"},
                {"risk_tier": "trivial", "status": "VERIFIED",
                 "tokens_total": 100, "latency_total_ms": 500,
                 "repair_rounds_used": 0, "agent_dispatch_count": 1},
            ]
            path.write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")
            agg = aggregate(path)
            self.assertEqual(agg["total_records"], 3)
            self.assertEqual(agg["status_distribution"]["VERIFIED"], 2)
            self.assertEqual(agg["status_distribution"]["BLOCKED"], 1)
            self.assertEqual(agg["top_failure_modes"]["TEST_FAILURE"], 1)
            self.assertIn("complex", agg["by_risk_tier"])
            self.assertIn("trivial", agg["by_risk_tier"])
            self.assertEqual(agg["by_risk_tier"]["complex"]["count"], 2)
            self.assertEqual(agg["by_risk_tier"]["trivial"]["mean_tokens"], 100.0)

    def test_render_markdown_contains_table(self):
        agg = {
            "total_records": 5,
            "by_risk_tier": {
                "complex": {"count": 3, "mean_tokens": 1000.0,
                            "mean_latency_ms": 5000.0,
                            "mean_dispatches": 4.0,
                            "mean_repair_rounds": 1.0},
            },
            "status_distribution": {"VERIFIED": 3, "BLOCKED": 2},
            "top_failure_modes": {"TEST_FAILURE": 1},
        }
        md = render_markdown(agg)
        self.assertIn("Telemetry dashboard", md)
        self.assertIn("Total records: 5", md)
        self.assertIn("VERIFIED", md)
        self.assertIn("complex (n=3)", md)


if __name__ == "__main__":
    unittest.main()