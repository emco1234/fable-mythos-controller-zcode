"""Tests for enforcement.py — tool-call enforcement."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from enforcement import enforce, tools_invoked, MUST_CALL


class TestToolsInvoked(unittest.TestCase):
    def test_extracts_at_tool_calls(self):
        text = "I will @tool verify() and @tool gate() now."
        self.assertEqual(tools_invoked(text), {"verify", "gate"})

    def test_extracts_tool_with_space(self):
        text = "I will @tool record_evidence(...) before stopping."
        self.assertEqual(tools_invoked(text), {"record_evidence"})

    def test_case_insensitive(self):
        text = "@TOOL Verify() called"
        self.assertEqual(tools_invoked(text), {"verify"})

    def test_no_tools_returns_empty(self):
        self.assertEqual(tools_invoked("just text"), set())


class TestEnforce(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.get("RELIABILITY_ENFORCE_TOOLS")
        os.environ["RELIABILITY_ENFORCE_TOOLS"] = "1"

    def tearDown(self):
        if self._old is None:
            os.environ.pop("RELIABILITY_ENFORCE_TOOLS", None)
        else:
            os.environ["RELIABILITY_ENFORCE_TOOLS"] = self._old

    def test_passing_when_required_tools_present(self):
        text = "Calling @tool verify() and then @tool gate()."
        result = enforce("reliability-verifier", text)
        self.assertTrue(result.passed)
        self.assertEqual(result.violations, [])

    def test_failing_when_required_tool_missing(self):
        text = "I just write some output without calling any tools."
        result = enforce("reliability-verifier", text)
        self.assertFalse(result.passed)
        self.assertEqual(len(result.violations), 2)

    def test_unknown_agent_passes(self):
        result = enforce("unknown-agent", "anything")
        self.assertTrue(result.passed)

    def test_disabled_skips_enforcement(self):
        os.environ["RELIABILITY_ENFORCE_TOOLS"] = "0"
        text = "I don't call anything."
        result = enforce("reliability-verifier", text)
        self.assertFalse(result.enforced)
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()