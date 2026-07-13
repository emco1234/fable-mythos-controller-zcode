"""
Custom Reliability Tools.

These are the tools exposed to the lead/verifier agents instead of
"trust the LLM". Each tool returns a machine-checkable result.

Available tools:
  - verify(contract, patch) -> dict   : runs 9-point check on a patch
  - gate(contract, report) -> Status   : evaluates the machine gate
  - record_evidence(task_id, payload)   : append to ledger
  - budget_status(task_id) -> dict     : token/latency consumption
  - mark_done(task_id, status)         : emit terminal status
"""
from __future__ import annotations

from typing import Any, Callable, Awaitable


# ----- Tool registry -----
class ToolRegistry:
    """Maps tool names to async callables. The lead/verifier agents invoke them."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Awaitable[Any]]] = {}

    def register(self, name: str, fn: Callable[..., Awaitable[Any]]) -> None:
        self._tools[name] = fn

    def names(self) -> list[str]:
        return sorted(self._tools)

    async def call(self, name: str, **kwargs: Any) -> Any:
        if name not in self._tools:
            raise KeyError(f"Unknown reliability tool: {name!r}. Known: {self.names()}")
        return await self._tools[name](**kwargs)


def default_registry(controller: Any) -> ToolRegistry:
    """Build the default registry wired to a controller instance."""
    from memory import TaskMemory

    reg = ToolRegistry()

    async def verify(contract: Any, patch: dict[str, Any]) -> dict[str, Any]:
        """Run the 9-point check on a patch. Returns dict[check_name, result]."""
        return await controller.run_nine_point_check_for_patch(contract, patch)

    async def gate(contract: Any, report: Any) -> str:
        """Evaluate the deterministic machine gate. Returns Status enum value."""
        return controller.evaluate_gate(contract, report).value

    async def record_evidence(task_id: str, kind: str, payload: dict[str, Any]) -> Any:
        mem: TaskMemory = controller.memory
        return mem.append_ledger(task_id, kind, payload)

    async def budget_status(task_id: str) -> dict[str, Any]:
        mem: TaskMemory = controller.memory
        return mem.load_budget(task_id) or {}

    async def mark_done(task_id: str, status: str, payload: dict[str, Any] | None = None) -> None:
        mem: TaskMemory = controller.memory
        mem.save_report(task_id, status, payload or {})

    reg.register("verify", verify)
    reg.register("gate", gate)
    reg.register("record_evidence", record_evidence)
    reg.register("budget_status", budget_status)
    reg.register("mark_done", mark_done)
    return reg