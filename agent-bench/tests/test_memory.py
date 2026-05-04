from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.memory import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def test_write_observation_includes_written_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory = MemoryStore(Path(temp_dir) / "memory.jsonl")
            observation = memory.write("Project Cedar deadline is Monday.")

        self.assertIn("MEMORY_WRITTEN", observation.content)
        self.assertIn("Project Cedar deadline is Monday.", observation.content)


if __name__ == "__main__":
    unittest.main()
