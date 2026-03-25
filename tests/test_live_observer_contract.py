from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from obs_test import format_observation
from balatro_ai.observation import BalatroPaths, BalatroSaveObserver


class LiveObserverContractTests(unittest.TestCase):
    def test_observe_normalizes_deck_vouchers_and_split_consumables(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text(
                json.dumps(
                    {
                        "state": {
                            "source": "live_state_exporter",
                            "phase": "shop",
                            "money": 10,
                            "hands_left": 4,
                            "discards_left": 2,
                            "score_to_beat": 300,
                            "current_score": 75,
                            "blind_name": "Small Blind",
                            "blind_key": "bl_small",
                            "deck": {
                                "name": "Erratic Deck",
                                "key": "b_erratic",
                            },
                            "vouchers": [
                                {
                                    "name": "Clearance Sale",
                                    "key": "v_clearance_sale",
                                }
                            ],
                            "consumable_capacity": 2,
                            "consumables_inventory": [
                                {
                                    "kind": "tarot",
                                    "name": "The Fool",
                                    "key": "c_fool",
                                }
                            ],
                            "consumables_shop": [
                                {
                                    "kind": "planet",
                                    "name": "Mercury",
                                    "key": "c_mercury",
                                    "cost": 3,
                                }
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )

            observer = BalatroSaveObserver(paths=BalatroPaths(root=root, profile=2))
            observation = observer.observe()

            self.assertEqual(observation.deck_name, "Erratic Deck")
            self.assertEqual(observation.deck_key, "b_erratic")
            self.assertEqual(observation.vouchers[0].name, "Clearance Sale")
            self.assertEqual(observation.vouchers[0].key, "v_clearance_sale")
            self.assertEqual(observation.consumable_capacity, 2)
            self.assertEqual(observation.consumables_inventory[0].kind, "tarot")
            self.assertEqual(observation.consumables_inventory[0].name, "The Fool")
            self.assertEqual(observation.consumables_shop[0].kind, "planet")
            self.assertEqual(observation.consumables_shop[0].cost, 3)

    def test_observe_normalizes_run_metadata_shop_items_and_pack_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text(
                json.dumps(
                    {
                        "state": {
                            "source": "live_state_exporter",
                            "phase": "shop",
                            "interaction_phase": "pack_reward",
                            "ante": 3,
                            "round_count": 17,
                            "stake": "Gold Stake",
                            "reroll_cost": 5,
                            "money": 14,
                            "hands_left": 4,
                            "discards_left": 2,
                            "score_to_beat": 800,
                            "current_score": 150,
                            "shop_items": [
                                {
                                    "kind": "joker",
                                    "name": "Vampire",
                                    "key": "j_vampire",
                                    "cost": 7,
                                },
                                {
                                    "kind": "consumable",
                                    "name": "The Sun",
                                    "key": "c_sun",
                                    "cost": 3,
                                },
                            ],
                            "shop_packs": [
                                {
                                    "name": "Arcana Pack",
                                    "key": "p_arcana_normal_1",
                                    "kind": "arcana",
                                    "cost": 4,
                                },
                                {
                                    "name": "Celestial Pack",
                                    "key": "p_celestial_normal_1",
                                    "kind": "celestial",
                                    "cost": 4,
                                },
                            ],
                            "skip_tag": {
                                "name": "Economy Tag",
                                "key": "tag_economy",
                            },
                            "skip_tag_claimed": True,
                        }
                    }
                ),
                encoding="utf-8",
            )

            observer = BalatroSaveObserver(paths=BalatroPaths(root=root, profile=2))
            observation = observer.observe()

            self.assertEqual(observation.ante, 3)
            self.assertEqual(observation.round_count, 17)
            self.assertEqual(observation.stake, "Gold Stake")
            self.assertEqual(observation.reroll_cost, 5)
            self.assertEqual(observation.interaction_phase, "pack_reward")
            self.assertTrue(observation.skip_tag_claimed)
            self.assertEqual(observation.skip_tag.name, "Economy Tag")
            self.assertEqual(observation.shop_items[0].kind, "joker")
            self.assertEqual(observation.shop_items[0].name, "Vampire")
            self.assertEqual(observation.shop_items[1].kind, "consumable")
            self.assertEqual(len(observation.shop_packs), 2)
            self.assertEqual(observation.shop_packs[1].name, "Celestial Pack")

    def test_format_observation_shows_deck_vouchers_and_consumables(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text(
                json.dumps(
                    {
                        "state": {
                            "source": "live_state_exporter",
                            "phase": "shop",
                            "money": 10,
                            "hands_left": 4,
                            "discards_left": 2,
                            "score_to_beat": 300,
                            "current_score": 75,
                            "blind_name": "Small Blind",
                            "blind_key": "bl_small",
                            "deck": {
                                "name": "Erratic Deck",
                                "key": "b_erratic",
                            },
                            "vouchers": [
                                {
                                    "name": "Clearance Sale",
                                    "key": "v_clearance_sale",
                                }
                            ],
                            "consumable_capacity": 2,
                            "consumables_inventory": [
                                {
                                    "kind": "tarot",
                                    "name": "The Fool",
                                    "key": "c_fool",
                                }
                            ],
                            "consumables_shop": [
                                {
                                    "kind": "planet",
                                    "name": "Mercury",
                                    "key": "c_mercury",
                                    "cost": 3,
                                }
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )

            observer = BalatroSaveObserver(paths=BalatroPaths(root=root, profile=2))
            formatted = format_observation(observer.observe())

            self.assertIn("deck: Erratic Deck", formatted)
            self.assertIn("vouchers: Clearance Sale", formatted)
            self.assertIn("consumable_capacity: 2", formatted)
            self.assertIn("inventory_consumables:", formatted)
            self.assertIn("shop_consumables:", formatted)
            self.assertIn("The Fool", formatted)
            self.assertIn("Mercury", formatted)

    def test_format_observation_shows_run_metadata_shop_items_and_pack_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text(
                json.dumps(
                    {
                        "state": {
                            "source": "live_state_exporter",
                            "phase": "shop",
                            "interaction_phase": "pack_reward",
                            "ante": 3,
                            "round_count": 17,
                            "stake": "Gold Stake",
                            "reroll_cost": 5,
                            "money": 14,
                            "hands_left": 4,
                            "discards_left": 2,
                            "score_to_beat": 800,
                            "current_score": 150,
                            "shop_items": [
                                {
                                    "kind": "joker",
                                    "name": "Vampire",
                                    "key": "j_vampire",
                                    "cost": 7,
                                }
                            ],
                            "shop_packs": [
                                {
                                    "name": "Arcana Pack",
                                    "key": "p_arcana_normal_1",
                                    "kind": "arcana",
                                    "cost": 4,
                                }
                            ],
                            "skip_tag": {
                                "name": "Economy Tag",
                                "key": "tag_economy",
                            },
                            "skip_tag_claimed": True,
                        }
                    }
                ),
                encoding="utf-8",
            )

            observer = BalatroSaveObserver(paths=BalatroPaths(root=root, profile=2))
            formatted = format_observation(observer.observe())

            self.assertIn("interaction_phase: pack_reward", formatted)
            self.assertIn("ante: 3", formatted)
            self.assertIn("round_count: 17", formatted)
            self.assertIn("stake: Gold Stake", formatted)
            self.assertIn("reroll_cost: 5", formatted)
            self.assertIn("skip_tag_claimed: True", formatted)
            self.assertIn("skip_tag: Economy Tag", formatted)
            self.assertIn("shop_items:", formatted)
            self.assertIn("Vampire", formatted)
            self.assertIn("shop_packs:", formatted)
            self.assertIn("Arcana Pack", formatted)

    def test_observe_normalizes_gameplay_relevant_joker_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text(
                json.dumps(
                    {
                        "state": {
                            "source": "live_state_exporter",
                            "phase": "shop",
                            "money": 18,
                            "hands_left": 4,
                            "discards_left": 2,
                            "score_to_beat": 450,
                            "current_score": 100,
                            "jokers": [
                                {
                                    "name": "Greedy Joker",
                                    "key": "j_greedy_joker",
                                    "edition": "Foil",
                                    "debuffed": False,
                                    "modifiers": [
                                        "mult=4",
                                        "rental",
                                    ],
                                }
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )

            observer = BalatroSaveObserver(paths=BalatroPaths(root=root, profile=2))
            observation = observer.observe()

            self.assertEqual(observation.jokers, ("Greedy Joker",))
            self.assertEqual(observation.joker_details[0].name, "Greedy Joker")
            self.assertEqual(observation.joker_details[0].key, "j_greedy_joker")
            self.assertEqual(observation.joker_details[0].edition, "Foil")
            self.assertEqual(
                observation.joker_details[0].modifiers,
                ("mult=4", "rental"),
            )

    def test_format_observation_shows_richer_joker_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text(
                json.dumps(
                    {
                        "state": {
                            "source": "live_state_exporter",
                            "phase": "shop",
                            "money": 18,
                            "hands_left": 4,
                            "discards_left": 2,
                            "score_to_beat": 450,
                            "current_score": 100,
                            "jokers": [
                                {
                                    "name": "Greedy Joker",
                                    "key": "j_greedy_joker",
                                    "edition": "Foil",
                                    "debuffed": False,
                                    "modifiers": [
                                        "mult=4",
                                        "rental",
                                    ],
                                }
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )

            observer = BalatroSaveObserver(paths=BalatroPaths(root=root, profile=2))
            formatted = format_observation(observer.observe())

            self.assertIn("joker_details:", formatted)
            self.assertIn("Greedy Joker", formatted)
            self.assertIn("edition=Foil", formatted)
            self.assertIn("mult=4", formatted)

    def test_observe_normalizes_tags_and_shop_packs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text(
                json.dumps(
                    {
                        "state": {
                            "source": "live_state_exporter",
                            "phase": "shop",
                            "money": 22,
                            "hands_left": 4,
                            "discards_left": 2,
                            "score_to_beat": 600,
                            "current_score": 0,
                            "tags": [
                                {
                                    "name": "Economy Tag",
                                    "key": "tag_economy",
                                }
                            ],
                            "shop_packs": [
                                {
                                    "name": "Arcana Pack",
                                    "key": "p_arcana_normal_1",
                                    "kind": "arcana",
                                    "cost": 4,
                                }
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )

            observer = BalatroSaveObserver(paths=BalatroPaths(root=root, profile=2))
            observation = observer.observe()

            self.assertEqual(observation.tags[0].name, "Economy Tag")
            self.assertEqual(observation.tags[0].key, "tag_economy")
            self.assertEqual(observation.shop_packs[0].name, "Arcana Pack")
            self.assertEqual(observation.shop_packs[0].kind, "arcana")
            self.assertEqual(observation.shop_packs[0].cost, 4)

    def test_format_observation_shows_tags_and_shop_packs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text(
                json.dumps(
                    {
                        "state": {
                            "source": "live_state_exporter",
                            "phase": "shop",
                            "money": 22,
                            "hands_left": 4,
                            "discards_left": 2,
                            "score_to_beat": 600,
                            "current_score": 0,
                            "tags": [
                                {
                                    "name": "Economy Tag",
                                    "key": "tag_economy",
                                }
                            ],
                            "shop_packs": [
                                {
                                    "name": "Arcana Pack",
                                    "key": "p_arcana_normal_1",
                                    "kind": "arcana",
                                    "cost": 4,
                                }
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )

            observer = BalatroSaveObserver(paths=BalatroPaths(root=root, profile=2))
            formatted = format_observation(observer.observe())

            self.assertIn("tags:", formatted)
            self.assertIn("Economy Tag", formatted)
            self.assertIn("shop_packs:", formatted)
            self.assertIn("Arcana Pack", formatted)
            self.assertIn("kind=arcana", formatted)

    def test_observe_normalizes_blind_choices(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text(
                json.dumps(
                    {
                        "state": {
                            "source": "live_state_exporter",
                            "phase": "blind_select",
                            "money": 8,
                            "hands_left": 4,
                            "discards_left": 4,
                            "score_to_beat": 300,
                            "current_score": 0,
                            "blind_name": "Small Blind",
                            "blind_key": "bl_small",
                            "blind_choices": [
                                {
                                    "slot": "Small",
                                    "key": "bl_small",
                                    "state": "Current",
                                    "tag": "tag_economy",
                                },
                                {
                                    "slot": "Boss",
                                    "key": "bl_head",
                                    "state": "Upcoming",
                                },
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )

            observer = BalatroSaveObserver(paths=BalatroPaths(root=root, profile=2))
            observation = observer.observe()

            self.assertEqual(observation.blind_choices[0].slot, "Small")
            self.assertEqual(observation.blind_choices[0].key, "bl_small")
            self.assertEqual(observation.blind_choices[0].state, "Current")
            self.assertEqual(observation.blind_choices[0].tag, "tag_economy")
            self.assertEqual(observation.blind_choices[1].slot, "Boss")

    def test_format_observation_shows_blind_choices(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            live_state_path = root / "ai" / "live_state.json"
            live_state_path.parent.mkdir(parents=True, exist_ok=True)
            live_state_path.write_text(
                json.dumps(
                    {
                        "state": {
                            "source": "live_state_exporter",
                            "phase": "blind_select",
                            "money": 8,
                            "hands_left": 4,
                            "discards_left": 4,
                            "score_to_beat": 300,
                            "current_score": 0,
                            "blind_name": "Small Blind",
                            "blind_key": "bl_small",
                            "blind_choices": [
                                {
                                    "slot": "Small",
                                    "key": "bl_small",
                                    "state": "Current",
                                    "tag": "tag_economy",
                                },
                                {
                                    "slot": "Boss",
                                    "key": "bl_head",
                                    "state": "Upcoming",
                                },
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )

            observer = BalatroSaveObserver(paths=BalatroPaths(root=root, profile=2))
            formatted = format_observation(observer.observe())

            self.assertIn("blind_choices:", formatted)
            self.assertIn("Small: bl_small", formatted)
            self.assertIn("state=Current", formatted)
            self.assertIn("tag=tag_economy", formatted)


if __name__ == "__main__":
    unittest.main()
