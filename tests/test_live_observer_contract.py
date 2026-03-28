from __future__ import annotations

import contextlib
import io
import json
import shutil
import unittest
import zlib
from pathlib import Path
from uuid import uuid4

from obs_test import format_observation
from balatro_ai.observation import BalatroPaths, BalatroSaveObserver
from balatro_ai.policy import DemoPolicy, RuleBasedValidator
from balatro_ai.runtime import EpisodeRunner, LoggingExecutor, ScriptedObserver


CANONICAL_TOP_LEVEL_KEYS = [
    "source",
    "state_id",
    "interaction_phase",
    "blind_key",
    "deck_key",
    "stake_id",
    "score",
    "money",
    "hands_left",
    "discards_left",
    "ante",
    "round_count",
    "joker_slots",
    "joker_count",
    "jokers",
    "consumable_slots",
    "consumables",
    "shop_vouchers",
    "vouchers",
    "skip_tags",
    "tags",
    "shop_items",
    "shop_discounts",
    "reroll_cost",
    "interest",
    "inflation",
    "pack_contents",
    "hand_size",
    "cards_in_hand",
    "selected_cards",
    "highlighted_card",
    "cards_in_deck",
    "blinds",
    "notes",
]

FORBIDDEN_LEGACY_KEYS = {
    "phase",
    "current_score",
    "score_to_beat",
    "blind_name",
    "deck_name",
    "consumables_inventory",
    "consumables_shop",
    "shop_packs",
    "booster_packs",
    "seen_at",
}


class LiveObserverContractTests(unittest.TestCase):
    def test_observe_returns_canonical_ordered_contract_and_defaults(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "shop",
                "state_id": 41,
                "score": {
                    "current": 75,
                    "target": 300,
                },
                "money": 10,
                "hands_left": 4,
                "discards_left": 2,
                "blind_key": "bl_small",
                "deck_key": "b_erratic",
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(list(observation.keys()), CANONICAL_TOP_LEVEL_KEYS)
        self.assertEqual(observation["source"], "live_state_exporter")
        self.assertEqual(observation["state_id"], 41)
        self.assertEqual(observation["interaction_phase"], "shop")
        self.assertEqual(observation["blind_key"], "bl_small")
        self.assertEqual(observation["deck_key"], "b_erratic")
        self.assertEqual(observation["score"], {"current": 75, "target": 300})
        self.assertEqual(observation["jokers"], [])
        self.assertEqual(observation["consumables"], [])
        self.assertEqual(observation["shop_items"], [])
        self.assertEqual(observation["selected_cards"], [])
        self.assertEqual(observation["cards_in_deck"], [])
        self.assertIsNone(observation["pack_contents"])
        self.assertIsNone(observation["highlighted_card"])
        self.assertTrue(FORBIDDEN_LEGACY_KEYS.isdisjoint(observation.keys()))

    def test_observe_populates_canonical_shop_owned_and_card_fields(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "shop",
                "score": {
                    "current": 150,
                    "target": 800,
                },
                "money": 14,
                "hands_left": 4,
                "discards_left": 2,
                "ante": 3,
                "round_count": 17,
                "stake_id": "gold_stake",
                "joker_slots": 5,
                "joker_count": 1,
                "reroll_cost": 5,
                "interest": 3,
                "inflation": 2,
                "hand_size": 8,
                "vouchers": [
                    {
                        "key": "v_clearance_sale",
                    }
                ],
                "shop_vouchers": [
                    {
                        "key": "v_overstock",
                        "cost": 10,
                    }
                ],
                "consumable_slots": 2,
                "consumables": [
                    {
                        "kind": "Tarot",
                        "key": "c_fool",
                        "edition": "Negative",
                        "sell_price": 1,
                        "stickers": ["eternal"],
                    }
                ],
                "shop_items": [
                    {
                        "kind": "Joker",
                        "name": "Vampire",
                        "key": "j_vampire",
                        "cost": 7,
                    },
                    {
                        "kind": "Consumable",
                        "name": "The Sun",
                        "key": "c_sun",
                        "cost": 3,
                    },
                    {
                        "kind": "Pack",
                        "name": "Arcana Pack",
                        "key": "p_arcana_normal_1",
                        "cost": 4,
                    },
                ],
                "tags": [
                    {
                        "key": "tag_top_up",
                    }
                ],
                "skip_tags": [
                    {
                        "slot": "Big",
                        "key": "tag_economy",
                    }
                ],
                "jokers": [
                    {
                        "key": "j_greedy_joker",
                        "rarity": "Common",
                        "edition": "Foil",
                        "debuffed": False,
                        "sell_price": 2,
                        "stickers": ["rental"],
                    }
                ],
                "hand_cards": [
                    {
                        "area": "hand",
                        "code": "S_A",
                        "name": "Ace of Spades",
                        "enhancement": "Bonus",
                        "edition": "Foil",
                    }
                ],
                "blinds": [
                    {
                        "slot": "Small",
                        "key": "bl_small",
                        "state": "Current",
                        "tag_key": "tag_economy",
                    }
                ],
                "notes": ["exporter=live_state_exporter", "screenshot_status=true"],
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(observation["stake_id"], "gold_stake")
        self.assertEqual(observation["joker_slots"], 5)
        self.assertEqual(observation["consumable_slots"], 2)
        self.assertEqual(observation["joker_count"], 1)
        self.assertEqual(observation["hand_size"], 8)
        self.assertEqual(observation["interest"], 3)
        self.assertEqual(observation["inflation"], 2)
        self.assertEqual(observation["reroll_cost"], 5)
        self.assertEqual(observation["vouchers"][0]["key"], "v_clearance_sale")
        self.assertNotIn("name", observation["vouchers"][0])
        self.assertEqual(observation["shop_vouchers"], [{"key": "v_overstock", "cost": 10}])
        self.assertEqual(observation["consumables"][0]["kind"], "tarot")
        self.assertEqual(observation["consumables"][0]["key"], "c_fool")
        self.assertEqual(observation["consumables"][0]["edition"], "negative")
        self.assertEqual(observation["consumables"][0]["sell_price"], 1)
        self.assertEqual(observation["consumables"][0]["stickers"], ["eternal"])
        self.assertNotIn("name", observation["consumables"][0])
        self.assertEqual(observation["jokers"][0]["key"], "j_greedy_joker")
        self.assertEqual(observation["jokers"][0]["rarity"], "common")
        self.assertEqual(observation["jokers"][0]["edition"], "foil")
        self.assertEqual(observation["jokers"][0]["sell_price"], 2)
        self.assertEqual(observation["jokers"][0]["stickers"], ["rental"])
        self.assertNotIn("name", observation["jokers"][0])
        self.assertEqual(observation["tags"][0]["key"], "tag_top_up")
        self.assertNotIn("name", observation["tags"][0])
        self.assertEqual(observation["skip_tags"][0]["key"], "tag_economy")
        self.assertEqual(observation["skip_tags"][0]["slot"], "big")
        self.assertNotIn("name", observation["skip_tags"][0])
        self.assertEqual(observation["blinds"][0]["slot"], "small")
        self.assertEqual(observation["blinds"][0]["state"], "current")
        self.assertEqual(observation["blinds"][0]["tag_key"], "tag_economy")
        self.assertEqual(observation["cards_in_hand"][0]["card_key"], "s_a")
        self.assertEqual(observation["cards_in_hand"][0]["enhancement"], "bonus")
        self.assertEqual(observation["shop_items"][0]["kind"], "joker")
        self.assertEqual(observation["shop_items"][1]["kind"], "consumable")
        self.assertEqual(observation["shop_items"][2]["kind"], "pack")
        self.assertEqual(observation["shop_items"][2]["key"], "p_arcana_normal_1")
        self.assertNotIn({"key": "v_overstock", "cost": 10}, observation["shop_items"])
        self.assertIn("screenshot_status=true", observation["notes"])
        self.assertTrue(any(note.startswith("seen_at=") for note in observation["notes"]))

    def test_observe_accepts_canonical_scalar_live_payload_without_legacy_aliases(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "shop",
                "state_id": 12,
                "blind_key": "bl_small",
                "deck_key": "b_erratic",
                "stake_id": 5,
                "score": {
                    "current": 150,
                    "target": 600,
                },
                "money": 11,
                "hands_left": 3,
                "discards_left": 1,
                "ante": 4,
                "round_count": 18,
                "joker_slots": 5,
                "joker_count": 2,
                "consumable_slots": 2,
                "reroll_cost": 6,
                "interest": 4,
                "inflation": 1,
                "hand_size": 8,
                "notes": ["exporter=live_state_exporter", "screenshot_status=true"],
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(observation["state_id"], 12)
        self.assertEqual(observation["blind_key"], "bl_small")
        self.assertEqual(observation["deck_key"], "b_erratic")
        self.assertEqual(observation["stake_id"], 5)
        self.assertEqual(observation["score"], {"current": 150, "target": 600})
        self.assertEqual(observation["joker_slots"], 5)
        self.assertEqual(observation["joker_count"], 2)
        self.assertEqual(observation["consumable_slots"], 2)
        self.assertEqual(observation["interest"], 4)
        self.assertEqual(observation["inflation"], 1)
        self.assertEqual(observation["hand_size"], 8)
        self.assertIn("screenshot_status=true", observation["notes"])
        self.assertTrue(FORBIDDEN_LEGACY_KEYS.isdisjoint(observation.keys()))

    def test_observe_keeps_live_shop_packs_only_in_shop_items(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "shop",
                "score": {
                    "current": 75,
                    "target": 300,
                },
                "money": 10,
                "hands_left": 4,
                "discards_left": 2,
                "shop_items": [
                    {
                        "kind": "Joker",
                        "name": "Credit Card",
                        "key": "j_credit_card",
                        "cost": 1,
                        "rarity": "Common",
                        "edition": "Foil",
                        "sell_price": 2,
                        "stickers": ["rental"],
                    },
                    {
                        "kind": "Pack",
                        "name": "Buffoon Pack",
                        "key": "p_buffoon_normal_1",
                        "cost": 4,
                        "pack_key": "p_buffoon_normal_1",
                        "pack_kind": "Buffoon",
                    },
                    {
                        "kind": "Consumable",
                        "name": "The Fool",
                        "key": "c_fool",
                        "cost": 3,
                        "consumable_kind": "Tarot",
                        "edition": "Negative",
                        "sell_price": 1,
                        "stickers": ["eternal"],
                        "debuffed": True,
                    },
                ],
                "booster_packs": [
                    {
                        "name": "Ghost Legacy Pack",
                        "key": "p_ghost_legacy_1",
                        "kind": "Ghost",
                        "cost": 99,
                    }
                ],
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(
            observation["shop_items"],
            [
                {
                    "kind": "joker",
                    "name": "Credit Card",
                    "key": "j_credit_card",
                    "cost": 1,
                    "rarity": "common",
                    "edition": "foil",
                    "sell_price": 2,
                    "stickers": ["rental"],
                },
                {
                    "kind": "pack",
                    "name": "Buffoon Pack",
                    "key": "p_buffoon_normal_1",
                    "cost": 4,
                    "pack_key": "p_buffoon_normal_1",
                    "pack_kind": "buffoon",
                },
                {
                    "kind": "consumable",
                    "name": "The Fool",
                    "key": "c_fool",
                    "cost": 3,
                    "consumable_kind": "tarot",
                    "edition": "negative",
                    "sell_price": 1,
                    "stickers": ["eternal"],
                    "debuffed": True,
                },
            ],
        )
        self.assertEqual(observation["shop_items"][0].get("item_kind"), None)
        self.assertNotIn("booster_packs", observation)

    def test_observe_ignores_legacy_shop_packs_input(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "shop",
                "score": {
                    "current": 75,
                    "target": 300,
                },
                "money": 10,
                "hands_left": 4,
                "discards_left": 2,
                "shop_items": [
                    {
                        "kind": "Pack",
                        "name": "Jumbo Standard Pack",
                        "key": "p_standard_jumbo_1",
                        "cost": 6,
                    }
                ],
                "shop_packs": [
                    {
                        "kind": "Booster",
                        "name": "Jumbo Standard Pack",
                        "key": "p_standard_jumbo_1",
                        "cost": 6,
                    },
                    {
                        "kind": "Arcana",
                        "name": "Arcana Pack",
                        "key": "p_arcana_normal_1",
                        "cost": 4,
                    },
                ],
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(
            observation["shop_items"],
            [
                {"kind": "pack", "name": "Jumbo Standard Pack", "key": "p_standard_jumbo_1", "cost": 6}
            ],
        )

    def test_observe_exposes_canonical_shop_discounts_array(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "shop",
                "score": {
                    "current": 75,
                    "target": 300,
                },
                "money": 10,
                "hands_left": 4,
                "discards_left": 2,
                "shop_discounts": [
                    {
                        "kind": "discount_percent",
                        "value": 25,
                    },
                    {
                        "kind": "shop_free",
                    },
                ],
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(
            observation["shop_discounts"],
            [
                {"kind": "discount_percent", "value": 25},
                {"kind": "shop_free"},
            ],
        )

    def test_observe_uses_live_interaction_phase_without_legacy_phase_bridge(self) -> None:
        blind_select = self.observe_live_payload(
            {
                "state": {
                    "source": "live_state_exporter",
                    "interaction_phase": "blind_select",
                    "score": {"current": 0, "target": 300},
                    "money": 8,
                    "hands_left": 4,
                    "discards_left": 4,
                }
            }
        )
        play_hand = self.observe_live_payload(
            {
                "state": {
                    "source": "live_state_exporter",
                    "interaction_phase": "play_hand",
                    "score": {"current": 120, "target": 300},
                    "money": 8,
                    "hands_left": 4,
                    "discards_left": 4,
                }
            }
        )
        pack_reward = self.observe_live_payload(
            {
                "state": {
                    "source": "live_state_exporter",
                    "interaction_phase": "pack_reward",
                    "pack_contents": {
                        "open_pack_kind": "tarot",
                    },
                    "score": {"current": 0, "target": 300},
                    "money": 8,
                    "hands_left": 4,
                    "discards_left": 4,
                }
            }
        )

        self.assertEqual(blind_select["interaction_phase"], "blind_select")
        self.assertEqual(play_hand["interaction_phase"], "play_hand")
        self.assertEqual(pack_reward["interaction_phase"], "pack_reward")
        self.assertIsNone(pack_reward["pack_contents"])

    def test_observe_preserves_phase_specific_blind_key_from_live_payload(self) -> None:
        blind_select = self.observe_live_payload(
            {
                "state": {
                    "source": "live_state_exporter",
                    "interaction_phase": "blind_select",
                    "blind_key": "bl_small",
                    "score": {"current": 0, "target": 0},
                    "money": 4,
                    "hands_left": 4,
                    "discards_left": 4,
                    "blinds": [
                        {"slot": "Small", "key": "bl_small", "state": "Select"},
                        {"slot": "Big", "key": "bl_big", "state": "Upcoming"},
                    ],
                }
            }
        )
        play_hand = self.observe_live_payload(
            {
                "state": {
                    "source": "live_state_exporter",
                    "interaction_phase": "play_hand",
                    "blind_key": "bl_big",
                    "score": {"current": 120, "target": 450},
                    "money": 6,
                    "hands_left": 4,
                    "discards_left": 4,
                    "blinds": [
                        {"slot": "Small", "key": "bl_small", "state": "Defeated"},
                        {"slot": "Big", "key": "bl_big", "state": "Current"},
                    ],
                }
            }
        )
        shop = self.observe_live_payload(
            {
                "state": {
                    "source": "live_state_exporter",
                    "interaction_phase": "shop",
                    "blind_key": "bl_big",
                    "score": {"current": 0, "target": 0},
                    "money": 5,
                    "hands_left": 4,
                    "discards_left": 4,
                    "blinds": [
                        {"slot": "Small", "key": "bl_small", "state": "Defeated"},
                        {"slot": "Big", "key": "bl_big", "state": "Upcoming"},
                        {"slot": "Boss", "key": "bl_head", "state": "Upcoming"},
                    ],
                }
            }
        )

        self.assertEqual(blind_select["blind_key"], "bl_small")
        self.assertEqual(play_hand["blind_key"], "bl_big")
        self.assertEqual(shop["blind_key"], "bl_big")

    def test_observe_orders_skip_tags_and_blinds_with_canonical_claim_fields(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "blind_select",
                "blind_key": "bl_small",
                "score": {"current": 0, "target": 300},
                "money": 4,
                "hands_left": 4,
                "discards_left": 4,
                "skip_tags": [
                    {"slot": "Boss", "key": "tag_boss"},
                    {"slot": "Small", "key": "tag_small", "claimed": True},
                    {"slot": "Big", "key": "tag_big"},
                ],
                "blinds": [
                    {"slot": "Boss", "key": "bl_head", "state": "Upcoming"},
                    {"slot": "Small", "key": "bl_small", "state": "Skipped", "tag_key": "tag_small", "tag_claimed": True},
                    {"slot": "Big", "key": "bl_big", "state": "Select", "tag_key": "tag_big"},
                ],
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(
            observation["skip_tags"],
            [
                {"slot": "small", "key": "tag_small", "claimed": True},
                {"slot": "big", "key": "tag_big"},
                {"slot": "boss", "key": "tag_boss"},
            ],
        )
        self.assertEqual(
            observation["blinds"],
            [
                {"slot": "small", "key": "bl_small", "state": "skipped", "tag_key": "tag_small", "tag_claimed": True},
                {"slot": "big", "key": "bl_big", "state": "select", "tag_key": "tag_big"},
                {"slot": "boss", "key": "bl_head", "state": "upcoming"},
            ],
        )

    def test_observe_keeps_skip_tags_distinct_from_empty_active_tags(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "blind_select",
                "blind_key": "bl_big",
                "score": {"current": 0, "target": 300},
                "money": 4,
                "hands_left": 4,
                "discards_left": 4,
                "skip_tags": [
                    {"slot": "Small", "key": "tag_foil"},
                    {"slot": "Big", "key": "tag_uncommon"},
                ],
                "tags": [],
                "blinds": [
                    {"slot": "Small", "key": "bl_small", "state": "Skipped", "tag_key": "tag_foil", "tag_claimed": True},
                    {"slot": "Big", "key": "bl_big", "state": "Select", "tag_key": "tag_uncommon"},
                ],
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(
            observation["skip_tags"],
            [
                {"slot": "small", "key": "tag_foil"},
                {"slot": "big", "key": "tag_uncommon"},
            ],
        )
        self.assertEqual(observation["tags"], [])

    def test_observe_separates_active_tags_from_claimable_skip_tags(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "shop",
                "blind_key": "bl_big",
                "score": {"current": 0, "target": 300},
                "money": 5,
                "hands_left": 4,
                "discards_left": 4,
                "skip_tags": [
                    {"slot": "Big", "key": "tag_economy"},
                ],
                "tags": [
                    {"key": "tag_top_up"},
                    {"key": "tag_buffoon"},
                ],
                "blinds": [
                    {"slot": "Small", "key": "bl_small", "state": "Defeated"},
                    {"slot": "Big", "key": "bl_big", "state": "Upcoming", "tag_key": "tag_economy"},
                ],
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(observation["skip_tags"], [{"slot": "big", "key": "tag_economy"}])
        self.assertEqual(
            observation["tags"],
            [
                {"key": "tag_top_up"},
                {"key": "tag_buffoon"},
            ],
        )

    def test_observe_does_not_backfill_phase4_arrays_from_removed_aliases(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "blind_select",
                "blind_key": "bl_small",
                "score": {"current": 0, "target": 300},
                "money": 4,
                "hands_left": 4,
                "discards_left": 4,
                "consumables_inventory": [
                    {"kind": "Tarot", "key": "c_fool"},
                ],
                "blind_choices": [
                    {"slot": "Small", "key": "bl_small", "state": "Select"},
                ],
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(observation["consumables"], [])
        self.assertEqual(observation["blinds"], [])

    def test_format_observation_renders_from_canonical_payload(self) -> None:
        observation = {
            "source": "live_state_exporter",
            "state_id": 7,
            "interaction_phase": "shop",
            "blind_key": "bl_small",
            "deck_key": "b_erratic",
            "stake_id": "gold_stake",
            "score": {"current": 150, "target": 800},
            "money": 14,
            "hands_left": 4,
            "discards_left": 2,
            "ante": 3,
            "round_count": 17,
            "joker_slots": 5,
            "joker_count": 1,
            "jokers": [
                {
                    "key": "j_greedy_joker",
                    "rarity": "common",
                    "edition": "foil",
                    "stickers": ["rental"],
                }
            ],
            "consumable_slots": 2,
            "consumables": [
                {
                    "key": "c_fool",
                    "kind": "tarot",
                    "sell_price": 1,
                }
            ],
            "shop_vouchers": [{"key": "v_overstock", "cost": 10}],
            "vouchers": [{"key": "v_clearance_sale"}],
            "skip_tags": [{"slot": "big", "key": "tag_economy"}],
            "tags": [{"key": "tag_economy"}],
            "shop_items": [
                {"key": "j_vampire", "kind": "joker", "cost": 7},
            ],
            "shop_discounts": [
                {"kind": "discount_percent", "value": 25},
                {"kind": "shop_free"},
            ],
            "reroll_cost": 5,
            "interest": 3,
            "inflation": 2,
            "pack_contents": None,
            "hand_size": 8,
            "cards_in_hand": [
                {
                    "card_key": "s_a",
                    "name": "Ace of Spades",
                    "enhancement": "bonus",
                }
            ],
            "selected_cards": [],
            "highlighted_card": None,
            "cards_in_deck": [],
            "blinds": [{"slot": "small", "key": "bl_small", "state": "current", "tag_key": "tag_economy"}],
            "notes": ["seen_at=2026-03-26T00:00:00+00:00"],
        }

        formatted = format_observation(observation)

        self.assertIn("interaction_phase: shop", formatted)
        self.assertIn("score: 150/800", formatted)
        self.assertIn("stake_id: gold_stake", formatted)
        self.assertIn("joker_slots: 5", formatted)
        self.assertIn("interest: 3", formatted)
        self.assertIn("inflation: 2", formatted)
        self.assertIn("hand_size: 8", formatted)
        self.assertIn("consumables:", formatted)
        self.assertIn("shop_vouchers:", formatted)
        self.assertIn("shop_items:", formatted)
        self.assertIn("shop_discounts:", formatted)
        self.assertIn("discount_percent=25", formatted)
        self.assertIn("shop_free", formatted)
        self.assertIn("cards_in_hand:", formatted)
        self.assertIn("j_greedy_joker", formatted)
        self.assertIn("v_overstock", formatted)
        self.assertNotIn("deck:", formatted)
        self.assertNotIn("current_score", formatted)
        self.assertNotIn("shop_packs", formatted)
        self.assertNotIn("Greedy Joker", formatted)

    def test_format_observation_prints_each_shop_pack_once_from_live_observer(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "shop",
                "score": {
                    "current": 75,
                    "target": 300,
                },
                "money": 10,
                "hands_left": 4,
                "discards_left": 2,
                "shop_items": [
                    {
                        "kind": "Pack",
                        "name": "Jumbo Standard Pack",
                        "key": "p_standard_jumbo_1",
                        "cost": 6,
                    }
                ],
                "shop_packs": [
                    {
                        "kind": "Booster",
                        "name": "Jumbo Standard Pack",
                        "key": "p_standard_jumbo_1",
                        "cost": 6,
                    }
                ],
            }
        }

        observation = self.observe_live_payload(live_payload)
        formatted = format_observation(observation)

        self.assertEqual(formatted.count("Jumbo Standard Pack"), 1)
        self.assertNotIn("shop_packs", formatted)

    def test_observe_save_fallback_uses_same_canonical_skeleton(self) -> None:
        # Transitional legacy bridge: save fallback still starts from legacy decoded save text and
        # must be normalized into the same canonical public payload.
        legacy_save_payload = (
            'return {["STATE"]=5,["BLIND"]={["config_blind"]="bl_big",["chips"]=to_big({300}, 1)},'
            '["GAME"]={["chips"]=to_big({120}, 1),["dollars"]=10,["current_round"]={["hands_left"]=3,["discards_left"]=1},'
            '["round_resets"]={["hands"]=4,["discards"]=2},["blind_on_deck"]="bl_big",["pseudorandom"]={["seed"]="seed42"}},'
            '["cardAreas"]={["hand"]={["cards"]={},["config"]={["card_count"]=2}},["jokers"]={["cards"]={},["config"]={["card_count"]=1}}}}'
        )

        observation = self.observe_legacy_save_payload(legacy_save_payload)

        self.assertEqual(list(observation.keys()), CANONICAL_TOP_LEVEL_KEYS)
        self.assertEqual(observation["source"], "save_file")
        self.assertEqual(observation["interaction_phase"], "state_5")
        self.assertEqual(observation["score"], {"current": 120, "target": 300})
        self.assertEqual(observation["jokers"], [])
        self.assertEqual(observation["cards_in_hand"], [])
        self.assertIsNone(observation["stake_id"])
        self.assertTrue(any(note.startswith("seen_at=") for note in observation["notes"]))
        self.assertTrue(FORBIDDEN_LEGACY_KEYS.isdisjoint(observation.keys()))

    def test_runtime_and_policy_consume_canonical_payload(self) -> None:
        observations = [
            {
                "source": "mock",
                "state_id": 1,
                "interaction_phase": "shop",
                "blind_key": None,
                "deck_key": None,
                "stake_id": None,
                "score": {"current": 90, "target": 300},
                "money": 6,
                "hands_left": 0,
                "discards_left": 0,
                "ante": None,
                "round_count": None,
                "joker_slots": None,
                "joker_count": 0,
                "jokers": [],
                "consumable_slots": None,
                "consumables": [],
                "shop_vouchers": [],
                "vouchers": [],
                "skip_tags": [],
                "tags": [],
                "shop_items": [],
                "shop_discounts": [],
                "reroll_cost": None,
                "interest": None,
                "inflation": None,
                "pack_contents": None,
                "hand_size": None,
                "cards_in_hand": [],
                "selected_cards": [],
                "highlighted_card": None,
                "cards_in_deck": [],
                "blinds": [],
                "notes": [],
            }
        ]

        runner = EpisodeRunner(
            observer=ScriptedObserver(observations),
            policy=DemoPolicy(),
            validator=RuleBasedValidator(),
            executor=LoggingExecutor(),
        )

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            records = runner.run()

        self.assertEqual(records[0].action.kind, "buy_joker")
        self.assertEqual(records[0].validation.accepted, True)
        self.assertIn("phase=shop", stdout.getvalue())
        self.assertIn("score=90/300", stdout.getvalue())

    def observe_live_payload(self, live_payload: dict[str, object]) -> dict[str, object]:
        root = self.make_fixture_root()
        try:
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text(json.dumps(live_payload), encoding="utf-8")

            observer = BalatroSaveObserver(paths=BalatroPaths(root=root, profile=2))
            return observer.observe()
        finally:
            shutil.rmtree(root, ignore_errors=True)
            self.cleanup_fixture_base()

    def observe_legacy_save_payload(self, legacy_save_payload: str) -> dict[str, object]:
        root = self.make_fixture_root()
        try:
            save_path = root / "1" / "save.jkr"
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(zlib.compress(legacy_save_payload.encode("utf-8")))

            observer = BalatroSaveObserver(paths=BalatroPaths(root=root, profile=1))
            return observer.observe()
        finally:
            shutil.rmtree(root, ignore_errors=True)
            self.cleanup_fixture_base()

    def make_fixture_root(self) -> Path:
        base = Path("tests_tmp")
        base.mkdir(exist_ok=True)
        root = base / f"observer_{uuid4().hex}"
        root.mkdir()
        return root

    def cleanup_fixture_base(self) -> None:
        base = Path("tests_tmp")
        try:
            base.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    unittest.main()
