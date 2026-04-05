--- STEAMODDED HEADER
--- MOD_ID: live_state_exporter
--- MOD_NAME: Live State Exporter
--- MOD_AUTHOR: [luisgarcia]
--- MOD_DESCRIPTION: Writes canonical live Balatro state to ai/live_state.json.
--- PREFIX: live_state_exporter
--- VERSION: 1.0.0

local unpack_fn = table.unpack or unpack

local function load_module(name)
  local mod = rawget(_G, "SMODS") and SMODS.current_mod
  local path = mod and mod.path
  local nfs = rawget(_G, "NFS")
  if path and nfs and type(nfs.read) == "function" then
    local chunk, err = load(
      nfs.read(path .. name),
      '=[SMODS live_state_exporter "' .. name .. '"]'
    )
    assert(chunk, err)
    return chunk()
  end
  return dofile("mods/live_state_exporter/" .. name)
end

local snap = load_module("snap.lua")
local out = load_module("out.lua")

local function current_time()
  local love = rawget(_G, "love")
  local timer = love and love.timer
  if type(timer) == "table" and type(timer.getTime) == "function" then
    return timer.getTime()
  end
  return os.clock()
end

local exporter = out.new_exporter({
  dt = 0.05,
  now = current_time,
  read_state = function()
    return snap.read_state(rawget(_G, "G"))
  end,
  build_shell = snap.build_shell,
  make_signature = out.make_signature,
  encode_json = out.encode_json,
  write_snapshot = out.write_snapshot,
})

local function safe_tick()
  local ok = pcall(function()
    exporter:tick()
  end)
  return ok
end

local function wrap_update(obj, key)
  if type(obj) ~= "table" or type(obj[key]) ~= "function" then
    return false
  end

  local tag = "__ls_wrap_" .. key
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
  safe_tick()
end

install_hooks()
