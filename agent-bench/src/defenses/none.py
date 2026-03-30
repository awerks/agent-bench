from __future__ import annotations

from agent.models import PolicyDecision


def allow(reason: str = "Allowed.") -> PolicyDecision:
    return PolicyDecision(True, reason)

