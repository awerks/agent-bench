from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.models import ToolEnvelope


@dataclass
class MemoryStore:
    path: Path

    def read(self, query: str = "") -> ToolEnvelope:
        entries = self._load()
        needle = query.lower().strip()
        matches = [
            item
            for item in entries
            if not needle or needle in str(item.get("content", "")).lower()
        ]
        if not matches:
            content = "No memory entries matched."
        else:
            content = "\n".join(str(item.get("content", "")) for item in matches)
        return ToolEnvelope(
            source="memory_untrusted",
            content=content,
            metadata={"tool": "memory_read", "query": query, "matches": len(matches)},
        )

    def write(self, content: str, *, source: str = "memory_untrusted", metadata: dict[str, Any] | None = None) -> ToolEnvelope:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "source": source,
            "content": content,
            "metadata": metadata or {"source": "agent_generated"},
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return ToolEnvelope(
            source="tool_untrusted",
            content=f"MEMORY_WRITTEN content={content}",
            metadata={"tool": "memory_write", "content": content},
        )

    def all_text(self) -> str:
        return "\n".join(str(item.get("content", "")) for item in self._load())

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        entries: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entries.append(json.loads(stripped))
            except json.JSONDecodeError:
                entries.append({"source": "memory_untrusted", "content": stripped, "metadata": {"parse_error": True}})
        return entries
