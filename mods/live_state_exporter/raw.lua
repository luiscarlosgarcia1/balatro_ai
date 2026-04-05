local raw = {}

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
local run_state = load_module("run_state.lua")
local zones = load_module("zones.lua")
local market = load_module("market.lua")
local values = load_module("shared/values.lua")
local as_table = values.as_table
local to_number = values.to_number
local first_defined = values.first_defined

local function read_deck_key(game)
  local selected_back = as_table(game and game.selected_back)
  return first_defined(game and game.selected_back_key, selected_back and selected_back.key)
end

function raw.read_state(root)
  root = as_table(root) or {}

  local game = as_table(root.GAME) or {}
  local round = as_table(game.current_round) or {}
  local resets = as_table(game.round_resets) or {}
  local blind = as_table(game.blind) or {}
  local interaction_phase = phase.infer(root)
  local collected = run_state.collect(root, interaction_phase)
  local zone_collected = zones.collect(root)
  local market_collected = market.collect(root, interaction_phase)
  local blinds = collected.blinds or {}

  return {
    state_id = to_number(first_defined(root.STATE, game.state, game.current_round_state)),
    interaction_phase = interaction_phase,
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

return raw
