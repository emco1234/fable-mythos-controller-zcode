"""
Token/latency budget enforcement.

The controller tracks per-task token consumption and elapsed latency.
When either exceeds the configured limit, the controller emits BLOCKED
with reason BUDGET_EXHAUSTED and aborts further agent dispatches.

Limits are configurable per risk_tier:
  trivial  → no limit (skipped)
  normal   → 200k tokens, 5 min
  complex  → 1M tokens, 30 min
  critical → 2M tokens, 90 min
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BudgetExceededReason(str, Enum):
    TOKENS = "TOKENS"
    LATENCY = "LATENCY"


DEFAULT_LIMITS: dict[str, tuple[int, int]] = {
    # (max_tokens, max_latency_ms)
    "trivial": (0, 0),            # no limit
    "normal": (200_000, 5 * 60 * 1000),
    "complex": (1_000_000, 30 * 60 * 1000),
    "critical": (2_000_000, 90 * 60 * 1000),
}


@dataclass
class BudgetTracker:
    risk_tier: str
    tokens_used: int = 0
    latency_ms: int = 0
    started_at: float = 0.0

    @property
    def limit_tokens(self) -> int:
        return DEFAULT_LIMITS.get(self.risk_tier, (0, 0))[0]

    @property
    def limit_latency_ms(self) -> int:
        return DEFAULT_LIMITS.get(self.risk_tier, (0, 0))[1]

    def record(self, tokens: int, latency_ms: int) -> None:
        self.tokens_used += tokens
        self.latency_ms += latency_ms

    def exceeded(self) -> BudgetExceededReason | None:
        if self.limit_tokens and self.tokens_used > self.limit_tokens:
            return BudgetExceededReason.TOKENS
        if self.limit_latency_ms and self.latency_ms > self.limit_latency_ms:
            return BudgetExceededReason.LATENCY
        return None

    def status(self) -> dict[str, int | str]:
        return {
            "risk_tier": self.risk_tier,
            "tokens_used": self.tokens_used,
            "tokens_limit": self.limit_tokens,
            "latency_ms": self.latency_ms,
            "latency_limit_ms": self.limit_latency_ms,
        }