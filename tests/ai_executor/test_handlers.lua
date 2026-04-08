local handlers = dofile("mods/ai_executor/handlers.lua")

local function eq(a, b, msg)
  if a ~= b then
    error(msg or ("expected " .. tostring(b) .. ", got " .. tostring(a)), 2)
  end
end

local function ne(a, b, msg)
  if a == b then
    error(msg or ("expected values to differ, both are: " .. tostring(a)), 2)
  end
end

local function ok(v, msg)
  if not v then
    error(msg or "expected truthy value", 2)
  end
end

local function is_nil(v, msg)
  if v ~= nil then
    error(msg or ("expected nil, got: " .. tostring(v)), 2)
  end
end

-- ============================================================
-- Cycle 1 — tracer bullet: module loads, find_card_by_id works
-- ============================================================

ok(handlers.find_card_by_id ~= nil, "handlers should export find_card_by_id")
ok(handlers.dispatch ~= nil, "handlers should export dispatch")
ok(handlers.ACTIONABLE_STATE_NAMES ~= nil, "handlers should export ACTIONABLE_STATE_NAMES")
ok(handlers.is_actionable_state ~= nil, "handlers should export is_actionable_state")

local cards = {
  { ID = 1, key = "c_ace" },
  { ID = 2, key = "c_king" },
  { ID = 3, key = "c_queen" },
}

local found = handlers.find_card_by_id(cards, 2)
ok(found ~= nil, "find_card_by_id should find existing card")
eq(found.key, "c_king", "find_card_by_id should return correct card")

is_nil(handlers.find_card_by_id(cards, 99), "find_card_by_id should return nil for missing ID")
is_nil(handlers.find_card_by_id({}, 1), "find_card_by_id should return nil on empty table")
is_nil(handlers.find_card_by_id(nil, 1), "find_card_by_id should handle nil cards table")

-- ============================================================
-- Cycle 2 — play_hand
-- ============================================================

do
  local play_calls = 0
  local mock_G = {
    hand = {
      highlighted = {},
      cards = {
        { ID = 10, highlighted = false },
        { ID = 11, highlighted = false },
        { ID = 12, highlighted = false },
      },
    },
    FUNCS = {
      play_cards_from_highlighted = function()
        play_calls = play_calls + 1
      end,
    },
  }

  local err = handlers.dispatch(
    { kind = "play_hand", target_ids = { 10, 12 }, target_key = nil, order = {} },
    mock_G
  )
  is_nil(err, "play_hand should succeed")
  eq(play_calls, 1, "play_hand should call play_cards_from_highlighted once")
  eq(#mock_G.hand.highlighted, 2, "play_hand should highlight 2 cards")
  eq(mock_G.hand.highlighted[1].ID, 10, "play_hand should highlight card 10 first")
  eq(mock_G.hand.highlighted[2].ID, 12, "play_hand should highlight card 12 second")
  ok(mock_G.hand.cards[1].highlighted, "card 10 should be highlighted")
  ok(not mock_G.hand.cards[2].highlighted, "card 11 should not be highlighted")
  ok(mock_G.hand.cards[3].highlighted, "card 12 should be highlighted")
end

-- play_hand clears previously highlighted cards
do
  local play_calls = 0
  local prev = { ID = 99, highlighted = true }
  local mock_G = {
    hand = {
      highlighted = { prev },
      cards = { { ID = 10, highlighted = false }, prev },
    },
    FUNCS = {
      play_cards_from_highlighted = function()
        play_calls = play_calls + 1
      end,
    },
  }

  handlers.dispatch(
    { kind = "play_hand", target_ids = { 10 }, target_key = nil, order = {} },
    mock_G
  )
  ok(not prev.highlighted, "play_hand should clear previously highlighted card")
  eq(#mock_G.hand.highlighted, 1, "play_hand should only highlight the new target")
end

-- ============================================================
-- Cycle 3 — discard
-- ============================================================

do
  local discard_calls = 0
  local mock_G = {
    hand = {
      highlighted = {},
      cards = {
        { ID = 20, highlighted = false },
        { ID = 21, highlighted = false },
      },
    },
    FUNCS = {
      discard_cards_from_highlighted = function()
        discard_calls = discard_calls + 1
      end,
    },
  }

  local err = handlers.dispatch(
    { kind = "discard", target_ids = { 21 }, target_key = nil, order = {} },
    mock_G
  )
  is_nil(err, "discard should succeed")
  eq(discard_calls, 1, "discard should call discard_cards_from_highlighted once")
  eq(#mock_G.hand.highlighted, 1, "discard should highlight 1 card")
  eq(mock_G.hand.highlighted[1].ID, 21, "discard should highlight the correct card")
end

-- ============================================================
-- Cycle 4 — buy_shop_item
-- ============================================================

do
  local buy_calls = 0
  local bought_ref = nil
  local joker_item = { ID = 30, key = "j_joker" }
  local mock_G = {
    shop_jokers = { cards = { joker_item } },
    shop_vouchers = { cards = {} },
    shop_booster = { cards = {} },
    FUNCS = {
      buy_from_shop = function(e)
        buy_calls = buy_calls + 1
        bought_ref = e.config.ref_table
      end,
    },
  }

  local err = handlers.dispatch(
    { kind = "buy_shop_item", target_ids = { 30 }, target_key = nil, order = {} },
    mock_G
  )
  is_nil(err, "buy_shop_item should succeed")
  eq(buy_calls, 1, "buy_shop_item should call buy_from_shop once")
  ok(bought_ref == joker_item, "buy_shop_item should pass correct item as ref_table")
end

-- buy_shop_item calls use_card for booster packs (found in shop_booster)
do
  local use_calls = 0
  local used_ref = nil
  local booster = { ID = 31, key = "p_arcana_normal_1" }
  local mock_G = {
    shop_jokers = { cards = {} },
    shop_vouchers = { cards = {} },
    shop_booster = { cards = { booster } },
    FUNCS = {
      use_card = function(e)
        use_calls = use_calls + 1
        used_ref = e.config.ref_table
      end,
      buy_from_shop = function() error("buy_from_shop must not be called for booster packs") end,
    },
  }

  local err = handlers.dispatch(
    { kind = "buy_shop_item", target_ids = { 31 }, target_key = nil, order = {} },
    mock_G
  )
  is_nil(err, "buy_shop_item for booster should succeed")
  eq(use_calls, 1, "buy_shop_item for booster should call use_card")
  ok(used_ref == booster, "buy_shop_item for booster should pass correct item as ref_table")
end

-- buy_shop_item calls use_card for vouchers (found in shop_vouchers)
do
  local use_calls = 0
  local used_ref = nil
  local voucher = { ID = 32, key = "v_overstock_norm" }
  local mock_G = {
    shop_jokers = { cards = {} },
    shop_vouchers = { cards = { voucher } },
    shop_booster = { cards = {} },
    FUNCS = {
      use_card = function(e)
        use_calls = use_calls + 1
        used_ref = e.config.ref_table
      end,
      buy_from_shop = function() error("buy_from_shop must not be called for vouchers") end,
    },
  }

  local err = handlers.dispatch(
    { kind = "buy_shop_item", target_ids = { 32 }, target_key = nil, order = {} },
    mock_G
  )
  is_nil(err, "buy_shop_item for voucher should succeed")
  eq(use_calls, 1, "buy_shop_item for voucher should call use_card")
  ok(used_ref == voucher, "buy_shop_item for voucher should pass correct item as ref_table")
end

-- buy_shop_item returns error when item not found
do
  local mock_G = {
    shop_jokers = { cards = {} },
    shop_vouchers = { cards = {} },
    shop_booster = { cards = {} },
    FUNCS = { use_card = function() end, buy_from_shop = function() end },
  }
  local err = handlers.dispatch(
    { kind = "buy_shop_item", target_ids = { 999 }, target_key = nil, order = {} },
    mock_G
  )
  ne(err, nil, "buy_shop_item should return error when item not found")
  ok(string.find(err, "not found") ~= nil, "buy_shop_item error should mention 'not found'")
end

-- ============================================================
-- Cycle 4b — buy_and_use
-- ============================================================

-- buy_and_use success, no hand targets
do
  local buy_calls = 0
  local buy_id = nil
  local used_ref = nil
  local tarot = { ID = 33, key = "c_the_fool" }
  local mock_G = {
    shop_jokers  = { cards = { tarot } },
    shop_vouchers = { cards = {} },
    shop_booster  = { cards = {} },
    hand = { highlighted = {}, cards = {} },
    FUNCS = {
      buy_from_shop = function(e)
        buy_calls = buy_calls + 1
        buy_id    = e.config.id
        used_ref  = e.config.ref_table
      end,
    },
  }

  local err = handlers.dispatch(
    { kind = "buy_and_use", target_ids = { 33 }, target_key = nil, order = {} },
    mock_G
  )
  is_nil(err, "buy_and_use should succeed")
  eq(buy_calls, 1, "buy_and_use should call G.FUNCS.buy_from_shop once")
  eq(buy_id, "buy_and_use", "buy_and_use should pass config.id = 'buy_and_use'")
  ok(used_ref == tarot, "buy_and_use should pass correct item as ref_table")
end

-- buy_and_use with hand targets highlights those cards before buying
do
  local buy_calls = 0
  local tarot = { ID = 34, key = "c_strength" }
  local card_a = { ID = 10, highlighted = false }
  local card_b = { ID = 11, highlighted = false }
  local mock_G = {
    shop_jokers  = { cards = { tarot } },
    shop_vouchers = { cards = {} },
    shop_booster  = { cards = {} },
    hand = { highlighted = {}, cards = { card_a, card_b } },
    FUNCS = {
      buy_from_shop = function() buy_calls = buy_calls + 1 end,
    },
  }

  local err = handlers.dispatch(
    { kind = "buy_and_use", target_ids = { 34, 10, 11 }, target_key = nil, order = {} },
    mock_G
  )
  is_nil(err, "buy_and_use with hand targets should succeed")
  eq(buy_calls, 1, "buy_and_use should call G.FUNCS.buy_from_shop once")
  eq(#mock_G.hand.highlighted, 2, "buy_and_use should highlight 2 hand cards")
  ok(card_a.highlighted, "buy_and_use should highlight card_a")
  ok(card_b.highlighted, "buy_and_use should highlight card_b")
end

-- buy_and_use returns error when item not found
do
  local mock_G = {
    shop_jokers  = { cards = {} },
    shop_vouchers = { cards = {} },
    shop_booster  = { cards = {} },
    FUNCS = { buy_from_shop = function() end },
  }
  local err = handlers.dispatch(
    { kind = "buy_and_use", target_ids = { 99999 }, target_key = nil, order = {} },
    mock_G
  )
  ne(err, nil, "buy_and_use should return error when item not found")
  ok(string.find(err, "buy_and_use") ~= nil, "buy_and_use error should mention 'buy_and_use'")
end

-- ============================================================
-- Cycle 5 — sell_joker
-- ============================================================

do
  local sell_calls = 0
  local joker = {
    ID = 40,
    sell_card = function(self)
      sell_calls = sell_calls + 1
    end,
  }
  local mock_G = { jokers = { cards = { joker } }, FUNCS = {} }

  local err = handlers.dispatch(
    { kind = "sell_joker", target_ids = { 40 }, target_key = nil, order = {} },
    mock_G
  )
  is_nil(err, "sell_joker should succeed")
  eq(sell_calls, 1, "sell_joker should call sell_card on the joker")
end

-- sell_joker returns error when joker not found
do
  local mock_G = { jokers = { cards = {} }, FUNCS = {} }
  local err = handlers.dispatch(
    { kind = "sell_joker", target_ids = { 999 }, target_key = nil, order = {} },
    mock_G
  )
  ne(err, nil, "sell_joker should return error when joker not found")
end

-- ============================================================
-- Cycle 6 — reroll_shop
-- ============================================================

do
  local calls = 0
  local mock_G = { FUNCS = { reroll_shop = function() calls = calls + 1 end } }

  local err = handlers.dispatch(
    { kind = "reroll_shop", target_ids = {}, target_key = nil, order = {} },
    mock_G
  )
  is_nil(err, "reroll_shop should succeed")
  eq(calls, 1, "reroll_shop should call G.FUNCS.reroll_shop")
end

-- ============================================================
-- Cycle 7 — leave_shop
-- ============================================================

do
  local calls = 0
  local mock_G = { FUNCS = { toggle_shop = function() calls = calls + 1 end } }

  local err = handlers.dispatch(
    { kind = "leave_shop", target_ids = {}, target_key = nil, order = {} },
    mock_G
  )
  is_nil(err, "leave_shop should succeed")
  eq(calls, 1, "leave_shop should call G.FUNCS.toggle_shop")
end

-- Builds a mock blind_select_opts entry: a UIBox-like table with
-- get_UIE_by_ID('select_blind_button') returning a UIElement-like child whose
-- .UIBox back-references the container and .config.ref_table holds the blind data.
local function make_blind_opt(blind_config)
  local elem = { config = { ref_table = blind_config } }
  local opt = {}
  opt.get_UIE_by_ID = function(self, id)
    if id == "select_blind_button" then return elem end
    return nil
  end
  elem.UIBox = opt
  return opt, elem
end

-- ============================================================
-- Cycle 8 — select_blind
-- ============================================================

do
  local selected_elem = nil
  local small_opt, small_elem = make_blind_opt({ key = "bl_small" })
  local big_opt,   big_elem   = make_blind_opt({ key = "bl_big"   })
  local boss_opt,  boss_elem  = make_blind_opt({ key = "bl_hook"  })
  local mock_G = {
    GAME = {
      round_resets = {
        blind_choices = {
          small = "bl_small",
          big = "bl_big",
          boss = "bl_hook",
        },
      },
    },
    blind_select_opts = { small = small_opt, big = big_opt, boss = boss_opt },
    FUNCS = { select_blind = function(e) selected_elem = e end },
  }

  local err = handlers.dispatch(
    { kind = "select_blind", target_ids = {}, target_key = "bl_big", order = {} },
    mock_G
  )
  is_nil(err, "select_blind should succeed")
  ok(selected_elem ~= nil, "select_blind should call G.FUNCS.select_blind")
  ok(selected_elem == big_elem, "select_blind should pass the UIElement from get_UIE_by_ID")
  ok(selected_elem.UIBox == big_opt, "selected element's .UIBox should be the blind UIBox")
end

-- select_blind returns error when blind key not found
do
  local opt, _ = make_blind_opt({ key = "bl_small" })
  local mock_G = {
    GAME = { round_resets = { blind_choices = { small = "bl_small" } } },
    blind_select_opts = { small = opt },
    FUNCS = { select_blind = function() end },
  }
  local err = handlers.dispatch(
    { kind = "select_blind", target_ids = {}, target_key = "bl_nonexistent", order = {} },
    mock_G
  )
  ne(err, nil, "select_blind should return error for unknown blind key")
end

-- ============================================================
-- Cycle 9 — skip_blind
-- ============================================================

do
  local skipped_elem = nil
  local small_opt, small_elem = make_blind_opt({ key = "bl_small" })
  local big_opt,   big_elem   = make_blind_opt({ key = "bl_big"   })
  local boss_opt,  boss_elem  = make_blind_opt({ key = "bl_hook"  })
  local mock_G = {
    GAME = {
      round_resets = {
        blind_choices = {
          small = "bl_small",
          big = "bl_big",
          boss = "bl_hook",
        },
      },
    },
    blind_select_opts = { small = small_opt, big = big_opt, boss = boss_opt },
    FUNCS = { skip_blind = function(e) skipped_elem = e end },
  }

  local err = handlers.dispatch(
    { kind = "skip_blind", target_ids = {}, target_key = "bl_small", order = {} },
    mock_G
  )
  is_nil(err, "skip_blind should succeed")
  ok(skipped_elem == small_elem, "skip_blind should pass the UIElement from get_UIE_by_ID")
  ok(skipped_elem.UIBox == small_opt, "skipped element's .UIBox should be the blind UIBox")
end

-- ============================================================
-- Cycle 10 — pick_pack_item
-- ============================================================

do
  local use_calls = 0
  local used_ref = nil
  local pack_card = { ID = 50, key = "c_2_of_spades" }
  local mock_G = {
    pack_cards = { cards = { pack_card } },
    FUNCS = {
      use_card = function(e)
        use_calls = use_calls + 1
        used_ref = e.config.ref_table
      end,
    },
  }

  local err = handlers.dispatch(
    { kind = "pick_pack_item", target_ids = { 50 }, target_key = nil, order = {} },
    mock_G
  )
  is_nil(err, "pick_pack_item should succeed")
  eq(use_calls, 1, "pick_pack_item should call G.FUNCS.use_card once")
  ok(used_ref == pack_card, "pick_pack_item should pass correct card as ref_table")
end

-- pick_pack_item returns error when card not found
do
  local mock_G = {
    pack_cards = { cards = {} },
    FUNCS = { use_card = function() end },
  }
  local err = handlers.dispatch(
    { kind = "pick_pack_item", target_ids = { 999 }, target_key = nil, order = {} },
    mock_G
  )
  ne(err, nil, "pick_pack_item should return error when card not found")
end

-- ============================================================
-- Cycle 11 — skip_pack
-- ============================================================

do
  local calls = 0
  local mock_G = { FUNCS = { skip_booster = function() calls = calls + 1 end } }

  local err = handlers.dispatch(
    { kind = "skip_pack", target_ids = {}, target_key = nil, order = {} },
    mock_G
  )
  is_nil(err, "skip_pack should succeed")
  eq(calls, 1, "skip_pack should call G.FUNCS.skip_booster")
end

-- ============================================================
-- Cycle 12 — use_consumable
-- ============================================================

do
  local use_calls = 0
  local used_ref = nil
  local consumable = { ID = 60, key = "c_the_fool" }
  local target = { ID = 61, highlighted = false }
  local other = { ID = 62, highlighted = false }
  local mock_G = {
    consumeables = { cards = { consumable } },
    hand = {
      highlighted = {},
      cards = { target, other },
    },
    FUNCS = {
      use_card = function(e)
        use_calls = use_calls + 1
        used_ref = e.config.ref_table
      end,
    },
  }

  local err = handlers.dispatch(
    { kind = "use_consumable", target_ids = { 60, 61 }, target_key = nil, order = {} },
    mock_G
  )
  is_nil(err, "use_consumable should succeed")
  eq(use_calls, 1, "use_consumable should call G.FUNCS.use_card once")
  ok(used_ref == consumable, "use_consumable should pass the consumable as ref_table")
  eq(#mock_G.hand.highlighted, 1, "use_consumable should highlight 1 target card")
  ok(target.highlighted, "use_consumable should highlight the target card")
  ok(not other.highlighted, "use_consumable should not highlight non-target card")
end

-- use_consumable with no hand targets
do
  local use_calls = 0
  local consumable = { ID = 70, key = "c_strength" }
  local mock_G = {
    consumeables = { cards = { consumable } },
    hand = { highlighted = {}, cards = {} },
    FUNCS = { use_card = function() use_calls = use_calls + 1 end },
  }

  local err = handlers.dispatch(
    { kind = "use_consumable", target_ids = { 70 }, target_key = nil, order = {} },
    mock_G
  )
  is_nil(err, "use_consumable with no targets should succeed")
  eq(use_calls, 1, "use_consumable with no targets should still call use_card")
end

-- use_consumable falls back to G.consumables (alternate spelling)
do
  local use_calls = 0
  local consumable = { ID = 71, key = "c_tower" }
  local mock_G = {
    consumables = { cards = { consumable } },  -- note: alternate spelling
    hand = { highlighted = {}, cards = {} },
    FUNCS = { use_card = function() use_calls = use_calls + 1 end },
  }

  local err = handlers.dispatch(
    { kind = "use_consumable", target_ids = { 71 }, target_key = nil, order = {} },
    mock_G
  )
  is_nil(err, "use_consumable should fall back to G.consumables spelling")
  eq(use_calls, 1, "use_consumable via alternate spelling should call use_card")
end

-- use_consumable returns error when consumable not found
do
  local mock_G = {
    consumeables = { cards = {} },
    hand = { highlighted = {}, cards = {} },
    FUNCS = { use_card = function() end },
  }
  local err = handlers.dispatch(
    { kind = "use_consumable", target_ids = { 999 }, target_key = nil, order = {} },
    mock_G
  )
  ne(err, nil, "use_consumable should return error when consumable not found")
end

-- ============================================================
-- Cycle 13 — dispatch error: unknown action kind
-- ============================================================

do
  local err = handlers.dispatch(
    { kind = "nonexistent_action", target_ids = {}, target_key = nil, order = {} },
    {}
  )
  ne(err, nil, "dispatch should return error for unknown action kind")
  ok(string.find(err, "unknown") ~= nil, "error should mention 'unknown'")
end

-- ============================================================
-- Cycle 13b — cash_out
-- ============================================================

do
  local cash_out_calls = 0
  local mock_G = {
    FUNCS = {
      cash_out = function(e)
        ok(type(e) == "table" and type(e.config) == "table", "cash_out called with {config={}}")
        cash_out_calls = cash_out_calls + 1
      end,
    },
  }
  local err = handlers.dispatch({ kind = "cash_out", target_ids = {}, target_key = nil, order = {} }, mock_G)
  is_nil(err, "cash_out dispatch should succeed")
  eq(cash_out_calls, 1, "cash_out should call G.FUNCS.cash_out once")
end

-- ============================================================
-- Cycle 14 — ACTIONABLE_STATE_NAMES + is_actionable_state
-- ============================================================

do
  eq(#handlers.ACTIONABLE_STATE_NAMES, 10, "should declare exactly 10 actionable states")

  local name_set = {}
  for _, name in ipairs(handlers.ACTIONABLE_STATE_NAMES) do
    name_set[name] = true
  end

  ok(name_set["SELECTING_HAND"], "SELECTING_HAND should be actionable")
  ok(name_set["SHOP"], "SHOP should be actionable")
  ok(name_set["BLIND_SELECT"], "BLIND_SELECT should be actionable")
  ok(name_set["ROUND_EVAL"], "ROUND_EVAL should be actionable")
  ok(name_set["TAROT_PACK"], "TAROT_PACK should be actionable")
  ok(name_set["PLANET_PACK"], "PLANET_PACK should be actionable")
  ok(name_set["SPECTRAL_PACK"], "SPECTRAL_PACK should be actionable")
  ok(name_set["BUFFOON_PACK"], "BUFFOON_PACK should be actionable")
  ok(name_set["STANDARD_PACK"], "STANDARD_PACK should be actionable")
  ok(name_set["SMODS_BOOSTER_OPENED"], "SMODS_BOOSTER_OPENED should be actionable")
end

do
  local mock_G = {
    STATE = 5,
    STATES = {
      SELECTING_HAND = 1,
      SHOP = 2,
      BLIND_SELECT = 3,
      TAROT_PACK = 4,
      PLANET_PACK = 5,
      SPECTRAL_PACK = 6,
      BUFFOON_PACK = 7,
      STANDARD_PACK = 8,
      ROUND_EVAL = 11,
      HAND_PLAYED = 9,
      SCORING = 10,
      SMODS_BOOSTER_OPENED = 12,
    },
  }

  ok(handlers.is_actionable_state(mock_G), "PLANET_PACK (5) should be actionable")

  mock_G.STATE = 9
  ok(not handlers.is_actionable_state(mock_G), "HAND_PLAYED (9) should not be actionable")

  mock_G.STATE = 1
  ok(handlers.is_actionable_state(mock_G), "SELECTING_HAND (1) should be actionable")

  mock_G.STATE = 8
  ok(handlers.is_actionable_state(mock_G), "STANDARD_PACK (8) should be actionable")

  mock_G.STATE = 11
  ok(handlers.is_actionable_state(mock_G), "ROUND_EVAL (11) should be actionable")

  mock_G.STATE = 12
  ok(handlers.is_actionable_state(mock_G), "SMODS_BOOSTER_OPENED (12) should be actionable")

  ok(not handlers.is_actionable_state({ STATE = 5 }), "no G.STATES should mean not actionable")
  ok(not handlers.is_actionable_state(nil), "nil G should not be actionable")
end

print("test_handlers: all tests passed")
