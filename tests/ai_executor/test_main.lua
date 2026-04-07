-- Smoke test: main.lua installs the love.update hook and the executor's
-- tick() is called on each update when action.json is present.

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

local old = {
  love  = rawget(_G, "love"),
  Game  = rawget(_G, "Game"),
  G     = rawget(_G, "G"),
  SMODS = rawget(_G, "SMODS"),
  NFS   = rawget(_G, "NFS"),
  json  = rawget(_G, "json"),
  __ai_executor_load_module = rawget(_G, "__ai_executor_load_module"),
}

-- Reset the module cache so each dofile("main.lua") starts fresh.
_G.__ai_executor_load_module = nil
_G.SMODS = nil
_G.NFS   = nil
_G.Game  = nil

-- ============================================================
-- Minimal mock environment
-- ============================================================

local action_file = nil   -- nil = absent, string = present
local written = {}
local deleted = {}
local events  = {}

_G.json = {
  decode = function(text)
    -- Simple enough for test: we set action_file to a real table in read mock.
    -- But the executor calls decode_json on what read_file returns, which is
    -- already a table in the real integration path.  For this smoke test we
    -- just need the executor to be instantiated correctly; the detailed
    -- behaviour is covered by test_executor.lua.
    return text
  end,
}

_G.G = {
  STATE  = 1,
  STATES = {
    SELECTING_HAND = 1,
    SHOP           = 2,
  },
  hand   = { highlighted = {}, cards = { { ID = 1, highlighted = false } } },
  FUNCS  = { play_cards_from_highlighted = function() end },
  E_MANAGER = {
    add_event = function(self, ev) events[#events + 1] = ev end,
  },
}

_G.love = {
  timer = { getTime = function() return 0 end },
  filesystem = {
    createDirectory = function() return true end,
    getInfo = function(path)
      if path == "ai/action.json" and action_file ~= nil then
        return { type = "file" }
      end
      return nil
    end,
    read = function(path)
      if path == "ai/action.json" then
        -- Return a pre-decoded table so decode_json (identity) works cleanly.
        return {
          actions = {
            { kind = "play_hand", target_ids = { 1 }, target_key = nil, order = {} },
          },
        }
      end
      return nil
    end,
    write = function(path, body)
      written[path] = body
      return true
    end,
    remove = function(path)
      deleted[#deleted + 1] = path
      if path == "ai/action.json" then action_file = nil end
      return true
    end,
  },
  update = function() return "original" end,
}

dofile("mods/ai_executor/main.lua")

-- ============================================================
-- Test: love.update is wrapped
-- ============================================================

ok(
  type(_G.love.update) == "function",
  "main.lua should preserve love.update as a function"
)

local ret = _G.love.update()
eq(ret, "original", "wrapped love.update should return the original return value")

-- ============================================================
-- Test: no events queued on first tick when action.json absent
-- ============================================================

eq(#events, 0, "no events should be queued when action.json is absent")

-- ============================================================
-- Test: events queued when action.json appears
-- ============================================================

action_file = "present"  -- make getInfo return non-nil
_G.love.update()

ok(#events >= 2, "at least one action event and one condition event should be queued")

-- ============================================================
-- Test: mod survives a tick error without crashing the game loop
-- ============================================================

_G.__ai_executor_load_module = nil  -- reset for a fresh load

local broken_events = {}
local bad_G = {
  E_MANAGER = {
    add_event = function(self, ev) broken_events[#broken_events + 1] = ev end,
  },
}

_G.G = bad_G
_G.love.update = function() return "ok" end

-- Load a second time with a mock that makes executor tick error
_G.SMODS = {
  current_mod = { path = "virtual_main/" },
}
_G.NFS = {
  read = function(path)
    if path == "virtual_main/shared/loader.lua" then
      return [[
        return { load = function(name)
          if name == "executor.lua" then
            return { new_executor = function() return { tick = function() error("boom from tick") end, busy = false } end }
          end
          if name == "handlers.lua" then
            return { dispatch = function() end, is_actionable_state = function() return true end, ACTIONABLE_STATE_NAMES = {} }
          end
          error("unexpected: " .. tostring(name))
        end }
      ]]
    end
    error("unexpected path: " .. tostring(path))
  end,
}

local boot_ok, boot_err = pcall(function()
  dofile("mods/ai_executor/main.lua")
end)

ok(boot_ok, "main.lua should load even when executor module errors: " .. tostring(boot_err))

local update_ok, update_result = pcall(function()
  return _G.love.update()
end)

ok(update_ok, "love.update should not bubble tick errors to the game loop")
eq(update_result, "ok", "love.update should still return original return value on tick error")

-- ============================================================
-- Restore globals
-- ============================================================

_G.love  = old.love
_G.Game  = old.Game
_G.G     = old.G
_G.SMODS = old.SMODS
_G.NFS   = old.NFS
_G.json  = old.json
_G.__ai_executor_load_module = old.__ai_executor_load_module

print("test_main: all tests passed")
