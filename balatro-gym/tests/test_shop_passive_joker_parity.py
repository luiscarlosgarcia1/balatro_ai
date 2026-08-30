from types import SimpleNamespace

from balatro_gym.core.constants import Action, Phase
from balatro_gym.core.jokers import JokerInfo
from balatro_gym.core.shop import ItemType, PlayerState, Shop, ShopItem
from balatro_gym.core_utils.phase_handlers.shop_phase import ShopPhaseHandler
from balatro_gym.core_utils.rng import DeterministicRNG
from balatro_gym.core_utils.round_manager import RoundManager
from balatro_gym.core_utils.state import UnifiedGameState
from balatro_gym.scoring.complete_joker_effects import CompleteJokerEffects


def test_credit_card_allows_shop_reroll_into_debt():
    state = UnifiedGameState(
        phase=Phase.SHOP,
        money=0,
        jokers=[JokerInfo(20, "Credit Card", 1, "Debt to -$20")],
    )
    handler = ShopPhaseHandler(state, DeterministicRNG(7))
    handler.generate_shop()

    reward, terminated, info = handler.step(Action.SHOP_REROLL)

    assert reward == 0.0
    assert terminated is False
    assert info["action"] == "reroll"
    assert state.money == -5


def test_buying_chaos_grants_a_free_reroll_for_the_current_shop():
    state = UnifiedGameState(phase=Phase.SHOP, money=10)
    handler = ShopPhaseHandler(state, DeterministicRNG(11))
    handler.generate_shop()
    handler.shop.inventory = [
        ShopItem(
            item_type=ItemType.JOKER,
            name="Chaos the Clown",
            cost=4,
            payload={"joker_id": 30, "joker": JokerInfo(30, "Chaos the Clown", 4, "Free reroll / shop")},
        )
    ]
    state.shop_inventory = handler.shop.inventory.copy()

    reward, terminated, info = handler.step(Action.SHOP_BUY_BASE)

    assert reward == 15.0
    assert terminated is False
    assert info["joker_acquired"] == "Chaos the Clown"
    assert state.money == 6
    assert state.shop_reroll_cost == 0

    reward, terminated, info = handler.step(Action.SHOP_REROLL)

    assert reward == 0.0
    assert terminated is False
    assert info["money_spent"] == 0
    assert state.money == 6
    assert state.shop_reroll_cost == 5


def test_astronomer_makes_planet_cards_and_celestial_packs_free():
    shop = Shop(1, PlayerState(chips=20, jokers=[143]), seed=13)
    shop.inventory = [
        ShopItem(
            item_type=ItemType.CARD,
            name="Mercury",
            cost=3,
            payload={
                "offer_set": "Planet",
                "consumable": "Mercury",
                "consumable_key": "c_mercury",
                "consumable_type": "Planet",
            },
        ),
        ShopItem(
            item_type=ItemType.PACK,
            name="Celestial Pack",
            cost=4,
            payload={
                "pack_key": "p_celestial_normal_1",
                "pack_kind": "Celestial",
                "pack_name": "Celestial Pack",
                "choose": 1,
                "extra": 3,
            },
        ),
        ShopItem(
            item_type=ItemType.CARD,
            name="The Fool",
            cost=3,
            payload={
                "offer_set": "Tarot",
                "consumable": "The Fool",
                "consumable_key": "c_fool",
                "consumable_type": "Tarot",
            },
        ),
    ]

    shop._refresh_inventory_costs()

    assert shop.inventory[0].cost == 0
    assert shop.inventory[1].cost == 0
    assert shop.inventory[2].cost == 3


def test_showman_allows_duplicate_joker_selection_in_shop_pool():
    shop = Shop(1, PlayerState(chips=20, jokers=[121, 20]), seed=17)
    shop.rng.random = lambda: 0.0
    shop.rng.choice = lambda seq: next(entry for entry in seq if getattr(entry, "id", None) == 20)

    joker = shop._choose_joker({"j_20"})

    assert joker.id == 20
    assert joker.name == "Credit Card"


def test_round_eval_grows_egg_and_gift_card_sell_values_for_owned_cards():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        round=1,
        money=0,
        hands_left=1,
        round_chips_scored=300,
        jokers=[
            JokerInfo(46, "Egg", 4, "+$3 sell/round"),
            JokerInfo(79, "Gift Card", 6, "+$1 sell value all"),
        ],
        consumables=["Mercury", "Hex"],
    )
    manager = RoundManager(
        state,
        SimpleNamespace(round_hands=0, round_discards=0, blind_index=0),
        CompleteJokerEffects(),
        boss_blind_manager=None,
    )

    outcome = manager.enter_round_eval()

    assert outcome == "round_eval"
    assert state.get_joker_sell_value(0) == 9
    assert state.get_joker_sell_value(1) == 1
    assert state.get_consumable_sell_value(0) == 2
    assert state.get_consumable_sell_value(1) == 3


def test_debuffed_gift_card_does_not_apply_its_sell_value_bonus():
    state = UnifiedGameState(
        phase=Phase.PLAY,
        round=1,
        money=0,
        hands_left=1,
        round_chips_scored=300,
        jokers=[
            JokerInfo(46, "Egg", 4, "+$3 sell/round"),
            JokerInfo(79, "Gift Card", 6, "+$1 sell value all"),
        ],
        consumables=["Mercury"],
        boss_disabled_joker_indexes=[1],
    )
    manager = RoundManager(
        state,
        SimpleNamespace(round_hands=0, round_discards=0, blind_index=0),
        CompleteJokerEffects(),
        boss_blind_manager=None,
    )

    manager.enter_round_eval()

    assert state.get_joker_sell_value(0) == 8
    assert state.get_joker_sell_value(1) == 0
    assert state.get_consumable_sell_value(0) == 1
