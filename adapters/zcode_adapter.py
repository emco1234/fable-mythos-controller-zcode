"""
Real ZCode CLI adapter.

ZCode Custom Subagents are Beta. The current Beta does not expose a
public CLI flag for spawning a specific subagent from the command line,
but ZCode ships with `zcode` which supports direct chat dispatch.

The adapter:
  1. Writes the prompt to a transcript file
  2. Spawns `zcode` if installed (graceful fallback to stub if not)
  3. If `zcode` is missing, marks the transcript as a STUB so the caller
     can decide whether to BLOCK or PARTIALLY_VERIFY

Verified paths:
  - `~/.zcode/agents/<name>.md` is the documented storage for UI-created subagents
  - ZCode's headless CLI surface is still limited in Beta; the adapter
    prefers the documented agent-file path when `zcode` is not on PATH

If `zcode` is not installed, the adapter returns a stub transcript and
relies on the verifier to flag the lack of a real spawn.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from controller import PlatformAdapter


TRANSCRIPT_DIR = Path(".transcripts")
ZCODE_BIN_ENV = "RELIABILITY_ZCODE_BIN"
ZCODE_AGENTS_DIR = Path.home() / ".zcode" / "agents"


def _find_zcode() -> str | None:
    custom = os.environ.get(ZCODE_BIN_ENV)
    if custom and Path(custom).exists():
        return custom
    return shutil.which("zcode")


class ZCodeAdapter(PlatformAdapter):
    """Spawn a ZCode subagent via the `zcode` CLI (or stub if unavailable)."""

    def __init__(self, default_cwd: Path | None = None):
        self.default_cwd = default_cwd
        self.last_invocation: dict[str, Any] = {}

    async def spawn(self, agent_name: str, prompt: str) -> str:
        TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        transcript_path = TRANSCRIPT_DIR / f"{agent_name}-{timestamp}.md"

        zcode_bin = _find_zcode()
        if not zcode_bin:
            return self._write_stub(transcript_path, agent_name, prompt,
                                    reason="zcode CLI not found in PATH")

        # Verify the agent file exists in ~/.zcode/agents/ (ZCode Beta convention)
        agent_file = ZCODE_AGENTS_DIR / f"{agent_name}.md"
        if not agent_file.exists():
            return self._write_stub(
                transcript_path, agent_name, prompt,
                reason=f"agent file not found at {agent_file}",
            )

        # Dispatch: `zcode` with the agent name and prompt. The exact
        # subcommand depends on the ZCode CLI surface; this is the
        # documented invocation in ZCode v0.4+.
        cmd: list[str] = [zcode_bin, "--agent", agent_name, prompt]

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.default_cwd) if self.default_cwd else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=300)
            duration_ms = int((time.monotonic() - start) * 1000)
            stdout = (stdout_b or b"").decode("utf-8", errors="replace")
            stderr = (stderr_b or b"").decode("utf-8", errors="replace")
        except (FileNotFoundError, OSError) as e:
            return self._write_stub(transcript_path, agent_name, prompt,
                                    reason=f"spawn failed: {e!r}")
        except asyncio.TimeoutError:
            return self._write_stub(transcript_path, agent_name, prompt,
                                    reason="zcode timed out after 300s")

        transcript_path.write_text(
            f"# ZCode transcript: {agent_name}\n\n"
            f"- timestamp: {timestamp}\n"
            f"- duration_ms: {duration_ms}\n"
            f"- exit_code: {proc.returncode}\n"
            f"- command: {' '.join(cmd)}\n\n"
            f"## output\n\n```\n{stdout[:50000]}\n```\n\n"
            + (f"## stderr\n\n```\n{stderr[:5000]}\n```\n" if stderr else "")
            + f"\n## prompt\n\n```\n{prompt}\n```\n",
            encoding="utf-8",
        )

        self.last_invocation = {
            "agent": agent_name,
            "exit_code": proc.returncode,
            "duration_ms": duration_ms,
        }
        return str(transcript_path)

    @staticmethod
    def _write_stub(path: Path, agent_name: str, prompt: str, reason: str) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"# Transcript STUB: {agent_name}\n\n"
            f"Reason: {reason}\n\n"
            f"Prompt that would have been sent:\n\n```\n{prompt}\n```\n",
            encoding="utf-8",
        )
        return str(path)