local phase = {}

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

function phase.infer(root)
  root = as_table(root) or {}
  local state = root.STATE
  local states = as_table(root.STATES) or {}

  if state == nil then return "play_hand" end

  if state == states.SELECTING_HAND then return "play_hand" end
  if state == states.SHOP then return "shop" end
  if state == states.BLIND_SELECT then return "blind_select" end
  if state == states.ROUND_EVAL then return "cash_out" end
  if state == states.TAROT_PACK
    or state == states.PLANET_PACK
    or state == states.SPECTRAL_PACK
    or state == states.BUFFOON_PACK
    or state == states.STANDARD_PACK then
    return "pack_reward"
  end

  return "play_hand"
end

return phase
