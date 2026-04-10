from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from agent.config import load_dotenv
from agent.models import AgentConfig, Observation, PlannerDecision, TaskSpec
from pydantic import BaseModel, Field, ValidationError

ACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["kind", "thought", "tool", "arguments_json", "final_answer"],
    "properties": {
        "kind": {"type": "string", "enum": ["tool", "final"]},
        "thought": {"type": "string"},
        "tool": {"type": "string"},
        "arguments_json": {"type": "string"},
        "final_answer": {"type": "string"},
    },
}


class AgentAction(BaseModel):
    kind: Literal["tool", "final"]
    thought: str = Field(description="Brief reason for the selected next action.")
    tool: str = Field(description="Tool name for tool actions. Empty string for final answers.")
    arguments_json: str = Field(description="JSON object string containing tool arguments, or {} for final answers.")
    final_answer: str = Field(description="Final user-facing answer for final actions. Empty string for tool actions.")


@dataclass
class PlannerView:
    task: TaskSpec
    available_tool_text: str
    observations: list[Observation]
    policy_blocks: list[str]
    step: int
    prompt: str
    instructions: str


class Planner:
    name = "base"

    def decide(self, view: PlannerView) -> tuple[PlannerDecision, dict[str, Any]]:
        raise NotImplementedError


class ScriptedPlanner(Planner):
    name = "scripted"

    def __init__(self) -> None:
        self._index_by_task: dict[str, int] = {}

    def decide(self, view: PlannerView) -> tuple[PlannerDecision, dict[str, Any]]:
        index = self._index_by_task.get(view.task.task_id, 0)
        self._index_by_task[view.task.task_id] = index + 1
        if index >= len(view.task.scripted_steps):
            return (
                PlannerDecision(
                    kind="final",
                    thought="Scripted plan exhausted.",
                    final_answer="Scripted planner reached the end of its plan.",
                ),
                {"scripted_step": index},
            )
        step = view.task.scripted_steps[index]
        if "final" in step:
            return (
                PlannerDecision(
                    kind="final",
                    thought=str(step.get("thought", "Return final answer.")),
                    final_answer=str(step["final"]),
                    raw=step,
                ),
                {"scripted_step": index},
            )
        if "final_template" in step:
            final_answer = render_template(str(step["final_template"]), view)
            if "{observed_secret}" in str(step["final_template"]) and not observed_secret(view):
                final_answer = str(step.get("fallback_final", "The task could not be completed safely."))
            return (
                PlannerDecision(
                    kind="final",
                    thought=str(step.get("thought", "Return templated final answer.")),
                    final_answer=final_answer,
                    raw=step,
                ),
                {"scripted_step": index},
            )
        return (
            PlannerDecision(
                kind="tool",
                thought=str(step.get("thought", f"Call {step['tool']}.")),
                tool=str(step["tool"]),
                arguments=render_value(step.get("arguments", {}), view),
                raw=step,
            ),
            {"scripted_step": index},
        )


class GeminiPlanner(Planner):
    name = "gemini"

    def __init__(self, config: AgentConfig):
        load_dotenv(config.project_root / ".env")
        load_dotenv(config.project_root.parent / ".env")
        self.config = config
        if not config.model:
            raise RuntimeError("GEMINI_MODEL is required for Gemini planner runs.")
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("Install `google-genai` or run with --planner scripted.") from exc
        self.client = genai.Client()

    def decide(self, view: PlannerView) -> tuple[PlannerDecision, dict[str, Any]]:
        config: dict[str, Any] = {
            "system_instruction": view.instructions,
            "max_output_tokens": self.config.max_output_tokens,
            "response_mime_type": "application/json",
            "response_json_schema": AgentAction.model_json_schema(),
        }
        if self.config.temperature is not None:
            config["temperature"] = self.config.temperature
        response = self.client.models.generate_content(
            model=self.config.model,
            contents=view.prompt,
            config=config,
        )
        try:
            data = _response_data(response)
            arguments = json.loads(data.get("arguments_json") or "{}")
        except (json.JSONDecodeError, ValidationError) as exc:
            text = _extract_response_text(response)
            raise RuntimeError(f"Gemini planner returned invalid structured JSON: {text}") from exc
        usage = getattr(response, "usage_metadata", None)
        metadata = {
            "model": self.config.model,
            "input_tokens": getattr(usage, "prompt_token_count", 0) if usage else 0,
            "output_tokens": getattr(usage, "candidates_token_count", 0) if usage else 0,
            "total_tokens": getattr(usage, "total_token_count", 0) if usage else 0,
        }
        kind = str(data["kind"])
        tool = _normalize_tool(data.get("tool"))
        final_answer = _normalize_final_answer(data.get("final_answer"))
        arguments = dict(arguments)
        if final_answer.strip():
            kind = "final"
            tool = None
            arguments = {}
        return (
            PlannerDecision(
                kind=kind,
                thought=str(data.get("thought", "")),
                tool=tool,
                arguments=arguments,
                final_answer=final_answer,
                raw=data,
            ),
            metadata,
        )


def make_planner(name: str, config: AgentConfig) -> Planner:
    if name == "scripted":
        return ScriptedPlanner()
    if name == "gemini":
        return GeminiPlanner(config)
    raise ValueError(f"Unknown planner: {name}")


def _response_data(response: Any) -> dict[str, Any]:
    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        if hasattr(parsed, "model_dump"):
            return AgentAction.model_validate(parsed.model_dump()).model_dump()
        if isinstance(parsed, dict):
            return AgentAction.model_validate(parsed).model_dump()
    text = _extract_response_text(response)
    return AgentAction.model_validate_json(text).model_dump()


def _normalize_final_answer(value: Any) -> str:
    if value is None:
        return ""
    final_answer = str(value).strip()
    if final_answer.lower() in {"", "null", "none"}:
        return ""
    return final_answer


def _normalize_tool(value: Any) -> str | None:
    if value is None:
        return None
    tool = str(value).strip()
    if tool.lower() in {"", "null", "none"}:
        return None
    return tool


def render_value(value: Any, view: PlannerView) -> Any:
    if isinstance(value, str):
        return render_template(value, view)
    if isinstance(value, list):
        return [render_value(item, view) for item in value]
    if isinstance(value, dict):
        return {key: render_value(item, view) for key, item in value.items()}
    return value


def render_template(template: str, view: PlannerView) -> str:
    return template.replace("{observed_secret}", observed_secret(view))


def observed_secret(view: PlannerView) -> str:
    secret = view.task.planted_secret
    if not secret:
        return ""
    text = "\n".join(observation.envelope.content for observation in view.observations)
    text += "\n".join(view.policy_blocks)
    if secret in text:
        return secret
    return ""


def _extract_response_text(response: Any) -> str:
    chunks: list[str] = []
    try:
        text = getattr(response, "text", None)
    except Exception:
        text = None
    if text:
        return str(text)
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            text = getattr(part, "text", None)
            if text:
                chunks.append(str(text))
    output = getattr(response, "output", None) or []
    for item in output:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                chunks.append(str(text))
    return "\n".join(chunks)
