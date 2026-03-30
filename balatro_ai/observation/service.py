from __future__ import annotations

from ..models import GameObservation
from .live_parser import LiveObservationParser
from .paths import BalatroPaths


class BalatroObserver:
    """Observation layer backed by the live exporter handoff."""

    def __init__(
        self,
        paths: BalatroPaths | None = None,
        live_parser: LiveObservationParser | None = None,
    ) -> None:
        self.paths = paths or BalatroPaths()
        self.live_parser = live_parser or LiveObservationParser()

    def observe(self) -> GameObservation:
        live_state_path = self.paths.live_state_path
        if not live_state_path.exists():
            raise FileNotFoundError(f"Live state file not found: {live_state_path}")

        live_observation = self.live_parser.parse_file(live_state_path)
        if live_observation is None:
            raise ValueError(f"Could not parse live observation from {live_state_path}")

        return live_observation
