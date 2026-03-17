from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.models import ToolEnvelope


@dataclass
class ControlledWebReader:
    project_root: Path
    web: dict[str, ToolEnvelope] = field(default_factory=dict)
    pdfs: dict[str, ToolEnvelope] = field(default_factory=dict)
    search_outputs: dict[str, ToolEnvelope] = field(default_factory=dict)

    def fetch_url(self, url: str) -> ToolEnvelope:
        envelope = self.web.get(url)
        if envelope:
            return envelope
        return ToolEnvelope(
            source="tool_untrusted",
            content=f"ERROR: no controlled web fixture for URL: {url}",
            metadata={"tool": "fetch_url", "url": url, "error": "not_found"},
        )

    def read_pdf(self, path: str) -> ToolEnvelope:
        envelope = self.pdfs.get(path)
        if envelope:
            return envelope
        fallback = self.project_root / "data" / "malicious_pdfs" / path
        if fallback.suffix == ".pdf":
            fallback = fallback.with_suffix(".txt")
        if fallback.exists() and fallback.is_file():
            return ToolEnvelope(
                source="web_untrusted",
                content=fallback.read_text(encoding="utf-8"),
                metadata={"tool": "read_pdf", "path": path, "fixture": str(fallback)},
            )
        return ToolEnvelope(
            source="tool_untrusted",
            content=f"ERROR: no controlled PDF fixture for path: {path}",
            metadata={"tool": "read_pdf", "path": path, "error": "not_found"},
        )

    def search(self, query: str) -> ToolEnvelope:
        key = normalize_query(query)
        envelope = self.search_outputs.get(key)
        if envelope:
            return envelope
        return ToolEnvelope(
            source="tool_untrusted",
            content=f"ERROR: no controlled search fixture for query: {query}",
            metadata={"tool": "search", "query": query, "error": "not_found"},
        )


def normalize_query(query: str) -> str:
    return " ".join(query.lower().split())


def load_fixture_text(item: dict[str, Any], base_dir: Path, project_root: Path) -> str:
    if "content" in item:
        return str(item["content"])
    file_path = item.get("content_path", item.get("path"))
    if not file_path:
        raise ValueError(f"Fixture item needs `content`, `content_path`, or `path`: {item}")
    candidate = Path(file_path)
    candidates = [candidate] if candidate.is_absolute() else [
        (base_dir / candidate).resolve() if base_dir else (project_root / candidate).resolve(),
        (project_root / candidate).resolve(),
    ]
    for resolved in candidates:
        if resolved.exists():
            return resolved.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Fixture file not found: {candidates[-1]}")
