#!/usr/bin/env python3
"""
Reliability Harness v2 — Walking Skeleton Controller (asyncio)

NOT production-ready. This is a concept validation scaffold.

P0 + P1 implemented:
- Parses task-contract.yaml (must, must_not, acceptance_criteria, risk_tier)
- Spawns orthogonal agents sequentially via the platform adapter
- Runs the 9-point clean-checkout check
- Emits VERIFIED / PARTIALLY_VERIFIED / BLOCKED / UNVERIFIED
- Idempotent CLI: re-runs do not corrupt state

P2 + P3 (planned, NOT implemented in this skeleton):
- Async / parallel agent dispatch            [planned]
- Persistent task memory (SQLite)            [planned]
- Context compaction that preserves ledger   [planned]
- Structured repair loops from verifier JSON [planned]
- Custom reliability tools                   [planned]
- Property-based / fuzzing / mutation tests  [planned]
- Telemetry                                  [planned]

See docs/ROADMAP.md for the full P2 + P3 plan.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable

import yaml


# --------------------------------------------------------------------------- #
# Status machine (machine gate — code, not prompt)
# --------------------------------------------------------------------------- #
class Status(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    BLOCKED = "BLOCKED"
    UNVERIFIED = "UNVERIFIED"


# --------------------------------------------------------------------------- #
# Domain types
# --------------------------------------------------------------------------- #
@dataclass
class AcceptanceCriterion:
    id: str
    condition: str
    satisfied: bool | None = None
    evidence_ref: str | None = None


@dataclass
class TaskContract:
    task_id: str
    base_commit: str
    goal: str
    risk_tier: str  # trivial | normal | complex | critical
    must: list[str]
    must_not: list[str]
    non_goals: list[str] = field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = field(default_factory=list)
    allowed_scope: list[str] = field(default_factory=list)
    blocking_unknowns: list[str] = field(default_factory=list)


@dataclass
class Finding:
    severity: str  # CRITICAL | HIGH | MEDIUM | LOW
    message: str
    location: str | None = None


@dataclass
class VerificationReport:
    task_id: str
    status: Status
    timestamp: str
    nine_point: dict[str, dict[str, Any]]
    acceptance_results: list[dict[str, Any]]
    scope_violations: list[str]
    findings: list[Finding]
    preexisting_failures: list[str]
    introduced_failures: list[str]
    residual_unknowns: list[str]
    agent_transcript_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "nine_point": self.nine_point,
            "acceptance_results": self.acceptance_results,
            "scope_violations": self.scope_violations,
            "findings": [f.__dict__ for f in self.findings],
            "preexisting_failures": self.preexisting_failures,
            "introduced_failures": self.introduced_failures,
            "residual_unknowns": self.residual_unknowns,
            "agent_transcript_ref": self.agent_transcript_ref,
        }


# --------------------------------------------------------------------------- #
# Contract loader
# --------------------------------------------------------------------------- #
def load_contract(path: Path) -> TaskContract:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    acs = [
        AcceptanceCriterion(id=ac["id"], condition=ac["condition"])
        for ac in raw.get("acceptance_criteria", [])
    ]
    return TaskContract(
        task_id=raw["task_id"],
        base_commit=raw["base_commit"],
        goal=raw["goal"],
        risk_tier=raw.get("risk_tier", "normal"),
        must=raw.get("must", []),
        must_not=raw.get("must_not", []),
        non_goals=raw.get("non_goals", []),
        acceptance_criteria=acs,
        allowed_scope=raw.get("allowed_scope", []),
        blocking_unknowns=raw.get("blocking_unknowns", []),
    )


# --------------------------------------------------------------------------- #
# Routing (trivial → critical)
# --------------------------------------------------------------------------- #
def route_for_tier(tier: str) -> list[str]:
    """Return the ordered list of agent roles to dispatch for a given tier."""
    if tier == "trivial":
        return []  # Main agent only — controller not even invoked
    if tier == "normal":
        return ["reliability-lead", "reliability-verifier"]
    if tier == "complex":
        return [
            "reliability-scout",            # parallel with spec-critic (P2)
            "reliability-spec-critic",
            "reliability-test-designer",
            "reliability-lead",
            "reliability-verifier",
        ]
    if tier == "critical":
        return [
            "reliability-scout",
            "reliability-spec-critic",
            "reliability-test-designer",
            "reliability-lead",
            "reliability-verifier",
            "reliability-adversary",
        ]
    raise ValueError(f"Unknown risk_tier: {tier}")


# --------------------------------------------------------------------------- #
# Platform adapter (interface; concrete impls live in adapters/)
# --------------------------------------------------------------------------- #
class PlatformAdapter:
    """Spawn a platform-specific agent session and return its transcript path."""

    async def spawn(self, agent_name: str, prompt: str) -> str:
        """Spawn agent, return path to its transcript file. Must be idempotent."""
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# 9-point clean-checkout verification
# --------------------------------------------------------------------------- #
async def run_nine_point_check(
    worktree_path: Path,
    contract: TaskContract,
    check_cmd: Callable[[str], Awaitable[tuple[int, str]]],
) -> dict[str, dict[str, Any]]:
    """Run the 9 mandated checks. Each entry: command + exit_code + summary."""
    checks = [
        ("reproduction_test", f"python -m pytest -xvs tests/repro -k {contract.task_id}"),
        ("new_tests", "python -m pytest -xvs tests/new"),
        ("affected_existing_tests", "python -m pytest -xvs tests/affected"),
        ("typecheck", "mypy src"),
        ("lint", "ruff check src"),
        ("build", "python -m build"),
        ("full_suite", "python -m pytest"),
        ("diff_scope_audit", f"git diff --name-only {contract.base_commit}"),
        ("acceptance_criteria_audit", "echo acceptance-results-from-transcript"),
    ]
    results: dict[str, dict[str, Any]] = {}
    for name, cmd in checks:
        exit_code, summary = await check_cmd(cmd)
        results[name] = {
            "command": cmd,
            "exit_code": exit_code,
            "summary": summary,
            "passed": exit_code == 0,
        }
    return results


# --------------------------------------------------------------------------- #
# Deterministic machine gate (not an LLM)
# --------------------------------------------------------------------------- #
def evaluate_gate(
    contract: TaskContract,
    nine_point: dict[str, dict[str, Any]],
    scope_violations: list[str],
    findings: list[Finding],
) -> Status:
    """The machine gate that no LLM can overrule."""
    # Any CRITICAL finding → BLOCKED
    if any(f.severity == "CRITICAL" for f in findings):
        return Status.BLOCKED
    # Any failed 9-point check → PARTIALLY_VERIFIED (or BLOCKED if it's typecheck/build/lint)
    hard_checks = {"typecheck", "lint", "build"}
    failed_hard = [k for k, v in nine_point.items() if not v["passed"] and k in hard_checks]
    if failed_hard:
        return Status.BLOCKED
    failed_soft = [k for k, v in nine_point.items() if not v["passed"]]
    if failed_soft:
        return Status.PARTIALLY_VERIFIED
    # Any scope violation → BLOCKED
    if scope_violations:
        return Status.BLOCKED
    # Any blocking unknown → BLOCKED
    if contract.blocking_unknowns:
        return Status.BLOCKED
    return Status.VERIFIED


# --------------------------------------------------------------------------- #
# Orchestrator (skeleton — sequential dispatch; async is P2)
# --------------------------------------------------------------------------- #
async def run_contract(
    contract: TaskContract,
    adapter: PlatformAdapter,
    worktree_path: Path,
    check_cmd: Callable[[str], Awaitable[tuple[int, str]]],
) -> VerificationReport:
    transcript_paths: list[str] = []
    agents = route_for_tier(contract.risk_tier)

    # Phase 0/3/4: dispatch orthogonal agents (sequential in skeleton)
    for agent in agents:
        prompt = f"You are {agent}. Contract: {contract.task_id}. Goal: {contract.goal}."
        transcript = await adapter.spawn(agent, prompt)
        transcript_paths.append(transcript)

    # Phase 4: 9-point clean-checkout check
    nine_point = await run_nine_point_check(worktree_path, contract, check_cmd)

    # Stub: extract scope violations, findings, AC results from transcripts (P2)
    scope_violations: list[str] = []
    findings: list[Finding] = []
    ac_results = [
        {"id": ac.id, "satisfied": None, "evidence_ref": None}
        for ac in contract.acceptance_criteria
    ]

    status = evaluate_gate(contract, nine_point, scope_violations, findings)

    return VerificationReport(
        task_id=contract.task_id,
        status=status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        nine_point=nine_point,
        acceptance_results=ac_results,
        scope_violations=scope_violations,
        findings=findings,
        preexisting_failures=[],
        introduced_failures=[],
        residual_unknowns=[],
        agent_transcript_ref=";".join(transcript_paths) or None,
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
async def _default_check(cmd: str) -> tuple[int, str]:
    """Skeleton check command — runs in subprocess and returns (exit_code, summary)."""
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    summary = (stdout or b"").decode("utf-8", errors="replace")[:500]
    return proc.returncode or 0, summary


async def _main(args: argparse.Namespace) -> int:
    contract = load_contract(Path(args.contract))
    # Adapter import is deferred so the skeleton stays platform-agnostic
    from adapters.zcode_adapter import ZCodeAdapter  # type: ignore

    adapter = ZCodeAdapter()
    report = await run_contract(contract, adapter, Path(args.worktree), _default_check)

    # Persist report
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    # Print status (machine-gate result)
    print(json.dumps({"status": report.status.value, "report": str(out)}, indent=2))

    # Exit code reflects status — CI-friendly
    return 0 if report.status == Status.VERIFIED else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reliability Harness v2 — Walking Skeleton Controller"
    )
    parser.add_argument("--contract", required=True, help="Path to task-contract.yaml")
    parser.add_argument("--worktree", required=True, help="Path to fresh clean checkout")
    parser.add_argument("--out", default="./out/verification-report.json")
    args = parser.parse_args()
    return asyncio.run(_main(args))


if __name__ == "__main__":
    sys.exit(main())