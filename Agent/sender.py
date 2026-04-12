from __future__ import annotations

import threading
import time

import httpx

from config import AgentConfig
from storage import StateStore


class LogSender:
    def __init__(self, config: AgentConfig, store: StateStore) -> None:
        self.config = config
        self.store = store
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread = threading.Thread(target=self._run, name="log-sender", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        self._thread.join(timeout=10)

    def notify_new_logs(self) -> None:
        self._wake_event.set()

    def _run(self) -> None:
        backoff = self.config.retry_backoff_seconds
        with httpx.Client(timeout=10.0) as client:
            while not self._stop_event.is_set():
                if self.store.pending_count() == 0:
                    self._wake_event.wait(timeout=self.config.flush_interval_seconds)
                    self._wake_event.clear()
                    continue

                batch = self.store.fetch_pending_batch(self.config.batch_size)
                if not batch:
                    continue

                ids = [item[0] for item in batch]
                logs = [item[1] for item in batch]
                payload = {
                    "agent_id": self.config.agent_id,
                    "logs": logs,
                }

                try:
                    response = client.post(self.config.server_url, json=payload)
                    response.raise_for_status()
                    self.store.delete_pending_batch(ids)
                    backoff = self.config.retry_backoff_seconds
                    continue
                except httpx.HTTPError:
                    self._wake_event.wait(timeout=backoff)
                    self._wake_event.clear()
                    backoff = min(backoff * 2, self.config.max_backoff_seconds)
                    continue

        # Graceful drain is best-effort; the persisted queue survives restart.
        time.sleep(0.01)
