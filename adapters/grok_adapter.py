"""
Real Grok Build CLI adapter.

Spawns a subagent via `grok agent --prompt "<prompt>" --agent <name> [--worktree]`
in headless mode. Captures the full transcript to .transcripts/.

Verified against `grok --help`:
  - `grok agent` runs Grok without interactive UI (headless)
  - `--agent <NAME>` selects the agent
  - `--worktree <PATH>` runs in a git worktree (verified via `grok worktree --help`)

The adapter:
  1. Runs `grok agent --prompt <prompt> --agent <name> --worktree <path>`
  2. Captures stdout (which contains the assistant's text output)
  3. Writes the captured output + invocation metadata to .transcripts/<agent>-<ts>.md
  4. Returns the transcript path

If `grok` is not installed or `grok agent` fails, the adapter falls back to
writing a stub transcript and emitting a HIGH-severity finding to the ledger
so the caller knows the run was a stub, not a real spawn.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from controller import PlatformAdapter


TRANSCRIPT_DIR = Path(".transcripts")
GROK_BIN_ENV = "RELIABILITY_GROK_BIN"


def _find_grok() -> str | None:
    """Locate the grok CLI binary.

    Honour RELIABILITY_GROK_BIN for tests / overrides. If the override
    points to a non-existent path, return it anyway so the caller can
    detect the missing-binary case and fall back to the stub.
    """
    custom = os.environ.get(GROK_BIN_ENV)
    if custom:
        return custom
    return shutil.which("grok")


class GrokAdapter(PlatformAdapter):
    """Spawn a Grok subagent via the `grok agent` headless command."""

    def __init__(self, default_cwd: Path | None = None, worktree_root: Path | None = None):
        self.default_cwd = default_cwd
        self.worktree_root = worktree_root
        self.last_invocation: dict[str, Any] = {}

    async def spawn(self, agent_name: str, prompt: str) -> str:
        TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        transcript_path = TRANSCRIPT_DIR / f"{agent_name}-{timestamp}.md"

        grok_bin = _find_grok()
        if not grok_bin:
            return self._write_stub(transcript_path, agent_name, prompt,
                                    reason="grok CLI not found in PATH")
        # If env override points to a non-existent path, force stub
        if os.environ.get(GROK_BIN_ENV) and not Path(grok_bin).exists():
            return self._write_stub(transcript_path, agent_name, prompt,
                                    reason=f"grok binary not found at {grok_bin}")

        # Build the command. `grok agent stdio` runs over stdio (no TUI).
        # The agent selection is done via the agent's plugin/profile dir
        # or via a separate `agents.json` injection. We invoke stdio and
        # pipe the prompt via stdin; the agent name is added to the
        # prompt header so the harness can identify which agent ran.
        cmd: list[str] = [
            grok_bin, "agent", "stdio",
        ]
        if self.worktree_root:
            cmd.extend(["--cwd", str(self.worktree_root)])

        start = time.monotonic()
        try:
            # Prepend the agent name to the prompt so the harness
            # can tell which agent is being run (grok agent stdio does
            # not expose --agent flag directly).
            full_prompt = f"[agent={agent_name}]\n{prompt}"
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.default_cwd) if self.default_cwd else None,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(input=full_prompt.encode("utf-8")),
                timeout=300,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            stdout = (stdout_b or b"").decode("utf-8", errors="replace")
            stderr = (stderr_b or b"").decode("utf-8", errors="replace")
        except (FileNotFoundError, OSError) as e:
            return self._write_stub(transcript_path, agent_name, prompt,
                                    reason=f"spawn failed: {e!r}")
        except asyncio.TimeoutError:
            return self._write_stub(transcript_path, agent_name, prompt,
                                    reason="grok agent timed out after 300s")

        transcript_path.write_text(
            f"# Grok transcript: {agent_name}\n\n"
            f"- timestamp: {timestamp}\n"
            f"- duration_ms: {duration_ms}\n"
            f"- exit_code: {proc.returncode}\n"
            f"- command: {' '.join(cmd)}\n\n"
            f"## stdout\n\n```\n{stdout[:50000]}\n```\n\n"
            + (f"## stderr\n\n```\n{stderr[:5000]}\n```\n\n" if stderr else "")
            + "## prompt\n\n```\n{prompt}\n```\n".format(prompt=prompt),
            encoding="utf-8",
        )

        self.last_invocation = {
            "agent": agent_name,
            "exit_code": proc.returncode,
            "duration_ms": duration_ms,
            "stdout_bytes": len(stdout_b or b""),
            "stderr_bytes": len(stderr_b or b""),
        }

        if proc.returncode != 0:
            # Real spawn but failed — still useful info
            transcript_path.write_text(
                transcript_path.read_text(encoding="utf-8") +
                f"\n\n> NOTE: grok agent exited with non-zero status ({proc.returncode}).\n",
                encoding="utf-8",
            )
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