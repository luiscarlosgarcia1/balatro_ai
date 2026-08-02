"""Joker effect engine for the simulator.

The simulator still has a simpler scoring pipeline than Balatro's event queue.
Jokers with implemented state transitions are handled here; unsupported
metadata is explicit instead of being hidden behind no-op placeholders.
"""

from __future__ import annotations

from enum import IntEnum
import random
from typing import Any, Dict, Iterable, List, Optional

from balatro_gym.core.cards import Enhancement, Rank, Suit
from balatro_gym.core.jokers import JOKER_LIBRARY


class CompleteJokerEffects:
    """Apply simulator-supported joker effects across scoring phases."""

    _HAND_TYPE_EFFECTS = {
        "Jolly Joker": ("Pair", {"mult": 8}),
        "Zany Joker": ("Three of a Kind", {"mult": 12}),
        "Mad Joker": ("Two Pair", {"mult": 10}),
        "Crazy Joker": ("Straight", {"mult": 12}),
        "Droll Joker": ("Flush", {"mult": 10}),
        "Sly Joker": ("Pair", {"chips": 50}),
        "Wily Joker": ("Three of a Kind", {"chips": 100}),
        "Clever Joker": ("Two Pair", {"chips": 80}),
        "Devious Joker": ("Straight", {"chips": 100}),
        "Crafty Joker": ("Flush", {"chips": 80}),
        "The Duo": ("Pair", {"x_mult": 2}),
        "The Trio": ("Three of a Kind", {"x_mult": 3}),
        "The Family": ("Four of a Kind", {"x_mult": 4}),
        "The Order": ("Straight", {"x_mult": 3}),
        "The Tribe": ("Flush", {"x_mult": 2}),
    }
    _SUIT_MULT_JOKERS = {
        "Greedy Joker": ("Diamonds", {"mult": 3}),
        "Lusty Joker": ("Hearts", {"mult": 3}),
        "Wrathful Joker": ("Spades", {"mult": 3}),
        "Gluttonous Joker": ("Clubs", {"mult": 3}),
    }
    _SUIT_INDIVIDUAL_JOKERS = {
        "Rough Gem": ("Diamonds", {"money": 1}),
        "Bloodstone": ("Hearts", {"x_mult": 1.5}, 0.5),
        "Arrowhead": ("Spades", {"chips": 50}),
        "Onyx Agate": ("Clubs", {"mult": 7}),
    }
    _RANK_INDIVIDUAL_JOKERS = {
        "Fibonacci": ({2, 3, 5, 8, 14}, {"mult": 8}),
        "Even Steven": ({2, 4, 6, 8, 10}, {"mult": 4}),
        "Odd Todd": ({3, 5, 7, 9, 14}, {"chips": 31}),
        "Scholar": ({14}, {"chips": 20, "mult": 4}),
        "Walkie Talkie": ({4, 10}, {"chips": 10, "mult": 4}),
        "Wee Joker": ({2}, {"chips": 8}),
        "Triboulet": ({12, 13}, {"x_mult": 2}),
    }
    _PLACEHOLDER_ONLY_NAMES = frozenset({
        "Credit Card", "Chaos the Clown", "Egg", "Gift Card", "Golden Joker",
        "To the Moon", "Astronomer", "Showman", "Oops! All 6s", "Blueprint",
        "Brainstorm", "Chicot", "Matador", "Mr. Bones", "Invisible Joker",
        "Troubadour", "Juggler", "Drunkard", "Merry Andy", "The Ox",
        "Burnt Joker", "Midas Mask", "Riff-Raff", "Certificate",
        "Marble Joker", "Luchador", "Perkeo", "Madness", "Burglar",
        "Cartomancer", "Sixth Sense",
    })
    _SUPPORTED_NAMES = frozenset(j.name for j in JOKER_LIBRARY) - _PLACEHOLDER_ONLY_NAMES

    def __init__(self, rng: Any | None = None):
        self.joker_states: Dict[str, Dict[str, Any]] = {}
        self.rng = rng
        self._fallback_rng = random.Random(0)
        self._active_joker_key: str | None = None

    @classmethod
    def supported_joker_names(cls) -> frozenset[str]:
        return cls._SUPPORTED_NAMES

    @classmethod
    def unsupported_joker_names(cls) -> frozenset[str]:
        return frozenset(j.name for j in JOKER_LIBRARY) - cls._SUPPORTED_NAMES

    def apply_joker_effect(
        self,
        joker: Any,
        context: Dict[str, Any],
        game_state: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        joker_name = self._joker_name(joker)
        if not joker_name or joker_name not in self._SUPPORTED_NAMES:
            return None

        phase = context.get("phase", "")
        self._active_joker_key = self._state_key(joker_name, context)
        if phase == "before_scoring":
            return self._before_scoring_effects(joker_name, context, game_state)
        if phase == "individual_scoring":
            return self._individual_scoring_effects(joker_name, context, game_state)
        if phase == "held_card":
            return self._held_card_effects(joker_name, context, game_state)
        if phase == "scoring":
            return self._scoring_effects(joker_name, context, game_state)
        if phase == "discard":
            return self._discard_effects(joker_name, context, game_state)
        if phase == "skip_blind":
            return self._skip_blind_effects(joker_name, context, game_state)
        if phase == "setting_blind":
            return self._setting_blind_effects(joker_name, game_state)
        if phase in {"pack_skip", "skipping_booster"}:
            return self._pack_skip_effects(joker_name)
        if phase in {"card_sold", "selling_card"}:
            return self._card_sold_effects(joker_name)
        if phase == "using_consumeable":
            return self._consumeable_effects(joker_name)
        return None

    def get_retrigger_count(
        self,
        joker: Any,
        context: Dict[str, Any],
        game_state: Dict[str, Any],
    ) -> int:
        joker_name = self._joker_name(joker)
        if not joker_name or joker_name not in self._SUPPORTED_NAMES:
            return 0

        phase = context.get("phase", "")
        card = context.get("card")
        if card is None:
            return 0

        if phase == "played_card":
            rank = self._rank(card)
            if joker_name == "Hanging Chad" and context.get("is_first_scoring_card"):
                return 2
            if joker_name == "Hack" and rank in {2, 3, 4, 5}:
                return 1
            if joker_name in {"Sock & Buskin", "Sock and Buskin"} and self._is_face(card, game_state):
                return 1
            if joker_name == "Dusk" and game_state.get("hands_left") == 0:
                return 1
            if joker_name == "Seltzer":
                state = self.joker_states.get(self._active_joker_key or joker_name, {})
                return 1 if state.get("rounds", 10) > 0 else 0
            return 0

        if phase == "held_card":
            if not context.get("effects_present"):
                return 0
            if joker_name == "Mime":
                return 1
            return 0

        return 0

    def _before_scoring_effects(
        self,
        joker_name: str,
        context: Dict[str, Any],
        game_state: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        scoring_cards = context.get("scoring_cards", [])
        full_hand = context.get("cards", [])
        hand_type = self._normalize_hand_type(context.get("hand_type"))

        if joker_name == "Green Joker":
            state = self._state(joker_name, mult=0)
            state["mult"] += 1
            return {"message": f"+1 Mult (now {state['mult']})"}
        if joker_name == "Ride the Bus":
            state = self._state(joker_name, mult=0)
            if any(self._is_face(card, game_state) for card in scoring_cards):
                state["mult"] = 0
                return {"message": "Reset"}
            state["mult"] += 1
            return {"message": f"+1 Mult (now {state['mult']})"}
        if joker_name == "Runner" and hand_type == "Straight":
            state = self._state(joker_name, chips=0)
            state["chips"] += 15
            return {"message": f"+15 Chips (now {state['chips']})"}
        if joker_name == "Square Joker" and len(full_hand) == 4:
            state = self._state(joker_name, chips=0)
            state["chips"] += 4
            return {"message": f"+4 Chips (now {state['chips']})"}
        if joker_name == "Spare Trousers" and hand_type in {"Two Pair", "Full House"}:
            state = self._state(joker_name, mult=0)
            state["mult"] += 2
            return {"message": f"+2 Mult (now {state['mult']})"}
        if joker_name == "Obelisk":
            state = self._state(joker_name, x_mult=1.0)
            if hand_type and hand_type != self._normalize_hand_type(game_state.get("most_played_hand")):
                state["x_mult"] = round(state["x_mult"] + 0.2, 10)
            else:
                state["x_mult"] = 1.0
            return {"message": f"x{state['x_mult']}"}
        if joker_name == "Red Card":
            return {"mult": 3 * int(game_state.get("packs_skipped", 0))}
        return None

    def _individual_scoring_effects(
        self,
        joker_name: str,
        context: Dict[str, Any],
        game_state: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        card = context.get("card")
        if card is None:
            return None

        rank = self._rank(card)
        suit = self._suit(card)

        if joker_name in self._RANK_INDIVIDUAL_JOKERS:
            ranks, effect = self._RANK_INDIVIDUAL_JOKERS[joker_name]
            if rank in ranks:
                return dict(effect)

        if joker_name in self._SUIT_INDIVIDUAL_JOKERS:
            target_suit, effect, *chance = self._SUIT_INDIVIDUAL_JOKERS[joker_name]
            if suit == target_suit and (not chance or self._roll(chance[0], "joker_effects")):
                return dict(effect)

        if joker_name == "8 Ball" and rank == 8 and self._roll(0.25, "joker_effects"):
            return {"created_consumable": "Tarot", "message": "Created Tarot"}
        if joker_name == "Scary Face" and self._is_face(card, game_state):
            return {"chips": 30}
        if joker_name == "Smiley Face" and self._is_face(card, game_state):
            return {"mult": 5}
        if joker_name == "Business Card" and self._is_face(card, game_state) and self._roll(0.5, "joker_effects"):
            return {"money": 2}
        if joker_name == "Golden Ticket" and self._enhancement(card) == "Gold":
            return {"money": 4}
        if joker_name == "Photograph" and self._is_face(card, game_state):
            state = self._state(joker_name, used=False)
            if not state["used"]:
                state["used"] = True
                return {"x_mult": 2}
        if joker_name == "Hanging Chad":
            state = self._state(joker_name, used=False)
            if not state["used"]:
                state["used"] = True
                return {"retriggers": 2, "message": "Retrigger first scoring card"}
        if joker_name == "Hack" and rank in {2, 3, 4, 5}:
            return {"retriggers": 1, "message": "Retrigger 2-5"}
        if joker_name == "Sock & Buskin" and self._is_face(card, game_state):
            return {"retriggers": 1, "message": "Retrigger face card"}
        if joker_name == "Dusk" and game_state.get("hands_left") == 0:
            return {"retriggers": 1, "message": "Retrigger final hand cards"}
        if joker_name == "Lucky Cat" and self._enhancement(card) == "Lucky":
            state = self._state(joker_name, x_mult=1.0)
            state["x_mult"] = round(state["x_mult"] + 0.25, 10)
            return {"message": f"x{state['x_mult']}"}
        if joker_name == "Vampire" and self._enhancement(card) not in {"None", None}:
            state = self._state(joker_name, x_mult=1.0)
            state["x_mult"] = round(state["x_mult"] + 0.1, 10)
            return {"message": f"x{state['x_mult']}"}
        return None

    def _held_card_effects(
        self,
        joker_name: str,
        context: Dict[str, Any],
        game_state: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        card = context.get("card")
        if card is None:
            return None

        if joker_name == "Shoot the Moon" and self._rank(card) == 12:
            return {"mult": 13}

        if joker_name == "Baron" and self._rank(card) == 13:
            return {"x_mult": 1.5}

        if joker_name == "Raised Fist":
            held_cards = game_state.get("held_cards") or game_state.get("hand", [])
            candidate_cards = [
                held_card
                for held_card in held_cards
                if self._enhancement(held_card) != "Stone"
            ]
            if not candidate_cards:
                return None
            lowest = min(candidate_cards, key=self._rank)
            if lowest is card:
                return {"mult": 2 * min(self._rank(card), 10)}

        return None

    def _scoring_effects(
        self,
        joker_name: str,
        context: Dict[str, Any],
        game_state: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        hand_type = self._normalize_hand_type(context.get("hand_type"))
        cards = context.get("cards", [])
        scoring_cards = context.get("scoring_cards", [])
        money = int(game_state.get("money", 0))

        static = self._static_scoring_effect(joker_name, cards, game_state)
        if static:
            return static

        if joker_name in self._HAND_TYPE_EFFECTS:
            required, effect = self._HAND_TYPE_EFFECTS[joker_name]
            if hand_type == required:
                return dict(effect)
        if joker_name in self._SUIT_MULT_JOKERS:
            target_suit, effect = self._SUIT_MULT_JOKERS[joker_name]
            if any(self._suit(card) == target_suit for card in scoring_cards):
                return dict(effect)
        if joker_name in {"Seance", "Séance"} and hand_type == "Straight Flush":
            return {"created_consumable": "Spectral"}

        if joker_name == "Blackboard" and self._blackboard_active(game_state):
            return {"x_mult": 3}
        if joker_name == "Seeing Double" and self._seeing_double_active(scoring_cards):
            return {"x_mult": 2}
        if joker_name == "Flower Pot" and len({self._suit(card) for card in scoring_cards}) >= 4:
            return {"x_mult": 3}
        if joker_name in {"Green Joker", "Ride the Bus"}:
            value = self._state(joker_name, mult=0)["mult"]
            return {"mult": value} if value else None
        if joker_name in {"Runner", "Square Joker"}:
            value = self._state(joker_name, chips=0)["chips"]
            return {"chips": value} if value else None
        if joker_name == "Spare Trousers":
            value = self._state(joker_name, mult=0)["mult"]
            return {"mult": value} if value else None
        if joker_name == "Ice Cream":
            state = self._state(joker_name, chips=100)
            chips = max(0, state["chips"])
            state["chips"] = max(0, chips - 5)
            return {"chips": chips} if chips else None
        if joker_name == "Popcorn":
            mult = self._state(joker_name, mult=20)["mult"]
            return {"mult": mult} if mult > 0 else None
        if joker_name == "Throwback":
            x_mult = self._state(joker_name, x_mult=1.0)["x_mult"]
            return {"x_mult": x_mult} if x_mult > 1 else None
        if joker_name == "Hit the Road":
            x_mult = self._state(joker_name, x_mult=1.0)["x_mult"]
            return {"x_mult": x_mult} if x_mult > 1 else None
        if joker_name == "Obelisk":
            x_mult = self._state(joker_name, x_mult=1.0)["x_mult"]
            return {"x_mult": x_mult} if x_mult > 1 else None
        if joker_name == "Constellation":
            return {"x_mult": 1 + 0.1 * len(game_state.get("unique_planet_cards_used", []))}
        if joker_name == "Hologram":
            return {"x_mult": 1 + 0.25 * int(game_state.get("cards_added_total", 0))}
        if joker_name == "Vampire":
            return {"x_mult": self._state(joker_name, x_mult=1.0)["x_mult"]}
        if joker_name == "Flash Card":
            return {"mult": 2 * int(game_state.get("rerolls_used", 0))}
        if joker_name == "Erosion":
            return {"mult": max(0, 52 - len(game_state.get("deck", []))) * 4}
        if joker_name == "Fortune Teller":
            return {"mult": int(game_state.get("tarot_cards_used", 0))}
        if joker_name == "Bull":
            return {"chips": 2 * money}
        if joker_name == "Bootstraps":
            return {"mult": 2 * (money // 5)}
        if joker_name == "Swashbuckler":
            return {"mult": self._joker_sell_total(game_state)}
        if joker_name == "Stone Joker":
            return {"chips": 25 * self._count_enhancement(game_state, "Stone")}
        if joker_name == "Steel Joker":
            return {"x_mult": 1 + 0.2 * self._count_enhancement(game_state, "Steel")}
        if joker_name == "Glass Joker":
            return {"x_mult": 1 + 0.75 * int(game_state.get("glass_cards_destroyed", 0))}
        if joker_name == "Cloud 9":
            return {"money": sum(1 for card in game_state.get("deck", []) if self._rank(card) == 9)}
        if joker_name == "Ancient Joker":
            target = game_state.get("ancient_suit")
            count = sum(1 for card in scoring_cards if self._suit(card) == target)
            return {"x_mult": 1.5 ** count} if count else None
        if joker_name == "The Idol":
            target_rank = game_state.get("idol_rank")
            target_suit = game_state.get("idol_suit")
            count = sum(
                1 for card in scoring_cards
                if self._rank(card) == target_rank and self._suit(card) == target_suit
            )
            return {"x_mult": 2 ** count} if count else None
        if joker_name == "Driver's License" and self._enhanced_count(game_state) >= 16:
            return {"x_mult": 3}
        if joker_name == "Canio":
            return {"x_mult": 1 + int(game_state.get("face_cards_destroyed", 0))}
        if joker_name == "Yorick":
            return {"x_mult": 1 + int(game_state.get("discarded_cards_total", 0)) // 23}
        if joker_name == "Ramen":
            return {"x_mult": max(1.0, 2.0 - 0.01 * int(game_state.get("cards_discarded_total", 0)))}
        if joker_name == "Seltzer":
            state = self._state(joker_name, rounds=10)
            return {"retriggers": 1} if state["rounds"] > 0 else None
        return None

    def _static_scoring_effect(self, joker_name: str, cards: List[Any], game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if joker_name == "Misprint":
            return {"mult": self._randint(0, 23, "joker_effects")}

        effects = {
            "Joker": {"mult": 4},
            "Stuntman": {"chips": 250},
            "Gros Michel": {"mult": 15},
            "Cavendish": {"x_mult": 3},
            "Abstract Joker": {"mult": 3 * len(game_state.get("jokers", []))},
            "Mystic Summit": {"mult": 15} if game_state.get("discards_left", 0) == 0 else None,
            "Banner": {"chips": 30 * game_state.get("discards_left", 0)},
            "Blue Joker": {"chips": 2 * len(game_state.get("draw_pile_indexes", game_state.get("deck", [])))},
            "Half Joker": {"mult": 20} if len(cards) <= 3 else None,
            "Acrobat": {"x_mult": 3} if game_state.get("hands_left", 1) == 1 else None,
            "Loyalty Card": {"x_mult": 4} if (int(game_state.get("hands_played", 0)) + 1) % 6 == 0 else None,
            "Supernova": {"mult": int(game_state.get("hands_played", 0))},
            "To Do List": {"money": 4} if game_state.get("todo_hand") == game_state.get("last_hand_played") else None,
            "Vagabond": {"created_consumable": "Tarot"} if game_state.get("money", 0) <= 4 else None,
        }
        return effects.get(joker_name)

    def _discard_effects(
        self,
        joker_name: str,
        context: Dict[str, Any],
        game_state: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        discarded = context.get("discarded_cards", [])
        first = bool(context.get("is_first_discard"))
        if joker_name == "Trading Card" and first and len(discarded) == 1:
            return {"money": 3}
        if joker_name == "Faceless Joker" and sum(self._is_face(card, game_state) for card in discarded) >= 3:
            return {"money": 5}
        if joker_name == "Mail-In Rebate":
            target_rank = (
                context.get("mail_in_rebate_rank")
                or context.get("mail_in_rebate_target_rank")
                or context.get("rebate_rank")
                or game_state.get("mail_in_rebate_rank")
                or game_state.get("mail_in_rebate_target_rank")
                or game_state.get("rebate_rank")
                or game_state.get("mail_rank")
            )
            matches = sum(1 for card in discarded if self._rank(card) == self._rank_value(target_rank))
            return {"money": 5 * matches} if matches else None
        if joker_name == "Green Joker":
            state = self._state(joker_name, mult=0)
            state["mult"] = max(0, state["mult"] - 1)
            return {"message": f"-1 Mult (now {state['mult']})"}
        if joker_name == "Hit the Road":
            jacks = sum(1 for card in discarded if self._rank(card) == 11)
            if jacks:
                state = self._state(joker_name, x_mult=1.0)
                state["x_mult"] = round(state["x_mult"] + 0.5 * jacks, 10)
                return {"message": f"x{state['x_mult']}"}
        if joker_name == "Castle":
            target_suit = game_state.get("castle_suit")
            matches = sum(1 for card in discarded if self._suit(card) == target_suit)
            if matches:
                state = self._state(joker_name, chips=0)
                state["chips"] += 3 * matches
                return {"chips": state["chips"]}
        return None

    def _skip_blind_effects(self, joker_name: str, context: Dict[str, Any], game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if joker_name == "Throwback":
            state = self._state(joker_name, x_mult=1.0)
            state["x_mult"] = round(state["x_mult"] + 0.25, 10)
            return {"message": f"x{state['x_mult']}"}
        if joker_name == "Diet Cola":
            return {"tag": "Double Tag"}
        return None

    def _setting_blind_effects(self, joker_name: str, game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._static_scoring_effect(joker_name, [], game_state)

    def _pack_skip_effects(self, joker_name: str) -> Optional[Dict[str, Any]]:
        if joker_name == "Red Card":
            state = self._state(joker_name, mult=0)
            state["mult"] += 3
            return {"message": f"+3 Mult (now {state['mult']})"}
        if joker_name == "Hallucination" and self._roll(0.5, "joker_effects"):
            return {"created_consumable": "Tarot"}
        return None

    def _card_sold_effects(self, joker_name: str) -> Optional[Dict[str, Any]]:
        if joker_name == "Campfire":
            state = self._state(joker_name, x_mult=1.0)
            state["x_mult"] = round(state["x_mult"] + 0.25, 10)
            return {"message": f"x{state['x_mult']}"}
        if joker_name == "Diet Cola":
            return {"tag": "Double Tag"}
        return None

    def _consumeable_effects(self, joker_name: str) -> Optional[Dict[str, Any]]:
        if joker_name == "Fortune Teller":
            state = self._state(joker_name, mult=0)
            state["mult"] += 1
            return {"message": f"+1 Mult (now {state['mult']})"}
        if joker_name == "Constellation":
            state = self._state(joker_name, x_mult=1.0)
            state["x_mult"] = round(state["x_mult"] + 0.1, 10)
            return {"message": f"x{state['x_mult']}"}
        return None

    def end_of_round_effects(self, game_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        effects: List[Dict[str, Any]] = []
        for joker_index, joker_name in enumerate(self._joker_names(game_state)):
            self._active_joker_key = self._round_state_key(joker_index, joker_name)
            if joker_name == "Popcorn":
                state = self._state(joker_name, mult=20)
                state["mult"] -= 4
                if state["mult"] <= 0:
                    effects.append({"destroy_joker": joker_name, "destroy_joker_index": joker_index})
            elif joker_name == "Gros Michel" and self._roll(1 / 6, "joker_effects"):
                effects.append({
                    "destroy_joker": joker_name,
                    "destroy_joker_index": joker_index,
                    "set_flag": "gros_michel_extinct",
                })
            elif joker_name == "Cavendish" and self._roll(1 / 1000, "joker_effects"):
                effects.append({"destroy_joker": joker_name, "destroy_joker_index": joker_index})
            elif joker_name == "Turtle Bean":
                state = self._state(joker_name, hand_size=5)
                state["hand_size"] -= 1
                if state["hand_size"] <= 0:
                    effects.append({"destroy_joker": joker_name, "destroy_joker_index": joker_index})
            elif joker_name == "Seltzer":
                state = self._state(joker_name, rounds=10)
                state["rounds"] -= 1
                if state["rounds"] <= 0:
                    effects.append({"destroy_joker": joker_name, "destroy_joker_index": joker_index})
            elif joker_name == "Campfire":
                self._state(joker_name, x_mult=1.0)["x_mult"] = 1.0
        return effects

    def reset_scoring_hand_state(self, game_state: Dict[str, Any]) -> None:
        """Reset per-play flags for jokers that trigger once per scored hand."""
        for joker_index, joker_name in enumerate(self._joker_names(game_state)):
            if joker_name not in {"Photograph", "Hanging Chad"}:
                continue
            for key in (self._round_state_key(joker_index, joker_name), joker_name):
                state = self.joker_states.get(key)
                if state is not None:
                    state["used"] = False

    def _state(self, joker_name: str, **defaults: Any) -> Dict[str, Any]:
        state = self.joker_states.setdefault(self._active_joker_key or joker_name, {})
        for key, value in defaults.items():
            state.setdefault(key, value)
        return state

    @staticmethod
    def _state_key(joker_name: str, context: Dict[str, Any]) -> str:
        joker_index = context.get("joker_index")
        if joker_index is None:
            return joker_name
        return f"{joker_index}:{joker_name}"

    def _round_state_key(self, joker_index: int, joker_name: str) -> str:
        indexed_key = f"{joker_index}:{joker_name}"
        if indexed_key not in self.joker_states and joker_name in self.joker_states:
            return joker_name
        return indexed_key

    def _roll(self, chance: float, stream: str) -> bool:
        if self.rng is not None and hasattr(self.rng, "get_float"):
            return self.rng.get_float(stream) < chance
        return self._fallback_rng.random() < chance

    def _randint(self, low: int, high: int, stream: str) -> int:
        if self.rng is not None and hasattr(self.rng, "get_int"):
            return self.rng.get_int(stream, low, high)
        return self._fallback_rng.randint(low, high)

    @staticmethod
    def _joker_name(joker: Any) -> Optional[str]:
        if isinstance(joker, str):
            return joker
        if isinstance(joker, dict):
            name = joker.get("name")
            return name if isinstance(name, str) else None
        name = getattr(joker, "name", None)
        return name if isinstance(name, str) else None

    def _joker_names(self, game_state: Dict[str, Any]) -> Iterable[str]:
        for joker in game_state.get("jokers", []):
            name = self._joker_name(joker)
            if name:
                yield name

    @staticmethod
    def _rank(card: Any) -> int:
        rank = getattr(card, "rank", card)
        return rank.value if isinstance(rank, IntEnum) else int(rank or 0)

    @staticmethod
    def _rank_value(value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, Rank):
            return value.value
        if isinstance(value, IntEnum):
            return int(value.value)
        if isinstance(value, str):
            key = value.strip().replace(" ", "_").upper()
            if key in Rank.__members__:
                return Rank[key].value
        return int(value)

    @staticmethod
    def _suit(card: Any) -> str:
        suit = getattr(card, "suit", card)
        if isinstance(suit, Suit):
            return suit.name.title()
        if isinstance(suit, IntEnum):
            return suit.name.title()
        return str(suit).title()

    @staticmethod
    def _enhancement(card: Any) -> str:
        enhancement = getattr(card, "enhancement", Enhancement.NONE)
        if isinstance(enhancement, Enhancement):
            return enhancement.name.title()
        if isinstance(enhancement, IntEnum):
            return enhancement.name.title()
        return str(enhancement).title()

    def _is_face(self, card: Any, game_state: Dict[str, Any]) -> bool:
        return bool(game_state.get("pareidolia_active")) or self._rank(card) in {11, 12, 13}

    def _blackboard_active(self, game_state: Dict[str, Any]) -> bool:
        hand = game_state.get("hand", [])
        return bool(hand) and all(self._suit(card) in {"Spades", "Clubs"} for card in hand)

    def _seeing_double_active(self, cards: List[Any]) -> bool:
        suits = {self._suit(card) for card in cards}
        return "Clubs" in suits and len(suits - {"Clubs"}) > 0

    @staticmethod
    def _normalize_hand_type(hand_type: Any) -> str:
        text = str(hand_type or "").replace("_", " ").strip().title()
        aliases = {
            "One Pair": "Pair",
            "Three Kind": "Three of a Kind",
            "Four Kind": "Four of a Kind",
            "Five Kind": "Five of a Kind",
        }
        return aliases.get(text, text)

    def _enhanced_count(self, game_state: Dict[str, Any]) -> int:
        return int(game_state.get("enhanced_card_count", self._count_enhancement(game_state, None)))

    def _count_enhancement(self, game_state: Dict[str, Any], enhancement_name: Optional[str]) -> int:
        count = 0
        for card in game_state.get("deck", []):
            enhancement = self._enhancement(card)
            if enhancement_name is None:
                count += int(enhancement not in {"None", "0"})
            elif enhancement == enhancement_name:
                count += 1
        return count

    @staticmethod
    def _joker_sell_total(game_state: Dict[str, Any]) -> int:
        total = 0
        for joker in game_state.get("jokers", []):
            if isinstance(joker, dict):
                total += int(joker.get("sell_value", joker.get("base_cost", 0)) or 0)
            else:
                total += int(getattr(joker, "base_cost", 0) or 0)
        return total
