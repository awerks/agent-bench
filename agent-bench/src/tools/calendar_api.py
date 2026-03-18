from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.models import ToolEnvelope


@dataclass
class MockCalendarAPI:
    events: list[dict[str, Any]] = field(default_factory=list)

    def create_calendar_event(self, title: str, time: str, attendees: list[str]) -> ToolEnvelope:
        record = {"title": title, "time": time, "attendees": attendees}
        self.events.append(record)
        return ToolEnvelope(
            source="tool_untrusted",
            content=f"MOCK_CALENDAR_EVENT_CREATED title={title}",
            metadata={"tool": "create_calendar_event", **record},
        )

