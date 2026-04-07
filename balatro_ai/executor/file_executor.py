from __future__ import annotations

import json
import time
from pathlib import Path

from ..models import GameAction


class ExecutorError(Exception):
    """Raised when the file executor encounters a failure or timeout."""


class FileExecutor:
    """Executor that communicates with the Lua side via action.json / action_error.json."""

    def __init__(self, paths, poll_interval: float = 0.05, timeout: float = 30.0) -> None:
        self._ai_dir: Path = paths.ai_dir
        self._action_path = self._ai_dir / "action.json"
        self._error_path = self._ai_dir / "action_error.json"
        self._poll_interval = poll_interval
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def execute(self, action: GameAction) -> None:
        """Write a single-action queue and block until the game acknowledges."""
        self._write_queue([action])
        self._wait_for_completion()

    def execute_sequence(self, actions: list[GameAction]) -> None:
        """Write a multi-action queue and block until the game acknowledges."""
        self._write_queue(actions)
        self._wait_for_completion()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _write_queue(self, actions: list[GameAction]) -> None:
        payload = {"actions": [a.to_action_dict() for a in actions]}
        data = json.dumps(payload)
        tmp_path = self._action_path.with_suffix(".tmp")
        tmp_path.write_text(data, encoding="utf-8")
        tmp_path.rename(self._action_path)

    def _wait_for_completion(self) -> None:
        deadline = time.monotonic() + self._timeout
        while True:
            if not self._action_path.exists():
                return
            if self._error_path.exists():
                reason = self._error_path.read_text(encoding="utf-8").strip()
                self._error_path.unlink(missing_ok=True)
                raise ExecutorError(reason)
            if time.monotonic() >= deadline:
                raise ExecutorError("timeout")
            time.sleep(self._poll_interval)
