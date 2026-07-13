"""
Acceptance-criteria evaluation.

Each AC in the task contract has the shape:
  { id: "AC1", condition: "<command> | <expected result>" }

The evaluator parses the condition into command + expected, runs the
command via the standard check_cmd callable, and marks the AC as
satisfied / unsatisfied / unknown based on exit code and output.

This replaces the placeholder `None` from the walking skeleton.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass
class ACEvaluation:
    id: str
    condition: str
    command: str | None
    expected: str | None
    satisfied: bool | None
    exit_code: int | None
    evidence_ref: str | None
    note: str | None = None


# Parse "<cmd> | <expected>" or "<cmd>" (no expectation → only exit-code)
_SEPARATOR = re.compile(r"\s*\|\s*(.+)$")


def _parse_condition(condition: str) -> tuple[str | None, str | None]:
    m = _SEPARATOR.search(condition)
    if m:
        command = condition[: m.start()].strip()
        expected = m.group(1).strip()
        return command, expected
    return condition.strip(), None


def _evidence_for(condition: str, exit_code: int, summary: str, expected: str | None) -> tuple[bool | None, str]:
    """Decide if satisfied given exit_code, output, expected (if any)."""
    if exit_code != 0:
        return False, f"command exited {exit_code}"
    if expected is None:
        return True, "exit 0 (no expectation given)"
    # Heuristic: expected string must appear (case-insensitive substring)
    if expected.lower() in summary.lower():
        return True, f"output contains expected: {expected!r}"
    return False, f"output missing expected: {expected!r}"


async def evaluate_acceptance_criteria(
    criteria: list,  # list[AcceptanceCriterion]
    check_cmd: Callable[[str], Awaitable[tuple[int, str]]],
) -> list[ACEvaluation]:
    """Run each AC's command and return a structured evaluation per AC."""
    out: list[ACEvaluation] = []
    for ac in criteria:
        command, expected = _parse_condition(ac.condition)
        if not command:
            out.append(ACEvaluation(
                id=ac.id, condition=ac.condition,
                command=None, expected=expected,
                satisfied=None, exit_code=None,
                evidence_ref=None, note="no command in condition",
            ))
            continue
        try:
            exit_code, summary = await check_cmd(command)
        except Exception as e:
            out.append(ACEvaluation(
                id=ac.id, condition=ac.condition,
                command=command, expected=expected,
                satisfied=None, exit_code=None,
                evidence_ref=None, note=f"exception: {e!r}",
            ))
            continue
        satisfied, note = _evidence_for(ac.condition, exit_code, summary, expected)
        out.append(ACEvaluation(
            id=ac.id, condition=ac.condition,
            command=command, expected=expected,
            satisfied=satisfied, exit_code=exit_code,
            evidence_ref=f"exit={exit_code};summary[:200]={summary[:200]!r}",
            note=note,
        ))
    return out