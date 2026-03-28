local BlindKey = dofile("mods/live_state_exporter/blind_key.lua")

local function assert_equal(left, right, message)
  if left ~= right then
    error(message or ("expected " .. tostring(right) .. ", got " .. tostring(left)), 2)
  end
end

local function assert_nil(value, message)
  if value ~= nil then
    error(message or ("expected nil, got " .. tostring(value)), 2)
  end
end

local function test_blind_select_uses_select_state()
  local blinds = {
    { slot = "Small", key = "bl_small", state = "Select" },
    { slot = "Big", key = "bl_big", state = "Upcoming" },
    { slot = "Boss", key = "bl_window", state = "Upcoming" },
  }
  local blind_key = BlindKey.derive("blind_select", blinds)

  assert_equal(blind_key, "bl_small", "blind_select should use the selected blind")
end

local function test_play_hand_uses_current_state()
  local blinds = {
    { slot = "Small", key = "bl_small", state = "Defeated" },
    { slot = "Big", key = "bl_big", state = "Current" },
    { slot = "Boss", key = "bl_pillar", state = "Upcoming" },
  }
  local blind_key = BlindKey.derive("play_hand", blinds)

  assert_equal(blind_key, "bl_big", "play_hand should use the current blind")
end

local function test_shop_uses_first_upcoming_blind_in_order()
  local blinds = {
    { slot = "Small", key = "bl_small", state = "Defeated" },
    { slot = "Big", key = "bl_big", state = "Upcoming" },
    { slot = "Boss", key = "bl_head", state = "Upcoming" },
  }
  local blind_key = BlindKey.derive("shop", blinds)

  assert_equal(blind_key, "bl_big", "shop should use the first upcoming blind in slot order")
end

local function test_missing_expected_state_returns_nil()
  local blinds = {
    { slot = "Small", key = "bl_small", state = "Defeated" },
    { slot = "Big", key = "bl_big", state = "Upcoming" },
  }
  local blind_key = BlindKey.derive("play_hand", blinds)

  assert_nil(blind_key, "missing expected blind state should keep blind_key nil")
end

test_blind_select_uses_select_state()
test_play_hand_uses_current_state()
test_shop_uses_first_upcoming_blind_in_order()
test_missing_expected_state_returns_nil()
