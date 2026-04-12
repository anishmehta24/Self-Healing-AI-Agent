from __future__ import annotations

from typing import Final


SAFE_ACTIONS: Final[set[str]] = {
    "restart_service",
    "clear_cache",
    "retry_request",
    "scale_worker_pool",
    "rollback_release",
}


def is_safe_action(action: str) -> bool:
    return action in SAFE_ACTIONS
