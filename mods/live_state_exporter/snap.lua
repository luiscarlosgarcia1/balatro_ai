local snap = {}

local array_meta = { __ls_arr = true }
local null_value = setmetatable({}, { __ls_null = true })

local function as_table(value)
  return type(value) == "table" and value or nil
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

local function first_defined(...)
  for i = 1, select("#", ...) do
    local value = select(i, ...)
    if value ~= nil then
      return value
    end
  end
  return nil
end

local function clone_array(source)
  local out = {}
  if type(source) == "table" then
    for i = 1, #source do
      out[i] = source[i]
    end
  end
  return setmetatable(out, array_meta)
end

local function required_or(value, default)
  if value == nil then
    return default
  end
  return value
end

local function optional_or_null(value)
  if value == nil then
    return null_value
  end
  return value
end

local function read_deck_key(game)
  local selected_back = as_table(game and game.selected_back)
  return first_defined(game and game.selected_back_key, selected_back and selected_back.key)
end

function snap.read_state(root)
  root = as_table(root) or {}

  local game = as_table(root.GAME) or {}
  local round = as_table(game.current_round) or {}
  local resets = as_table(game.round_resets) or {}
  local blind = as_table(game.blind) or {}

  return {
    state_id = to_number(first_defined(root.STATE, game.state, game.current_round_state)),
    dollars = to_number(first_defined(game.dollars, game.money)),
    hands_left = to_number(first_defined(round.hands_left, resets.hands, game.hands_left, game.hands)),
    discards_left = to_number(first_defined(round.discards_left, resets.discards, game.discards_left, game.discards)),
    score = {
      current = to_number(first_defined(game.chips, game.current_round_score, game.score)),
      target = to_number(first_defined(blind.chips, game.score_to_beat, game.target_score)),
    },
    deck_key = read_deck_key(game),
    stake_id = first_defined(game.stake_id, game.stake),
    blind_key = nil,
    ante = to_number(resets.ante),
    round = to_number(game.round),
    reroll_cost = to_number(round.reroll_cost),
  }
end

function snap.build_shell(source)
  source = as_table(source) or {}
  local score = as_table(source.score) or {}

  return {
    state_id = required_or(source.state_id, 0),
    dollars = required_or(source.dollars, 0),
    hands_left = required_or(source.hands_left, 0),
    discards_left = required_or(source.discards_left, 0),
    score = {
      current = required_or(score.current, 0),
      target = required_or(score.target, 0),
    },
    deck_key = optional_or_null(source.deck_key),
    stake_id = optional_or_null(source.stake_id),
    blind_key = optional_or_null(source.blind_key),
    ante = optional_or_null(source.ante),
    round = optional_or_null(source.round),
    blinds = clone_array(source.blinds),
    joker_slots = optional_or_null(source.joker_slots),
    jokers = clone_array(source.jokers),
    consumable_slots = optional_or_null(source.consumable_slots),
    consumables = clone_array(source.consumables),
    tags = clone_array(source.tags),
    vouchers = clone_array(source.vouchers),
    run_info = optional_or_null(source.run_info),
    interest = optional_or_null(source.interest),
    shop_items = clone_array(source.shop_items),
    reroll_cost = optional_or_null(source.reroll_cost),
    pack_contents = optional_or_null(source.pack_contents),
    hand_size = optional_or_null(source.hand_size),
    cards_in_hand = clone_array(source.cards_in_hand),
    selected_cards = clone_array(source.selected_cards),
    cards_in_deck = clone_array(source.cards_in_deck),
  }
end

function snap.is_array(value)
  local meta = getmetatable(value)
  return meta and meta.__ls_arr == true or false
end

function snap.is_null(value)
  local meta = getmetatable(value)
  return meta and meta.__ls_null == true or false
end

return snap
