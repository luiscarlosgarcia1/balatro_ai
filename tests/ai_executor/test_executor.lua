local executor_mod = dofile("mods/ai_executor/executor.lua")

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
-- Helpers
-- ============================================================

-- Run all queued events to completion (immediate events once, condition events
-- until they return true).
local function flush_events(queued)
  local max_passes = 20
  for pass = 1, max_passes do
    local pending = false
    for i = 1, #queued do
      local ev = queued[i]
      if not ev._done then
        local result = ev.func(ev)
        if result then
          ev._done = true
        else
          pending = true
        end
      end
    end
    if not pending then
      return
    end
  end
end

-- Build a standard mock G with the given STATE value (defaults to SELECTING_HAND=1).
local function make_mock_G(state_override)
  return {
    STATE = state_override or 1,
    STATES = {
      SELECTING_HAND = 1,
      SHOP = 2,
      BLIND_SELECT = 3,
      TAROT_PACK = 4,
      PLANET_PACK = 5,
      SPECTRAL_PACK = 6,
      BUFFOON_PACK = 7,
      STANDARD_PACK = 8,
      HAND_PLAYED = 9,
    },
    hand = {
      highlighted = {},
      cards = { { ID = 1, highlighted = false } },
    },
    FUNCS = {
      play_cards_from_highlighted = function() end,
    },
  }
end

-- ============================================================
-- Cycle 15 — tick() is a no-op when action.json absent
-- ============================================================

do
  local queued = {}
  local ex = executor_mod.new_executor({
    file_exists = function() return false end,
    read_file = function() return nil end,
    write_file = function() return true end,
    remove_file = function() end,
    decode_json = function(t) return t end,
    add_event = function(ev) queued[#queued + 1] = ev end,
    get_G = make_mock_G,
  })

  local result = ex:tick()
  ok(result == false, "tick() should return false when action.json absent")
  eq(#queued, 0, "tick() should queue no events when action.json absent")
end

-- ============================================================
-- Cycle 16 — tick() queues events when action.json is present
-- ============================================================

do
  local queued = {}
  local play_calls = 0
  local mock_G = make_mock_G()
  mock_G.FUNCS.play_cards_from_highlighted = function() play_calls = play_calls + 1 end

  local action_present = true
  local ex = executor_mod.new_executor({
    file_exists = function(path) return action_present end,
    read_file = function(path)
      return { actions = { { kind = "play_hand", target_ids = { 1 }, target_key = nil, order = {} } } }
    end,
    write_file = function() return true end,
    remove_file = function(path) action_present = false end,
    decode_json = function(t) return t end,  -- identity: read_file already returns a table
    add_event = function(ev) queued[#queued + 1] = ev end,
    get_G = function() return mock_G end,
  })

  local result = ex:tick()
  ok(result == true, "tick() should return true when action.json present")
  -- 1 action event + 1 condition event
  eq(#queued, 2, "tick() should queue one action event plus one condition event")

  -- Execute all events: action fires play_hand, condition sees actionable state
  flush_events(queued)
  eq(play_calls, 1, "action event should have called play_hand handler")
  ok(not action_present, "condition event should have deleted action.json")
end

-- ============================================================
-- Cycle 16b — busy flag prevents re-processing
-- ============================================================

do
  local queued = {}
  local action_present = true
  local ex = executor_mod.new_executor({
    file_exists = function() return action_present end,
    read_file = function()
      return { actions = { { kind = "play_hand", target_ids = { 1 }, target_key = nil, order = {} } } }
    end,
    write_file = function() return true end,
    remove_file = function() action_present = false end,
    decode_json = function(t) return t end,
    add_event = function(ev) queued[#queued + 1] = ev end,
    get_G = make_mock_G,
  })

  ex:tick()  -- first tick: queues events, sets busy
  local count_after_first = #queued

  ex:tick()  -- second tick while busy: should be a no-op
  eq(#queued, count_after_first, "tick() should not re-queue events while busy")
end

-- ============================================================
-- Cycle 16c — multiple actions in queue all execute
-- ============================================================

do
  local queued = {}
  local calls = {}
  local mock_G = {
    STATE = 2,  -- SHOP
    STATES = { SHOP = 2 },
    FUNCS = {
      reroll_shop = function() calls[#calls + 1] = "reroll" end,
      toggle_shop = function() calls[#calls + 1] = "leave" end,
    },
  }

  local action_present = true
  local ex = executor_mod.new_executor({
    file_exists = function() return action_present end,
    read_file = function()
      return {
        actions = {
          { kind = "reroll_shop", target_ids = {}, target_key = nil, order = {} },
          { kind = "leave_shop",  target_ids = {}, target_key = nil, order = {} },
        },
      }
    end,
    write_file = function() return true end,
    remove_file = function() action_present = false end,
    decode_json = function(t) return t end,
    add_event = function(ev) queued[#queued + 1] = ev end,
    get_G = function() return mock_G end,
  })

  ex:tick()
  -- 2 action events + 1 condition event
  eq(#queued, 3, "tick() should queue one event per action plus one condition event")

  flush_events(queued)
  eq(#calls, 2, "both action handlers should have executed")
  eq(calls[1], "reroll", "reroll_shop should execute first")
  eq(calls[2], "leave", "leave_shop should execute second")
  ok(not action_present, "condition event should delete action.json after both actions")
end

-- ============================================================
-- Cycle 17 — error path: handler fails → error file written,
--            subsequent actions skipped, action.json not deleted
-- ============================================================

do
  local queued = {}
  local error_writes = {}
  local calls = {}
  local action_present = true

  local mock_G = {
    STATE = 2,
    STATES = { SHOP = 2 },
    FUNCS = {
      reroll_shop = function()
        calls[#calls + 1] = "reroll"
        error("reroll failed: out of gold")
      end,
      toggle_shop = function()
        calls[#calls + 1] = "leave"
      end,
    },
  }

  local ex = executor_mod.new_executor({
    file_exists = function() return action_present end,
    read_file = function()
      return {
        actions = {
          { kind = "reroll_shop", target_ids = {}, target_key = nil, order = {} },
          { kind = "leave_shop",  target_ids = {}, target_key = nil, order = {} },
        },
      }
    end,
    write_file = function(path, body)
      error_writes[#error_writes + 1] = { path = path, body = body }
      return true
    end,
    remove_file = function() action_present = false end,
    decode_json = function(t) return t end,
    add_event = function(ev) queued[#queued + 1] = ev end,
    get_G = function() return mock_G end,
  })

  ex:tick()
  flush_events(queued)

  eq(#calls, 1, "only the failing action should execute; subsequent actions skipped")
  eq(calls[1], "reroll", "the failing action should have been attempted")
  eq(#error_writes, 1, "one error file should be written")
  eq(error_writes[1].path, "ai/action_error.json", "error should be written to action_error.json")
  ok(string.find(error_writes[1].body, "reroll_shop") ~= nil,
    "error body should contain the failing action kind")
  ok(action_present, "action.json should NOT be deleted after a handler error")
end

-- ============================================================
-- Cycle 17b — error path: busy flag is cleared after error
--             so a corrected action.json can be processed next tick
-- ============================================================

do
  local queued = {}
  local action_present = true

  local mock_G = {
    STATE = 1,
    STATES = { SELECTING_HAND = 1 },
    hand = { highlighted = {}, cards = {} },
    FUNCS = {
      play_cards_from_highlighted = function()
        error("play failed")
      end,
    },
  }

  local ex = executor_mod.new_executor({
    file_exists = function() return action_present end,
    read_file = function()
      return { actions = { { kind = "play_hand", target_ids = {}, target_key = nil, order = {} } } }
    end,
    write_file = function() return true end,
    remove_file = function() action_present = false end,
    decode_json = function(t) return t end,
    add_event = function(ev) queued[#queued + 1] = ev end,
    get_G = function() return mock_G end,
  })

  ex:tick()
  flush_events(queued)

  -- After flushing, the error path should have cleared busy
  ok(not ex.busy, "busy flag should be cleared after error path")
end

-- ============================================================
-- Cycle 18 — condition event waits for non-actionable state,
--            then fires when state becomes actionable
-- ============================================================

do
  local queued = {}
  local action_present = true
  local current_state = 9  -- HAND_PLAYED: non-actionable

  local mock_G = {
    get_state = function(self) return current_state end,
    STATES = { SELECTING_HAND = 1, HAND_PLAYED = 9 },
  }
  -- Inject a get_G that reads current_state dynamically
  local dynamic_G = setmetatable({}, {
    __index = function(t, k)
      if k == "STATE" then return current_state end
      return mock_G[k]
    end
  })

  local ex = executor_mod.new_executor({
    file_exists = function() return action_present end,
    read_file = function()
      return { actions = { { kind = "reroll_shop", target_ids = {}, target_key = nil, order = {} } } }
    end,
    write_file = function() return true end,
    remove_file = function() action_present = false end,
    decode_json = function(t) return t end,
    add_event = function(ev) queued[#queued + 1] = ev end,
    get_G = function() return dynamic_G end,
  })

  -- Patch reroll_shop into dynamic_G
  dynamic_G.FUNCS = { reroll_shop = function() end }

  ex:tick()

  -- Run events once: action fires, condition sees HAND_PLAYED → stays pending
  for i = 1, #queued do
    if not queued[i]._done then
      local r = queued[i].func(queued[i])
      if r then queued[i]._done = true end
    end
  end

  ok(action_present, "action.json should still exist while state is non-actionable")

  -- Transition to actionable state
  current_state = 1  -- SELECTING_HAND

  flush_events(queued)

  ok(not action_present, "action.json should be deleted once state becomes actionable")
  ok(not ex.busy, "busy flag should be cleared after successful completion")
end

print("test_executor: all tests passed")
