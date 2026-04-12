from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from config import AgentConfig
from storage import StateStore


def build_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_dev}:{stat.st_ino}"


@dataclass(slots=True)
class ReadResult:
    lines: list[str]
    offset: int
    fingerprint: str | None


class LogReader:
    def __init__(self, path: str, config: AgentConfig, store: StateStore) -> None:
        self.path = Path(path)
        self.config = config
        self.store = store
        self._file = None
        self._offset = 0
        self._fingerprint: str | None = None
        self._open_if_available()

    def _open_if_available(self) -> None:
        if not self.path.exists():
            self._close()
            return

        fingerprint = build_fingerprint(self.path)
        checkpoint = self.store.get_checkpoint(str(self.path))
        handle = self.path.open("r", encoding="utf-8", errors="replace")

        if checkpoint is None:
            if self.config.start_position == "end":
                handle.seek(0, os.SEEK_END)
            else:
                handle.seek(0, os.SEEK_SET)
            self._offset = handle.tell()
            self.store.save_checkpoint(str(self.path), fingerprint, self._offset)
        else:
            saved_fingerprint, saved_offset = checkpoint
            if saved_fingerprint == fingerprint:
                handle.seek(saved_offset, os.SEEK_SET)
                self._offset = saved_offset
            else:
                handle.seek(0, os.SEEK_SET)
                self._offset = 0
                self.store.save_checkpoint(str(self.path), fingerprint, self._offset)

        self._file = handle
        self._fingerprint = fingerprint

    def _close(self) -> None:
        if self._file is not None:
            self._file.close()
        self._file = None
        self._fingerprint = None

    def _needs_reopen(self) -> bool:
        if not self.path.exists():
            return self._file is not None
        if self._file is None:
            return True

        current_fingerprint = build_fingerprint(self.path)
        if current_fingerprint != self._fingerprint:
            return True

        current_size = self.path.stat().st_size
        return current_size < self._offset

    def _should_keep_line(self, line: str) -> bool:
        if not self.config.filters:
            return True

        upper = line.upper()
        if any(level in upper for level in self.config.filters):
            return True

        if self.config.parse_json_logs:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                return False
            level = str(payload.get("level", "")).upper()
            return level in self.config.filters

        return False

    def poll(self) -> ReadResult:
        if self._needs_reopen():
            self._open_if_available()

        if self._file is None or self._fingerprint is None:
            return ReadResult(lines=[], offset=self._offset, fingerprint=self._fingerprint)

        lines: list[str] = []
        while True:
            position = self._file.tell()
            line = self._file.readline()
            if not line:
                self._offset = position
                break
            cleaned = line.rstrip("\r\n")
            if cleaned and self._should_keep_line(cleaned):
                lines.append(cleaned)
            self._offset = self._file.tell()

        return ReadResult(lines=lines, offset=self._offset, fingerprint=self._fingerprint)
