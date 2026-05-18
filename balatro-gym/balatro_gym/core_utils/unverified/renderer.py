"""Simple console renderer for the refactored Balatro environment."""

from __future__ import annotations


class ConsoleRenderer:
    """Render a compact text snapshot of the current game state."""

    def render(self, state, boss_blind_manager=None) -> None:
        hand_cards = []
        for idx in state.hand_indexes:
            if 0 <= idx < len(state.deck):
                card = state.deck[idx]
                hand_cards.append(f"{card.rank.name} of {card.suit.name}")

        boss_name = None
        if boss_blind_manager and boss_blind_manager.active_blind:
            boss_name = boss_blind_manager.active_blind.name

        print(f"Phase: {state.phase.name}")
        print(
            f"Ante {state.ante} Round {state.round} | "
            f"Money ${state.money} | "
            f"Chips {state.round_chips_scored}/{state.chips_needed}"
        )
        print(
            f"Hands left: {state.hands_left} | "
            f"Discards left: {state.discards_left}"
        )
        if boss_name:
            print(f"Boss blind: {boss_name}")
        print(f"Hand: {', '.join(hand_cards) if hand_cards else '(empty)'}")
