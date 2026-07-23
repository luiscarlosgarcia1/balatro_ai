from __future__ import annotations

from types import SimpleNamespace

from balatro_gym.core.boss_blinds import BossBlindType
from balatro_gym.core.cards import Card, Rank, Suit
from balatro_gym.core.constants import Action, Phase
from balatro_gym.core.jokers import JokerInfo
from balatro_gym.core_utils.round_manager import RoundManager
from balatro_gym.core_utils.state import UnifiedGameState


def test_round_manager_enter_round_eval_stages_cashout_without_paying():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        round=2,
        money=37,
        hands_left=2,
        vouchers=["Seed Money"],
        jokers=[JokerInfo(84, "To the Moon", 5, "Extra interest")],
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=None)

    manager.enter_round_eval()

    assert state.phase == Phase.ROUND_EVAL
    assert state.money == 37
    assert state.round_eval_cashout == 20
    assert state.round_eval_completed_round == 2
    assert state.round == 3


def test_round_manager_cash_out_pays_staged_eval_and_enters_shop():
    state = UnifiedGameState(
        phase=Phase.ROUND_EVAL,
        round=3,
        money=37,
        hands_left=0,
        discards_left=0,
        round_eval_cashout=20,
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=None)

    manager.cash_out()

    assert state.phase == Phase.SHOP
    assert state.money == 57
    assert state.round_eval_cashout == 0
    assert state.round_eval_completed_round is None
    assert state.hands_left == 4
    assert state.discards_left == 3
    assert game.round_hands == 4
    assert game.round_discards == 3


def test_round_manager_final_boss_sets_won_during_round_eval():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        ante=8,
        win_ante=8,
        round=3,
        money=24,
        hands_left=1,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_HOOK,
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    boss_blind_manager = SimpleNamespace(active_blind=SimpleNamespace(money_reward=5), deactivate=lambda: None)
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=boss_blind_manager)

    manager.enter_round_eval()

    assert state.phase == Phase.ROUND_EVAL
    assert state.won is True
    assert state.game_over is False
    assert state.ante == 9
    assert state.round == 1


def test_round_eval_action_mask_only_allows_cashout():
    state = UnifiedGameState(phase=Phase.ROUND_EVAL, round_eval_cashout=12)

    from balatro_gym.core_utils.mvp_contract import build_action_mask, build_mvp_action_mask

    mask = build_mvp_action_mask(state)
    kwargs_mask = build_action_mask(phase=Phase.ROUND_EVAL)

    assert mask[Action.SHOP_END] == 1
    assert mask.sum() == 1
    assert kwargs_mask[Action.SHOP_END] == 1
    assert kwargs_mask.sum() == 1


def test_game_over_action_mask_has_no_actions():
    state = UnifiedGameState(phase=Phase.GAME_OVER, deck=[Card(Rank.ACE, Suit.SPADES)])

    from balatro_gym.core_utils.mvp_contract import build_action_mask, build_mvp_action_mask

    assert build_mvp_action_mask(state).sum() == 0
    assert build_action_mask(phase=Phase.GAME_OVER).sum() == 0
