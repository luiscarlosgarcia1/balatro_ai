"""Shop phase handler for Balatro RL environment.

This module handles all actions during the SHOP phase including:
- Buying items (jokers, cards, vouchers, packs)
- Rerolling shop
- Selling jokers
- Ending shopping
"""

from typing import Any, Dict, List, Optional, Tuple

from balatro_gym.core.cards import Card, Edition, Enhancement, Rank, Seal, Suit
from balatro_gym.core.boss_blinds import BossBlindManager, BossBlindType, select_boss_blind
from balatro_gym.core.constants import Action, Phase
from balatro_gym.core_utils.rng import DeterministicRNG
from balatro_gym.core_utils.joker_sale import sell_joker
from balatro_gym.core_utils.state import UnifiedGameState
from balatro_gym.core.shop import Shop, ShopAction, PlayerState, ItemType
from balatro_gym.core.jokers import JOKER_LIBRARY
from balatro_gym.scoring.scoring_engine import HandType


class ShopPhaseHandler:
    """Handles all actions during the SHOP phase."""
    
    def __init__(
        self,
        state: UnifiedGameState,
        rng: DeterministicRNG,
        boss_blind_manager: BossBlindManager | None = None,
        game: Any | None = None,
    ):
        """Initialize the shop phase handler.
        
        Args:
            state: Game state
            rng: RNG system
        """
        self.state = state
        self.rng = rng
        self.boss_blind_manager = boss_blind_manager
        self.game = game
        self.shop: Optional[Shop] = None
        self.pack_open_handler = None
    
    def step(self, action: int) -> Tuple[float, bool, Dict]:
        """Process an action during shop phase.
        
        Args:
            action: Action to execute
            
        Returns:
            Tuple of (reward, terminated, info)
        """
        if self.shop is None:
            self.generate_shop()
        
        if action == Action.SHOP_END:
            return self._handle_end_shop()
        elif action == Action.SHOP_REROLL:
            return self._handle_reroll()
        elif Action.SHOP_BUY_BASE <= action < Action.SHOP_BUY_BASE + Action.SHOP_BUY_COUNT:
            return self._handle_buy_item(action)
        elif Action.SELL_JOKER_BASE <= action < Action.SELL_JOKER_BASE + Action.SELL_JOKER_COUNT:
            return self._handle_sell_joker(action)
        elif Action.SELL_CONSUMABLE_BASE <= action < Action.SELL_CONSUMABLE_BASE + Action.SELL_CONSUMABLE_COUNT:
            return self._handle_sell_consumable(action)
        else:
            return -1.0, False, {'error': 'Invalid shop action'}
    
    def generate_shop(self):
        """Generate a new shop with items."""
        # Create or update player state
        player_state = self._create_player_state()
        
        # Generate shop with RNG
        shop_seed = self.rng.get_int('shop_generation', 0, 2**31 - 1)
        self.shop = Shop(self.state.ante, player_state, seed=shop_seed)
        
        # Sync inventory
        self.state.shop_inventory = self.shop.inventory.copy()
        self.state.shop_reroll_cost = int(self.shop.reroll_cost * self.shop._cost_mult())
        self.state.shop_visits += 1

    def invalidate_shop(self):
        """Clear cached shop state so the next shop entry regenerates inventory."""
        self.shop = None
        self.state.shop_inventory = []
    
    def _handle_end_shop(self) -> Tuple[float, bool, Dict]:
        """Handle ending the shopping phase."""
        # Return to blind select so the next pending blind is chosen explicitly.
        if int(self.state.round) == 3 and self.state.pending_boss_blind is None:
            try:
                self.state.pending_boss_blind = select_boss_blind(
                    self.state.ante,
                    rng=self.rng,
                    bosses_used=self.state.bosses_used,
                )
            except TypeError:
                self.state.pending_boss_blind = select_boss_blind(self.state.ante, rng=self.rng)
        self.state.phase = Phase.BLIND_SELECT
        self.state.selected_cards = []
        self.state.face_down_cards = []
        self.state.shop_inventory = []
        self.shop = None
        
        # Draw initial hand for next round
        # This should be handled by the main environment
        
        return -0.05, False, {
            'action': 'shop_ended',
            'transition_to': 'blind_select',
            'current_round': self.state.round,
        }  # time pressure: each shop visit must pay off
    
    def _handle_reroll(self) -> Tuple[float, bool, Dict]:
        """Handle rerolling the shop."""
        if self.state.money < self.state.shop_reroll_cost:
            return -1.0, False, {'error': 'Cannot afford reroll'}

        previous_reroll_cost = self.state.shop_reroll_cost
        
        # Execute reroll
        self._sync_player_state()
        reward, _, shop_info = self.shop.step(ShopAction.REROLL)
        
        # Update state
        self.state.money = self.shop.player.chips
        self.state.shop_inventory = self.shop.inventory.copy()
        self.state.rerolls_used += 1
        
        # Increase reroll cost
        self.state.shop_reroll_cost = int(self.shop.reroll_cost * self.shop._cost_mult())
        
        info = {
            'action': 'rerolled',
            'new_reroll_cost': self.state.shop_reroll_cost,
            'money_spent': previous_reroll_cost
        }
        info.update(shop_info)
        
        return reward, False, info
    
    def _handle_buy_item(self, action: int) -> Tuple[float, bool, Dict]:
        """Handle buying an item from the shop."""
        item_idx = action - Action.SHOP_BUY_BASE
        
        if not (0 <= item_idx < len(self.shop.inventory)):
            return -1.0, False, {'error': 'Invalid item index'}
        
        item = self.shop.inventory[item_idx]
        
        # Check affordability
        if self.state.money < item.cost:
            return -1.0, False, {'error': f'Cannot afford {item.name} (costs ${item.cost})'}
        
        # Map to shop action
        if item.item_type == ItemType.PACK:
            shop_action = ShopAction.BUY_PACK_BASE + item_idx
        elif item.item_type == ItemType.JOKER:
            # Check joker slot availability
            if len(self.state.jokers) >= self.state.joker_slots:
                return -1.0, False, {'error': 'No joker slots available'}
            shop_action = ShopAction.BUY_JOKER_BASE + item_idx
        elif item.item_type == ItemType.CARD:
            shop_action = ShopAction.BUY_CARD_BASE + item_idx
        elif item.item_type == ItemType.VOUCHER:
            shop_action = ShopAction.BUY_VOUCHER_BASE + item_idx
        else:
            return -1.0, False, {'error': f'Unknown item type: {item.item_type}'}
        
        # Execute purchase
        self._sync_player_state()
        reward, _, shop_info = self.shop.step(shop_action)
        
        # Handle errors from shop
        if 'error' in shop_info:
            return -1.0, False, shop_info

        # Sync post-purchase state before purchase-specific processing.
        self.state.money = self.shop.player.chips
        self.state.shop_inventory = self.shop.inventory.copy()
        cost_mult = self.shop._cost_mult() if hasattr(self.shop, '_cost_mult') else 1.0
        self.state.shop_reroll_cost = int(self.shop.reroll_cost * cost_mult)
        self._sync_inventory_from_player(shop_info)

        if item.item_type == ItemType.PACK:
            return self._handle_pack_purchase(item, shop_info)

        # Update state based on purchase type
        info = self._process_purchase(item, shop_info)
        
        # Calculate reward based on item type
        if item.item_type == ItemType.PACK:
            reward = 5.0  # Packs open new opportunities
        elif item.item_type == ItemType.JOKER:
            reward = 15.0  # Jokers are high value
        elif item.item_type == ItemType.CARD:
            reward = 3.0  # Cards are moderate value
        elif item.item_type == ItemType.VOUCHER:
            reward = 10.0  # Vouchers provide permanent benefits
        
        return reward, False, info
    
    def _handle_sell_joker(self, action: int) -> Tuple[float, bool, Dict]:
        """Handle selling a joker."""
        joker_idx = action - Action.SELL_JOKER_BASE
        
        if not (0 <= joker_idx < len(self.state.jokers)):
            return -1.0, False, {'error': 'Invalid joker index'}

        try:
            sold_joker, sell_value, sale_effects = sell_joker(
                self.state,
                joker_idx,
                boss_blind_manager=self.boss_blind_manager,
                game=self.game,
            )
        except ValueError as exc:
            return -1.0, False, {'error': str(exc)}
        
        # Sync with shop player state
        self._sync_player_state()
        
        # Calculate reward (small positive to allow strategic selling)
        reward = sell_value / 10.0
        
        info = {
            'action': 'sold_joker',
            'joker_sold': sold_joker.name,
            'money_gained': sell_value,
            'jokers_remaining': len(self.state.jokers)
        }
        info.update(sale_effects)
        
        return reward, False, info

    def _handle_sell_consumable(self, action: int) -> Tuple[float, bool, Dict]:
        """Handle selling a consumable with minimal MVP economics."""
        consumable_idx = action - Action.SELL_CONSUMABLE_BASE

        if not (0 <= consumable_idx < len(self.state.consumables)):
            return -1.0, False, {'error': 'Invalid consumable index'}

        consumable_name = self.state.consumables.pop(consumable_idx)
        sell_value = self._calculate_consumable_sell_value(consumable_name)
        self.state.money += sell_value
        self._sync_player_state()

        info = {
            'action': 'sold_consumable',
            'consumable_sold': consumable_name,
            'money_gained': sell_value,
            'consumables_remaining': len(self.state.consumables),
        }

        return sell_value / 10.0, False, info
    
    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------
    
    def _create_player_state(self) -> PlayerState:
        """Create player state from unified state."""
        existing_player = self.shop.player if self.shop and self.shop.player else None
        player = PlayerState(
            chips=self.state.money,
            consumables=self.state.consumables.copy(),
            first_shop_buffoon_seen=getattr(existing_player, 'first_shop_buffoon_seen', False),
            shop_visits=max(
                int(getattr(existing_player, 'shop_visits', 0) or 0),
                int(getattr(self.state, 'shop_visits', 0) or 0),
            ),
            spectral_rate=int(getattr(existing_player, 'spectral_rate', 0) or 0),
            most_played_hand=self._derive_most_played_hand(existing_player),
        )
        player.jokers = [j.id for j in self.state.jokers]
        player.vouchers = self.state.vouchers.copy()
        player.deck = [int(card) for card in self.state.deck]
        return player
    
    def _sync_player_state(self):
        """Sync player state with unified state."""
        if self.shop and self.shop.player:
            self.shop.player.chips = self.state.money
            self.shop.player.jokers = [j.id for j in self.state.jokers]
            self.shop.player.vouchers = self.state.vouchers.copy()
            self.shop.player.deck = [int(card) for card in self.state.deck]
            self.shop.player.consumables = self.state.consumables.copy()
            self.shop.player.first_shop_buffoon_seen = bool(
                getattr(self.shop.player, 'first_shop_buffoon_seen', False)
            )
            self.shop.player.shop_visits = max(
                int(getattr(self.shop.player, 'shop_visits', 0) or 0),
                int(getattr(self.state, 'shop_visits', 0) or 0),
            )
            self.shop.player.spectral_rate = int(getattr(self.shop.player, 'spectral_rate', 0) or 0)
            self.shop.player.most_played_hand = self._derive_most_played_hand(self.shop.player)
    
    def _sync_jokers_from_player(self):
        """Sync jokers from player state back to unified state."""
        if self.shop and self.shop.player:
            # Get new jokers that were added
            current_joker_ids = {j.id for j in self.state.jokers}
            for joker_id in self.shop.player.jokers:
                if joker_id not in current_joker_ids:
                    # Find joker info and add it
                    for joker_info in JOKER_LIBRARY:
                        if joker_info.id == joker_id:
                            self.state.add_joker(joker_info)
                            break

    def _sync_inventory_from_player(self, shop_info: Optional[Dict[str, Any]] = None) -> None:
        """Sync deck and consumables after shop purchases mutate the player state."""
        if not self.shop or not self.shop.player:
            return

        player_deck = list(self.shop.player.deck)
        purchased_card = (shop_info or {}).get("card_added")
        purchased_card_payload = purchased_card if isinstance(purchased_card, dict) else None
        if len(player_deck) > len(self.state.deck):
            for encoded_card in player_deck[len(self.state.deck):]:
                card = self._decode_shop_card(encoded_card)
                card_idx = len(self.state.deck)
                self.state.deck.append(card)
                self._apply_shop_card_modifiers(card_idx, purchased_card_payload)

        self.state.consumables = self.shop.player.consumables.copy()

    def _decode_shop_card(self, card_index: int) -> Card:
        """Convert the shop's integer card encoding back into a core Card."""
        normalized = int(card_index)
        rank = Rank((normalized // 4) + 2)
        suit = Suit(normalized % 4)
        return Card(rank=rank, suit=suit)

    def _apply_shop_card_modifiers(self, card_idx: int, payload: Optional[Dict[str, Any]]) -> None:
        """Apply direct shop card modifiers carried by the purchase payload."""
        if not payload or payload.get("offer_set") != "Playing":
            return

        card_state = self.state.get_card_state(card_idx)
        card_state.enhancement = payload.get("enhancement", Enhancement.NONE)
        card_state.edition = payload.get("edition", Edition.NONE)
        card_state.seal = payload.get("seal", Seal.NONE)
    
    def _process_purchase(self, item, shop_info: Dict) -> Dict:
        """Process purchase results based on item type."""
        info = {
            'action': 'bought_item',
            'item_name': item.name,
            'item_type': item.item_type.name,
            'cost': item.cost
        }
        
        if item.item_type == ItemType.PACK:
            info['transition_to'] = 'pack_open'
        
        elif item.item_type == ItemType.JOKER:
            # Sync joker from player state
            self._sync_jokers_from_player()
            if self.state.jokers:
                info['joker_acquired'] = self.state.jokers[-1].name
        
        elif item.item_type == ItemType.CARD:
            # Card was added to deck
            info['card_added'] = True
            if 'card_added' in shop_info:
                info['card_details'] = shop_info['card_added']
        
        elif item.item_type == ItemType.VOUCHER:
            # Sync vouchers
            self.state.vouchers = self.shop.player.vouchers.copy()
            if self.state.vouchers:
                acquired_voucher = self.state.vouchers[-1]
                info['voucher_acquired'] = acquired_voucher
                info['voucher_effect'] = self._get_voucher_effect(acquired_voucher)
                info.update(self._apply_voucher_effects(acquired_voucher))
        
        return info

    def _handle_pack_purchase(self, item, shop_info: Dict) -> Tuple[float, bool, Dict]:
        """Transition a purchased pack into the pack opening phase."""
        self.state.money = self.shop.player.chips
        self.state.shop_inventory = self.shop.inventory.copy()

        info = self._process_purchase(item, shop_info)
        pack_type = self._extract_pack_type(item, shop_info)
        pack_contents = self._extract_pack_contents(item, shop_info)

        info['pack_type'] = pack_type
        info['pack_contents_raw'] = pack_contents

        if self.pack_open_handler is None:
            info['warning'] = 'Pack purchased without pack handler attached'
            return 5.0, False, info

        cards_to_select = shop_info.get('pack_choose')
        if cards_to_select is None:
            cards_to_select = getattr(item, 'payload', {}).get('choose')

        pack_info = self.pack_open_handler.open_pack(
            pack_type,
            pack_contents,
            cards_to_select=cards_to_select,
        )
        info.update(pack_info)

        return 5.0, False, info

    def _extract_pack_type(self, item, shop_info: Dict[str, Any]) -> str:
        """Get the best available pack type label from item/shop payloads."""
        for source in (shop_info, getattr(item, 'payload', None) or {}):
            if not isinstance(source, dict):
                continue
            for key in ('pack_type', 'pack_name', 'name'):
                value = source.get(key)
                if isinstance(value, str) and value:
                    return value
        return item.name

    def _extract_pack_contents(self, item, shop_info: Dict[str, Any]) -> List[Any]:
        """Get pack contents from the current shop interface."""
        candidate_keys = (
            'pack_contents',
            'contents',
            'choices',
            'cards',
            'new_cards',
        )

        for source in (shop_info, getattr(item, 'payload', None) or {}):
            if not isinstance(source, dict):
                continue
            for key in candidate_keys:
                value = source.get(key)
                if isinstance(value, list):
                    return value

        return []

    def _derive_most_played_hand(self, player: Optional[PlayerState]) -> Optional[str]:
        """Return the best available shop hand hint from state or prior player data."""
        hand_levels = getattr(self.state, 'hand_levels', {}) or {}
        best_hand: Optional[HandType] = None
        best_level = 0

        for hand_type, level in hand_levels.items():
            try:
                normalized_level = int(level)
            except (TypeError, ValueError):
                continue

            if normalized_level > best_level and isinstance(hand_type, HandType):
                best_hand = hand_type
                best_level = normalized_level

        if best_hand is not None and best_level > 1:
            return self._format_hand_type(best_hand)

        return getattr(player, 'most_played_hand', None)

    def _format_hand_type(self, hand_type: HandType) -> str:
        """Convert HandType enum names to the shop's display strings."""
        hand_name_map = {
            HandType.HIGH_CARD: 'High Card',
            HandType.ONE_PAIR: 'Pair',
            HandType.TWO_PAIR: 'Two Pair',
            HandType.THREE_KIND: 'Three of a Kind',
            HandType.STRAIGHT: 'Straight',
            HandType.FLUSH: 'Flush',
            HandType.FULL_HOUSE: 'Full House',
            HandType.FOUR_KIND: 'Four of a Kind',
            HandType.STRAIGHT_FLUSH: 'Straight Flush',
            HandType.FIVE_KIND: 'Five of a Kind',
            HandType.FLUSH_HOUSE: 'Flush House',
            HandType.FLUSH_FIVE: 'Flush Five',
        }
        return hand_name_map.get(hand_type, hand_type.name.replace('_', ' ').title())
    
    def _get_voucher_effect(self, voucher_name: str) -> str:
        """Get description of voucher effect."""
        voucher_effects = {
            'Overstock': '+1 card slot in shop',
            'Clearance Sale': 'All items in shop are 25% off',
            'Hone': 'Foil, Holographic, and Polychrome cards appear 2X more often',
            'Reroll Surplus': 'Rerolls cost $2 less',
            'Crystal Ball': '+1 consumable slot',
            'Telescope': 'Celestial Packs always contain your most used poker hand\'s Planet card',
            'Grabber': '+1 hand per round',
            'Dusk': 'Tarot and Planet cards appear 2X more often in the shop',
            "Director's Cut": 'Pay $10 to reroll the boss blind once per ante',
            'Retcon': 'Pay $10 to reroll the boss blind repeatedly each ante',
            'Paint Brush': '+1 hand size',
            'Overstock Plus': '+1 card slot in shop (again)',
            'Liquidation': 'All items in shop are 50% off',
            'Wasteful': 'Permanently gain +1 discard every round',
            'Tarot Merchant': 'Tarot cards appear 2X more often in the shop',
            'Planet Merchant': 'Planet cards appear 2X more often in the shop',
            'Seed Money': 'Gain $1 interest for every $5 you have at the end of the round',
        }
        
        return voucher_effects.get(voucher_name, 'Unknown voucher effect')

    def _apply_voucher_effects(self, voucher_name: str) -> Dict[str, Any]:
        """Apply the persistent voucher effects that materially affect sim state."""
        effects: Dict[str, Any] = {}

        if voucher_name == 'Crystal Ball':
            self.state.consumable_slots += 1
            effects['consumable_slots'] = self.state.consumable_slots
        elif voucher_name == 'Antimatter':
            self.state.joker_slots += 1
            effects['joker_slots'] = self.state.joker_slots
        elif voucher_name == 'Grabber':
            self.state.hands_left += 1
            effects['hands_left'] = self.state.hands_left
        elif voucher_name == 'Nacho Tong':
            self.state.hands_left += 1
            effects['hands_left'] = self.state.hands_left
        elif voucher_name == 'Wasteful':
            self.state.discards_left += 1
            effects['discards_left'] = self.state.discards_left
        elif voucher_name == 'Recyclomancy':
            self.state.discards_left += 1
            effects['discards_left'] = self.state.discards_left
        elif voucher_name == 'Paint Brush':
            self.state.hand_size += 1
            effects['hand_size'] = self.state.hand_size
        elif voucher_name == 'Palette':
            self.state.hand_size += 1
            effects['hand_size'] = self.state.hand_size

        effects['shop_reroll_cost'] = self.state.shop_reroll_cost
        return effects

    def _calculate_consumable_sell_value(self, consumable_name: str) -> int:
        """Approximate live sell_cost semantics for MVP contract parity."""
        spectral_names = {
            'Familiar', 'Grim', 'Incantation', 'Talisman', 'Aura', 'Wraith',
            'Sigil', 'Ouija', 'Ectoplasm', 'Immolate', 'Ankh', 'Deja Vu',
            'Hex', 'Trance', 'Medium', 'Cryptid', 'The Soul', 'Black Hole',
        }
        return 2 if consumable_name in spectral_names else 1
