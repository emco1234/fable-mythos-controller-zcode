# Roadmap — fable-mythos-controller-{grok,opencode,zcode}

This document tracks what is implemented in the **walking skeleton** vs what is planned for P2 (real agentik) and P3 (frontier-level).

## Walking skeleton (this commit)

Implemented:
- `controller.py` — Python 3.11+ asyncio orchestrator
- Task-contract YAML schema + loader
- Routing by `risk_tier` (trivial / normal / complex / critical)
- 9-point clean-checkout check scaffold (commands run, results captured)
- Deterministic machine gate (no LLM can override)
- Per-platform adapter (stub)

Smoke test:
```bash
python controller.py --contract examples/task-contract.example.yaml --worktree . --out out/verification-report.json
```

---

## P2 — Real agentik

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | Lang-lived agents (resume / context-inherit) | planned | requires platform support; Grok has `resume_from` |
| 2 | Persistent task memory (SQLite per task_id) | planned | schema in `core/task-contract.schema.json` from sibling repo |
| 3 | Context compaction that preserves ledger | planned | requires explicit ledger boundary in compaction policy |
| 4 | Async / parallel dispatch for `complex`+ tiers | planned | `asyncio.gather` for scout + spec-critic + test-designer |
| 5 | Custom reliability tools (e.g. `@tool gate()`) | planned | depends on platform (OpenCode custom tools, Grok plugin extension) |
| 6 | Structured repair loops | planned | verifier returns JSON findings → lead agent addresses |
| 7 | Per-task token / latency budget enforcement | planned | hard timeout + cost cap, BLOCKED on overflow |

## P3 — Frontier-level

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | Property-based testing (Hypothesis / fast-check) | planned | per-language adapter |
| 2 | Fuzzing (libFuzzer / Atheris) | planned | security tier only |
| 3 | Mutation testing (mutmut / Stryker) | planned | CI nightly, not per-PR |
| 4 | Differential tests vs reference impl | planned | opt-in per repo |
| 5 | Second model as verifier | planned | requires second API key, opt-in |
| 6 | Telemetry (anonymized failure modes) | planned | DSGVO opt-in only |

---

## Validation strategy

The walking skeleton is **concept validation**, not a feature drop. To decide whether the controller approach is preferable to prompt-only:

1. Run both harnesses on the same task corpus (5-10 real coding tasks)
2. Compare: false_done_rate, regression_rate, tokens spent, latency
3. If the controller wins on ≥ 2 of 4 metrics → proceed to P2 implementation
4. If the controller does not win → keep the prompt-based harness and document why

See `emco1234/fable-mythos-grok/docs/EMPIRICAL-BENCHMARK-PLAN.md` for the full validation plan.

---

## Why not just add a controller to the existing repo?

- The prompt-based harness is already used by users; we cannot break it
- The controller is a fundamentally different architecture; mixing them in one repo creates confusion
- Three parallel controller repos let us validate the concept on three platforms independently

After validation, the plan is to **graduate** the controller into the main repos as a v2.0 release, not replace v1.