from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class AgentConfig:
    log_paths: list[str]
    server_url: str
    agent_id: str
    batch_size: int = 50
    flush_interval_seconds: float = 3.0
    poll_interval_seconds: float = 0.5
    retry_backoff_seconds: float = 2.0
    max_backoff_seconds: float = 30.0
    state_db_path: str = ".agent_state/agent.db"
    start_position: str = "end"
    filters: list[str] = field(default_factory=list)
    parse_json_logs: bool = True


def load_config(config_path: str | Path) -> AgentConfig:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    required = ["log_paths", "server_url", "agent_id"]
    missing = [key for key in required if not raw.get(key)]
    if missing:
        raise ValueError(f"Missing required config values: {', '.join(missing)}")

    filters = raw.get("filters") or {}
    levels = filters.get("levels") if isinstance(filters, dict) else []

    return AgentConfig(
        log_paths=[str(item) for item in raw["log_paths"]],
        server_url=str(raw["server_url"]),
        agent_id=str(raw["agent_id"]),
        batch_size=int(raw.get("batch_size", 50)),
        flush_interval_seconds=float(raw.get("flush_interval_seconds", 3.0)),
        poll_interval_seconds=float(raw.get("poll_interval_seconds", 0.5)),
        retry_backoff_seconds=float(raw.get("retry_backoff_seconds", 2.0)),
        max_backoff_seconds=float(raw.get("max_backoff_seconds", 30.0)),
        state_db_path=str(raw.get("state_db_path", ".agent_state/agent.db")),
        start_position=str(raw.get("start_position", "end")),
        filters=[str(level).upper() for level in levels],
        parse_json_logs=bool(raw.get("parse_json_logs", True)),
    )


def example_config() -> dict[str, Any]:
    return {
        "log_paths": [
            "./logs/server.log",
            "./logs/app.log",
        ],
        "server_url": "http://localhost:8000/logs",
        "agent_id": "agent-dev-001",
        "batch_size": 50,
        "flush_interval_seconds": 3,
        "poll_interval_seconds": 0.5,
        "retry_backoff_seconds": 2,
        "max_backoff_seconds": 30,
        "state_db_path": ".agent_state/agent.db",
        "start_position": "end",
        "filters": {
            "levels": ["ERROR", "WARN"],
        },
        "parse_json_logs": True,
    }
