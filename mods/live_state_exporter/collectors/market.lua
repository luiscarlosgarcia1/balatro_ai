local market = {}

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
local common = load_module("shared/entities/common.lua")(values)
local owned = load_module("shared/entities/owned.lua")(common)
local entity_market = load_module("shared/entities/market.lua")(common, owned)
local as_table = values.as_table
local to_number = values.to_number
local first_boolean = values.first_boolean

local function state_equals(root, name)
  local states = as_table(root and root.STATES) or {}
  local expected = states[name]
  return expected ~= nil and root and root.STATE == expected
end

local function read_pack_skip_available(root, game, pack)
  local direct = first_boolean(
    pack and pack.skip_available,
    pack and pack.can_skip,
    game and game.pack_skip_available
  )
  if direct ~= nil then
    return direct
  end

  local stop_use = to_number(game and game.STOP_USE) or 0
  if not as_table(root and root.pack_cards) or stop_use > 0 then
    return false
  end

  return state_equals(root, "SMODS_BOOSTER_OPENED")
    or state_equals(root, "PLANET_PACK")
    or state_equals(root, "STANDARD_PACK")
    or state_equals(root, "BUFFOON_PACK")
    or as_table(root and root.hand) ~= nil
end

local function append_row_items(target, source)
  source = as_table(source) or {}
  for i = 1, #source do
    local item = entity_market.classify_shop_item(as_table(source[i]))
    if item ~= nil then
      target[#target + 1] = item
    end
  end
end

function market.collect(root, interaction_phase)
  root = as_table(root) or {}
  local game = as_table(root.GAME) or {}

  local out = {
    shop_items = {},
    pack_contents = nil,
  }

  if interaction_phase == "shop" or interaction_phase == "pack_reward" then
    local shop_jokers = as_table(root.shop_jokers)
    local shop_booster = as_table(root.shop_booster)
    local shop_vouchers = as_table(root.shop_vouchers)

    append_row_items(out.shop_items, shop_jokers and shop_jokers.cards)
    append_row_items(out.shop_items, shop_vouchers and shop_vouchers.cards)
    append_row_items(out.shop_items, shop_booster and shop_booster.cards)
  end

  if interaction_phase == "pack_reward" then
    local pack = as_table(root.pack)
    local pack_cards = as_table(root.pack_cards)
    local items = {}
    local skip_available = read_pack_skip_available(root, game, pack)
    local source = as_table(pack_cards and pack_cards.cards) or {}

    for i = 1, #source do
      local item = entity_market.classify_pack_reward_item(as_table(source[i]))
      if item ~= nil then
        items[#items + 1] = item
      end
    end

    out.pack_contents = {
      choices_remaining = to_number(game.pack_choices),
      skip_available = skip_available,
      items = items,
    }
  end

  return out
end

return market
