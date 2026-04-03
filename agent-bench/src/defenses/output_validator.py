from __future__ import annotations

import json
from typing import Any

from agent.models import PolicyDecision, TaskSpec


EGRESS_TOOLS = {
    "write_file",
    "send_email",
    "create_calendar_event",
    "create_ticket",
    "memory_write",
}


def validate_egress(tool_name: str, arguments: dict[str, Any], task: TaskSpec) -> PolicyDecision | None:
    if tool_name not in EGRESS_TOOLS and not tool_name.startswith("mcp."):
        return None
    if contains_secret(arguments, task.planted_secret):
        return PolicyDecision(
            False,
            "Blocked planted-secret egress in tool arguments.",
            blocked_by="output_validator",
        )
    if is_unauthorized_action(task, tool_name, arguments):
        return PolicyDecision(
            False,
            "Blocked unauthorized sensitive action.",
            blocked_by="output_validator",
        )
    return None


def validate_final_answer(final_answer: str, task: TaskSpec) -> PolicyDecision | None:
    if contains_secret(final_answer, task.planted_secret):
        return PolicyDecision(
            False,
            "Blocked planted-secret egress in final answer.",
            blocked_by="output_validator",
        )
    return None


def contains_secret(value: Any, secret: str) -> bool:
    if not secret:
        return False
    return secret in searchable_text(_stringify(value))


def is_unauthorized_action(task: TaskSpec, tool_name: str | None, arguments: dict[str, Any]) -> bool:
    if not tool_name:
        return False
    scoring = task.scoring
    if tool_name in scoring.get("unauthorized_tools", []):
        return True
    if tool_name.startswith("mcp.") and tool_name in scoring.get("unauthorized_tools", []):
        return True
    if tool_name == "send_email":
        recipient = str(arguments.get("to", "")).lower()
        blocked = {str(item).lower() for item in scoring.get("unauthorized_recipients", [])}
        if recipient in blocked:
            return True
        authorized = {str(item).lower() for item in scoring.get("authorized_recipients", [])}
        if authorized and recipient not in authorized:
            return True
    return False


def searchable_text(text: str) -> str:
    decoded = decode_hidden_tags(text)
    if decoded:
        return f"{text}\n{decoded}"
    return text


def decode_hidden_tags(text: str) -> str:
    tag_min = 0xE0000
    tag_max = 0xE007F
    chars: list[str] = []
    for char in text:
        code = ord(char)
        if tag_min <= code <= tag_max:
            chars.append(chr(code - tag_min))
    return "".join(chars)


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True)
    except TypeError:
        return str(value)

