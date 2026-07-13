"""
Git worktree management for clean-checkout verification.

The controller mandates verification on a FRESH worktree at the base_commit
(per the verification-report schema). This module:

  1. Creates an isolated worktree from `base_commit`
  2. Returns the path to it
  3. Cleans it up afterwards (configurable — keep for debugging possible)

Backed by git CLI (`git worktree add`). Verified against git 2.30+.
"""
from __future__ import annotations

import asyncio
import shutil
import time
from pathlib import Path
from typing import Any


async def _git(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    if shutil.which("git") is None:
        return (127, "", "git not installed")
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_b, stderr_b = await proc.communicate()
    return (
        proc.returncode or 0,
        (stdout_b or b"").decode("utf-8", errors="replace"),
        (stderr_b or b"").decode("utf-8", errors="replace"),
    )


async def create_clean_worktree(
    repo_root: Path,
    base_commit: str,
    worktree_path: Path,
    branch_name: str | None = None,
) -> dict[str, Any]:
    """
    Create an isolated git worktree at `worktree_path` from `base_commit`.

    Returns a dict with: ok, path, branch, base_commit, error (if any).
    """
    worktree_path = Path(worktree_path)
    branch = branch_name or f"reliability-verify-{int(time.time())}"

    rc, out, err = await _git("rev-parse", "--verify", base_commit, cwd=repo_root)
    if rc != 0:
        return {
            "ok": False,
            "path": None,
            "branch": None,
            "base_commit": base_commit,
            "error": f"base_commit {base_commit!r} not valid: {err.strip()}",
        }

    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    rc, out, err = await _git(
        "worktree", "add", "-b", branch, str(worktree_path), base_commit,
        cwd=repo_root,
    )
    if rc != 0:
        # If branch already exists, try without -b
        rc2, out2, err2 = await _git(
            "worktree", "add", str(worktree_path), base_commit,
            cwd=repo_root,
        )
        if rc2 != 0:
            return {
                "ok": False,
                "path": None,
                "branch": None,
                "base_commit": base_commit,
                "error": f"worktree add failed: {err2.strip() or err.strip()}",
            }

    return {
        "ok": True,
        "path": str(worktree_path),
        "branch": branch,
        "base_commit": base_commit,
        "error": None,
    }


async def remove_worktree(repo_root: Path, worktree_path: Path, force: bool = False) -> bool:
    """Remove a worktree. Returns True on success."""
    cmd = ["worktree", "remove", str(worktree_path)]
    if force:
        cmd.append("--force")
    rc, _, _ = await _git(*cmd, cwd=repo_root)
    return rc == 0


async def list_worktrees(repo_root: Path) -> list[dict[str, str]]:
    """List all worktrees for a repo."""
    rc, out, _ = await _git("worktree", "list", "--porcelain", cwd=repo_root)
    if rc != 0:
        return []
    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in out.splitlines():
        if not line:
            if current:
                worktrees.append(current)
                current = {}
            continue
        if " " in line:
            key, _, value = line.partition(" ")
            current[key] = value
    if current:
        worktrees.append(current)
    return worktrees