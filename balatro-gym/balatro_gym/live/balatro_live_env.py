"""
balatro_gym/balatro_live_env.py

Gymnasium environment backed by a real Balatro instance via balatrobot.

Drop-in replacement for BalatroEnv: identical observation_space and
action_space so the existing training script works unchanged.

Usage:
    # Launch Balatro first (in a separate terminal):
    #   uvx balatrobot serve --fast --headless --no-shaders \\
    #       --fps-cap 5 --gamespeed 16 --animation-fps 1 --port 12345

    env = BalatroLiveEnv(port=12345)
    obs, info = env.reset()
    obs, reward, terminated, truncated, info = env.step(action)

    # N parallel envs wired to N Balatro instances:
    from stable_baselines3.common.vec_env import SubprocVecEnv
    def make_env(port):
        return lambda: BalatroLiveEnv(port=port)
    vec_env = SubprocVecEnv([make_env(12345 + i) for i in range(4)])
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

import numpy as np
import gymnasium as gym
from gymnasium import spaces

from balatro_gym.core.constants import Phase, Action, ActionCounts

# ---------------------------------------------------------------------------
# Load BalatroClient directly from vendored source to avoid importing the
# full balatrobot package (which pulls in typer via its __init__ chain).
# ---------------------------------------------------------------------------
import importlib.util as _ilu
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLIENT_PY = _REPO_ROOT / "balatrobot" / "src" / "balatrobot" / "cli" / "client.py"
_spec = _ilu.spec_from_file_location("balatrobot_client", _CLIENT_PY)
_client_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_client_mod)
BalatroClient = _client_mod.BalatroClient
APIError = _client_mod.APIError

import httpx  # noqa: E402

# ---------------------------------------------------------------------------
# Card encoding helpers
# ---------------------------------------------------------------------------

SUIT_MAP = {"H": 0, "D": 1, "C": 2, "S": 3}
RANK_MAP = {
    "2": 0, "3": 1, "4": 2, "5": 3, "6": 4,
    "7": 5, "8": 6, "9": 7, "T": 8, "J": 9,
    "Q": 10, "K": 11, "A": 12,
}

# Map balatrobot game state strings → Phase enum
STATE_TO_PHASE = {
    "BLIND_SELECT": Phase.BLIND_SELECT,
    "SELECTING_HAND": Phase.PLAY,
    "HAND_PLAYED": Phase.PLAY,
    "DRAW_TO_HAND": Phase.PLAY,
    "NEW_ROUND": Phase.PLAY,
    "SHOP": Phase.SHOP,
    "SMODS_BOOSTER_OPENED": Phase.PACK_OPEN,
}

# States that require polling until they settle into a stable state
_TRANSITIONAL = {"HAND_PLAYED", "DRAW_TO_HAND", "NEW_ROUND"}

# Poker hand names in the order we expose them (index 0-11)
HAND_NAME_ORDER = [
    "High Card", "Pair", "Two Pair", "Three of a Kind",
    "Straight", "Flush", "Full House", "Four of a Kind",
    "Straight Flush", "Five of a Kind", "Flush House", "Flush Five",
]

# Consumable label → integer ID (matches balatro_env_2.py)
_CONSUMABLE_ID_MAP: dict[str, int] = {
    "The Fool": 1, "The Magician": 2, "The High Priestess": 3,
    "The Empress": 4, "The Emperor": 5, "The Hierophant": 6,
    "The Lovers": 7, "The Chariot": 8, "Strength": 9,
    "The Hermit": 10, "Wheel of Fortune": 11, "Justice": 12,
    "The Hanged Man": 13, "Death": 14, "Temperance": 15,
    "The Devil": 16, "The Tower": 17, "The Star": 18,
    "The Moon": 19, "The Sun": 20, "Judgement": 21, "The World": 22,
    "Mercury": 30, "Venus": 31, "Earth": 32, "Mars": 33,
    "Jupiter": 34, "Saturn": 35, "Uranus": 36, "Neptune": 37,
    "Pluto": 38, "Planet X": 39, "Ceres": 40, "Eris": 41,
    "Familiar": 50, "Grim": 51, "Incantation": 52, "Talisman": 53,
    "Aura": 54, "Wraith": 55, "Sigil": 56, "Ouija": 57,
    "Ectoplasm": 58, "Immolate": 59, "Ankh": 60, "Deja Vu": 61,
    "Hex": 62, "Trance": 63, "Medium": 64, "Cryptid": 65,
    "The Soul": 66, "Black Hole": 67,
}

# Joker label sets for type-flag observations
_MULT_JOKERS = {
    "Crazy Joker", "Jolly Joker", "Zany Joker", "Mad Joker", "Devious Joker",
    "Crafty Joker", "Half Joker", "Joker Stencil", "Four Fingers", "Mime",
    "Ceremonial Dagger", "Banner", "Mystic Summit", "Marble Joker", "Loyalty Card",
    "Misprint", "Dusk", "Raised Fist", "Chaos the Clown", "Fibonacci",
    "Steel Joker", "Scary Face", "Abstract Joker", "Delayed Gratification",
    "Pareidolia", "Even Steven", "Odd Todd", "Scholar", "Business Card",
    "Supernova", "Ride the Bus", "Space Joker",
}
_CHIP_JOKERS = {
    "Joker", "Greedy Joker", "Lusty Joker", "Wrathful Joker", "Gluttonous Joker",
    "Fibonacci", "Scary Face", "Scholar", "Business Card", "Bootstraps",
}
_XMULT_JOKERS = {
    "Baron", "Baseball Card", "Ancient Joker", "Campfire", "Blueprint", "Brainstorm",
}
_ECONOMY_JOKERS = {
    "To Do List", "Credit Card", "Delayed Gratification", "Bootstraps",
    "Mr. Bones", "Acrobat", "Sock and Buskin", "Swashbuckler", "Egg",
    "Burglar", "Blackboard", "Reserved Parking", "Mail-In Rebate",
    "To the Moon", "Gift Card", "Turtle Bean", "Erosion", "Flash Card",
    "Popcorn", "Ramen", "Satellite", "Shoot the Moon", "Castle",
    "Wee Joker", "Hologram",
}


def _joker_key_to_id(key: str) -> int:
    """Stable hash of a joker key to an integer in [1, 200]. 0 = empty slot."""
    return (hash(key) % 199) + 1


# ---------------------------------------------------------------------------
# BalatroLiveEnv
# ---------------------------------------------------------------------------

class BalatroLiveEnv(gym.Env):
    """
    Gymnasium environment that drives a real Balatro instance via balatrobot.

    Identical observation_space / action_space to BalatroEnv so training
    scripts need no changes. The caller is responsible for launching
    Balatro before creating this env.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        port: int = 12346,
        host: str = "127.0.0.1",
        timeout: float = 60.0,
        max_episode_steps: int = 10_000,
        render_mode: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.client = BalatroClient(host=host, port=port, timeout=min(timeout, 10.0))
        self.render_mode = render_mode
        self.max_episode_steps = max_episode_steps

        self.action_space = spaces.Discrete(ActionCounts.ACTION_SPACE_SIZE)
        self.observation_space = self._create_observation_space()

        # Internal bookkeeping (not visible to agent)
        self._selected: list[int] = []     # 0-based hand indices currently toggled
        self._gs: dict = {}                # last gamestate from the API
        self._total_chips: int = 0         # cumulative chips scored across all hands
        self._best_hand_score: int = 0     # best single-hand score this ante
        self._hands_played: int = 0        # total hands played this episode
        self._prev_round_chips: int = 0    # round chips before last action (for delta)
        self._prev_progress: float = 0.0
        self._step_count: int = 0

    # ------------------------------------------------------------------
    # Observation space — must match balatro_env_2.py exactly
    # ------------------------------------------------------------------

    def _create_observation_space(self) -> spaces.Dict:
        S = ActionCounts.ACTION_SPACE_SIZE
        return spaces.Dict({
            "hand": spaces.Box(-1, 51, (8,), dtype=np.int8),
            "hand_size": spaces.Box(0, 12, (), dtype=np.int8),
            "deck_size": spaces.Box(0, 52, (), dtype=np.int8),
            "selected_cards": spaces.MultiBinary(8),

            "chips_scored": spaces.Box(0, 10_000_000_000, (), dtype=np.int64),
            "round_chips_scored": spaces.Box(0, 10_000_000, (), dtype=np.int32),
            "progress_ratio": spaces.Box(0.0, 2.0, (), dtype=np.float32),
            "mult": spaces.Box(0, 10_000, (), dtype=np.int32),
            "chips_needed": spaces.Box(0, 10_000_000, (), dtype=np.int32),
            "money": spaces.Box(-20, 999, (), dtype=np.int32),

            "ante": spaces.Box(1, 1000, (), dtype=np.int16),
            "round": spaces.Box(1, 3, (), dtype=np.int8),
            "hands_left": spaces.Box(0, 12, (), dtype=np.int8),
            "discards_left": spaces.Box(0, 10, (), dtype=np.int8),

            "joker_count": spaces.Box(0, 10, (), dtype=np.int8),
            "joker_ids": spaces.Box(0, 200, (10,), dtype=np.int16),
            "joker_slots": spaces.Box(0, 10, (), dtype=np.int8),

            "consumable_count": spaces.Box(0, 5, (), dtype=np.int8),
            "consumables": spaces.Box(0, 100, (5,), dtype=np.int16),
            "consumable_slots": spaces.Box(0, 5, (), dtype=np.int8),

            "shop_items": spaces.Box(0, 300, (10,), dtype=np.int16),
            "shop_costs": spaces.Box(0, 5000, (10,), dtype=np.int16),
            "shop_rerolls": spaces.Box(0, 999, (), dtype=np.int16),

            "hand_levels": spaces.Box(0, 15, (12,), dtype=np.int8),
            "phase": spaces.Box(0, 3, (), dtype=np.int8),
            "action_mask": spaces.MultiBinary(S),

            "hands_played": spaces.Box(0, 10000, (), dtype=np.int32),
            "best_hand_this_ante": spaces.Box(0, 10_000_000, (), dtype=np.int32),

            "boss_blind_active": spaces.Box(0, 1, (), dtype=np.int8),
            "boss_blind_type": spaces.Box(0, 30, (), dtype=np.int8),
            "face_down_cards": spaces.MultiBinary(8),

            "hand_one_hot": spaces.Box(0, 1, (8, 52), dtype=np.float32),
            "hand_suits": spaces.Box(0, 4, (8,), dtype=np.int8),
            "hand_ranks": spaces.Box(0, 13, (8,), dtype=np.int8),

            "rank_counts": spaces.Box(0, 4, (13,), dtype=np.int8),
            "suit_counts": spaces.Box(0, 8, (4,), dtype=np.int8),
            "straight_potential": spaces.Box(0, 1, (), dtype=np.float32),
            "flush_potential": spaces.Box(0, 1, (), dtype=np.float32),

            "avg_score_per_hand": spaces.Box(0, 10000, (), dtype=np.float32),
            "hands_until_shop": spaces.Box(0, 20, (), dtype=np.int8),
            "rounds_until_boss": spaces.Box(0, 3, (), dtype=np.int8),

            "has_mult_jokers": spaces.Box(0, 1, (), dtype=np.int8),
            "has_chip_jokers": spaces.Box(0, 1, (), dtype=np.int8),
            "has_xmult_jokers": spaces.Box(0, 1, (), dtype=np.int8),
            "has_economy_jokers": spaces.Box(0, 1, (), dtype=np.int8),
            "hand_potential_scores": spaces.Box(0, 10000, (12,), dtype=np.int32),
            "joker_synergy_score": spaces.Box(0, 10, (), dtype=np.float32),
            "risk_level": spaces.Box(0, 1, (), dtype=np.float32),
            "economy_health": spaces.Box(0, 1, (), dtype=np.float32),

            "blind_difficulty": spaces.Box(0, 1, (), dtype=np.float32),
            "win_probability": spaces.Box(0, 1, (), dtype=np.float32),
        })

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)

        self._selected = []
        self._total_chips = 0
        self._best_hand_score = 0
        self._hands_played = 0
        self._prev_round_chips = 0
        self._prev_progress = 0.0
        self._step_count = 0

        # Attempt to return to the main menu (may already be there)
        try:
            self.client.call("menu")
        except (APIError, httpx.HTTPError):
            pass

        self._gs = self.client.call("start", {"deck": "RED", "stake": "WHITE"})
        return self._build_obs(), {"state": self._gs.get("state")}

    # ------------------------------------------------------------------
    # Step
    # ------------------------------------------------------------------

    def step(self, action: int):
        action = int(action)  # numpy int64 → Python int so httpx can JSON-serialize it
        self._step_count += 1
        if self._step_count >= self.max_episode_steps:
            return self._build_obs(), 0.0, False, True, {"truncated": "max_steps"}

        # Settle any pending animations before acting
        state_str = self._gs.get("state", "UNKNOWN")
        if state_str in _TRANSITIONAL or state_str == "ROUND_EVAL":
            self._gs = self._advance_to_stable(self._gs)

        phase = STATE_TO_PHASE.get(self._gs.get("state", ""), Phase.PLAY)

        try:
            if phase == Phase.PLAY:
                return self._step_play(action)
            elif phase == Phase.SHOP:
                return self._step_shop(action)
            elif phase == Phase.BLIND_SELECT:
                return self._step_blind(action)
            elif phase == Phase.PACK_OPEN:
                return self._step_pack(action)
            else:
                return self._build_obs(), -1.0, False, False, {
                    "error": f"unhandled state: {self._gs.get('state')}"
                }
        except APIError as e:
            return self._build_obs(), -1.0, False, False, {
                "error": e.name, "message": e.message
            }
        except (httpx.ConnectError, httpx.TimeoutException):
            return self._build_obs(), -10.0, True, False, {"error": "connection_lost"}

    # ------------------------------------------------------------------
    # Phase handlers
    # ------------------------------------------------------------------

    def _step_play(self, action: int):
        gs = self._gs
        round_info = gs.get("round") or {}
        hand_cards = (gs.get("hand") or {}).get("cards") or []
        chips_needed = self._get_chips_needed(gs)
        round_chips = round_info.get("chips", 0)
        old_progress = min(1.0, round_chips / max(1, chips_needed))

        if action == Action.PLAY_HAND:
            if not self._selected:
                return self._build_obs(), -1.0, False, False, {"error": "no cards selected"}
            new_gs = self.client.call("play", {"cards": sorted(self._selected)})
            self._selected = []
            self._hands_played += 1
            return self._resolve_after_play(new_gs, round_chips, old_progress, chips_needed)

        elif action == Action.DISCARD:
            if not self._selected:
                return self._build_obs(), -1.0, False, False, {"error": "no cards selected"}
            if round_info.get("discards_left", 0) <= 0:
                return self._build_obs(), -1.0, False, False, {"error": "no discards left"}
            self._gs = self.client.call("discard", {"cards": sorted(self._selected)})
            self._selected = []
            return self._build_obs(), 0.0, False, False, {"action": "discard"}

        elif Action.SELECT_CARD_BASE <= action < Action.SELECT_CARD_BASE + ActionCounts.SELECT_CARD_COUNT:
            idx = action - Action.SELECT_CARD_BASE
            if idx >= len(hand_cards):
                return self._build_obs(), -1.0, False, False, {"error": "card idx out of range"}
            if idx in self._selected:
                self._selected.remove(idx)
            else:
                self._selected.append(idx)
            return self._build_obs(), 0.0, False, False, {"selected": self._selected[:]}

        elif Action.USE_CONSUMABLE_BASE <= action < Action.USE_CONSUMABLE_BASE + ActionCounts.USE_CONSUMABLE_COUNT:
            i = action - Action.USE_CONSUMABLE_BASE
            self._gs = self.client.call("use", {"consumable": i})
            return self._build_obs(), 0.5, False, False, {"action": "use_consumable"}

        return self._build_obs(), -1.0, False, False, {"error": "invalid play action"}

    def _step_shop(self, action: int):
        gs = self._gs

        if Action.SHOP_BUY_BASE <= action < Action.SHOP_BUY_BASE + ActionCounts.SHOP_BUY_COUNT:
            i = action - Action.SHOP_BUY_BASE
            # Determine if this is a pack or a card slot
            shop_cards = (gs.get("shop") or {}).get("cards") or []
            if i < len(shop_cards):
                self._gs = self.client.call("buy", {"card": i})
            else:
                pack_i = i - len(shop_cards)
                self._gs = self.client.call("buy", {"pack": pack_i})
            return self._build_obs(), 0.5, False, False, {"action": "buy"}

        elif action == Action.SHOP_REROLL:
            self._gs = self.client.call("reroll")
            return self._build_obs(), 0.0, False, False, {"action": "reroll"}

        elif action == Action.SHOP_END:
            self._gs = self.client.call("next_round")
            return self._build_obs(), 0.0, False, False, {"action": "next_round"}

        elif Action.SELL_JOKER_BASE <= action < Action.SELL_JOKER_BASE + ActionCounts.SELL_JOKER_COUNT:
            i = action - Action.SELL_JOKER_BASE
            self._gs = self.client.call("sell", {"joker": i})
            return self._build_obs(), 0.3, False, False, {"action": "sell_joker"}

        elif Action.SELL_CONSUMABLE_BASE <= action < Action.SELL_CONSUMABLE_BASE + ActionCounts.SELL_CONSUMABLE_COUNT:
            i = action - Action.SELL_CONSUMABLE_BASE
            self._gs = self.client.call("sell", {"consumable": i})
            return self._build_obs(), 0.1, False, False, {"action": "sell_consumable"}

        return self._build_obs(), -1.0, False, False, {"error": "invalid shop action"}

    def _step_blind(self, action: int):
        if Action.SELECT_BLIND_BASE <= action < Action.SELECT_BLIND_BASE + ActionCounts.SELECT_BLIND_COUNT:
            self._gs = self.client.call("select")
            self._selected = []
            self._prev_round_chips = 0
            self._prev_progress = 0.0
            self._best_hand_score = 0
            return self._build_obs(), 0.0, False, False, {"action": "select_blind"}

        elif action == Action.SKIP_BLIND:
            self._gs = self.client.call("skip")
            return self._build_obs(), 0.0, False, False, {"action": "skip_blind"}

        return self._build_obs(), -1.0, False, False, {"error": "invalid blind action"}

    def _step_pack(self, action: int):
        if Action.SELECT_FROM_PACK_BASE <= action < Action.SELECT_FROM_PACK_BASE + ActionCounts.SELECT_FROM_PACK_COUNT:
            i = action - Action.SELECT_FROM_PACK_BASE
            self._gs = self.client.call("pack", {"card": i})
            return self._build_obs(), 0.5, False, False, {"action": "select_pack"}

        elif action == Action.SKIP_PACK:
            self._gs = self.client.call("pack", {"skip": True})
            return self._build_obs(), 0.0, False, False, {"action": "skip_pack"}

        return self._build_obs(), -1.0, False, False, {"error": "invalid pack action"}

    # ------------------------------------------------------------------
    # Post-play: settle state + compute reward
    # ------------------------------------------------------------------

    def _resolve_after_play(
        self,
        new_gs: dict,
        old_chips: int,
        old_progress: float,
        chips_needed: int,
    ) -> tuple:
        # Settle transitional states (HAND_PLAYED → SELECTING_HAND, ROUND_EVAL → SHOP, etc.)
        new_gs = self._advance_to_stable(new_gs)
        self._gs = new_gs

        state_str = new_gs.get("state", "UNKNOWN")
        terminated = state_str == "GAME_OVER" or new_gs.get("won", False)

        round_info = new_gs.get("round") or {}
        new_chips_needed = self._get_chips_needed(new_gs)
        new_round_chips = round_info.get("chips", 0)
        new_progress = min(1.0, new_round_chips / max(1, new_chips_needed))

        score_delta = max(0, new_round_chips - old_chips)
        self._total_chips += score_delta
        self._best_hand_score = max(self._best_hand_score, score_delta)
        ante = new_gs.get("ante_num", 1)

        # 1. Progress reward
        progress_reward = 15.0 * new_progress

        # 2. Milestone bonuses
        milestone_reward = 0.0
        if old_progress < 0.25 <= new_progress:
            milestone_reward = 5.0
        elif old_progress < 0.5 <= new_progress:
            milestone_reward = 10.0
        elif old_progress < 0.75 <= new_progress:
            milestone_reward = 15.0
        elif old_progress < 1.0 <= new_progress:
            milestone_reward = 25.0

        # 3. Score delta reward, scaled by ante
        if ante <= 3:
            score_reward = min(10.0, score_delta / 100.0)
        else:
            score_reward = min(10.0, 3.0 * float(np.log10(max(1, score_delta))))

        # 4. Ante progression bonus
        ante_bonus = min(5.0, (ante - 3) * 0.5) if ante >= 4 else 0.0

        # 5. Beat-blind bonus (game moved to SHOP or BLIND_SELECT after win)
        beat_bonus = 0.0
        beat_blind = state_str in ("SHOP", "BLIND_SELECT") or new_gs.get("won", False)
        if beat_blind:
            beat_bonus = min(50.0, 25.0 + 10.0 * ante)

        # 6. Failure penalty
        failure_penalty = 0.0
        if terminated and not new_gs.get("won", False) and not beat_blind:
            failure_penalty = -50.0 * (1.0 - new_progress)

        reward = min(
            100.0,
            progress_reward + milestone_reward + score_reward +
            ante_bonus + beat_bonus + failure_penalty,
        )

        self._prev_round_chips = new_round_chips
        self._prev_progress = new_progress

        return (
            self._build_obs(),
            float(reward),
            bool(terminated),
            False,
            {
                "beat_blind": beat_blind,
                "failed": bool(terminated and not new_gs.get("won", False)),
                "score_delta": score_delta,
                "progress": new_progress,
            },
        )

    # ------------------------------------------------------------------
    # State advancement (auto-flows through animations and round eval)
    # ------------------------------------------------------------------

    def _advance_to_stable(self, gs: dict, max_polls: int = 30) -> dict:
        """
        Advance through transitional states automatically:
          - HAND_PLAYED / DRAW_TO_HAND / NEW_ROUND → poll until settled
          - ROUND_EVAL → call cash_out, then poll
        Returns the first stable gamestate.
        """
        for _ in range(max_polls):
            state_str = gs.get("state", "UNKNOWN")

            if state_str == "ROUND_EVAL":
                try:
                    gs = self.client.call("cash_out")
                except APIError:
                    gs = self.client.call("gamestate")
                continue

            if state_str in _TRANSITIONAL:
                time.sleep(0.01)
                gs = self.client.call("gamestate")
                continue

            # Stable state
            return gs

        return gs

    # ------------------------------------------------------------------
    # Observation builder
    # ------------------------------------------------------------------

    def _build_obs(self) -> dict[str, Any]:
        gs = self._gs
        if not gs:
            return {k: sp.sample() * 0 for k, sp in self.observation_space.spaces.items()}

        state_str = gs.get("state", "UNKNOWN")
        phase = STATE_TO_PHASE.get(state_str, Phase.PLAY)

        round_info = gs.get("round") or {}
        blinds = gs.get("blinds") or {}
        hand_area = gs.get("hand") or {}
        jokers_area = gs.get("jokers") or {}
        consumables_area = gs.get("consumables") or {}
        shop_area = gs.get("shop") or {}
        packs_area = gs.get("packs") or {}
        pack_area = gs.get("pack") or {}
        deck_area = gs.get("cards") or {}

        hand_cards = hand_area.get("cards") or []
        joker_cards = jokers_area.get("cards") or []
        consumable_cards = consumables_area.get("cards") or []
        shop_cards = shop_area.get("cards") or []
        pack_cards = pack_area.get("cards") or []

        # --- Encode hand cards ---
        hand_array = np.full(8, -1, dtype=np.int8)
        hand_one_hot = np.zeros((8, 52), dtype=np.float32)
        hand_suits_arr = np.zeros(8, dtype=np.int8)
        hand_ranks_arr = np.zeros(8, dtype=np.int8)
        rank_counts = np.zeros(13, dtype=np.int8)
        suit_counts = np.zeros(4, dtype=np.int8)

        for i, card in enumerate(hand_cards[:8]):
            val = card.get("value") or {}
            suit_ch = val.get("suit")
            rank_ch = val.get("rank")
            if suit_ch in SUIT_MAP and rank_ch in RANK_MAP:
                s = SUIT_MAP[suit_ch]
                r = RANK_MAP[rank_ch]
                enc = r * 4 + s
                hand_array[i] = enc
                hand_one_hot[i, enc] = 1.0
                hand_suits_arr[i] = s
                hand_ranks_arr[i] = r
                rank_counts[r] = min(4, rank_counts[r] + 1)
                suit_counts[s] = min(8, suit_counts[s] + 1)

        # --- Jokers ---
        joker_ids = np.zeros(10, dtype=np.int16)
        joker_labels: list[str] = []
        for i, jk in enumerate(joker_cards[:10]):
            joker_ids[i] = _joker_key_to_id(jk.get("key", ""))
            joker_labels.append(jk.get("label", ""))

        # --- Consumables ---
        cons_ids = np.zeros(5, dtype=np.int16)
        for i, c in enumerate(consumable_cards[:5]):
            cons_ids[i] = _CONSUMABLE_ID_MAP.get(c.get("label", ""), 0)

        # --- Shop (cards + packs merged into 10 slots) ---
        shop_items = np.zeros(10, dtype=np.int16)
        shop_costs = np.zeros(10, dtype=np.int16)
        _SET_TO_INT = {
            "JOKER": 1, "TAROT": 2, "PLANET": 3,
            "SPECTRAL": 4, "VOUCHER": 5, "BOOSTER": 6,
        }
        pack_cards_shop = (packs_area.get("cards") or [])
        all_shop = list(shop_cards) + list(pack_cards_shop)
        for i, item in enumerate(all_shop[:10]):
            shop_items[i] = _SET_TO_INT.get(item.get("set", ""), 0)
            shop_costs[i] = (item.get("cost") or {}).get("buy", 0)

        # --- Score / progress ---
        chips_needed = self._get_chips_needed(gs)
        round_chips = round_info.get("chips", 0)
        progress_ratio = min(2.0, round_chips / max(1, chips_needed))

        # --- Hand levels ---
        hand_levels_arr = np.zeros(12, dtype=np.int8)
        hands_data = gs.get("hands") or {}
        for i, hname in enumerate(HAND_NAME_ORDER):
            info = hands_data.get(hname) or {}
            hand_levels_arr[i] = min(15, info.get("level", 1))

        # --- Derived features ---
        straight_pot = self._straight_potential(hand_ranks_arr, len(hand_cards))
        flush_pot = float(np.max(suit_counts)) / 5.0
        flush_pot = min(1.0, flush_pot)

        ante = gs.get("ante_num", 1)
        round_num = gs.get("round_num", 1)
        hands_left = round_info.get("hands_left", 4)
        discards_left = round_info.get("discards_left", 3)
        reroll_cost = round_info.get("reroll_cost", 5)
        money = gs.get("money", 0)

        # Boss blind: round 3 with CURRENT status
        boss_info = blinds.get("boss") or {}
        is_boss = int(round_num == 3 and boss_info.get("status") == "CURRENT")

        # Joker type flags
        has_mult = int(any(lbl in _MULT_JOKERS for lbl in joker_labels))
        has_chip = int(any(lbl in _CHIP_JOKERS for lbl in joker_labels))
        has_xmult = int(any(lbl in _XMULT_JOKERS for lbl in joker_labels))
        has_econ = int(any(lbl in _ECONOMY_JOKERS for lbl in joker_labels))

        risk_level = float(max(0.0, 1.0 - min(1.0, progress_ratio)))
        economy_health = float(min(1.0, money / 20.0))

        return {
            "hand": hand_array,
            "hand_size": np.int8(len(hand_cards)),
            "deck_size": np.int8(deck_area.get("count", 52)),
            "selected_cards": np.array(
                [1 if i in self._selected else 0 for i in range(8)], dtype=np.int8
            ),

            "chips_scored": np.int64(max(0, self._total_chips)),
            "round_chips_scored": np.int32(max(0, round_chips)),
            "progress_ratio": np.float32(progress_ratio),
            "mult": np.int32(1),
            "chips_needed": np.int32(max(0, chips_needed)),
            "money": np.int32(money),

            "ante": np.int16(max(1, ante)),
            "round": np.int8(max(1, min(3, round_num))),
            "hands_left": np.int8(max(0, hands_left)),
            "discards_left": np.int8(max(0, discards_left)),

            "joker_count": np.int8(len(joker_cards)),
            "joker_ids": joker_ids,
            "joker_slots": np.int8(jokers_area.get("limit", 5)),

            "consumable_count": np.int8(len(consumable_cards)),
            "consumables": cons_ids,
            "consumable_slots": np.int8(consumables_area.get("limit", 2)),

            "shop_items": shop_items,
            "shop_costs": shop_costs,
            "shop_rerolls": np.int16(reroll_cost),

            "hand_levels": hand_levels_arr,
            "phase": np.int8(int(phase)),
            "action_mask": self._build_action_mask(gs, phase),

            "hands_played": np.int32(self._hands_played),
            "best_hand_this_ante": np.int32(self._best_hand_score),

            "boss_blind_active": np.int8(is_boss),
            "boss_blind_type": np.int8(0),
            "face_down_cards": np.zeros(8, dtype=np.int8),

            "hand_one_hot": hand_one_hot,
            "hand_suits": hand_suits_arr,
            "hand_ranks": hand_ranks_arr,

            "rank_counts": rank_counts,
            "suit_counts": suit_counts,
            "straight_potential": np.float32(straight_pot),
            "flush_potential": np.float32(flush_pot),

            "avg_score_per_hand": np.float32(
                self._total_chips / max(1, self._hands_played)
            ),
            "hands_until_shop": np.int8(max(0, hands_left)),
            "rounds_until_boss": np.int8(max(0, 3 - round_num)),

            "has_mult_jokers": np.int8(has_mult),
            "has_chip_jokers": np.int8(has_chip),
            "has_xmult_jokers": np.int8(has_xmult),
            "has_economy_jokers": np.int8(has_econ),
            "hand_potential_scores": np.zeros(12, dtype=np.int32),
            "joker_synergy_score": np.float32(0.0),
            "risk_level": np.float32(risk_level),
            "economy_health": np.float32(economy_health),

            "blind_difficulty": np.float32(min(1.0, chips_needed / 100_000.0)),
            "win_probability": np.float32(min(1.0, progress_ratio)),
        }

    # ------------------------------------------------------------------
    # Action mask
    # ------------------------------------------------------------------

    def _build_action_mask(self, gs: dict, phase: Phase) -> np.ndarray:
        mask = np.zeros(ActionCounts.ACTION_SPACE_SIZE, dtype=np.int8)
        round_info = gs.get("round") or {}
        money = gs.get("money", 0)

        hand_cards = (gs.get("hand") or {}).get("cards") or []
        joker_cards = (gs.get("jokers") or {}).get("cards") or []
        consumable_cards = (gs.get("consumables") or {}).get("cards") or []
        shop_cards = (gs.get("shop") or {}).get("cards") or []
        pack_cards_shop = (gs.get("packs") or {}).get("cards") or []
        pack_cards = (gs.get("pack") or {}).get("cards") or []

        if phase == Phase.PLAY:
            for i in range(min(8, len(hand_cards))):
                mask[Action.SELECT_CARD_BASE + i] = 1
            if self._selected:
                mask[Action.PLAY_HAND] = 1
                if round_info.get("discards_left", 0) > 0:
                    mask[Action.DISCARD] = 1
            for i in range(min(5, len(consumable_cards))):
                mask[Action.USE_CONSUMABLE_BASE + i] = 1

        elif phase == Phase.SHOP:
            all_shop = list(shop_cards) + list(pack_cards_shop)
            for i, item in enumerate(all_shop[:10]):
                cost = (item.get("cost") or {}).get("buy", 0)
                if money >= cost:
                    mask[Action.SHOP_BUY_BASE + i] = 1
            reroll_cost = round_info.get("reroll_cost", 5)
            if money >= reroll_cost:
                mask[Action.SHOP_REROLL] = 1
            mask[Action.SHOP_END] = 1
            for i in range(min(5, len(joker_cards))):
                mask[Action.SELL_JOKER_BASE + i] = 1
            for i in range(min(5, len(consumable_cards))):
                mask[Action.SELL_CONSUMABLE_BASE + i] = 1

        elif phase == Phase.BLIND_SELECT:
            for i in range(ActionCounts.SELECT_BLIND_COUNT):
                mask[Action.SELECT_BLIND_BASE + i] = 1
            mask[Action.SKIP_BLIND] = 1

        elif phase == Phase.PACK_OPEN:
            for i in range(min(ActionCounts.SELECT_FROM_PACK_COUNT, len(pack_cards))):
                mask[Action.SELECT_FROM_PACK_BASE + i] = 1
            mask[Action.SKIP_PACK] = 1

        return mask

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def action_masks(self) -> np.ndarray:
        """Called by MaskablePPO before every action selection."""
        return self._build_action_mask(self._gs, self._current_phase())

    def _current_phase(self) -> Phase:
        return STATE_TO_PHASE.get(self._gs.get("state", ""), Phase.PLAY)

    def _get_chips_needed(self, gs: dict) -> int:
        """Return chip requirement for the current blind."""
        blinds = gs.get("blinds") or {}
        round_num = gs.get("round_num", 1)
        key = {1: "small", 2: "big", 3: "boss"}.get(round_num, "boss")
        blind = blinds.get(key) or {}
        return max(1, blind.get("score", 300))

    def _straight_potential(self, ranks: np.ndarray, hand_size: int) -> float:
        if hand_size < 2:
            return 0.0
        unique = sorted({int(r) for r in ranks[:hand_size] if r >= 0})
        if len(unique) < 2:
            return 0.0
        max_run = run = 1
        for i in range(1, len(unique)):
            run = (run + 1) if unique[i] == unique[i - 1] + 1 else 1
            max_run = max(max_run, run)
        return min(1.0, max_run / 5.0)

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self):
        if self.render_mode != "human":
            return
        gs = self._gs
        round_info = gs.get("round") or {}
        hand_cards = (gs.get("hand") or {}).get("cards") or []
        print(f"\n{'='*50}")
        print(
            f"State: {gs.get('state')} | "
            f"Ante {gs.get('ante_num')} Round {gs.get('round_num')}"
        )
        print(
            f"Chips: {round_info.get('chips', 0)}/{self._get_chips_needed(gs)} | "
            f"Hands: {round_info.get('hands_left')} | "
            f"Discards: {round_info.get('discards_left')} | "
            f"Money: ${gs.get('money', 0)}"
        )
        hand_str = " ".join(
            f"{(c.get('value') or {}).get('rank', '?')}"
            f"{(c.get('value') or {}).get('suit', '?')}"
            for c in hand_cards
        )
        print(f"Hand: {hand_str}")
        if self._selected:
            print(f"Selected: {self._selected}")
