local schema = dofile("mods/live_state_exporter/schema.lua")

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

local shell = schema.build_shell({})

eq(shell.state_id, 0, "state_id should default to 0")
eq(shell.dollars, 0, "dollars should default to 0")
eq(shell.hands_left, 0, "hands_left should default to 0")
eq(shell.discards_left, 0, "discards_left should default to 0")
ok(type(shell.score) == "table", "score should always be present")
eq(shell.score.current, 0, "score.current should default to 0")
eq(shell.score.target, 0, "score.target should default to 0")
ok(schema.is_null(shell.interaction_phase), "interaction_phase should default to null")
ok(schema.is_null(shell.deck_key), "deck_key should default to null")
ok(schema.is_null(shell.stake_id), "stake_id should default to null")
ok(schema.is_null(shell.blind_key), "blind_key should default to null")
ok(schema.is_null(shell.ante), "ante should default to null")
ok(schema.is_null(shell.round), "round should default to null")
ok(schema.is_null(shell.joker_slots), "joker_slots should default to null")
ok(schema.is_null(shell.consumable_slots), "consumable_slots should default to null")
ok(schema.is_null(shell.run_info), "run_info should default to null")
ok(schema.is_null(shell.interest), "interest should default to null")
ok(schema.is_null(shell.reroll_cost), "reroll_cost should default to null")
ok(schema.is_null(shell.pack_contents), "pack_contents should default to null")
ok(schema.is_null(shell.hand_size), "hand_size should default to null")
is_arr(shell.blinds, "blinds should be an empty array")
is_arr(shell.jokers, "jokers should be an empty array")
is_arr(shell.consumables, "consumables should be an empty array")
is_arr(shell.tags, "tags should be an empty array")
is_arr(shell.vouchers, "vouchers should be an empty array")
is_arr(shell.shop_items, "shop_items should be an empty array")
is_arr(shell.cards_in_hand, "cards_in_hand should be an empty array")
is_arr(shell.selected_cards, "selected_cards should be an empty array")
is_arr(shell.cards_in_deck, "cards_in_deck should be an empty array")

local shaped = schema.build_shell({
  interaction_phase = "shop",
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

eq(shaped.interaction_phase, "shop", "interaction_phase should be preserved when present")
ok(schema.is_null(shaped.cards_in_hand[1].enhancement), "hand card enhancement should shape to null")
ok(schema.is_null(shaped.cards_in_hand[1].edition), "hand card edition should shape to null")
ok(schema.is_null(shaped.cards_in_hand[1].seal), "hand card seal should shape to null")
ok(schema.is_null(shaped.cards_in_hand[1].facing), "hand card facing should shape to null")
ok(schema.is_null(shaped.cards_in_hand[1].cost), "hand card cost should shape to null")
ok(schema.is_null(shaped.cards_in_hand[1].sell_cost), "hand card sell_cost should shape to null")
ok(schema.is_null(shaped.jokers[1].perish_tally), "joker perish_tally should shape to null")
ok(schema.is_null(shaped.jokers[1].edition), "joker edition should shape to null")
ok(schema.is_null(shaped.jokers[1].sell_cost), "joker sell_cost should shape to null")
ok(schema.is_null(shaped.consumables[1].edition), "consumable edition should shape to null")
ok(schema.is_null(shaped.consumables[1].cost), "consumable cost should shape to null")
ok(schema.is_null(shaped.consumables[1].sell_cost), "consumable sell_cost should shape to null")

local shaped_market = schema.build_shell({
  interaction_phase = "pack_reward",
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

eq(shaped_market.interaction_phase, "pack_reward", "shell should preserve pack interaction phase")
ok(type(shaped_market.shop_items) == "table", "shell should keep shop_items array")
ok(schema.is_null(shaped_market.shop_items[1].joker), "shell should null-fill inactive shop joker member")
ok(schema.is_null(shaped_market.shop_items[1].consumable), "shell should null-fill inactive shop consumable member")
ok(schema.is_null(shaped_market.shop_items[1].voucher), "shell should null-fill inactive shop voucher member")
ok(schema.is_null(shaped_market.shop_items[1].pack), "shell should null-fill inactive shop pack member")
ok(schema.is_null(shaped_market.shop_items[2].card), "shell should null-fill inactive shop card member")
ok(schema.is_null(shaped_market.shop_items[2].joker), "shell should null-fill inactive shop joker member on voucher wrappers")
eq(shaped_market.shop_items[2].voucher.key, "v_clearance_sale", "shell should preserve active shop voucher payload")
ok(type(shaped_market.pack_contents) == "table", "shell should keep active pack_contents object")
ok(schema.is_null(shaped_market.pack_contents.pack.cost), "shell should null-fill missing pack cost")
eq(shaped_market.pack_contents.choices_remaining, 2, "shell should preserve pack choice count")
eq(shaped_market.pack_contents.skip_available, false, "shell should preserve pack skip flag")
eq(#shaped_market.pack_contents.items, 3, "shell should keep pack item array")
ok(schema.is_null(shaped_market.pack_contents.items[1].perish_tally), "shell should null-fill missing joker perish_tally in pack items")
ok(schema.is_null(shaped_market.pack_contents.items[2].enhancement), "shell should null-fill missing card enhancement in pack items")
ok(schema.is_null(shaped_market.pack_contents.items[3].edition), "shell should null-fill missing consumable edition in pack items")

local malformed = schema.build_shell({
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

ok(schema.is_null(malformed.run_info), "shell should collapse malformed run_info to null")
ok(schema.is_null(malformed.interest), "shell should collapse malformed interest to null")
is_arr(malformed.blinds, "shell should keep malformed blinds as an empty array")
is_arr(malformed.tags, "shell should keep malformed tags as an empty array")
is_arr(malformed.vouchers, "shell should keep malformed vouchers as an empty array")
is_arr(malformed.shop_items, "shell should keep malformed shop_items as an empty array")
is_arr(malformed.cards_in_hand, "shell should keep malformed cards_in_hand as an empty array")
is_arr(malformed.selected_cards, "shell should keep malformed selected_cards as an empty array")
is_arr(malformed.cards_in_deck, "shell should keep malformed cards_in_deck as an empty array")
