"""Trace schema for representing a hierarchical run tree."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TraceRun:
    """A single node in a trace tree.

    Each node represents one logical step: a chain (top-level or subagent),
    an LLM call (agent reasoning), or a tool invocation.
    """

    id: str
    parent_id: str | None
    run_type: str          # "chain" | "llm" | "tool"
    name: str              # e.g. "search_notes", "agent_reasoning", "subagent:chart-specialist"
    inputs: dict
    outputs: dict
    start_time: str        # ISO-8601
    end_time: str          # ISO-8601
    tokens: dict = field(default_factory=lambda: {"input": 0, "output": 0})
    status: str = "success"
    children: list[TraceRun] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialise the trace tree to a plain dict (JSON-safe)."""
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "run_type": self.run_type,
            "name": self.name,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "tokens": self.tokens,
            "status": self.status,
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict) -> TraceRun:
        """Reconstruct a TraceRun tree from a plain dict."""
        children = [cls.from_dict(c) for c in data.get("children", [])]
        return cls(
            id=data["id"],
            parent_id=data.get("parent_id"),
            run_type=data["run_type"],
            name=data["name"],
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", {}),
            start_time=data.get("start_time", ""),
            end_time=data.get("end_time", ""),
            tokens=data.get("tokens", {"input": 0, "output": 0}),
            status=data.get("status", "success"),
            children=children,
        )
