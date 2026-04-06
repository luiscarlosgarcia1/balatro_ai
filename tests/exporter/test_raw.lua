local raw = dofile("mods/live_state_exporter/state/raw.lua")

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

local simple = raw.read_state({
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

eq(simple.state_id, 41, "reader should prefer root state id")
eq(simple.interaction_phase, "shop", "reader should surface interaction_phase")
eq(simple.dollars, 12, "reader should read dollars")
eq(simple.hands_left, 3, "reader should read hands_left")
eq(simple.discards_left, 1, "reader should read discards_left")
eq(simple.score.current, 75, "reader should read current score")
eq(simple.score.target, 300, "reader should read target score")
eq(simple.stake_id, 2, "reader should carry stake_id")
eq(simple.deck_key, "b_red", "reader should read deck_key")
eq(simple.ante, 2, "reader should read ante")
eq(simple.round, 4, "reader should read round")
eq(simple.reroll_cost, 5, "reader should read reroll_cost")

local partial = raw.read_state({ STATE = 7 })
ok(type(partial) == "table", "reader should return a table for partial state")
eq(partial.state_id, 7, "partial reader should keep state_id")
eq(partial.dollars, nil, "missing dollars should stay nil before shell defaults")
eq(partial.score.current, nil, "missing score.current should stay nil before shell defaults")
eq(partial.score.target, nil, "missing score.target should stay nil before shell defaults")

local table_deck_key = raw.read_state({
  GAME = {
    selected_back_key = { key = "b_yellow", name = "Yellow Deck" },
  },
})

eq(table_deck_key.deck_key, "b_yellow", "reader should extract deck_key from selected_back_key tables")

local phase_two = raw.read_state({
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

eq(phase_two.interaction_phase, "shop", "reader should preserve inferred interaction_phase")
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

local market_state = raw.read_state({
  STATE = 15,
  shop_jokers = {
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
  shop_booster = {
    cards = {
      {
        ID = 903,
        cost = 4,
        config = {
          center_key = "p_arcana_normal_1",
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

eq(market_state.interaction_phase, "shop", "reader should infer shop phase")
eq(#market_state.shop_items, 4, "reader should export collected shop_items")
eq(market_state.shop_items[1].card.card_key, "S_A", "reader should keep wrapped shop cards")
eq(market_state.shop_items[2].joker.key, "j_blue_joker", "reader should keep wrapped shop jokers")
eq(market_state.shop_items[3].voucher.key, "v_clearance_sale", "reader should append wrapped shop vouchers")
eq(market_state.shop_items[4].pack.key, "p_arcana_normal_1", "reader should append wrapped shop boosters")
eq(market_state.pack_contents, nil, "shop state should leave pack_contents inactive before shell shaping")

local stale_pack_choice_shop_state = raw.read_state({
  STATE = 5,
  shop_jokers = {
    cards = {
      {
        ID = 904,
        config = {
          center_key = "j_greedy_joker",
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
    pack_choices = 1,
    current_round = {
      hands_left = 2,
      discards_left = 1,
      reroll_cost = 5,
    },
  },
})

eq(stale_pack_choice_shop_state.interaction_phase, "shop", "reader should ignore stale pack choices when shop rows are visible")
eq(#stale_pack_choice_shop_state.shop_items, 2, "reader should still export visible shop rows with stale pack choices")
eq(stale_pack_choice_shop_state.pack_contents, nil, "reader should keep pack_contents inactive for stale pack choice shop states")

local pack_state = raw.read_state({
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

eq(pack_state.interaction_phase, "pack_reward", "reader should infer pack_reward phase")
ok(type(pack_state.pack_contents) == "table", "reader should export active pack_contents")
eq(pack_state.pack_contents.choices_remaining, 2, "reader should export pack choice count")
eq(pack_state.pack_contents.skip_available, true, "reader should export explicit pack skip availability")
eq(#pack_state.pack_contents.items, 3, "reader should export concrete pack items")
eq(pack_state.pack_contents.items[1].card_key, "H_A", "reader should keep pack item order")
eq(pack_state.pack_contents.items[2].key, "j_blue_joker", "reader should export pack jokers")
eq(pack_state.pack_contents.items[3].key, "c_fool", "reader should export pack consumables")

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

local nfs_raw = dofile("mods/live_state_exporter/state/raw.lua")
local nfs_state = nfs_raw.read_state({
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

eq(nfs_state.interaction_phase, "shop", "NFS-loaded raw reader should preserve inferred interaction_phase")

local saw_values = false
local saw_common = false
local saw_owned = false
local saw_market = false
local saw_run_state = false
for i = 1, #read_calls do
  if read_calls[i] == "virtual/shared/values.lua" then
    saw_values = true
  end
  if read_calls[i] == "virtual/shared/entities/common.lua" then
    saw_common = true
  end
  if read_calls[i] == "virtual/shared/entities/owned.lua" then
    saw_owned = true
  end
  if read_calls[i] == "virtual/shared/entities/market.lua" then
    saw_market = true
  end
  if read_calls[i] == "virtual/collectors/run_state.lua" then
    saw_run_state = true
  end
end

ok(saw_values, "NFS-loaded raw reader should load nested shared values through the current module loader path")
ok(saw_common, "NFS-loaded raw reader should load the shared entity common reader module")
ok(saw_owned, "NFS-loaded raw reader should load the shared owned-entity reader module")
ok(saw_market, "NFS-loaded raw reader should load the shared market-entity reader module")
ok(saw_run_state, "NFS-loaded raw reader should load the run-state collector module")

_G.SMODS = old.SMODS
_G.NFS = old.NFS
