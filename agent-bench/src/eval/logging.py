from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TraceLogger:
    def __init__(self, trace_dir: Path, run_id: str):
        trace_dir.mkdir(parents=True, exist_ok=True)
        self.path = trace_dir / f"{run_id}.jsonl"
        self._handle = self.path.open("w", encoding="utf-8")

    def write(self, event: str, **payload: Any) -> None:
        record = {"event": event, **payload}
        self._handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> "TraceLogger":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

