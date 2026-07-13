"""Tests for acceptance.py — AC evaluation."""
import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from controller import AcceptanceCriterion
from acceptance import evaluate_acceptance_criteria, _parse_condition, _evidence_for


class TestParseCondition(unittest.TestCase):
    def test_condition_with_pipe(self):
        cmd, exp = _parse_condition("pytest tests/ | all pass")
        self.assertEqual(cmd, "pytest tests/")
        self.assertEqual(exp, "all pass")

    def test_condition_without_pipe(self):
        cmd, exp = _parse_condition("pytest tests/")
        self.assertEqual(cmd, "pytest tests/")
        self.assertIsNone(exp)

    def test_condition_with_extra_spaces(self):
        cmd, exp = _parse_condition("make build  |  exit 0")
        self.assertEqual(cmd, "make build")
        self.assertEqual(exp, "exit 0")


class TestEvidenceFor(unittest.TestCase):
    def test_exit_zero_no_expectation(self):
        sat, note = _evidence_for("pytest", 0, "all passed", None)
        self.assertTrue(sat)
        self.assertIn("exit 0", note)

    def test_exit_nonzero(self):
        sat, note = _evidence_for("pytest", 1, "FAILED", "all pass")
        self.assertFalse(sat)
        self.assertIn("exited 1", note)

    def test_expected_in_output(self):
        sat, note = _evidence_for("pytest", 0, "all pass", "all pass")
        self.assertTrue(sat)
        self.assertIn("expected", note)

    def test_expected_missing(self):
        sat, note = _evidence_for("pytest", 0, "1 failed", "all pass")
        self.assertFalse(sat)
        self.assertIn("missing", note)


async def _ok_check(_: str) -> tuple[int, str]:
    return 0, "all pass"


async def _fail_check(_: str) -> tuple[int, str]:
    return 1, "1 failed"


class TestEvaluateAcceptanceCriteria(unittest.TestCase):
    def test_evaluate_all_pass(self):
        async def run():
            acs = [
                AcceptanceCriterion(id="AC1", condition="pytest | all pass"),
                AcceptanceCriterion(id="AC2", condition="make build"),
            ]
            return await evaluate_acceptance_criteria(acs, _ok_check)
        results = asyncio.run(run())
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].satisfied)
        self.assertTrue(results[1].satisfied)

    def test_evaluate_one_fails(self):
        async def run():
            acs = [
                AcceptanceCriterion(id="AC1", condition="pytest | all pass"),
                AcceptanceCriterion(id="AC2", condition="make build"),
            ]
            return await evaluate_acceptance_criteria(acs, _fail_check)
        results = asyncio.run(run())
        self.assertFalse(results[0].satisfied)
        self.assertFalse(results[1].satisfied)

    def test_no_command_in_condition(self):
        async def run():
            acs = [AcceptanceCriterion(id="AC1", condition="")]
            return await evaluate_acceptance_criteria(acs, _ok_check)
        results = asyncio.run(run())
        self.assertIsNone(results[0].satisfied)
        self.assertIn("no command", results[0].note)


if __name__ == "__main__":
    unittest.main()