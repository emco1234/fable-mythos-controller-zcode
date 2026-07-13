"""
Structured repair loops.

When a verifier returns findings (JSON-serialised), the lead agent is
re-prompted with the findings as a STRUCTURED list. Each finding has
an id, severity, location, and a fix-suggestion. The lead must
acknowledge each finding (FIXED / WONT_FIX / NEEDS_MORE_INFO).

The repair loop has a hard cap (default 3). Beyond the cap, status
is BLOCKED with reason REPAIR_BUDGET_EXHAUSTED.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RepairDisposition(str, Enum):
    FIXED = "FIXED"
    WONT_FIX = "WONT_FIX"
    NEEDS_MORE_INFO = "NEEDS_MORE_INFO"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass
class RepairFinding:
    id: str
    severity: str  # CRITICAL | HIGH | MEDIUM | LOW
    message: str
    location: str | None = None
    fix_suggestion: str | None = None
    disposition: RepairDisposition | None = None
    repair_round: int = 0
    note: str | None = None


@dataclass
class RepairLoop:
    findings: list[RepairFinding] = field(default_factory=list)
    round: int = 0
    max_rounds: int = 3

    def add(self, finding: RepairFinding) -> None:
        finding.repair_round = self.round
        self.findings.append(finding)

    def unresolved(self) -> list[RepairFinding]:
        """Findings the lead has not yet FIXED."""
        return [f for f in self.findings if f.disposition != RepairDisposition.FIXED]

    def next_round(self) -> bool:
        """Advance to the next round. Returns False if budget exhausted."""
        if self.round >= self.max_rounds:
            return False
        self.round += 1
        return True

    def render_for_lead(self) -> str:
        """Build the prompt injected into the lead agent's next turn."""
        if not self.findings:
            return "(no findings — verifier approved patch)"
        out = [
            f"REPAIR LOOP round {self.round + 1}/{self.max_rounds}",
            "",
            "The verifier returned the following findings on your last patch.",
            "For EACH finding, respond with one of: FIXED / WONT_FIX / NEEDS_MORE_INFO / OUT_OF_SCOPE.",
            "For FIXED, describe the concrete change you made (file:line).",
            "For WONT_FIX, justify why the finding is invalid.",
            "For NEEDS_MORE_INFO, request the specific data you need.",
            "For OUT_OF_SCOPE, declare that the fix lies outside allowed_scope.",
            "",
        ]
        for f in self.findings:
            sev = f.severity
            loc = f" @ {f.location}" if f.location else ""
            out.append(f"[{f.id}] {sev}{loc}: {f.message}")
            if f.fix_suggestion:
                out.append(f"    Suggested fix: {f.fix_suggestion}")
            out.append("")
        return "\n".join(out)

    def to_json(self) -> str:
        return json.dumps(
            {
                "round": self.round,
                "max_rounds": self.max_rounds,
                "findings": [f.__dict__ for f in self.findings],
            },
            indent=2,
        )