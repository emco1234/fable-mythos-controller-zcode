"""Integration tests for controller_v2 — the full orchestrator."""
import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controller import TaskContract, AcceptanceCriterion, Status, PlatformAdapter
from controller_v2 import ControllerV2
from memory import TaskMemory


class StubAdapter(PlatformAdapter):
    """Records every spawn call; returns deterministic transcript paths."""
    def __init__(self):
        self.calls: list[tuple[str, str]] = []
    async def spawn(self, agent_name: str, prompt: str) -> str:
        self.calls.append((agent_name, prompt))
        return f".transcripts/{agent_name}-stub.md"


async def _passing_check(cmd: str) -> tuple[int, str]:
    return 0, "ok"


async def _failing_check(cmd: str) -> tuple[int, str]:
    return 1, "fail"


class TestControllerV2(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.worktree = Path(self.tmp.name)
        self.memory = TaskMemory(self.worktree / "memory.sqlite")
        self.adapter = StubAdapter()
        self.controller = ControllerV2(adapter=self.adapter, memory=self.memory)
        self.contract = TaskContract(
            task_id="t-test",
            base_commit="HEAD",
            goal="smoke test",
            risk_tier="complex",
            must=["x"],
            must_not=["y"],
            acceptance_criteria=[AcceptanceCriterion(id="AC1", condition="c")],
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_complex_dispatches_in_parallel_phase_then_serial(self):
        report = asyncio.run(self.controller.run(
            self.contract, self.worktree, _passing_check,
        ))
        # complex = scout + spec-critic + test-designer (parallel) + lead + verifier (serial)
        agents_dispatched = {c[0] for c in self.adapter.calls}
        self.assertIn("reliability-scout", agents_dispatched)
        self.assertIn("reliability-spec-critic", agents_dispatched)
        self.assertIn("reliability-test-designer", agents_dispatched)
        self.assertIn("reliability-lead", agents_dispatched)
        self.assertIn("reliability-verifier", agents_dispatched)

    def test_passing_checks_with_clean_state_yields_verified(self):
        report = asyncio.run(self.controller.run(
            self.contract, self.worktree, _passing_check,
        ))
        self.assertEqual(report.status, Status.VERIFIED)

    def test_failing_hard_check_blocks(self):
        report = asyncio.run(self.controller.run(
            self.contract, self.worktree, _failing_check,
        ))
        self.assertEqual(report.status, Status.BLOCKED)
        # Should record one of the failed checks as a finding
        self.assertTrue(any("typecheck" in f.message or "build" in f.message or "lint" in f.message
                            for f in report.findings))

    def test_persistence_round_trip(self):
        report = asyncio.run(self.controller.run(
            self.contract, self.worktree, _passing_check,
        ))
        # Contract saved
        loaded = self.memory.load_contract("t-test")
        self.assertIsNotNone(loaded)
        # Ledger contains agent transcripts
        ledger = self.memory.load_ledger("t-test")
        kinds = {e.kind for e in ledger}
        self.assertIn("AGENT_TRANSCRIPT", kinds)
        # Report saved
        latest = self.memory.latest_report("t-test")
        self.assertEqual(latest["status"], "VERIFIED")
        # Budget recorded
        budget = self.memory.load_budget("t-test")
        self.assertIsNotNone(budget)

    def test_normal_tier_dispatches_lead_and_verifier_only(self):
        self.contract.risk_tier = "normal"
        asyncio.run(self.controller.run(self.contract, self.worktree, _passing_check))
        agents = {c[0] for c in self.adapter.calls}
        self.assertEqual(agents, {"reliability-lead", "reliability-verifier"})

    def test_critical_tier_includes_adversary(self):
        self.contract.risk_tier = "critical"
        asyncio.run(self.controller.run(self.contract, self.worktree, _passing_check))
        agents = {c[0] for c in self.adapter.calls}
        self.assertIn("reliability-adversary", agents)


if __name__ == "__main__":
    unittest.main()