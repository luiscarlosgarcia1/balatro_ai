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
        { key = "c_fool", kind = "tarot" },
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

local function test_pack_reward_open_pack_kind_changes_signature()
  local first = Signature.make({
    state = {
      interaction_phase = "pack_reward",
      pack_contents = {
        open_pack_kind = "tarot",
      },
    },
  })

  local second = Signature.make({
    state = {
      interaction_phase = "pack_reward",
      pack_contents = {
        open_pack_kind = "planet",
      },
    },
  })

  assert_not_equal(first, second, "signature should track pack kind through pack_contents")
end

local function test_blind_and_skip_claim_fields_change_signature()
  local first = Signature.make({
    state = {
      skip_tags = {
        { slot = "small", key = "tag_small", claimed = true },
      },
      blinds = {
        { slot = "small", key = "bl_small", state = "skipped", tag_key = "tag_small", tag_claimed = true },
      },
    },
  })

  local second = Signature.make({
    state = {
      skip_tags = {
        { slot = "small", key = "tag_small", claimed = false },
      },
      blinds = {
        { slot = "small", key = "bl_small", state = "upcoming", tag_key = "tag_small", tag_claimed = false },
      },
    },
  })

  assert_not_equal(first, second, "signature should track canonical blind and skip-tag claim semantics")
end

test_missing_scalar_fields_still_produce_signature()
test_missing_item_keys_do_not_crash()
test_distinct_real_values_change_signature()
test_score_shape_changes_signature()
test_pack_reward_open_pack_kind_changes_signature()
test_blind_and_skip_claim_fields_change_signature()
