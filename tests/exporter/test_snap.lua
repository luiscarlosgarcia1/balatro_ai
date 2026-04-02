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
