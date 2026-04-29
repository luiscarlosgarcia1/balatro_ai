from __future__ import annotations

import argparse
import atexit
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

# -----------------------------------------------
#
#               BEHAVIOR NOTES
#
# -----------------------------------------------
#
# BalatraPool defaults:
#   n=3, executable="luajit", script="headless/run.lua"
#   shutdown_timeout=2.0s, poll_interval=0.5s, DEFAULT_IO_TIMEOUT=15.0s
#
# PoolManager defaults:
#   poll_interval=0.5s
#
# Shutdown sequence (stop / restart / close):
#   SIGTERM sent first; grace period = shutdown_timeout (default 2.0s).
#   If the process is still alive after the deadline, SIGKILL is sent.
#   An additional 1.0s wait follows SIGKILL before giving up.
#
# On non-Windows, processes are launched in a new session (start_new_session=True)
# and signals are sent to the whole process group via os.killpg().
#
# Per-instance environment:
#   BALATRO_SAVE_DIR is set to headless/.save/instance_{i}/ for each slot.
#   BALATRO_PORT is set to a fixed per-slot HTTP port.
#
# Log files:
#   Written to headless/logs/instance_{i}.log, truncated on each launch (not appended).
#   Pool-level log lines are prefixed with [pool YYYY-MM-DD HH:MM:SS].
#
# PoolManager runtime directory layout (headless/.pool/):
#   manager.pid    — PID of the running manager process.
#   status.json    — written atomically via .tmp + replace() each poll cycle.
#   commands.jsonl — append-only command queue; consumed and deleted each poll cycle.
#   manager.log    — manager-level log, append mode.
#
# Command processing:
#   commands.jsonl is read then unlinked in one step; malformed or unknown commands
#   are logged and skipped, not re-queued.
#
# BalatroPool is an alias for BalatraPool (backwards-compat name).
#
# wait_for_ready() blocks until the instance answers a JSON-RPC health request at
# http://127.0.0.1:{port}/ with result.status == "ok". Raises RuntimeError if the
# process exits before becoming healthy and TimeoutError if the deadline expires.
#
# main() with no subcommand runs a demo: starts 3 instances, waits for all to be
# ready, then prints each slot's port and status.
#
# stop CLI --timeout default is 2.0s (SIGTERM wait before SIGKILL).


# -----------------------------------------------
#
#               DATA MODEL
#
# -----------------------------------------------

@dataclass
class _InstanceSlot:
    index: int
    port: int
    save_dir: Path
    log_path: Path
    process: subprocess.Popen[Any] | None = None
    log_handle: IO[str] | None = None
    state: str = "stopped"
    pid: int | None = None
    returncode: int | None = None
    expected_exit: bool = False
    last_event: str | None = None


# -----------------------------------------------
#
#               BALATRA POOL
#
# -----------------------------------------------

class BalatraPool:
    DEFAULT_IO_TIMEOUT = 15.0

    def __init__(
        self,
        n: int = 3,
        *,
        executable: str = "luajit",
        script: str = "headless/run.lua",
        project_root: str | os.PathLike[str] | None = None,
        shutdown_timeout: float = 2.0,
        poll_interval: float = 0.5,
        base_port: int = 12346,
    ) -> None:
        if n <= 0:
            raise ValueError("n must be greater than zero")

        self.n = n
        self.executable = executable
        self.script = script
        self.project_root = Path(project_root or Path(__file__).resolve().parent.parent).resolve()
        self.headless_root = self.project_root / "headless"
        self.logs_dir = self.headless_root / "logs"
        self.saves_dir = self.headless_root / ".save"
        self.shutdown_timeout = shutdown_timeout
        self.poll_interval = poll_interval
        self.base_port = base_port

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.saves_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._monitor_stop = threading.Event()
        self._monitor_thread: threading.Thread | None = None
        self._closed = False

        self._slots = [
            _InstanceSlot(
                index=i,
                port=self.base_port + i,
                save_dir=self.saves_dir / f"instance_{i}",
                log_path=self.logs_dir / f"instance_{i}.log",
            )
            for i in range(n)
        ]

        atexit.register(self._atexit_cleanup)

    # ---  public API  ---------------------------------------------------

    def start(self) -> None:
        with self._lock:
            self._ensure_open()
            self._refresh_processes_locked()
            self._ensure_monitor_thread_locked()
            for slot in self._slots:
                if slot.process is not None and slot.process.poll() is None:
                    continue
                self._launch_slot_locked(slot)

    def stop(self) -> None:
        with self._lock:
            self._refresh_processes_locked()
            alive_slots = [
                slot for slot in self._slots
                if slot.process is not None and slot.process.poll() is None
            ]

            for slot in alive_slots:
                slot.expected_exit = True
                self._append_log_locked(slot, "sending SIGTERM")
                self._signal_slot_locked(slot, signal.SIGTERM)

        deadline = time.monotonic() + self.shutdown_timeout
        while time.monotonic() < deadline:
            with self._lock:
                self._refresh_processes_locked()
                if all(slot.process is None for slot in alive_slots):
                    return
            time.sleep(0.1)

        with self._lock:
            for slot in alive_slots:
                if slot.process is not None and slot.process.poll() is None:
                    self._append_log_locked(slot, "did not exit after SIGTERM; sending SIGKILL")
                    self._signal_slot_locked(slot, signal.SIGKILL)

        kill_deadline = time.monotonic() + 1.0
        while time.monotonic() < kill_deadline:
            with self._lock:
                self._refresh_processes_locked()
                if all(slot.process is None for slot in alive_slots):
                    break
            time.sleep(0.05)

        with self._lock:
            self._refresh_processes_locked()

    def restart(self, i: int) -> None:
        with self._lock:
            self._ensure_open()
            slot = self._get_slot_locked(i)
            self._refresh_processes_locked()

            if slot.process is not None and slot.process.poll() is None:
                slot.expected_exit = True
                self._append_log_locked(slot, "restart requested; sending SIGTERM")
                self._signal_slot_locked(slot, signal.SIGTERM)

        deadline = time.monotonic() + self.shutdown_timeout
        while time.monotonic() < deadline:
            with self._lock:
                self._refresh_processes_locked()
                if slot.process is None:
                    break
            time.sleep(0.1)

        with self._lock:
            if slot.process is not None and slot.process.poll() is None:
                self._append_log_locked(slot, "restart escalation; sending SIGKILL")
                self._signal_slot_locked(slot, signal.SIGKILL)

        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            with self._lock:
                self._refresh_processes_locked()
                if slot.process is None:
                    break
            time.sleep(0.05)

        with self._lock:
            self._refresh_processes_locked()
            self._ensure_monitor_thread_locked()
            self._launch_slot_locked(slot)

    def status(self) -> list[dict[str, Any]]:
        with self._lock:
            self._refresh_processes_locked()
            snapshot: list[dict[str, Any]] = []
            for slot in self._slots:
                snapshot.append({
                    "index": slot.index,
                    "port": slot.port,
                    "state": slot.state,
                    "alive": slot.state == "alive",
                    "pid": slot.pid,
                    "returncode": slot.returncode,
                    "save_dir": str(slot.save_dir),
                    "log_path": str(slot.log_path),
                    "last_event": slot.last_event,
                })
            return snapshot

    def wait_for_ready(self, i: int, timeout: float = DEFAULT_IO_TIMEOUT) -> None:
        slot = self._get_live_slot(i)
        deadline = time.monotonic() + timeout
        payload = json.dumps({"jsonrpc": "2.0", "method": "health", "id": 1}).encode("utf-8")
        url = f"http://127.0.0.1:{slot.port}/"

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._mark_slot_dead(slot, f"timed out waiting {timeout:.1f}s for health check")
                raise TimeoutError(f"timed out waiting for instance {i} to be ready")

            with self._lock:
                self._refresh_processes_locked()
                process = slot.process
                if process is None or process.poll() is not None or slot.state != "alive":
                    raise RuntimeError(f"instance {i} exited before becoming healthy")

            request = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            try:
                request_timeout = max(0.1, min(remaining, 1.0))
                with urllib.request.urlopen(request, timeout=request_timeout) as response:
                    body = response.read()
                data = json.loads(body.decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, ValueError):
                time.sleep(min(0.1, max(remaining, 0.0)))
                continue

            if not isinstance(data, dict):
                time.sleep(min(0.1, max(remaining, 0.0)))
                continue

            result = data.get("result")
            if isinstance(result, dict) and result.get("status") == "ok":
                return

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True

        self.stop()
        self._monitor_stop.set()
        monitor = self._monitor_thread
        if monitor is not None and monitor.is_alive():
            monitor.join(timeout=1.0)

        with self._lock:
            for slot in self._slots:
                self._close_log_locked(slot)

    # ---  private internals  --------------------------------------------

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("pool is closed")

    def _get_slot_locked(self, index: int) -> _InstanceSlot:
        if index < 0 or index >= self.n:
            raise IndexError(f"instance index {index} is out of range")
        return self._slots[index]

    def _ensure_monitor_thread_locked(self) -> None:
        thread = self._monitor_thread
        if thread is not None and thread.is_alive():
            return

        self._monitor_stop.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="balatra-pool-monitor",
            daemon=True,
        )
        self._monitor_thread.start()

    def _monitor_loop(self) -> None:
        while not self._monitor_stop.wait(self.poll_interval):
            with self._lock:
                self._refresh_processes_locked()

    def _launch_slot_locked(self, slot: _InstanceSlot) -> None:
        if slot.process is not None and slot.process.poll() is None:
            return

        self._close_log_locked(slot)
        slot.save_dir.mkdir(parents=True, exist_ok=True)
        slot.log_path.parent.mkdir(parents=True, exist_ok=True)
        if slot.state == "dead" and slot.log_path.exists():
            slot.log_path.replace(slot.log_path.with_suffix(".prev.log"))
        log_handle = slot.log_path.open("w", encoding="utf-8", buffering=1)

        env = os.environ.copy()
        env["BALATRO_SAVE_DIR"] = str(slot.save_dir)
        env["BALATRO_PORT"] = str(slot.port)

        kwargs: dict[str, Any] = {
            "cwd": str(self.project_root),
            "env": env,
            "stdin": subprocess.DEVNULL,
            "stdout": log_handle,
            "stderr": log_handle,
            "text": True,
            "encoding": "utf-8",
            "bufsize": 1,
        }
        if os.name != "nt":
            kwargs["start_new_session"] = True

        try:
            process = subprocess.Popen(
                [self.executable, self.script],
                **kwargs,
            )
        except Exception:
            log_handle.close()
            raise

        slot.log_handle = log_handle
        slot.process = process
        slot.state = "alive"
        slot.pid = process.pid
        slot.returncode = None
        slot.expected_exit = False
        slot.last_event = "started"
        self._append_log_locked(
            slot,
            f"started pid={process.pid} port={slot.port} save_dir={slot.save_dir}",
        )

    def _refresh_processes_locked(self) -> None:
        for slot in self._slots:
            process = slot.process
            if process is None:
                continue

            returncode = process.poll()
            if returncode is None:
                continue

            unexpected = not slot.expected_exit
            self._finalize_slot_exit_locked(slot, returncode, unexpected=unexpected)

    def _finalize_slot_exit_locked(
        self,
        slot: _InstanceSlot,
        returncode: int,
        *,
        unexpected: bool,
    ) -> None:
        crashed = unexpected and returncode != 0

        slot.returncode = returncode
        slot.state = "dead" if unexpected else "stopped"
        if crashed:
            slot.last_event = "crashed"
        elif unexpected:
            slot.last_event = "exited"
        else:
            slot.last_event = "stopped"

        if crashed:
            self._append_log_locked(
                slot,
                f"process exited unexpectedly with returncode={returncode}",
            )
        else:
            self._append_log_locked(
                slot,
                f"process exited with returncode={returncode}",
            )

        slot.process = None
        slot.expected_exit = False
        self._close_log_locked(slot)

    def _signal_slot_locked(self, slot: _InstanceSlot, sig: signal.Signals) -> None:
        process = slot.process
        if process is None or process.poll() is not None:
            return

        try:
            if os.name != "nt":
                os.killpg(process.pid, sig)
            elif sig == signal.SIGTERM:
                process.terminate()
            else:
                process.kill()
        except ProcessLookupError:
            return

    def _append_log_locked(self, slot: _InstanceSlot, message: str) -> None:
        if slot.log_handle is None:
            return
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        slot.log_handle.write(f"[pool {timestamp}] {message}\n")
        slot.log_handle.flush()

    def _close_log_locked(self, slot: _InstanceSlot) -> None:
        if slot.log_handle is None:
            return
        try:
            slot.log_handle.flush()
        finally:
            slot.log_handle.close()
            slot.log_handle = None

    def _get_live_slot(self, index: int) -> _InstanceSlot:
        with self._lock:
            self._ensure_open()
            slot = self._get_slot_locked(index)
            self._refresh_processes_locked()
            process = slot.process
            if process is None or process.poll() is not None or slot.state != "alive":
                raise RuntimeError(f"instance {index} is not alive")
            return slot

    def _mark_slot_dead(self, slot: _InstanceSlot, reason: str) -> None:
        process_to_wait: subprocess.Popen[Any] | None = None

        with self._lock:
            self._append_log_locked(slot, reason)
            process = slot.process
            if process is None:
                if slot.state == "alive":
                    slot.state = "dead"
                    slot.last_event = "io_error"
                return

            returncode = process.poll()
            if returncode is not None:
                self._finalize_slot_exit_locked(slot, returncode, unexpected=True)
                return

            slot.state = "dead"
            slot.last_event = "io_error"
            slot.expected_exit = True
            process_to_wait = process
            self._signal_slot_locked(slot, signal.SIGKILL)

        if process_to_wait is None:
            return

        try:
            returncode = process_to_wait.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            return

        with self._lock:
            if slot.process is process_to_wait:
                self._finalize_slot_exit_locked(slot, returncode, unexpected=True)

    def _atexit_cleanup(self) -> None:
        try:
            self.close()
        except Exception:
            pass


# -----------------------------------------------
#
#               BACKWARDS-COMPAT ALIAS
#
# -----------------------------------------------

BalatroPool = BalatraPool


# -----------------------------------------------
#
#               POOL MANAGER
#
# -----------------------------------------------

class PoolManager:
    def __init__(
        self,
        n: int,
        *,
        runtime_dir: str | os.PathLike[str] | None = None,
        project_root: str | os.PathLike[str] | None = None,
        poll_interval: float = 0.5,
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parent.parent).resolve()
        self.runtime_dir = Path(runtime_dir or (self.project_root / "headless" / ".pool")).resolve()
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

        self.pid_path = self.runtime_dir / "manager.pid"
        self.status_path = self.runtime_dir / "status.json"
        self.commands_path = self.runtime_dir / "commands.jsonl"
        self.manager_log_path = self.runtime_dir / "manager.log"
        self.stop_event = threading.Event()
        self.pool = BalatraPool(n=n, project_root=self.project_root, poll_interval=poll_interval)
        self.n = n
        self.poll_interval = poll_interval

    # ---  public API  ---------------------------------------------------

    def run(self) -> int:
        self._install_signal_handlers()
        self._write_pid_file()
        self._write_status()

        try:
            self.pool.start()
            self._write_status()

            while not self.stop_event.wait(self.poll_interval):
                self._process_commands()
                self._write_status()

            return 0
        finally:
            self.pool.stop()
            self._write_status()
            self.pool.close()
            self._cleanup_pid_file()

    def request_stop(self) -> None:
        self.stop_event.set()

    # ---  private internals  --------------------------------------------

    def _install_signal_handlers(self) -> None:
        def handler(signum: int, _frame: Any) -> None:
            self._append_manager_log(f"received signal {signum}; shutting down")
            self.request_stop()

        signal.signal(signal.SIGTERM, handler)
        signal.signal(signal.SIGINT, handler)

    def _write_pid_file(self) -> None:
        self.pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
        self._append_manager_log(f"manager started pid={os.getpid()} n={self.n}")

    def _cleanup_pid_file(self) -> None:
        try:
            if self.pid_path.exists():
                self.pid_path.unlink()
        except FileNotFoundError:
            pass

    def _write_status(self) -> None:
        payload = {
            "manager_pid": os.getpid(),
            "n": self.n,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "instances": self.pool.status(),
        }
        tmp_path = self.status_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp_path.replace(self.status_path)

    def _append_manager_log(self, message: str) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with self.manager_log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[manager {timestamp}] {message}\n")

    def _process_commands(self) -> None:
        if not self.commands_path.exists():
            return

        try:
            lines = self.commands_path.read_text(encoding="utf-8").splitlines()
            self.commands_path.unlink()
        except FileNotFoundError:
            return

        for line in lines:
            if not line.strip():
                continue

            try:
                command = json.loads(line)
            except json.JSONDecodeError:
                self._append_manager_log(f"ignored malformed command: {line}")
                continue

            action = command.get("action")
            if action == "restart":
                index = command.get("index")
                if not isinstance(index, int):
                    self._append_manager_log(f"ignored restart command with invalid index: {line}")
                    continue

                try:
                    self.pool.restart(index)
                    self._append_manager_log(f"restarted instance index={index}")
                except Exception as exc:
                    self._append_manager_log(f"failed to restart instance index={index}: {exc}")
            else:
                self._append_manager_log(f"ignored unknown command action={action!r}")


# -----------------------------------------------
#
#               CLI UTILITIES
#
# -----------------------------------------------

def _runtime_paths(project_root: Path) -> tuple[Path, Path, Path, Path]:
    runtime_dir = project_root / "headless" / ".pool"
    return (
        runtime_dir,
        runtime_dir / "manager.pid",
        runtime_dir / "status.json",
        runtime_dir / "commands.jsonl",
    )


def _read_manager_pid(pid_path: Path) -> int | None:
    try:
        return int(pid_path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# -----------------------------------------------
#
#               CLI COMMANDS
#
# -----------------------------------------------

def _cmd_run(args: argparse.Namespace) -> int:
    manager = PoolManager(n=args.n, project_root=Path(args.project_root).resolve())
    return manager.run()


def _cmd_start(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    runtime_dir, pid_path, _status_path, _commands_path = _runtime_paths(project_root)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    existing_pid = _read_manager_pid(pid_path)
    if existing_pid and _pid_is_alive(existing_pid):
        print(f"manager already running with pid {existing_pid}")
        return 0

    manager_log_path = runtime_dir / "manager.log"
    with manager_log_path.open("a", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "run",
                "--n",
                str(args.n),
                "--project-root",
                str(project_root),
            ],
            cwd=str(project_root),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=(os.name != "nt"),
        )

    print(f"started manager pid={process.pid} n={args.n}")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    _runtime_dir, pid_path, status_path, _commands_path = _runtime_paths(project_root)

    manager_pid = _read_manager_pid(pid_path)
    if manager_pid is None:
        print("manager not running")
        if status_path.exists():
            print(status_path.read_text(encoding="utf-8"))
        return 1

    alive = _pid_is_alive(manager_pid)
    print(f"manager pid={manager_pid} alive={alive}")

    if status_path.exists():
        print(status_path.read_text(encoding="utf-8"))
        return 0

    print(f"no status file found at {status_path}")
    return 1


def _cmd_stop(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    _runtime_dir, pid_path, _status_path, _commands_path = _runtime_paths(project_root)

    manager_pid = _read_manager_pid(pid_path)
    if manager_pid is None:
        print("manager not running")
        return 0

    if not _pid_is_alive(manager_pid):
        print(f"stale pid file for pid {manager_pid}; removing it")
        pid_path.unlink(missing_ok=True)
        return 0

    try:
        os.kill(manager_pid, signal.SIGTERM)
    except PermissionError:
        print(f"could not signal manager pid={manager_pid}; permission denied")
        return 1

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        if not _pid_is_alive(manager_pid):
            print(f"stopped manager pid={manager_pid}")
            pid_path.unlink(missing_ok=True)
            return 0
        time.sleep(0.1)

    try:
        os.kill(manager_pid, signal.SIGKILL)
    except PermissionError:
        print(f"manager pid={manager_pid} did not stop, and SIGKILL was not permitted")
        return 1

    print(f"force-killed manager pid={manager_pid}")
    pid_path.unlink(missing_ok=True)
    return 0


def _cmd_restart(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    runtime_dir, pid_path, _status_path, commands_path = _runtime_paths(project_root)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    manager_pid = _read_manager_pid(pid_path)
    if manager_pid is None or not _pid_is_alive(manager_pid):
        print("manager not running")
        return 1

    command = {
        "action": "restart",
        "index": args.index,
        "requested_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with commands_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(command) + "\n")

    print(f"queued restart for instance index={args.index}")
    return 0


# -----------------------------------------------
#
#               ENTRY POINT
#
# -----------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    project_root = Path(__file__).resolve().parent.parent

    parser = argparse.ArgumentParser(description="Manage a pool of headless Balatro instances.")
    parser.set_defaults(func=None)
    subparsers = parser.add_subparsers(dest="command")

    start_parser = subparsers.add_parser("start", help="Start the pool manager in the background.")
    start_parser.add_argument("--n", type=int, required=True, help="Number of instances to launch.")
    start_parser.add_argument("--project-root", default=str(project_root), help="Project root path.")
    start_parser.set_defaults(func=_cmd_start)

    run_parser = subparsers.add_parser("run", help="Run the pool manager in the foreground.")
    run_parser.add_argument("--n", type=int, required=True, help="Number of instances to launch.")
    run_parser.add_argument("--project-root", default=str(project_root), help="Project root path.")
    run_parser.set_defaults(func=_cmd_run)

    status_parser = subparsers.add_parser("status", help="Show manager and instance status.")
    status_parser.add_argument("--project-root", default=str(project_root), help="Project root path.")
    status_parser.set_defaults(func=_cmd_status)

    stop_parser = subparsers.add_parser("stop", help="Stop the background pool manager.")
    stop_parser.add_argument("--project-root", default=str(project_root), help="Project root path.")
    stop_parser.add_argument("--timeout", type=float, default=2.0, help="Grace period before SIGKILL.")
    stop_parser.set_defaults(func=_cmd_stop)

    restart_parser = subparsers.add_parser("restart", help="Restart one managed instance by index.")
    restart_parser.add_argument("--index", type=int, required=True, help="Instance index to restart.")
    restart_parser.add_argument("--project-root", default=str(project_root), help="Project root path.")
    restart_parser.set_defaults(func=_cmd_restart)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.func is None:
        pool = BalatraPool(n=3)
        try:
            pool.start()
            for i in range(3):
                pool.wait_for_ready(i)
            for entry in pool.status():
                print(f"instance {entry['index']}: port={entry['port']} status={entry['state']}")
        finally:
            pool.stop()
        return 0

    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
