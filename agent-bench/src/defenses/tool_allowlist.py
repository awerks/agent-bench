from __future__ import annotations

from agent.models import PolicyDecision


def check_tool_allowlist(tool_name: str, allowed_tools: list[str]) -> PolicyDecision | None:
    if not allowed_tools:
        return None
    if tool_name in allowed_tools:
        return None
    return PolicyDecision(
        allowed=False,
        reason=f"`{tool_name}` is not in the task/config allowlist.",
        blocked_by="tool_allowlist",
    )

