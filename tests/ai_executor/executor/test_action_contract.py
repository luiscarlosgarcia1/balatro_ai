from __future__ import annotations

import json
import unittest

from balatro_ai.action_kind import ActionKind
from balatro_ai.models import GameAction


class ActionKindConstantsTests(unittest.TestCase):
    def test_all_action_kind_constants_are_strings(self) -> None:
        expected = {
            "PLAY_HAND": "play_hand",
            "DISCARD": "discard",
            "BUY_SHOP_ITEM": "buy_shop_item",
            "SELL_JOKER": "sell_joker",
            "REROLL_SHOP": "reroll_shop",
            "LEAVE_SHOP": "leave_shop",
            "SELECT_BLIND": "select_blind",
            "SKIP_BLIND": "skip_blind",
            "PICK_PACK_ITEM": "pick_pack_item",
            "SKIP_PACK": "skip_pack",
            "USE_CONSUMABLE": "use_consumable",
            "REORDER_JOKERS": "reorder_jokers",
            "REORDER_HAND": "reorder_hand",
        }
        for attr, value in expected.items():
            with self.subTest(attr=attr):
                self.assertEqual(getattr(ActionKind, attr), value)


_ALL_KINDS = [
    ActionKind.PLAY_HAND,
    ActionKind.DISCARD,
    ActionKind.BUY_SHOP_ITEM,
    ActionKind.SELL_JOKER,
    ActionKind.REROLL_SHOP,
    ActionKind.LEAVE_SHOP,
    ActionKind.SELECT_BLIND,
    ActionKind.SKIP_BLIND,
    ActionKind.PICK_PACK_ITEM,
    ActionKind.SKIP_PACK,
    ActionKind.USE_CONSUMABLE,
    ActionKind.REORDER_JOKERS,
    ActionKind.REORDER_HAND,
]


class ActionKindJsonRoundTripTests(unittest.TestCase):
    def test_every_action_kind_round_trips_through_json_without_mutation(self) -> None:
        for kind in _ALL_KINDS:
            with self.subTest(kind=kind):
                action = GameAction(kind=kind, target_ids=(1, 2), order=(3,), target="key")
                payload = {"actions": [action.to_action_dict()]}
                serialized = json.dumps(payload)
                recovered = json.loads(serialized)
                action_obj = recovered["actions"][0]
                self.assertEqual(action_obj["kind"], kind)
                self.assertEqual(action_obj["target_ids"], [1, 2])
                self.assertEqual(action_obj["order"], [3])
                self.assertEqual(action_obj["target_key"], "key")


class GameActionSerializationTests(unittest.TestCase):
    def test_to_action_dict_contains_all_four_fields(self) -> None:
        action = GameAction(kind=ActionKind.PLAY_HAND, target_ids=(10, 20), target="unused")
        d = action.to_action_dict()
        self.assertIn("kind", d)
        self.assertIn("target_ids", d)
        self.assertIn("target_key", d)
        self.assertIn("order", d)

    def test_to_action_dict_kind_is_string_value(self) -> None:
        action = GameAction(kind=ActionKind.DISCARD, target_ids=(5,))
        d = action.to_action_dict()
        self.assertEqual(d["kind"], "discard")

    def test_to_action_dict_target_ids_is_list_of_ints(self) -> None:
        action = GameAction(kind=ActionKind.PLAY_HAND, target_ids=(1, 2, 3))
        d = action.to_action_dict()
        self.assertEqual(d["target_ids"], [1, 2, 3])
        self.assertIsInstance(d["target_ids"], list)

    def test_to_action_dict_order_is_list_of_ints(self) -> None:
        action = GameAction(kind=ActionKind.REORDER_HAND, order=(7, 4, 2))
        d = action.to_action_dict()
        self.assertEqual(d["order"], [7, 4, 2])
        self.assertIsInstance(d["order"], list)

    def test_to_action_dict_target_key_is_target_string(self) -> None:
        action = GameAction(kind=ActionKind.SELECT_BLIND, target="small")
        d = action.to_action_dict()
        self.assertEqual(d["target_key"], "small")

    def test_to_action_dict_target_key_is_null_when_target_is_none(self) -> None:
        action = GameAction(kind=ActionKind.PLAY_HAND)
        d = action.to_action_dict()
        self.assertIsNone(d["target_key"])


class GameActionFieldTests(unittest.TestCase):
    def test_target_ids_defaults_to_empty_tuple(self) -> None:
        action = GameAction(kind=ActionKind.PLAY_HAND)
        self.assertEqual(action.target_ids, ())

    def test_target_ids_accepts_tuple_of_ints(self) -> None:
        action = GameAction(kind=ActionKind.PLAY_HAND, target_ids=(1, 2, 3))
        self.assertEqual(action.target_ids, (1, 2, 3))

    def test_order_defaults_to_empty_tuple(self) -> None:
        action = GameAction(kind=ActionKind.REORDER_HAND)
        self.assertEqual(action.order, ())

    def test_order_accepts_tuple_of_ints(self) -> None:
        action = GameAction(kind=ActionKind.REORDER_HAND, order=(5, 3, 1))
        self.assertEqual(action.order, (5, 3, 1))


if __name__ == "__main__":
    unittest.main()
