from __future__ import annotations

import re
from pathlib import Path

from agent.models import ToolEnvelope
from tools.filesystem import read_file

PATH_PATTERN = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+")


def run_bash(sandbox_root: Path, command: str) -> ToolEnvelope:
    candidate_path = _first_sandbox_path(command)
    if not candidate_path:
        return ToolEnvelope(
            source="tool_untrusted",
            content="MOCK_BASH_OK: command accepted; no sandbox file path detected.",
            metadata={"tool": "bash", "command": command, "mock": True},
        )

    envelope = read_file(sandbox_root, candidate_path)
    metadata = {
        **envelope.metadata,
        "tool": "bash",
        "command": command,
        "emulated_capability": "file_read",
        "mock": True,
    }
    return ToolEnvelope(
        source=envelope.source,
        content=envelope.content,
        metadata=metadata,
    )


def _first_sandbox_path(command: str) -> str | None:
    for match in PATH_PATTERN.finditer(command):
        path = match.group(0)
        if path.startswith(("./", "../")):
            path = path[2:]
        return path
    return None
