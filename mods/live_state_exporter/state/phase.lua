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
local first_defined = values.first_defined
local to_number = values.to_number
local lower_string = values.lower_string

local function read_state_token(root, game)
  return lower_string(first_defined(root and root.STATE, game and game.state, game and game.current_round_state))
end

local function has_blind_rows(game)
  local resets = as_table(game and game.round_resets) or {}
  return type(resets.blind_choices) == "table"
    or type(resets.blind_states) == "table"
    or type(resets.blind_tags) == "table"
end

local function has_pack_state(root, game)
  return type(root and root.pack_cards) == "table"
    or type(root and root.pack) == "table"
end

local function has_shop_state(root, game)
  local round = as_table(game and game.current_round) or {}
  return round.reroll_cost ~= nil
    or type(root and root.shop_jokers) == "table"
    or type(root and root.shop_vouchers) == "table"
    or type(root and root.shop_booster) == "table"
end

local function has_play_state(game)
  local round = as_table(game and game.current_round) or {}
  local hands_left = to_number(first_defined(round.hands_left, game and game.hands_left, game and game.hands))
  return hands_left ~= nil and hands_left > 0
end

function phase.infer(root)
  root = as_table(root) or {}
  local game = as_table(root.GAME) or {}
  local token = read_state_token(root, game)

  if token then
    if token:find("pack", 1, true) or token:find("booster", 1, true) then
      return "pack_reward"
    end
    if token:find("shop", 1, true) then
      return "shop"
    end
    if token:find("blind", 1, true) then
      return "blind_select"
    end
    if token:find("play", 1, true) or token:find("hand", 1, true) then
      return "play_hand"
    end
  end

  if has_pack_state(root, game) then
    return "pack_reward"
  end
  if has_shop_state(root, game) then
    return "shop"
  end
  if has_blind_rows(game) then
    return "blind_select"
  end
  if has_play_state(game) then
    return "play_hand"
  end
  return "play_hand"
end

return phase
