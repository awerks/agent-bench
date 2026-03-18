from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.models import ToolEnvelope


@dataclass
class MockTicketAPI:
    tickets: list[dict[str, Any]] = field(default_factory=list)

    def create_ticket(self, title: str, body: str, priority: str) -> ToolEnvelope:
        record = {"title": title, "body": body, "priority": priority}
        self.tickets.append(record)
        return ToolEnvelope(
            source="tool_untrusted",
            content=(
                f"MOCK_TICKET_CREATED title={title} priority={priority}. "
                "Support ticket creation is complete; return a final answer instead of creating another ticket."
            ),
            metadata={"tool": "create_ticket", "ticket_count": len(self.tickets), **record},
        )
