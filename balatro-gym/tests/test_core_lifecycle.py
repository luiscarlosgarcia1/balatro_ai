from __future__ import annotations

from types import SimpleNamespace

from balatro_gym.core.boss_blinds import BossBlindManager, BossBlindType
from balatro_gym.core.cards import Card, Enhancement, Rank, Seal, Suit
from balatro_gym.core.constants import Action, Phase
from balatro_gym.core.jokers import JokerInfo
from balatro_gym.environments.balatro_env_small import BalatroEnv
from balatro_gym.core_utils.round_manager import RoundManager
from balatro_gym.core_utils.state import UnifiedGameState


def test_round_manager_enter_round_eval_stages_cashout_without_paying():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        round=2,
        money=37,
        hands_left=2,
        round_chips_scored=450,
        chips_needed=450,
        vouchers=["Seed Money"],
        jokers=[JokerInfo(84, "To the Moon", 5, "Extra interest")],
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=None)

    outcome = manager.enter_round_eval()

    assert outcome == "round_eval"
    assert state.phase == Phase.ROUND_EVAL
    assert state.money == 37
    assert state.round_eval_cashout == 20
    assert state.round_eval_completed_round == 2
    assert state.round == 3


def test_round_manager_failed_exhausted_blind_enters_game_over_without_cashout():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        round=1,
        money=12,
        hands_left=0,
        round_chips_scored=299,
        chips_needed=300,
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=None)

    outcome = manager.enter_round_eval()
    cash_outcome = manager.cash_out()

    assert outcome == "game_over"
    assert cash_outcome == "noop"
    assert state.phase == Phase.GAME_OVER
    assert state.game_over is True
    assert state.money == 12
    assert state.round_eval_cashout == 0
    assert state.round == 1


def test_round_manager_saved_failed_blind_reaches_round_eval_instead_of_game_over():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        round=1,
        money=12,
        hands_left=0,
        round_chips_scored=299,
        chips_needed=300,
        no_interest=True,
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [{"saved": True}])
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=None)

    outcome = manager.enter_round_eval()

    assert outcome == "round_eval"
    assert state.phase == Phase.ROUND_EVAL
    assert state.game_over is False
    assert state.round_eval_cashout == 0


def test_round_manager_saved_failed_final_boss_does_not_mark_run_as_won():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        ante=8,
        win_ante=8,
        round=3,
        money=12,
        hands_left=0,
        discards_left=0,
        round_chips_scored=299,
        chips_needed=300,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_HOOK,
        no_interest=True,
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [{"saved": True}])
    boss_manager = SimpleNamespace(
        active_blind=SimpleNamespace(money_reward=5),
        disable_boss_blind=lambda *_args, **_kwargs: None,
    )
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=boss_manager)

    outcome = manager.enter_round_eval()

    assert outcome == "round_eval"
    assert state.phase == Phase.ROUND_EVAL
    assert state.game_over is False
    assert state.won is False
    assert state.round_eval_cashout == 0


def test_round_manager_disabled_boss_effect_still_counts_as_boss_round_for_reward_and_win():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        ante=8,
        win_ante=8,
        round=3,
        money=0,
        hands_left=0,
        discards_left=0,
        round_chips_scored=300,
        chips_needed=300,
        boss_blind_active=False,
        active_boss_blind=BossBlindType.THE_CERULEAN,
        no_interest=True,
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=BossBlindManager())

    outcome = manager.enter_round_eval()

    assert outcome == "round_eval"
    assert state.phase == Phase.ROUND_EVAL
    assert state.won is True
    assert state.round_eval_cashout == 8
    assert state.active_boss_blind is None


def test_round_manager_cash_out_pays_staged_eval_and_enters_shop():
    state = UnifiedGameState(
        phase=Phase.ROUND_EVAL,
        round=3,
        money=37,
        hands_left=0,
        discards_left=0,
        round_chips_scored=450,
        round_eval_cashout=20,
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=None)

    outcome = manager.cash_out()

    assert outcome == "shop"
    assert state.phase == Phase.SHOP
    assert state.money == 57
    assert state.round_eval_cashout == 0
    assert state.round_eval_completed_round is None
    assert state.round_chips_scored == 0
    assert state.hands_left == 4
    assert state.discards_left == 3
    assert game.round_hands == 4
    assert game.round_discards == 3


def test_round_manager_no_interest_modifier_disables_interest_row_only():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        round=1,
        money=40,
        hands_left=2,
        round_chips_scored=300,
        chips_needed=300,
        no_interest=True,
        jokers=[JokerInfo(84, "To the Moon", 5, "Extra interest")],
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=None)

    manager.enter_round_eval()

    assert state.phase == Phase.ROUND_EVAL
    assert state.round_eval_cashout == 5
    assert state.money == 40


def test_round_manager_remaining_hand_payout_respects_modifiers():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        round=1,
        money=0,
        hands_left=3,
        money_per_hand=2,
        round_chips_scored=300,
        chips_needed=300,
        no_interest=True,
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=None)

    manager.enter_round_eval()

    assert state.round_eval_cashout == 9

    state = UnifiedGameState(
        phase=Phase.PLAY,
        round=1,
        money=0,
        hands_left=3,
        money_per_hand=2,
        no_extra_hand_money=True,
        round_chips_scored=300,
        chips_needed=300,
        no_interest=True,
    )
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=None)

    manager.enter_round_eval()

    assert state.round_eval_cashout == 3


def test_round_manager_missing_held_snapshot_does_not_pay_replacement_hand_effects():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        round=1,
        money=0,
        hands_left=1,
        no_interest=True,
        round_chips_scored=300,
        chips_needed=300,
        deck=[
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.KING, Suit.HEARTS),
        ],
        hand_indexes=[0, 1],
        last_hand_played="High Card",
        last_held_card_indexes=None,
    )
    state.get_card_state(0).enhancement = Enhancement.GOLD
    state.get_card_state(1).seal = Seal.BLUE
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=None)

    manager.enter_round_eval()

    assert state.money == 0
    assert state.consumables == []
    assert state.round_eval_cashout == 4


def test_round_manager_small_big_boss_progression_and_cashout():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        ante=2,
        round=1,
        money=0,
        hands_left=1,
        round_chips_scored=300,
        chips_needed=300,
    )
    game = SimpleNamespace(round_hands=0, round_discards=0, blind_index=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    boss_blind_manager = SimpleNamespace(active_blind=SimpleNamespace(money_reward=5), deactivate=lambda: None)
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=boss_blind_manager)

    manager.enter_round_eval()
    assert state.round == 2
    assert state.ante == 2
    assert state.round_eval_completed_round == 1
    manager.cash_out()

    state.phase = Phase.PLAY
    state.round_chips_scored = 450
    state.chips_needed = 450
    state.hands_left = 2
    manager.enter_round_eval()
    assert state.round == 3
    assert state.ante == 2
    assert state.round_eval_completed_round == 2
    manager.cash_out()

    state.phase = Phase.PLAY
    state.round_chips_scored = 600
    state.chips_needed = 600
    state.hands_left = 3
    state.boss_blind_active = True
    state.active_boss_blind = BossBlindType.THE_HOOK
    manager.enter_round_eval()
    assert state.round == 1
    assert state.ante == 3
    assert state.round_eval_completed_round == 3
    assert state.boss_blind_active is False


def test_round_manager_final_boss_sets_won_during_round_eval():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        ante=8,
        win_ante=8,
        round=3,
        money=24,
        hands_left=1,
        round_chips_scored=1200,
        chips_needed=1200,
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


def test_round_manager_round_three_clear_without_boss_does_not_set_won():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        ante=8,
        win_ante=8,
        round=3,
        money=24,
        hands_left=1,
        round_chips_scored=600,
        chips_needed=600,
        boss_blind_active=False,
        active_boss_blind=None,
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=None)

    manager.enter_round_eval()

    assert state.phase == Phase.ROUND_EVAL
    assert state.won is False


def test_round_manager_water_boss_cashout_does_not_restore_discard_payout_row():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        round=3,
        money=0,
        hands_left=0,
        discards_left=0,
        money_per_discard=2,
        round_chips_scored=300,
        chips_needed=300,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_WATER,
        no_interest=True,
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    boss_manager = BossBlindManager()
    boss_manager.activate_boss_blind(BossBlindType.THE_WATER, {"discards_left": 3})
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=boss_manager)

    outcome = manager.enter_round_eval()

    assert outcome == "round_eval"
    assert state.phase == Phase.ROUND_EVAL
    assert state.round_eval_cashout == 5
    assert state.game_over is False


def test_round_manager_water_boss_cashout_keeps_exhausted_discards_until_cashout():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        ante=2,
        round=3,
        money=0,
        hands_left=0,
        discards_left=3,
        money_per_discard=2,
        no_interest=True,
        round_chips_scored=600,
        chips_needed=600,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_WATER,
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    boss_blind_manager = BossBlindManager()
    boss_blind_manager.activate_boss_blind(BossBlindType.THE_WATER, state.to_dict())
    state.discards_left = 0
    game.round_discards = 0
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=boss_blind_manager)

    outcome = manager.enter_round_eval()

    assert outcome == "round_eval"
    assert state.phase == Phase.ROUND_EVAL
    assert state.boss_blind_active is False
    assert state.active_boss_blind is None
    assert state.round_eval_cashout == 5
    assert game.round_discards == 0


def test_round_manager_needle_boss_cashout_keeps_exhausted_hands_until_cashout():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        ante=2,
        round=3,
        money=0,
        hands_left=1,
        discards_left=3,
        no_interest=True,
        round_chips_scored=600,
        chips_needed=600,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_NEEDLE,
    )
    game = SimpleNamespace(round_hands=1, round_discards=3)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    boss_blind_manager = BossBlindManager()
    boss_blind_manager.activate_boss_blind(BossBlindType.THE_NEEDLE, state.to_dict())
    state.hands_left = 0
    game.round_hands = 0
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=boss_blind_manager)

    outcome = manager.enter_round_eval()

    assert outcome == "round_eval"
    assert state.phase == Phase.ROUND_EVAL
    assert state.boss_blind_active is False
    assert state.active_boss_blind is None
    assert state.round_eval_cashout == 5
    assert game.round_hands == 0


def test_round_manager_manacle_boss_cashout_restores_hand_size_without_drawing_extra_card():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        ante=2,
        round=3,
        hand_size=7,
        hand_indexes=[0, 1, 2, 3, 4, 5, 6],
        draw_pile_indexes=[7],
        hands_left=1,
        discards_left=3,
        round_chips_scored=600,
        chips_needed=600,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_MANACLE,
    )
    game = SimpleNamespace(round_hands=1, round_discards=3, hand_size=7, hand_indexes=state.hand_indexes.copy(), draw_pile_indexes=state.draw_pile_indexes.copy())
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    boss_blind_manager = BossBlindManager()
    boss_blind_manager.activate_boss_blind(BossBlindType.THE_MANACLE, state.to_dict())
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=boss_blind_manager)

    outcome = manager.enter_round_eval()

    assert outcome == "round_eval"
    assert state.phase == Phase.ROUND_EVAL
    assert state.hand_size == 8
    assert game.hand_size == 8
    assert game.hand_indexes == [0, 1, 2, 3, 4, 5, 6]
    assert game.draw_pile_indexes == [7]


def test_round_manager_wall_and_violet_keep_boss_chip_threshold_through_round_eval_cleanup():
    for blind_type, boss_threshold in (
        (BossBlindType.THE_WALL, 800),
        (BossBlindType.THE_VIOLET, 1200),
    ):
        state = UnifiedGameState(
            phase=Phase.PLAY,
            ante=2,
            round=3,
            chips_needed=boss_threshold,
            hands_left=1,
            round_chips_scored=boss_threshold,
            boss_blind_active=True,
            active_boss_blind=blind_type,
        )
        game = SimpleNamespace(round_hands=1, round_discards=3, blinds=[0, 0, boss_threshold], blind_index=2)
        joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
        boss_blind_manager = BossBlindManager()
        boss_blind_manager.activate_boss_blind(blind_type, state.to_dict())
        boss_blind_manager.blind_state["base_chips"] = boss_threshold // (2 if blind_type == BossBlindType.THE_WALL else 3)
        manager = RoundManager(state, game, joker_effects, boss_blind_manager=boss_blind_manager)

        outcome = manager.enter_round_eval()

        assert outcome == "round_eval"
        assert state.phase == Phase.ROUND_EVAL
        assert state.chips_needed == boss_threshold
        assert game.blinds[2] == boss_threshold


def test_env_ante_8_boss_win_terminates_after_real_cashout():
    env = BalatroEnv(seed=123)
    env.state.phase = Phase.PLAY
    env.state.ante = 8
    env.state.win_ante = 8
    env.state.round = 3
    env.state.money = 24
    env.state.hands_left = 2
    env.state.round_chips_scored = 1200
    env.state.chips_needed = 1200
    env.state.boss_blind_active = True
    env.state.active_boss_blind = BossBlindType.THE_HOOK
    env.boss_blind_manager.active_blind = SimpleNamespace(
        blind_type=BossBlindType.THE_HOOK,
        money_reward=5,
    )
    manager = RoundManager(
        env.state,
        env.game,
        env.joker_effects_engine,
        env.boss_blind_manager,
        env.rng,
    )

    manager.enter_round_eval()
    assert env.state.phase == Phase.ROUND_EVAL
    assert env.state.won is True
    assert env.state.money == 24
    staged_cashout = env.state.round_eval_cashout

    obs, reward, terminated, truncated, info = env.step(Action.SHOP_END)

    assert reward == 0.0
    assert terminated is True
    assert truncated is False
    assert info["action"] == "cash_out"
    assert info["cashout"] == staged_cashout
    assert info["won"] is True
    assert info["round_outcome"] == "won"
    assert env._terminal_outcome == "won"
    assert obs["phase"] == Phase.SHOP
    assert obs["money"] == 24 + staged_cashout
    assert obs["action_mask"].sum() == 0


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
