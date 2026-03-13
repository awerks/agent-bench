from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PERMISSION_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}

DEFENSE_NAMES = {
    "tool_allowlist",
    "user_confirmation",
    "content_labeling",
    "output_validator",
    "memory_gate",
}

TRUSTED_SOURCES = {"trusted_user", "workspace_private", "agent_generated"}
UNTRUSTED_SOURCES = {"web_untrusted", "tool_untrusted", "memory_untrusted", "mcp_untrusted"}


@dataclass(frozen=True)
class ToolEnvelope:
    source: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "content": self.content,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class PlannerDecision:
    kind: str
    thought: str = ""
    tool: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    final_answer: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "thought": self.thought,
            "tool": self.tool,
            "arguments": self.arguments,
            "final_answer": self.final_answer,
            "raw": self.raw,
        }


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    blocked_by: str | None = None
    user_steps: int = 0
    quarantine: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "blocked_by": self.blocked_by,
            "user_steps": self.user_steps,
            "quarantine": self.quarantine,
        }


@dataclass(frozen=True)
class Observation:
    step: int
    tool: str
    envelope: ToolEnvelope

    def as_prompt_text(self, include_labels: bool) -> str:
        if include_labels:
            return (
                f"Observation {self.step} from `{self.tool}` "
                f"[source={self.envelope.source}]:\n{self.envelope.content}"
            )
        return f"Observation {self.step} from `{self.tool}`:\n{self.envelope.content}"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    variant: str
    user_goal: str
    permission_profile: str = "P4"
    defense_profile: str = "baseline"
    allowed_tools: list[str] = field(default_factory=list)
    fixtures: dict[str, Any] = field(default_factory=dict)
    planted_secret: str = ""
    attack_goal: str | None = None
    scoring: dict[str, Any] = field(default_factory=dict)
    scripted_steps: list[dict[str, Any]] = field(default_factory=list)
    task_path: str = ""
    experiment: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], task_path: str = "") -> "TaskSpec":
        return cls(
            task_id=str(data.get("task_id", "manual")),
            variant=str(data.get("variant", "manual")),
            user_goal=str(data["user_goal"]),
            permission_profile=str(data.get("permission_profile", data.get("permission", "P4"))),
            defense_profile=str(data.get("defense_profile", data.get("defense", "baseline"))),
            allowed_tools=list(data.get("allowed_tools", [])),
            fixtures=dict(data.get("fixtures", {})),
            planted_secret=str(data.get("planted_secret", "")),
            attack_goal=data.get("attack_goal"),
            scoring=dict(data.get("scoring", {})),
            scripted_steps=list(data.get("scripted_steps", [])),
            task_path=task_path,
            experiment=str(data.get("experiment", "")),
        )


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    trust_label: str = "mcp_untrusted"
    allowed_tools: list[str] = field(default_factory=list)
    permission_level: str = "P4"


@dataclass
class AgentConfig:
    name: str
    project_root: Path
    model: str
    max_output_tokens: int
    temperature: float | None
    max_steps: int
    permission_profile: str
    defenses: dict[str, bool]
    allowed_tools: list[str]
    confirm_mode: str
    sandbox_dir: Path
    trace_dir: Path
    memory_path: Path
    mcp_manifest_path: Path
    mcp_servers: list[MCPServerConfig] = field(default_factory=list)
    fixtures: dict[str, Any] = field(default_factory=dict)

    def defense_enabled(self, name: str) -> bool:
        return bool(self.defenses.get(name, False))


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    schema: dict[str, Any]
    min_permission: str
    source: str = "local"
    metadata: dict[str, Any] = field(default_factory=dict)

    def prompt_line(self) -> str:
        required = self.schema.get("required", [])
        return f"- {self.name}: {self.description} Required args: {required}"


@dataclass
class RunResult:
    run_id: str
    task: TaskSpec
    final_answer: str
    termination_reason: str
    trace_path: Path
    score: dict[str, Any]
    token_usage: dict[str, int]
