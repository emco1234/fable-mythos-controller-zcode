"""
Property-based testing harness (Hypothesis).

Wraps Hypothesis so the controller can run property tests against the
target repo's pure functions, not just example-based tests.

Per-language adapter:
  - Python: Hypothesis (native)
  - TypeScript/JavaScript: fast-check (via subprocess)
  - Rust: proptest (via cargo test)
"""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PropertyTestResult:
    framework: str
    passed: bool
    test_count: int
    shrunk_examples: int
    duration_ms: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _detect_framework(worktree: Path) -> str:
    """Best-effort detection of property-testing framework."""
    # Hypothesis (Python) — check pyproject/requirements/setup first (most reliable)
    for cfg in ("pyproject.toml", "requirements.txt", "setup.py"):
        f = worktree / cfg
        if f.exists() and "hypothesis" in f.read_text(encoding="utf-8", errors="ignore").lower():
            return "hypothesis"
    if (worktree / "hypothesis_searches.txt").exists():
        return "hypothesis"
    # fast-check (JS/TS)
    pkg = worktree / "package.json"
    if pkg.exists() and "fast-check" in pkg.read_text(encoding="utf-8", errors="ignore"):
        return "fast-check"
    # proptest (Rust)
    cargo = worktree / "Cargo.toml"
    if cargo.exists() and "proptest" in cargo.read_text(encoding="utf-8", errors="ignore"):
        return "proptest"
    return "unknown"


async def run_property_tests(
    worktree: Path,
    timeout_s: int = 120,
    python_executable: str | None = None,
) -> PropertyTestResult:
    """Detect framework and run property tests; return a structured result."""
    framework = _detect_framework(worktree)
    py = python_executable or sys.executable
    start = asyncio.get_event_loop().time()

    if framework == "hypothesis":
        cmd = [py, "-m", "pytest", "-x", "--tb=short", "--hypothesis-show-statistics", "tests/"]
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(worktree),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
    elif framework == "fast-check":
        if not shutil.which("npx"):
            return PropertyTestResult("fast-check", False, 0, 0, 0, "", "npx not installed")
        cmd = ["npx", "jest", "--testPathPattern=property"]
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(worktree),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
    elif framework == "proptest":
        cmd = ["cargo", "test", "--", "--test-threads=1"]
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(worktree),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
    else:
        return PropertyTestResult("unknown", True, 0, 0, 0, "(no framework detected — skipped)", "")

    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        return PropertyTestResult(framework, False, 0, 0, int((asyncio.get_event_loop().time() - start) * 1000), "", f"timeout after {timeout_s}s")

    duration_ms = int((asyncio.get_event_loop().time() - start) * 1000)
    out = (stdout_b or b"").decode("utf-8", errors="replace")
    err = (stderr_b or b"").decode("utf-8", errors="replace")
    return PropertyTestResult(
        framework=framework,
        passed=(proc.returncode == 0),
        test_count=0,
        shrunk_examples=out.lower().count("shrunk example"),
        duration_ms=duration_ms,
        stdout=out[:2000],
        stderr=err[:2000],
    )


async def main(worktree: str, timeout_s: int = 120) -> int:
    """CLI entry point. Prints JSON result, exits 0 on PASS else 1."""
    result = await run_property_tests(Path(worktree), timeout_s=timeout_s)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.passed else 1