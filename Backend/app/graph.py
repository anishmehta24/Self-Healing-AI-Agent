from __future__ import annotations

from typing import Callable

from langgraph.graph import END, START, StateGraph

from Backend.app.llm import LLMClient
from Backend.app.nodes import (
    analyze_root_cause,
    classify_issue,
    detect_issue,
    execute_fix_node,
    finalize_report,
    ingest_logs,
    request_approval,
    suggest_fix,
    validate_fix,
)
from Backend.app.persistence import IncidentStore
from Backend.app.state import IncidentState


class WorkflowEngine:
    def __init__(self, *, llm_client: LLMClient, store: IncidentStore, max_retries: int) -> None:
        self.llm_client = llm_client
        self.store = store
        self.max_retries = max_retries
        self.graph = self._build_graph()

    def _persisting_node(self, func: Callable[[IncidentState], IncidentState]) -> Callable[[IncidentState], IncidentState]:
        def wrapped(state: IncidentState) -> IncidentState:
            updates = func(state)
            merged = dict(state)
            merged.update(updates)
            self.store.save_state(IncidentState(**merged))
            return updates

        return wrapped

    def _build_graph(self):
        workflow = StateGraph(IncidentState)
        workflow.add_node("ingest_logs", self._persisting_node(ingest_logs))
        workflow.add_node("detect_issue", self._persisting_node(detect_issue))
        workflow.add_node("classify_issue", self._persisting_node(classify_issue))
        workflow.add_node(
            "analyze_root_cause",
            self._persisting_node(lambda state: analyze_root_cause(state, self.llm_client)),
        )
        workflow.add_node(
            "suggest_fix",
            self._persisting_node(lambda state: suggest_fix(state, self.llm_client)),
        )
        workflow.add_node("request_approval", self._persisting_node(request_approval))
        workflow.add_node("execute_fix", self._persisting_node(execute_fix_node))
        workflow.add_node("validate_fix", self._persisting_node(validate_fix))
        workflow.add_node("finalize_report", self._persisting_node(finalize_report))

        workflow.add_edge(START, "ingest_logs")
        workflow.add_edge("ingest_logs", "detect_issue")
        workflow.add_conditional_edges(
            "detect_issue",
            lambda state: "classify_issue" if state.get("issue_detected") else "finalize_report",
            {"classify_issue": "classify_issue", "finalize_report": "finalize_report"},
        )
        workflow.add_edge("classify_issue", "analyze_root_cause")
        workflow.add_edge("analyze_root_cause", "suggest_fix")
        workflow.add_edge("suggest_fix", "request_approval")
        workflow.add_conditional_edges(
            "request_approval",
            self._after_approval,
            {
                "execute_fix": "execute_fix",
                "finalize_report": "finalize_report",
            },
        )
        workflow.add_edge("execute_fix", "validate_fix")
        workflow.add_conditional_edges(
            "validate_fix",
            self._after_validation,
            {
                "analyze_root_cause": "analyze_root_cause",
                "finalize_report": "finalize_report",
            },
        )
        workflow.add_edge("finalize_report", END)
        return workflow.compile()

    def _after_approval(self, state: IncidentState) -> str:
        if state.get("approved") is True or state.get("approval_required") is False:
            return "execute_fix"
        return "finalize_report"

    def _after_validation(self, state: IncidentState) -> str:
        if state.get("validation_status") == "needs_retry" and state.get("retry_count", 0) < self.max_retries:
            return "analyze_root_cause"
        return "finalize_report"

    def run(self, initial_state: IncidentState) -> IncidentState:
        initial_state.setdefault("metadata", {})
        initial_state["metadata"]["max_retries"] = self.max_retries
        self.store.save_state(initial_state)
        result = self.graph.invoke(initial_state)
        self.store.save_state(IncidentState(**result))
        return IncidentState(**result)

    def resume(self, incident_id: str, *, approved: bool | None = None) -> IncidentState | None:
        state = self.store.get_state(incident_id)
        if state is None:
            return None
        if approved is not None:
            state["approved"] = approved
        return self.run(state)

    def get_diagram(self) -> str:
        try:
            return self.graph.get_graph().draw_mermaid()
        except Exception:
            return "graph TD\nSTART-->ingest_logs-->detect_issue"
