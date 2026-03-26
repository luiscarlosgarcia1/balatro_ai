from __future__ import annotations

from .models import GameAction, ObservationPayload, ValidationResult


class DemoPolicy:
    """A tiny heuristic policy to exercise the runtime."""

    def choose_action(self, observation: ObservationPayload) -> GameAction:
        phase = str(observation.get("interaction_phase") or "unknown")
        money = int(observation.get("money") or 0)

        if phase == "shop":
            if money >= 5:
                return GameAction(
                    kind="buy_joker",
                    target="economy_joker",
                    reason="Enough money to improve scaling before the next blind.",
                )
            return GameAction(
                kind="leave_shop",
                reason="Not enough money for a meaningful purchase.",
            )

        if phase == "play_hand":
            return GameAction(
                kind="play_best_hand",
                reason="Advance the round with the strongest available hand.",
            )

        return GameAction(
            kind="continue",
            reason="No special handling for this phase yet.",
        )


class RuleBasedValidator:
    """Reject obviously invalid actions before they reach the executor."""

    _allowed_actions = {
        "shop": {"buy_joker", "reroll_shop", "leave_shop"},
        "play_hand": {"play_best_hand", "discard_worst_cards"},
        "blind_select": {"select_blind", "skip_blind"},
        "reward": {"continue"},
    }

    def validate(
        self,
        observation: ObservationPayload,
        action: GameAction,
    ) -> ValidationResult:
        phase = str(observation.get("interaction_phase") or "unknown")
        money = int(observation.get("money") or 0)
        allowed = self._allowed_actions.get(phase, {"continue"})
        if action.kind not in allowed:
            return ValidationResult(
                accepted=False,
                notes=(
                    f"Action '{action.kind}' is not valid during phase '{phase}'.",
                ),
            )

        if action.kind == "buy_joker" and money < 5:
            return ValidationResult(
                accepted=False,
                notes=("Cannot buy a joker without enough money.",),
            )

        return ValidationResult(
            accepted=True,
            notes=("Action passed rule-based validation.",),
        )
