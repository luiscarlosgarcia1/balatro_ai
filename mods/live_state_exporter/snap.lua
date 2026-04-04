local snap = {}

local array_meta = { __ls_arr = true }
local null_value = setmetatable({}, { __ls_null = true })

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

local phase = load_module("phase.lua")
local core = load_module("core.lua")
local zones = load_module("zones.lua")
local market = load_module("market.lua")

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

local function clone_mapped_array(source, map_fn)
  local out = {}
  if type(source) == "table" then
    for i = 1, #source do
      out[i] = map_fn(as_table(source[i]) or {})
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

local function clone_blinds(source)
  local out = {}
  if type(source) == "table" then
    for i = 1, #source do
      local blind = as_table(source[i]) or {}
      out[i] = {
        key = blind.key,
        state = blind.state,
        tag_key = optional_or_null(blind.tag_key),
      }
    end
  end
  return setmetatable(out, array_meta)
end

local function clone_card(card)
  card = as_table(card) or {}
  return {
    card_key = card.card_key,
    instance_id = card.instance_id,
    enhancement = optional_or_null(card.enhancement),
    edition = optional_or_null(card.edition),
    seal = optional_or_null(card.seal),
    facing = optional_or_null(card.facing),
    debuffed = card.debuffed == true,
    cost = optional_or_null(card.cost),
    sell_cost = optional_or_null(card.sell_cost),
  }
end

local function clone_cards(source)
  return clone_mapped_array(source, clone_card)
end

local function clone_joker(joker)
  joker = as_table(joker) or {}
  return {
    key = joker.key,
    instance_id = joker.instance_id,
    eternal = joker.eternal == true,
    perishable = joker.perishable == true,
    rental = joker.rental == true,
    perish_tally = optional_or_null(joker.perish_tally),
    edition = optional_or_null(joker.edition),
    debuffed = joker.debuffed == true,
    sell_cost = optional_or_null(joker.sell_cost),
  }
end

local function clone_jokers(source)
  return clone_mapped_array(source, clone_joker)
end

local function clone_consumable(consumable)
  consumable = as_table(consumable) or {}
  return {
    key = consumable.key,
    instance_id = consumable.instance_id,
    edition = optional_or_null(consumable.edition),
    cost = optional_or_null(consumable.cost),
    sell_cost = optional_or_null(consumable.sell_cost),
  }
end

local function clone_consumables(source)
  return clone_mapped_array(source, clone_consumable)
end

local function clone_voucher(voucher)
  voucher = as_table(voucher) or {}
  return {
    key = voucher.key,
    cost = required_or(to_number(voucher.cost), 0),
  }
end

local function clone_pack(pack)
  pack = as_table(pack) or {}
  return {
    key = pack.key,
    instance_id = pack.instance_id,
    cost = optional_or_null(pack.cost),
  }
end

local function clone_references(source)
  return clone_mapped_array(source, function(reference)
    return {
      zone = reference.zone,
      instance_id = reference.instance_id,
      key = reference.key,
    }
  end)
end

local function clone_shop_items(source)
  return clone_mapped_array(source, function(item)
    item = as_table(item) or {}
    return {
      card = item.card ~= nil and clone_card(item.card) or null_value,
      joker = item.joker ~= nil and clone_joker(item.joker) or null_value,
      consumable = item.consumable ~= nil and clone_consumable(item.consumable) or null_value,
      voucher = item.voucher ~= nil and clone_voucher(item.voucher) or null_value,
      pack = item.pack ~= nil and clone_pack(item.pack) or null_value,
    }
  end)
end

local function clone_pack_item(item)
  item = as_table(item) or {}
  if item.card_key ~= nil then
    return clone_card(item)
  end
  if item.eternal ~= nil or item.perishable ~= nil or item.rental ~= nil or item.perish_tally ~= nil or item.debuffed ~= nil or item.sell_cost ~= nil then
    return clone_joker(item)
  end
  return clone_consumable(item)
end

local function clone_pack_contents(source)
  source = as_table(source)
  if not source then
    return null_value
  end
  return {
    pack = source.pack ~= nil and clone_pack(source.pack) or null_value,
    choices_remaining = optional_or_null(source.choices_remaining),
    skip_available = source.skip_available == true,
    items = clone_mapped_array(source.items, clone_pack_item),
  }
end

local function clone_run_info(source)
  source = as_table(source)
  local hands = as_table(source and source.hands)
  if not hands then
    return null_value
  end

  local out = {}
  local count = 0
  for hand_name, hand in pairs(hands) do
    if type(hand_name) == "string" and type(hand) == "table" then
      out[hand_name] = hand
      count = count + 1
    end
  end

  if count == 0 then
    return null_value
  end

  return {
    hands = out,
  }
end

local function clone_interest(source)
  source = as_table(source)
  if not source then
    return null_value
  end

  local amount = to_number(source.amount)
  local cap = to_number(source.cap)
  local no_interest = source.no_interest
  if amount == nil and cap == nil and no_interest == nil then
    return null_value
  end

  return {
    amount = required_or(amount, 0),
    cap = required_or(cap, 0),
    no_interest = no_interest == true,
  }
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
  local interaction_phase = phase.infer(root)
  local collected = core.collect(root, interaction_phase)
  local zone_collected = zones.collect(root)
  local market_collected = market.collect(root, interaction_phase)
  local blinds = collected.blinds or {}

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
    blind_key = phase.derive_blind_key(root, interaction_phase, blinds),
    ante = to_number(resets.ante),
    round = to_number(game.round),
    blinds = blinds,
    joker_slots = collected.joker_slots,
    consumable_slots = collected.consumable_slots,
    tags = collected.tags,
    vouchers = collected.vouchers,
    run_info = collected.run_info,
    interest = collected.interest,
    shop_items = market_collected.shop_items,
    reroll_cost = to_number(round.reroll_cost),
    pack_contents = market_collected.pack_contents,
    hand_size = collected.hand_size,
    jokers = zone_collected.jokers,
    consumables = zone_collected.consumables,
    cards_in_hand = zone_collected.cards_in_hand,
    selected_cards = zone_collected.selected_cards,
    cards_in_deck = zone_collected.cards_in_deck,
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
    blinds = clone_blinds(source.blinds),
    joker_slots = optional_or_null(source.joker_slots),
    jokers = clone_jokers(source.jokers),
    consumable_slots = optional_or_null(source.consumable_slots),
    consumables = clone_consumables(source.consumables),
    tags = clone_array(source.tags),
    vouchers = clone_array(source.vouchers),
    run_info = clone_run_info(source.run_info),
    interest = clone_interest(source.interest),
    shop_items = clone_shop_items(source.shop_items),
    reroll_cost = optional_or_null(source.reroll_cost),
    pack_contents = clone_pack_contents(source.pack_contents),
    hand_size = optional_or_null(source.hand_size),
    cards_in_hand = clone_cards(source.cards_in_hand),
    selected_cards = clone_references(source.selected_cards),
    cards_in_deck = clone_cards(source.cards_in_deck),
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
