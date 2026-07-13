"""
Telemetry aggregator / dashboard.

Reads the JSONL events from .telemetry/events.jsonl and emits
aggregated statistics:
  - run count by risk_tier
  - status distribution (VERIFIED / PARTIAL / BLOCKED / UNVERIFIED)
  - failure modes
  - mean tokens / latency by tier

CLI:
  python dashboard.py --path .telemetry/events.jsonl
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path


def aggregate(path: Path) -> dict:
    by_tier: dict[str, list[dict]] = defaultdict(list)
    statuses: Counter = Counter()
    failure_modes: Counter = Counter()
    total_records = 0

    if not path.exists():
        return {"error": f"telemetry file not found: {path}"}

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        total_records += 1
        tier = rec.get("risk_tier", "unknown")
        by_tier[tier].append(rec)
        statuses[rec.get("status", "UNKNOWN")] += 1
        if rec.get("failure_mode"):
            failure_modes[rec["failure_mode"]] += 1

    out: dict = {
        "total_records": total_records,
        "by_risk_tier": {},
        "status_distribution": dict(statuses),
        "top_failure_modes": dict(failure_modes.most_common(10)),
    }
    for tier, records in by_tier.items():
        tokens = [r.get("tokens_total", 0) for r in records]
        latencies = [r.get("latency_total_ms", 0) for r in records]
        out["by_risk_tier"][tier] = {
            "count": len(records),
            "mean_tokens": statistics.mean(tokens) if tokens else 0,
            "median_tokens": statistics.median(tokens) if tokens else 0,
            "mean_latency_ms": statistics.mean(latencies) if latencies else 0,
            "median_latency_ms": statistics.median(latencies) if latencies else 0,
            "mean_repair_rounds": statistics.mean(
                [r.get("repair_rounds_used", 0) for r in records]
            ) if records else 0,
            "mean_dispatches": statistics.mean(
                [r.get("agent_dispatch_count", 0) for r in records]
            ) if records else 0,
        }
    return out


def render_markdown(agg: dict) -> str:
    if "error" in agg:
        return f"# Telemetry dashboard\n\n_{agg['error']}_\n"
    out = [
        "# Telemetry dashboard\n",
        f"Total records: {agg['total_records']}\n",
        "## Status distribution\n",
    ]
    for status, count in agg["status_distribution"].items():
        out.append(f"- **{status}**: {count}")
    if agg["top_failure_modes"]:
        out.append("\n## Top failure modes\n")
        for mode, count in agg["top_failure_modes"].items():
            out.append(f"- {mode}: {count}")
    if agg["by_risk_tier"]:
        out.append("\n## By risk tier\n")
        for tier, stats in agg["by_risk_tier"].items():
            out.append(
                f"### {tier} (n={stats['count']})\n"
                f"- mean tokens: {stats['mean_tokens']:.0f}\n"
                f"- mean latency: {stats['mean_latency_ms']:.0f} ms\n"
                f"- mean dispatches: {stats['mean_dispatches']:.1f}\n"
                f"- mean repair rounds: {stats['mean_repair_rounds']:.1f}\n"
            )
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Telemetry aggregator / dashboard",
    )
    parser.add_argument("--path", default=".telemetry/events.jsonl")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    agg = aggregate(Path(args.path))
    if args.format == "markdown":
        print(render_markdown(agg))
    else:
        print(json.dumps(agg, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())