"""Context manager for a Balatro instance."""

import json
import subprocess
import time
import urllib.error
import urllib.request
from asyncio import TimeoutError as AsyncTimeoutError, get_running_loop, wait_for
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from balatrobot.config import Config
from balatrobot.platforms import get_launcher

HEALTH_TIMEOUT = 30.0


class BalatroInstance:
    """Context manager for a single Balatro instance."""

    def __init__(
        self, config: Config | None = None, session_id: str | None = None, **overrides
    ) -> None:
        """Initialize a Balatro instance.

        Args:
            config: Base configuration. If None, uses Config from environment.
            session_id: Optional session ID for log directory. If None, generated at start().
            **overrides: Override specific config fields (e.g., port=12347).
        """
        base = config or Config.from_env()
        self._config = replace(base, **overrides) if overrides else base
        self._process: subprocess.Popen | None = None
        self._log_path: Path | None = None
        self._session_id = session_id

    @property
    def port(self) -> int:
        """Get the port this instance is running on."""
        return self._config.port

    @property
    def process(self) -> subprocess.Popen:
        """Get the subprocess. Raises if not started."""
        if self._process is None:
            raise RuntimeError("Instance not started")
        return self._process

    @property
    def log_path(self) -> Path | None:
        """Get the log file path, if available."""
        return self._log_path

    def _wait_for_health(self, timeout: float = HEALTH_TIMEOUT) -> None:
        """Wait for health endpoint to respond."""
        deadline = time.monotonic() + timeout
        payload = json.dumps({"jsonrpc": "2.0", "method": "health", "id": 1}).encode(
            "utf-8"
        )
        url = f"http://{self._config.host}:{self._config.port}/"

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"Health check failed after {timeout}s on 127.0.0.1:{self._config.port}"
                )

            process = self._process
            if process is None or process.poll() is not None:
                raise RuntimeError("Instance exited before becoming healthy")

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

    async def start(self) -> None:
        """Start the Balatro instance and wait for health."""
        if self._process is not None:
            raise RuntimeError("Instance already started")

        # Create session directory (use provided session_id or generate one)
        timestamp = self._session_id or datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        session_dir = Path(self._config.logs_path) / timestamp
        session_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = session_dir / f"{self._config.port}.log"

        # Get launcher and start process
        launcher = get_launcher(self._config.platform)
        print(f"Starting Balatro on port {self._config.port}...")

        self._process = await launcher.start(self._config, session_dir)

        # Wait for health
        print(f"Waiting for health check on 127.0.0.1:{self._config.port}...")
        try:
            loop = get_running_loop()
            await loop.run_in_executor(None, self._wait_for_health)
        except (RuntimeError, TimeoutError) as e:
            await self.stop()
            raise RuntimeError(f"{e}. Check log file: {self._log_path}") from e

        print(f"Balatro started (PID: {self._process.pid})")

    async def stop(self) -> None:
        """Stop the Balatro instance."""
        if self._process is None:
            return

        process = self._process
        self._process = None

        print(f"Stopping instance on port {self._config.port}...")

        # Try graceful termination first
        process.terminate()

        loop = get_running_loop()
        try:
            await wait_for(
                loop.run_in_executor(None, process.wait),
                timeout=5,
            )
        except AsyncTimeoutError:
            print(f"Force killing instance on port {self._config.port}...")
            process.kill()
            await loop.run_in_executor(None, process.wait)

    async def __aenter__(self) -> "BalatroInstance":
        """Start instance on context entry."""
        await self.start()
        return self

    async def __aexit__(self, *args) -> None:
        """Stop instance on context exit."""
        await self.stop()
