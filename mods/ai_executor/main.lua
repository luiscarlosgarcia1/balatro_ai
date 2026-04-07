--- STEAMODDED HEADER
--- MOD_ID: ai_executor
--- MOD_NAME: AI Executor
--- MOD_AUTHOR: [luisgarcia]
--- MOD_DESCRIPTION: Reads ai/action.json and executes the declared action queue in-game.
--- PREFIX: ai_executor
--- VERSION: 1.0.0

local unpack_fn = table.unpack or unpack

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

local executor_mod = load_module("executor.lua")

-- ============================================================
-- File-I/O helpers (thin wrappers around love.filesystem)
-- ============================================================

local ACTION_FILE = "ai/action.json"

local function fs()
  local love = rawget(_G, "love")
  return love and love.filesystem
end

local function file_exists(path)
  local filesystem = fs()
  if not filesystem or type(filesystem.getInfo) ~= "function" then
    return false
  end
  local info = filesystem.getInfo(path)
  return info ~= nil
end

local function read_file(path)
  local filesystem = fs()
  if not filesystem or type(filesystem.read) ~= "function" then
    return nil
  end
  local ok, result = pcall(filesystem.read, path)
  if not ok then return nil end
  return result
end

local function write_file(path, body)
  local filesystem = fs()
  if not filesystem or type(filesystem.write) ~= "function" then
    return false
  end
  local dir = path:match("^(.+)/[^/]+$")
  if dir and type(filesystem.createDirectory) == "function" then
    pcall(filesystem.createDirectory, dir)
  end
  local ok = pcall(filesystem.write, path, body)
  return ok
end

local function remove_file(path)
  local filesystem = fs()
  if not filesystem or type(filesystem.remove) ~= "function" then
    return
  end
  pcall(filesystem.remove, path)
end

-- ============================================================
-- JSON decoder: uses the game's built-in json.decode
-- ============================================================

local function decode_json(raw)
  -- raw may already be a pre-decoded table (injected in tests); pass it through.
  if type(raw) == "table" then
    return raw
  end
  local decoder = rawget(_G, "json")
  if type(decoder) == "table" and type(decoder.decode) == "function" then
    return decoder.decode(raw)
  end
  error("ai_executor: no JSON decoder available")
end

-- ============================================================
-- Event helpers
-- ============================================================

local function add_event(event_table)
  local G = rawget(_G, "G")
  if not G then return end
  local mgr = G.E_MANAGER
  if type(mgr) ~= "table" or type(mgr.add_event) ~= "function" then
    return
  end
  -- Wrap the plain table in a Balatro Event object when available.
  local event_obj = event_table
  local Event = rawget(_G, "Event")
  if type(Event) == "function" then
    event_obj = Event(event_table)
  end
  mgr:add_event(event_obj)
end

-- ============================================================
-- Build and wire the executor
-- ============================================================

local executor = executor_mod.new_executor({
  file_exists  = file_exists,
  read_file    = read_file,
  write_file   = write_file,
  remove_file  = remove_file,
  decode_json  = decode_json,
  add_event    = add_event,
  get_G        = function() return rawget(_G, "G") end,
})

-- ============================================================
-- Hook installation (same pattern as live_state_exporter)
-- ============================================================

local function safe_tick()
  pcall(function() executor:tick() end)
end

local function wrap_update(obj, key)
  if type(obj) ~= "table" or type(obj[key]) ~= "function" then
    return false
  end

  local tag = "__ae_wrap_" .. key
  if obj[tag] then
    return false
  end

  local old = obj[key]
  obj[tag] = true
  obj[key] = function(...)
    local results = { old(...) }
    safe_tick()
    return unpack_fn(results)
  end
  return true
end

local function install_hooks()
  if not wrap_update(rawget(_G, "love"), "update") then
    wrap_update(rawget(_G, "Game"), "update")
  end
end

install_hooks()
