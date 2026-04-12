from fastapi import FastAPI
from fastapi.testclient import TestClient

from Backend.app.api import build_router
from Backend.app.graph import WorkflowEngine
from Backend.app.llm import LLMClient
from Backend.app.persistence import IncidentStore
from Backend.app.state import build_initial_state


def build_test_client(tmp_path):
    store = IncidentStore(str(tmp_path / "incidents.db"))
    llm_client = LLMClient(api_key=None, base_url="https://example.com", model="fake")
    engine = WorkflowEngine(llm_client=llm_client, store=store, max_retries=3)
    app = FastAPI()
    app.include_router(build_router(engine))
    return TestClient(app), engine


def test_workflow_retries_then_resolves(workspace_tmp_path) -> None:
    client, _ = build_test_client(workspace_tmp_path)
    response = client.post(
        "/simulate",
        json={"scenario_name": "database_connection_saturation", "approved": True, "approval_required": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["retry_count"] == 1
    assert payload["report"]["validation_status"] == "resolved"


def test_approval_pending_stops_before_execution(workspace_tmp_path) -> None:
    client, _ = build_test_client(workspace_tmp_path)
    response = client.post(
        "/simulate",
        json={"scenario_name": "network_dns_failure", "approval_required": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["execution_status"] == "pending"


def test_resume_approved_incident_executes(workspace_tmp_path) -> None:
    client, engine = build_test_client(workspace_tmp_path)
    initial = build_initial_state(
        "2026-04-12T10:05:01Z ERROR dns lookup failed",
        scenario_name="network_dns_failure",
        approval_required=True,
    )
    paused = engine.run(initial)
    assert paused["approved"] is None

    response = client.post(f"/incidents/{paused['incident_id']}/approve", json={"approved": True})
    assert response.status_code == 200
    assert response.json()["report"]["validation_status"] == "resolved"


def test_incident_persistence_round_trip(workspace_tmp_path) -> None:
    _, engine = build_test_client(workspace_tmp_path)
    state = build_initial_state(
        "ERROR node memory pressure critical",
        scenario_name="infrastructure_resource_exhaustion",
        approved=True,
    )
    result = engine.run(state)
    restored = engine.store.get_state(result["incident_id"])
    assert restored is not None
    assert restored["incident_id"] == result["incident_id"]
