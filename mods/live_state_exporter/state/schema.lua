local schema = {}

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
local primitives = load_module("state/schema/primitives.lua")(values)
local entities = load_module("state/schema/entities.lua")(values, primitives)
local sections = load_module("state/schema/sections.lua")(values, primitives, entities)
local as_table = values.as_table
local clone_array = primitives.clone_array
local optional_or_null = primitives.optional_or_null
local required_or = primitives.required_or

function schema.build_shell(source)
  source = as_table(source) or {}
  local score = as_table(source.score) or {}

  return {
    state_id = required_or(source.state_id, 0),
    interaction_phase = optional_or_null(source.interaction_phase),
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
    blinds = sections.clone_blinds(source.blinds),
    joker_slots = optional_or_null(source.joker_slots),
    jokers = entities.clone_jokers(source.jokers),
    consumable_slots = optional_or_null(source.consumable_slots),
    consumables = entities.clone_consumables(source.consumables),
    tags = clone_array(source.tags),
    vouchers = clone_array(source.vouchers),
    run_info = sections.clone_run_info(source.run_info),
    interest = sections.clone_interest(source.interest),
    shop_items = sections.clone_shop_items(source.shop_items),
    reroll_cost = optional_or_null(source.reroll_cost),
    pack_contents = sections.clone_pack_contents(source.pack_contents),
    hand_size = optional_or_null(source.hand_size),
    cards_in_hand = entities.clone_cards(source.cards_in_hand),
    selected_cards = entities.clone_references(source.selected_cards),
    cards_in_deck = entities.clone_cards(source.cards_in_deck),
  }
end

function schema.is_array(value)
  return primitives.is_array(value)
end

function schema.is_null(value)
  return primitives.is_null(value)
end

return schema
