"""
Differential test harness.

Runs the same test suite against two implementations (e.g. old vs.
new) and compares results. Any divergence is a finding.

Use cases:
  - Refactor: ensure behaviour is preserved
  - Library upgrade: detect breaking changes
  - Optimisation: ensure equivalence
"""
from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DifferentialResult:
    passed: bool
    divergent_tests: list[str]
    total_compared: int
    duration_ms: int
    left_label: str
    right_label: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


async def _run_test_suite(cwd: Path, cmd: list[str], env: dict[str, str] | None = None) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        env={**__import__("os").environ, **(env or {})},
    )
    stdout_b, stderr_b = await proc.communicate()
    return (
        proc.returncode or 0,
        (stdout_b or b"").decode("utf-8", errors="replace"),
        (stderr_b or b"").decode("utf-8", errors="replace"),
    )


async def run_differential(
    left: tuple[Path, list[str], str],
    right: tuple[Path, list[str], str],
    timeout_s: int = 300,
) -> DifferentialResult:
    """
    left, right: (cwd, command, label) tuples.
    Runs the same test command in two checkouts and diffs the results.
    """
    import time
    start = time.monotonic()
    left_rc, left_out, left_err = await asyncio.wait_for(
        _run_test_suite(left[0], left[1]), timeout=timeout_s,
    ) if False else await _run_test_suite(left[0], left[1])
    right_rc, right_out, right_err = await asyncio.wait_for(
        _run_test_suite(right[0], right[1]), timeout=timeout_s,
    ) if False else await _run_test_suite(right[0], right[1])

    left_tests = _extract_test_names(left_out)
    right_tests = _extract_test_names(right_out)
    only_left = sorted(left_tests - right_tests)
    only_right = sorted(right_tests - left_tests)
    divergent = only_left + only_right

    duration_ms = int((time.monotonic() - start) * 1000)
    passed = (left_rc == 0 and right_rc == 0) and not divergent
    notes = ""
    if left_rc != right_rc:
        notes = f"exit codes differ: left={left_rc}, right={right_rc}"
    return DifferentialResult(
        passed=passed,
        divergent_tests=divergent[:200],  # cap
        total_compared=len(left_tests | right_tests),
        duration_ms=duration_ms,
        left_label=left[2],
        right_label=right[2],
        notes=notes,
    )


def _extract_test_names(output: str) -> set[str]:
    """Pull 'PASSED test_xyz' / 'FAILED test_xyz' / 'ok test_xyz' style names."""
    names: set[str] = set()
    for line in output.splitlines():
        line_l = line.lower()
        for marker in ("passed", "failed", "ok "):
            if marker in line_l:
                parts = line.strip().split()
                for p in parts:
                    if "::" in p or p.startswith("test_"):
                        names.add(p)
                        break
                break
    return names


async def main(
    left_dir: str,
    right_dir: str,
    cmd: str,
    timeout_s: int = 300,
) -> int:
    """CLI entry point. Both dirs run the same `cmd`. Prints JSON diff."""
    cmd_list = cmd.split()
    result = await run_differential(
        left=(Path(left_dir), cmd_list, f"{left_dir}:{cmd}"),
        right=(Path(right_dir), cmd_list, f"{right_dir}:{cmd}"),
        timeout_s=timeout_s,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.passed else 1