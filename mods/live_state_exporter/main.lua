--- STEAMODDED HEADER
--- MOD_ID: live_state_exporter
--- MOD_NAME: Live State Exporter
--- MOD_AUTHOR: [luisgarcia]
--- MOD_DESCRIPTION: Writes canonical live Balatro state to ai/live_state.json.
--- PREFIX: live_state_exporter
--- VERSION: 1.0.0

local unpack_fn = table.unpack or unpack

local load_module = rawget(_G, "__live_state_exporter_load_module")
if not load_module then
  local mod = rawget(_G, "SMODS") and SMODS.current_mod
  local path = mod and mod.path
  local nfs = rawget(_G, "NFS")
  if path and nfs and type(nfs.read) == "function" then
    local chunk, err = load(
      nfs.read(path .. "shared/loader.lua"),
      '=[SMODS live_state_exporter "shared/loader.lua"]'
    )
    assert(chunk, err)
    load_module = chunk().load
  else
    load_module = dofile("mods/live_state_exporter/shared/loader.lua").load
  end
  _G.__live_state_exporter_load_module = load_module
end

local raw = load_module("state/raw.lua")
local schema = load_module("state/schema.lua")
local out = load_module("out.lua")
local probe = load_module("probe.lua")

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
    return raw.read_state(rawget(_G, "G"))
  end,
  build_shell = schema.build_shell,
  make_signature = out.make_signature,
  encode_json = out.encode_json,
  write_snapshot = out.write_snapshot,
})

local function safe_tick()
  local ok_export = pcall(function()
    exporter:tick()
  end)
  local ok_probe = pcall(function()
    probe.tick(rawget(_G, "G"))
  end)
  return ok_export and ok_probe
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
