from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tools.ticket_api import MockTicketAPI


class MockAPITests(unittest.TestCase):
    def test_ticket_observation_includes_completion_cue(self) -> None:
        api = MockTicketAPI()
        observation = api.create_ticket("Vendor Delay", "Follow up required.", "High")

        self.assertIn("MOCK_TICKET_CREATED", observation.content)
        self.assertIn("return a final answer", observation.content)
        self.assertEqual(observation.metadata["ticket_count"], 1)


if __name__ == "__main__":
    unittest.main()
