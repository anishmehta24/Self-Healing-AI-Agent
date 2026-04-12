from config import load_config


def test_load_config_reads_levels(workspace_tmp_path) -> None:
    config_path = workspace_tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "log_paths:",
                "  - ./logs/app.log",
                "server_url: http://localhost:8000/logs",
                "agent_id: agent-123",
                "filters:",
                "  levels:",
                "    - error",
                "    - warn",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.agent_id == "agent-123"
    assert config.filters == ["ERROR", "WARN"]
