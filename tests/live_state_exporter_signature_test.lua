local Signature = dofile("mods/live_state_exporter/signature.lua")

local function assert_true(condition, message)
  if not condition then
    error(message or "assertion failed", 2)
  end
end

local function assert_not_equal(left, right, message)
  if left == right then
    error(message or ("expected values to differ, both were: " .. tostring(left)), 2)
  end
end

local function assert_equal(left, right, message)
  if left ~= right then
    error(message or ("expected values to match, left=" .. tostring(left) .. " right=" .. tostring(right)), 2)
  end
end

local function test_missing_scalar_fields_still_produce_signature()
  local signature = Signature.make({
    state = {
      interaction_phase = "shop",
      money = 4,
      blind_key = "bl_small",
      score = {
        current = 12,
        target = 300,
      },
    },
  })

  assert_true(type(signature) == "string", "signature should be a string")
  assert_true(#signature > 0, "signature should not be empty")
end

local function test_missing_item_keys_do_not_crash()
  local signature = Signature.make({
    state = {
      jokers = {
        { key = "j_joker" },
        { key = nil },
      },
      vouchers = {
        { key = nil },
      },
      consumables = {
        { key = "c_fool" },
      },
    },
  })

  assert_true(type(signature) == "string", "signature should be a string for partial item data")
end

local function test_distinct_real_values_change_signature()
  local first = Signature.make({
    state = {
      interaction_phase = "shop",
      money = 4,
      score = {
        current = 25,
        target = 300,
      },
      jokers = {
        { key = "j_joker" },
      },
    },
  })

  local second = Signature.make({
    state = {
      interaction_phase = "shop",
      money = 5,
      score = {
        current = 25,
        target = 300,
      },
      jokers = {
        { key = "j_joker" },
      },
    },
  })

  assert_not_equal(first, second, "signature should change when gameplay-relevant state changes")
end

local function test_score_shape_changes_signature()
  local first = Signature.make({
    state = {
      interaction_phase = "play_hand",
      score = {
        current = 120,
        target = 300,
      },
    },
  })

  local second = Signature.make({
    state = {
      interaction_phase = "play_hand",
      score = {
        current = 180,
        target = 300,
      },
    },
  })

  assert_not_equal(first, second, "signature should track canonical score fields")
end

local function test_pack_reward_pack_key_changes_signature()
  local first = Signature.make({
    state = {
      interaction_phase = "pack_reward",
      pack_contents = {
        pack_key = "p_arcana_normal_1",
        cards = {
          { card_key = "c_fool" },
        },
      },
    },
  })

  local second = Signature.make({
    state = {
      interaction_phase = "pack_reward",
      pack_contents = {
        pack_key = "p_arcana_mega_2",
        cards = {
          { card_key = "c_fool" },
        },
      },
    },
  })

  assert_not_equal(first, second, "signature should track exact pack identity through pack_contents")
end

local function test_legacy_open_pack_kind_does_not_affect_signature()
  local first = Signature.make({
    state = {
      interaction_phase = "pack_reward",
      pack_contents = {
        pack_key = "p_arcana_normal_1",
        open_pack_kind = "tarot",
      },
    },
  })

  local second = Signature.make({
    state = {
      interaction_phase = "pack_reward",
      pack_contents = {
        pack_key = "p_arcana_normal_1",
        open_pack_kind = "planet",
      },
    },
  })

  assert_equal(first, second, "signature should ignore removed legacy pack kind fields")
end

local function test_blind_and_skip_claim_fields_change_signature()
  local first = Signature.make({
    state = {
      blinds = {
        { key = "bl_small", state = "skipped", tag_key = "tag_small", tag_claimed = true },
      },
    },
  })

  local second = Signature.make({
    state = {
      blinds = {
        { key = "bl_small", state = "upcoming", tag_key = "tag_small", tag_claimed = false },
      },
    },
  })

  assert_not_equal(first, second, "signature should track canonical blind and skip-tag claim semantics")
end

local function test_shop_item_structure_changes_signature()
  local first = Signature.make({
    state = {
      shop_items = {
        { key = "j_credit_card", edition = "foil", sell_price = 2, stickers = { "rental" } },
      },
    },
  })

  local second = Signature.make({
    state = {
      shop_items = {
        { key = "j_credit_card", edition = "negative", sell_price = 2, stickers = { "rental" } },
      },
    },
  })

  assert_not_equal(first, second, "signature should track canonical shop item structure, not only item keys")
end

local function test_card_zones_change_signature()
  local first = Signature.make({
    state = {
      cards_in_hand = {
        { card_key = "c_a" },
      },
      cards_in_deck = {
        { card_key = "c_k" },
      },
    },
  })

  local second = Signature.make({
    state = {
      cards_in_hand = {
        { card_key = "s_a" },
      },
      cards_in_deck = {
        { card_key = "c_k" },
      },
    },
  })

  assert_not_equal(first, second, "signature should track canonical hand and deck card zones")
end

local function test_selection_references_change_signature()
  local first = Signature.make({
    state = {
      selected_cards = {
        { zone = "cards_in_hand", card_key = "h_8" },
      },
    },
  })

  local second = Signature.make({
    state = {
      selected_cards = {
        { zone = "jokers", joker_key = "j_blueprint" },
      },
    },
  })

  assert_not_equal(first, second, "signature should track lightweight selected-card references")
end

local function test_removed_highlighted_card_does_not_affect_signature()
  local first = Signature.make({
    state = {
      selected_cards = {
        { zone = "cards_in_hand", card_key = "h_8" },
      },
      highlighted_card = {
        zone = "jokers",
        joker_key = "j_blueprint",
      },
    },
  })

  local second = Signature.make({
    state = {
      selected_cards = {
        { zone = "cards_in_hand", card_key = "h_8" },
      },
      highlighted_card = {
        zone = "jokers",
        joker_key = "j_brainstorm",
      },
    },
  })

  assert_equal(first, second, "signature should ignore removed highlighted_card payloads")
end

local function test_legacy_booster_packs_do_not_affect_signature()
  local first = Signature.make({
    state = {
      shop_items = {
        { key = "p_buffoon_normal_1" },
      },
      booster_packs = {
        { key = "p_ghost_legacy_1" },
      },
    },
  })

  local second = Signature.make({
    state = {
      shop_items = {
        { key = "p_buffoon_normal_1" },
      },
      booster_packs = {
        { key = "p_arcana_legacy_2" },
      },
    },
  })

  assert_equal(first, second, "signature should ignore removed legacy booster_packs")
end

test_missing_scalar_fields_still_produce_signature()
test_missing_item_keys_do_not_crash()
test_distinct_real_values_change_signature()
test_score_shape_changes_signature()
test_pack_reward_pack_key_changes_signature()
test_legacy_open_pack_kind_does_not_affect_signature()
test_blind_and_skip_claim_fields_change_signature()
test_shop_item_structure_changes_signature()
test_card_zones_change_signature()
test_selection_references_change_signature()
test_removed_highlighted_card_does_not_affect_signature()
test_legacy_booster_packs_do_not_affect_signature()
