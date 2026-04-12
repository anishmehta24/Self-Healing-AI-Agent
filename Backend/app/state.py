from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, TypedDict
from uuid import uuid4


IssueType = Literal["database", "network", "infrastructure", "application_bug", "unknown"]
ExecutionStatus = Literal["pending", "approved", "skipped", "completed", "failed"]
ValidationStatus = Literal["pending", "resolved", "failed", "needs_retry", "not_applicable"]
ActionName = Literal["restart_service", "clear_cache", "retry_request", "scale_worker_pool", "rollback_release", "no_action"]


class HistoryEntry(TypedDict, total=False):
    timestamp: str
    node: str
    decision: str
    summary: str
    details: dict[str, Any]


class IncidentState(TypedDict, total=False):
    incident_id: str
    scenario_name: str | None
    logs: str
    parsed_logs: dict[str, Any]
    issue_detected: bool
    issue_type: IssueType
    root_cause: str
    suggested_fix: str
    suggested_action: ActionName
    execution_status: ExecutionStatus
    validation_status: ValidationStatus
    retry_count: int
    history: list[HistoryEntry]
    approval_required: bool
    approved: bool | None
    confidence_score: float
    available_actions: list[str]
    final_report: dict[str, Any]
    metadata: dict[str, Any]
    post_fix_logs: str
    validation_reason: str
    fix_rationale: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_initial_state(
    logs: str,
    *,
    metadata: dict[str, Any] | None = None,
    scenario_name: str | None = None,
    approved: bool | None = None,
    approval_required: bool = True,
) -> IncidentState:
    return IncidentState(
        incident_id=str(uuid4()),
        scenario_name=scenario_name,
        logs=logs,
        parsed_logs={},
        issue_detected=False,
        issue_type="unknown",
        root_cause="",
        suggested_fix="",
        suggested_action="no_action",
        execution_status="pending",
        validation_status="pending",
        retry_count=0,
        history=[],
        approval_required=approval_required,
        approved=approved,
        confidence_score=0.0,
        available_actions=[
            "restart_service",
            "clear_cache",
            "retry_request",
            "scale_worker_pool",
            "rollback_release",
        ],
        final_report={},
        metadata=metadata or {},
        post_fix_logs="",
        validation_reason="",
        fix_rationale="",
    )


def append_history(
    state: IncidentState,
    *,
    node: str,
    decision: str,
    summary: str,
    details: dict[str, Any] | None = None,
) -> list[HistoryEntry]:
    entries = list(state.get("history", []))
    entries.append(
        HistoryEntry(
            timestamp=utc_now(),
            node=node,
            decision=decision,
            summary=summary,
            details=details or {},
        )
    )
    return entries
