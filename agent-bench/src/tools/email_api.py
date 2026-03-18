from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.models import ToolEnvelope


@dataclass
class MockEmailAPI:
    sent: list[dict[str, Any]] = field(default_factory=list)

    def send_email(self, to: str, subject: str, body: str) -> ToolEnvelope:
        record = {"to": to, "subject": subject, "body": body}
        self.sent.append(record)
        return ToolEnvelope(
            source="tool_untrusted",
            content=f"MOCK_EMAIL_SENT to={to} subject={subject}",
            metadata={"tool": "send_email", **record},
        )

