from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.graph import WorkflowEngine
from app.simulator import get_scenario
from app.state import build_initial_state


class AnalyzeRequest(BaseModel):
    logs: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    approved: bool | None = None
    approval_required: bool = True


class SimulateRequest(BaseModel):
    scenario_name: str
    approved: bool | None = None
    approval_required: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApproveRequest(BaseModel):
    approved: bool = True


def build_router(engine: WorkflowEngine):
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/analyze")
    def analyze(request: AnalyzeRequest) -> dict[str, Any]:
        state = build_initial_state(
            request.logs,
            metadata=request.metadata,
            approved=request.approved,
            approval_required=request.approval_required,
        )
        result = engine.run(state)
        return {"incident_id": result["incident_id"], "state": result, "report": result.get("final_report", {})}

    @router.post("/simulate")
    def simulate(request: SimulateRequest) -> dict[str, Any]:
        try:
            scenario = get_scenario(request.scenario_name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        state = build_initial_state(
            scenario["logs"],
            metadata=request.metadata,
            scenario_name=request.scenario_name,
            approved=request.approved,
            approval_required=request.approval_required,
        )
        result = engine.run(state)
        return {"incident_id": result["incident_id"], "state": result, "report": result.get("final_report", {})}

    @router.get("/incidents/{incident_id}")
    def get_incident(incident_id: str) -> dict[str, Any]:
        state = engine.store.get_state(incident_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        return {"incident_id": incident_id, "state": state, "report": state.get("final_report", {})}

    @router.post("/incidents/{incident_id}/approve")
    def approve_incident(incident_id: str, request: ApproveRequest) -> dict[str, Any]:
        result = engine.resume(incident_id, approved=request.approved)
        if result is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        return {"incident_id": incident_id, "state": result, "report": result.get("final_report", {})}

    @router.get("/workflow/diagram")
    def workflow_diagram() -> dict[str, str]:
        return {"mermaid": engine.get_diagram()}

    return router
