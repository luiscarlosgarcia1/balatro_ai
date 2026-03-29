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
    "interest",
    "hands_left",
    "discards_left",
    "joker_slots",
    "jokers",
    "consumable_slots",
    "consumables",
    "vouchers",
    "tags",
    "ante",
    "round_count",
    "blinds",
    "shop_items",
    "reroll_cost",
    "pack_contents",
    "hand_size",
    "cards_in_hand",
    "selected_cards",
    "cards_in_deck",
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
                "reroll_cost": 5,
                "interest": {"amount": 3, "cap": 25, "no_interest": False},
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
                "cards_in_hand": [
                    {
                        "card_key": "S_A",
                        "card_kind": "Base",
                        "suit": "Spades",
                        "rank": "Ace",
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
        self.assertEqual(observation["hand_size"], 8)
        self.assertEqual(observation["interest"], {"amount": 3, "cap": 25, "no_interest": False})
        self.assertEqual(observation["reroll_cost"], 5)
        self.assertEqual(observation["vouchers"][0]["key"], "v_clearance_sale")
        self.assertNotIn("name", observation["vouchers"][0])
        self.assertEqual(observation["consumables"][0]["key"], "c_fool")
        self.assertEqual(observation["consumables"][0]["edition"], "negative")
        self.assertEqual(observation["consumables"][0]["sell_price"], 1)
        self.assertEqual(observation["consumables"][0]["stickers"], ["eternal"])
        self.assertNotIn("name", observation["consumables"][0])
        self.assertNotIn("kind", observation["consumables"][0])
        self.assertEqual(observation["jokers"][0]["key"], "j_greedy_joker")
        self.assertEqual(observation["jokers"][0]["rarity"], "common")
        self.assertEqual(observation["jokers"][0]["edition"], "foil")
        self.assertEqual(observation["jokers"][0]["sell_price"], 2)
        self.assertEqual(observation["jokers"][0]["stickers"], ["rental"])
        self.assertNotIn("name", observation["jokers"][0])
        self.assertEqual(observation["tags"][0]["key"], "tag_top_up")
        self.assertNotIn("name", observation["tags"][0])
        self.assertEqual(observation["blinds"][0]["state"], "current")
        self.assertEqual(observation["blinds"][0]["tag_key"], "tag_economy")
        self.assertNotIn("slot", observation["blinds"][0])
        self.assertEqual(observation["cards_in_hand"][0]["card_key"], "s_a")
        self.assertEqual(observation["cards_in_hand"][0]["enhancement"], "bonus")
        self.assertNotIn("card_kind", observation["cards_in_hand"][0])
        self.assertNotIn("suit", observation["cards_in_hand"][0])
        self.assertNotIn("rank", observation["cards_in_hand"][0])
        self.assertEqual(observation["shop_items"][0]["key"], "j_vampire")
        self.assertEqual(observation["shop_items"][1]["key"], "c_sun")
        self.assertEqual(observation["shop_items"][2]["key"], "p_arcana_normal_1")
        self.assertEqual(observation["shop_items"][3]["key"], "v_overstock")
        self.assertEqual(observation["shop_items"][3]["cost"], 10)
        self.assertNotIn("kind", observation["shop_items"][0])
        self.assertNotIn("name", observation["shop_items"][0])
        self.assertIn("screenshot_status=true", observation["notes"])
        self.assertTrue(any(note.startswith("seen_at=") for note in observation["notes"]))

    def test_observe_orders_cards_in_hand_and_deck_by_canonical_suit_then_rank(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "play_hand",
                "score": {"current": 120, "target": 300},
                "money": 8,
                "hands_left": 4,
                "discards_left": 2,
                "cards_in_hand": [
                    {
                        "card_key": "s_10",
                        "card_kind": "Base",
                        "suit": "Spades",
                        "rank": "10",
                        "enhancement": "Bonus",
                        "edition": "Foil",
                        "seal": "Gold",
                        "stickers": ["eternal"],
                        "facing": "Front",
                        "cost": 3,
                        "sell_price": 1,
                        "debuffed": True,
                    },
                    {
                        "card_key": "c_a",
                        "card_kind": "Base",
                        "suit": "Clubs",
                        "rank": "Ace",
                    },
                    {
                        "card_key": "h_k",
                        "card_kind": "Stone",
                        "suit": "Hearts",
                        "rank": "King",
                        "rarity": "Common",
                    },
                ],
                "cards_in_deck": [
                    {
                        "card_key": "s_2",
                        "card_kind": "Base",
                        "suit": "Spades",
                        "rank": "2",
                    },
                    {
                        "card_key": "d_a",
                        "card_kind": "Base",
                        "suit": "Diamonds",
                        "rank": "Ace",
                    },
                    {
                        "card_key": "c_k",
                        "card_kind": "Base",
                        "suit": "Clubs",
                        "rank": "King",
                    },
                ],
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(
            [card["card_key"] for card in observation["cards_in_hand"]],
            ["c_a", "h_k", "s_10"],
        )
        self.assertEqual(
            observation["cards_in_hand"][2],
            {
                "card_key": "s_10",
                "enhancement": "bonus",
                "edition": "foil",
                "seal": "gold",
                "stickers": ["eternal"],
                "facing": "front",
                "cost": 3,
                "sell_price": 1,
                "debuffed": True,
            },
        )
        self.assertEqual(
            [card["card_key"] for card in observation["cards_in_deck"]],
            ["c_k", "d_a", "s_2"],
        )
        self.assertNotIn("name", observation["cards_in_hand"][0])

    def test_observe_emits_lightweight_selected_references(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "play_hand",
                "score": {"current": 120, "target": 300},
                "money": 8,
                "hands_left": 4,
                "discards_left": 2,
                "selected_cards": [
                    {"zone": "cards_in_hand", "card_key": "h_8"},
                    {"zone": "jokers", "joker_key": "j_blueprint"},
                ],
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(
            observation["selected_cards"],
            [
                {"zone": "cards_in_hand", "card_key": "h_8"},
                {"zone": "jokers", "joker_key": "j_blueprint"},
            ],
        )

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
                "consumable_slots": 2,
                "reroll_cost": 6,
                "interest": {"amount": 4, "cap": 50, "no_interest": True},
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
        self.assertEqual(observation["consumable_slots"], 2)
        self.assertEqual(observation["interest"], {"amount": 4, "cap": 50, "no_interest": True})
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
                    "key": "j_credit_card",
                    "cost": 1,
                    "rarity": "common",
                    "edition": "foil",
                    "sell_price": 2,
                    "stickers": ["rental"],
                },
                {
                    "key": "p_buffoon_normal_1",
                    "cost": 4,
                },
                {
                    "key": "c_fool",
                    "cost": 3,
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
                {"key": "p_standard_jumbo_1", "cost": 6}
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
                        "choices_remaining": 1,
                        "skip_available": True,
                        "cards": [
                            {
                                "card_key": "c_fool",
                                "card_kind": "Tarot",
                                "cost": 0,
                                "sell_price": 1,
                            }
                        ],
                    },
                    "selected_cards": [
                        {"zone": "pack_contents", "card_key": "c_fool"},
                    ],
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
        self.assertEqual(
            pack_reward["pack_contents"],
            {
                "choices_remaining": 1,
                "skip_available": True,
                "cards": [
                    {
                        "card_key": "c_fool",
                        "cost": 0,
                        "sell_price": 1,
                    }
                ],
            },
        )
        self.assertEqual(
            pack_reward["selected_cards"],
            [{"zone": "pack_contents", "card_key": "c_fool"}],
        )

    def test_observe_keeps_active_pack_contents_without_identity_metadata(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "pack_reward",
                "pack_contents": {
                    "choices_remaining": 1,
                    "skip_available": True,
                    "cards": [
                        {
                            "card_key": "c_fool",
                            "card_kind": "Tarot",
                        }
                    ],
                },
                "score": {"current": 0, "target": 300},
                "money": 8,
                "hands_left": 4,
                "discards_left": 4,
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(
            observation["pack_contents"],
            {
                "choices_remaining": 1,
                "skip_available": True,
                "cards": [
                    {
                        "card_key": "c_fool",
                    }
                ],
            },
        )

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

    def test_observe_orders_blinds_with_canonical_claim_fields(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "blind_select",
                "blind_key": "bl_small",
                "score": {"current": 0, "target": 300},
                "money": 4,
                "hands_left": 4,
                "discards_left": 4,
                "blinds": [
                    {"slot": "Boss", "key": "bl_head", "state": "Upcoming"},
                    {"slot": "Small", "key": "bl_small", "state": "Skipped", "tag_key": "tag_small", "tag_claimed": True},
                    {"slot": "Big", "key": "bl_big", "state": "Select", "tag_key": "tag_big"},
                ],
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(
            observation["blinds"],
            [
                {"key": "bl_head", "state": "upcoming"},
                {"key": "bl_small", "state": "skipped", "tag_key": "tag_small", "tag_claimed": True},
                {"key": "bl_big", "state": "select", "tag_key": "tag_big"},
            ],
        )

    def test_observe_keeps_unclaimed_blind_tag_fields_distinct_from_empty_active_tags(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "blind_select",
                "blind_key": "bl_big",
                "score": {"current": 0, "target": 300},
                "money": 4,
                "hands_left": 4,
                "discards_left": 4,
                "tags": [],
                "blinds": [
                    {"slot": "Small", "key": "bl_small", "state": "Select", "tag_key": "tag_foil"},
                    {"slot": "Big", "key": "bl_big", "state": "Select", "tag_key": "tag_uncommon"},
                ],
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(observation["blinds"][0]["tag_key"], "tag_foil")
        self.assertEqual(observation["blinds"][1]["tag_key"], "tag_uncommon")
        self.assertEqual(observation["tags"], [])

    def test_observe_tags_follow_direct_source_exactly(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "shop",
                "blind_key": "bl_big",
                "score": {"current": 0, "target": 300},
                "money": 5,
                "hands_left": 4,
                "discards_left": 4,
                "tags": [
                    {"key": "tag_top_up"},
                    {"key": "tag_buffoon"},
                    {"key": "tag_top_up"},
                ],
                "blinds": [
                    {"slot": "Small", "key": "bl_small", "state": "Skipped", "tag_key": "tag_coupon", "tag_claimed": True},
                    {"slot": "Big", "key": "bl_big", "state": "Skipped", "tag_key": "tag_economy", "tag_claimed": True},
                ],
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(
            observation["tags"],
            [
                {"key": "tag_top_up"},
                {"key": "tag_buffoon"},
                {"key": "tag_top_up"},
            ],
        )

    def test_observe_tags_stay_empty_even_if_blinds_have_claimed_tags(self) -> None:
        live_payload = {
            "state": {
                "source": "live_state_exporter",
                "interaction_phase": "shop",
                "blind_key": "bl_big",
                "score": {"current": 0, "target": 300},
                "money": 5,
                "hands_left": 4,
                "discards_left": 4,
                "tags": [],
                "blinds": [
                    {"slot": "Small", "key": "bl_small", "state": "Skipped", "tag_key": "tag_coupon", "tag_claimed": True},
                    {"slot": "Big", "key": "bl_big", "state": "Skipped", "tag_key": "tag_economy", "tag_claimed": True},
                ],
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(
            observation["tags"],
            [],
        )

    def test_observe_ignores_removed_skip_tags_alias(self) -> None:
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
                    {"slot": "Small", "key": "tag_foil"},
                ],
                "blinds": [],
            }
        }

        observation = self.observe_live_payload(live_payload)

        self.assertEqual(observation["blinds"], [])

    def test_observe_only_merges_legacy_shop_vouchers_into_shop_items_during_shop(self) -> None:
        shop = self.observe_live_payload(
            {
                "state": {
                    "source": "live_state_exporter",
                    "interaction_phase": "shop",
                    "score": {"current": 0, "target": 300},
                    "money": 5,
                    "hands_left": 4,
                    "discards_left": 4,
                    "shop_vouchers": [
                        {"key": "v_overstock", "cost": 10},
                    ],
                    "shop_items": [],
                }
            }
        )
        play_hand = self.observe_live_payload(
            {
                "state": {
                    "source": "live_state_exporter",
                    "interaction_phase": "play_hand",
                    "score": {"current": 120, "target": 300},
                    "money": 5,
                    "hands_left": 4,
                    "discards_left": 4,
                    "shop_vouchers": [
                        {"key": "v_overstock", "cost": 10},
                    ],
                    "shop_items": [],
                }
            }
        )

        self.assertEqual(
            shop["shop_items"],
            [
                {
                    "key": "v_overstock",
                    "cost": 10,
                }
            ],
        )
        self.assertEqual(play_hand["shop_items"], [])

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
                    "sell_price": 1,
                }
            ],
            "vouchers": [{"key": "v_clearance_sale"}],
            "tags": [{"key": "tag_economy"}],
            "shop_items": [
                {"key": "j_vampire", "cost": 7},
                {"key": "v_overstock", "cost": 10},
            ],
            "reroll_cost": 5,
            "interest": {"amount": 3, "cap": 25, "no_interest": False},
            "pack_contents": None,
            "hand_size": 8,
            "cards_in_hand": [
                {
                    "card_key": "s_a",
                    "enhancement": "bonus",
                }
            ],
            "selected_cards": [{"zone": "cards_in_hand", "card_key": "s_a"}],
            "cards_in_deck": [
                {
                    "card_key": "c_k",
                }
            ],
            "blinds": [{"key": "bl_small", "state": "current", "tag_key": "tag_economy"}],
            "notes": ["seen_at=2026-03-26T00:00:00+00:00"],
        }

        formatted = format_observation(observation)

        self.assertIn("interaction_phase: shop", formatted)
        self.assertIn("score: 150/800", formatted)
        self.assertIn("stake_id: gold_stake", formatted)
        self.assertIn("joker_slots: 5", formatted)
        self.assertIn("interest: amount=3, cap=25, no_interest=false", formatted)
        self.assertIn("hand_size: 8", formatted)
        self.assertIn("consumables:", formatted)
        self.assertIn("shop_items:", formatted)
        self.assertNotIn("open_pack_kind", formatted)
        self.assertIn("cards_in_hand:", formatted)
        self.assertIn("cards_in_deck:", formatted)
        self.assertIn("selected_cards:", formatted)
        self.assertIn("j_greedy_joker", formatted)
        self.assertIn("v_overstock", formatted)
        self.assertNotIn("\n  deck:", formatted)
        self.assertNotIn("current_score", formatted)
        self.assertNotIn("shop_packs", formatted)
        self.assertNotIn("Greedy Joker", formatted)
        self.assertNotIn("Ace of Spades", formatted)

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

        self.assertEqual(formatted.count("p_standard_jumbo_1"), 1)
        self.assertNotIn("shop_packs", formatted)

    def test_format_observation_renders_canonical_pack_contents(self) -> None:
        observation = {
            "source": "live_state_exporter",
            "state_id": 8,
            "interaction_phase": "pack_reward",
            "blind_key": "bl_big",
            "deck_key": "b_erratic",
            "stake_id": "gold_stake",
            "score": {"current": 0, "target": 800},
            "money": 14,
            "hands_left": 4,
            "discards_left": 2,
            "ante": 3,
            "round_count": 17,
            "joker_slots": 5,
            "jokers": [],
            "consumable_slots": 2,
            "consumables": [],
            "vouchers": [],
            "tags": [],
            "shop_items": [],
            "reroll_cost": 5,
            "interest": {"amount": 3, "cap": 25, "no_interest": False},
            "pack_contents": {
                "choices_remaining": 1,
                "skip_available": True,
                "cards": [
                    {
                        "card_key": "c_fool",
                        "card_kind": "tarot",
                        "cost": 0,
                    }
                ],
            },
            "hand_size": 8,
            "cards_in_hand": [],
            "selected_cards": [{"zone": "pack_contents", "card_key": "c_fool"}],
            "cards_in_deck": [],
            "blinds": [],
            "notes": ["seen_at=2026-03-26T00:00:00+00:00"],
        }

        formatted = format_observation(observation)

        self.assertIn("pack_contents:", formatted)
        self.assertIn("choices_remaining=1", formatted)
        self.assertIn("skip_available=true", formatted)
        self.assertIn("c_fool", formatted)
        self.assertNotIn("open_pack_kind", formatted)

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

    def test_observe_save_fallback_extracts_canonical_hand_and_deck_cards(self) -> None:
        legacy_save_payload = (
            'return {["STATE"]=5,["BLIND"]={["config_blind"]="bl_big",["chips"]=to_big({300}, 1)},'
            '["GAME"]={["chips"]=to_big({120}, 1),["dollars"]=10,["current_round"]={["hands_left"]=3,["discards_left"]=1},'
            '["round_resets"]={["hands"]=4,["discards"]=2},["blind_on_deck"]="bl_big"},'
            '["cardAreas"]={'
            '["hand"]={["cards"]={'
            '[1]={["save_fields"]={["card"]="S_A"},["base"]={["value"]="Ace",["suit"]="Spades"},'
            '["ability"]={["set"]="Base",["effect"]="Bonus"},["edition"]={["type"]="Foil"},["seal"]="Gold",["debuff"]=true}'
            '},["config"]={["card_count"]=1}},'
            '["deck"]={["cards"]={'
            '[1]={["save_fields"]={["card"]="D_A"},["base"]={["value"]="Ace",["suit"]="Diamonds"},["ability"]={["set"]="Base"}},'
            '[2]={["save_fields"]={["card"]="C_K"},["base"]={["value"]="King",["suit"]="Clubs"},["ability"]={["set"]="Base"}}'
            '},["config"]={["card_count"]=2}},'
            '["jokers"]={["cards"]={},["config"]={["card_count"]=1}}}}'
        )

        observation = self.observe_legacy_save_payload(legacy_save_payload)

        self.assertEqual(
            observation["cards_in_hand"],
            [
                {
                    "card_key": "s_a",
                    "enhancement": "bonus",
                    "edition": "foil",
                    "seal": "gold",
                    "debuffed": True,
                }
            ],
        )
        self.assertEqual(
            [card["card_key"] for card in observation["cards_in_deck"]],
            ["c_k", "d_a"],
        )
        self.assertEqual(observation["selected_cards"], [])

    def test_observe_save_fallback_extracts_raw_interest_object(self) -> None:
        legacy_save_payload = (
            'return {["STATE"]=5,["BLIND"]={["config_blind"]="bl_big",["chips"]=to_big({300}, 1)},'
            '["GAME"]={["chips"]=to_big({120}, 1),["dollars"]=10,["interest_amount"]=2,["interest_cap"]=50,'
            '["modifiers"]={["no_interest"]=true},["current_round"]={["hands_left"]=3,["discards_left"]=1},'
            '["round_resets"]={["hands"]=4,["discards"]=2},["blind_on_deck"]="bl_big"},'
            '["cardAreas"]={["hand"]={["cards"]={},["config"]={["card_count"]=0}},["jokers"]={["cards"]={},["config"]={["card_count"]=0}}}}'
        )

        observation = self.observe_legacy_save_payload(legacy_save_payload)

        self.assertEqual(
            observation["interest"],
            {"amount": 2, "cap": 50, "no_interest": True},
        )

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
                "jokers": [],
                "consumable_slots": None,
                "consumables": [],
                "vouchers": [],
                "tags": [],
                "shop_items": [],
                "reroll_cost": None,
                "interest": None,
                "pack_contents": None,
                "hand_size": None,
                "cards_in_hand": [],
                "selected_cards": [],
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
