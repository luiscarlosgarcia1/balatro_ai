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
  return game and game.pack_choices ~= nil
    or type(root and root.pack_cards) == "table"
    or type(root and root.pack) == "table"
end

local function has_shop_state(root, game)
  local round = as_table(game and game.current_round) or {}
  return round.reroll_cost ~= nil
    or type(root and root.shop) == "table"
    or type(root and root.shop_jokers) == "table"
    or type(root and root.shop_vouchers) == "table"
end

local function has_play_state(game)
  local round = as_table(game and game.current_round) or {}
  local hands_left = to_number(first_defined(round.hands_left, game and game.hands_left, game and game.hands))
  return hands_left ~= nil and hands_left > 0
end

local function is_selectable_state(state)
  local normalized = lower_string(state)
  if normalized == nil or normalized == "" then
    return true
  end
  return normalized ~= "defeated"
    and normalized ~= "skipped"
    and normalized ~= "selected"
    and normalized ~= "current"
    and normalized ~= "cleared"
end

local function read_active_blind_key(game)
  local blind = as_table(game and game.blind)
  return first_defined(blind and blind.key, blind and blind.config_blind and blind.config_blind.key)
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

function phase.derive_blind_key(root, interaction_phase, blinds)
  root = as_table(root) or {}
  local game = as_table(root.GAME) or {}

  if interaction_phase == "blind_select" and type(blinds) == "table" then
    for i = 1, #blinds do
      local blind = as_table(blinds[i])
      if blind and blind.key and is_selectable_state(blind.state) then
        return blind.key
      end
    end
    if #blinds > 0 then
      local first_blind = as_table(blinds[1])
      return first_blind and first_blind.key or nil
    end
  end

  return read_active_blind_key(game)
end

return phase
