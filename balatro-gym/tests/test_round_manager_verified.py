from __future__ import annotations

from types import SimpleNamespace

from balatro_gym.core.boss_blinds import BossBlindType
from balatro_gym.core.jokers import JokerInfo
from balatro_gym.core.constants import Phase
from balatro_gym.core_utils.rng import DeterministicRNG
from balatro_gym.core_utils.round_manager import RoundManager
from balatro_gym.core_utils.state import UnifiedGameState


def test_round_manager_stages_round_eval_before_cashout():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        round=2,
        money=20,
        hands_left=2,
        round_chips_scored=300,
        vouchers=["Seed Money"],
        jokers=[JokerInfo(84, "To the Moon", 5, "Extra interest")],
    )
    game = SimpleNamespace(round_hands=0, round_discards=0, blind_index=1)
    manager = RoundManager(
        state,
        game,
        SimpleNamespace(end_of_round_effects=lambda _: []),
        boss_blind_manager=None,
    )

    outcome = manager.enter_round_eval()

    assert outcome == "round_eval"
    assert state.phase == Phase.ROUND_EVAL
    assert state.money == 20
    assert state.round_eval_completed_round == 2
    assert state.round_eval_cashout == 14

    cashout_outcome = manager.cash_out()

    assert cashout_outcome == "shop"
    assert state.money == 34
    assert state.phase == Phase.SHOP
    assert state.round_eval_cashout == 0
    assert state.round_eval_completed_round is None


def test_round_manager_honors_legacy_unverified_select_boss_blind_patch(monkeypatch):
    import balatro_gym.core_utils.unverified.round_manager as legacy_round_manager

    state = UnifiedGameState(phase=Phase.PLAY, ante=2, round=2, money=0, hands_left=1)
    game = SimpleNamespace(round_hands=0, round_discards=0, blind_index=1)
    manager = RoundManager(
        state,
        game,
        SimpleNamespace(end_of_round_effects=lambda _: []),
        boss_blind_manager=None,
        rng=DeterministicRNG(7),
    )

    monkeypatch.setattr(
        legacy_round_manager,
        "select_boss_blind",
        lambda ante, exclude=None, rng=None: BossBlindType.THE_HOOK,
    )

    outcome = manager.enter_round_eval()

    assert outcome == "round_eval"
    assert state.pending_boss_blind == BossBlindType.THE_HOOK
