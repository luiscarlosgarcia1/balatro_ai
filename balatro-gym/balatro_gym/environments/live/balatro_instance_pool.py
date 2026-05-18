"""
balatro_gym/balatro_instance_pool.py

Manages a pool of real Balatro instances for parallel RL training.

Usage:
    with BalatroInstancePool(n=4, base_port=12345) as pool:
        ports = pool.ports  # [12345, 12346, 12347, 12348]
        envs = SubprocVecEnv([lambda p=p: BalatroLiveEnv(port=p) for p in ports])
        # train ...

The pool launches instances using `uvx balatrobot serve` with headless/fast flags
and waits for each health endpoint to respond before returning.
"""

from __future__ import annotations

import atexit
import os
import shlex
import signal
import subprocess
import time
from typing import Optional

import httpx


_HEADLESS_FLAGS = [
    "--fast",
    "--headless",
    "--no-shaders",
    "--fps-cap", "5",
    "--gamespeed", "16",
    "--animation-fps", "1",
]

_VISIBLE_FLAGS = [
    "--fast",
    "--no-shaders",
    "--fps-cap", "5",
    "--gamespeed", "16",
    "--animation-fps", "1",
]

_HEALTH_TIMEOUT = 60.0
_POLL_INTERVAL  = 0.5


def _health_ok(host: str, port: int, timeout: float = 2.0) -> bool:
    payload = {"jsonrpc": "2.0", "method": "health", "params": {}, "id": 1}
    try:
        r = httpx.post(f"http://{host}:{port}", json=payload, timeout=timeout)
        return r.json().get("result", {}).get("status") == "ok"
    except Exception:
        return False


def _kill_group(proc: subprocess.Popen) -> None:
    """Kill the entire process group spawned by proc (catches uvx child processes)."""
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        try:
            proc.terminate()
        except OSError:
            pass


def _kill_group_force(proc: subprocess.Popen) -> None:
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        try:
            proc.kill()
        except OSError:
            pass


class BalatroInstancePool:
    """
    Launches and owns N Balatro processes, one per training environment.

    Args:
        n:           Number of instances (also number of parallel envs).
        base_port:   First port; subsequent instances use base_port+1, +2, …
        extra_ports: Additional ports to launch (e.g. for a dedicated eval env).
        show_first:  If True, launch the first instance visible (no --headless).
                     Useful for watching the agent play in real time.
        host:        Host to bind / poll health on.
        health_timeout: Seconds to wait for each instance to become healthy.
    """

    def __init__(
        self,
        n: int = 4,
        base_port: int = 12345,
        extra_ports: int = 0,
        show_first: bool = False,
        host: str = "127.0.0.1",
        health_timeout: float = _HEALTH_TIMEOUT,
    ) -> None:
        self.n = n
        self.base_port = base_port
        self.host = host
        self.health_timeout = health_timeout
        self.show_first = show_first

        total = n + extra_ports
        self._ports: list[int] = [base_port + i for i in range(total)]
        self._procs: list[subprocess.Popen] = []
        self._started = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def ports(self) -> list[int]:
        """Ports for the primary training envs (excludes extra_ports)."""
        return self._ports[: self.n]

    @property
    def all_ports(self) -> list[int]:
        """All launched ports, including extra (e.g. eval env)."""
        return list(self._ports)

    def start(self) -> "BalatroInstancePool":
        if self._started:
            return self
        self._started = True

        print(f"[BalatroInstancePool] Launching {len(self._ports)} instances…")

        for i, port in enumerate(self._ports):
            visible = True
            flags = _VISIBLE_FLAGS
            cmd = ["uvx", "balatrobot", "serve", "--port", str(port)] + flags
            print(f"  → port {port} (visible): {shlex.join(cmd)}")
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # own process group so we can kill the whole tree
            )
            self._procs.append(proc)
            time.sleep(1.5)  # stagger launches to avoid resource contention at startup

        atexit.register(self.stop)

        self._wait_for_all_healthy()
        print(f"[BalatroInstancePool] All {len(self._ports)} instances healthy.")
        return self

    def stop(self) -> None:
        if not self._procs:
            return
        procs, self._procs = self._procs, []
        print(f"[BalatroInstancePool] Stopping {len(procs)} instances…")

        for proc in procs:
            _kill_group(proc)

        deadline = time.monotonic() + 5.0
        for proc in procs:
            remaining = max(0.0, deadline - time.monotonic())
            try:
                proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                _kill_group_force(proc)
                proc.wait()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "BalatroInstancePool":
        return self.start()

    def __exit__(self, *_) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _wait_for_all_healthy(self) -> None:
        deadline = time.monotonic() + self.health_timeout
        pending = list(self._ports)

        while pending:
            if time.monotonic() > deadline:
                raise RuntimeError(
                    f"[BalatroInstancePool] Timed out waiting for instances on ports: {pending}"
                )
            still_pending = []
            for port in pending:
                if _health_ok(self.host, port):
                    print(f"  ✓ port {port} healthy")
                else:
                    still_pending.append(port)
            pending = still_pending
            if pending:
                time.sleep(_POLL_INTERVAL)
