# fable-mythos-controller-zcode

**Walking Skeleton** — concept validation for a deterministic Python asyncio controller that drives the Reliability Harness v2 inside [ZCode CLI](https://zcode.ai).

> ⚠️ **NOT production-ready.** This is a concept-validation scaffold to test whether a code-based controller is preferable to the prompt-only harness in [`emco1234/fable-mythos-zcode`](https://github.com/emco1234/fable-mythos-zcode). The existing `fable-mythos-zcode` repo is unchanged on `main` and continues to work via pure prompting.

---

## What this repo is

| Component | Status |
|---|---|
| Task-contract YAML schema + loader | ✅ Implemented |
| Routing by `risk_tier` (trivial → critical) | ✅ Implemented |
| 9-point clean-checkout check (scaffold commands) | ✅ Implemented |
| Machine gate (deterministic status emission) | ✅ Implemented |
| ZCode CLI adapter (stub) | ✅ Implemented |
| Async / parallel agent dispatch | ⏳ P2 |
| Persistent task memory (SQLite) | ⏳ P2 |
| Context compaction with ledger invariant | ⏳ P2 |
| Structured repair loops | ⏳ P2 |
| Custom reliability tools | ⏳ P2 |
| Property-based / fuzzing / mutation tests | ⏳ P3 |
| Telemetry | ⏳ P3 |

---

## Quick start (smoke test)

```bash
# 1. Install Python deps
pip install pyyaml

# 2. Run the controller against the example contract
python controller.py \
  --contract examples/task-contract.example.yaml \
  --worktree . \
  --out out/verification-report.json
```

Expected:
- `out/verification-report.json` is written
- Status field reflects the machine gate (likely `VERIFIED` or `PARTIALLY_VERIFIED` for the example)
- Exit code is `0` only when `status == VERIFIED`

---

## Why three new repos?

The original three (`fable-mythos-grok`, `fable-mythos-opencode`, `fable-mythos-zcode`) work via prompt-only sub-agents. This controller replaces prompt-based orchestration with a Python DAG scheduler — a fundamentally different architecture. The new repos are isolated for testing so the prompt-based harnesses keep working.

Once the controller concept is validated here, the long-term plan is to:
1. Refine the controller until it's production-ready
2. Port to `fable-mythos-zcode` as a new major version
3. Mirror to the other platforms as well

---

## Repository structure

```
fable-mythos-controller-zcode/
├── controller.py                       # Walking-skeleton controller (asyncio)
├── adapters/
│   └── zcode_adapter.py                # ZCode CLI spawn adapter (stub)
├── examples/
│   └── task-contract.example.yaml      # Example contract for smoke test
├── out/                                # Generated verification reports
├── .transcripts/                       # Agent transcripts (gitignored)
├── docs/
│   └── ROADMAP.md                      # P2 + P3 plan
└── README.md
```

---

## Honest scope

This walking skeleton validates **the shape** of a controller, not its features. It does not yet:
- Spawn real ZCode subagents (the adapter is a stub; ZCode Custom Subagents are Beta and currently run in the foreground)
- Run real tests/build/lint (commands are scaffolded)
- Run async / in parallel
- Persist memory across runs
- Repair loops

It DOES demonstrate:
- Task-contract → routing → agent-dispatch → 9-point-check → machine-gate pipeline
- Status emission that no LLM can overrule
- A path to swap stubs for real adapters in P2

---

## See also

- [`emco1234/fable-mythos-zcode`](https://github.com/emco1234/fable-mythos-zcode) — Prompt-based harness (production-ready, unchanged)
- [`emco1234/fable-mythos-controller-grok`](https://github.com/emco1234/fable-mythos-controller-grok) — Same skeleton for Grok Build CLI
- [`emco1234/fable-mythos-controller-opencode`](https://github.com/emco1234/fable-mythos-controller-opencode) — Same skeleton for OpenCode
- `anpassungen.md` — the analysis that motivated this work

## Primary MAP for daily use

**Do not use this controller as your primary MAP setup.** Daily reliable MAP is the **prompt-based** harness (able-mythos-zcode / able-mythos-opencode / able-mythos-grok). This controller remains an experimental walking skeleton with stub adapters.
