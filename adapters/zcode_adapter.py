"""
ZCode CLI adapter for the Walking Skeleton controller.

Spawns an agent via ZCode Custom Subagents and writes the transcript to .transcripts/.
NOTE: This is a scaffold — wire to the real ZCode CLI invocation in P2.

ZCode Custom Subagents are Beta and use ~/.zcode/agents/<name>.md files.
The controller cannot spawn ZCode subagents asynchronously today, so this
adapter falls back to direct prompt dispatch (one chat session per agent).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from controller import PlatformAdapter


TRANSCRIPT_DIR = Path(".transcripts")


class ZCodeAdapter(PlatformAdapter):
    """Spawn a ZCode subagent and capture its transcript."""

    async def spawn(self, agent_name: str, prompt: str) -> str:
        TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        transcript_path = TRANSCRIPT_DIR / f"{agent_name}-{timestamp}.md"

        # Scaffold: write the prompt as the transcript. Replace with real
        # ZCode dispatch (await per-subagent chat session) in P2.
        transcript_path.write_text(
            f"# Transcript stub for {agent_name}\n\nPrompt:\n\n{prompt}\n",
            encoding="utf-8",
        )

        await asyncio.sleep(0)
        return str(transcript_path)