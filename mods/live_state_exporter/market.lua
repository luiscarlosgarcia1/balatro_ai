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
local as_table = values.as_table
local first_defined = values.first_defined
local to_number = values.to_number
local first_boolean = values.first_boolean

local function normalize_card_key(card)
  local config = as_table(card and card.config) or {}
  local key = first_defined(config.card_key, config.key)
  if type(key) == "string" and key ~= "" then
    return key
  end
  return nil
end

local function normalize_center_key(card)
  local config = as_table(card and card.config) or {}
  local key = first_defined(config.center_key, config.key)
  if type(key) == "string" and key ~= "" then
    return key
  end
  return nil
end

local function read_card_enhancement(card)
  local config = as_table(card and card.config) or {}
  local key = config.center_key
  if type(key) == "string" and key ~= "" and key ~= "c_base" then
    return key
  end
  return nil
end

local function read_edition(card)
  local edition = as_table(card and card.edition) or {}
  if type(edition.type) == "string" and edition.type ~= "" then
    return edition.type
  end
  return nil
end

local function read_instance_id(card)
  return to_number(first_defined(card and card.instance_id, card and card.id, card and card.ID))
end

local function wrap_item(kind, value)
  return {
    card = kind == "card" and value or nil,
    joker = kind == "joker" and value or nil,
    consumable = kind == "consumable" and value or nil,
    voucher = kind == "voucher" and value or nil,
    pack = kind == "pack" and value or nil,
  }
end

local function collect_card_item(raw)
  local instance_id = read_instance_id(raw)
  local card_key = normalize_card_key(raw)
  if instance_id == nil or card_key == nil then
    return nil
  end
  return {
    card_key = card_key,
    instance_id = instance_id,
    enhancement = read_card_enhancement(raw),
    edition = read_edition(raw),
    seal = raw.seal,
    facing = raw.facing,
    debuffed = raw.debuff == true,
    cost = to_number(raw.cost),
    sell_cost = to_number(first_defined(raw.sell_cost, raw.sell_price)),
  }
end

local function collect_joker_item(raw, key)
  local instance_id = read_instance_id(raw)
  if instance_id == nil or key == nil then
    return nil
  end
  local ability = as_table(raw.ability) or {}
  return {
    key = key,
    instance_id = instance_id,
    eternal = ability.eternal == true,
    perishable = ability.perishable == true,
    rental = ability.rental == true,
    perish_tally = to_number(ability.perish_tally),
    edition = read_edition(raw),
    debuffed = raw.debuff == true,
    sell_cost = to_number(first_defined(raw.sell_cost, raw.sell_price)),
  }
end

local function collect_consumable_item(raw, key)
  local instance_id = read_instance_id(raw)
  if instance_id == nil or key == nil then
    return nil
  end
  return {
    key = key,
    instance_id = instance_id,
    edition = read_edition(raw),
    cost = to_number(raw.cost),
    sell_cost = to_number(first_defined(raw.sell_cost, raw.sell_price)),
  }
end

local function collect_pack_item(raw, key)
  local instance_id = read_instance_id(raw)
  if instance_id == nil or key == nil then
    return nil
  end
  return {
    key = key,
    instance_id = instance_id,
    cost = to_number(raw.cost),
  }
end

local function collect_voucher_item(raw, key)
  if key == nil then
    return nil
  end
  return {
    key = key,
    cost = to_number(first_defined(raw and raw.cost, raw and raw.price)) or 0,
  }
end

local function collect_pack_reward_item(raw)
  local card_key = normalize_card_key(raw)
  if card_key ~= nil then
    return collect_card_item(raw)
  end

  local center_key = normalize_center_key(raw)
  if type(center_key) ~= "string" then
    return nil
  end

  local prefix = center_key:sub(1, 2)
  if prefix == "j_" then
    return collect_joker_item(raw, center_key)
  end
  if prefix == "c_" then
    return collect_consumable_item(raw, center_key)
  end
  return nil
end

local function append_row_items(target, source)
  source = as_table(source) or {}
  for i = 1, #source do
    local raw = as_table(source[i])
    local card_key = normalize_card_key(raw)
    local center_key = normalize_center_key(raw)
    local item = nil
    if card_key ~= nil then
      item = collect_card_item(raw)
      if item ~= nil then
        target[#target + 1] = wrap_item("card", item)
      end
    elseif type(center_key) == "string" then
      local prefix = center_key:sub(1, 2)
      if prefix == "j_" then
        item = collect_joker_item(raw, center_key)
        if item ~= nil then
          target[#target + 1] = wrap_item("joker", item)
        end
      elseif prefix == "c_" then
        item = collect_consumable_item(raw, center_key)
        if item ~= nil then
          target[#target + 1] = wrap_item("consumable", item)
        end
      elseif prefix == "p_" then
        item = collect_pack_item(raw, center_key)
        if item ~= nil then
          target[#target + 1] = wrap_item("pack", item)
        end
      elseif prefix == "v_" then
        item = collect_voucher_item(raw, center_key)
        if item ~= nil then
          target[#target + 1] = wrap_item("voucher", item)
        end
      end
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
    local pack_key = normalize_center_key(pack)
    local pack_id = read_instance_id(pack)
    local pack_cards = as_table(root.pack_cards)
    local items = {}
    local source = as_table(pack_cards and pack_cards.cards) or {}

    for i = 1, #source do
      local item = collect_pack_reward_item(as_table(source[i]))
      if item ~= nil then
        items[#items + 1] = item
      end
    end

    out.pack_contents = {
      pack = (pack_key ~= nil and pack_id ~= nil) and {
        key = pack_key,
        instance_id = pack_id,
        cost = to_number(pack and pack.cost),
      } or nil,
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
