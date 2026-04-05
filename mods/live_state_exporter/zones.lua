local zones = {}

local function as_table(value)
  return type(value) == "table" and value or nil
end

local function first_defined(...)
  for i = 1, select("#", ...) do
    local value = select(i, ...)
    if value ~= nil then
      return value
    end
  end
  return nil
end

local function to_number(value)
  if type(value) == "number" then
    return value
  end
  if type(value) == "string" and value:match("^%-?%d+$") then
    return tonumber(value)
  end
  return nil
end

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

local function is_selected(card)
  return card and (card.highlighted == true or card.selected == true) or false
end

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

local function lower_string(value)
  return type(value) == "string" and string.lower(value) or nil
end

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
    local instance_id = read_instance_id(raw)
    local card_key = normalize_card_key(raw)
    if instance_id ~= nil and card_key ~= nil then
      cards[#cards + 1] = {
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

      if is_selected(raw) then
        selected[#selected + 1] = {
          zone = zone,
          instance_id = instance_id,
          key = card_key,
        }
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
    local instance_id = read_instance_id(raw)
    local card_key = normalize_card_key(raw)
    if instance_id ~= nil and card_key ~= nil then
      deck_cards[#deck_cards + 1] = {
        card_key = card_key,
        instance_id = instance_id,
        enhancement = read_card_enhancement(raw),
        edition = read_edition(raw),
        seal = raw.seal,
        facing = raw.facing,
        debuffed = raw.debuff == true,
        cost = to_number(raw.cost),
        sell_cost = to_number(first_defined(raw.sell_cost, raw.sell_price)),
        __sort_suit = read_suit_order(raw),
        __sort_rank = read_rank_order(raw),
      }
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
    local instance_id = read_instance_id(raw)
    local key = normalize_center_key(raw)
    if instance_id ~= nil and key ~= nil then
      local ability = as_table(raw.ability) or {}
      jokers[#jokers + 1] = {
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

      if is_selected(raw) then
        selected[#selected + 1] = {
          zone = zone,
          instance_id = instance_id,
          key = key,
        }
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
    local instance_id = read_instance_id(raw)
    local key = normalize_center_key(raw)
    if instance_id ~= nil and key ~= nil then
      consumables[#consumables + 1] = {
        key = key,
        instance_id = instance_id,
        edition = read_edition(raw),
        cost = to_number(raw.cost),
        sell_cost = to_number(first_defined(raw.sell_cost, raw.sell_price)),
      }

      if is_selected(raw) then
        selected[#selected + 1] = {
          zone = zone,
          instance_id = instance_id,
          key = key,
        }
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
