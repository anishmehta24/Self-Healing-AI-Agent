from __future__ import annotations

import json
from collections import Counter
from typing import Any

from app.llm import LLMClient
from app.safety import is_safe_action
from app.simulator import execute_action
from app.state import IncidentState, append_history


KEYWORD_MAP = {
    "database": {"postgres", "db", "connection", "pool", "sql"},
    "network": {"timeout", "dns", "socket", "upstream", "unreachable"},
    "infrastructure": {"cpu", "memory", "oom", "evicted", "node"},
    "application_bug": {"exception", "nullpointerexception", "traceback", "deploy", "5xx"},
}


def _extract_lines(logs: str) -> list[str]:
    return [line.strip() for line in logs.splitlines() if line.strip()]


def ingest_logs(state: IncidentState) -> IncidentState:
    raw_logs = state.get("logs", "")
    parsed_payload: dict[str, Any]
    if raw_logs.strip().startswith("{") or raw_logs.strip().startswith("["):
        try:
            parsed_payload = {"structured": json.loads(raw_logs)}
            lines = [json.dumps(item) for item in parsed_payload["structured"]] if isinstance(parsed_payload["structured"], list) else [raw_logs]
        except json.JSONDecodeError:
            lines = _extract_lines(raw_logs)
            parsed_payload = {"raw_lines": lines}
    else:
        lines = _extract_lines(raw_logs)
        parsed_payload = {"raw_lines": lines}

    severities = Counter()
    signals: set[str] = set()
    for line in lines:
        normalized = line.lower()
        if "error" in normalized:
            severities["ERROR"] += 1
        if "warn" in normalized:
            severities["WARN"] += 1
        if "info" in normalized:
            severities["INFO"] += 1
        for terms in KEYWORD_MAP.values():
            for term in terms:
                if term in normalized:
                    signals.add(term)

    parsed_logs = {
        "lines": lines,
        "severity_counts": dict(severities),
        "signals": sorted(signals),
        "line_count": len(lines),
    }
    return IncidentState(
        parsed_logs=parsed_logs,
        history=append_history(
            state,
            node="ingest_logs",
            decision="parsed",
            summary="Normalized incoming logs into parsed events.",
            details={"line_count": len(lines), "signals": parsed_logs["signals"]},
        ),
    )


def detect_issue(state: IncidentState) -> IncidentState:
    parsed_logs = state.get("parsed_logs", {})
    severities = parsed_logs.get("severity_counts", {})
    signals = parsed_logs.get("signals", [])
    issue_detected = severities.get("ERROR", 0) > 0 or any(
        signal in {"timeout", "exception", "oom", "dns", "pool"} for signal in signals
    )
    decision = "issue_detected" if issue_detected else "no_issue"
    summary = "Anomaly detected in log stream." if issue_detected else "No anomaly detected."
    return IncidentState(
        issue_detected=issue_detected,
        validation_status="pending" if issue_detected else "not_applicable",
        history=append_history(
            state,
            node="detect_issue",
            decision=decision,
            summary=summary,
            details={"severity_counts": severities, "signals": signals},
        ),
    )


def classify_issue(state: IncidentState) -> IncidentState:
    signals = set(state.get("parsed_logs", {}).get("signals", []))
    scores = {
        issue_type: len(signals.intersection(keywords))
        for issue_type, keywords in KEYWORD_MAP.items()
    }
    issue_type = max(scores, key=scores.get) if max(scores.values(), default=0) > 0 else "unknown"
    confidence = 0.85 if issue_type != "unknown" else 0.35
    return IncidentState(
        issue_type=issue_type,
        confidence_score=confidence,
        history=append_history(
            state,
            node="classify_issue",
            decision=issue_type,
            summary=f"Classified incident as {issue_type}.",
            details={"scores": scores},
        ),
    )


def analyze_root_cause(state: IncidentState, llm_client: LLMClient) -> IncidentState:
    diagnosis = llm_client.diagnose(
        {
            "issue_type": state.get("issue_type"),
            "signals": state.get("parsed_logs", {}).get("signals", []),
            "logs": state.get("logs", ""),
            "retry_count": state.get("retry_count", 0),
            "history": state.get("history", []),
        }
    )
    return IncidentState(
        root_cause=diagnosis.root_cause,
        confidence_score=round(diagnosis.confidence_score, 2),
        history=append_history(
            state,
            node="analyze_root_cause",
            decision="diagnosed",
            summary=diagnosis.root_cause,
            details={"confidence_score": diagnosis.confidence_score},
        ),
    )


def suggest_fix(state: IncidentState, llm_client: LLMClient) -> IncidentState:
    fix = llm_client.suggest_fix(
        {
            "issue_type": state.get("issue_type"),
            "root_cause": state.get("root_cause"),
            "available_actions": state.get("available_actions", []),
            "retry_count": state.get("retry_count", 0),
            "history": state.get("history", []),
        }
    )
    action = fix.action if is_safe_action(fix.action) else "no_action"
    approval_required = state.get("approval_required", True)
    suggested_fix = fix.suggested_fix if action != "no_action" else "No safe automatic action available."
    history = append_history(
        state,
        node="suggest_fix",
        decision=action,
        summary=suggested_fix,
        details={"rationale": fix.rationale, "confidence_score": fix.confidence_score},
    )
    if action == "no_action":
        approval_required = True
    return IncidentState(
        suggested_action=action,
        suggested_fix=suggested_fix,
        fix_rationale=fix.rationale,
        confidence_score=round(fix.confidence_score, 2),
        approval_required=approval_required,
        history=history,
    )


def request_approval(state: IncidentState) -> IncidentState:
    approved = state.get("approved")
    approval_required = state.get("approval_required", True)
    if not approval_required:
        decision = "auto_approved"
        approved = True
        execution_status = "approved"
    elif approved is True:
        decision = "approved"
        execution_status = "approved"
    elif state.get("suggested_action") == "no_action":
        decision = "blocked"
        execution_status = "skipped"
    else:
        decision = "awaiting_approval"
        execution_status = "pending"
    return IncidentState(
        approved=approved,
        execution_status=execution_status,
        history=append_history(
            state,
            node="request_approval",
            decision=decision,
            summary="Approval gate evaluated.",
            details={"approval_required": approval_required, "approved": approved},
        ),
    )


def execute_fix_node(state: IncidentState) -> IncidentState:
    action = state.get("suggested_action", "no_action")
    if action == "no_action":
        return IncidentState(
            execution_status="skipped",
            validation_status="failed",
            validation_reason="No safe action available for execution.",
            history=append_history(
                state,
                node="execute_fix",
                decision="skipped",
                summary="Execution skipped because no safe action was available.",
            ),
        )
    result = execute_action(state, action)
    return IncidentState(
        execution_status=result.execution_status,
        post_fix_logs=result.post_fix_logs,
        validation_status=result.validation_status,
        validation_reason=result.validation_reason,
        history=append_history(
            state,
            node="execute_fix",
            decision=result.execution_status,
            summary=f"Executed action {action}.",
            details={"post_fix_logs": result.post_fix_logs},
        ),
    )


def validate_fix(state: IncidentState) -> IncidentState:
    validation_status = state.get("validation_status", "failed")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("metadata", {}).get("max_retries", 3)
    if validation_status == "resolved":
        decision = "resolved"
    elif retry_count + 1 >= max_retries:
        validation_status = "failed"
        decision = "retry_exhausted"
    else:
        validation_status = "needs_retry"
        decision = "needs_retry"
    updates: IncidentState = IncidentState(
        validation_status=validation_status,
        history=append_history(
            state,
            node="validate_fix",
            decision=decision,
            summary=state.get("validation_reason", "Validation evaluated."),
            details={"retry_count": retry_count},
        ),
    )
    if validation_status == "needs_retry":
        updates["retry_count"] = retry_count + 1
    return updates


def finalize_report(state: IncidentState) -> IncidentState:
    report = {
        "incident_id": state.get("incident_id"),
        "scenario_name": state.get("scenario_name"),
        "issue_detected": state.get("issue_detected"),
        "issue_type": state.get("issue_type"),
        "root_cause": state.get("root_cause"),
        "suggested_action": state.get("suggested_action"),
        "suggested_fix": state.get("suggested_fix"),
        "execution_status": state.get("execution_status"),
        "validation_status": state.get("validation_status"),
        "retry_count": state.get("retry_count", 0),
        "confidence_score": state.get("confidence_score"),
        "approval_required": state.get("approval_required"),
        "approved": state.get("approved"),
        "validation_reason": state.get("validation_reason"),
        "history": state.get("history", []),
    }
    return IncidentState(
        final_report=report,
        history=append_history(
            state,
            node="finalize_report",
            decision="completed",
            summary="Compiled final incident report.",
            details={"validation_status": state.get("validation_status")},
        ),
    )
