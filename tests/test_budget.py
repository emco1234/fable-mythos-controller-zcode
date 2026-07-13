"""Tests for budget.py — token / latency enforcement."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from budget import BudgetTracker, BudgetExceededReason


class TestBudgetTracker(unittest.TestCase):
    def test_trivial_tier_has_no_limits(self):
        b = BudgetTracker(risk_tier="trivial")
        b.record(tokens=999_999_999, latency_ms=999_999_999)
        self.assertIsNone(b.exceeded())

    def test_normal_tier_token_cap(self):
        b = BudgetTracker(risk_tier="normal")
        b.record(tokens=200_001, latency_ms=0)
        self.assertEqual(b.exceeded(), BudgetExceededReason.TOKENS)

    def test_normal_tier_latency_cap(self):
        b = BudgetTracker(risk_tier="normal")
        b.record(tokens=0, latency_ms=5 * 60 * 1000 + 1)
        self.assertEqual(b.exceeded(), BudgetExceededReason.LATENCY)

    def test_complex_tier_higher_caps(self):
        b = BudgetTracker(risk_tier="complex")
        b.record(tokens=500_000, latency_ms=10 * 60 * 1000)
        self.assertIsNone(b.exceeded())
        b.record(tokens=600_000, latency_ms=0)
        self.assertEqual(b.exceeded(), BudgetExceededReason.TOKENS)

    def test_critical_tier_highest(self):
        b = BudgetTracker(risk_tier="critical")
        b.record(tokens=1_999_999, latency_ms=89 * 60 * 1000)
        self.assertIsNone(b.exceeded())
        b.record(tokens=2, latency_ms=0)
        self.assertEqual(b.exceeded(), BudgetExceededReason.TOKENS)

    def test_status_dict_contains_all_fields(self):
        b = BudgetTracker(risk_tier="normal")
        b.record(tokens=100, latency_ms=200)
        s = b.status()
        self.assertEqual(s["risk_tier"], "normal")
        self.assertEqual(s["tokens_used"], 100)
        self.assertEqual(s["latency_ms"], 200)
        self.assertEqual(s["tokens_limit"], 200_000)
        self.assertEqual(s["latency_limit_ms"], 5 * 60 * 1000)


if __name__ == "__main__":
    unittest.main()