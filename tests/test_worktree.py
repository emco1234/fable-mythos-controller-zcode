"""Tests for worktree.py — git worktree management."""
import asyncio
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from worktree import create_clean_worktree, remove_worktree, list_worktrees


def _git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


class TestWorktree(unittest.TestCase):
    def setUp(self):
        if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
            self.skipTest("git not installed")
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        _git("init", cwd=self.repo)
        _git("config", "user.email", "test@test", cwd=self.repo)
        _git("config", "user.name", "Test", cwd=self.repo)
        (self.repo / "README.md").write_text("hello", encoding="utf-8")
        _git("add", ".", cwd=self.repo)
        _git("commit", "-m", "initial", cwd=self.repo)
        self.head = _git("rev-parse", "HEAD", cwd=self.repo).stdout.strip()

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_and_remove(self):
        async def run():
            wt_path = Path(self.tmp.name) / "wt1"
            r = await create_clean_worktree(self.repo, self.head, wt_path)
            assert r["ok"], f"expected ok but got {r}"
            self.assertTrue(wt_path.exists())
            self.assertIn("reliability-verify-", r["branch"])
            ok = await remove_worktree(self.repo, wt_path)
            self.assertTrue(ok)
            self.assertFalse(wt_path.exists())
        asyncio.run(run())

    def test_invalid_base_commit(self):
        async def run():
            wt_path = Path(self.tmp.name) / "wt_bad"
            r = await create_clean_worktree(self.repo, "nonexistent", wt_path)
            self.assertFalse(r["ok"])
            self.assertIn("not valid", r["error"])
        asyncio.run(run())

    def test_list_worktrees(self):
        async def run():
            wt_path = Path(self.tmp.name) / "wt2"
            await create_clean_worktree(self.repo, self.head, wt_path)
            wts = await list_worktrees(self.repo)
            self.assertGreaterEqual(len(wts), 2)  # main + new
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()