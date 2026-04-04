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
    },
  },
  consumables = {
    config = {
      card_limit = 3,
    },
  },
  hand = {
    config = {
      card_limit = 9,
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
