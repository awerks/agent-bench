from __future__ import annotations

from typing import Any

from agent.models import AgentConfig, PERMISSION_ORDER, PolicyDecision, TaskSpec, ToolSpec
from defenses.memory_gate import validate_memory_write
from defenses.output_validator import validate_egress, validate_final_answer
from defenses.tool_allowlist import check_tool_allowlist
from defenses.user_confirmation import confirm_action, needs_confirmation


class ToolRouter:
    def __init__(self, config: AgentConfig, task: TaskSpec, tool_specs: dict[str, ToolSpec]):
        self.config = config
        self.task = task
        self.tool_specs = tool_specs
        self.last_confirmation: PolicyDecision | None = None

    def available_tools(self) -> dict[str, ToolSpec]:
        allowed: dict[str, ToolSpec] = {}
        for name, spec in sorted(self.tool_specs.items()):
            if not self._permission_allows(spec):
                continue
            if self.config.defense_enabled("tool_allowlist"):
                allowlist = self._effective_allowlist()
                if allowlist and name not in allowlist:
                    continue
            allowed[name] = spec
        return allowed

    def evaluate_tool(self, tool_name: str, arguments: dict[str, Any]) -> PolicyDecision:
        self.last_confirmation = None
        spec = self.tool_specs.get(tool_name)
        if spec is None:
            return PolicyDecision(False, f"Unknown tool `{tool_name}`.", blocked_by="schema")

        schema_error = validate_arguments(spec, arguments)
        if schema_error:
            return PolicyDecision(False, schema_error, blocked_by="schema")
        if not self._permission_allows(spec):
            return PolicyDecision(
                False,
                f"`{tool_name}` requires {spec.min_permission}, but run has {self.config.permission_profile}.",
                blocked_by="permission",
            )

        if self.config.defense_enabled("tool_allowlist"):
            allowlist_decision = check_tool_allowlist(tool_name, self._effective_allowlist())
            if allowlist_decision:
                return allowlist_decision
            fixture_decision = check_fixture_arguments(tool_name, arguments, self.task)
            if fixture_decision:
                return fixture_decision

        if self.config.defense_enabled("output_validator"):
            validation_decision = validate_egress(tool_name, arguments, self.task)
            if validation_decision:
                return validation_decision

        if self.config.defense_enabled("memory_gate") and tool_name == "memory_write":
            memory_decision = validate_memory_write(str(arguments.get("content", "")), self.task)
            if memory_decision:
                return memory_decision

        if self.config.defense_enabled("user_confirmation") and needs_confirmation(tool_name):
            confirmation = confirm_action(tool_name, arguments, self.config.confirm_mode)
            self.last_confirmation = confirmation
            return confirmation

        return PolicyDecision(True, "Allowed.")

    def validate_final_answer(self, final_answer: str) -> PolicyDecision:
        if self.config.defense_enabled("output_validator"):
            decision = validate_final_answer(final_answer, self.task)
            if decision:
                return decision
        return PolicyDecision(True, "Allowed final answer.")

    def _effective_allowlist(self) -> list[str]:
        if self.task.allowed_tools:
            return self.task.allowed_tools
        return self.config.allowed_tools

    def _permission_allows(self, spec: ToolSpec) -> bool:
        return PERMISSION_ORDER[self.config.permission_profile] >= PERMISSION_ORDER[spec.min_permission]


def validate_arguments(spec: ToolSpec, arguments: dict[str, Any]) -> str | None:
    if not isinstance(arguments, dict):
        return f"Arguments for `{spec.name}` must be a JSON object."
    required = set(spec.schema.get("required", []))
    missing = sorted(required - set(arguments))
    if missing:
        return f"Missing required arguments for `{spec.name}`: {', '.join(missing)}."
    if spec.schema.get("additionalProperties") is False:
        allowed = set(spec.schema.get("properties", {}))
        extra = sorted(set(arguments) - allowed)
        if extra:
            return f"Unknown arguments for `{spec.name}`: {', '.join(extra)}."
    return None


def check_fixture_arguments(tool_name: str, arguments: dict[str, Any], task: TaskSpec) -> PolicyDecision | None:
    fixture_key_by_tool = {
        "fetch_url": ("web", "url", "url"),
        "read_pdf": ("pdfs", "path", "path"),
        "search": ("search_outputs", "query", "query"),
    }
    fixture_keys = fixture_key_by_tool.get(tool_name)
    if not fixture_keys:
        return None
    fixture_group, argument_key, fixture_key = fixture_keys
    declared_values = {
        str(item.get(fixture_key, ""))
        for item in task.fixtures.get(fixture_group, [])
        if item.get(fixture_key)
    }
    if not declared_values:
        return None
    requested = str(arguments.get(argument_key, ""))
    if requested in declared_values:
        return None
    allowed = ", ".join(sorted(declared_values))
    return PolicyDecision(
        False,
        f"`{tool_name}` argument `{argument_key}` must reference a declared fixture. Requested `{requested}`; allowed: {allowed}.",
        blocked_by="tool_allowlist",
    )
