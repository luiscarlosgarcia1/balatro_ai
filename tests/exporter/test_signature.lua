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

local function test_pack_reward_choices_remaining_changes_signature()
  local first = Signature.make({
    state = {
      interaction_phase = "pack_reward",
      pack_contents = {
        choices_remaining = 1,
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
        choices_remaining = 2,
        cards = {
          { card_key = "c_fool" },
        },
      },
    },
  })

  assert_not_equal(first, second, "signature should track actionable pack choice state")
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

local function test_interest_object_changes_signature()
  local first = Signature.make({
    state = {
      interest = {
        amount = 1,
        cap = 25,
        no_interest = false,
      },
    },
  })

  local second = Signature.make({
    state = {
      interest = {
        amount = 1,
        cap = 50,
        no_interest = false,
      },
    },
  })

  assert_not_equal(first, second, "signature should track raw interest determinants")
end

local function test_run_info_hand_state_changes_signature()
  local first = Signature.make({
    state = {
      run_info = {
        hands = {
          ["Straight Flush"] = {
            level = 1,
            mult = 8,
            chips = 100,
            played = 0,
            played_this_round = 0,
          },
        },
      },
    },
  })

  local second = Signature.make({
    state = {
      run_info = {
        hands = {
          ["Straight Flush"] = {
            level = 2,
            mult = 12,
            chips = 140,
            played = 1,
            played_this_round = 1,
          },
        },
      },
    },
  })

  assert_not_equal(first, second, "signature should track per-hand run state")
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

test_missing_scalar_fields_still_produce_signature()
test_missing_item_keys_do_not_crash()
test_distinct_real_values_change_signature()
test_score_shape_changes_signature()
test_pack_reward_choices_remaining_changes_signature()
test_blind_and_skip_claim_fields_change_signature()
test_shop_item_structure_changes_signature()
test_interest_object_changes_signature()
test_run_info_hand_state_changes_signature()
test_card_zones_change_signature()
test_selection_references_change_signature()
