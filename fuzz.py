"""
Fuzzing adapter.

Provides a thin interface to language-specific fuzzers:
  - Python: Atheris (libFuzzer-compatible)
  - Rust: cargo-fuzz / libFuzzer
  - C/C++: libFuzzer directly

This module does NOT bundle fuzzers; it expects them to be installed
in the target repo. It runs them with a configurable timeout and
parses their output for crashes + coverage.
"""
from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class FuzzResult:
    backend: str
    duration_s: int
    crashes: int
    coverage_pct: float | None
    corpus_size: int
    timed_out: bool
    stdout_tail: str
    stderr_tail: str
    crash_artifacts: list[str]

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _detect_backend(worktree: Path) -> str:
    if (worktree / "fuzz" / "fuzz_*.py").exists() or any(worktree.glob("fuzz/fuzz_*.py")):
        return "atheris"
    if (worktree / "fuzz").is_dir() and any((worktree / "fuzz").glob("fuzz_*.rs")):
        return "cargo-fuzz"
    return "unknown"


async def run_fuzz(
    worktree: Path,
    duration_s: int = 30,
    target: str | None = None,
) -> FuzzResult:
    """Run fuzzing for `duration_s` seconds. Returns a structured result."""
    backend = _detect_backend(worktree)
    if backend == "unknown":
        return FuzzResult(
            backend="unknown", duration_s=0, crashes=0, coverage_pct=None,
            corpus_size=0, timed_out=False,
            stdout_tail="(no fuzz harness detected — skipped)",
            stderr_tail="", crash_artifacts=[],
        )
    if backend == "atheris":
        if not target:
            targets = list((worktree / "fuzz").glob("fuzz_*.py"))
            if not targets:
                return FuzzResult(backend, 0, 0, None, 0, False, "(no fuzz targets)", "", [])
            target = str(targets[0])
        cmd = ["python", target, f"-max_total_time={duration_s}"]
    elif backend == "cargo-fuzz":
        if not target:
            return FuzzResult(backend, 0, 0, None, 0, False, "(target required for cargo-fuzz)", "", [])
        cmd = ["cargo", "fuzz", "run", target, "--", f"-max_total_time={duration_s}"]
    else:
        return FuzzResult(backend, 0, 0, None, 0, False, "(unsupported backend)", "", [])

    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(worktree),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=duration_s + 30)
    except asyncio.TimeoutError:
        proc.kill()
        return FuzzResult(
            backend, duration_s, 0, None, 0, True,
            "(fuzz run timed out, killed)", "", [],
        )
    out = (stdout_b or b"").decode("utf-8", errors="replace")
    err = (stderr_b or b"").decode("utf-8", errors="replace")
    crashes = out.lower().count("==ERROR==") + err.lower().count("==ERROR==")
    crash_artifacts = [p for p in (worktree / "fuzz" / "artifacts").rglob("*") if p.is_file()] if (worktree / "fuzz" / "artifacts").exists() else []
    coverage = None
    if "cov:" in out:
        try:
            coverage = float(out.split("cov:")[1].split()[0].rstrip(",%"))
        except (ValueError, IndexError):
            coverage = None
    return FuzzResult(
        backend=backend,
        duration_s=duration_s,
        crashes=crashes,
        coverage_pct=coverage,
        corpus_size=out.lower().count("cov:"),  # rough
        timed_out=False,
        stdout_tail=out[-1500:],
        stderr_tail=err[-1500:],
        crash_artifacts=[str(p) for p in crash_artifacts[:10]],
    )


async def main(worktree: str, duration_s: int = 30, target: str | None = None) -> int:
    """CLI entry point. Prints JSON, exits 0 if no crashes else 1."""
    result = await run_fuzz(Path(worktree), duration_s=duration_s, target=target)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.crashes == 0 else 1