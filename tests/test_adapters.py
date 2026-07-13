"""Tests for zcode_adapter."""
import asyncio
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestZCodeAdapterStub(unittest.TestCase):
    def setUp(self):
        os.environ["RELIABILITY_ZCODE_BIN"] = "/nonexistent/zcode-binary-xyz"

    def test_stub_when_no_binary(self):
        from adapters.zcode_adapter import ZCodeAdapter
        adapter = ZCodeAdapter()
        async def run():
            return await adapter.spawn("reliability-scout", "test prompt")
        path = asyncio.run(run())
        text = Path(path).read_text(encoding="utf-8")
        self.assertIn("STUB", text)
        self.assertTrue(
            "zcode CLI not found" in text or "zcode binary not found" in text,
            f"expected zcode-not-found reason, got: {text[:200]!r}",
        )

    def test_spawn_writes_prompt_to_transcript(self):
        from adapters.zcode_adapter import ZCodeAdapter
        adapter = ZCodeAdapter()
        async def run():
            return await adapter.spawn("reliability-lead", "do the thing")
        path = asyncio.run(run())
        text = Path(path).read_text(encoding="utf-8")
        self.assertIn("do the thing", text)


if __name__ == "__main__":
    unittest.main()