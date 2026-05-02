from __future__ import annotations

import random
from typing import Dict, List, Any, Optional


class DeterministicRNG:
    """Centralized RNG system with separate streams for each subsystem"""

    def __init__(self, master_seed: Optional[int] = None):
        self.master_seed = master_seed or random.randint(0, 2**32 - 1)
        self.streams = {}
        self.history = []
        self._initialize_streams()

    def _initialize_streams(self):
        """Create separate RNG streams for each game subsystem"""
        stream_names = [
            'deck_shuffle', 'card_draw', 'shop_generation', 'shop_reroll',
            'joker_effects', 'blind_selection', 'skip_rewards', 'pack_opening',
            'voucher_appearance', 'boss_abilities', 'random_events',
            'card_enhancement', 'edition_rolls', 'seal_applications',
            'consumable_effects', 'score_variance'
        ]

        for i, name in enumerate(stream_names):
            stream_seed = (self.master_seed + i * 1000) % (2**32)
            self.streams[name] = random.Random(stream_seed)

    def get_float(self, stream: str, low: float = 0.0, high: float = 1.0) -> float:
        """Get random float from a specific stream"""
        if stream not in self.streams:
            raise ValueError(f"Unknown RNG stream: {stream}")

        value = self.streams[stream].uniform(low, high)
        self.history.append((stream, 'float', value))
        return value

    def get_int(self, stream: str, low: int, high: int) -> int:
        """Get random integer from a specific stream (inclusive)"""
        if stream not in self.streams:
            raise ValueError(f"Unknown RNG stream: {stream}")

        value = self.streams[stream].randint(low, high)
        self.history.append((stream, 'int', value))
        return value

    def choice(self, stream: str, sequence: List[Any]) -> Any:
        """Make a random choice from a sequence"""
        if stream not in self.streams:
            raise ValueError(f"Unknown RNG stream: {stream}")

        if not sequence:
            raise ValueError("Cannot choose from empty sequence")

        value = self.streams[stream].choice(sequence)
        self.history.append((stream, 'choice', value))
        return value

    def shuffle(self, stream: str, sequence: List[Any]) -> None:
        """Shuffle a sequence in-place"""
        if stream not in self.streams:
            raise ValueError(f"Unknown RNG stream: {stream}")

        self.streams[stream].shuffle(sequence)
        self.history.append((stream, 'shuffle', len(sequence)))

    def get_state(self) -> Dict[str, Any]:
        """Get complete RNG state for saving"""
        return {
            'master_seed': self.master_seed,
            'streams': {name: rng.getstate() for name, rng in self.streams.items()},
            'history_length': len(self.history)
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        """Restore complete RNG state"""
        self.master_seed = state['master_seed']
        for name, stream_state in state['streams'].items():
            if name in self.streams:
                self.streams[name].setstate(stream_state)
