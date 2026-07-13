"""
Persistent task memory (SQLite).

Stores Task-Contract, Evidence-Ledger, Routing-Decisions, Findings,
Verification-Reports per task_id across runs. Resume a previous run by
loading the same task_id.

Schema:
  contracts(task_id, base_commit, goal, risk_tier, raw_yaml, created_at)
  ledger(task_id, sequence, kind, payload, created_at)
    -- kind: AGENT_TRANSCRIPT | FINDING | REPAIR_ATTEMPT | EVIDENCE
  reports(task_id, status, payload_json, created_at)
  budget(task_id, tokens_used, latency_ms, blocked_reason)
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS contracts (
    task_id     TEXT PRIMARY KEY,
    base_commit TEXT NOT NULL,
    goal        TEXT NOT NULL,
    risk_tier   TEXT NOT NULL,
    raw_yaml    TEXT NOT NULL,
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger (
    task_id    TEXT NOT NULL,
    sequence   INTEGER NOT NULL,
    kind       TEXT NOT NULL,
    payload    TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (task_id, sequence)
);

CREATE TABLE IF NOT EXISTS reports (
    task_id    TEXT NOT NULL,
    status     TEXT NOT NULL,
    payload    TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS budget (
    task_id        TEXT PRIMARY KEY,
    tokens_used    INTEGER NOT NULL DEFAULT 0,
    latency_ms     INTEGER NOT NULL DEFAULT 0,
    blocked_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_ledger_task ON ledger(task_id, sequence);
CREATE INDEX IF NOT EXISTS idx_reports_task ON reports(task_id, created_at);
"""


@dataclass
class LedgerEntry:
    sequence: int
    kind: str
    payload: dict[str, Any]
    created_at: float


class TaskMemory:
    """SQLite-backed persistent memory for a task_id."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ----- contracts ----- #
    def save_contract(self, task_id: str, base_commit: str, goal: str,
                      risk_tier: str, raw_yaml: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO contracts VALUES (?, ?, ?, ?, ?, ?)",
                (task_id, base_commit, goal, risk_tier, raw_yaml, time.time()),
            )

    def load_contract(self, task_id: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM contracts WHERE task_id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else None

    # ----- ledger (append-only) ----- #
    def append_ledger(self, task_id: str, kind: str, payload: dict[str, Any]) -> LedgerEntry:
        with self._conn() as c:
            last_seq = c.execute(
                "SELECT COALESCE(MAX(sequence), 0) FROM ledger WHERE task_id = ?",
                (task_id,),
            ).fetchone()[0]
            entry = LedgerEntry(
                sequence=last_seq + 1,
                kind=kind,
                payload=payload,
                created_at=time.time(),
            )
            c.execute(
                "INSERT INTO ledger VALUES (?, ?, ?, ?, ?)",
                (task_id, entry.sequence, entry.kind, json.dumps(entry.payload), entry.created_at),
            )
            return entry

    def load_ledger(self, task_id: str) -> list[LedgerEntry]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT sequence, kind, payload, created_at FROM ledger WHERE task_id = ? ORDER BY sequence",
                (task_id,),
            ).fetchall()
            return [
                LedgerEntry(
                    sequence=r["sequence"],
                    kind=r["kind"],
                    payload=json.loads(r["payload"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    # ----- reports ----- #
    def save_report(self, task_id: str, status: str, payload: dict[str, Any]) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO reports VALUES (?, ?, ?, ?)",
                (task_id, status, json.dumps(payload), time.time()),
            )

    def latest_report(self, task_id: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT status, payload FROM reports WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
                (task_id,),
            ).fetchone()
            if not row:
                return None
            return {"status": row["status"], "payload": json.loads(row["payload"])}

    # ----- budget ----- #
    def record_budget(self, task_id: str, tokens: int, latency_ms: int,
                      blocked_reason: str | None = None) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO budget VALUES (?, ?, ?, ?)",
                (task_id, tokens, latency_ms, blocked_reason),
            )

    def load_budget(self, task_id: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM budget WHERE task_id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else None

    # ----- resume helper ----- #
    def can_resume(self, task_id: str) -> bool:
        """True if a previous run exists and last status is not terminal."""
        latest = self.latest_report(task_id)
        if not latest:
            return False
        return latest["status"] not in ("VERIFIED", "BLOCKED")