from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from agent.models import AgentConfig, TaskSpec
from agent.react_agent import ReActAgent
from eval.metrics import aggregate


SUMMARY_FIELDS = [
    "run_id",
    "task_id",
    "variant",
    "experiment",
    "defense_profile",
    "permission_profile",
    "planner",
    "trace_file",
    "label",
    "run_error",
    "planner_error",
    "provider_error",
    "max_steps",
    "attack_success",
    "benign_success",
    "blocked_attack",
    "false_positive",
    "false_negative",
    "policy_blocks",
    "user_steps",
    "steps_to_compromise",
    "latency_seconds",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "final_answer",
]


def load_tasks(path: Path) -> list[TaskSpec]:
    tasks: list[TaskSpec] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        data = json.loads(stripped)
        task = TaskSpec.from_dict(data, str(path))
        if not task.task_id:
            raise ValueError(f"Task on line {line_number} has no task_id.")
        tasks.append(task)
    return tasks


def run_eval(config: AgentConfig, tasks_path: Path, *, planner_name: str, repetitions: int = 1) -> Path:
    tasks = load_tasks(tasks_path)
    rows: list[dict[str, Any]] = []
    for task in tasks:
        for repetition in range(repetitions):
            task_for_run = TaskSpec.from_dict(
                {
                    **task.__dict__,
                    "task_id": f"{task.task_id}_rep{repetition}" if repetitions > 1 else task.task_id,
                },
                task.task_path,
            )
            result = ReActAgent(config, planner_name=planner_name).run(task=task_for_run)
            rows.append(
                {
                    "run_id": result.run_id,
                    "task_id": task.task_id,
                    "variant": task.variant,
                    "experiment": task.experiment,
                    "defense_profile": config.name,
                    "permission_profile": config.permission_profile,
                    "planner": planner_name,
                    "trace_file": str(result.trace_path),
                    "final_answer": result.final_answer,
                    **result.score,
                }
            )

    summary_path = config.project_root / "results" / "summary_tables.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(summary_path, rows, SUMMARY_FIELDS)
    _write_csv(config.project_root / "results" / "aggregate.csv", aggregate(rows), None)
    return summary_path


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None) -> None:
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
