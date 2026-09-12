"""BalatroBot composition for a managed live Watchable session."""

from __future__ import annotations

import asyncio
from contextlib import redirect_stdout
import os
from typing import Any, Protocol, TextIO

from .watchable_lifecycle import BRIDGE_PHASE, CLEANUP_PHASE, LAUNCH_PHASE

class Bridge(Protocol):
    """The synchronous JSON-RPC boundary consumed by Round Tactics."""

    def call(self, method: str, params: object = None) -> dict[str, Any]: ...


class LiveSession(Protocol):
    """Start and stop a live session while exposing its settled bridge."""

    @property
    def log_path(self) -> str | None: ...

    def start(self) -> Bridge: ...

    def stop(self) -> None: ...


class BalatroBotSessionError(RuntimeError):
    """A composition failure classified for the Watchable lifecycle trace."""

    def __init__(self, phase: str, message: str) -> None:
        super().__init__(message)
        self.phase = phase


class BalatroBotLiveSession:
    """Own BalatroBot setup, process lifetime, bridge health, and launcher output."""

    def __init__(self, session_id: str, diagnostics: TextIO) -> None:
        self._session_id = session_id
        self._diagnostics = diagnostics
        self._instance: Any | None = None
        self._started = False

    @property
    def log_path(self) -> str | None:
        if self._instance is None or self._instance.log_path is None:
            return None
        return str(self._instance.log_path)

    def start(self) -> Bridge:
        try:
            self._instance = self._create_instance()
            self._started = True
            self._run(self._instance.start())
        except Exception as error:
            raise BalatroBotSessionError(LAUNCH_PHASE, str(error)) from error

        try:
            return self._create_bridge(self._instance.port)
        except Exception as error:
            raise BalatroBotSessionError(BRIDGE_PHASE, str(error)) from error

    def stop(self) -> None:
        if not self._started or self._instance is None:
            return
        try:
            self._run(self._instance.stop())
        except Exception as error:
            raise BalatroBotSessionError(CLEANUP_PHASE, str(error)) from error
        self._started = False

    def _create_instance(self) -> Any:
        BalatroInstance, _, Config = _load_balatrobot()
        return BalatroInstance(
            config=Config(
                balatro_path=os.environ.get("BALATROBOT_BALATRO_PATH"),
                lovely_path=os.environ.get("BALATROBOT_LOVELY_PATH"),
                love_path=os.environ.get("BALATROBOT_LOVE_PATH"),
                platform=os.environ.get("BALATROBOT_PLATFORM"),
                logs_path=os.environ.get("BALATROBOT_LOGS_PATH", "logs"),
            ),
            session_id=self._session_id,
        )

    @staticmethod
    def _create_bridge(port: int) -> Bridge:
        _, BalatroClient, _ = _load_balatrobot()
        return BalatroClient(port=port)

    def _run(self, awaitable: Any) -> None:
        with redirect_stdout(self._diagnostics):
            asyncio.run(awaitable)


def _load_balatrobot() -> tuple[Any, Any, Any]:
    try:
        from balatrobot import BalatroClient, BalatroInstance, Config
    except ImportError as error:
        raise RuntimeError(
            "BalatroBot must be installed to run a watchable session"
        ) from error
    return BalatroInstance, BalatroClient, Config
