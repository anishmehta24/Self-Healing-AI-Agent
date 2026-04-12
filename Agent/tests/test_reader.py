from config import AgentConfig
from reader import LogReader
from storage import StateStore


def build_config(database_path: str) -> AgentConfig:
    return AgentConfig(
        log_paths=[],
        server_url="http://localhost:8000/logs",
        agent_id="agent-test",
        state_db_path=database_path,
        start_position="beginning",
    )


def test_reader_tails_new_lines(workspace_tmp_path) -> None:
    log_path = workspace_tmp_path / "app.log"
    log_path.write_text("INFO boot\nERROR failed\n", encoding="utf-8")

    store = StateStore(str(workspace_tmp_path / "agent.db"))
    config = build_config(str(workspace_tmp_path / "agent.db"))
    reader = LogReader(str(log_path), config, store)

    first = reader.poll()
    assert first.lines == ["INFO boot", "ERROR failed"]

    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("WARN retrying\n")

    second = reader.poll()
    assert second.lines == ["WARN retrying"]


def test_reader_reopens_after_rotation(workspace_tmp_path) -> None:
    log_path = workspace_tmp_path / "app.log"
    log_path.write_text("ERROR one\n", encoding="utf-8")

    store = StateStore(str(workspace_tmp_path / "agent.db"))
    config = build_config(str(workspace_tmp_path / "agent.db"))
    reader = LogReader(str(log_path), config, store)
    assert reader.poll().lines == ["ERROR one"]

    rotated = workspace_tmp_path / "app.log.1"
    reader._close()
    log_path.replace(rotated)
    log_path.write_text("ERROR two\n", encoding="utf-8")

    rotated_read = reader.poll()
    assert rotated_read.lines == ["ERROR two"]
