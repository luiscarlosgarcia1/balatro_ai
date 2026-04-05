local zones = {}

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
local as_table = values.as_table
local first_defined = values.first_defined
local lower_string = values.lower_string

local function read_zone_name(area, fallback)
  local config = as_table(area and area.config) or {}
  local zone = first_defined(config.type, area and area.type, area and area.name, fallback)
  if type(zone) == "string" and zone ~= "" then
    return zone
  end
  return fallback
end

local SUIT_ORDER = {
  spades = 1,
  hearts = 2,
  clubs = 3,
  diamonds = 4,
}

local RANK_ORDER = {
  ace = 1,
  ["2"] = 2,
  ["3"] = 3,
  ["4"] = 4,
  ["5"] = 5,
  ["6"] = 6,
  ["7"] = 7,
  ["8"] = 8,
  ["9"] = 9,
  ["10"] = 10,
  jack = 11,
  queen = 12,
  king = 13,
}

local function read_suit_order(card)
  local base = as_table(card and card.base) or {}
  local suit = lower_string(first_defined(base.suit, base.suit_name, card and card.suit))
  return SUIT_ORDER[suit] or math.huge
end

local function read_rank_order(card)
  local base = as_table(card and card.base) or {}
  local value = first_defined(base.value, base.rank, card and card.rank)
  if type(value) == "number" then
    return RANK_ORDER[tostring(value)] or math.huge
  end
  local token = lower_string(value)
  return RANK_ORDER[token] or math.huge
end

local function collect_playing_cards(area)
  local source = as_table(area and area.cards) or {}
  local cards = {}
  local selected = {}
  local zone = read_zone_name(area, "hand")

  for i = 1, #source do
    local raw = as_table(source[i])
    local item = owned.read_playing_card(raw)
    if item ~= nil then
      cards[#cards + 1] = item

      local reference = common.read_selected_reference(raw, zone, item.card_key)
      if reference ~= nil then
        selected[#selected + 1] = reference
      end
    end
  end

  return cards, selected
end

local function collect_deck_cards(root)
  local game = as_table(root and root.GAME) or {}
  local deck = as_table(game.deck) or as_table(root and root.deck)
  local source = as_table(game.playing_cards)
    or as_table(deck and deck.cards)
    or {}
  local deck_cards = {}

  for i = 1, #source do
    local raw = as_table(source[i])
    local item = owned.read_playing_card(raw)
    if item ~= nil then
      item.__sort_suit = read_suit_order(raw)
      item.__sort_rank = read_rank_order(raw)
      deck_cards[#deck_cards + 1] = item
    end
  end

  table.sort(deck_cards, function(left, right)
    if left.__sort_suit ~= right.__sort_suit then
      return left.__sort_suit < right.__sort_suit
    end
    if left.__sort_rank ~= right.__sort_rank then
      return left.__sort_rank < right.__sort_rank
    end
    return left.instance_id < right.instance_id
  end)

  for i = 1, #deck_cards do
    deck_cards[i].__sort_suit = nil
    deck_cards[i].__sort_rank = nil
  end

  return deck_cards
end

local function collect_jokers(area)
  local source = as_table(area and area.cards) or {}
  local jokers = {}
  local selected = {}
  local zone = read_zone_name(area, "jokers")

  for i = 1, #source do
    local raw = as_table(source[i])
    local item = owned.read_joker(raw)
    if item ~= nil then
      jokers[#jokers + 1] = item

      local reference = common.read_selected_reference(raw, zone, item.key)
      if reference ~= nil then
        selected[#selected + 1] = reference
      end
    end
  end

  return jokers, selected
end

local function collect_consumables(area)
  local source = as_table(area and area.cards) or {}
  local consumables = {}
  local selected = {}
  local zone = read_zone_name(area, "consumeables")

  for i = 1, #source do
    local raw = as_table(source[i])
    local item = owned.read_consumable(raw)
    if item ~= nil then
      consumables[#consumables + 1] = item

      local reference = common.read_selected_reference(raw, zone, item.key)
      if reference ~= nil then
        selected[#selected + 1] = reference
      end
    end
  end

  return consumables, selected
end

local function append_all(target, values)
  for i = 1, #values do
    target[#target + 1] = values[i]
  end
end

function zones.collect(root)
  root = as_table(root) or {}
  local cards_in_hand, selected_cards = collect_playing_cards(root.hand)
  local jokers, selected_jokers = collect_jokers(root.jokers)
  local consumable_area = as_table(root.consumables) or as_table(root.consumeables)
  local consumables, selected_consumables = collect_consumables(consumable_area)
  local cards_in_deck = collect_deck_cards(root)
  append_all(selected_cards, selected_jokers)
  append_all(selected_cards, selected_consumables)

  return {
    cards_in_hand = cards_in_hand,
    selected_cards = selected_cards,
    jokers = jokers,
    consumables = consumables,
    cards_in_deck = cards_in_deck,
  }
end

return zones
