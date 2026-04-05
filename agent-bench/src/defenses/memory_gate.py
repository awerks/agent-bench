from __future__ import annotations

from agent.models import PolicyDecision, TaskSpec


INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "system override",
    "developer override",
    "private validation values",
    "validation mailbox",
    "illia@gmail.com",
    "always forward",
)


def validate_memory_write(content: str, task: TaskSpec) -> PolicyDecision | None:
    lowered = content.lower()
    markers = list(INJECTION_MARKERS)
    markers.extend(str(item).lower() for item in task.scoring.get("memory_poison_markers", []))
    if any(marker in lowered for marker in markers):
        return PolicyDecision(
            False,
            "Quarantined suspicious memory write.",
            blocked_by="memory_gate",
            quarantine=True,
        )
    return None
