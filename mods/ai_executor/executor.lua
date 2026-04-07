local executor_mod = {}

local load_module = rawget(_G, "__ai_executor_load_module")
if not load_module then
  local mod = rawget(_G, "SMODS") and SMODS.current_mod
  local path = mod and mod.path
  local nfs = rawget(_G, "NFS")
  if path and nfs and type(nfs.read) == "function" then
    local chunk, err = load(
      nfs.read(path .. "shared/loader.lua"),
      '=[SMODS ai_executor "shared/loader.lua"]'
    )
    assert(chunk, err)
    load_module = chunk().load
  else
    load_module = dofile("mods/ai_executor/shared/loader.lua").load
  end
  _G.__ai_executor_load_module = load_module
end

local handlers = load_module("handlers.lua")

local ACTION_FILE = "ai/action.json"
local ERROR_FILE  = "ai/action_error.json"

-- ============================================================
-- new_executor(options) → executor object
--
-- options:
--   file_exists(path)        → bool
--   read_file(path)          → table (already decoded) or nil
--   write_file(path, body)   → bool
--   remove_file(path)
--   decode_json(raw)         → table  (called on the result of read_file)
--   add_event(event_table)
--   get_G()                  → current G
--   dispatch(action, G)      → nil or error string  [optional, defaults to handlers.dispatch]
--   is_actionable(G)         → bool                 [optional, defaults to handlers.is_actionable_state]
-- ============================================================

function executor_mod.new_executor(options)
  options = type(options) == "table" and options or {}

  local ex = {
    file_exists  = options.file_exists,
    read_file    = options.read_file,
    write_file   = options.write_file,
    remove_file  = options.remove_file,
    decode_json  = options.decode_json  or function(t) return t end,
    add_event    = options.add_event,
    get_G        = options.get_G        or function() return rawget(_G, "G") end,
    dispatch     = options.dispatch     or handlers.dispatch,
    is_actionable = options.is_actionable or handlers.is_actionable_state,
    busy         = false,
    failed       = false,
  }

  function ex:_write_error(kind, reason)
    local body = '{"kind":"' .. tostring(kind) .. '","reason":"' .. tostring(reason) .. '"}'
    pcall(self.write_file, ERROR_FILE, body)
  end

  -- Queue all action events plus the final condition event.
  -- Called only when action.json is freshly detected.
  function ex:_queue(actions)
    self.busy   = true
    self.failed = false

    for i = 1, #actions do
      local action = actions[i]
      self.add_event({
        trigger = "immediate",
        func = function(self_event)
          if ex.failed then
            -- A previous handler already failed; skip silently.
            return true
          end
          local err = ex.dispatch(action, ex.get_G())
          if err then
            ex:_write_error(action.kind, err)
            ex.failed = true
          end
          return true
        end,
      })
    end

    -- Condition event: poll G.STATE until actionable, then clean up.
    self.add_event({
      trigger      = "condition",
      blocking     = false,
      blocking_type = "other",
      func = function(self_event)
        if ex.failed then
          -- Error was recorded; do not delete action.json, just clear busy.
          ex.busy = false
          return true
        end
        if not ex.is_actionable(ex.get_G()) then
          return false  -- keep waiting
        end
        pcall(ex.remove_file, ACTION_FILE)
        ex.busy = false
        return true
      end,
    })
  end

  function ex:tick()
    if self.busy then
      return false
    end
    if not self.file_exists(ACTION_FILE) then
      return false
    end

    local raw = self.read_file(ACTION_FILE)
    if raw == nil then
      return false
    end

    local ok_decode, data = pcall(self.decode_json, raw)
    if not ok_decode or type(data) ~= "table" or type(data.actions) ~= "table" then
      self:_write_error("parse_error", "failed to decode action.json")
      return false
    end

    self:_queue(data.actions)
    return true
  end

  return ex
end

return executor_mod
