"""
Resume CLI entry point.

Resumes a previously interrupted task from its SQLite memory DB.

Usage:
  python controller_resume.py --memory-db out/memory.sqlite --contract contract.yaml
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from controller import load_contract as _load_contract_yaml, Status
from controller_v2 import ControllerV2
from memory import TaskMemory


def _build_adapter(platform: str, worktree: Path):
    """Lazy-build the platform-specific adapter. ImportError → returns stub."""
    adapters = {
        "grok": ("adapters.grok_adapter", "GrokAdapter"),
        "opencode": ("adapters.opencode_adapter", "OpenCodeAdapter"),
        "zcode": ("adapters.zcode_adapter", "ZCodeAdapter"),
    }
    if platform not in adapters:
        raise ValueError(f"unknown platform {platform!r}")
    module_name, class_name = adapters[platform]
    try:
        import importlib
        mod = importlib.import_module(module_name)
        cls = getattr(mod, class_name)
        return cls(default_cwd=worktree)
    except (ImportError, AttributeError):
        # Adapter file not in this repo — return a minimal stub.
        class _StubAdapter:
            async def spawn(self, agent_name: str, prompt: str) -> str:
                from datetime import datetime, timezone
                from pathlib import Path
                p = Path(".transcripts") / f"{agent_name}-stub-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.md"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(f"# STUB: {platform}/{agent_name}\n\n{prompt}\n", encoding="utf-8")
                return str(p)
        return _StubAdapter()


async def _main(args: argparse.Namespace) -> int:
    contract = _load_contract_yaml(Path(args.contract))
    memory = TaskMemory(Path(args.memory_db))
    if not memory.can_resume(contract.task_id):
        print(json.dumps({
            "error": "cannot resume",
            "task_id": contract.task_id,
            "reason": "no open run found (or last status was VERIFIED/BLOCKED)",
        }, indent=2))
        return 2

    # Build the appropriate adapter per platform
    platform = args.platform
    adapter = _build_adapter(platform, Path(args.worktree))

    controller = ControllerV2(adapter=adapter, memory=memory)
    async def _default_check(cmd: str) -> tuple[int, str]:
        import asyncio
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode or 0, (stdout or b"").decode("utf-8", errors="replace")[:500]

    report = await controller.run(contract, Path(args.worktree), _default_check)
    print(json.dumps({
        "status": report.status.value,
        "task_id": contract.task_id,
        "resumed": True,
    }, indent=2))
    return 0 if report.status == Status.VERIFIED else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resume a previously interrupted controller run",
    )
    parser.add_argument("--memory-db", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--worktree", default=".")
    parser.add_argument("--platform", required=True, choices=("grok", "opencode", "zcode"))
    args = parser.parse_args()
    return asyncio.run(_main(args))


if __name__ == "__main__":
    sys.exit(main())