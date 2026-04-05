local snap = dofile("mods/live_state_exporter/snap.lua")

local function eq(a, b, msg)
  if a ~= b then
    error(msg or ("expected " .. tostring(b) .. ", got " .. tostring(a)), 2)
  end
end

local function ok(v, msg)
  if not v then
    error(msg or "expected truthy value", 2)
  end
end

local function is_arr(v, msg)
  ok(type(v) == "table", msg or "expected table")
  eq(#v, 0, msg or "expected empty array")
end

local shell = snap.build_shell({})

eq(shell.state_id, 0, "state_id should default to 0")
eq(shell.dollars, 0, "dollars should default to 0")
eq(shell.hands_left, 0, "hands_left should default to 0")
eq(shell.discards_left, 0, "discards_left should default to 0")
ok(type(shell.score) == "table", "score should always be present")
eq(shell.score.current, 0, "score.current should default to 0")
eq(shell.score.target, 0, "score.target should default to 0")
ok(snap.is_null(shell.deck_key), "deck_key should default to null")
ok(snap.is_null(shell.stake_id), "stake_id should default to null")
ok(snap.is_null(shell.blind_key), "blind_key should default to null")
ok(snap.is_null(shell.ante), "ante should default to null")
ok(snap.is_null(shell.round), "round should default to null")
ok(snap.is_null(shell.joker_slots), "joker_slots should default to null")
ok(snap.is_null(shell.consumable_slots), "consumable_slots should default to null")
ok(snap.is_null(shell.run_info), "run_info should default to null")
ok(snap.is_null(shell.interest), "interest should default to null")
ok(snap.is_null(shell.reroll_cost), "reroll_cost should default to null")
ok(snap.is_null(shell.pack_contents), "pack_contents should default to null")
ok(snap.is_null(shell.hand_size), "hand_size should default to null")
is_arr(shell.blinds, "blinds should be an empty array")
is_arr(shell.jokers, "jokers should be an empty array")
is_arr(shell.consumables, "consumables should be an empty array")
is_arr(shell.tags, "tags should be an empty array")
is_arr(shell.vouchers, "vouchers should be an empty array")
is_arr(shell.shop_items, "shop_items should be an empty array")
is_arr(shell.cards_in_hand, "cards_in_hand should be an empty array")
is_arr(shell.selected_cards, "selected_cards should be an empty array")
is_arr(shell.cards_in_deck, "cards_in_deck should be an empty array")

local shaped = snap.build_shell({
  cards_in_hand = {
    {
      card_key = "S_A",
      instance_id = 1,
      debuffed = false,
    },
  },
  jokers = {
    {
      key = "j_greedy_joker",
      instance_id = 2,
      eternal = false,
      perishable = true,
      rental = false,
      debuffed = false,
    },
  },
  consumables = {
    {
      key = "c_fool",
      instance_id = 3,
    },
  },
  selected_cards = {
    {
      zone = "hand",
      instance_id = 1,
      key = "S_A",
    },
  },
  cards_in_deck = {
    {
      card_key = "S_A",
      instance_id = 1,
      debuffed = false,
    },
  },
})

ok(snap.is_null(shaped.cards_in_hand[1].enhancement), "hand card enhancement should shape to null")
ok(snap.is_null(shaped.cards_in_hand[1].edition), "hand card edition should shape to null")
ok(snap.is_null(shaped.cards_in_hand[1].seal), "hand card seal should shape to null")
ok(snap.is_null(shaped.cards_in_hand[1].facing), "hand card facing should shape to null")
ok(snap.is_null(shaped.cards_in_hand[1].cost), "hand card cost should shape to null")
ok(snap.is_null(shaped.cards_in_hand[1].sell_cost), "hand card sell_cost should shape to null")
ok(snap.is_null(shaped.jokers[1].perish_tally), "joker perish_tally should shape to null")
ok(snap.is_null(shaped.jokers[1].edition), "joker edition should shape to null")
ok(snap.is_null(shaped.jokers[1].sell_cost), "joker sell_cost should shape to null")
ok(snap.is_null(shaped.consumables[1].edition), "consumable edition should shape to null")
ok(snap.is_null(shaped.consumables[1].cost), "consumable cost should shape to null")
ok(snap.is_null(shaped.consumables[1].sell_cost), "consumable sell_cost should shape to null")

local raw = snap.read_state({
  STATE = 41,
  GAME = {
    dollars = 12,
    chips = 75,
    stake = 2,
    round = 4,
    selected_back = { key = "b_red" },
    blind = { chips = 300 },
    round_resets = { ante = 2 },
    current_round = {
      hands_left = 3,
      discards_left = 1,
      reroll_cost = 5,
    },
  },
})

eq(raw.state_id, 41, "reader should prefer root state id")
eq(raw.dollars, 12, "reader should read dollars")
eq(raw.hands_left, 3, "reader should read hands_left")
eq(raw.discards_left, 1, "reader should read discards_left")
eq(raw.score.current, 75, "reader should read current score")
eq(raw.score.target, 300, "reader should read target score")
eq(raw.stake_id, 2, "reader should carry stake_id")
eq(raw.deck_key, "b_red", "reader should read deck_key")
eq(raw.ante, 2, "reader should read ante")
eq(raw.round, 4, "reader should read round")
eq(raw.reroll_cost, 5, "reader should read reroll_cost")

local partial = snap.read_state({ STATE = 7 })
ok(type(partial) == "table", "reader should return a table for partial state")
eq(partial.state_id, 7, "partial reader should keep state_id")
eq(partial.dollars, nil, "missing dollars should stay nil before shell defaults")
eq(partial.score.current, nil, "missing score.current should stay nil before shell defaults")
eq(partial.score.target, nil, "missing score.target should stay nil before shell defaults")

local phase_two = snap.read_state({
  STATE = 12,
  tags = {
    { key = "tag_investment" },
  },
  jokers = {
    config = {
      card_limit = 6,
      type = "joker",
    },
    cards = {
      {
        ID = 801,
        sell_cost = 5,
        debuff = true,
        config = {
          center_key = "j_greedy_joker",
        },
        ability = {
          eternal = true,
          perishable = false,
          rental = false,
        },
      },
    },
  },
  consumables = {
    config = {
      card_limit = 3,
      type = "consumeables",
    },
    cards = {
      {
        ID = 601,
        cost = 4,
        config = {
          center_key = "c_fool",
        },
      },
    },
  },
  hand = {
    config = {
      card_limit = 9,
      type = "hand",
    },
    cards = {
      {
        ID = 501,
        highlighted = true,
        config = {
          card_key = "S_A",
          center_key = "m_bonus",
        },
        edition = {
          type = "foil",
        },
        seal = "Gold",
      },
    },
  },
  GAME = {
    dollars = 20,
    chips = 90,
    state = "SHOP",
    selected_back_key = "b_blue",
    blind = { key = "bl_big", chips = 400 },
    round = 3,
    stake_id = "stake_green",
    interest_amount = 3,
    interest_cap = 25,
    modifiers = {
      no_interest = true,
    },
    playing_cards = {
      {
        ID = 702,
        base = {
          suit = "Hearts",
          value = "Ace",
        },
        config = {
          card_key = "H_A",
        },
      },
      {
        ID = 701,
        base = {
          suit = "Spades",
          value = "Ace",
        },
        config = {
          card_key = "S_A",
        },
      },
    },
    hands = {
      Pair = {
        level = 2,
        chips = 15,
        mult = 2,
        played = 3,
        played_this_round = 1,
      },
      ["High Card"] = {
        level = 1,
        chips = 5,
        mult = 1,
        played = 0,
        played_this_round = 0,
      },
    },
    used_vouchers = {
      v_clearance_sale = {
        cost = 10,
      },
    },
    current_round = {
      hands_left = 2,
      discards_left = 1,
      reroll_cost = 7,
    },
    round_resets = {
      ante = 2,
      blind_choices = {
        small = "bl_small",
        big = "bl_big",
        boss = "bl_hook",
      },
      blind_states = {
        small = "defeated",
        big = "current",
        boss = "upcoming",
      },
      blind_tags = {
        boss = "tag_boss",
      },
    },
  },
})

eq(phase_two.blind_key, "bl_big", "reader should derive blind_key from active blind outside blind select")
eq(#phase_two.blinds, 3, "reader should export blind rows")
eq(phase_two.blinds[3].tag_key, "tag_boss", "reader should export blind tag keys")
eq(phase_two.run_info.hands.Pair.level, 2, "reader should export run_info hands")
eq(phase_two.interest.amount, 3, "reader should export interest")
eq(phase_two.interest.no_interest, true, "reader should export interest.no_interest")
eq(phase_two.joker_slots, 6, "reader should export joker_slots")
eq(phase_two.consumable_slots, 3, "reader should export consumable_slots")
eq(phase_two.hand_size, 9, "reader should export hand_size")
eq(phase_two.vouchers[1].key, "v_clearance_sale", "reader should export vouchers")
eq(phase_two.vouchers[1].cost, 10, "reader should export voucher cost")
eq(phase_two.tags[1].key, "tag_investment", "reader should export tags")
eq(phase_two.cards_in_hand[1].card_key, "S_A", "reader should export cards_in_hand")
eq(phase_two.cards_in_hand[1].enhancement, "m_bonus", "reader should export hand card enhancement")
eq(phase_two.selected_cards[1].zone, "hand", "reader should export selected card references")
eq(phase_two.selected_cards[1].instance_id, 501, "reader should export selected card instance_id")
eq(phase_two.jokers[1].key, "j_greedy_joker", "reader should export jokers")
eq(phase_two.jokers[1].debuffed, true, "reader should export joker debuffed state")
eq(phase_two.consumables[1].key, "c_fool", "reader should export consumables")
eq(phase_two.cards_in_deck[1].card_key, "S_A", "reader should export deck cards in canonical order")
eq(phase_two.cards_in_deck[2].card_key, "H_A", "reader should export later deck cards after ordering")

local market_state = snap.read_state({
  STATE = 15,
  shop = {
    cards = {
      {
        ID = 901,
        cost = 8,
        config = {
          card_key = "S_A",
          center_key = "m_bonus",
        },
      },
      {
        ID = 902,
        config = {
          center_key = "j_blue_joker",
        },
        ability = {
          rental = true,
        },
      },
    },
  },
  shop_vouchers = {
    cards = {
      {
        cost = 10,
        config = {
          center_key = "v_clearance_sale",
        },
      },
    },
  },
  GAME = {
    state = "SHOP",
    blind = {
      key = "bl_small",
      chips = 300,
    },
    current_round = {
      hands_left = 2,
      discards_left = 1,
      reroll_cost = 5,
    },
  },
})

eq(#market_state.shop_items, 3, "reader should export collected shop_items")
eq(market_state.shop_items[1].card.card_key, "S_A", "reader should keep wrapped shop cards")
eq(market_state.shop_items[2].joker.key, "j_blue_joker", "reader should keep wrapped shop jokers")
eq(market_state.shop_items[3].voucher.key, "v_clearance_sale", "reader should append wrapped shop vouchers")
eq(market_state.pack_contents, nil, "shop state should leave pack_contents inactive before shell shaping")

local pack_state = snap.read_state({
  STATE = 16,
  pack = {
    ID = 950,
    can_skip = true,
    config = {
      center_key = "p_arcana_normal_1",
    },
  },
  pack_cards = {
    cards = {
      {
        ID = 951,
        config = {
          card_key = "H_A",
        },
      },
      {
        ID = 952,
        config = {
          center_key = "j_blue_joker",
        },
      },
      {
        ID = 953,
        config = {
          center_key = "c_fool",
        },
      },
    },
  },
  GAME = {
    state = "PACK",
    blind = {
      key = "bl_big",
      chips = 400,
    },
    pack_choices = 2,
    current_round = {
      hands_left = 2,
      discards_left = 1,
    },
  },
})

ok(type(pack_state.pack_contents) == "table", "reader should export active pack_contents")
eq(pack_state.pack_contents.pack.key, "p_arcana_normal_1", "reader should export opened pack")
eq(pack_state.pack_contents.choices_remaining, 2, "reader should export pack choice count")
eq(pack_state.pack_contents.skip_available, true, "reader should export explicit pack skip availability")
eq(#pack_state.pack_contents.items, 3, "reader should export concrete pack items")
eq(pack_state.pack_contents.items[1].card_key, "H_A", "reader should keep pack item order")
eq(pack_state.pack_contents.items[2].key, "j_blue_joker", "reader should export pack jokers")
eq(pack_state.pack_contents.items[3].key, "c_fool", "reader should export pack consumables")

local shaped_market = snap.build_shell({
  shop_items = {
    {
      card = {
        card_key = "S_A",
        instance_id = 1,
        debuffed = false,
      },
    },
    {
      voucher = {
        key = "v_clearance_sale",
        cost = 10,
      },
    },
  },
  pack_contents = {
    pack = {
      key = "p_arcana_normal_1",
      instance_id = 5,
    },
    choices_remaining = 2,
    skip_available = false,
    items = {
      {
        key = "j_blue_joker",
        instance_id = 6,
        eternal = false,
        perishable = false,
        rental = false,
        debuffed = false,
      },
      {
        card_key = "H_A",
        instance_id = 7,
        debuffed = false,
      },
      {
        key = "c_fool",
        instance_id = 8,
      },
    },
  },
})

ok(type(shaped_market.shop_items) == "table", "shell should keep shop_items array")
ok(snap.is_null(shaped_market.shop_items[1].joker), "shell should null-fill inactive shop joker member")
ok(snap.is_null(shaped_market.shop_items[1].consumable), "shell should null-fill inactive shop consumable member")
ok(snap.is_null(shaped_market.shop_items[1].voucher), "shell should null-fill inactive shop voucher member")
ok(snap.is_null(shaped_market.shop_items[1].pack), "shell should null-fill inactive shop pack member")
ok(snap.is_null(shaped_market.shop_items[2].card), "shell should null-fill inactive shop card member")
ok(snap.is_null(shaped_market.shop_items[2].joker), "shell should null-fill inactive shop joker member on voucher wrappers")
eq(shaped_market.shop_items[2].voucher.key, "v_clearance_sale", "shell should preserve active shop voucher payload")
ok(type(shaped_market.pack_contents) == "table", "shell should keep active pack_contents object")
ok(snap.is_null(shaped_market.pack_contents.pack.cost), "shell should null-fill missing pack cost")
eq(shaped_market.pack_contents.choices_remaining, 2, "shell should preserve pack choice count")
eq(shaped_market.pack_contents.skip_available, false, "shell should preserve pack skip flag")
eq(#shaped_market.pack_contents.items, 3, "shell should keep pack item array")
ok(snap.is_null(shaped_market.pack_contents.items[1].perish_tally), "shell should null-fill missing joker perish_tally in pack items")
ok(snap.is_null(shaped_market.pack_contents.items[2].enhancement), "shell should null-fill missing card enhancement in pack items")
ok(snap.is_null(shaped_market.pack_contents.items[3].edition), "shell should null-fill missing consumable edition in pack items")

local malformed = snap.build_shell({
  run_info = {},
  interest = "bad-interest",
  blinds = "bad-blinds",
  tags = "bad-tags",
  vouchers = "bad-vouchers",
  shop_items = "bad-shop-items",
  cards_in_hand = "bad-cards-in-hand",
  selected_cards = "bad-selected-cards",
  cards_in_deck = "bad-cards-in-deck",
})

ok(snap.is_null(malformed.run_info), "shell should collapse malformed run_info to null")
ok(snap.is_null(malformed.interest), "shell should collapse malformed interest to null")
is_arr(malformed.blinds, "shell should keep malformed blinds as an empty array")
is_arr(malformed.tags, "shell should keep malformed tags as an empty array")
is_arr(malformed.vouchers, "shell should keep malformed vouchers as an empty array")
is_arr(malformed.shop_items, "shell should keep malformed shop_items as an empty array")
is_arr(malformed.cards_in_hand, "shell should keep malformed cards_in_hand as an empty array")
is_arr(malformed.selected_cards, "shell should keep malformed selected_cards as an empty array")
is_arr(malformed.cards_in_deck, "shell should keep malformed cards_in_deck as an empty array")

local old = {
  SMODS = rawget(_G, "SMODS"),
  NFS = rawget(_G, "NFS"),
}

local function read_text(path)
  local handle = assert(io.open(path, "r"))
  local body = assert(handle:read("*a"))
  handle:close()
  return body
end

local read_calls = {}

_G.SMODS = {
  current_mod = {
    path = "virtual/",
  },
}
_G.NFS = {
  read = function(path)
    read_calls[#read_calls + 1] = path
    local relative = path:gsub("^virtual/", "")
    return read_text("mods/live_state_exporter/" .. relative)
  end,
}

local nfs_snap = dofile("mods/live_state_exporter/snap.lua")
local nfs_state = nfs_snap.read_state({
  STATE = "SHOP",
  GAME = {
    blind = {
      key = "bl_big",
      chips = 300,
    },
    current_round = {
      hands_left = 2,
      discards_left = 1,
      reroll_cost = 5,
    },
  },
})

eq(nfs_state.blind_key, "bl_big", "NFS-loaded snap should keep nested phase and collector behavior")

local saw_shared_values = false
for i = 1, #read_calls do
  if read_calls[i] == "virtual/shared/values.lua" then
    saw_shared_values = true
    break
  end
end

ok(saw_shared_values, "NFS-loaded snap should load nested shared values through the current module loader path")

_G.SMODS = old.SMODS
_G.NFS = old.NFS
