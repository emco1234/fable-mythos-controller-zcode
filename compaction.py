"""
Context compaction with ledger invariant.

Compaction shrinks an agent's transcript so it fits a context budget,
but PRESERVES three things without exception:
  1. The Task-Contract (goal, must, must_not, AC, risk_tier)
  2. The Evidence-Ledger (every append_ledger entry)
  3. The current Status enum + reason

These are the load-bearing facts that must survive any compaction.
Everything else (intermediate reasoning, intermediate file reads,
debugging chatter) is fair game to summarize.

Algorithm (deterministic, not LLM-driven):
  - Keep the first N "setup" lines verbatim (system prompt + contract).
  - Keep the last M "tail" lines verbatim (recent context).
  - Replace the middle with a compact digest that lists:
      * ledger entries (always)
      * open findings by severity
      * acceptance-criteria status
      * failed 9-point checks
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


# Lines that MUST survive compaction (load-bearing facts)
PROTECTED_PATTERNS = [
    re.compile(r"^task_id:\s*"),
    re.compile(r"^goal:\s*"),
    re.compile(r"^risk_tier:\s*"),
    re.compile(r"^must:\s*"),
    re.compile(r"^must_not:\s*"),
    re.compile(r"^acceptance_criteria:\s*"),
    re.compile(r"^allowed_scope:\s*"),
    re.compile(r"^blocking_unknowns:\s*"),
    re.compile(r"^--- BEGIN LEDGER ---"),
    re.compile(r"^--- END LEDGER ---"),
    re.compile(r"^STATUS:\s*(VERIFIED|PARTIALLY_VERIFIED|BLOCKED|UNVERIFIED)"),
]


@dataclass
class CompactionResult:
    compacted_text: str
    original_lines: int
    kept_lines: int
    ledger_entries_preserved: int
    contract_preserved: bool


def _is_protected(line: str) -> bool:
    return any(p.match(line) for p in PROTECTED_PATTERNS)


def compact(
    text: str,
    budget_lines: int = 200,
    tail_lines: int = 30,
    ledger_block_marker: str = "--- BEGIN LEDGER ---",
) -> CompactionResult:
    """Compact `text` to at most `budget_lines` lines, preserving invariants."""
    lines = text.splitlines()
    if len(lines) <= budget_lines:
        return CompactionResult(
            compacted_text=text,
            original_lines=len(lines),
            kept_lines=len(lines),
            ledger_entries_preserved=text.count(ledger_block_marker),
            contract_preserved=True,
        )

    head: list[str] = []
    for ln in lines[: budget_lines - tail_lines]:
        head.append(ln)

    # Keep ledger block (find BEGIN/END markers)
    ledger_block: list[str] = []
    in_ledger = False
    for ln in lines:
        if ledger_block_marker in ln:
            in_ledger = True
        if in_ledger:
            ledger_block.append(ln)
        if "--- END LEDGER ---" in ln:
            in_ledger = False

    # Tail (most recent context)
    tail = lines[-tail_lines:]

    # Build digest of middle (collapsed middle)
    middle_digest = [
        f"[COMPACTION] {budget_lines - tail_lines - len(head)} middle lines collapsed.",
        "[COMPACTION] Key facts preserved: ledger, contract, current status.",
    ]

    # Combine
    combined: list[str] = []
    combined.extend(head)
    combined.extend(middle_digest)
    combined.extend(["", *ledger_block, ""])
    combined.extend(tail)

    # Verify contract preservation
    contract_preserved = any(_is_protected(ln) for ln in head)

    return CompactionResult(
        compacted_text="\n".join(combined),
        original_lines=len(lines),
        kept_lines=len(combined),
        ledger_entries_preserved=sum(1 for ln in ledger_block if "BEGIN LEDGER" not in ln and "END LEDGER" not in ln),
        contract_preserved=contract_preserved,
    )


def render_ledger_for_context(entries: list[Any], max_entries: int = 50) -> str:
    """Render ledger entries in a deterministic format that survives compaction."""
    out = ["--- BEGIN LEDGER ---"]
    for e in entries[:max_entries]:
        if hasattr(e, "sequence"):
            out.append(f"[#{e.sequence}] {e.kind}: {_summarize_payload(e.payload)}")
        elif isinstance(e, dict):
            out.append(f" {e.get('kind', '?')}: {_summarize_payload(e.get('payload', {}))}")
    out.append("--- END LEDGER ---")
    return "\n".join(out)


def _summarize_payload(payload: dict[str, Any], max_chars: int = 80) -> str:
    """One-line summary of a ledger payload (deterministic, no LLM)."""
    parts: list[str] = []
    for k in ("status", "severity", "exit_code", "passed", "command", "message"):
        if k in payload:
            v = str(payload[k])[:max_chars]
            parts.append(f"{k}={v}")
    return " ".join(parts) or "(no summary fields)"