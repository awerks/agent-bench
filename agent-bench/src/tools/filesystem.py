from __future__ import annotations

from pathlib import Path

from agent.models import ToolEnvelope


class SandboxViolation(ValueError):
    pass


def resolve_sandbox_path(sandbox_root: Path, user_path: str) -> Path:
    root = sandbox_root.resolve()
    candidate = (root / user_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise SandboxViolation(f"Path escapes sandbox: {user_path}")
    return candidate


def seed_file(sandbox_root: Path, user_path: str, content: str) -> None:
    target = resolve_sandbox_path(sandbox_root, user_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def read_file(sandbox_root: Path, path: str) -> ToolEnvelope:
    try:
        target = resolve_sandbox_path(sandbox_root, path)
    except SandboxViolation as exc:
        return ToolEnvelope(
            source="tool_untrusted",
            content=f"ERROR: {exc}",
            metadata={"tool": "read_file", "path": path, "error": "sandbox_violation"},
        )
    if not target.exists() or not target.is_file():
        return ToolEnvelope(
            source="tool_untrusted",
            content=f"ERROR: workspace file not found: {path}",
            metadata={"tool": "read_file", "path": path, "error": "not_found"},
        )
    return ToolEnvelope(
        source="workspace_private",
        content=target.read_text(encoding="utf-8"),
        metadata={"tool": "read_file", "path": path},
    )


def write_file(sandbox_root: Path, path: str, content: str) -> ToolEnvelope:
    try:
        target = resolve_sandbox_path(sandbox_root, path)
    except SandboxViolation as exc:
        return ToolEnvelope(
            source="tool_untrusted",
            content=f"ERROR: {exc}",
            metadata={"tool": "write_file", "path": path, "error": "sandbox_violation"},
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return ToolEnvelope(
        source="tool_untrusted",
        content=f"WROTE sandbox file {path}",
        metadata={"tool": "write_file", "path": path, "bytes": len(content.encode("utf-8"))},
    )

