local market = {}

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

local values = load_module("shared/values.lua")
local common = load_module("shared/entities/common.lua")(values)
local owned = load_module("shared/entities/owned.lua")(common)
local entity_market = load_module("shared/entities/market.lua")(common, owned)
local as_table = values.as_table
local to_number = values.to_number
local first_boolean = values.first_boolean

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

  if interaction_phase == "shop" then
    local shop = as_table(root.shop)
    local shop_jokers = as_table(root.shop_jokers)
    local shop_vouchers = as_table(root.shop_vouchers)
    local main_cards = (shop and shop.cards) or (shop_jokers and shop_jokers.cards)

    append_row_items(out.shop_items, main_cards)
    append_row_items(out.shop_items, shop_vouchers and shop_vouchers.cards)
    return out
  end

  if interaction_phase == "pack_reward" then
    local pack = as_table(root.pack)
    local pack_item = entity_market.read_pack(pack)
    local pack_cards = as_table(root.pack_cards)
    local items = {}
    local source = as_table(pack_cards and pack_cards.cards) or {}

    for i = 1, #source do
      local item = entity_market.classify_pack_reward_item(as_table(source[i]))
      if item ~= nil then
        items[#items + 1] = item
      end
    end

    out.pack_contents = {
      pack = pack_item,
      choices_remaining = to_number(game.pack_choices),
      skip_available = first_boolean(
        pack and pack.skip_available,
        pack and pack.can_skip,
        game.pack_skip_available,
        game.can_skip_booster
      ) == true,
      items = items,
    }
  end

  return out
end

return market
