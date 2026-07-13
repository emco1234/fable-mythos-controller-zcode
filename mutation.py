"""
Mutation testing harness.

Runs a mutation-testing tool to measure how many introduced mutants
are killed by the test suite. A low kill rate means tests are weak
(they pass even when the code is broken).

Per-language adapter:
  - Python: mutmut (https://mutmut.readthedocs.io)
  - TypeScript: Stryker (https://stryker-mutator.io)
  - Rust: cargo-mutants (https://github.com/sourcefrog/cargo-mutants)

Mutation testing is SLOW — run in CI nightly, not per-PR.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MutationResult:
    backend: str
    total_mutants: int
    killed: int
    survived: int
    timeout: int
    kill_rate_pct: float
    duration_ms: int
    stdout_tail: str
    stderr_tail: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _detect_backend(worktree: Path) -> str:
    if (worktree / "setup.cfg").exists() and "mutmut" in (worktree / "setup.cfg").read_text(encoding="utf-8", errors="ignore"):
        return "mutmut"
    if (worktree / "pyproject.toml").exists() and "mutmut" in (worktree / "pyproject.toml").read_text(encoding="utf-8", errors="ignore"):
        return "mutmut"
    if (worktree / "stryker.conf.js").exists() or (worktree / "stryker.conf.json").exists():
        return "stryker"
    if shutil.which("cargo-mutants") and (worktree / "Cargo.toml").exists():
        return "cargo-mutants"
    return "unknown"


async def run_mutation_tests(
    worktree: Path,
    timeout_s: int = 600,
    sample_limit: int = 50,  # for CI nightly: full run; for fast feedback: limit
) -> MutationResult:
    """Run mutation testing with a hard timeout. Returns structured result."""
    backend = _detect_backend(worktree)
    if backend == "unknown":
        return MutationResult(
            "unknown", 0, 0, 0, 0, 0.0, 0,
            "(no mutation framework detected — skipped)", "",
        )
    py = sys.executable
    start = asyncio.get_event_loop().time()

    if backend == "mutmut":
        cmd = [py, "-m", "mutmut", "run", "--runner", f"python -m pytest -x -q", "--no-progress"]
    elif backend == "stryker":
        cmd = ["npx", "stryker", "run", f"--mutate={sample_limit}", "--reporters=json"]
    elif backend == "cargo-mutants":
        cmd = ["cargo", "mutants", "--no-shuffle", "--timeout", "60"]
    else:
        return MutationResult(backend, 0, 0, 0, 0, 0.0, 0, "(unsupported)", "")

    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(worktree),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        return MutationResult(backend, 0, 0, 0, 0, 0.0, int(timeout_s * 1000), "(timeout)", "(timeout)")

    duration_ms = int((asyncio.get_event_loop().time() - start) * 1000)
    out = (stdout_b or b"").decode("utf-8", errors="replace")
    err = (stderr_b or b"").decode("utf-8", errors="replace")
    killed, survived, timeout_count, total = 0, 0, 0, 0
    for line in out.splitlines():
        line_l = line.lower()
        if "killed" in line_l and ":" in line:
            try:
                killed = int(line.split(":")[-1].strip())
            except ValueError:
                pass
        if "survived" in line_l and ":" in line:
            try:
                survived = int(line.split(":")[-1].strip())
            except ValueError:
                pass
        if "timeout" in line_l and ":" in line:
            try:
                timeout_count = int(line.split(":")[-1].strip())
            except ValueError:
                pass
    total = killed + survived + timeout_count
    kill_rate = (killed / total * 100.0) if total else 0.0
    return MutationResult(
        backend=backend,
        total_mutants=total,
        killed=killed,
        survived=survived,
        timeout=timeout_count,
        kill_rate_pct=kill_rate,
        duration_ms=duration_ms,
        stdout_tail=out[-1500:],
        stderr_tail=err[-1500:],
    )


async def main(worktree: str, timeout_s: int = 600) -> int:
    """CLI entry point. Prints JSON, exits 0 if kill_rate >= 70% else 1."""
    result = await run_mutation_tests(Path(worktree), timeout_s=timeout_s)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.kill_rate_pct >= 70.0 else 1