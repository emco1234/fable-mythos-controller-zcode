#!/usr/bin/env bash
# fable-mythos-controller — helper script invoked by the LLM via bash.
#
# Resolves the controller repo + python, then runs controller_v2.py with the
# provided task-contract and worktree. Writes the verification report +
# memory DB to ./out/ inside the worktree by default.
#
# Usage:
#   bash run-controller.sh --contract <contract.yaml> --worktree <repo-path>
#                          [--platform zcode]
#                          [--read-only]
#                          [--out <report-path>]
#                          [--memory-db <sqlite-path>]
#
# Exit code:
#   0  controller emitted VERIFIED
#   1  controller emitted PARTIALLY_VERIFIED / BLOCKED / UNVERIFIED
#   2  usage / argument error
#   3  controller not found, python not found, or contract missing

set -euo pipefail

# ---- Defaults ----
PLATFORM="zcode"
READ_ONLY=0
OUT=""
MEMORY_DB=""
CONTRACT=""
WORKTREE=""

# ---- Argument parsing ----
while [[ $# -gt 0 ]]; do
  case "$1" in
    --contract)   CONTRACT="${2:-}"; shift 2 ;;
    --worktree)   WORKTREE="${2:-}"; shift 2 ;;
    --platform)   PLATFORM="${2:-}"; shift 2 ;;
    --out)        OUT="${2:-}"; shift 2 ;;
    --memory-db)  MEMORY_DB="${2:-}"; shift 2 ;;
    --read-only)  READ_ONLY=1; shift ;;
    -h|--help)
      sed -n '2,15p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

# ---- Locate the controller repo ----
# Resolution order:
#   1. env var FABLE_MYTHOS_CONTROLLER_DIR
#   2. marker file <skill>/.controller-dir (written by install.sh)
#   3. sibling-of-scripts convention (this script lives in <controller>/scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ -n "${FABLE_MYTHOS_CONTROLLER_DIR:-}" ]]; then
  CONTROLLER_DIR="$FABLE_MYTHOS_CONTROLLER_DIR"
elif [[ -f "$SKILL_DIR/.controller-dir" ]]; then
  CONTROLLER_DIR="$(cat "$SKILL_DIR/.controller-dir")"
else
  CONTROLLER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

if [[ ! -f "$CONTROLLER_DIR/controller_v2.py" ]]; then
  echo "ERROR: controller_v2.py not found at $CONTROLLER_DIR/controller_v2.py" >&2
  echo "Resolution tried:" >&2
  echo "  - FABLE_MYTHOS_CONTROLLER_DIR env: ${FABLE_MYTHOS_CONTROLLER_DIR:-<unset>}" >&2
  echo "  - marker file: $SKILL_DIR/.controller-dir ($( [[ -f "$SKILL_DIR/.controller-dir" ]] && echo found || echo missing))" >&2
  echo "  - sibling-of-scripts: $SCRIPT_DIR/.." >&2
  exit 3
fi

# ---- Locate Python ----
PYTHON_BIN=""
for candidate in python python3 /c/Python313/python.exe; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v "$candidate")"
    break
  fi
done
if [[ -z "$PYTHON_BIN" ]]; then
  echo "ERROR: python not found in PATH" >&2
  exit 3
fi

# ---- Validate inputs ----
if [[ -z "$CONTRACT" ]]; then
  echo "ERROR: --contract is required" >&2
  exit 2
fi
if [[ ! -f "$CONTRACT" ]]; then
  echo "ERROR: contract not found: $CONTRACT" >&2
  exit 3
fi
if [[ -z "$WORKTREE" ]]; then
  WORKTREE="$(pwd)"
fi
if [[ ! -d "$WORKTREE" ]]; then
  echo "ERROR: worktree not found: $WORKTREE" >&2
  exit 3
fi

# ---- Defaults ----
[[ -z "$OUT" ]] && OUT="$WORKTREE/.fable-mythos/verification-report.json"
[[ -z "$MEMORY_DB" ]] && MEMORY_DB="$WORKTREE/.fable-mythos/memory.sqlite"

mkdir -p "$(dirname "$OUT")" "$(dirname "$MEMORY_DB")"

# ---- Env overrides for the adapter ----
# Force a non-existent zcode binary path so the adapter falls back to stubs
# when the user runs without an active ZCode login.
export RELIABILITY_ZCODE_BIN="${RELIABILITY_ZCODE_BIN:-/nonexistent/zcode-binary-by-script}"

# ---- Run the controller ----
echo "[run-controller] contract: $CONTRACT"
echo "[run-controller] worktree: $WORKTREE"
echo "[run-controller] platform: $PLATFORM"
echo "[run-controller] read-only: $READ_ONLY"
echo "[run-controller] out: $OUT"
echo "[run-controller] memory: $MEMORY_DB"

set +e
"$PYTHON_BIN" "$CONTROLLER_DIR/controller_v2.py" \
  --contract "$CONTRACT" \
  --worktree "$WORKTREE" \
  --memory-db "$MEMORY_DB" \
  --out "$OUT"
CONTROLLER_RC=$?
set -e

echo ""
echo "[run-controller] controller exit code: $CONTROLLER_RC"
echo "[run-controller] report: $OUT"
echo "[run-controller] memory: $MEMORY_DB"

# ---- Print status to stdout for easy LLM consumption ----
if [[ -f "$OUT" ]]; then
  echo ""
  echo "[run-controller] === STATUS SUMMARY ==="
  "$PYTHON_BIN" -c "
import json, sys
try:
    r = json.load(open(r'$OUT', encoding='utf-8'))
    print(f\"  status: {r.get('status', 'UNKNOWN')}\")
    print(f\"  task_id: {r.get('task_id', '?')}\")
    acs = r.get('acceptance_results', [])
    sat = sum(1 for a in acs if a.get('satisfied'))
    print(f\"  acceptance_criteria: {sat}/{len(acs)} satisfied\")
    findings = r.get('findings', [])
    high = sum(1 for f in findings if f.get('severity') in ('HIGH','CRITICAL'))
    print(f\"  findings: {len(findings)} total, {high} HIGH/CRITICAL\")
except Exception as e:
    print(f'  could not parse report: {e}', file=sys.stderr)
"
fi

# Map controller status to our exit code:
#   controller_v2.py exits 0 only when status == VERIFIED
#   we mirror that behaviour
exit $CONTROLLER_RC
