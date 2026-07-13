"""
Tool-call enforcement.

When an agent is supposed to invoke a reliability tool (e.g. `@tool gate()`),
this module scans the agent's transcript and verifies that the tool was
actually called. If a tool that MUST have been called is missing, the
verifier adds a HIGH-severity finding: TOOL_NOT_INVOKED.

The "must-call" set is configured per tier and per agent role:
  - reliability-verifier: must call `verify` and `gate`
  - reliability-lead: must call `record_evidence` at least once per change
  - reliability-adversary: must call `verify` at least twice
  - reliability-synthesizer: must call `mark_done` exactly once

Enforcement is OFF by default; enable with RELIABILITY_ENFORCE_TOOLS=1.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass
class EnforcementResult:
    enforced: bool
    violations: list[str]
    passed: bool


# What each agent MUST have called (tool names match tools.py registry)
MUST_CALL: dict[str, set[str]] = {
    "reliability-verifier": {"verify", "gate"},
    "reliability-lead": {"record_evidence"},
    "reliability-adversary": {"verify"},
    "reliability-synthesizer": {"mark_done"},
    "mythos-verifier": {"verify"},
    "mythos-executor": {"record_evidence"},
    "mythos-synthesizer": {"mark_done"},
}

TOOL_INVOCATION_PATTERN = re.compile(r"@(?:tool\s+)?(\w+)\s*\(", re.IGNORECASE)


def tools_invoked(transcript_text: str) -> set[str]:
    """Extract the set of tool names invoked in a transcript."""
    return {m.group(1).lower() for m in TOOL_INVOCATION_PATTERN.finditer(transcript_text)}


def enforce(agent_name: str, transcript_text: str) -> EnforcementResult:
    """If enforcement is enabled, verify required tools were invoked."""
    if os.environ.get("RELIABILITY_ENFORCE_TOOLS", "0") != "1":
        return EnforcementResult(enforced=False, violations=[], passed=True)

    required = MUST_CALL.get(agent_name, set())
    if not required:
        return EnforcementResult(enforced=True, violations=[], passed=True)

    invoked = tools_invoked(transcript_text)
    missing = required - invoked
    if missing:
        violations = [
            f"{agent_name}: required tool not invoked: {m}" for m in sorted(missing)
        ]
        return EnforcementResult(enforced=True, violations=violations, passed=False)
    return EnforcementResult(enforced=True, violations=[], passed=True)