from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class StateStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    path TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL,
                    offset INTEGER NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    log_line TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()

    def get_checkpoint(self, path: str) -> tuple[str, int] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT fingerprint, offset FROM checkpoints WHERE path = ?",
                (path,),
            ).fetchone()
        if row is None:
            return None
        return str(row["fingerprint"]), int(row["offset"])

    def save_checkpoint(self, path: str, fingerprint: str, offset: int) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO checkpoints (path, fingerprint, offset, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(path) DO UPDATE SET
                    fingerprint = excluded.fingerprint,
                    offset = excluded.offset,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (path, fingerprint, offset),
            )
            connection.commit()

    def append_logs_and_checkpoint(
        self,
        *,
        path: str,
        fingerprint: str,
        offset: int,
        log_lines: list[str],
    ) -> None:
        if not log_lines:
            self.save_checkpoint(path, fingerprint, offset)
            return

        with self._lock, self._connect() as connection:
            connection.executemany(
                "INSERT INTO pending_logs (path, log_line) VALUES (?, ?)",
                [(path, line) for line in log_lines],
            )
            connection.execute(
                """
                INSERT INTO checkpoints (path, fingerprint, offset, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(path) DO UPDATE SET
                    fingerprint = excluded.fingerprint,
                    offset = excluded.offset,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (path, fingerprint, offset),
            )
            connection.commit()

    def fetch_pending_batch(self, limit: int) -> list[tuple[int, str]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT id, log_line FROM pending_logs ORDER BY id ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [(int(row["id"]), str(row["log_line"])) for row in rows]

    def delete_pending_batch(self, ids: list[int]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self._lock, self._connect() as connection:
            connection.execute(f"DELETE FROM pending_logs WHERE id IN ({placeholders})", ids)
            connection.commit()

    def pending_count(self) -> int:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM pending_logs").fetchone()
        return int(row["count"])
