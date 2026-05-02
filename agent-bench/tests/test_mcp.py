from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.config import load_config
from agent.models import MCPServerConfig
from mcps.client import MCPRegistry


class MCPTests(unittest.TestCase):
    def test_benign_mcp_server_can_be_discovered_and_called(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_config(ROOT / "configs" / "baseline.yaml")
            config.mcp_manifest_path = Path(temp_dir) / "manifest.json"
            config.mcp_servers = [
                MCPServerConfig(
                    name="demo",
                    command=sys.executable,
                    args=["-m", "mcps.benign_server"],
                    allowed_tools=["vendor_status"],
                    permission_level="P4",
                )
            ]
            registry = MCPRegistry(config)
            tools = registry.discover()
            self.assertIn("mcp.demo.vendor_status", tools)
            result = registry.call_tool("mcp.demo.vendor_status", {"query": "vendor status"})
        self.assertIn("follow-up", result.content)

    def test_mcp_descriptor_hash_is_recorded_without_blocking_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "manifest.json"
            config = load_config(ROOT / "configs" / "baseline.yaml")
            config.mcp_manifest_path = manifest
            config.mcp_servers = [
                MCPServerConfig(
                    name="demo",
                    command=sys.executable,
                    args=["-m", "mcps.benign_server"],
                    allowed_tools=["vendor_status"],
                    permission_level="P4",
                )
            ]
            MCPRegistry(config).discover()

            poisoned = load_config(ROOT / "configs" / "baseline.yaml")
            poisoned.mcp_manifest_path = manifest
            poisoned.mcp_servers = [
                MCPServerConfig(
                    name="demo",
                    command=sys.executable,
                    args=["-m", "mcps.poisoned_server"],
                    allowed_tools=["vendor_status"],
                    permission_level="P4",
                )
            ]
            registry = MCPRegistry(poisoned)
            tools = registry.discover()
            result = registry.call_tool("mcp.demo.vendor_status", {"query": "vendor status"})
        self.assertIn("descriptor_hash", tools["mcp.demo.vendor_status"].metadata)
        self.assertIn("Vendor status", result.content)


if __name__ == "__main__":
    unittest.main()
