"""String constants for every valid action kind in the file-channel protocol."""


class ActionKind:
    PLAY_HAND = "play_hand"
    DISCARD = "discard"
    BUY_SHOP_ITEM = "buy_shop_item"
    SELL_JOKER = "sell_joker"
    REROLL_SHOP = "reroll_shop"
    LEAVE_SHOP = "leave_shop"
    SELECT_BLIND = "select_blind"
    SKIP_BLIND = "skip_blind"
    PICK_PACK_ITEM = "pick_pack_item"
    SKIP_PACK = "skip_pack"
    USE_CONSUMABLE = "use_consumable"
    REORDER_JOKERS = "reorder_jokers"
    REORDER_HAND = "reorder_hand"
    CASH_OUT = "cash_out"
