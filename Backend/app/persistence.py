from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from Backend.app.state import IncidentState, utc_now


class IncidentStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    scenario_name TEXT,
                    state_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def save_state(self, state: IncidentState) -> None:
        now = utc_now()
        status = state.get("validation_status") or state.get("execution_status") or "pending"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO incidents (incident_id, scenario_name, state_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    scenario_name = excluded.scenario_name,
                    state_json = excluded.state_json,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    state["incident_id"],
                    state.get("scenario_name"),
                    json.dumps(state),
                    status,
                    now,
                    now,
                ),
            )
            connection.commit()

    def get_state(self, incident_id: str) -> IncidentState | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
        if row is None:
            return None
        return IncidentState(**json.loads(row["state_json"]))

    def list_incidents(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT incident_id, scenario_name, status, created_at, updated_at FROM incidents ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]
