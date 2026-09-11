from __future__ import annotations

import io

import pytest


class FakeConfig:
    def __init__(self, **values: object) -> None:
        self.values = values


class FakeInstance:
    created: list["FakeInstance"] = []

    start_error: Exception | None = None

    def __init__(self, *, config: FakeConfig, session_id: str) -> None:
        self.config = config
        self.session_id = session_id
        self.port = 12346
        self.log_path = "/tmp/balatrobot.log"
        self.started = False
        self.stopped = False
        self.created.append(self)

    async def start(self) -> None:
        print("launcher started")
        self.started = True
        if self.start_error is not None:
            raise self.start_error

    async def stop(self) -> None:
        print("launcher stopped")
        self.stopped = True


class FakeClient:
    def __init__(self, *, port: int) -> None:
        self.port = port
        self.calls: list[str] = []

    def call(self, method: str, params: object = None) -> dict[str, str]:
        self.calls.append(method)
        return {"status": "ok"}


def test_balatrobot_live_session_owns_composition_and_routes_launcher_output(
    monkeypatch,
) -> None:
    import balatro_gym.balatrobot_session as balatrobot_session

    FakeInstance.created.clear()
    monkeypatch.setattr(
        balatrobot_session,
        "_load_balatrobot",
        lambda: (FakeInstance, FakeClient, FakeConfig),
    )
    diagnostics = io.StringIO()
    session = balatrobot_session.BalatroBotLiveSession("session-123", diagnostics)

    bridge = session.start()
    session.stop()

    instance = FakeInstance.created[0]
    assert isinstance(bridge, FakeClient)
    assert bridge.port == instance.port
    assert bridge.calls == []
    assert instance.session_id == "session-123"
    assert instance.config.values["logs_path"] == "logs"
    assert instance.started and instance.stopped
    assert session.log_path == "/tmp/balatrobot.log"
    assert diagnostics.getvalue().splitlines() == ["launcher started", "launcher stopped"]


def test_balatrobot_live_session_can_clean_up_after_a_failed_launch(monkeypatch) -> None:
    import balatro_gym.balatrobot_session as balatrobot_session

    FakeInstance.created.clear()
    FakeInstance.start_error = RuntimeError("launcher stopped responding")
    monkeypatch.setattr(
        balatrobot_session,
        "_load_balatrobot",
        lambda: (FakeInstance, FakeClient, FakeConfig),
    )
    session = balatrobot_session.BalatroBotLiveSession("session-123", io.StringIO())

    try:
        with pytest.raises(balatrobot_session.BalatroBotSessionError, match="stopped responding") as error:
            session.start()
        session.stop()
    finally:
        FakeInstance.start_error = None

    assert error.value.phase == "launch"
    assert FakeInstance.created[0].stopped
