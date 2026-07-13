"""
Second-model verifier.

Optional cross-check: route the verification report to a different
model (different provider or different version) and demand agreement.
If both models report VERIFIED, the orchestrator promotes the status
to VERIFIED_BY_DUAL_MODEL (a stronger guarantee). If they disagree,
emit DUAL_MODEL_DISAGREEMENT as a HIGH severity finding.

This is OPT-IN. Requires a second API key in env:
  RELIABILITY_2ND_MODEL_PROVIDER  (e.g. "openai", "anthropic", "google")
  RELIABILITY_2ND_MODEL_NAME     (e.g. "gpt-4", "claude-3-5-sonnet")

Cost: doubles the verification cost. Use only for critical tier
by default.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class DualModelResult:
    enabled: bool
    agreed: bool | None
    primary_status: str
    second_status: str | None
    prompt_tokens: int
    completion_tokens: int
    duration_ms: int
    reason_if_skipped: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _second_model_enabled_for_tier(risk_tier: str) -> bool:
    """By default, second model is only used for `critical` tier."""
    if not os.environ.get("RELIABILITY_2ND_MODEL_PROVIDER"):
        return False
    if not os.environ.get("RELIABILITY_2ND_MODEL_NAME"):
        return False
    if os.environ.get("RELIABILITY_2ND_MODEL_ALWAYS") == "1":
        return True
    return risk_tier == "critical"


async def run_dual_model_verification(
    risk_tier: str,
    primary_status: str,
    primary_report: dict[str, Any],
    primary_findings: list[dict[str, Any]],
) -> DualModelResult:
    """
    Send the verification report + findings to a second model and ask:
      "Given this report, would you emit VERIFIED, PARTIALLY_VERIFIED, or BLOCKED?"
    Compare against the primary status.
    """
    if not _second_model_enabled_for_tier(risk_tier):
        return DualModelResult(
            enabled=False, agreed=None,
            primary_status=primary_status, second_status=None,
            prompt_tokens=0, completion_tokens=0, duration_ms=0,
            reason_if_skipped="not enabled (see RELIABILITY_2ND_MODEL_* env vars)",
        )

    provider = os.environ["RELIABILITY_2ND_MODEL_PROVIDER"]
    model = os.environ["RELIABILITY_2ND_MODEL_NAME"]

    prompt = (
        "You are an independent verifier. Given this primary verification report, "
        "respond with EXACTLY one of: VERIFIED, PARTIALLY_VERIFIED, BLOCKED.\n\n"
        f"Primary status: {primary_status}\n"
        f"Primary findings: {json.dumps(primary_findings, indent=2)}\n"
        f"Primary report excerpt: {json.dumps(primary_report.get('nine_point', {}), indent=2)}\n"
    )

    start = time.monotonic()
    prompt_tokens = len(prompt.split()) * 2  # rough; no real tokenizer

    # ---- Begin provider dispatch (scaffolded) ----
    # Each provider has its own SDK. This dispatch table is intentionally
    # explicit so adding a new provider is a one-line change.
    if provider == "openai":
        try:
            from openai import OpenAI  # type: ignore
            client = OpenAI()
            resp = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                )
            )
            second_status = resp.choices[0].message.content.strip().upper()
            completion_tokens = resp.usage.completion_tokens if resp.usage else 0
        except ImportError:
            return DualModelResult(
                enabled=True, agreed=None,
                primary_status=primary_status, second_status=None,
                prompt_tokens=prompt_tokens, completion_tokens=0,
                duration_ms=int((time.monotonic() - start) * 1000),
                reason_if_skipped="openai SDK not installed; pip install openai",
            )
    elif provider == "anthropic":
        try:
            from anthropic import Anthropic  # type: ignore
            client = Anthropic()
            resp = await asyncio.to_thread(
                lambda: client.messages.create(
                    model=model,
                    max_tokens=64,
                    messages=[{"role": "user", "content": prompt}],
                )
            )
            second_status = resp.content[0].text.strip().upper()
            completion_tokens = resp.usage.output_tokens if resp.usage else 0
        except ImportError:
            return DualModelResult(
                enabled=True, agreed=None,
                primary_status=primary_status, second_status=None,
                prompt_tokens=prompt_tokens, completion_tokens=0,
                duration_ms=int((time.monotonic() - start) * 1000),
                reason_if_skipped="anthropic SDK not installed; pip install anthropic",
            )
    else:
        return DualModelResult(
            enabled=True, agreed=None,
            primary_status=primary_status, second_status=None,
            prompt_tokens=prompt_tokens, completion_tokens=0,
            duration_ms=int((time.monotonic() - start) * 1000),
            reason_if_skipped=f"unsupported provider {provider!r}",
        )
    # ---- End provider dispatch ----

    duration_ms = int((time.monotonic() - start) * 1000)
    valid_statuses = {"VERIFIED", "PARTIALLY_VERIFIED", "BLOCKED"}
    if second_status not in valid_statuses:
        return DualModelResult(
            enabled=True, agreed=False,
            primary_status=primary_status, second_status=second_status,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            duration_ms=duration_ms,
            reason_if_skipped=f"second model returned invalid status: {second_status!r}",
        )

    agreed = (second_status == primary_status)
    return DualModelResult(
        enabled=True, agreed=agreed,
        primary_status=primary_status,
        second_status=second_status,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        duration_ms=duration_ms,
    )


async def main(risk_tier: str, primary_status: str, report_file: str) -> int:
    """CLI entry point. Reads report from file, runs dual check, prints JSON."""
    report = json.loads(Path(report_file).read_text(encoding="utf-8"))
    findings = report.get("findings", [])
    result = await run_dual_model_verification(risk_tier, primary_status, report, findings)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.agreed in (True, None) else 1