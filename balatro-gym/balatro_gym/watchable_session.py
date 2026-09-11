"""Run one visible, seeded Round Tactics session through BalatroBot."""

from __future__ import annotations

import asyncio
from contextlib import redirect_stdout
import json
import os
import signal
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any, Protocol, TextIO

from balatro_gym.environments.live import LegalAction, RoundTacticsEnvironment
from balatro_gym.episode_runner import (
    EpisodeExecutionError,
    RoundTacticsEpisodeRunner,
    settlement_state,
)
from balatro_gym.policies import DeterministicLegalHeuristic


SCHEMA_VERSION = "watchable-session/v1"


class ManagedInstance(Protocol):
    """The BalatroBot process lifecycle owned by a watchable session."""

    port: int
    log_path: Path | None

    async def start(self) -> None: ...

    async def stop(self) -> None: ...


class Bridge(Protocol):
    """The synchronous BalatroBot JSON-RPC boundary used by Round Tactics."""

    def call(self, method: str, params: object = None) -> dict[str, Any]: ...


@dataclass(frozen=True)
class WatchableSessionResult:
    """The terminal result reported by a watchable session."""

    exit_code: int
    outcome: str | None
    phase: str | None = None


def run_watchable_session(
    seed: str,
    *,
    keep_open: bool = False,
    output: TextIO | None = None,
    diagnostics: TextIO | None = None,
) -> WatchableSessionResult:
    """Run one seeded Red Deck / White Stake first Small Blind visibly.

    JSON Lines are written exclusively to ``output`` (standard output by default);
    human-readable lifecycle diagnostics go to ``diagnostics`` (standard error by
    default). The runner creates and owns both the BalatroBot instance and bridge.
    """
    output = output or sys.stdout
    diagnostics = diagnostics or sys.stderr
    session_id = str(uuid.uuid4())
    emit = _EventEmitter(output, session_id, seed)
    emit("launching")

    instance: ManagedInstance | None = None
    started = False
    phase = "launch"
    try:
        instance = _create_instance(session_id)
        _run_lifecycle(instance.start(), diagnostics)
        started = True

        phase = "bridge"
        bridge = _create_bridge(instance.port)
        health = bridge.call("health")
        if health.get("status") != "ok":
            raise RuntimeError(f"BalatroBot health did not report ok: {health!r}")
        emit("bridge_ready")

        phase = "reset"
        environment = RoundTacticsEnvironment(bridge)

        policy = DeterministicLegalHeuristic()
        phase = "step"
        try:
            episode = RoundTacticsEpisodeRunner(
                environment,
                action_observer=lambda action: emit(
                    "action_applied", action=_action_payload(action)
                ),
                ready_observer=lambda: emit("session_ready"),
            )(policy, seed)
        except EpisodeExecutionError as error:
            phase = error.phase
            if error.unexpected:
                raise _UnexpectedState(str(error)) from error
            raise
        outcome = settlement_state(episode)

        if keep_open:
            print("Session settled; keeping Balatro open until interrupted.", file=diagnostics)
            _wait_for_interruption()
            phase = "cleanup"
            _run_lifecycle(instance.stop(), diagnostics)
            started = False
            emit("settled", outcome=outcome)
        else:
            phase = "cleanup"
            _run_lifecycle(instance.stop(), diagnostics)
            started = False
            emit("settled", outcome=outcome)
        return WatchableSessionResult(exit_code=0, outcome=outcome)
    except (Exception, KeyboardInterrupt) as error:
        if isinstance(error, KeyboardInterrupt):
            error = RuntimeError("session interrupted")
        if started and instance is not None:
            try:
                _run_lifecycle(instance.stop(), diagnostics)
                started = False
            except Exception as cleanup_error:
                if phase == "cleanup":
                    error = cleanup_error
                else:
                    print(f"Cleanup after {phase} failure also failed: {cleanup_error}", file=diagnostics)
        failure_phase = "unexpected-state" if isinstance(error, _UnexpectedState) else phase
        emit("failed", phase=failure_phase, error=str(error), log_path=_log_path(instance))
        print(f"Watchable session failed during {failure_phase}: {error}", file=diagnostics)
        return WatchableSessionResult(exit_code=1, outcome=None, phase=failure_phase)
    finally:
        if keep_open and started and instance is not None:
            try:
                _run_lifecycle(instance.stop(), diagnostics)
            except Exception as cleanup_error:
                print(f"Cleanup after inspection failed: {cleanup_error}", file=diagnostics)


class _EventEmitter:
    def __init__(self, output: TextIO, session_id: str, seed: str) -> None:
        self._output = output
        self._common = {
            "version": SCHEMA_VERSION,
            "session_id": session_id,
            "seed": seed,
        }

    def __call__(self, event: str, **fields: object) -> None:
        json.dump(self._common | {"event": event} | fields, self._output, sort_keys=True)
        self._output.write("\n")
        self._output.flush()


class _UnexpectedState(RuntimeError):
    pass


def _create_instance(session_id: str) -> ManagedInstance:
    BalatroInstance, _, Config = _load_balatrobot()
    return BalatroInstance(
        config=Config(
            balatro_path=os.environ.get("BALATROBOT_BALATRO_PATH"),
            lovely_path=os.environ.get("BALATROBOT_LOVELY_PATH"),
            love_path=os.environ.get("BALATROBOT_LOVE_PATH"),
            platform=os.environ.get("BALATROBOT_PLATFORM"),
            logs_path=os.environ.get("BALATROBOT_LOGS_PATH", "logs"),
        ),
        session_id=session_id,
    )


def _create_bridge(port: int) -> Bridge:
    _, BalatroClient, _ = _load_balatrobot()
    return BalatroClient(port=port)


def _load_balatrobot() -> tuple[Any, Any, Any]:
    try:
        from balatrobot import BalatroClient, BalatroInstance, Config
    except ImportError as error:
        raise RuntimeError(
            "BalatroBot must be installed to run a watchable session"
        ) from error
    return BalatroInstance, BalatroClient, Config


def _run_lifecycle(awaitable: Any, diagnostics: TextIO) -> None:
    """Keep BalatroBot's launcher messages out of the JSONL stream."""
    with redirect_stdout(diagnostics):
        asyncio.run(awaitable)


def _wait_for_interruption() -> None:
    interrupted = Event()

    def mark_interrupted(signum: int, frame: object) -> None:
        del signum, frame
        interrupted.set()

    previous = {
        signal.SIGINT: signal.signal(signal.SIGINT, mark_interrupted),
        signal.SIGTERM: signal.signal(signal.SIGTERM, mark_interrupted),
    }
    try:
        interrupted.wait()
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _action_payload(action: LegalAction) -> dict[str, object]:
    return {"kind": action.kind.value, "indices": list(action.indices)}


def _log_path(instance: ManagedInstance | None) -> str | None:
    if instance is None or instance.log_path is None:
        return None
    return str(instance.log_path)
