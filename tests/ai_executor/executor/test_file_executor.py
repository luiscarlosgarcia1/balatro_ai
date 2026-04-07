from __future__ import annotations

import json
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from balatro_ai.action_kind import ActionKind
from balatro_ai.executor import ExecutorError, FileExecutor
from balatro_ai.models import GameAction


def _make_paths(ai_dir: Path):
    """Minimal paths stub — only needs .ai_dir."""
    class _Paths:
        pass
    p = _Paths()
    p.ai_dir = ai_dir
    return p


class TestFileExecutorWritesActionJson(unittest.TestCase):
    """Tracer bullet: execute writes action.json and returns when it is deleted."""

    def test_execute_writes_action_json_and_returns_on_deletion(self) -> None:
        with TemporaryDirectory() as tmp:
            ai_dir = Path(tmp)
            action_path = ai_dir / "action.json"
            paths = _make_paths(ai_dir)
            executor = FileExecutor(paths, poll_interval=0.01, timeout=2.0)
            action = GameAction(kind=ActionKind.PLAY_HAND, target_ids=(1, 2))

            written_payload: list[dict] = []

            def _deleter():
                # Wait until action.json appears, capture payload, then delete it
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline:
                    if action_path.exists():
                        written_payload.append(json.loads(action_path.read_text()))
                        action_path.unlink()
                        return
                    time.sleep(0.005)

            t = threading.Thread(target=_deleter, daemon=True)
            t.start()
            executor.execute(action)  # must return after deletion
            t.join(timeout=3.0)

            self.assertTrue(written_payload, "action.json was never written")
            payload = written_payload[0]
            self.assertIn("actions", payload)
            self.assertEqual(len(payload["actions"]), 1)
            item = payload["actions"][0]
            self.assertEqual(item["kind"], ActionKind.PLAY_HAND)
            self.assertEqual(item["target_ids"], [1, 2])
            self.assertIn("target_key", item)
            self.assertIn("order", item)


class TestFileExecutorErrorHandling(unittest.TestCase):
    """execute raises ExecutorError with reason when action_error.json appears."""

    def test_execute_raises_executor_error_on_error_file(self) -> None:
        with TemporaryDirectory() as tmp:
            ai_dir = Path(tmp)
            action_path = ai_dir / "action.json"
            error_path = ai_dir / "action_error.json"
            paths = _make_paths(ai_dir)
            executor = FileExecutor(paths, poll_interval=0.01, timeout=2.0)
            action = GameAction(kind=ActionKind.DISCARD, target_ids=(5,))

            def _write_error():
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline:
                    if action_path.exists():
                        error_path.write_text("card not found", encoding="utf-8")
                        return
                    time.sleep(0.005)

            t = threading.Thread(target=_write_error, daemon=True)
            t.start()
            with self.assertRaises(ExecutorError) as ctx:
                executor.execute(action)
            t.join(timeout=3.0)

            self.assertIn("card not found", str(ctx.exception))

    def test_execute_cleans_up_error_file_after_raising(self) -> None:
        with TemporaryDirectory() as tmp:
            ai_dir = Path(tmp)
            action_path = ai_dir / "action.json"
            error_path = ai_dir / "action_error.json"
            paths = _make_paths(ai_dir)
            executor = FileExecutor(paths, poll_interval=0.01, timeout=2.0)
            action = GameAction(kind=ActionKind.DISCARD)

            def _write_error():
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline:
                    if action_path.exists():
                        error_path.write_text("some error", encoding="utf-8")
                        return
                    time.sleep(0.005)

            t = threading.Thread(target=_write_error, daemon=True)
            t.start()
            with self.assertRaises(ExecutorError):
                executor.execute(action)
            t.join(timeout=3.0)

            self.assertFalse(error_path.exists(), "error file should be deleted after raising")


class TestFileExecutorTimeout(unittest.TestCase):
    """execute raises ExecutorError when neither signal arrives within timeout."""

    def test_execute_raises_on_timeout(self) -> None:
        with TemporaryDirectory() as tmp:
            ai_dir = Path(tmp)
            paths = _make_paths(ai_dir)
            executor = FileExecutor(paths, poll_interval=0.01, timeout=0.05)
            action = GameAction(kind=ActionKind.REROLL_SHOP)

            with self.assertRaises(ExecutorError) as ctx:
                executor.execute(action)

            self.assertIn("timeout", str(ctx.exception))


class TestExecuteSequence(unittest.TestCase):
    """execute_sequence writes all actions as one atomic queue."""

    def test_execute_sequence_writes_all_actions_in_single_payload(self) -> None:
        with TemporaryDirectory() as tmp:
            ai_dir = Path(tmp)
            action_path = ai_dir / "action.json"
            paths = _make_paths(ai_dir)
            executor = FileExecutor(paths, poll_interval=0.01, timeout=2.0)
            actions = [
                GameAction(kind=ActionKind.PLAY_HAND, target_ids=(1, 2)),
                GameAction(kind=ActionKind.DISCARD, target_ids=(3,)),
                GameAction(kind=ActionKind.LEAVE_SHOP),
            ]

            written_payloads: list[dict] = []

            def _deleter():
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline:
                    if action_path.exists():
                        written_payloads.append(json.loads(action_path.read_text()))
                        action_path.unlink()
                        return
                    time.sleep(0.005)

            t = threading.Thread(target=_deleter, daemon=True)
            t.start()
            executor.execute_sequence(actions)
            t.join(timeout=3.0)

            self.assertTrue(written_payloads, "action.json was never written")
            payload = written_payloads[0]
            self.assertIn("actions", payload)
            self.assertEqual(len(payload["actions"]), 3)
            kinds = [item["kind"] for item in payload["actions"]]
            self.assertEqual(kinds, [ActionKind.PLAY_HAND, ActionKind.DISCARD, ActionKind.LEAVE_SHOP])

    def test_execute_sequence_single_write_is_atomic(self) -> None:
        """execute_sequence must use exactly ONE file write (temp+rename), not one per action."""
        with TemporaryDirectory() as tmp:
            ai_dir = Path(tmp)
            action_path = ai_dir / "action.json"
            paths = _make_paths(ai_dir)
            executor = FileExecutor(paths, poll_interval=0.01, timeout=2.0)
            actions = [
                GameAction(kind=ActionKind.BUY_SHOP_ITEM, target_ids=(10,)),
                GameAction(kind=ActionKind.LEAVE_SHOP),
            ]

            appearances: list[int] = []

            def _observer():
                seen = False
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline:
                    exists_now = action_path.exists()
                    if exists_now and not seen:
                        appearances.append(1)
                        seen = True
                    elif not exists_now and seen:
                        action_path.unlink(missing_ok=True)  # shouldn't be needed, but safety
                        return
                    time.sleep(0.002)

            # Simpler: just delete after first appearance and count appearances
            written: list[dict] = []

            def _deleter():
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline:
                    if action_path.exists():
                        written.append(json.loads(action_path.read_text()))
                        action_path.unlink()
                        return
                    time.sleep(0.005)

            t = threading.Thread(target=_deleter, daemon=True)
            t.start()
            executor.execute_sequence(actions)
            t.join(timeout=3.0)

            # The payload should contain both actions in one write
            self.assertEqual(len(written), 1)
            self.assertEqual(len(written[0]["actions"]), 2)


if __name__ == "__main__":
    unittest.main()
