"""Tests for tools.py — custom reliability tools."""
import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import ToolRegistry


class FakeController:
    """Minimal stand-in for ControllerV2 used by the tool registry tests."""
    def __init__(self, memory):
        self.memory = memory
    def evaluate_gate(self, contract, report):
        from controller import Status
        return Status.VERIFIED
    async def run_nine_point_check_for_patch(self, contract, patch):
        return {}


class TestToolRegistry(unittest.TestCase):
    def test_register_and_call(self):
        reg = ToolRegistry()
        async def echo(x):
            return x
        reg.register("echo", echo)
        self.assertEqual(asyncio.run(reg.call("echo", x=42)), 42)

    def test_unknown_tool_raises(self):
        reg = ToolRegistry()
        try:
            asyncio.run(reg.call("nope"))
        except KeyError as e:
            self.assertIn("Unknown reliability tool", str(e))
        else:
            self.fail("expected KeyError")

    def test_names_sorted(self):
        reg = ToolRegistry()
        async def noop():
            return None
        reg.register("zeta", noop)
        reg.register("alpha", noop)
        reg.register("beta", noop)
        self.assertEqual(reg.names(), ["alpha", "beta", "zeta"])


if __name__ == "__main__":
    unittest.main()