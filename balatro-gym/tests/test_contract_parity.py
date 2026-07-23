from __future__ import annotations

import numpy as np
import pytest
import sys
import types
from types import MethodType
from types import SimpleNamespace

try:
    import httpx  # noqa: F401
except ModuleNotFoundError:
    httpx = types.ModuleType("httpx")

    class _StubHTTPXError(Exception):
        pass

    httpx.ConnectError = _StubHTTPXError
    httpx.TimeoutException = _StubHTTPXError
    httpx.post = lambda *args, **kwargs: None
    sys.modules["httpx"] = httpx

from balatro_gym.core.constants import Action, Phase
from balatro_gym.core.cards import Card, Enhancement, Edition, Rank, Seal, Suit
from balatro_gym.core.boss_blinds import BossBlindType
from balatro_gym.core.jokers import JokerInfo
from balatro_gym.core_utils.blind_scaling import get_blind_chips
from balatro_gym.core_utils.mvp_contract import (
    SHOP_ITEM_TYPE_IDS,
    build_mvp_action_mask,
    encode_consumable_id,
    encode_pack_item_types,
)
from balatro_gym.core_utils.action_handler import ActionHandler
from balatro_gym.core_utils.observation_builder import ObservationBuilder
from balatro_gym.core_utils.phase_handlers.blind_select import BlindSelectHandler
from balatro_gym.core_utils.phase_handlers.pack_open import PackOpenHandler
from balatro_gym.core_utils.phase_handlers.play_phase import PlayPhaseHandler
from balatro_gym.core_utils.phase_handlers.shop_phase import ShopPhaseHandler
from balatro_gym.core_utils.rng import DeterministicRNG
from balatro_gym.core_utils.state import UnifiedGameState
from balatro_gym.environments.balatro_env_small import BalatroEnv
from balatro_gym.environments.live.balatro_live_env import BalatroLiveEnv
from balatro_gym.scoring.scoring_engine import HandType
try:
    from balatro_gym.training.greedy_expert import direct_play_action_for_combo
except ModuleNotFoundError:
    def direct_play_action_for_combo(_obs, slots):
        from balatro_gym.core.constants import encode_play_subset_action

        return encode_play_subset_action(slots)


def _requires_direct_play_block():
    if not hasattr(Action, "PLAY_SUBSET_BASE") or not hasattr(Action, "PLAY_SUBSET_COUNT"):
        pytest.skip("direct subset-play action block is not exposed in this tree")


def _make_live_env_stub() -> BalatroLiveEnv:
    env = BalatroLiveEnv.__new__(BalatroLiveEnv)
    env._selected = []
    env._gs = {}
    env._total_chips = 0
    env._best_hand_score = 0
    env._hands_played = 0
    env._prev_round_chips = 0
    env._prev_progress = 0.0
    env._step_count = 0
    env.max_episode_steps = 1000
    env.render_mode = None
    env.observation_space = env._create_observation_space()
    return env


def test_reduced_obs_keyset_matches_live_contract():
    sim_space = ObservationBuilder().create_observation_space()
    live_space = _make_live_env_stub()._create_observation_space()

    assert tuple(sim_space.spaces.keys()) == tuple(live_space.spaces.keys())


def test_hand_levels_follow_canonical_order_in_sim_observation():
    builder = ObservationBuilder()
    state = UnifiedGameState()
    insertion_order = [
        HandType.FLUSH,
        HandType.HIGH_CARD,
        HandType.FLUSH_FIVE,
        HandType.ONE_PAIR,
        HandType.STRAIGHT,
        HandType.THREE_KIND,
        HandType.TWO_PAIR,
        HandType.FULL_HOUSE,
        HandType.FOUR_KIND,
        HandType.STRAIGHT_FLUSH,
        HandType.FIVE_KIND,
        HandType.FLUSH_HOUSE,
    ]
    expected = []
    assigned = {}
    for index, hand_type in enumerate(HandType):
        assigned[hand_type] = index + 2
        expected.append(index + 2)

    state.hand_levels = {hand_type: assigned[hand_type] for hand_type in insertion_order}
    obs = builder.build_observation(state)

    assert obs["hand_levels"].tolist() == expected


def test_sim_observation_exposes_visible_state_without_leaking_face_down_identity():
    builder = ObservationBuilder()
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=[
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.KING, Suit.CLUBS),
        ],
        hand_indexes=[0, 1, 2],
        draw_pile_indexes=[2],
        discard_pile_indexes=[0],
        face_down_cards=[1],
        selected_cards=[],
    )
    state.get_card_state(0).enhancement = Enhancement.MULT
    state.get_card_state(0).edition = Edition.FOIL
    state.get_card_state(0).seal = Seal.RED
    state.get_card_state(1).enhancement = Enhancement.GLASS
    state.get_card_state(1).edition = Edition.POLYCHROME
    state.get_card_state(1).seal = Seal.BLUE
    state.get_card_state(2).is_debuffed = True
    state.eternal_jokers = [0]
    state.perishable_counters = {1: 4}
    state.rental_jokers = [2]
    state.boss_blind_rerolls_used_ante = 1
    state.discards_used_this_round = 2

    obs = builder.build_observation(state)

    assert obs["hand"][0] == int(state.deck[0])
    assert obs["hand"][1] == -1
    assert obs["hand"][2] == int(state.deck[2])
    assert obs["face_down_cards"].tolist()[:3] == [0, 1, 0]
    assert obs["deck_id"] == 0
    assert obs["stake_id"] == 0
    assert obs["hand_enhancements"].tolist()[:3] == [Enhancement.MULT.value, 0, 0]
    assert obs["hand_editions"].tolist()[:3] == [Edition.FOIL.value, 0, 0]
    assert obs["hand_seals"].tolist()[:3] == [Seal.RED.value, 0, 0]
    assert obs["hand_debuffed"].tolist()[:3] == [0, 0, 1]
    assert obs["rank_counts"][Rank.TWO.value - 2] == 0
    assert obs["suit_counts"][Suit.HEARTS.value] == 0
    assert obs["discard_pile_cards"][0] == int(state.deck[0]) + 1
    assert obs["draw_pile_counts"][int(state.deck[2])] == 1
    assert obs["joker_eternal"].tolist()[:3] == [1, 0, 0]
    assert obs["joker_perishable"].tolist()[:3] == [0, 1, 0]
    assert obs["joker_perishable_rounds"].tolist()[:3] == [0, 4, 0]
    assert obs["joker_rental"].tolist()[:3] == [0, 0, 1]
    assert obs["boss_blind_rerolls_used_ante"] == 1
    assert obs["discards_used_this_round"] == 2
    assert obs["action_mask"][Action.SELECT_CARD_BASE + 1] == 1
    assert builder.create_observation_space().contains(obs)


def test_joker_ids_match_between_sim_and_live_contract():
    builder = ObservationBuilder()
    state = UnifiedGameState(
        jokers=[
            JokerInfo(1, "Joker", 2, "+4 Mult"),
            JokerInfo(109, "Sock & Buskin", 6, "Retrigger face cards"),
        ]
    )
    sim_obs = builder.build_observation(state)

    live_env = _make_live_env_stub()
    live_env._gs = {
        "state": "SHOP",
        "round": {"chips": 0, "hands_left": 4, "discards_left": 3, "reroll_cost": 5},
        "blinds": {"small": {"score": 300, "status": "DEFEATED"}, "big": {"score": 450, "status": "CURRENT"}, "boss": {"score": 600, "status": "UPCOMING"}},
        "hand": {"cards": []},
        "jokers": {"cards": [{"label": "Joker"}, {"label": "Sock & Buskin"}], "limit": 5},
        "consumables": {"cards": [], "limit": 2},
        "shop": {"cards": []},
        "packs": {"cards": []},
        "pack": {"cards": []},
        "cards": {"count": 52},
        "hands": {},
        "money": 0,
        "ante_num": 1,
        "round_num": 2,
    }
    live_obs = live_env._build_obs()

    assert sim_obs["joker_ids"][:2].tolist() == live_obs["joker_ids"][:2].tolist()


def test_live_observation_redacts_hidden_hand_cards_and_exposes_modifiers():
    env = _make_live_env_stub()
    env._gs = {
        "state": "SELECTING_HAND",
        "round": {"chips": 0, "hands_left": 4, "discards_left": 3, "reroll_cost": 5},
        "blinds": {"small": {"score": 300}, "big": {"score": 450}, "boss": {"score": 600, "name": "The Hook"}},
        "hand": {
            "cards": [
                {
                    "value": {"rank": "A", "suit": "S"},
                    "modifier": {"enhancement": "MULT", "edition": "FOIL", "seal": "RED"},
                    "state": {},
                },
                {
                    "value": {"rank": "2", "suit": "H"},
                    "modifier": {"enhancement": "GLASS", "edition": "POLYCHROME", "seal": "BLUE"},
                    "state": {"hidden": True, "debuff": True},
                },
            ]
        },
        "jokers": {
            "cards": [{"label": "Joker", "modifier": {"edition": "NEGATIVE", "eternal": True}}],
            "limit": 5,
        },
        "consumables": {"cards": [], "limit": 2},
        "shop": {"cards": []},
        "packs": {"cards": []},
        "pack": {"cards": []},
        "cards": {"count": 50, "cards": [{"value": {"rank": "K", "suit": "C"}}]},
        "discard": {"count": 1, "cards": [{"value": {"rank": "Q", "suit": "D"}}]},
        "play": {"count": 1, "cards": [{"value": {"rank": "J", "suit": "C"}}]},
        "hands": {},
        "money": 4,
        "ante_num": 1,
        "round_num": 1,
        "deck": "BLUE",
        "stake": "BLACK",
    }

    obs = env._build_obs()

    assert obs["deck_id"] == 2
    assert obs["stake_id"] == 4
    assert obs["hand"][0] >= 0
    assert obs["hand"][1] == -1
    assert obs["face_down_cards"].tolist()[:2] == [0, 1]
    assert obs["hand_enhancements"].tolist()[:2] == [Enhancement.MULT.value, 0]
    assert obs["hand_editions"].tolist()[:2] == [Edition.FOIL.value, 0]
    assert obs["hand_seals"].tolist()[:2] == [Seal.RED.value, 0]
    assert obs["rank_counts"][0] == 0
    assert obs["suit_counts"][Suit.HEARTS.value] == 0
    assert obs["straight_potential"] == 0.0
    assert obs["discard_pile_cards"][0] > 0
    assert obs["play_area_cards"][0] > 0
    assert obs["joker_editions"][0] == Edition.NEGATIVE.value
    assert obs["joker_eternal"][0] == 1
    assert obs["action_mask"][Action.SELL_JOKER_BASE] == 0
    assert env.observation_space.contains(obs)


def test_pack_observation_keys_and_values_match_between_sim_and_stub_live_contract():
    required_pack_keys = (
        "pack_item_types",
        "pack_item_ids",
        "pack_item_selectable",
        "pack_cards_to_select",
        "pack_choices_remaining",
        "fool_replayable_consumable",
    )

    sim_state = UnifiedGameState(
        phase=Phase.PACK_OPEN,
        consumables=[],
        consumable_slots=1,
        last_tarot_planet_consumable="Mars",
    )
    sim_state.pack_contents = [
        {"consumable": "The Fool"},
        {"consumable": "The Lovers"},
        {"consumable": "Jupiter"},
    ]
    sim_state.pack_selected_indexes = [2]
    sim_state.pack_cards_to_select = 2
    sim_obs = ObservationBuilder().build_observation(sim_state)

    live_env = _make_live_env_stub()
    live_env._gs = {
        "state": "PACK_OPEN",
        "round": {"chips": 0, "hands_left": 4, "discards_left": 3, "reroll_cost": 5},
        "blinds": {
            "small": {"score": 300, "status": "DEFEATED"},
            "big": {"score": 450, "status": "CURRENT"},
            "boss": {"score": 600, "status": "UPCOMING"},
        },
        "hand": {"cards": []},
        "jokers": {"cards": [], "limit": 5},
        "consumables": {"cards": [], "limit": 1},
        "shop": {"cards": []},
        "packs": {"cards": []},
        "pack": {
            "cards": [
                {"label": "The Fool", "selectable": True},
                {"label": "The Lovers", "selectable": False},
                {"label": "Jupiter", "selectable": True},
            ],
            "choices": 2,
            "selected_indexes": [2],
        },
        "cards": {"count": 52},
        "hands": {},
        "money": 0,
        "ante_num": 1,
        "round_num": 2,
        "last_tarot_planet_consumable": "Mars",
    }
    live_obs = live_env._build_obs()

    assert tuple(ObservationBuilder().create_observation_space().spaces.keys()) == tuple(
        live_env._create_observation_space().spaces.keys()
    )
    for key in required_pack_keys:
        assert key in sim_obs
        assert key in live_obs

    assert sim_obs["pack_item_types"][:3].tolist() == live_obs["pack_item_types"][:3].tolist() == (
        encode_pack_item_types(sim_state.pack_contents, slots=5)[:3].tolist()
    )
    assert sim_obs["pack_item_ids"][:3].tolist() == live_obs["pack_item_ids"][:3].tolist() == [
        encode_consumable_id("The Fool"),
        encode_consumable_id("The Lovers"),
        encode_consumable_id("Jupiter"),
    ]
    assert sim_obs["pack_item_selectable"][:3].tolist() == live_obs["pack_item_selectable"][:3].tolist() == [1, 0, 0]
    assert sim_obs["pack_cards_to_select"] == live_obs["pack_cards_to_select"] == 2
    assert sim_obs["pack_choices_remaining"] == live_obs["pack_choices_remaining"] == 1
    assert sim_obs["fool_replayable_consumable"] == live_obs["fool_replayable_consumable"] == encode_consumable_id("Mars")


def test_sell_consumable_is_legal_in_shop_masks_and_handler():
    state = UnifiedGameState(
        phase=Phase.SHOP,
        money=4,
        consumables=["The Fool", "Hex"],
    )
    action_handler = ActionHandler(state, DeterministicRNG(123))
    obs = ObservationBuilder().build_observation(state)

    assert action_handler.is_valid_action(Action.SELL_CONSUMABLE_BASE)
    assert obs["action_mask"][Action.SELL_CONSUMABLE_BASE] == 1

    shop_handler = ShopPhaseHandler(state, DeterministicRNG(123))
    reward, terminated, info = shop_handler.step(Action.SELL_CONSUMABLE_BASE)

    assert reward > 0.0
    assert terminated is False
    assert info["action"] == "sold_consumable"
    assert state.money == 5
    assert state.consumables == ["Hex"]


def test_live_shop_contract_includes_voucher_slots_between_cards_and_packs():
    env = _make_live_env_stub()
    env._gs = {
        "state": "SHOP",
        "round": {"chips": 0, "hands_left": 4, "discards_left": 3, "reroll_cost": 5},
        "blinds": {"small": {"score": 300}, "big": {"score": 450}, "boss": {"score": 600}},
        "hand": {"cards": []},
        "jokers": {"cards": [], "limit": 5},
        "consumables": {"cards": [], "limit": 2},
        "shop": {"cards": [{"set": "JOKER", "label": "Joker", "cost": {"buy": 2}}]},
        "vouchers": {"cards": [{"set": "VOUCHER", "label": "Grabber", "cost": {"buy": 10}}]},
        "packs": {"cards": [{"set": "BOOSTER", "label": "Arcana Pack", "cost": {"buy": 4}}]},
        "pack": {"cards": []},
        "cards": {"count": 52},
        "hands": {},
        "money": 10,
        "ante_num": 1,
        "round_num": 1,
    }

    obs = env._build_obs()

    assert obs["shop_items"][:3].tolist() == [
        SHOP_ITEM_TYPE_IDS["JOKER"],
        SHOP_ITEM_TYPE_IDS["VOUCHER"],
        SHOP_ITEM_TYPE_IDS["BOOSTER"],
    ]
    assert obs["shop_costs"][:3].tolist() == [2, 10, 4]
    assert obs["action_mask"][Action.SHOP_BUY_BASE] == 1
    assert obs["action_mask"][Action.SHOP_BUY_BASE + 1] == 1
    assert obs["action_mask"][Action.SHOP_BUY_BASE + 2] == 1


def test_live_blind_mask_exposes_only_current_selectable_slot_and_skip_legality():
    env = _make_live_env_stub()
    gs = {
        "state": "BLIND_SELECT",
        "round": {},
        "hand": {"cards": []},
        "jokers": {"cards": []},
        "consumables": {"cards": []},
        "shop": {"cards": []},
        "packs": {"cards": []},
        "pack": {"cards": []},
        "money": 0,
        "blinds": {
            "small": {"status": "SKIPPED", "score": 300},
            "big": {"status": "SELECT", "score": 450},
            "boss": {"status": "UPCOMING", "score": 600},
        },
    }

    mask = env._build_action_mask(gs, Phase.BLIND_SELECT)

    assert mask[Action.SELECT_BLIND_BASE + 0] == 0
    assert mask[Action.SELECT_BLIND_BASE + 1] == 1
    assert mask[Action.SELECT_BLIND_BASE + 2] == 0
    assert mask[Action.SKIP_BLIND] == 1

    gs["blinds"]["big"]["status"] = "SKIPPED"
    gs["blinds"]["boss"]["status"] = "SELECT"
    mask = env._build_action_mask(gs, Phase.BLIND_SELECT)

    assert mask[Action.SELECT_BLIND_BASE + 2] == 1
    assert mask[Action.SKIP_BLIND] == 0


def test_play_mask_disallows_playing_more_than_five_selected_cards_and_keeps_hardened_fool_illegal():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        hand_indexes=[0, 1, 2, 3, 4, 5],
        selected_cards=[0, 1, 2, 3, 4, 5],
        discards_left=1,
        consumables=["The Fool"],
    )

    mask = build_mvp_action_mask(state)

    assert mask[Action.PLAY_HAND] == 0
    assert mask[Action.DISCARD] == 1
    assert mask[Action.USE_CONSUMABLE_BASE] == 0


def test_play_mask_allows_backing_out_of_full_selection():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        hand_indexes=[0, 1, 2, 3, 4],
        selected_cards=[0, 1, 2, 3, 4],
        discards_left=0,
    )

    mask = build_mvp_action_mask(state)

    assert mask[Action.PLAY_HAND] == 1
    assert mask[Action.DISCARD] == 0
    assert mask[Action.SELECT_CARD_BASE + 0] == 1
    assert mask[Action.SELECT_CARD_BASE + 4] == 1


def test_play_mask_exposes_direct_subset_play_actions_for_legal_subsets():
    _requires_direct_play_block()

    state = UnifiedGameState(
        phase=Phase.PLAY,
        hand_indexes=[0, 1, 2, 3],
        discards_left=1,
    )
    obs = ObservationBuilder().build_observation(state)

    single_action = direct_play_action_for_combo(obs, (0,))
    pair_action = direct_play_action_for_combo(obs, (1, 3))

    assert single_action is not None
    assert pair_action is not None
    assert obs["action_mask"][single_action] == 1
    assert obs["action_mask"][pair_action] == 1


def test_play_mask_requires_exact_target_counts_for_targeted_consumables():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        deck=[
            Card(Rank.FIVE, Suit.CLUBS),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.ACE, Suit.SPADES),
        ],
        hand_indexes=[0, 1, 2],
        consumables=["The Magician", "Death"],
        selected_cards=[0, 1, 2],
    )

    mask = build_mvp_action_mask(state)

    assert mask[Action.USE_CONSUMABLE_BASE + 0] == 0
    assert mask[Action.USE_CONSUMABLE_BASE + 1] == 0

    state.selected_cards = [0]
    mask = build_mvp_action_mask(state)

    assert mask[Action.USE_CONSUMABLE_BASE + 0] == 1
    assert mask[Action.USE_CONSUMABLE_BASE + 1] == 0

    state.selected_cards = [0, 1]
    mask = build_mvp_action_mask(state)

    assert mask[Action.USE_CONSUMABLE_BASE + 0] == 0
    assert mask[Action.USE_CONSUMABLE_BASE + 1] == 1


def test_face_down_cards_remain_selectable_in_play_handler():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        hand_indexes=[0, 1],
        face_down_cards=[1],
    )
    handler = PlayPhaseHandler(
        state,
        None,
        None,
        None,
        None,
        None,
        None,
        DeterministicRNG(123),
    )

    reward, terminated, info = handler.step(Action.SELECT_CARD_BASE + 1)

    assert reward == 0.0
    assert terminated is False
    assert info["selected_cards"] == [1]
    assert state.selected_cards == [1]


def test_shop_mask_blocks_affordable_buys_when_joker_or_consumable_slots_are_full():
    state = UnifiedGameState(
        phase=Phase.SHOP,
        money=10,
        jokers=[JokerInfo(1, "Joker", 2, "+4 Mult")],
        joker_slots=1,
        consumables=["The Fool", "Hex"],
        consumable_slots=2,
        shop_inventory=[
            {"item_type": "JOKER", "cost": 3},
            {"item_type": "CARD", "cost": 3, "payload": {"consumable": True}},
        ],
    )

    mask = build_mvp_action_mask(state)

    assert mask[Action.SHOP_BUY_BASE + 0] == 0
    assert mask[Action.SHOP_BUY_BASE + 1] == 0
    assert mask[Action.SHOP_END] == 1


def test_mega_pack_selection_updates_mask_until_pack_completes():
    state = UnifiedGameState(hand_levels={HandType.ONE_PAIR: 1})
    shop_handler = SimpleNamespace(shop=None, pack_open_handler=None)
    handler = PackOpenHandler(state, shop_handler)

    open_info = handler.open_pack("Mega Arcana Pack", ["Mercury", "The Lovers", "The Hermit"])

    assert open_info["cards_to_select"] == 2
    assert state.phase == Phase.PACK_OPEN
    assert state.pack_selected_indexes == []

    mask = build_mvp_action_mask(state)
    assert mask[Action.SELECT_FROM_PACK_BASE + 0] == 1
    assert mask[Action.SELECT_FROM_PACK_BASE + 1] == 0
    assert mask[Action.SELECT_FROM_PACK_BASE + 2] == 1
    assert mask[Action.SKIP_PACK] == 1

    reward, terminated, info = handler.step(Action.SELECT_FROM_PACK_BASE + 0)

    assert reward > 0.0
    assert terminated is False
    assert info["cards_selected"] == 1
    assert info["cards_remaining"] == 1
    assert info["consumable_used"] == "Mercury"
    assert state.phase == Phase.PACK_OPEN
    assert state.pack_selected_indexes == [0]
    assert state.hand_levels[HandType.ONE_PAIR] == 2

    mask = build_mvp_action_mask(state)
    assert mask[Action.SELECT_FROM_PACK_BASE + 0] == 0
    assert mask[Action.SELECT_FROM_PACK_BASE + 1] == 0
    assert mask[Action.SELECT_FROM_PACK_BASE + 2] == 1
    assert mask[Action.SKIP_PACK] == 1


def test_live_targeted_pack_subflow_requires_exact_targets_and_confirms_with_targets():
    env = _make_live_env_stub()
    calls: list[tuple[str, dict | None]] = []
    shop_gs = {
        "state": "SHOP",
        "round": {"chips": 0, "hands_left": 4, "discards_left": 3, "reroll_cost": 5},
        "blinds": {
            "small": {"score": 300, "status": "DEFEATED"},
            "big": {"score": 450, "status": "CURRENT"},
            "boss": {"score": 600, "status": "UPCOMING"},
        },
        "hand": {"cards": []},
        "jokers": {"cards": [], "limit": 5},
        "consumables": {"cards": [], "limit": 2},
        "shop": {"cards": []},
        "packs": {"cards": []},
        "pack": {"cards": []},
        "cards": {"count": 52},
        "hands": {},
        "money": 0,
        "ante_num": 1,
        "round_num": 2,
    }

    class StubClient:
        def call(self, action: str, payload: dict | None = None):
            calls.append((action, payload))
            if action == "pack":
                assert payload == {"card": 0, "targets": [1]}
                return shop_gs
            raise AssertionError(f"unexpected live client action: {action}")

    env.client = StubClient()
    env._gs = {
        "state": "PACK_OPEN",
        "round": {"chips": 0, "hands_left": 4, "discards_left": 3, "reroll_cost": 5},
        "blinds": {
            "small": {"score": 300, "status": "DEFEATED"},
            "big": {"score": 450, "status": "CURRENT"},
            "boss": {"score": 600, "status": "UPCOMING"},
        },
        "hand": {
            "cards": [
                {"value": {"rank": "5", "suit": "C"}},
                {"value": {"rank": "K", "suit": "H"}},
                {"value": {"rank": "A", "suit": "S"}},
            ]
        },
        "jokers": {"cards": [], "limit": 5},
        "consumables": {"cards": [], "limit": 2},
        "shop": {"cards": []},
        "packs": {"cards": []},
        "pack": {
            "cards": [
                {"label": "The Lovers", "set": "Tarot", "selectable": True},
                {"label": "Mercury", "set": "Planet", "selectable": True},
            ],
            "choices": 1,
            "selected_indexes": [],
        },
        "cards": {"count": 52},
        "hands": {},
        "money": 0,
        "ante_num": 1,
        "round_num": 2,
    }
    initial_obs = env._build_obs()
    assert initial_obs["action_mask"][Action.SELECT_FROM_PACK_BASE] == 1
    assert initial_obs["action_mask"][Action.SELECT_FROM_PACK_BASE + 1] == 1
    assert initial_obs["action_mask"][Action.SKIP_PACK] == 1

    obs, reward, terminated, truncated, info = env.step(Action.SELECT_FROM_PACK_BASE)

    assert reward == 0.0
    assert terminated is False
    assert truncated is False
    assert info["action"] == "pending_pack_target_selection"
    assert info["card"] == 0
    assert info["targets_required"] == 1
    assert calls == []
    assert env._pending_pack_consumable == "The Lovers"
    assert env._pending_pack_index == 0
    assert obs["pack_item_ids"][:2].tolist() == [
        encode_consumable_id("The Lovers"),
        encode_consumable_id("Mercury"),
    ]
    assert obs["pack_choices_remaining"] == 1
    assert obs["action_mask"][Action.SELECT_FROM_PACK_BASE] == 0
    assert obs["action_mask"][Action.SELECT_FROM_PACK_BASE + 1] == 0
    assert obs["action_mask"][Action.SELECT_CARD_BASE + 0] == 1
    assert obs["action_mask"][Action.SELECT_CARD_BASE + 1] == 1
    assert obs["action_mask"][Action.SELECT_CARD_BASE + 2] == 1
    assert obs["action_mask"][Action.SKIP_PACK] == 1

    obs, reward, terminated, truncated, info = env.step(Action.SELECT_FROM_PACK_BASE)

    assert reward == -1.0
    assert terminated is False
    assert truncated is False
    assert info["error"] == "invalid action"
    assert calls == []

    obs, reward, terminated, truncated, info = env.step(Action.SELECT_CARD_BASE + 1)

    assert reward == 0.0
    assert terminated is False
    assert truncated is False
    assert info["action"] == "toggle_pack_target"
    assert info["selected"] == [1]
    assert info["required_targets"] == 1
    assert obs["pack_choices_remaining"] == 0
    assert obs["action_mask"][Action.SELECT_FROM_PACK_BASE] == 1
    assert obs["action_mask"][Action.SELECT_FROM_PACK_BASE + 1] == 0
    assert obs["action_mask"][Action.SKIP_PACK] == 1

    obs, reward, terminated, truncated, info = env.step(Action.SELECT_FROM_PACK_BASE)

    assert reward == 0.5
    assert terminated is False
    assert truncated is False
    assert info["action"] == "select_pack"
    assert calls == [("pack", {"card": 0, "targets": [1]})]
    assert obs["phase"] == Phase.SHOP
    assert env._pending_pack_consumable is None
    assert env._pending_pack_index is None
    assert env._selected == []


def test_selecting_big_blind_resets_round_state_and_transitions_to_play():
    state = UnifiedGameState(
        ante=2,
        round=2,
        phase=Phase.BLIND_SELECT,
        round_chips_scored=125,
        face_down_cards=[0, 2],
    )
    game = SimpleNamespace(blinds=[0, 0, 0], blind_index=1)
    joker_effects = SimpleNamespace(apply_joker_effect=lambda *_args, **_kwargs: None)
    handler = BlindSelectHandler(
        state,
        game,
        SimpleNamespace(),
        joker_effects,
        DeterministicRNG(123),
    )

    mask = build_mvp_action_mask(state)

    assert mask[Action.SELECT_BLIND_BASE + 0] == 0
    assert mask[Action.SELECT_BLIND_BASE + 1] == 1
    assert mask[Action.SELECT_BLIND_BASE + 2] == 0

    reward, terminated, info = handler.step(Action.SELECT_BLIND_BASE + 1)

    assert reward == 0.0
    assert terminated is False
    assert info["blind_type"] == "big"
    assert info["chips_needed"] == get_blind_chips(2, "big")
    assert info["transition_to"] == "play"
    assert state.round == 2
    assert state.chips_needed == get_blind_chips(2, "big")
    assert state.round_chips_scored == 0
    assert state.face_down_cards == []
    assert state.phase == Phase.PLAY
    assert game.blinds[1] == state.chips_needed


def test_shop_end_returns_to_blind_select_contract_for_next_round():
    state = UnifiedGameState(
        phase=Phase.SHOP,
        round=2,
        selected_cards=[0],
        face_down_cards=[1, 3],
        shop_inventory=[{"item_type": "JOKER", "cost": 3}],
    )
    handler = ShopPhaseHandler(state, DeterministicRNG(123))

    reward, terminated, info = handler.step(Action.SHOP_END)

    assert reward == -0.05
    assert terminated is False
    assert info["action"] == "shop_ended"
    assert state.round == 2
    assert state.phase == Phase.BLIND_SELECT
    assert state.selected_cards == []
    assert state.face_down_cards == []
    assert state.shop_inventory == []
    obs = ObservationBuilder().build_observation(state)
    assert obs["action_mask"][Action.SELECT_BLIND_BASE + 0] == 0
    assert obs["action_mask"][Action.SELECT_BLIND_BASE + 1] == 1
    assert obs["action_mask"][Action.SELECT_BLIND_BASE + 2] == 0
    assert obs["action_mask"][Action.PLAY_HAND] == 0
    assert obs["action_mask"][Action.SKIP_BLIND] == 1


def test_sim_env_preserves_existing_shop_when_pack_closes_back_to_shop():
    env = BalatroEnv.__new__(BalatroEnv)
    env.state = UnifiedGameState(phase=Phase.SHOP)
    calls: list[str] = []
    env.shop_handler = SimpleNamespace(
        invalidate_shop=lambda: calls.append("invalidate"),
        generate_shop=lambda: calls.append("generate"),
    )

    env._handle_phase_transition(Phase.PACK_OPEN)

    assert calls == []


def test_sim_env_regenerates_shop_on_round_transition_into_shop():
    env = BalatroEnv.__new__(BalatroEnv)
    env.state = UnifiedGameState(phase=Phase.SHOP)
    calls: list[str] = []
    env.shop_handler = SimpleNamespace(
        invalidate_shop=lambda: calls.append("invalidate"),
        generate_shop=lambda: calls.append("generate"),
    )

    env._handle_phase_transition(Phase.PLAY)

    assert calls == ["invalidate", "generate"]


def test_env_full_round_flow_keeps_next_blind_pointer_in_sync():
    env = BalatroEnv(seed=123)

    obs, reward, terminated, truncated, info = env.step(Action.SELECT_BLIND_BASE)

    assert reward == 0.0
    assert terminated is False
    assert truncated is False
    assert info["blind_type"] == "small"
    assert obs["phase"] == Phase.PLAY
    assert env.game.blind_index == 0

    def _force_clear_blind(self, selected_cards, hand_type, hand_type_name):
        return self.state.chips_needed, {}

    def _skip_card_effects(self, selected_cards, selected_game_cards, base_score):
        return base_score, 0, [], []

    env.play_handler._score_hand = MethodType(_force_clear_blind, env.play_handler)
    env.play_handler._apply_card_effects = MethodType(_skip_card_effects, env.play_handler)

    obs, reward, terminated, truncated, info = env.step(Action.SELECT_CARD_BASE)

    assert terminated is False
    assert truncated is False
    assert obs["action_mask"][Action.PLAY_HAND] == 1

    obs, reward, terminated, truncated, info = env.step(Action.PLAY_HAND)

    assert terminated is False
    assert truncated is False
    assert info["beat_blind"] is True
    assert info["transition_to"] == "round_eval"
    assert obs["phase"] == Phase.ROUND_EVAL
    assert env.state.round == 2
    assert env.game.blind_index == 1
    assert obs["action_mask"][Action.SHOP_END] == 1

    obs, reward, terminated, truncated, info = env.step(Action.SHOP_END)

    assert terminated is False
    assert truncated is False
    assert info["action"] == "cash_out"
    assert obs["phase"] == Phase.SHOP

    obs, reward, terminated, truncated, info = env.step(Action.SHOP_END)

    assert terminated is False
    assert truncated is False
    assert obs["phase"] == Phase.BLIND_SELECT
    assert env.state.round == 2
    assert env.game.blind_index == 1
    assert obs["action_mask"][Action.SELECT_BLIND_BASE + 1] == 1

    obs, reward, terminated, truncated, info = env.step(Action.SELECT_BLIND_BASE + 1)

    assert reward == 0.0
    assert terminated is False
    assert truncated is False
    assert info["blind_type"] == "big"
    assert obs["phase"] == Phase.PLAY
    assert env.game.blind_index == 1
    assert env.game.blinds[1] == env.state.chips_needed


def test_env_big_blind_clear_to_boss_startup_keeps_pending_boss_and_play_sync(monkeypatch):
    import balatro_gym.core_utils.phase_handlers.blind_select as blind_select_module
    import balatro_gym.core_utils.phase_handlers.shop_phase as shop_phase_module
    import balatro_gym.core_utils.unverified.round_manager as round_manager_module
    from balatro_gym.core.boss_blinds import BossBlindType

    env = BalatroEnv(seed=123)

    def _force_clear_blind(self, selected_cards, hand_type, hand_type_name):
        return self.state.chips_needed, {}

    def _skip_card_effects(self, selected_cards, selected_game_cards, base_score):
        return base_score, 0, [], []

    monkeypatch.setattr(round_manager_module, "select_boss_blind", lambda ante, exclude=None, rng=None: BossBlindType.THE_HOOK)
    monkeypatch.setattr(blind_select_module, "select_boss_blind", lambda ante, exclude=None, rng=None: BossBlindType.THE_HOOK)
    monkeypatch.setattr(shop_phase_module, "select_boss_blind", lambda ante, rng=None: BossBlindType.THE_HOOK)

    env.play_handler._score_hand = MethodType(_force_clear_blind, env.play_handler)
    env.play_handler._apply_card_effects = MethodType(_skip_card_effects, env.play_handler)

    env.step(Action.SELECT_BLIND_BASE)
    env.step(Action.SELECT_CARD_BASE)
    env.step(Action.PLAY_HAND)
    env.step(Action.SHOP_END)
    env.step(Action.SHOP_END)
    env.step(Action.SELECT_BLIND_BASE + 1)
    env.step(Action.SELECT_CARD_BASE)
    obs, reward, terminated, truncated, info = env.step(Action.PLAY_HAND)

    assert reward > 0.0
    assert terminated is False
    assert truncated is False
    assert info["beat_blind"] is True
    assert info["transition_to"] == "round_eval"
    assert obs["phase"] == Phase.ROUND_EVAL
    assert env.state.round == 3
    assert env.state.pending_boss_blind == BossBlindType.THE_HOOK
    assert env.game.blind_index == 2

    obs, reward, terminated, truncated, info = env.step(Action.SHOP_END)

    assert terminated is False
    assert truncated is False
    assert info["action"] == "cash_out"
    assert obs["phase"] == Phase.SHOP

    obs, reward, terminated, truncated, info = env.step(Action.SHOP_END)

    assert reward == -0.05
    assert terminated is False
    assert truncated is False
    assert obs["phase"] == Phase.BLIND_SELECT
    assert env.state.pending_boss_blind == BossBlindType.THE_HOOK
    assert env.game.blind_index == 2
    assert obs["action_mask"][Action.SELECT_BLIND_BASE + 2] == 1

    obs, reward, terminated, truncated, info = env.step(Action.SELECT_BLIND_BASE + 2)

    assert reward > 0.0
    assert terminated is False
    assert truncated is False
    assert info["blind_type"] == "boss"
    assert info["boss_blind"] == "The Hook"
    assert obs["phase"] == Phase.PLAY
    assert env.state.pending_boss_blind is None
    assert env.state.active_boss_blind == BossBlindType.THE_HOOK
    assert env.state.boss_blind_active is True
    assert env.game.blind_index == 2


def test_env_failed_blind_enters_explicit_game_over_phase():
    env = BalatroEnv(seed=123)
    env.step(Action.SELECT_BLIND_BASE)
    env.state.hands_left = 1
    env.game.round_hands = 1

    def _force_miss_blind(self, selected_cards, hand_type, hand_type_name):
        return 0, {}

    env.play_handler._score_hand = MethodType(_force_miss_blind, env.play_handler)

    env.step(Action.SELECT_CARD_BASE)
    obs, reward, terminated, truncated, info = env.step(Action.PLAY_HAND)

    assert terminated is True
    assert truncated is False
    assert info["failed"] is True
    assert info["transition_to"] == "game_over"
    assert obs["phase"] == Phase.GAME_OVER
    assert env.state.game_over is True
    assert env.game.round_hands == env.state.hands_left
    assert env.game.round_discards == env.state.discards_left
    assert env.game.hand_indexes == env.state.hand_indexes
    assert len(env.state.hand_indexes) == 8


def test_env_winning_round_eval_cashout_terminates_episode():
    env = BalatroEnv(seed=123)
    env.state.phase = Phase.ROUND_EVAL
    env.state.won = True
    env.state.round_eval_cashout = 12
    env.state.money = 20

    obs, reward, terminated, truncated, info = env.step(Action.SHOP_END)

    assert reward == 0.0
    assert terminated is True
    assert truncated is False
    assert info["action"] == "cash_out"
    assert info["won"] is True
    assert obs["phase"] == Phase.SHOP
    assert obs["money"] == 32


def test_env_round3_boss_offer_is_seed_stable_across_repeated_episodes():
    offers = []

    for _ in range(4):
        env = BalatroEnv(seed=123)

        def _force_clear_blind(self, selected_cards, hand_type, hand_type_name):
            return self.state.chips_needed, {}

        def _skip_card_effects(self, selected_cards, selected_game_cards, base_score):
            return base_score, 0, [], []

        env.play_handler._score_hand = MethodType(_force_clear_blind, env.play_handler)
        env.play_handler._apply_card_effects = MethodType(_skip_card_effects, env.play_handler)

        env.step(Action.SELECT_BLIND_BASE)
        env.step(Action.SELECT_CARD_BASE)
        env.step(Action.PLAY_HAND)
        env.step(Action.SHOP_END)
        env.step(Action.SHOP_END)
        env.step(Action.SELECT_BLIND_BASE + 1)
        env.step(Action.SELECT_CARD_BASE)
        env.step(Action.PLAY_HAND)
        env.step(Action.SHOP_END)
        env.step(Action.SHOP_END)

        assert env.state.phase == Phase.BLIND_SELECT
        assert env.state.round == 3
        assert env.state.pending_boss_blind is not None
        offers.append(env.state.pending_boss_blind)

    assert len(set(offers)) == 1


def test_env_active_hook_discard_is_seed_stable_across_repeated_episodes():
    outcomes = []

    for _ in range(4):
        env = BalatroEnv(seed=123)
        env.boss_blind_manager.activate_boss_blind(BossBlindType.THE_HOOK, env.state.to_dict())
        env.state.phase = Phase.PLAY
        env.state.boss_blind_active = True
        env.state.active_boss_blind = BossBlindType.THE_HOOK
        env.state.hand_indexes = list(range(8))
        env.game.hand_indexes = env.state.hand_indexes.copy()

        env.play_handler.apply_boss_blind_to_hand()
        outcomes.append(tuple(env.state.hand_indexes))

    assert outcomes == [outcomes[0]] * 4
    assert len(outcomes[0]) == 8


def test_env_active_hook_discard_redraw_is_seed_stable_across_repeated_episodes():
    outcomes = []

    for _ in range(4):
        env = BalatroEnv(seed=123)
        env.boss_blind_manager.activate_boss_blind(BossBlindType.THE_HOOK, env.state.to_dict())
        env.state.phase = Phase.PLAY
        env.state.boss_blind_active = True
        env.state.active_boss_blind = BossBlindType.THE_HOOK
        env.state.hand_indexes = list(range(8))
        env.game.hand_indexes = env.state.hand_indexes.copy()

        env.play_handler.apply_boss_blind_to_hand()
        first_draw_hand = tuple(env.state.hand_indexes)
        first_draw_roll_count = len([entry for entry in env.rng.history if entry[0] == "boss_abilities"])

        _, reward, terminated, truncated, info = env.step(Action.SELECT_CARD_BASE)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0]

        obs, reward, terminated, truncated, info = env.step(Action.DISCARD)

        assert np.isfinite(reward)
        assert terminated is False
        assert truncated is False
        assert obs["phase"] == Phase.PLAY
        assert info["cards_discarded"] == 1
        assert env.state.boss_blind_active is True
        assert env.state.active_boss_blind == BossBlindType.THE_HOOK
        assert env.state.discards_left == 2

        second_draw_hand = tuple(env.state.hand_indexes)
        boss_rolls = [entry for entry in env.rng.history if entry[0] == "boss_abilities"]

        assert len(second_draw_hand) == 8
        assert len(boss_rolls) == first_draw_roll_count
        outcomes.append((first_draw_hand, second_draw_hand, tuple(boss_rolls)))

    assert outcomes == [outcomes[0]] * 4


def test_env_active_hook_mid_round_save_load_preserves_seed_stable_discard_redraw():
    outcomes = []

    for _ in range(4):
        env = BalatroEnv(seed=123)
        env.boss_blind_manager.activate_boss_blind(BossBlindType.THE_HOOK, env.state.to_dict())
        env.state.phase = Phase.PLAY
        env.state.boss_blind_active = True
        env.state.active_boss_blind = BossBlindType.THE_HOOK
        env.state.hand_indexes = list(range(8))
        env.game.hand_indexes = env.state.hand_indexes.copy()

        env.play_handler.apply_boss_blind_to_hand()
        saved = env.save_state()
        saved_hand = tuple(env.state.hand_indexes)

        _, reward, terminated, truncated, info = env.step(Action.SELECT_CARD_BASE)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0]

        obs, reward, terminated, truncated, info = env.step(Action.DISCARD)

        assert np.isfinite(reward)
        assert terminated is False
        assert truncated is False
        assert obs["phase"] == Phase.PLAY
        assert info["cards_discarded"] == 1

        continued_hand = tuple(env.state.hand_indexes)

        restored = BalatroEnv(seed=999)
        restored.load_state(saved)

        assert tuple(restored.state.hand_indexes) == saved_hand
        assert restored.state.boss_blind_active is True
        assert restored.state.active_boss_blind == BossBlindType.THE_HOOK
        assert restored.game.hand_indexes == list(saved_hand)
        assert restored.game.round_discards == restored.state.discards_left

        _, reward, terminated, truncated, info = restored.step(Action.SELECT_CARD_BASE)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0]

        obs, reward, terminated, truncated, info = restored.step(Action.DISCARD)

        assert np.isfinite(reward)
        assert terminated is False
        assert truncated is False
        assert obs["phase"] == Phase.PLAY
        assert info["cards_discarded"] == 1
        assert restored.state.boss_blind_active is True
        assert restored.state.active_boss_blind == BossBlindType.THE_HOOK

        restored_hand = tuple(restored.state.hand_indexes)
        outcomes.append((saved_hand, continued_hand, restored_hand))

        assert restored_hand == continued_hand

    assert outcomes == [outcomes[0]] * 4


def test_env_active_wheel_face_down_draw_is_seed_stable_across_repeated_episodes():
    outcomes = []

    for _ in range(4):
        env = BalatroEnv(seed=123)
        env.state.round = 3
        env.state.phase = Phase.BLIND_SELECT
        env.state.pending_boss_blind = BossBlindType.THE_WHEEL

        obs, reward, terminated, truncated, info = env.step(Action.SELECT_BLIND_BASE + 2)

        assert reward > 0.0
        assert terminated is False
        assert truncated is False
        assert info["blind_type"] == "boss"
        assert info["boss_blind"] == "The Wheel"
        assert obs["phase"] == Phase.PLAY
        assert env.state.active_boss_blind == BossBlindType.THE_WHEEL
        assert env.state.boss_blind_active is True
        outcomes.append(tuple(env.state.face_down_cards))

    assert outcomes == [outcomes[0]] * 4


def test_env_active_wheel_second_same_round_draw_is_seed_stable_across_repeated_episodes():
    outcomes = []

    for _ in range(4):
        env = BalatroEnv(seed=123)
        env.state.round = 3
        env.state.phase = Phase.BLIND_SELECT
        env.state.pending_boss_blind = BossBlindType.THE_WHEEL

        def _low_score(self, selected_cards, hand_type, hand_type_name):
            return 1, {}

        def _skip_card_effects(self, selected_cards, selected_game_cards, base_score):
            return base_score, 0, [], []

        env.play_handler._score_hand = MethodType(_low_score, env.play_handler)
        env.play_handler._apply_card_effects = MethodType(_skip_card_effects, env.play_handler)

        obs, reward, terminated, truncated, info = env.step(Action.SELECT_BLIND_BASE + 2)

        assert reward > 0.0
        assert terminated is False
        assert truncated is False
        assert info["blind_type"] == "boss"
        assert info["boss_blind"] == "The Wheel"
        assert obs["phase"] == Phase.PLAY

        first_draw_face_down = tuple(env.state.face_down_cards)

        _, reward, terminated, truncated, info = env.step(Action.SELECT_CARD_BASE)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0]

        obs, reward, terminated, truncated, info = env.step(Action.PLAY_HAND)

        assert np.isfinite(reward)
        assert terminated is False
        assert truncated is False
        assert obs["phase"] == Phase.PLAY
        assert info["cards_played"] == 1
        assert env.state.boss_blind_active is True
        assert env.state.active_boss_blind == BossBlindType.THE_WHEEL
        assert env.state.hands_left == 3

        second_draw_face_down = tuple(env.state.face_down_cards)
        boss_rolls = [entry for entry in env.rng.history if entry[0] == "boss_abilities"]

        outcomes.append((first_draw_face_down, second_draw_face_down, tuple(boss_rolls)))

    assert outcomes == [outcomes[0]] * 4


def test_env_active_wheel_discard_redraw_is_seed_stable_across_repeated_episodes():
    outcomes = []

    for _ in range(4):
        env = BalatroEnv(seed=123)
        env.state.round = 3
        env.state.phase = Phase.BLIND_SELECT
        env.state.pending_boss_blind = BossBlindType.THE_WHEEL

        obs, reward, terminated, truncated, info = env.step(Action.SELECT_BLIND_BASE + 2)

        assert reward > 0.0
        assert terminated is False
        assert truncated is False
        assert info["blind_type"] == "boss"
        assert info["boss_blind"] == "The Wheel"
        assert obs["phase"] == Phase.PLAY

        first_draw_face_down = tuple(env.state.face_down_cards)
        first_draw_roll_count = len([entry for entry in env.rng.history if entry[0] == "boss_abilities"])

        _, reward, terminated, truncated, info = env.step(Action.SELECT_CARD_BASE)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0]

        obs, reward, terminated, truncated, info = env.step(Action.DISCARD)

        assert np.isfinite(reward)
        assert terminated is False
        assert truncated is False
        assert obs["phase"] == Phase.PLAY
        assert info["cards_discarded"] == 1
        assert env.state.boss_blind_active is True
        assert env.state.active_boss_blind == BossBlindType.THE_WHEEL
        assert env.state.discards_left == 2

        second_draw_face_down = tuple(env.state.face_down_cards)
        boss_rolls = [entry for entry in env.rng.history if entry[0] == "boss_abilities"]

        assert len(boss_rolls) == first_draw_roll_count + len(env.state.hand_indexes)
        outcomes.append((first_draw_face_down, second_draw_face_down, tuple(boss_rolls)))

    assert outcomes == [outcomes[0]] * 4


def test_env_active_wheel_mid_round_save_load_preserves_seed_stable_discard_redraw():
    outcomes = []

    for _ in range(4):
        env = BalatroEnv(seed=123)
        env.state.round = 3
        env.state.phase = Phase.BLIND_SELECT
        env.state.pending_boss_blind = BossBlindType.THE_WHEEL

        obs, reward, terminated, truncated, info = env.step(Action.SELECT_BLIND_BASE + 2)

        assert reward > 0.0
        assert terminated is False
        assert truncated is False
        assert info["blind_type"] == "boss"
        assert info["boss_blind"] == "The Wheel"
        assert obs["phase"] == Phase.PLAY

        saved = env.save_state()
        saved_hand = tuple(env.state.hand_indexes)
        saved_face_down = tuple(env.state.face_down_cards)

        _, reward, terminated, truncated, info = env.step(Action.SELECT_CARD_BASE)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0]

        obs, reward, terminated, truncated, info = env.step(Action.DISCARD)

        assert np.isfinite(reward)
        assert terminated is False
        assert truncated is False
        assert obs["phase"] == Phase.PLAY
        assert info["cards_discarded"] == 1

        continued_hand = tuple(env.state.hand_indexes)
        continued_face_down = tuple(env.state.face_down_cards)

        restored = BalatroEnv(seed=999)
        restored.load_state(saved)

        assert tuple(restored.state.hand_indexes) == saved_hand
        assert tuple(restored.state.face_down_cards) == saved_face_down
        assert restored.state.boss_blind_active is True
        assert restored.state.active_boss_blind == BossBlindType.THE_WHEEL
        assert restored.game.hand_indexes == list(saved_hand)
        assert restored.game.round_discards == restored.state.discards_left

        _, reward, terminated, truncated, info = restored.step(Action.SELECT_CARD_BASE)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0]

        obs, reward, terminated, truncated, info = restored.step(Action.DISCARD)

        assert np.isfinite(reward)
        assert terminated is False
        assert truncated is False
        assert obs["phase"] == Phase.PLAY
        assert info["cards_discarded"] == 1
        assert restored.state.boss_blind_active is True
        assert restored.state.active_boss_blind == BossBlindType.THE_WHEEL

        restored_hand = tuple(restored.state.hand_indexes)
        restored_face_down = tuple(restored.state.face_down_cards)
        outcomes.append(
            (
                saved_hand,
                saved_face_down,
                continued_hand,
                continued_face_down,
                restored_hand,
                restored_face_down,
            )
        )

        assert restored_hand == continued_hand
        assert restored_face_down == continued_face_down

    assert outcomes == [outcomes[0]] * 4


def test_env_active_fish_mid_round_save_load_preserves_face_down_redraw_state():
    outcomes = []

    for _ in range(4):
        env = BalatroEnv(seed=123)
        env.state.round = 3
        env.state.phase = Phase.BLIND_SELECT
        env.state.pending_boss_blind = BossBlindType.THE_FISH

        def _low_score(self, selected_cards, hand_type, hand_type_name):
            return 1, {}

        def _skip_card_effects(self, selected_cards, selected_game_cards, base_score):
            return base_score, 0, [], []

        env.play_handler._score_hand = MethodType(_low_score, env.play_handler)
        env.play_handler._apply_card_effects = MethodType(_skip_card_effects, env.play_handler)

        obs, reward, terminated, truncated, info = env.step(Action.SELECT_BLIND_BASE + 2)

        assert reward > 0.0
        assert terminated is False
        assert truncated is False
        assert info["blind_type"] == "boss"
        assert info["boss_blind"] == "The Fish"
        assert obs["phase"] == Phase.PLAY
        assert env.state.active_boss_blind == BossBlindType.THE_FISH
        assert env.state.boss_blind_active is True
        assert tuple(env.state.face_down_cards) == ()

        _, reward, terminated, truncated, info = env.step(Action.SELECT_CARD_BASE)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0]

        obs, reward, terminated, truncated, info = env.step(Action.PLAY_HAND)

        assert np.isfinite(reward)
        assert terminated is False
        assert truncated is False
        assert obs["phase"] == Phase.PLAY
        assert info["cards_played"] == 1
        assert env.state.hands_left == 3

        saved = env.save_state()
        saved_hand = tuple(env.state.hand_indexes)
        saved_face_down = tuple(env.state.face_down_cards)

        assert saved_face_down == tuple(range(len(saved_hand)))

        _, reward, terminated, truncated, info = env.step(Action.SELECT_CARD_BASE)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0]

        obs, reward, terminated, truncated, info = env.step(Action.DISCARD)

        assert np.isfinite(reward)
        assert terminated is False
        assert truncated is False
        assert obs["phase"] == Phase.PLAY
        assert info["cards_discarded"] == 1
        assert env.state.active_boss_blind == BossBlindType.THE_FISH
        assert env.state.boss_blind_active is True

        continued_hand = tuple(env.state.hand_indexes)
        continued_face_down = tuple(env.state.face_down_cards)

        restored = BalatroEnv(seed=999)
        restored.load_state(saved)

        assert tuple(restored.state.hand_indexes) == saved_hand
        assert tuple(restored.state.face_down_cards) == saved_face_down
        assert restored.state.active_boss_blind == BossBlindType.THE_FISH
        assert restored.state.boss_blind_active is True
        assert restored.game.hand_indexes == list(saved_hand)
        assert restored.game.round_discards == restored.state.discards_left

        _, reward, terminated, truncated, info = restored.step(Action.SELECT_CARD_BASE)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0]

        obs, reward, terminated, truncated, info = restored.step(Action.DISCARD)

        assert reward >= 0.0
        assert terminated is False
        assert truncated is False
        assert obs["phase"] == Phase.PLAY
        assert info["cards_discarded"] == 1
        assert restored.state.active_boss_blind == BossBlindType.THE_FISH
        assert restored.state.boss_blind_active is True

        restored_hand = tuple(restored.state.hand_indexes)
        restored_face_down = tuple(restored.state.face_down_cards)
        outcomes.append(
            (
                saved_hand,
                saved_face_down,
                continued_hand,
                continued_face_down,
                restored_hand,
                restored_face_down,
            )
        )

        assert restored_hand == continued_hand
        assert restored_face_down == continued_face_down

    assert outcomes == [outcomes[0]] * 4


def test_env_active_house_mid_round_save_load_preserves_first_hand_face_down_state():
    outcomes = []

    for _ in range(4):
        env = BalatroEnv(seed=123)
        env.state.round = 3
        env.state.phase = Phase.BLIND_SELECT
        env.state.pending_boss_blind = BossBlindType.THE_HOUSE

        def _low_score(self, selected_cards, hand_type, hand_type_name):
            return 1, {}

        def _skip_card_effects(self, selected_cards, selected_game_cards, base_score):
            return base_score, 0, [], []

        env.play_handler._score_hand = MethodType(_low_score, env.play_handler)
        env.play_handler._apply_card_effects = MethodType(_skip_card_effects, env.play_handler)

        obs, reward, terminated, truncated, info = env.step(Action.SELECT_BLIND_BASE + 2)

        assert reward > 0.0
        assert terminated is False
        assert truncated is False
        assert info["blind_type"] == "boss"
        assert info["boss_blind"] == "The House"
        assert obs["phase"] == Phase.PLAY
        assert env.state.active_boss_blind == BossBlindType.THE_HOUSE
        assert env.state.boss_blind_active is True

        saved_hand = tuple(env.state.hand_indexes)
        saved_face_down = tuple(env.state.face_down_cards)
        saved = env.save_state()

        assert saved_face_down == tuple(range(len(saved_hand)))
        assert env.boss_blind_manager.blind_state["first_hand"] is True

        _, reward, terminated, truncated, info = env.step(Action.SELECT_CARD_BASE)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0]

        obs, reward, terminated, truncated, info = env.step(Action.PLAY_HAND)

        assert np.isfinite(reward)
        assert terminated is False
        assert truncated is False
        assert obs["phase"] == Phase.PLAY
        assert info["cards_played"] == 1
        assert env.state.active_boss_blind == BossBlindType.THE_HOUSE
        assert env.state.boss_blind_active is True
        assert env.boss_blind_manager.blind_state["first_hand"] is False

        continued_hand = tuple(env.state.hand_indexes)
        continued_face_down = tuple(env.state.face_down_cards)

        restored = BalatroEnv(seed=999)
        restored.load_state(saved)

        assert tuple(restored.state.hand_indexes) == saved_hand
        assert tuple(restored.state.face_down_cards) == saved_face_down
        assert restored.state.active_boss_blind == BossBlindType.THE_HOUSE
        assert restored.state.boss_blind_active is True
        assert restored.boss_blind_manager.blind_state["first_hand"] is True
        assert restored.game.hand_indexes == list(saved_hand)
        assert restored.game.round_discards == restored.state.discards_left

        _, reward, terminated, truncated, info = restored.step(Action.SELECT_CARD_BASE)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0]

        obs, reward, terminated, truncated, info = restored.step(Action.PLAY_HAND)

        assert np.isfinite(reward)
        assert terminated is False
        assert truncated is False
        assert obs["phase"] == Phase.PLAY
        assert info["cards_played"] == 1
        assert restored.state.active_boss_blind == BossBlindType.THE_HOUSE
        assert restored.state.boss_blind_active is True
        assert restored.boss_blind_manager.blind_state["first_hand"] is False

        restored_hand = tuple(restored.state.hand_indexes)
        restored_face_down = tuple(restored.state.face_down_cards)
        outcomes.append(
            (
                saved_hand,
                saved_face_down,
                continued_hand,
                continued_face_down,
                restored_hand,
                restored_face_down,
            )
        )

        assert restored_hand == continued_hand
        assert restored_face_down == continued_face_down
        assert restored_face_down == ()

    assert outcomes == [outcomes[0]] * 4


def test_env_active_house_mid_round_save_load_preserves_first_hand_discard_redraw_state():
    outcomes = []

    for _ in range(4):
        env = BalatroEnv(seed=123)
        env.state.round = 3
        env.state.phase = Phase.BLIND_SELECT
        env.state.pending_boss_blind = BossBlindType.THE_HOUSE

        obs, reward, terminated, truncated, info = env.step(Action.SELECT_BLIND_BASE + 2)

        assert reward > 0.0
        assert terminated is False
        assert truncated is False
        assert info["blind_type"] == "boss"
        assert info["boss_blind"] == "The House"
        assert obs["phase"] == Phase.PLAY
        assert env.state.active_boss_blind == BossBlindType.THE_HOUSE
        assert env.state.boss_blind_active is True

        saved_hand = tuple(env.state.hand_indexes)
        saved_face_down = tuple(env.state.face_down_cards)
        saved = env.save_state()

        assert saved_face_down == tuple(range(len(saved_hand)))
        assert env.boss_blind_manager.blind_state["first_hand"] is True

        _, reward, terminated, truncated, info = env.step(Action.SELECT_CARD_BASE)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0]

        obs, reward, terminated, truncated, info = env.step(Action.DISCARD)

        assert reward >= 0.0
        assert terminated is False
        assert truncated is False
        assert obs["phase"] == Phase.PLAY
        assert info["cards_discarded"] == 1
        assert env.state.active_boss_blind == BossBlindType.THE_HOUSE
        assert env.state.boss_blind_active is True
        assert env.boss_blind_manager.blind_state["first_hand"] is True

        continued_hand = tuple(env.state.hand_indexes)
        continued_face_down = tuple(env.state.face_down_cards)

        restored = BalatroEnv(seed=999)
        restored.load_state(saved)

        assert tuple(restored.state.hand_indexes) == saved_hand
        assert tuple(restored.state.face_down_cards) == saved_face_down
        assert restored.state.active_boss_blind == BossBlindType.THE_HOUSE
        assert restored.state.boss_blind_active is True
        assert restored.boss_blind_manager.blind_state["first_hand"] is True
        assert restored.game.hand_indexes == list(saved_hand)
        assert restored.game.round_discards == restored.state.discards_left

        _, reward, terminated, truncated, info = restored.step(Action.SELECT_CARD_BASE)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0]

        obs, reward, terminated, truncated, info = restored.step(Action.DISCARD)

        assert reward >= 0.0
        assert terminated is False
        assert truncated is False
        assert obs["phase"] == Phase.PLAY
        assert info["cards_discarded"] == 1
        assert restored.state.active_boss_blind == BossBlindType.THE_HOUSE
        assert restored.state.boss_blind_active is True
        assert restored.boss_blind_manager.blind_state["first_hand"] is True

        restored_hand = tuple(restored.state.hand_indexes)
        restored_face_down = tuple(restored.state.face_down_cards)
        outcomes.append(
            (
                saved_hand,
                saved_face_down,
                continued_hand,
                continued_face_down,
                restored_hand,
                restored_face_down,
            )
        )

        assert restored_hand == continued_hand
        assert restored_face_down == continued_face_down
        assert restored_face_down == ()

    assert outcomes == [outcomes[0]] * 4


def test_env_active_house_mid_round_save_load_preserves_first_hand_multi_discard_redraw_state():
    outcomes = []

    for _ in range(4):
        env = BalatroEnv(seed=123)
        env.state.round = 3
        env.state.phase = Phase.BLIND_SELECT
        env.state.pending_boss_blind = BossBlindType.THE_HOUSE

        obs, reward, terminated, truncated, info = env.step(Action.SELECT_BLIND_BASE + 2)

        assert reward > 0.0
        assert terminated is False
        assert truncated is False
        assert info["blind_type"] == "boss"
        assert info["boss_blind"] == "The House"
        assert obs["phase"] == Phase.PLAY
        assert env.state.active_boss_blind == BossBlindType.THE_HOUSE
        assert env.state.boss_blind_active is True

        saved_hand = tuple(env.state.hand_indexes)
        saved_face_down = tuple(env.state.face_down_cards)
        saved = env.save_state()

        assert saved_face_down == tuple(range(len(saved_hand)))
        assert env.boss_blind_manager.blind_state["first_hand"] is True

        _, reward, terminated, truncated, info = env.step(Action.SELECT_CARD_BASE)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0]

        _, reward, terminated, truncated, info = env.step(Action.SELECT_CARD_BASE + 1)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0, 1]

        obs, reward, terminated, truncated, info = env.step(Action.DISCARD)

        assert reward >= 0.0
        assert terminated is False
        assert truncated is False
        assert obs["phase"] == Phase.PLAY
        assert info["cards_discarded"] == 2
        assert env.state.active_boss_blind == BossBlindType.THE_HOUSE
        assert env.state.boss_blind_active is True
        assert env.boss_blind_manager.blind_state["first_hand"] is True

        continued_hand = tuple(env.state.hand_indexes)
        continued_face_down = tuple(env.state.face_down_cards)

        restored = BalatroEnv(seed=999)
        restored.load_state(saved)

        assert tuple(restored.state.hand_indexes) == saved_hand
        assert tuple(restored.state.face_down_cards) == saved_face_down
        assert restored.state.active_boss_blind == BossBlindType.THE_HOUSE
        assert restored.state.boss_blind_active is True
        assert restored.boss_blind_manager.blind_state["first_hand"] is True
        assert restored.game.hand_indexes == list(saved_hand)
        assert restored.game.round_discards == restored.state.discards_left

        _, reward, terminated, truncated, info = restored.step(Action.SELECT_CARD_BASE)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0]

        _, reward, terminated, truncated, info = restored.step(Action.SELECT_CARD_BASE + 1)

        assert reward == 0.0
        assert terminated is False
        assert truncated is False
        assert info["selected_cards"] == [0, 1]

        obs, reward, terminated, truncated, info = restored.step(Action.DISCARD)

        assert reward >= 0.0
        assert terminated is False
        assert truncated is False
        assert obs["phase"] == Phase.PLAY
        assert info["cards_discarded"] == 2
        assert restored.state.active_boss_blind == BossBlindType.THE_HOUSE
        assert restored.state.boss_blind_active is True
        assert restored.boss_blind_manager.blind_state["first_hand"] is True

        restored_hand = tuple(restored.state.hand_indexes)
        restored_face_down = tuple(restored.state.face_down_cards)
        outcomes.append(
            (
                saved_hand,
                saved_face_down,
                continued_hand,
                continued_face_down,
                restored_hand,
                restored_face_down,
            )
        )

        assert restored_hand == continued_hand
        assert restored_face_down == continued_face_down
        assert restored_face_down == ()

    assert outcomes == [outcomes[0]] * 4
