from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_BALATRO_ROOT = Path.home() / "AppData" / "Roaming" / "Balatro"


@dataclass(frozen=True)
class BalatroPaths:
    root: Path = DEFAULT_BALATRO_ROOT

    @property
    def ai_dir(self) -> Path:
        return self.root / "ai"

    @property
    def live_state_path(self) -> Path:
        return self.ai_dir / "live_state.json"
