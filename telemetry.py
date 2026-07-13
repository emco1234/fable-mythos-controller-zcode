"""
Anonymized telemetry.

Records (per task_id, anonymously):
  - risk_tier, status, agent_dispatch_count, repair_rounds_used
  - token_total, latency_total_ms
  - failure_mode (CRITICAL_FINDING | TEST_FAILURE | BUDGET_EXHAUSTED | REPAIR_BUDGET_EXHAUSTED | UNKNOWN)

NO prompt contents, NO file paths, NO user-supplied data. Storage is
local JSONL in .telemetry/ by default. Opt-in via env var
RELIABILITY_TELEMETRY=1.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_TELEMETRY_DIR = Path(".telemetry")


@dataclass
class TelemetryRecord:
    timestamp: float
    task_id_hash: str  # 8-char SHA256 prefix, NOT the raw task_id
    risk_tier: str
    status: str
    agent_dispatch_count: int
    repair_rounds_used: int
    tokens_total: int
    latency_total_ms: int
    failure_mode: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


def _hash_task_id(task_id: str) -> str:
    import hashlib
    return hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:8]


def enabled() -> bool:
    return os.environ.get("RELIABILITY_TELEMETRY", "0") == "1"


def record(record: TelemetryRecord, path: Path | None = None) -> None:
    """Append a record to the JSONL telemetry file. No-op if telemetry is disabled."""
    if not enabled():
        return
    out = path or (DEFAULT_TELEMETRY_DIR / "events.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.__dict__, separators=(",", ":")) + "\n")


def make_record(
    task_id: str,
    risk_tier: str,
    status: str,
    agent_dispatch_count: int,
    repair_rounds_used: int,
    tokens_total: int,
    latency_total_ms: int,
    failure_mode: str | None = None,
    **extras: Any,
) -> TelemetryRecord:
    return TelemetryRecord(
        timestamp=time.time(),
        task_id_hash=_hash_task_id(task_id),
        risk_tier=risk_tier,
        status=status,
        agent_dispatch_count=agent_dispatch_count,
        repair_rounds_used=repair_rounds_used,
        tokens_total=tokens_total,
        latency_total_ms=latency_total_ms,
        failure_mode=failure_mode,
        extras=dict(extras),
    )