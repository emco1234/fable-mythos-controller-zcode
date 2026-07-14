---
name: fable-mythos-controller
description: |
  Run the Reliability Harness v2 Controller on the current coding task.
  Use when the user asks for: "use the controller", "verify this with the controller",
  "run the reliability harness", "check this with v2", "test my code with the controller",
  "audit with controller", or any explicit request to drive a coding task through
  the deterministic Python controller at ~/.zcode/skills/fable-mythos-controller/scripts/run-controller.sh.
  Also use when the user submits a non-trivial coding task and asks for a verification,
  review, or analysis through "the harness" or "v2".
when-to-use: "use the controller", "verify with controller", "run v2", "controller audit"
allowed-tools: ["read", "grep", "glob", "bash"]
argument-hint: <coding task description>
---

# fable-mythos-controller — Auto-Trigger Skill

When the user submits a coding task that should be driven through the
deterministic Python controller (not the prompt-only sub-agent path),
follow this procedure.

## When to fire

Fire this skill when the user request matches any of:

- "use the controller", "controller test", "verify with controller"
- "run v2", "reliability harness v2", "controller audit"
- "audit with harness", "verify my code with v2"
- Any explicit mention of "controller" + (coding / audit / verify / test / review)

Do NOT fire for: pure Q&A, code reading without changes, file exploration,
or tasks that explicitly ask for the prompt-only subagent harness
(`mythos-*` / `reliability-*` agent names).

## Procedure

1. **Identify the target repo.** The current working directory is the
   default. If the user names a path, use that instead.

2. **Inspect the repo** (read-only): `ls`, check for `pyproject.toml` /
   `package.json` / `Cargo.toml` to detect language. Note the test runner
   (`pytest`, `npm test`, `cargo test`, etc.).

3. **Generate a task-contract YAML** in the user's working directory at
   `.fable-mythos/contract-<short-id>.yaml`. The schema is:

   ```yaml
   task_id: <short-id>           # e.g. "fix-typo-20260714"
   base_commit: HEAD
   goal: <one sentence>
   risk_tier: trivial | normal | complex | critical
   must:
     - <observable requirement>
   must_not:
     - <prohibition>
   non_goals: []
   acceptance_criteria:
     - id: AC1
       condition: <command> | <expected output substring>
   allowed_scope:
     - "<glob>"
   blocking_unknowns: []
   ```

   Risk-tier heuristic:
   - **trivial** = typo, 1-line, value change, comment
   - **normal** = standard bugfix, single-file change
   - **complex** = multi-file, schema/API change, unclear spec
   - **critical** = security-sensitive, concurrency, data-loss risk

   For non-trivial tasks, write **at least one acceptance criterion** that
   exercises the existing test suite (e.g.
   `<absolute path to python> -m pytest -q | 2 passed`).

4. **Invoke the controller** via the helper script. The script handles
   Python discovery, error handling, and report rendering:

   ```bash
   bash ~/.zcode/skills/fable-mythos-controller/scripts/run-controller.sh \
     --contract .fable-mythos/contract-<short-id>.yaml \
     --worktree <target-repo-path> \
     --platform zcode
   ```

   If the user did not say "modify" or "fix", default to read-only mode:
   pass `--read-only` to the script and write the contract to
   `.fable-mythos/audit-<short-id>.yaml` instead.

5. **Read the resulting report** at `<out>/verification-report.json`.
   Surface the `status` field (one of `VERIFIED`, `PARTIALLY_VERIFIED`,
   `BLOCKED`, `UNVERIFIED`) and a 5-line summary to the user.

6. **Do not modify any source file.** The controller itself runs agents
   and may modify the target repo; you (the LLM) must not. The user
   can ask the controller to apply changes via `--allow-write`.

## What the controller does (don't duplicate)

The controller already handles:

- Spawning orthogonal agents (scout / spec-critic / test-designer / lead /
  verifier / adversary) per `risk_tier`
- 9-point clean-checkout verification (tests / typecheck / lint / build)
- Per-AC evidence check (run the AC command, grep for expected output)
- Structured repair loop (3-round cap)
- SQLite-backed memory (contracts, ledger, reports, budget)
- Anonymized telemetry (opt-in via `RELIABILITY_TELEMETRY=1`)
- Deterministic machine-gate that emits `VERIFIED` / `PARTIAL` / `BLOCKED`
  regardless of LLM opinion

You do not need to do any of this yourself. After the controller runs,
your job is to **interpret the report** and explain it to the user.

## Output to the user

After the controller completes, show:

```
Controller report (status: <STATUS>)
  AC1: satisfied=True  — "2 passed"
  AC2: satisfied=False — "exit 1"
  Findings: <N>
  Report path: <out>/verification-report.json
  Memory DB:   <out>/memory.sqlite
  Transcripts: .transcripts/ (5 files)
```

If the user wants more detail, point them to the report path.

## Limits (honest)

- Controller adapters that spawn real ZCode agents require an active
  ZCode login. Without login, the adapter writes a STUB transcript and
  the controller still emits a status (machine-gate is code, not LLM).
- The 9-point check uses scaffold commands (`mypy src`, `ruff check src`,
  `python -m build`). For projects that don't match this layout, customise
  the contract's `acceptance_criteria` instead.
- The controller does not modify any file by default. To apply patches,
  use the prompt-only harness (`mythos-lead` / `reliability-lead`) or pass
  `--allow-write` (planned, not yet wired in this version).
