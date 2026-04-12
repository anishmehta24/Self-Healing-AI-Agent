from app.llm import LLMClient
from app.nodes import classify_issue, detect_issue, ingest_logs, suggest_fix
from app.state import build_initial_state


def test_ingest_and_detect_issue() -> None:
    state = build_initial_state("2026-04-12T00:00:00Z ERROR timeout contacting db")
    state.update(ingest_logs(state))
    state.update(detect_issue(state))
    assert state["issue_detected"] is True
    assert "timeout" in state["parsed_logs"]["signals"]


def test_classify_database_issue() -> None:
    state = build_initial_state("ERROR postgres connection pool exhausted")
    state.update(ingest_logs(state))
    state.update(classify_issue(state))
    assert state["issue_type"] == "database"


def test_suggest_fix_uses_safe_action() -> None:
    client = LLMClient(api_key=None, base_url="https://example.com", model="fake")
    state = build_initial_state("ERROR dns lookup failed")
    state.update(ingest_logs(state))
    state.update(detect_issue(state))
    state.update(classify_issue(state))
    state["root_cause"] = "Network instability"
    state.update(suggest_fix(state, client))
    assert state["suggested_action"] in state["available_actions"]
