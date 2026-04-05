local core = {}

local RUN_INFO_HAND_ORDER = {
  "Flush Five",
  "Flush House",
  "Five of a Kind",
  "Straight Flush",
  "Four of a Kind",
  "Full House",
  "Flush",
  "Straight",
  "Three of a Kind",
  "Two Pair",
  "Pair",
  "High Card",
}

local BLIND_ROW_ORDER = { "small", "big", "boss" }

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

local function lower_string(value)
  return type(value) == "string" and string.lower(value) or nil
end

local function table_lookup(source, wanted_key)
  if type(source) ~= "table" then
    return nil
  end
  local direct = source[wanted_key]
  if direct ~= nil then
    return direct
  end
  for key, value in pairs(source) do
    if lower_string(key) == wanted_key then
      return value
    end
  end
  return nil
end

local function collect_blinds(game)
  local resets = as_table(game and game.round_resets) or {}
  local blind_choices = as_table(resets.blind_choices) or {}
  local blind_states = as_table(resets.blind_states) or {}
  local blind_tags = as_table(resets.blind_tags) or {}
  local blinds = {}

  for i = 1, #BLIND_ROW_ORDER do
    local row = BLIND_ROW_ORDER[i]
    local key = table_lookup(blind_choices, row)
    local state = table_lookup(blind_states, row)
    local tag_key = table_lookup(blind_tags, row)
    if key ~= nil or state ~= nil or tag_key ~= nil then
      blinds[#blinds + 1] = {
        key = key,
        state = state,
        tag_key = tag_key,
      }
    end
  end

  return blinds
end

local function collect_run_info(game)
  local hands = as_table(game and game.hands)
  if not hands then
    return nil
  end

  local ordered_hands = {}
  local count = 0
  for i = 1, #RUN_INFO_HAND_ORDER do
    local hand_name = RUN_INFO_HAND_ORDER[i]
    local hand = as_table(hands[hand_name])
    if hand then
      ordered_hands[hand_name] = {
        level = to_number(hand.level) or 0,
        chips = to_number(hand.chips) or 0,
        mult = to_number(hand.mult) or 0,
        played = to_number(hand.played) or 0,
        played_this_round = to_number(hand.played_this_round) or 0,
      }
      count = count + 1
    end
  end

  if count == 0 then
    return nil
  end

  return {
    hands = ordered_hands,
  }
end

local function collect_interest(game)
  local modifiers = as_table(game and game.modifiers) or {}
  local amount = to_number(game and game.interest_amount)
  local cap = to_number(game and game.interest_cap)
  local no_interest = modifiers.no_interest

  if amount == nil and cap == nil and no_interest == nil then
    return nil
  end

  return {
    amount = amount or 0,
    cap = cap or 0,
    no_interest = no_interest == true,
  }
end

local function collect_slot_limit(area, fallback_value)
  local config = as_table(area and area.config) or {}
  return to_number(first_defined(config.card_limit, area and area.temp_limit, config.temp_limit, fallback_value))
end

local function append_voucher(vouchers, key, value)
  if type(key) ~= "string" or key == "" then
    return
  end
  local cost = 0
  if type(value) == "number" then
    cost = value
  elseif type(value) == "table" then
    cost = to_number(first_defined(value.cost, value.price)) or 0
  end
  vouchers[#vouchers + 1] = {
    key = key,
    cost = cost,
  }
end

local function collect_vouchers(game)
  local source = as_table(game and game.used_vouchers)
  if not source then
    return {}
  end

  local vouchers = {}
  for key, value in pairs(source) do
    if type(key) == "number" then
      local item = as_table(value)
      local item_key = first_defined(item and item.key, item and item.voucher_key)
      append_voucher(vouchers, item_key, item)
    else
      append_voucher(vouchers, key, value)
    end
  end

  table.sort(vouchers, function(left, right)
    return left.key < right.key
  end)

  return vouchers
end

local function collect_tags(root, game)
  local source = as_table(root and root.tags)
  if not source then
    source = as_table(game and game.tags)
  end
  if not source then
    return {}
  end

  local tags = {}
  for i = 1, #source do
    local item = source[i]
    local key = nil
    if type(item) == "string" then
      key = item
    else
      local item_table = as_table(item)
      key = item_table and first_defined(item_table.key, item_table.tag_key)
    end
    if type(key) == "string" and key ~= "" then
      tags[#tags + 1] = { key = key }
    end
  end
  return tags
end

function core.collect(root, interaction_phase)
  root = as_table(root) or {}
  local game = as_table(root.GAME) or {}
  local starting = as_table(game.starting_params) or {}
  local consumables = as_table(root.consumables) or as_table(root.consumeables)

  return {
    blinds = collect_blinds(game),
    run_info = collect_run_info(game),
    interest = collect_interest(game),
    joker_slots = collect_slot_limit(root.jokers, starting.joker_slots),
    consumable_slots = collect_slot_limit(consumables, starting.consumable_slots),
    hand_size = collect_slot_limit(root.hand, starting.hand_size),
    vouchers = collect_vouchers(game),
    tags = collect_tags(root, game),
    interaction_phase = interaction_phase,
  }
end

return core
