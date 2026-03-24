from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.models import AgentConfig, MCPServerConfig, ToolEnvelope, ToolSpec


@dataclass(frozen=True)
class MCPToolDescriptor:
    full_name: str
    server_name: str
    tool_name: str
    description: str
    input_schema: dict[str, Any]
    descriptor_hash: str
    trust_label: str
    min_permission: str

    def as_tool_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.full_name,
            description=f"[MCP:{self.server_name}] {self.description}",
            schema=self.input_schema or {"type": "object", "properties": {}, "required": []},
            min_permission=self.min_permission,
            source="mcp",
            metadata={
                "server": self.server_name,
                "tool_name": self.tool_name,
                "descriptor_hash": self.descriptor_hash,
                "trust_label": self.trust_label,
            },
        )


class MCPRegistry:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.descriptors: dict[str, MCPToolDescriptor] = {}
        self._servers_by_name = {server.name: server for server in config.mcp_servers}

    def discover(self) -> dict[str, ToolSpec]:
        self.descriptors = {}
        manifest = _load_manifest(self.config.mcp_manifest_path)
        changed = False

        for server in self.config.mcp_servers:
            for raw_tool in _list_tools_sync(server, self.config.project_root):
                tool_name = str(raw_tool.get("name"))
                if server.allowed_tools and tool_name not in server.allowed_tools:
                    continue
                input_schema = raw_tool.get("inputSchema") or raw_tool.get("input_schema") or {}
                description = str(raw_tool.get("description", ""))
                descriptor_hash = _descriptor_hash(server.name, tool_name, description, input_schema)
                changed_for_tool = _record_descriptor_hash(manifest, server, tool_name, descriptor_hash)
                changed = changed or changed_for_tool
                full_name = f"mcp.{server.name}.{tool_name}"
                self.descriptors[full_name] = MCPToolDescriptor(
                    full_name=full_name,
                    server_name=server.name,
                    tool_name=tool_name,
                    description=description,
                    input_schema=input_schema,
                    descriptor_hash=descriptor_hash,
                    trust_label=server.trust_label,
                    min_permission=server.permission_level,
                )

        if changed:
            _save_manifest(self.config.mcp_manifest_path, manifest)
        return {name: descriptor.as_tool_spec() for name, descriptor in self.descriptors.items()}

    def call_tool(self, full_name: str, arguments: dict[str, Any]) -> ToolEnvelope:
        descriptor = self.descriptors.get(full_name)
        if descriptor is None:
            return ToolEnvelope(
                source="tool_untrusted",
                content=f"ERROR: MCP tool not discovered: {full_name}",
                metadata={"tool": full_name, "error": "not_discovered"},
            )
        server = self._servers_by_name[descriptor.server_name]
        content = _call_tool_sync(server, descriptor.tool_name, arguments, self.config.project_root)
        return ToolEnvelope(
            source=descriptor.trust_label,
            content=content,
            metadata={
                "tool": full_name,
                "server": descriptor.server_name,
                "tool_name": descriptor.tool_name,
                "descriptor_hash": descriptor.descriptor_hash,
            },
        )


def _descriptor_hash(server_name: str, tool_name: str, description: str, input_schema: dict[str, Any]) -> str:
    payload = {
        "server": server_name,
        "tool": tool_name,
        "description": description,
        "input_schema": input_schema,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _record_descriptor_hash(
    manifest: dict[str, Any],
    server: MCPServerConfig,
    tool_name: str,
    descriptor_hash: str,
) -> bool:
    servers = manifest.setdefault("servers", {})
    tools = servers.setdefault(server.name, {})
    known = tools.get(tool_name)
    if not known:
        tools[tool_name] = descriptor_hash
        return True
    return False


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"servers": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"servers": {}}


def _save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _mcp_env(project_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    src_path = str(project_root / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}{os.pathsep}{existing}"
    return env


def _list_tools_sync(server: MCPServerConfig, project_root: Path) -> list[dict[str, Any]]:
    return asyncio.run(_list_tools(server, project_root))


def _call_tool_sync(server: MCPServerConfig, tool_name: str, arguments: dict[str, Any], project_root: Path) -> str:
    return asyncio.run(_call_tool(server, tool_name, arguments, project_root))


async def _list_tools(server: MCPServerConfig, project_root: Path) -> list[dict[str, Any]]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=server.command, args=server.args, env=_mcp_env(project_root))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            tools = getattr(result, "tools", result)
            return [_tool_to_dict(tool) for tool in tools]


async def _call_tool(server: MCPServerConfig, tool_name: str, arguments: dict[str, Any], project_root: Path) -> str:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=server.command, args=server.args, env=_mcp_env(project_root))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return _content_to_text(getattr(result, "content", result))


def _tool_to_dict(tool: Any) -> dict[str, Any]:
    if hasattr(tool, "model_dump"):
        return tool.model_dump(by_alias=True)
    if isinstance(tool, dict):
        return tool
    return {
        "name": getattr(tool, "name", ""),
        "description": getattr(tool, "description", ""),
        "inputSchema": getattr(tool, "inputSchema", getattr(tool, "input_schema", {})),
    }


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            text = getattr(item, "text", None)
            if text is not None:
                chunks.append(str(text))
            elif isinstance(item, dict) and "text" in item:
                chunks.append(str(item["text"]))
            else:
                chunks.append(str(item))
        return "\n".join(chunks)
    return str(content)
