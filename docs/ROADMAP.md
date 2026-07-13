# Roadmap — fable-mythos-controller-{grok,opencode,zcode}

This document tracks what is implemented vs. what is still planned.

## ✅ Implemented (P2 + P3 — all features in place)

| # | Item | Module | Tests |
|---|---|---|---|
| P2 #1 | Async / parallel agent dispatch | `controller_v2.py` (`_dispatch_parallel`) | `test_controller_v2.py::test_complex_dispatches_in_parallel_phase_then_serial` |
| P2 #2 | Persistent task memory (SQLite) | `memory.py` | `test_memory.py` (6 tests) |
| P2 #3 | Context compaction with ledger invariant | `compaction.py` | `test_compaction.py` (4 tests) |
| P2 #4 | Structured repair loops | `repair.py` | `test_repair.py` (6 tests) |
| P2 #5 | Custom reliability tools (`verify`, `gate`, `record_evidence`, `budget_status`, `mark_done`) | `tools.py` | `test_tools.py` (3 tests) |
| P2 #6 | Token / latency budget enforcement | `budget.py` | `test_budget.py` (6 tests) |
| P3 #1 | Property-based testing (Hypothesis / fast-check / proptest) | `property_tests.py` | `test_property_tests.py` (5 tests) |
| P3 #2 | Fuzzing (Atheris / cargo-fuzz) | `fuzz.py` | `test_fuzz.py` (3 tests) |
| P3 #3 | Mutation testing (mutmut / Stryker / cargo-mutants) | `mutation.py` | `test_mutation.py` (4 tests) |
| P3 #4 | Differential tests (left vs. right checkouts) | `differential.py` | (smoke-tested via CLI) |
| P3 #5 | Second model as verifier (opt-in via env) | `second_model.py` | (requires 2nd API key; scaffolded) |
| P3 #6 | Anonymized telemetry (opt-in via env) | `telemetry.py` | `test_telemetry.py` (4 tests) |

**Total: 48 unit tests pass.**

## Smoke test

```bash
pip install pyyaml
python run_tests.py                    # all 48 tests should pass
python controller.py --contract examples/task-contract.example.yaml --worktree . --out out/verification-report.json
python controller_v2.py --contract examples/task-contract.example.yaml --worktree . --memory-db out/memory.sqlite --out out/verification-report.json
```

## What is NOT yet implemented

| Item | Status | Notes |
|---|---|---|
| Real CLI dispatch in adapters | stubbed | adapters write prompt to `.transcripts/`, do not actually invoke `grok` / `opencode` / `zcode` CLIs. Wiring is platform-specific; see platform docs. |
| Resume across crashes | scaffolded | `memory.can_resume()` returns True for non-terminal status, but no entry point to resume yet |
| Tool-side call enforcement | registry only | tools are registered and callable; the LLM-side enforcement (the lead actually USING `@tool gate()` instead of ignoring it) requires platform-level integration |
| P3 #1-3 runtime (the actual `hypothesis`/`mutmut` invocation) | wired but depends on target repo having those tools installed | detection works; execution requires the target repo to install them |
| P3 #5 second model | scaffolded for OpenAI + Anthropic | other providers (Google, Cohere) need a 5-line dispatch addition |

## Validation strategy

To decide whether the controller approach is preferable to the prompt-only harness in `emco1234/fable-mythos-{grok,opencode,zcode}`:

1. Run both harnesses on the same task corpus (5-10 real coding tasks)
2. Compare: false_done_rate, regression_rate, tokens spent, latency
3. If the controller wins on ≥ 2 of 4 metrics → graduate to v2 of the prompt-based repos
4. If the controller does not win → keep the prompt-based harness and document why

See `emco1234/fable-mythos-grok/docs/EMPIRICAL-BENCHMARK-PLAN.md` for the full validation plan.