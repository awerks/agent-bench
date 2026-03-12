from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import yaml

from agent.models import AgentConfig, DEFENSE_NAMES, MCPServerConfig, PERMISSION_ORDER

CONFIG_NAMES = {
    "baseline",
    "allowlist_confirm",
    "labeling_validation",
    "memory_enabled",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def load_config(
    config_path: str | Path | None,
    *,
    permission: str | None = None,
    enable: list[str] | None = None,
    disable: list[str] | None = None,
    confirm_mode: str | None = None,
) -> AgentConfig:
    root = project_root()
    load_dotenv(root / ".env")
    load_dotenv(root.parent / ".env")

    raw: dict[str, Any] = {}
    if config_path:
        path = Path(config_path)
        if not path.is_absolute():
            path = root / path
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    defenses = {name: False for name in DEFENSE_NAMES}
    defenses.update({str(k): bool(v) for k, v in (raw.get("defenses") or {}).items()})

    for name in enable or []:
        _validate_defense(name)
        defenses[name] = True
    for name in disable or []:
        _validate_defense(name)
        defenses[name] = False

    resolved_permission = permission or raw.get("permission_profile", "P4")
    if resolved_permission not in PERMISSION_ORDER:
        raise ValueError(f"Unknown permission profile: {resolved_permission}")

    resolved_confirm_mode = confirm_mode or raw.get("confirm_mode", "auto-deny")
    if resolved_confirm_mode not in {"interactive", "auto-allow", "auto-deny"}:
        raise ValueError(f"Unknown confirm mode: {resolved_confirm_mode}")

    mcp_servers = [_parse_mcp_server(item, root) for item in (raw.get("mcp", {}) or {}).get("servers", [])]

    return AgentConfig(
        name=str(raw.get("name", "manual")),
        project_root=root,
        model=str(
            os.environ.get("GEMINI_MODEL") or os.environ.get("GOOGLE_MODEL") or raw.get("model", "gemini-2.5-pro")
        ),
        max_output_tokens=int(raw.get("max_output_tokens") or os.environ.get("GEMINI_MAX_OUTPUT_TOKENS", "800")),
        temperature=_temperature(raw.get("temperature", os.environ.get("GEMINI_TEMPERATURE", "0"))),
        max_steps=int(raw.get("max_steps", 8)),
        permission_profile=resolved_permission,
        defenses=defenses,
        allowed_tools=list(raw.get("allowed_tools", [])),
        confirm_mode=resolved_confirm_mode,
        sandbox_dir=_resolve_path(root, raw.get("sandbox_dir", "data/sandbox")),
        trace_dir=_resolve_path(root, raw.get("trace_dir", "results/traces")),
        memory_path=_resolve_path(root, raw.get("memory_path", "data/memory_poisoning/memory.jsonl")),
        mcp_manifest_path=_resolve_path(root, raw.get("mcp_manifest_path", "data/tool_outputs/mcp_manifest.json")),
        mcp_servers=mcp_servers,
        fixtures=dict(raw.get("fixtures", {})),
    )


def _parse_mcp_server(raw: dict[str, Any], root: Path) -> MCPServerConfig:
    command = str(raw["command"]).format(python=sys.executable, root=str(root))
    args = [str(arg).format(python=sys.executable, root=str(root)) for arg in raw.get("args", [])]
    return MCPServerConfig(
        name=str(raw["name"]),
        command=command,
        args=args,
        trust_label=str(raw.get("trust_label", "mcp_untrusted")),
        allowed_tools=list(raw.get("allowed_tools", [])),
        permission_level=str(raw.get("permission_level", "P4")),
    )


def _resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path


def _temperature(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _validate_defense(name: str) -> None:
    if name not in DEFENSE_NAMES:
        available = ", ".join(sorted(DEFENSE_NAMES))
        raise ValueError(f"Unknown defense `{name}`. Available: {available}")
