from __future__ import annotations

import io
import json

import pytest


def test_watch_forwards_seed_and_inspection_mode_while_preserving_output_streams(
    monkeypatch,
) -> None:
    from balatro_gym import cli
    from balatro_gym.watchable_session import WatchableSessionResult

    calls: list[tuple[str, bool]] = []

    def fake_runner(seed: str, *, keep_open: bool, output, diagnostics):
        calls.append((seed, keep_open))
        print(json.dumps({"event": "settled", "seed": seed}), file=output)
        print("Session settled.", file=diagnostics)
        return WatchableSessionResult(exit_code=0, outcome="ROUND_EVAL")

    monkeypatch.setattr(cli, "run_watchable_session", fake_runner)
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = cli.main(
        ["watch", "--seed", "BAL9SEED", "--keep-open"],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert calls == [("BAL9SEED", True)]
    assert [json.loads(line) for line in stdout.getvalue().splitlines()] == [
        {"event": "settled", "seed": "BAL9SEED"}
    ]
    assert stderr.getvalue() == "Session settled.\n"


def test_watch_returns_the_runner_failure_exit_code(monkeypatch) -> None:
    from balatro_gym import cli
    from balatro_gym.watchable_session import WatchableSessionResult

    calls: list[tuple[str, bool]] = []

    def fake_runner(seed: str, *, keep_open: bool, output, diagnostics):
        calls.append((seed, keep_open))
        del output
        print("Watchable session failed during launch.", file=diagnostics)
        return WatchableSessionResult(exit_code=1, outcome=None, phase="launch")

    monkeypatch.setattr(cli, "run_watchable_session", fake_runner)
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = cli.main(["watch", "--seed", "BAL9SEED"], stdout=stdout, stderr=stderr)

    assert exit_code == 1
    assert calls == [("BAL9SEED", False)]
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Watchable session failed during launch.\n"


def test_watch_help_keeps_standard_output_jsonl_safe() -> None:
    from balatro_gym import cli

    stdout = io.StringIO()
    stderr = io.StringIO()

    with pytest.raises(SystemExit) as exit_error:
        cli.main(["watch", "--help"], stdout=stdout, stderr=stderr)

    assert exit_error.value.code == 0
    assert stdout.getvalue() == ""
    assert "usage: balatro-gym watch" in stderr.getvalue()
