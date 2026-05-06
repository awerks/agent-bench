from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.config import load_config
from agent.models import TaskSpec
from agent.planner import AgentAction, GeminiPlanner, PlannerView


class _FakeModels:
    def __init__(self, text: str | None = None, response=None) -> None:
        self.last_request = None
        self.requests = []
        self.response = response
        self.text = text or (
            '{"kind":"tool","thought":"read it","tool":"read_file",'
            '"arguments_json":"{\\"path\\":\\"notes.txt\\"}","final_answer":""}'
        )

    def generate_content(self, **kwargs):
        self.last_request = kwargs
        self.requests.append(kwargs)
        if self.response is not None:
            return self.response
        return SimpleNamespace(
            text=self.text,
            parsed=None,
            usage_metadata=SimpleNamespace(
                prompt_token_count=10,
                candidates_token_count=5,
                total_token_count=15,
            ),
        )


class _FakeClient:
    def __init__(self, text: str | None = None, response=None) -> None:
        self.models = _FakeModels(text, response)


class _BrokenTextResponse:
    parsed = {
        "kind": "tool",
        "thought": "read it",
        "tool": "read_file",
        "arguments_json": '{"path":"notes.txt"}',
        "final_answer": "",
    }
    usage_metadata = SimpleNamespace(prompt_token_count=10, candidates_token_count=5, total_token_count=15)

    @property
    def text(self):
        raise TypeError("'NoneType' object is not iterable")


class GeminiPlannerTests(unittest.TestCase):
    def test_gemini_planner_uses_structured_json_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_config(ROOT / "configs" / "baseline.yaml")
            config.sandbox_dir = Path(temp_dir) / "sandbox"
            config.memory_path = Path(temp_dir) / "memory.jsonl"
            with patch("google.genai.Client", return_value=_FakeClient()):
                planner = GeminiPlanner(config)
                decision, metadata = planner.decide(
                    PlannerView(
                        task=TaskSpec(task_id="test", variant="manual", user_goal="read notes"),
                        available_tool_text="- read_file",
                        observations=[],
                        policy_blocks=[],
                        step=1,
                        prompt="read notes",
                        instructions="return structured output",
                    )
                )

        self.assertEqual(decision.kind, "tool")
        self.assertEqual(decision.tool, "read_file")
        self.assertEqual(decision.arguments, {"path": "notes.txt"})
        self.assertEqual(metadata["total_tokens"], 15)
        request_config = planner.client.models.last_request["config"]
        self.assertIn("response_json_schema", request_config)
        self.assertNotIn("response_schema", request_config)

    def test_gemini_tool_response_with_final_answer_is_normalized(self) -> None:
        text = (
            '{"kind":"final","thought":"done","tool":"",'
            '"arguments_json":"{\\"path\\":\\"vendor_alpha.pdf\\"}",'
            '"final_answer":"Vendor Alpha is cheaper."}'
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_config(ROOT / "configs" / "baseline.yaml")
            config.sandbox_dir = Path(temp_dir) / "sandbox"
            config.memory_path = Path(temp_dir) / "memory.jsonl"
            with patch("google.genai.Client", return_value=_FakeClient(text)):
                planner = GeminiPlanner(config)
                decision, _metadata = planner.decide(
                    PlannerView(
                        task=TaskSpec(task_id="test", variant="manual", user_goal="compare"),
                        available_tool_text="- read_pdf",
                        observations=[],
                        policy_blocks=[],
                        step=1,
                        prompt="compare",
                        instructions="return structured output",
                    )
                )

        self.assertEqual(decision.kind, "final")
        self.assertIsNone(decision.tool)
        self.assertEqual(decision.arguments, {})
        self.assertEqual(decision.final_answer, "Vendor Alpha is cheaper.")

    def test_gemini_tool_response_with_null_final_answer_stays_tool(self) -> None:
        text = (
            '{"kind":"tool","thought":"read it","tool":"read_file",'
            '"arguments_json":"{\\"path\\":\\"notes.txt\\"}",'
            '"final_answer":"null"}'
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_config(ROOT / "configs" / "baseline.yaml")
            config.sandbox_dir = Path(temp_dir) / "sandbox"
            config.memory_path = Path(temp_dir) / "memory.jsonl"
            with patch("google.genai.Client", return_value=_FakeClient(text)):
                planner = GeminiPlanner(config)
                decision, _metadata = planner.decide(
                    PlannerView(
                        task=TaskSpec(task_id="test", variant="manual", user_goal="read notes"),
                        available_tool_text="- read_file",
                        observations=[],
                        policy_blocks=[],
                        step=1,
                        prompt="read notes",
                        instructions="return structured output",
                    )
                )

        self.assertEqual(decision.kind, "tool")
        self.assertEqual(decision.tool, "read_file")
        self.assertEqual(decision.arguments, {"path": "notes.txt"})
        self.assertEqual(decision.final_answer, "")

    def test_gemini_prefers_parsed_response_before_text_property(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_config(ROOT / "configs" / "baseline.yaml")
            config.sandbox_dir = Path(temp_dir) / "sandbox"
            config.memory_path = Path(temp_dir) / "memory.jsonl"
            with patch("google.genai.Client", return_value=_FakeClient(response=_BrokenTextResponse())):
                planner = GeminiPlanner(config)
                decision, _metadata = planner.decide(
                    PlannerView(
                        task=TaskSpec(task_id="test", variant="manual", user_goal="read notes"),
                        available_tool_text="- read_file",
                        observations=[],
                        policy_blocks=[],
                        step=1,
                        prompt="read notes",
                        instructions="return structured output",
                    )
                )

        self.assertEqual(decision.kind, "tool")
        self.assertEqual(decision.tool, "read_file")
        self.assertEqual(decision.arguments, {"path": "notes.txt"})

    def test_gemini_schema_uses_required_strings_without_nullable_fields(self) -> None:
        schema = AgentAction.model_json_schema()

        self.assertEqual(set(schema["required"]), {"kind", "thought", "tool", "arguments_json", "final_answer"})
        self.assertEqual(schema["properties"]["tool"]["type"], "string")
        self.assertEqual(schema["properties"]["final_answer"]["type"], "string")
        self.assertNotIn("default", str(schema))
        self.assertNotIn("null", str(schema).lower())


if __name__ == "__main__":
    unittest.main()
