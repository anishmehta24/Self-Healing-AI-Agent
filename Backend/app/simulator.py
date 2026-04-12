from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class SimulationResult:
    execution_status: str
    post_fix_logs: str
    validation_status: str
    validation_reason: str


SCENARIOS: dict[str, dict[str, Any]] = {
    "database_connection_saturation": {
        "logs": "\n".join(
            [
                "2026-04-12T10:00:00Z ERROR db pool exhausted",
                "2026-04-12T10:00:01Z ERROR timeout while waiting for postgres connection",
                "2026-04-12T10:00:02Z WARN queue depth exceeded threshold",
            ]
        ),
        "execution_outcomes": {
            "restart_service": {"resolved": False, "post_fix_logs": "ERROR db pool exhausted persists after restart"},
            "scale_worker_pool": {"resolved": True, "post_fix_logs": "INFO queue drained and postgres latency stabilized"},
        },
    },
    "network_dns_failure": {
        "logs": "\n".join(
            [
                "2026-04-12T10:05:00Z ERROR upstream timeout contacting payments-api",
                "2026-04-12T10:05:01Z ERROR dns lookup failed for payments-api.internal",
                "2026-04-12T10:05:02Z WARN retry budget exhausted",
            ]
        ),
        "execution_outcomes": {
            "retry_request": {"resolved": True, "post_fix_logs": "INFO upstream request succeeded after retry"},
            "restart_service": {"resolved": False, "post_fix_logs": "ERROR dns lookup still failing after restart"},
        },
    },
    "infrastructure_resource_exhaustion": {
        "logs": "\n".join(
            [
                "2026-04-12T10:10:00Z ERROR node memory pressure critical",
                "2026-04-12T10:10:01Z ERROR container evicted due to OOM",
                "2026-04-12T10:10:02Z WARN cpu throttling above threshold",
            ]
        ),
        "execution_outcomes": {
            "scale_worker_pool": {"resolved": True, "post_fix_logs": "INFO capacity restored and error rate back to baseline"},
            "restart_service": {"resolved": False, "post_fix_logs": "ERROR pod restarted but resource pressure remains"},
        },
    },
    "application_bad_deploy": {
        "logs": "\n".join(
            [
                "2026-04-12T10:15:00Z ERROR NullPointerException in checkout handler",
                "2026-04-12T10:15:01Z ERROR deployment version 2026.04.12 introduced failing route",
                "2026-04-12T10:15:02Z WARN 5xx error rate spike on /checkout",
            ]
        ),
        "execution_outcomes": {
            "rollback_release": {"resolved": True, "post_fix_logs": "INFO rollback complete and exception rate normalized"},
            "restart_service": {"resolved": False, "post_fix_logs": "ERROR exception persists after restart"},
        },
    },
}


def get_scenario(name: str) -> dict[str, Any]:
    try:
        return SCENARIOS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown scenario '{name}'") from exc


def execute_action(state: dict[str, Any], action: str) -> SimulationResult:
    scenario_name = state.get("scenario_name")
    scenario = SCENARIOS.get(scenario_name or "")
    if scenario is None:
        if action == "no_action":
            return SimulationResult("skipped", state.get("logs", ""), "failed", "No action available to execute.")
        resolved = action in {"retry_request", "restart_service"}
        return SimulationResult(
            execution_status="completed" if resolved else "failed",
            post_fix_logs="INFO generic recovery succeeded" if resolved else "ERROR generic recovery did not resolve the issue",
            validation_status="resolved" if resolved else "needs_retry",
            validation_reason="Generic simulation path used for ad hoc analysis.",
        )
    outcome = scenario["execution_outcomes"].get(action)
    if outcome is None:
        return SimulationResult(
            execution_status="failed",
            post_fix_logs=state.get("logs", ""),
            validation_status="needs_retry",
            validation_reason=f"Scenario does not support action '{action}'.",
        )
    resolved = bool(outcome["resolved"])
    return SimulationResult(
        execution_status="completed" if resolved else "failed",
        post_fix_logs=outcome["post_fix_logs"],
        validation_status="resolved" if resolved else "needs_retry",
        validation_reason="Action resolved the incident." if resolved else "Action executed but the incident persists.",
    )
