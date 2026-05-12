from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.memory import MemoryStore
from agent.models import AgentConfig, TaskSpec, ToolEnvelope, ToolSpec
from mcps.client import MCPRegistry
from tools.calendar_api import MockCalendarAPI
from tools.email_api import MockEmailAPI
from tools.filesystem import seed_file, read_file as fs_read_file, write_file as fs_write_file
from tools.shell import run_bash
from tools.ticket_api import MockTicketAPI
from tools.web_reader import ControlledWebReader, load_fixture_text, normalize_query


LOCAL_TOOL_SPECS: dict[str, ToolSpec] = {
    "read_file": ToolSpec(
        name="read_file",
        description="Read a file from the per-run sandbox.",
        schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        min_permission="P2",
    ),
    "write_file": ToolSpec(
        name="write_file",
        description="Write a file into the per-run sandbox.",
        schema={
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        min_permission="P3",
    ),
    "fetch_url": ToolSpec(
        name="fetch_url",
        description="Fetch a controlled local web fixture by URL.",
        schema={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
            "additionalProperties": False,
        },
        min_permission="P1",
    ),
    "read_pdf": ToolSpec(
        name="read_pdf",
        description="Read text from a controlled PDF-like fixture.",
        schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        min_permission="P1",
    ),
    "search": ToolSpec(
        name="search",
        description="Return a controlled search/tool-output fixture.",
        schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        min_permission="P1",
    ),
    "bash": ToolSpec(
        name="bash",
        description="Run a controlled mock shell command inside the per-run sandbox.",
        schema={
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
            "additionalProperties": False,
        },
        min_permission="P4",
    ),
    "send_email": ToolSpec(
        name="send_email",
        description="Record a mock email send; never sends real email.",
        schema={
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
            "additionalProperties": False,
        },
        min_permission="P4",
    ),
    "create_calendar_event": ToolSpec(
        name="create_calendar_event",
        description="Record a mock calendar event.",
        schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "time": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "time", "attendees"],
            "additionalProperties": False,
        },
        min_permission="P4",
    ),
    "create_ticket": ToolSpec(
        name="create_ticket",
        description="Record a mock ticket creation.",
        schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": "string"},
                "priority": {"type": "string"},
            },
            "required": ["title", "body", "priority"],
            "additionalProperties": False,
        },
        min_permission="P4",
    ),
    "memory_read": ToolSpec(
        name="memory_read",
        description="Read synthetic persistent memory.",
        schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        min_permission="P2",
    ),
    "memory_write": ToolSpec(
        name="memory_write",
        description="Write synthetic persistent memory.",
        schema={
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
            "additionalProperties": False,
        },
        min_permission="P3",
    ),
}


@dataclass
class RuntimeState:
    task: TaskSpec
    config: AgentConfig
    run_id: str
    sandbox_root: Path
    web_reader: ControlledWebReader
    memory: MemoryStore
    email_api: MockEmailAPI = field(default_factory=MockEmailAPI)
    calendar_api: MockCalendarAPI = field(default_factory=MockCalendarAPI)
    ticket_api: MockTicketAPI = field(default_factory=MockTicketAPI)
    workspace_writes: dict[str, str] = field(default_factory=dict)
    workspace_sources: dict[str, str] = field(default_factory=dict)
    quarantined_memory: list[ToolEnvelope] = field(default_factory=list)
    mcp_registry: MCPRegistry | None = None

    @property
    def mock_api(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "emails_sent": self.email_api.sent,
            "calendar_events": self.calendar_api.events,
            "tickets_created": self.ticket_api.tickets,
        }


class Executor:
    def __init__(self, config: AgentConfig, task: TaskSpec, run_id: str):
        self.config = config
        self.task = task
        self.run_id = run_id
        self.state = self._prepare_state()

    def tool_specs(self) -> dict[str, ToolSpec]:
        specs = dict(LOCAL_TOOL_SPECS)
        if self.state.mcp_registry:
            specs.update(self.state.mcp_registry.discover())
        return specs

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolEnvelope:
        if tool_name.startswith("mcp."):
            if not self.state.mcp_registry:
                return ToolEnvelope(
                    source="tool_untrusted",
                    content="ERROR: MCP is not configured.",
                    metadata={"tool": tool_name, "error": "mcp_not_configured"},
                )
            return self.state.mcp_registry.call_tool(tool_name, arguments)

        if tool_name == "read_file":
            path = str(arguments["path"])
            envelope = fs_read_file(self.state.sandbox_root, path)
            source = self.state.workspace_sources.get(path)
            if source and "error" not in envelope.metadata:
                return ToolEnvelope(
                    source=source,
                    content=envelope.content,
                    metadata=envelope.metadata,
                )
            return envelope
        if tool_name == "write_file":
            path = str(arguments["path"])
            content = str(arguments["content"])
            envelope = fs_write_file(self.state.sandbox_root, path, content)
            if "error" not in envelope.metadata:
                self.state.workspace_writes[path] = content
            return envelope
        if tool_name == "fetch_url":
            return self.state.web_reader.fetch_url(str(arguments["url"]))
        if tool_name == "read_pdf":
            return self.state.web_reader.read_pdf(str(arguments["path"]))
        if tool_name == "search":
            return self.state.web_reader.search(str(arguments["query"]))
        if tool_name == "bash":
            return run_bash(self.state.sandbox_root, str(arguments["command"]))
        if tool_name == "send_email":
            return self.state.email_api.send_email(
                str(arguments["to"]),
                str(arguments["subject"]),
                str(arguments["body"]),
            )
        if tool_name == "create_calendar_event":
            attendees = arguments["attendees"]
            if not isinstance(attendees, list):
                attendees = [str(attendees)]
            return self.state.calendar_api.create_calendar_event(
                str(arguments["title"]),
                str(arguments["time"]),
                [str(item) for item in attendees],
            )
        if tool_name == "create_ticket":
            return self.state.ticket_api.create_ticket(
                str(arguments["title"]),
                str(arguments["body"]),
                str(arguments["priority"]),
            )
        if tool_name == "memory_read":
            return self.state.memory.read(str(arguments["query"]))
        if tool_name == "memory_write":
            return self.state.memory.write(str(arguments["content"]))
        return ToolEnvelope(
            source="tool_untrusted",
            content=f"ERROR: unknown tool: {tool_name}",
            metadata={"tool": tool_name, "error": "unknown_tool"},
        )

    def _prepare_state(self) -> RuntimeState:
        sandbox_root = self.config.sandbox_dir / self.run_id
        sandbox_root.mkdir(parents=True, exist_ok=True)
        web_reader = ControlledWebReader(project_root=self.config.project_root)
        memory_path = self.config.memory_path
        if self.task.variant != "manual":
            memory_path = self.config.memory_path.parent / f"{self.run_id}.memory.jsonl"
        memory = MemoryStore(memory_path)

        state = RuntimeState(
            task=self.task,
            config=self.config,
            run_id=self.run_id,
            sandbox_root=sandbox_root,
            web_reader=web_reader,
            memory=memory,
        )
        self._load_fixtures(state)
        if self.config.mcp_servers:
            state.mcp_registry = MCPRegistry(self.config)
        return state

    def _load_fixtures(self, state: RuntimeState) -> None:
        fixtures = dict(self.config.fixtures)
        fixtures.update(self.task.fixtures)
        base_dir = Path(self.task.task_path).parent if self.task.task_path else self.config.project_root

        for item in fixtures.get("workspace_files", []):
            content = load_fixture_text(item, base_dir, self.config.project_root)
            path = str(item["path"])
            seed_file(state.sandbox_root, path, content)
            state.workspace_sources[path] = str(item.get("source", "workspace_private"))

        for item in fixtures.get("web", []):
            url = str(item["url"])
            state.web_reader.web[url] = ToolEnvelope(
                source=str(item.get("source", "web_untrusted")),
                content=load_fixture_text(item, base_dir, self.config.project_root),
                metadata={"fixture_id": item.get("id", url), "url": url},
            )

        for item in fixtures.get("pdfs", []):
            path = str(item["path"])
            state.web_reader.pdfs[path] = ToolEnvelope(
                source=str(item.get("source", "web_untrusted")),
                content=load_fixture_text(item, base_dir, self.config.project_root),
                metadata={"fixture_id": item.get("id", path), "path": path},
            )

        for item in fixtures.get("search_outputs", []):
            query = normalize_query(str(item["query"]))
            state.web_reader.search_outputs[query] = ToolEnvelope(
                source=str(item.get("source", "tool_untrusted")),
                content=load_fixture_text(item, base_dir, self.config.project_root),
                metadata={"fixture_id": item.get("id", query), "query": item["query"]},
            )

        for item in fixtures.get("memory", []):
            content = load_fixture_text(item, base_dir, self.config.project_root)
            state.memory.write(
                content,
                source=str(item.get("source", "memory_untrusted")),
                metadata={"fixture_id": item.get("id", "memory_fixture")},
            )

        mock_api = fixtures.get("mock_api", {})
        state.email_api.sent.extend(mock_api.get("emails_sent", []))
        state.calendar_api.events.extend(mock_api.get("calendar_events", []))
        state.ticket_api.tickets.extend(mock_api.get("tickets_created", []))
