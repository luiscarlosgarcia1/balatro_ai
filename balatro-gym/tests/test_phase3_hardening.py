from __future__ import annotations

from types import SimpleNamespace

import pytest

from balatro_gym.core.boss_blinds import BossBlindManager, BossBlindType
from balatro_gym.core.cards import Card, Rank, Suit
from balatro_gym.core.consumables import ConsumableManager
from balatro_gym.core.constants import Action, Phase
from balatro_gym.core.jokers import JokerInfo
from balatro_gym.core.shop import (
    ItemType,
    PACK_DEFINITIONS_BY_KEY,
    TAROT_DEFINITIONS,
    VOUCHER_BY_NAME,
    PlayerState,
    Shop,
    ShopItem,
)
from balatro_gym.core_utils.mvp_contract import (
    build_mvp_action_mask,
    encode_consumable_id,
    encode_pack_item_types,
)
from balatro_gym.core_utils.observation_builder import ObservationBuilder
import balatro_gym.core_utils.phase_handlers.blind_select as blind_select_module
from balatro_gym.core_utils.phase_handlers.blind_select import BlindSelectHandler
from balatro_gym.core_utils.phase_handlers.pack_open import PackOpenHandler
from balatro_gym.core_utils.phase_handlers.play_phase import PlayPhaseHandler
from balatro_gym.core_utils.phase_handlers.shop_phase import ShopPhaseHandler
from balatro_gym.core_utils.round_manager import RoundManager
from balatro_gym.core_utils.rng import DeterministicRNG
from balatro_gym.core_utils.state import UnifiedGameState
from balatro_gym.scoring.scoring_engine import HandType


def test_play_reward_uses_preplay_round_score(monkeypatch):
    state = UnifiedGameState(
        phase=Phase.PLAY,
        selected_cards=[0],
        hand_indexes=[0],
        deck=[Card(Rank.ACE, Suit.SPADES)],
        round_chips_scored=120,
        chips_needed=400,
        hands_left=3,
        ante=2,
    )
    game = SimpleNamespace(
        hand_indexes=[0],
        highlighted_indexes=[],
        round_hands=state.hands_left,
        round_discards=state.discards_left,
        round_score=0,
        _classify_hand=lambda cards: (HandType.ONE_PAIR, None),
        highlight_card=lambda idx: None,
        play_hand=lambda: None,
    )
    engine = SimpleNamespace(hand_play_counts={hand_type: 0 for hand_type in HandType})
    handler = PlayPhaseHandler(
        state,
        game,
        engine,
        unified_scorer=SimpleNamespace(),
        joker_effects_engine=SimpleNamespace(),
        consumable_manager=SimpleNamespace(),
        boss_blind_manager=SimpleNamespace(active_blind=None),
        rng=DeterministicRNG(123),
    )

    monkeypatch.setattr(handler, "_get_selected_cards", lambda: ([SimpleNamespace(hand_type=HandType.ONE_PAIR)], [state.deck[0]]))
    monkeypatch.setattr(handler, "_sync_and_highlight_cards", lambda: None)
    monkeypatch.setattr(handler, "_check_boss_blind_can_play", lambda cards, hand_name: True)
    monkeypatch.setattr(handler, "_score_hand", lambda *args, **kwargs: (80, {}))
    monkeypatch.setattr(handler, "_apply_card_effects", lambda *args, **kwargs: (80, 0, [], []))
    monkeypatch.setattr(handler, "_apply_boss_blind_scoring", lambda score, *args, **kwargs: score)
    monkeypatch.setattr(handler, "_consume_played_hand", lambda: None)
    monkeypatch.setattr(handler, "_prepare_next_hand", lambda: None)

    captured: dict[str, int] = {}

    def _capture_reward(**kwargs):
        captured.update(kwargs)
        return {"total_reward": 1.0}

    handler.reward_calculator = SimpleNamespace(calculate_play_reward=_capture_reward)

    reward, terminated, info = handler.step(Action.PLAY_HAND)

    assert reward == 1.0
    assert terminated is False
    assert info["final_score"] == 80
    assert captured["old_score"] == 120
    assert captured["new_score"] == 200


def test_play_mask_keeps_face_down_cards_selectable():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        hand_indexes=list(range(5)),
        face_down_cards=[1, 3],
    )

    mask = build_mvp_action_mask(state)

    assert mask[Action.SELECT_CARD_BASE + 0] == 1
    assert mask[Action.SELECT_CARD_BASE + 1] == 1
    assert mask[Action.SELECT_CARD_BASE + 2] == 1
    assert mask[Action.SELECT_CARD_BASE + 3] == 1


def test_play_handler_allows_selecting_face_down_cards():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        hand_indexes=list(range(4)),
        face_down_cards=[2],
    )
    handler = PlayPhaseHandler.__new__(PlayPhaseHandler)
    handler.state = state

    reward, terminated, info = handler._handle_card_selection(Action.SELECT_CARD_BASE + 2)

    assert reward == pytest.approx(0.0)
    assert terminated is False
    assert info["selected_cards"] == [2]
    assert info["selection_reward_breakdown"]["buildup_bonus"] == pytest.approx(0.05)


def test_play_handler_penalizes_revisiting_selection_states():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        hand_indexes=list(range(4)),
    )
    handler = PlayPhaseHandler.__new__(PlayPhaseHandler)
    handler.state = state

    first_reward, _, first_info = handler._handle_card_selection(Action.SELECT_CARD_BASE + 0)
    second_reward, _, second_info = handler._handle_card_selection(Action.SELECT_CARD_BASE + 0)

    assert first_reward == pytest.approx(0.0)
    assert second_reward == pytest.approx(-0.11)
    assert second_info["selected_cards"] == []
    assert second_info["selection_reward_breakdown"]["repeat_penalty"] == pytest.approx(-0.04)
    assert second_info["selection_reward_breakdown"]["deselect_penalty"] == pytest.approx(-0.02)
    assert first_info["selection_reward_breakdown"]["repeat_penalty"] == pytest.approx(0.0)


def test_play_handler_rewards_committing_constructive_selection_sequence(monkeypatch):
    state = UnifiedGameState(
        phase=Phase.PLAY,
        selected_cards=[],
        hand_indexes=[0],
        deck=[Card(Rank.ACE, Suit.SPADES)],
        round_chips_scored=120,
        chips_needed=500,
        hands_left=3,
    )
    game = SimpleNamespace(
        hand_indexes=[0],
        highlighted_indexes=[],
        round_hands=state.hands_left,
        round_discards=state.discards_left,
        round_score=0,
        _classify_hand=lambda cards: (HandType.ONE_PAIR, None),
        highlight_card=lambda idx: None,
        play_hand=lambda: None,
    )
    engine = SimpleNamespace(hand_play_counts={hand_type: 0 for hand_type in HandType})
    handler = PlayPhaseHandler(
        state,
        game,
        engine,
        unified_scorer=SimpleNamespace(),
        joker_effects_engine=SimpleNamespace(),
        consumable_manager=SimpleNamespace(),
        boss_blind_manager=SimpleNamespace(active_blind=None),
        rng=DeterministicRNG(123),
    )

    monkeypatch.setattr(handler, "_get_selected_cards", lambda: ([SimpleNamespace(hand_type=HandType.ONE_PAIR)], [state.deck[0]]))
    monkeypatch.setattr(handler, "_sync_and_highlight_cards", lambda: None)
    monkeypatch.setattr(handler, "_check_boss_blind_can_play", lambda cards, hand_name: True)
    monkeypatch.setattr(handler, "_score_hand", lambda *args, **kwargs: (80, {}))
    monkeypatch.setattr(handler, "_apply_card_effects", lambda *args, **kwargs: (80, 0, [], []))
    monkeypatch.setattr(handler, "_apply_boss_blind_scoring", lambda score, *args, **kwargs: score)
    monkeypatch.setattr(handler, "_consume_played_hand", lambda: None)
    monkeypatch.setattr(handler, "_prepare_next_hand", lambda: None)
    handler.reward_calculator = SimpleNamespace(calculate_play_reward=lambda **kwargs: {"total_reward": 1.0})

    select_reward, _, select_info = handler.step(Action.SELECT_CARD_BASE)
    reward, terminated, info = handler.step(Action.PLAY_HAND)

    assert select_reward == pytest.approx(0.0)
    assert select_info["selection_reward_breakdown"]["buildup_bonus"] == pytest.approx(0.05)
    assert reward == pytest.approx(1.15)
    assert terminated is False
    assert info["reward_breakdown"]["selection_commit_bonus"] == pytest.approx(0.15)


def test_boss_post_score_state_changes_propagate_back_to_unified_state(monkeypatch):
    state = UnifiedGameState(
        phase=Phase.PLAY,
        selected_cards=[0],
        hand_indexes=[0],
        deck=[Card(Rank.ACE, Suit.SPADES)],
        round_chips_scored=50,
        chips_needed=500,
        hands_left=3,
        money=7,
        boss_blind_active=True,
    )
    game = SimpleNamespace(
        hand_indexes=[0],
        highlighted_indexes=[],
        round_hands=state.hands_left,
        round_discards=state.discards_left,
        round_score=0,
        _classify_hand=lambda cards: (HandType.HIGH_CARD, None),
        highlight_card=lambda idx: None,
        play_hand=lambda: None,
    )
    engine = SimpleNamespace(hand_play_counts={hand_type: 0 for hand_type in HandType})
    boss_blind_manager = SimpleNamespace(
        active_blind=SimpleNamespace(name="Test Boss", description="Regression harness"),
        on_hand_scored=lambda cards, hand_name, game_state: game_state.update(
            {"money": 2, "force_draw_count": 3}
        ),
    )
    handler = PlayPhaseHandler(
        state,
        game,
        engine,
        unified_scorer=SimpleNamespace(),
        joker_effects_engine=SimpleNamespace(),
        consumable_manager=SimpleNamespace(),
        boss_blind_manager=boss_blind_manager,
        rng=DeterministicRNG(123),
    )

    monkeypatch.setattr(
        handler,
        "_get_selected_cards",
        lambda: ([SimpleNamespace(hand_type=HandType.HIGH_CARD)], [state.deck[0]]),
    )
    monkeypatch.setattr(handler, "_sync_and_highlight_cards", lambda: None)
    monkeypatch.setattr(handler, "_check_boss_blind_can_play", lambda cards, hand_name: True)
    monkeypatch.setattr(handler, "_score_hand", lambda *args, **kwargs: (80, {}))
    monkeypatch.setattr(handler, "_apply_card_effects", lambda *args, **kwargs: (80, 0, [], []))
    monkeypatch.setattr(handler, "_apply_boss_blind_scoring", lambda score, *args, **kwargs: score)
    monkeypatch.setattr(handler, "_consume_played_hand", lambda: None)
    monkeypatch.setattr(handler, "_prepare_next_hand", lambda: None)
    handler.reward_calculator = SimpleNamespace(calculate_play_reward=lambda **_: {"total_reward": 0.0})

    reward, terminated, info = handler.step(Action.PLAY_HAND)

    assert reward == 0.0
    assert terminated is False
    assert info["final_score"] == 80
    assert state.money == 2
    assert state.force_draw_count == 3


def test_shop_purchase_syncs_consumables_back_to_state():
    state = UnifiedGameState(phase=Phase.SHOP, money=10, consumables=[])
    handler = ShopPhaseHandler(state, DeterministicRNG(123))

    item = ShopItem(
        item_type=ItemType.CARD,
        name="The Fool",
        cost=3,
        payload={"offer_set": "Tarot", "consumable": "The Fool"},
    )
    player = PlayerState(chips=10, consumables=[])

    class FakeShop:
        def __init__(self):
            self.inventory = [item]
            self.player = player
            self.reroll_cost = 5

        def step(self, action):
            self.player.chips -= item.cost
            self.player.consumables.append("The Fool")
            self.inventory = []
            return 0.0, False, {"card_added": item.payload, "consumable_added": "The Fool"}

    handler.shop = FakeShop()

    reward, terminated, info = handler.step(Action.SHOP_BUY_BASE)

    assert reward == 3.0
    assert terminated is False
    assert info["card_added"] is True
    assert state.money == 7
    assert state.consumables == ["The Fool"]
    assert state.shop_inventory == []


def test_shop_purchase_syncs_playing_cards_back_to_state():
    state = UnifiedGameState(phase=Phase.SHOP, money=10, deck=[])
    handler = ShopPhaseHandler(state, DeterministicRNG(123))

    item = ShopItem(
        item_type=ItemType.CARD,
        name="Ace of Spades",
        cost=4,
        payload={"offer_set": "Playing", "card_index": 51},
    )
    player = PlayerState(chips=10, deck=[])

    class FakeShop:
        def __init__(self):
            self.inventory = [item]
            self.player = player
            self.reroll_cost = 5

        def step(self, action):
            self.player.chips -= item.cost
            self.player.deck.append(51)
            self.inventory = []
            return 0.0, False, {"card_added": item.payload}

    handler.shop = FakeShop()

    reward, terminated, info = handler.step(Action.SHOP_BUY_BASE)

    assert reward == 3.0
    assert terminated is False
    assert info["card_added"] is True
    assert state.money == 6
    assert len(state.deck) == 1
    assert state.deck[0].rank == Rank.ACE
    assert state.deck[0].suit == Suit.SPADES


def test_pack_mask_and_handler_reject_unselectable_items():
    state = UnifiedGameState(
        phase=Phase.PACK_OPEN,
        consumables=["The Fool", "Hex"],
        consumable_slots=2,
        jokers=[JokerInfo(1, "Joker", 2, "+4 Mult")],
        joker_slots=1,
    )
    shop_handler = SimpleNamespace(pack_open_handler=None)
    handler = PackOpenHandler(state, shop_handler)
    handler.pack_contents = [
        {"consumable": "The Magician"},
        {"joker": JokerInfo(2, "Greedy Joker", 5, "Test")},
        {"card": Card(Rank.TEN, Suit.HEARTS)},
    ]
    handler.cards_to_select = 1
    handler._sync_pack_state_to_unified_state()

    mask = build_mvp_action_mask(state)

    assert mask[Action.SELECT_FROM_PACK_BASE + 0] == 0
    assert mask[Action.SELECT_FROM_PACK_BASE + 1] == 0
    assert mask[Action.SELECT_FROM_PACK_BASE + 2] == 1

    reward, terminated, info = handler.step(Action.SELECT_FROM_PACK_BASE)

    assert reward == -1.0
    assert terminated is False
    assert info["error"] == "Cannot take selected pack item"
    assert handler.selected_indexes == []


def test_pack_open_uses_explicit_choice_count_from_shop():
    state = UnifiedGameState(phase=Phase.SHOP)
    shop_handler = SimpleNamespace(pack_open_handler=None)
    handler = PackOpenHandler(state, shop_handler)

    info = handler.open_pack(
        "Arcana Pack",
        [{"consumable": "The Fool"}, {"consumable": "Mercury"}],
        cards_to_select=2,
    )

    assert handler.cards_to_select == 2
    assert state.cards_to_select == 2
    assert info["cards_to_select"] == 2


def test_voucher_purchase_applies_persistent_state_effects_and_reroll_cost():
    state = UnifiedGameState(
        phase=Phase.SHOP,
        money=10,
        consumable_slots=2,
        joker_slots=5,
        hand_size=8,
        hands_left=4,
        discards_left=3,
        shop_reroll_cost=5,
        vouchers=[],
    )
    handler = ShopPhaseHandler(state, DeterministicRNG(123))

    item = ShopItem(
        item_type=ItemType.VOUCHER,
        name="Crystal Ball",
        cost=10,
        payload={"voucher": "Crystal Ball", "voucher_key": "v_crystal_ball"},
    )
    player = PlayerState(chips=10, vouchers=[])

    class FakeShop:
        def __init__(self):
            self.inventory = [item]
            self.player = player
            self.reroll_cost = 3

        def _cost_mult(self):
            return 1.0

        def step(self, action):
            self.player.chips -= item.cost
            self.player.vouchers.append("Crystal Ball")
            self.reroll_cost = 3
            self.inventory = []
            return 0.0, False, {"voucher_added": "Crystal Ball"}

    handler.shop = FakeShop()

    reward, terminated, info = handler.step(Action.SHOP_BUY_BASE)

    assert reward == 10.0
    assert terminated is False
    assert state.vouchers == ["Crystal Ball"]
    assert state.consumable_slots == 3
    assert state.shop_reroll_cost == 3
    assert info["voucher_acquired"] == "Crystal Ball"
    assert info["consumable_slots"] == 3
    assert info["shop_reroll_cost"] == 3


def test_voucher_purchase_applies_hand_discard_and_joker_slot_effects():
    state = UnifiedGameState(
        phase=Phase.SHOP,
        money=40,
        hands_left=4,
        discards_left=3,
        joker_slots=5,
        hand_size=8,
        shop_reroll_cost=5,
    )
    handler = ShopPhaseHandler(state, DeterministicRNG(123))

    def _buy_voucher(voucher_name: str):
        item = ShopItem(
            item_type=ItemType.VOUCHER,
            name=voucher_name,
            cost=5,
            payload={"voucher": voucher_name, "voucher_key": voucher_name.lower().replace(" ", "_")},
        )

        class FakeShop:
            def __init__(self):
                self.inventory = [item]
                self.player = PlayerState(chips=state.money, vouchers=state.vouchers.copy())
                self.reroll_cost = 5

            def _cost_mult(self):
                return 1.0

            def step(self, action):
                self.player.chips -= item.cost
                self.player.vouchers.append(voucher_name)
                self.inventory = []
                return 0.0, False, {"voucher_added": voucher_name}

        handler.shop = FakeShop()
        return handler.step(Action.SHOP_BUY_BASE)

    _buy_voucher("Grabber")
    _buy_voucher("Wasteful")
    _buy_voucher("Antimatter")
    reward, terminated, info = _buy_voucher("Paint Brush")

    assert reward == 10.0
    assert terminated is False
    assert state.hands_left == 5
    assert state.discards_left == 4
    assert state.joker_slots == 6
    assert state.hand_size == 9
    assert info["hand_size"] == 9


def test_round_manager_preserves_voucher_hand_and_discard_bonuses():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        round=1,
        vouchers=["Grabber", "Wasteful", "Nacho Tong", "Recyclomancy"],
        hands_left=1,
        discards_left=0,
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=None)

    manager.advance_round()

    assert state.phase == Phase.SHOP
    assert state.hands_left == 6
    assert state.discards_left == 5
    assert game.round_hands == 6
    assert game.round_discards == 5


def test_round_manager_cashout_uses_blind_reward_hands_and_interest():
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

    manager.advance_round()

    assert state.money == 57
    assert state.phase == Phase.SHOP
    assert state.round == 3


def test_round_manager_boss_cashout_uses_boss_reward_and_resets_blind_state():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        ante=2,
        round=3,
        money=24,
        hands_left=1,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_HOOK,
        face_down_cards=[0, 2],
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    boss_blind_manager = SimpleNamespace(active_blind=SimpleNamespace(money_reward=5), deactivate=lambda: None)
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=boss_blind_manager)

    manager.advance_round()

    assert state.money == 34
    assert state.ante == 3
    assert state.round == 1
    assert state.phase == Phase.SHOP
    assert state.boss_blind_active is False
    assert state.active_boss_blind is None
    assert state.face_down_cards == []


def test_round_manager_cashout_includes_supported_joker_rows_and_discard_modifier():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        round=2,
        money=20,
        hands_left=2,
        discards_left=3,
        money_per_discard=2,
        deck=[
            Card(Rank.NINE, Suit.CLUBS),
            Card(Rank.NINE, Suit.HEARTS),
            Card(Rank.ACE, Suit.SPADES),
        ],
        jokers=[
            JokerInfo(90, "Golden Joker", 6, "+$4 each round"),
            JokerInfo(73, "Cloud 9", 7, "$ per 9 in deck"),
            JokerInfo(35, "Delayed Grat.", 4, "$2/discard if none"),
            JokerInfo(139, "Satellite", 6, "$ per Planet used"),
            JokerInfo(74, "Rocket", 6, "$ each round +2 boss"),
        ],
        unique_planet_cards_used=["Mercury", "Mars"],
    )
    state.rocket_payouts = {4: 5}
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=None)

    manager.advance_round()

    assert state.money == 55
    assert state.phase == Phase.SHOP
    assert state.round == 3
    assert state.get_rocket_payout(4) == 5


def test_round_manager_delayed_gratification_requires_no_discards_used():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        round=1,
        money=0,
        hands_left=1,
        discards_left=3,
        discards_used_this_round=1,
        jokers=[JokerInfo(35, "Delayed Grat.", 4, "$2/discard if none")],
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=None)

    manager.advance_round()

    assert state.money == 4


def test_round_manager_boss_clear_increases_future_rocket_payout_after_current_cashout():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        ante=2,
        round=3,
        money=0,
        hands_left=1,
        jokers=[JokerInfo(74, "Rocket", 6, "$ each round +2 boss")],
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_HOOK,
    )
    state.rocket_payouts = {0: 3}
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    boss_blind_manager = SimpleNamespace(active_blind=SimpleNamespace(money_reward=5), deactivate=lambda: None)
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=boss_blind_manager)

    manager.advance_round()

    assert state.money == 9
    assert state.get_rocket_payout(0) == 5


def test_skip_blind_progression_advances_visible_selection_without_changing_ante():
    state = UnifiedGameState(phase=Phase.BLIND_SELECT, ante=2, round=1)
    handler = BlindSelectHandler(
        state,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(apply_joker_effect=lambda *_args, **_kwargs: None),
        DeterministicRNG(123),
    )

    reward, terminated, info = handler.step(Action.SKIP_BLIND)

    assert reward == -5.0
    assert terminated is False
    assert info["new_ante"] == 2
    assert info["new_round"] == 2
    assert state.phase == Phase.BLIND_SELECT
    assert state.ante == 2
    assert state.round == 2

    mask = build_mvp_action_mask(state)
    assert mask[Action.SELECT_BLIND_BASE + 0] == 0
    assert mask[Action.SELECT_BLIND_BASE + 1] == 1
    assert mask[Action.SELECT_BLIND_BASE + 2] == 0
    assert mask[Action.SKIP_BLIND] == 1

    reward, terminated, info = handler.step(Action.SKIP_BLIND)

    assert reward == -5.0
    assert terminated is False
    assert info["new_ante"] == 2
    assert info["new_round"] == 3
    assert state.phase == Phase.BLIND_SELECT
    assert state.round == 3

    mask = build_mvp_action_mask(state)
    assert mask[Action.SELECT_BLIND_BASE + 0] == 0
    assert mask[Action.SELECT_BLIND_BASE + 1] == 0
    assert mask[Action.SELECT_BLIND_BASE + 2] == 1
    assert mask[Action.SKIP_BLIND] == 0


def test_directors_cut_allows_one_boss_reroll_per_ante(monkeypatch):
    state = UnifiedGameState(
        phase=Phase.BLIND_SELECT,
        ante=2,
        round=3,
        money=25,
        vouchers=["Director's Cut"],
        pending_boss_blind=BossBlindType.THE_HOOK,
    )
    handler = BlindSelectHandler(
        state,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(apply_joker_effect=lambda *_args, **_kwargs: None),
        DeterministicRNG(123),
    )

    def _reroll(ante, exclude=None, rng=None):
        assert ante == 2
        assert exclude == [BossBlindType.THE_HOOK]
        return BossBlindType.THE_WALL

    monkeypatch.setattr(blind_select_module, "select_boss_blind", _reroll)

    mask = build_mvp_action_mask(state)
    assert mask[Action.REROLL_BOSS_BLIND] == 1

    reward, terminated, info = handler.step(Action.REROLL_BOSS_BLIND)

    assert reward == 0.0
    assert terminated is False
    assert info["boss_blind"] == "THE_WALL"
    assert state.money == 15
    assert state.pending_boss_blind == BossBlindType.THE_WALL
    assert state.boss_blind_rerolls_used_ante == 1

    mask = build_mvp_action_mask(state)
    assert mask[Action.REROLL_BOSS_BLIND] == 0

    reward, terminated, info = handler.step(Action.REROLL_BOSS_BLIND)

    assert reward == -1.0
    assert terminated is False
    assert info["error"] == "Boss blind reroll unavailable"


def test_retcon_allows_repeated_boss_rerolls(monkeypatch):
    state = UnifiedGameState(
        phase=Phase.BLIND_SELECT,
        ante=2,
        round=3,
        money=35,
        vouchers=["Retcon"],
        pending_boss_blind=BossBlindType.THE_HOOK,
    )
    handler = BlindSelectHandler(
        state,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(apply_joker_effect=lambda *_args, **_kwargs: None),
        DeterministicRNG(123),
    )
    offers = iter([BossBlindType.THE_WALL, BossBlindType.THE_WHEEL])
    excludes: list[list[BossBlindType] | None] = []

    def _reroll(_ante, exclude=None, rng=None):
        excludes.append(exclude)
        return next(offers)

    monkeypatch.setattr(blind_select_module, "select_boss_blind", _reroll)

    reward, terminated, info = handler.step(Action.REROLL_BOSS_BLIND)

    assert reward == 0.0
    assert terminated is False
    assert info["boss_blind"] == "THE_WALL"
    assert state.pending_boss_blind == BossBlindType.THE_WALL
    assert state.money == 25

    mask = build_mvp_action_mask(state)
    assert mask[Action.REROLL_BOSS_BLIND] == 1

    reward, terminated, info = handler.step(Action.REROLL_BOSS_BLIND)

    assert reward == 0.0
    assert terminated is False
    assert info["boss_blind"] == "THE_WHEEL"
    assert state.pending_boss_blind == BossBlindType.THE_WHEEL
    assert state.money == 15
    assert state.boss_blind_rerolls_used_ante == 2
    assert excludes == [
        [BossBlindType.THE_HOOK],
        [BossBlindType.THE_WALL],
    ]


def test_pending_boss_choice_is_observed_and_activated_on_boss_select(monkeypatch):
    state = UnifiedGameState(
        phase=Phase.BLIND_SELECT,
        ante=2,
        round=3,
        pending_boss_blind=BossBlindType.THE_FISH,
    )
    builder = ObservationBuilder()

    obs = builder.build_observation(state)
    assert obs["boss_blind_type"] == BossBlindType.THE_FISH.value

    state.phase = Phase.SHOP
    obs = builder.build_observation(state)
    assert obs["boss_blind_type"] == BossBlindType.THE_FISH.value

    state.phase = Phase.BLIND_SELECT

    monkeypatch.setattr(
        blind_select_module,
        "select_boss_blind",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected fresh boss roll")),
    )

    boss_blind_manager = SimpleNamespace(
        active_blind=SimpleNamespace(name="The Fish", description="Cards drawn face down after each hand played"),
        activate_boss_blind=lambda blind_type, _game_state: {"chip_mult": 1.0, "modifications": {}},
    )
    handler = BlindSelectHandler(
        state,
        SimpleNamespace(),
        boss_blind_manager,
        SimpleNamespace(apply_joker_effect=lambda *_args, **_kwargs: None),
        DeterministicRNG(123),
    )

    reward, terminated, info = handler.step(Action.SELECT_BLIND_BASE + 2)

    assert reward == 14.0
    assert terminated is False
    assert info["boss_blind"] == "The Fish"
    assert state.phase == Phase.PLAY
    assert state.active_boss_blind == BossBlindType.THE_FISH
    assert state.pending_boss_blind is None
    assert state.boss_blind_active is True

    obs = builder.build_observation(state)
    assert obs["boss_blind_type"] == BossBlindType.THE_FISH.value


def test_boss_reroll_state_resets_after_boss_round_advances_ante():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        ante=2,
        round=3,
        money=0,
        boss_blind_active=True,
        active_boss_blind=BossBlindType.THE_HOOK,
        boss_blind_rerolls_used_ante=1,
    )
    game = SimpleNamespace(round_hands=0, round_discards=0)
    joker_effects = SimpleNamespace(end_of_round_effects=lambda _: [])
    boss_blind_manager = SimpleNamespace(active_blind=SimpleNamespace(money_reward=5), deactivate=lambda: None)
    manager = RoundManager(state, game, joker_effects, boss_blind_manager=boss_blind_manager)

    manager.advance_round()

    assert state.ante == 3
    assert state.round == 1
    assert state.phase == Phase.SHOP
    assert state.boss_blind_active is False
    assert state.active_boss_blind is None
    assert state.pending_boss_blind is None
    assert state.boss_blind_rerolls_used_ante == 0


def test_boss_hook_draw_discards_use_seeded_boss_ability_rng():
    hand_cards = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
        Card(Rank.JACK, Suit.CLUBS),
        Card(Rank.TEN, Suit.SPADES),
    ]

    discard_sequences = []
    rng_histories = []
    for _ in range(3):
        rng = DeterministicRNG(321)
        manager = BossBlindManager(rng)
        manager.activate_boss_blind(BossBlindType.THE_HOOK, {})
        effects = manager.on_hand_drawn(hand_cards, {})
        discard_sequences.append(tuple(effects["discarded_cards"]))
        rng_histories.append(rng.history.copy())

    assert discard_sequences == [discard_sequences[0]] * 3
    assert rng_histories[0] == [("boss_abilities", "sample", discard_sequences[0])]


def test_boss_wheel_draw_flips_use_seeded_boss_ability_rng():
    hand_cards = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.DIAMONDS),
        Card(Rank.JACK, Suit.CLUBS),
        Card(Rank.TEN, Suit.SPADES),
        Card(Rank.NINE, Suit.HEARTS),
    ]

    face_down_sequences = []
    for _ in range(3):
        rng = DeterministicRNG(654)
        manager = BossBlindManager(rng)
        manager.activate_boss_blind(BossBlindType.THE_WHEEL, {})
        effects = manager.on_hand_drawn(hand_cards, {})
        face_down_sequences.append(tuple(effects["face_down_cards"]))
        assert [entry[0] for entry in rng.history] == ["boss_abilities"] * len(hand_cards)

    assert face_down_sequences == [face_down_sequences[0]] * 3


def test_pack_mask_updates_after_first_consumable_fills_last_slot():
    state = UnifiedGameState(
        phase=Phase.SHOP,
        consumables=["Hex"],
        consumable_slots=2,
        last_tarot_planet_consumable="Mercury",
    )
    shop_handler = SimpleNamespace(shop=None, pack_open_handler=None)
    handler = PackOpenHandler(state, shop_handler)

    handler.open_pack(
        "Mega Arcana Pack",
        [
            {"consumable": "The Fool"},
            {"consumable": "The Lovers"},
            {"card": Card(Rank.TEN, Suit.HEARTS)},
        ],
        cards_to_select=2,
    )

    reward, terminated, info = handler.step(Action.SELECT_FROM_PACK_BASE + 0)

    assert reward > 0.0
    assert terminated is False
    assert info["cards_selected"] == 1
    assert info["consumable_used"] == "The Fool"
    assert state.consumables == ["Hex", "Mercury"]

    mask = build_mvp_action_mask(state)
    assert mask[Action.SELECT_FROM_PACK_BASE + 0] == 0
    assert mask[Action.SELECT_FROM_PACK_BASE + 1] == 0
    assert mask[Action.SELECT_FROM_PACK_BASE + 2] == 1
    assert mask[Action.SKIP_PACK] == 1

    reward, terminated, info = handler.step(Action.SELECT_FROM_PACK_BASE + 1)

    assert reward == -1.0
    assert terminated is False
    assert info["error"] == "Cannot take selected pack item"
    assert handler.selected_indexes == [0]


def test_pack_planet_consumable_resolves_immediately_instead_of_entering_inventory():
    state = UnifiedGameState(
        phase=Phase.PACK_OPEN,
        hand_levels={HandType.FLUSH: 1},
        consumables=[],
    )
    shop_handler = SimpleNamespace(shop=None, pack_open_handler=None)
    handler = PackOpenHandler(state, shop_handler)
    handler.open_pack("Celestial Pack", [{"consumable": "Jupiter"}], cards_to_select=1)

    reward, terminated, info = handler.step(Action.SELECT_FROM_PACK_BASE)

    assert reward > 0.0
    assert terminated is False
    assert info["consumable_used"] == "Jupiter"
    assert state.phase == Phase.SHOP
    assert state.consumables == []
    assert state.hand_levels[HandType.FLUSH] == 2
    assert state.unique_planet_cards_used == ["Jupiter"]


def test_targeted_pack_consumable_enters_pending_subflow_and_resolves_with_explicit_targets():
    state = UnifiedGameState(
        phase=Phase.PACK_OPEN,
        deck=[
            Card(Rank.FIVE, Suit.CLUBS),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.ACE, Suit.SPADES),
        ],
        hand_indexes=[0, 1, 2],
        consumables=[],
        consumable_slots=2,
    )
    shop_handler = SimpleNamespace(shop=None, pack_open_handler=None)
    handler = PackOpenHandler(state, shop_handler)
    handler.open_pack(
        "Arcana Pack",
        [{"consumable": "The Lovers"}, {"consumable": "Mercury"}],
        cards_to_select=1,
    )

    mask = build_mvp_action_mask(state)

    assert mask[Action.SELECT_FROM_PACK_BASE] == 1
    assert mask[Action.SELECT_FROM_PACK_BASE + 1] == 1
    assert mask[Action.SKIP_PACK] == 1

    reward, terminated, info = handler.step(Action.SELECT_FROM_PACK_BASE)

    assert reward == 0.0
    assert terminated is False
    assert info["action"] == "pending_pack_target_selection"
    assert info["consumable"] == "The Lovers"
    assert info["required_targets"] == 1
    assert state.phase == Phase.PACK_OPEN
    assert state.pending_pack_consumable == "The Lovers"
    assert state.pending_pack_index == 0
    assert state.selected_cards == []
    assert state.pack_selected_indexes == []

    pending_mask = build_mvp_action_mask(state)
    assert pending_mask[Action.SELECT_FROM_PACK_BASE] == 0
    assert pending_mask[Action.SELECT_FROM_PACK_BASE + 1] == 0
    assert pending_mask[Action.SELECT_CARD_BASE + 0] == 1
    assert pending_mask[Action.SELECT_CARD_BASE + 1] == 1
    assert pending_mask[Action.SELECT_CARD_BASE + 2] == 1
    assert pending_mask[Action.SKIP_PACK] == 1

    pending_obs = ObservationBuilder().build_observation(state)
    assert pending_obs["pack_item_ids"][:2].tolist() == [
        encode_consumable_id("The Lovers"),
        encode_consumable_id("Mercury"),
    ]
    assert pending_obs["pack_choices_remaining"] == 1
    assert pending_obs["action_mask"][Action.SELECT_CARD_BASE + 0] == 1
    assert pending_obs["action_mask"][Action.SKIP_PACK] == 1

    reward, terminated, info = handler.step(Action.SELECT_CARD_BASE + 1)

    assert reward == 0.0
    assert terminated is False
    assert info["action"] == "toggled_pack_target"
    assert info["selected_targets"] == [1]
    assert state.selected_cards == [1]

    exact_mask = build_mvp_action_mask(state)
    assert exact_mask[Action.SELECT_FROM_PACK_BASE] == 1
    assert exact_mask[Action.SELECT_FROM_PACK_BASE + 1] == 0
    assert exact_mask[Action.SKIP_PACK] == 1

    reward, terminated, info = handler.step(Action.SELECT_CARD_BASE + 0)

    assert reward == 0.0
    assert terminated is False
    assert info["selected_targets"] == [0, 1]
    assert state.selected_cards == [0, 1]

    over_targeted_mask = build_mvp_action_mask(state)
    assert over_targeted_mask[Action.SELECT_FROM_PACK_BASE] == 0
    assert over_targeted_mask[Action.SELECT_FROM_PACK_BASE + 1] == 0
    assert over_targeted_mask[Action.SKIP_PACK] == 1

    reward, terminated, info = handler.step(Action.SELECT_FROM_PACK_BASE)

    assert reward == -1.0
    assert terminated is False
    assert info["error"] == "Invalid target count for pending pack consumable"
    assert info["required_targets"] == 1
    assert info["selected_targets"] == 2

    reward, terminated, info = handler.step(Action.SELECT_CARD_BASE + 0)

    assert reward == 0.0
    assert terminated is False
    assert info["selected_targets"] == [1]
    assert state.selected_cards == [1]

    confirm_obs = ObservationBuilder().build_observation(state)
    assert confirm_obs["pack_choices_remaining"] == 0
    assert confirm_obs["action_mask"][Action.SELECT_FROM_PACK_BASE] == 1
    assert confirm_obs["action_mask"][Action.SKIP_PACK] == 1

    reward, terminated, info = handler.step(Action.SELECT_FROM_PACK_BASE)

    assert reward > 0.0
    assert terminated is False
    assert info["consumable_used"] == "The Lovers"
    assert state.phase == Phase.SHOP
    assert state.pending_pack_consumable is None
    assert state.pending_pack_index is None
    assert state.selected_cards == []
    assert state.get_card_state(0).enhancement.name != "WILD"
    assert state.get_card_state(1).enhancement.name == "WILD"
    assert state.get_card_state(2).enhancement.name != "WILD"


def test_skip_pack_abandons_pending_targeted_consumable_and_closes_pack():
    state = UnifiedGameState(
        phase=Phase.PACK_OPEN,
        deck=[Card(Rank.FIVE, Suit.CLUBS)],
        hand_indexes=[0],
        consumables=[],
        consumable_slots=2,
    )
    shop_handler = SimpleNamespace(shop=None, pack_open_handler=None)
    handler = PackOpenHandler(state, shop_handler)
    handler.open_pack("Arcana Pack", [{"consumable": "The Lovers"}], cards_to_select=1)

    reward, terminated, info = handler.step(Action.SELECT_FROM_PACK_BASE)

    assert reward == 0.0
    assert terminated is False
    assert info["action"] == "pending_pack_target_selection"
    assert state.pending_pack_consumable == "The Lovers"

    reward, terminated, info = handler.step(Action.SKIP_PACK)

    assert reward == -1.0
    assert terminated is False
    assert info["action"] == "skipped_pack"
    assert info["cards_skipped"] == 1
    assert info["abandoned_pending_consumable"] == "The Lovers"
    assert info["transition_to"] == "shop"
    assert state.phase == Phase.SHOP
    assert state.pending_pack_consumable is None
    assert state.pending_pack_index is None
    assert state.selected_cards == []
    assert state.pack_contents == []


def test_pack_fool_uses_last_tarot_or_planet_memory_instead_of_inventory_contents():
    state = UnifiedGameState(
        phase=Phase.PACK_OPEN,
        consumables=["Hex"],
        consumable_slots=2,
        last_tarot_planet_consumable="Mars",
    )
    shop_handler = SimpleNamespace(shop=None, pack_open_handler=None)
    handler = PackOpenHandler(state, shop_handler)
    handler.open_pack("Arcana Pack", [{"consumable": "The Fool"}], cards_to_select=1)

    mask = build_mvp_action_mask(state)
    assert mask[Action.SELECT_FROM_PACK_BASE] == 1

    reward, terminated, info = handler.step(Action.SELECT_FROM_PACK_BASE)

    assert reward > 0.0
    assert terminated is False
    assert info["consumable_used"] == "The Fool"
    assert state.consumables == ["Hex", "Mars"]
    assert state.last_tarot_planet_consumable == "The Fool"


def test_sim_observation_exposes_pack_slot_identity_selectability_and_fool_memory():
    state = UnifiedGameState(
        phase=Phase.PACK_OPEN,
        consumables=[],
        consumable_slots=1,
        last_tarot_planet_consumable="Mars",
    )
    state.pack_contents = [
        {"consumable": "The Fool"},
        {"consumable": "The Lovers"},
        {"consumable": "Jupiter"},
    ]
    state.pack_selected_indexes = [2]
    state.pack_cards_to_select = 2

    obs = ObservationBuilder().build_observation(state)

    assert obs["pack_item_types"][:3].tolist() == encode_pack_item_types(state.pack_contents, slots=5)[:3].tolist()
    assert obs["pack_item_ids"][:3].tolist() == [
        encode_consumable_id("The Fool"),
        encode_consumable_id("The Lovers"),
        encode_consumable_id("Jupiter"),
    ]
    assert obs["pack_item_selectable"][:3].tolist() == [1, 0, 0]
    assert obs["pack_cards_to_select"] == 2
    assert obs["pack_choices_remaining"] == 1
    assert obs["fool_replayable_consumable"] == encode_consumable_id("Mars")


def test_play_mask_blocks_fool_without_recreatable_memory_or_capacity():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        consumables=["The Fool"],
        consumable_slots=1,
        last_tarot_planet_consumable="Mercury",
    )

    mask = build_mvp_action_mask(state)

    assert mask[Action.USE_CONSUMABLE_BASE] == 0

    state.last_tarot_planet_consumable = None
    state.consumable_slots = 2

    mask = build_mvp_action_mask(state)

    assert mask[Action.USE_CONSUMABLE_BASE] == 0

    state.last_tarot_planet_consumable = "The Fool"

    mask = build_mvp_action_mask(state)

    assert mask[Action.USE_CONSUMABLE_BASE] == 0


def test_play_mask_requires_selected_targets_for_single_target_consumables():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=[Card(Rank.FIVE, Suit.CLUBS)],
        hand_indexes=[0, 1, 2],
        consumables=["The Magician", "Mercury"],
        selected_cards=[],
    )
    state.deck = [
        Card(Rank.FIVE, Suit.CLUBS),
        Card(Rank.SEVEN, Suit.HEARTS),
        Card(Rank.KING, Suit.SPADES),
    ]

    mask = build_mvp_action_mask(state)

    assert mask[Action.USE_CONSUMABLE_BASE + 0] == 0
    assert mask[Action.USE_CONSUMABLE_BASE + 1] == 1

    state.selected_cards = [0]
    mask = build_mvp_action_mask(state)

    assert mask[Action.USE_CONSUMABLE_BASE + 0] == 1

    state.selected_cards = [0, 1, 2]
    mask = build_mvp_action_mask(state)

    assert mask[Action.USE_CONSUMABLE_BASE + 0] == 0


def test_play_mask_requires_two_selected_targets_for_death():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=[
            Card(Rank.FIVE, Suit.CLUBS),
            Card(Rank.KING, Suit.HEARTS),
        ],
        hand_indexes=[0, 1],
        consumables=["Death"],
        selected_cards=[0],
    )

    mask = build_mvp_action_mask(state)

    assert mask[Action.USE_CONSUMABLE_BASE] == 0

    state.selected_cards = [0, 1]
    mask = build_mvp_action_mask(state)

    assert mask[Action.USE_CONSUMABLE_BASE] == 1

    state.selected_cards = [0, 1, 2]
    state.hand_indexes = [0, 1, 2]
    state.deck.append(Card(Rank.ACE, Suit.SPADES))
    mask = build_mvp_action_mask(state)

    assert mask[Action.USE_CONSUMABLE_BASE] == 0


def test_play_consumable_rejects_overselected_single_target_tarot_before_engine_call():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=[
            Card(Rank.FIVE, Suit.CLUBS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
        ],
        hand_indexes=[0, 1, 2],
        selected_cards=[0, 1, 2],
        consumables=["The Lovers"],
    )
    manager = SimpleNamespace(use_consumable=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("engine should not be called")))
    handler = PlayPhaseHandler(
        state,
        SimpleNamespace(hand_size=state.hand_size),
        SimpleNamespace(apply_planet=lambda *_args, **_kwargs: None),
        unified_scorer=SimpleNamespace(),
        joker_effects_engine=SimpleNamespace(),
        consumable_manager=manager,
        boss_blind_manager=SimpleNamespace(active_blind=None),
        rng=DeterministicRNG(123),
    )

    reward, terminated, info = handler.step(Action.USE_CONSUMABLE_BASE)

    assert reward == -1.0
    assert terminated is False
    assert info["error"] == "Invalid target count for consumable"
    assert info["required_targets"] == 1
    assert info["selected_targets"] == 3


def test_play_consumable_rejects_non_exact_target_count_for_death_before_engine_call():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=[
            Card(Rank.FIVE, Suit.CLUBS),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.ACE, Suit.SPADES),
        ],
        hand_indexes=[0, 1, 2],
        selected_cards=[0],
        consumables=["Death"],
    )
    manager = SimpleNamespace(use_consumable=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("engine should not be called")))
    handler = PlayPhaseHandler(
        state,
        SimpleNamespace(hand_size=state.hand_size),
        SimpleNamespace(apply_planet=lambda *_args, **_kwargs: None),
        unified_scorer=SimpleNamespace(),
        joker_effects_engine=SimpleNamespace(),
        consumable_manager=manager,
        boss_blind_manager=SimpleNamespace(active_blind=None),
        rng=DeterministicRNG(123),
    )

    reward, terminated, info = handler.step(Action.USE_CONSUMABLE_BASE)

    assert reward == -1.0
    assert terminated is False
    assert info["error"] == "Invalid target count for consumable"
    assert info["required_targets"] == 2
    assert info["selected_targets"] == 1


def test_play_consumable_updates_memory_and_persists_rank_suit_mutations():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=[
            Card(Rank.FIVE, Suit.CLUBS),
            Card(Rank.KING, Suit.HEARTS),
        ],
        hand_indexes=[0, 1],
        selected_cards=[0, 1],
        consumables=["Death"],
    )
    game = SimpleNamespace(hand_size=state.hand_size)
    handler = PlayPhaseHandler(
        state,
        game,
        SimpleNamespace(apply_planet=lambda *_args, **_kwargs: None),
        unified_scorer=SimpleNamespace(),
        joker_effects_engine=SimpleNamespace(),
        consumable_manager=ConsumableManager(),
        boss_blind_manager=SimpleNamespace(active_blind=None),
        rng=DeterministicRNG(123),
    )

    reward, terminated, info = handler.step(Action.USE_CONSUMABLE_BASE)

    assert reward > 0.0
    assert terminated is False
    assert info["consumable_used"] == "Death"
    assert state.consumables == []
    assert state.last_tarot_planet_consumable == "Death"
    assert state.deck[0].rank == Rank.KING
    assert state.deck[0].suit == Suit.HEARTS


def test_play_discard_tracks_discards_used_this_round():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=[Card(Rank.FIVE, Suit.CLUBS)],
        hand_indexes=[0],
        selected_cards=[0],
        discards_left=3,
    )
    game = SimpleNamespace(
        hand_indexes=[0],
        highlighted_indexes=[],
        deck=state.deck,
        round_hands=state.hands_left,
        round_discards=state.discards_left,
        discards=state.discards_left,
        highlight_card=lambda idx: None,
    )

    def _discard_hand():
        game.round_discards -= 1

    game.discard_hand = _discard_hand

    handler = PlayPhaseHandler(
        state,
        game,
        SimpleNamespace(),
        unified_scorer=SimpleNamespace(),
        joker_effects_engine=SimpleNamespace(apply_joker_effect=lambda *_args, **_kwargs: None),
        consumable_manager=SimpleNamespace(),
        boss_blind_manager=SimpleNamespace(active_blind=None),
        rng=DeterministicRNG(123),
    )

    reward, terminated, info = handler.step(Action.DISCARD)

    assert reward >= 0.2
    assert terminated is False
    assert info["cards_discarded"] == 1
    assert state.discards_used_this_round == 1


def test_play_planet_consumable_records_unique_planet_usage():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        consumables=["Mercury"],
        hand_levels={HandType.ONE_PAIR: 1},
    )
    game = SimpleNamespace(hand_size=state.hand_size)
    engine = SimpleNamespace(apply_planet=lambda *_args, **_kwargs: None)
    handler = PlayPhaseHandler(
        state,
        game,
        engine,
        unified_scorer=SimpleNamespace(),
        joker_effects_engine=SimpleNamespace(),
        consumable_manager=ConsumableManager(),
        boss_blind_manager=SimpleNamespace(active_blind=None),
        rng=DeterministicRNG(123),
    )

    reward, terminated, info = handler.step(Action.USE_CONSUMABLE_BASE)

    assert reward > 0.0
    assert terminated is False
    assert info["consumable_used"] == "Mercury"
    assert state.consumables == []
    assert state.last_tarot_planet_consumable == "Mercury"
    assert state.unique_planet_cards_used == ["Mercury"]


def test_telescope_forces_first_celestial_pack_choice_to_most_played_planet(monkeypatch):
    shop = Shop(
        1,
        PlayerState(
            chips=20,
            vouchers=["Telescope"],
            most_played_hand="Flush",
        ),
        seed=123,
    )
    monkeypatch.setattr(shop, "_roll_pack_special_consumable", lambda kind: None)

    contents = shop._generate_pack_contents(PACK_DEFINITIONS_BY_KEY["p_celestial_normal_1"])

    assert contents[0]["consumable"] == "Jupiter"
    assert contents[0]["consumable_key"] == "c_jupiter"
    assert all(item["consumable_type"] == "Planet" for item in contents)


def test_buying_clearance_sale_reprices_remaining_shop_inventory():
    state = UnifiedGameState(phase=Phase.SHOP, money=20)
    handler = ShopPhaseHandler(state, DeterministicRNG(123))
    shop = Shop(1, PlayerState(chips=20), seed=321)
    voucher_item = shop._make_voucher_item(VOUCHER_BY_NAME["Clearance Sale"])
    tarot_item = shop._make_consumable_item(TAROT_DEFINITIONS[0])
    shop.inventory = [voucher_item, tarot_item]
    handler.shop = shop
    state.shop_inventory = shop.inventory.copy()
    state.shop_reroll_cost = int(shop.reroll_cost * shop._cost_mult())

    reward, terminated, info = handler.step(Action.SHOP_BUY_BASE + 0)

    assert reward == 10.0
    assert terminated is False
    assert state.money == 10
    assert state.vouchers == ["Clearance Sale"]
    assert info["voucher_acquired"] == "Clearance Sale"
    assert info["voucher_effect"] == "All items in shop are 25% off"
    assert len(state.shop_inventory) == 1
    assert state.shop_inventory[0].name == "The Fool"
    assert state.shop_inventory[0].cost == 2
