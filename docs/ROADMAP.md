# Roadmap — fable-mythos-controller-{grok,opencode,zcode}

All planned features are now implemented. The walking skeleton is preserved
in `controller.py` as a reference for the minimal DAG shape.

## ✅ Implemented (full P2 + P3)

| # | Item | Module | Tests |
|---|---|---|---|
| P2 #1 | Async / parallel agent dispatch | `controller_v2.py` | `test_controller_v2.py` |
| P2 #2 | Persistent task memory (SQLite) | `memory.py` | `test_memory.py` (6 tests) |
| P2 #3 | Context compaction with ledger invariant | `compaction.py` | `test_compaction.py` (4 tests) |
| P2 #4 | Structured repair loops | `repair.py` | `test_repair.py` (6 tests) |
| P2 #5 | Custom reliability tools | `tools.py` | `test_tools.py` (3 tests) |
| P2 #6 | Token / latency budget enforcement | `budget.py` | `test_budget.py` (6 tests) |
| P3 #1 | Property-based testing | `property_tests.py` | `test_property_tests.py` (5 tests) |
| P3 #2 | Fuzzing | `fuzz.py` | `test_fuzz.py` (3 tests) |
| P3 #3 | Mutation testing | `mutation.py` | `test_mutation.py` (4 tests) |
| P3 #4 | Differential tests | `differential.py` | CLI-tested |
| P3 #5 | Second-model verifier (5 providers) | `second_model.py` | wired; SDK-gated |
| P3 #6 | Anonymized telemetry | `telemetry.py` | `test_telemetry.py` (4 tests) |
| — | Real CLI adapters (grok/opencode/zcode) | `adapters/*.py` | `test_adapters.py` (2 tests) |
| — | Resume CLI entry point | `resume.py` | (manual via `--platform`) |
| — | Git worktree management | `worktree.py` | `test_worktree.py` (3 tests) |
| — | Acceptance-criteria evaluation | `acceptance.py` | `test_acceptance.py` (5 tests) |
| — | Tool-call enforcement | `enforcement.py` | `test_enforcement.py` (5 tests) |
| — | Telemetry dashboard | `dashboard.py` | `test_dashboard.py` (3 tests) |

**Total: 74 unit tests pass on Python 3.13.**

## What the controller does end-to-end

```
1. Load task-contract.yaml (must/must_not/AC/risk_tier)
2. Save contract + init ledger in SQLite
3. Dispatch orthogonal agents in parallel (scout + spec-critic + test-designer)
4. Dispatch serial agents (lead, verifier, adversary for critical)
5. Verify each agent invoked required tools (@tool gate(), @tool verify(), etc.)
6. Run 9-point clean-checkout check (tests, typecheck, lint, build)
7. Run per-AC evaluation (run the AC's command, check output)
8. If findings: enter repair loop (3-round cap)
9. Evaluate deterministic machine gate → emit VERIFIED/PARTIAL/BLOCKED
10. If critical tier: dispatch second-model verifier (opt-in, 5 providers)
11. Compact large transcripts (preserves ledger + contract + status)
12. Check budget → BLOCKED if exceeded
13. Persist final report + ledger + budget to SQLite
14. Emit anonymized telemetry record (opt-in via env)
```

## CLI entry points

| Command | Purpose |
|---|---|
| `python controller.py` | Walking skeleton (reference only) |
| `python controller_v2.py` | Full orchestrator |
| `python resume.py` | Resume an interrupted task from SQLite |
| `python dashboard.py` | Telemetry aggregator → JSON or Markdown |
| `python run_tests.py` | All 74 tests |

## What is STILL NOT implemented (honest)

| Item | Status | Notes |
|---|---|---|
| Real agent invocation when CLIs are missing | falls back to stub | Adapter writes prompt to `.transcripts/` with reason. Caller decides whether to BLOCK. |
| P3 #5 second-model providers | SDK-gated | Only runs when provider SDK + API key present. Otherwise skipped. |
| Provider dispatch beyond the 5 listed | not implemented | Adding Google/Cohere/Mistral is a one-block addition in `second_model.py`. |
| Resume cross-process state | partial | `memory.can_resume()` exists; `resume.py` requires `--platform` to know which adapter to use. Auto-detection from ledger is not implemented. |

## Validation strategy

To decide whether the controller approach is preferable to the prompt-only harness in `emco1234/fable-mythos-{grok,opencode,zcode}`:

1. Run both harnesses on the same task corpus (5-10 real coding tasks)
2. Compare: false_done_rate, regression_rate, tokens spent, latency
3. If the controller wins on ≥ 2 of 4 metrics → graduate to v2 of the prompt-based repos
4. If the controller does not win → keep the prompt-based harness and document why