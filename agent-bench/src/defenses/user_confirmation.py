from __future__ import annotations

import sys
from typing import Any

from agent.models import PolicyDecision


SENSITIVE_TOOLS = {
    "write_file",
    "send_email",
    "create_calendar_event",
    "create_ticket",
    "memory_write",
}


def needs_confirmation(tool_name: str) -> bool:
    return tool_name in SENSITIVE_TOOLS or tool_name.startswith("mcp.")


def confirm_action(tool_name: str, arguments: dict[str, Any], mode: str) -> PolicyDecision:
    if mode == "auto-allow":
        return PolicyDecision(True, "Simulated user confirmation approved the action.", user_steps=1)
    if mode == "auto-deny":
        return PolicyDecision(
            False,
            "Simulated user confirmation denied the action.",
            blocked_by="user_confirmation",
            user_steps=1,
        )

    if mode != "interactive":
        raise ValueError(f"Unknown confirmation mode: {mode}")
    if not sys.stdin.isatty():
        return PolicyDecision(
            False,
            "Interactive confirmation unavailable on non-interactive stdin.",
            blocked_by="user_confirmation",
            user_steps=1,
        )

    print(f"\nSensitive action requested: {tool_name}({arguments})")
    answer = input("Approve? [y/N] ").strip().lower()
    if answer in {"y", "yes"}:
        return PolicyDecision(True, "User approved the action.", user_steps=1)
    return PolicyDecision(False, "User denied the action.", blocked_by="user_confirmation", user_steps=1)

