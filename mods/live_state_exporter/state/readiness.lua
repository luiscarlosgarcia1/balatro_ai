local readiness = {}

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

local values = load_module("shared/values.lua")
local as_table = values.as_table
local to_number = values.to_number

function readiness.is_ready(root)
  local game_root = as_table(root)
  if not game_root then
    return false
  end

  local controller = as_table(game_root.CONTROLLER)
  local game = as_table(game_root.GAME)
  if not controller or not game then
    return false
  end

  local interrupt = as_table(controller.interrupt)
  local stop_use = to_number(game.STOP_USE) or 0

  if controller.locked == true then
    return false
  end
  if interrupt and interrupt.focus then
    return false
  end
  if stop_use ~= 0 then
    return false
  end

  return true
end

return readiness
