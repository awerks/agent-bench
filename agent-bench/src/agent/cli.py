from __future__ import annotations

import argparse
from pathlib import Path

from agent.config import load_config
from agent.models import DEFENSE_NAMES
from agent.react_agent import ReActAgent
from eval.runner import run_eval


def main() -> None:
    parser = argparse.ArgumentParser(prog="asr-agent", description="Minimal agent security research CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    chat_parser = subparsers.add_parser("chat", help="Start an interactive manual testing session.")
    add_common_args(chat_parser)
    chat_parser.add_argument("--planner", choices=["gemini", "scripted"], default="gemini")

    run_parser = subparsers.add_parser("run", help="Run one input through the agent.")
    add_common_args(run_parser)
    run_parser.add_argument("--input", required=True, help="User task for the agent.")
    run_parser.add_argument("--planner", choices=["gemini", "scripted"], default="gemini")

    eval_parser = subparsers.add_parser("eval", help="Run JSONL benchmark tasks.")
    add_common_args(eval_parser)
    eval_parser.add_argument("--tasks", required=True, help="Path to benign or attack JSONL tasks.")
    eval_parser.add_argument("--planner", choices=["gemini", "scripted"], default="scripted")
    eval_parser.add_argument("--repetitions", type=int, default=1)

    args = parser.parse_args()
    config = load_config(
        args.config,
        permission=args.permission,
        enable=args.enable,
        disable=args.disable,
        confirm_mode=args.confirm_mode,
    )

    if args.command == "chat":
        run_chat(config, args.planner)
        return
    if args.command == "run":
        result = ReActAgent(config, planner_name=args.planner).run(args.input)
        print(result.final_answer)
        print(f"Trace: {result.trace_path}")
        return
    if args.command == "eval":
        tasks_path = Path(args.tasks)
        if not tasks_path.is_absolute():
            tasks_path = config.project_root / tasks_path
        summary = run_eval(config, tasks_path, planner_name=args.planner, repetitions=args.repetitions)
        print(f"Summary: {summary}")
        print(f"Traces: {config.trace_dir}")
        return


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default="configs/baseline.yaml")
    parser.add_argument("--permission", choices=["P0", "P1", "P2", "P3", "P4"], default=None)
    parser.add_argument("--enable", action="append", choices=sorted(DEFENSE_NAMES), default=[])
    parser.add_argument("--disable", action="append", choices=sorted(DEFENSE_NAMES), default=[])
    parser.add_argument("--confirm-mode", choices=["interactive", "auto-allow", "auto-deny"], default=None)


def run_chat(config, planner_name: str) -> None:
    print("Agent security CLI. Type `exit` or `quit` to stop.")
    while True:
        try:
            user_input = input("> ").strip()
        except EOFError:
            print()
            return
        if user_input.lower() in {"exit", "quit"}:
            return
        if not user_input:
            continue
        result = ReActAgent(config, planner_name=planner_name).run(user_input)
        print(result.final_answer)
        print(f"Trace: {result.trace_path}")


if __name__ == "__main__":
    main()
