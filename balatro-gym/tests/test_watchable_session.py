from __future__ import annotations

import io
import json
from types import SimpleNamespace


class FakeBridge:
    def __init__(
        self, *, health_error: Exception | None = None, health_status: str = "ok"
    ) -> None:
        self.calls: list[str] = []
        self.health_error = health_error
        self.health_status = health_status

    def call(self, method: str, params: object = None) -> dict[str, str]:
        self.calls.append(method)
        if self.health_error:
            raise self.health_error
        return {"status": self.health_status}


class FakeLiveSession:
    log_path = "/tmp/balatrobot.log"

    def __init__(
        self,
        bridge: FakeBridge,
        *,
        start_error: Exception | None = None,
        stop_error: Exception | None = None,
    ) -> None:
        self.bridge = bridge
        self.start_error = start_error
        self.stop_error = stop_error
        self.started = False
        self.stopped = False

    def start(self) -> FakeBridge:
        if self.start_error:
            raise self.start_error
        self.started = True
        return self.bridge

    def stop(self) -> None:
        if self.stop_error:
            raise self.stop_error
        self.stopped = True


class FakeEnvironment:
    terminal_state = "ROUND_EVAL"
    reset_error: Exception | None = None
    step_error: Exception | None = None

    def __init__(self, bridge: FakeBridge) -> None:
        self.bridge = bridge
        self.steps = 0

    def reset(self, seed: str) -> object:
        from balatro_gym.environments.live import ActionKind, LegalAction

        if self.reset_error:
            raise self.reset_error
        return SimpleNamespace(
            observation="initial", legal_action_mask=(LegalAction(ActionKind.PLAY, (0,)),)
        )

    def step(self, action: object) -> object:
        if self.step_error:
            raise self.step_error
        self.steps += 1
        return SimpleNamespace(
            state=self.terminal_state,
            observation=SimpleNamespace(hands_left=2),
            legal_action_mask=(),
            reward=1.0 if self.terminal_state == "ROUND_EVAL" else -1.0,
            terminated=True,
            truncated=False,
        )


class FakePolicy:
    def select_action(self, observation: object, legal_action_mask: tuple[object, ...]) -> object:
        return legal_action_mask[0]


def patch_session_collaborators(monkeypatch) -> None:
    import balatro_gym.watchable_session as watchable_session

    monkeypatch.setattr(watchable_session, "RoundTacticsEnvironment", FakeEnvironment)
    monkeypatch.setattr(watchable_session, "DeterministicLegalHeuristic", FakePolicy)
    monkeypatch.setattr(watchable_session.uuid, "uuid4", lambda: "session-123")


def test_runner_emits_a_versioned_lifecycle_and_cleans_up_after_round_eval(
    monkeypatch,
) -> None:
    import balatro_gym.watchable_session as watchable_session

    bridge = FakeBridge()
    live_session = FakeLiveSession(bridge)
    output = io.StringIO()
    patch_session_collaborators(monkeypatch)

    result = watchable_session.run_watchable_session(
        "BAL9SEED", output=output, live_session=live_session
    )

    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [event["event"] for event in events] == [
        "launching",
        "bridge_ready",
        "session_ready",
        "action_applied",
        "settled",
    ]
    assert all(event["version"] == watchable_session.SCHEMA_VERSION for event in events)
    assert all(event["session_id"] == "session-123" for event in events)
    assert all(event["seed"] == "BAL9SEED" for event in events)
    assert events[3]["action"] == {"kind": "PLAY", "indices": [0]}
    assert events[-1]["outcome"] == "ROUND_EVAL"
    assert bridge.calls == ["health"]
    assert live_session.started
    assert live_session.stopped
    assert result.outcome == "ROUND_EVAL"
    assert result.exit_code == 0


def test_runner_treats_game_over_as_a_successful_settlement(monkeypatch) -> None:
    import balatro_gym.watchable_session as watchable_session

    bridge = FakeBridge()
    live_session = FakeLiveSession(bridge)
    FakeEnvironment.terminal_state = "GAME_OVER"
    patch_session_collaborators(monkeypatch)

    try:
        result = watchable_session.run_watchable_session(
            "BAL9SEED", output=io.StringIO(), live_session=live_session
        )
    finally:
        FakeEnvironment.terminal_state = "ROUND_EVAL"

    assert result == watchable_session.WatchableSessionResult(0, "GAME_OVER")
    assert live_session.stopped


def test_runner_reports_lifecycle_failures_with_phase_cause_and_log_path(monkeypatch) -> None:
    import balatro_gym.watchable_session as watchable_session

    cases = [
        ("launch", RuntimeError("could not launch")),
        ("reset", None),
        ("step", None),
        ("cleanup", None),
    ]

    for phase, start_error in cases:
        live_session = FakeLiveSession(
            FakeBridge(),
            start_error=start_error,
            stop_error=RuntimeError("could not stop") if phase == "cleanup" else None,
        )
        FakeEnvironment.reset_error = RuntimeError("reset failed") if phase == "reset" else None
        FakeEnvironment.step_error = RuntimeError("step failed") if phase == "step" else None
        patch_session_collaborators(monkeypatch)
        output = io.StringIO()

        result = watchable_session.run_watchable_session(
            "BAL9SEED", output=output, live_session=live_session
        )
        terminal = json.loads(output.getvalue().splitlines()[-1])

        assert result.exit_code == 1
        assert terminal["event"] == "failed"
        assert terminal["phase"] == phase
        assert terminal["error"]
        assert terminal["log_path"] == "/tmp/balatrobot.log"
        if phase == "reset":
            assert [json.loads(line)["event"] for line in output.getvalue().splitlines()] == [
                "launching",
                "bridge_ready",
                "failed",
            ]

    FakeEnvironment.reset_error = None
    FakeEnvironment.step_error = None


def test_runner_cleans_up_after_inspection_is_interrupted(monkeypatch) -> None:
    import balatro_gym.watchable_session as watchable_session

    bridge = FakeBridge()
    live_session = FakeLiveSession(bridge)
    output = io.StringIO()
    patch_session_collaborators(monkeypatch)
    monkeypatch.setattr(watchable_session, "_wait_for_interruption", lambda: None)

    result = watchable_session.run_watchable_session(
        "BAL9SEED", keep_open=True, output=output, live_session=live_session
    )

    assert result.exit_code == 0
    assert live_session.stopped
    assert [json.loads(line)["event"] for line in output.getvalue().splitlines()][-1] == "settled"


def test_runner_reports_unexpected_terminal_states_as_failures(monkeypatch) -> None:
    import balatro_gym.watchable_session as watchable_session

    bridge = FakeBridge()
    live_session = FakeLiveSession(bridge)
    output = io.StringIO()
    FakeEnvironment.terminal_state = "MENU"
    patch_session_collaborators(monkeypatch)

    try:
        result = watchable_session.run_watchable_session(
            "BAL9SEED", output=output, live_session=live_session
        )
    finally:
        FakeEnvironment.terminal_state = "ROUND_EVAL"

    terminal = json.loads(output.getvalue().splitlines()[-1])
    assert result.phase == "unexpected-state"
    assert terminal["event"] == "failed"
    assert terminal["phase"] == "unexpected-state"
    assert live_session.stopped


def test_runner_requires_an_healthy_bridge_before_reporting_it_ready(monkeypatch) -> None:
    import balatro_gym.watchable_session as watchable_session

    output = io.StringIO()
    live_session = FakeLiveSession(FakeBridge(health_status="starting"))
    patch_session_collaborators(monkeypatch)

    result = watchable_session.run_watchable_session(
        "BAL9SEED", output=output, live_session=live_session
    )

    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert result.phase == "bridge"
    assert [event["event"] for event in events] == ["launching", "failed"]


def test_runner_reports_retained_instance_cleanup_failure_as_its_terminal_event(
    monkeypatch,
) -> None:
    import balatro_gym.watchable_session as watchable_session

    live_session = FakeLiveSession(FakeBridge(), stop_error=RuntimeError("could not stop"))
    output = io.StringIO()
    patch_session_collaborators(monkeypatch)
    monkeypatch.setattr(watchable_session, "_wait_for_interruption", lambda: None)

    result = watchable_session.run_watchable_session(
        "BAL9SEED", keep_open=True, output=output, live_session=live_session
    )

    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert result == watchable_session.WatchableSessionResult(1, None, "cleanup")
    assert [event["event"] for event in events][-1] == "failed"
    assert sum(event["event"] in {"settled", "failed"} for event in events) == 1
