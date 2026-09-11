"""Run one visible, seeded Round Tactics session through BalatroBot."""

from __future__ import annotations

import json
import signal
import sys
import uuid
from dataclasses import dataclass
from threading import Event
from typing import TextIO

from balatro_gym.balatrobot_session import (
    BalatroBotLiveSession,
    BalatroBotSessionError,
    LiveSession,
)
from balatro_gym.environments.live import LegalAction, RoundTacticsEnvironment
from balatro_gym.episode_runner import (
    EpisodeExecutionError,
    RoundTacticsEpisodeRunner,
    settlement_state,
)
from balatro_gym.policies import DeterministicLegalHeuristic
from balatro_gym.watchable_lifecycle import (
    BRIDGE_PHASE,
    CLEANUP_PHASE,
    LAUNCH_PHASE,
    RESET_PHASE,
    STEP_PHASE,
    UNEXPECTED_STATE_PHASE,
)


SCHEMA_VERSION = "watchable-session/v1"


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
    live_session: LiveSession | None = None,
) -> WatchableSessionResult:
    """Run one seeded Red Deck / White Stake first Small Blind visibly.

    JSON Lines are written exclusively to ``output`` (standard output by default);
    human-readable lifecycle diagnostics go to ``diagnostics`` (standard error by
    default). The runner owns visible lifecycle records and delegates BalatroBot
    composition to its live-session adapter.
    """
    output = output or sys.stdout
    diagnostics = diagnostics or sys.stderr
    session_id = str(uuid.uuid4())
    emit = _EventEmitter(output, session_id, seed)
    emit("launching")

    live_session = live_session or BalatroBotLiveSession(session_id, diagnostics)
    started = False
    phase = LAUNCH_PHASE
    try:
        # A bridge failure can follow a successfully launched process, so always
        # give the adapter a chance to release resources after a start attempt.
        started = True
        bridge = live_session.start()
        phase = BRIDGE_PHASE
        health = bridge.call("health")
        if health.get("status") != "ok":
            raise RuntimeError(f"BalatroBot health did not report ok: {health!r}")
        emit("bridge_ready")

        phase = RESET_PHASE
        environment = RoundTacticsEnvironment(bridge)

        policy = DeterministicLegalHeuristic()
        phase = STEP_PHASE
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
            phase = CLEANUP_PHASE
            live_session.stop()
            started = False
            emit("settled", outcome=outcome)
        else:
            phase = CLEANUP_PHASE
            live_session.stop()
            started = False
            emit("settled", outcome=outcome)
        return WatchableSessionResult(exit_code=0, outcome=outcome)
    except (Exception, KeyboardInterrupt) as error:
        if isinstance(error, KeyboardInterrupt):
            error = RuntimeError("session interrupted")
        if isinstance(error, BalatroBotSessionError):
            phase = error.phase
        if started:
            try:
                live_session.stop()
                started = False
            except Exception as cleanup_error:
                if phase == CLEANUP_PHASE:
                    error = cleanup_error
                else:
                    print(f"Cleanup after {phase} failure also failed: {cleanup_error}", file=diagnostics)
        failure_phase = UNEXPECTED_STATE_PHASE if isinstance(error, _UnexpectedState) else phase
        emit("failed", phase=failure_phase, error=str(error), log_path=live_session.log_path)
        print(f"Watchable session failed during {failure_phase}: {error}", file=diagnostics)
        return WatchableSessionResult(exit_code=1, outcome=None, phase=failure_phase)
    finally:
        if keep_open and started:
            try:
                live_session.stop()
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
