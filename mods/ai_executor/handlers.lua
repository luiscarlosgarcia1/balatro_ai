local handlers = {}

-- ============================================================
-- Actionable states: the game is stable and ready for a new action
-- ============================================================

local ACTIONABLE_STATE_NAMES = {
  "SELECTING_HAND",
  "SHOP",
  "BLIND_SELECT",
  "TAROT_PACK",
  "PLANET_PACK",
  "SPECTRAL_PACK",
  "BUFFOON_PACK",
  "STANDARD_PACK",
}

handlers.ACTIONABLE_STATE_NAMES = ACTIONABLE_STATE_NAMES

function handlers.is_actionable_state(G)
  if type(G) ~= "table" then
    return false
  end
  local states = G.STATES
  local current = G.STATE
  if type(states) ~= "table" or current == nil then
    return false
  end
  for i = 1, #ACTIONABLE_STATE_NAMES do
    if states[ACTIONABLE_STATE_NAMES[i]] == current then
      return true
    end
  end
  return false
end

-- ============================================================
-- Utilities
-- ============================================================

function handlers.find_card_by_id(cards, id)
  if type(cards) ~= "table" then
    return nil
  end
  for i = 1, #cards do
    local card = cards[i]
    if type(card) == "table" and card.ID == id then
      return card
    end
  end
  return nil
end

-- Clear the highlighted list and flag, then highlight only the cards whose
-- IDs appear in target_ids (preserving their order in area.cards).
local function select_cards_in_area(area, target_ids)
  local highlighted = area.highlighted
  if type(highlighted) == "table" then
    for i = 1, #highlighted do
      highlighted[i].highlighted = false
    end
  end
  area.highlighted = {}

  local target_set = {}
  for i = 1, #target_ids do
    target_set[target_ids[i]] = true
  end

  local cards = area.cards or {}
  for i = 1, #cards do
    local card = cards[i]
    if target_set[card.ID] then
      card.highlighted = true
      area.highlighted[#area.highlighted + 1] = card
    end
  end
end

local function find_in_areas(areas, id)
  for i = 1, #areas do
    local area = areas[i]
    if area and type(area.cards) == "table" then
      local card = handlers.find_card_by_id(area.cards, id)
      if card then
        return card
      end
    end
  end
  return nil
end

local function find_blind_opt(G, target_key)
  local resets = G.GAME and G.GAME.round_resets
  local choices = resets and resets.blind_choices
  if not choices then
    return nil, "no blind choices available"
  end
  local position = nil
  for pos, key in pairs(choices) do
    if key == target_key then
      position = pos
      break
    end
  end
  if not position then
    return nil, "blind not found: " .. tostring(target_key)
  end
  local opt = G.blind_select_opts and G.blind_select_opts[position]
  if not opt then
    return nil, "blind option not available for position: " .. tostring(position)
  end
  return opt, nil
end

-- ============================================================
-- Action handlers
-- ============================================================

local DISPATCH = {}

DISPATCH["play_hand"] = function(action, G)
  select_cards_in_area(G.hand, action.target_ids)
  if #G.hand.highlighted == 0 then
    error("play_hand: no cards matched target_ids in hand")
  end
  G.FUNCS.play_cards_from_highlighted()
end

DISPATCH["discard"] = function(action, G)
  select_cards_in_area(G.hand, action.target_ids)
  if #G.hand.highlighted == 0 then
    error("discard: no cards matched target_ids in hand")
  end
  G.FUNCS.discard_cards_from_highlighted()
end

DISPATCH["buy_shop_item"] = function(action, G)
  local id = action.target_ids[1]
  local item = find_in_areas({ G.shop_jokers, G.shop_vouchers, G.shop_booster }, id)
  if not item then
    error("buy_shop_item: item not found with ID " .. tostring(id))
  end
  G.FUNCS.buy_from_shop({ config = { ref_table = item } })
end

DISPATCH["sell_joker"] = function(action, G)
  local id = action.target_ids[1]
  local card = handlers.find_card_by_id(G.jokers.cards, id)
  if not card then
    error("sell_joker: joker not found with ID " .. tostring(id))
  end
  card:sell_card()
end

DISPATCH["reroll_shop"] = function(action, G)
  G.FUNCS.reroll_shop()
end

DISPATCH["leave_shop"] = function(action, G)
  G.FUNCS.toggle_shop()
end

DISPATCH["select_blind"] = function(action, G)
  local opt, err = find_blind_opt(G, action.target_key)
  if err then
    error("select_blind: " .. err)
  end
  G.FUNCS.select_blind(opt)
end

DISPATCH["skip_blind"] = function(action, G)
  local opt, err = find_blind_opt(G, action.target_key)
  if err then
    error("skip_blind: " .. err)
  end
  G.FUNCS.skip_blind(opt)
end

DISPATCH["pick_pack_item"] = function(action, G)
  local id = action.target_ids[1]
  local pack_cards = G.pack_cards
  if not pack_cards then
    error("pick_pack_item: no pack_cards area")
  end
  local card = handlers.find_card_by_id(pack_cards.cards, id)
  if not card then
    error("pick_pack_item: card not found with ID " .. tostring(id))
  end
  G.FUNCS.use_card({ config = { ref_table = card } })
end

DISPATCH["skip_pack"] = function(action, G)
  G.FUNCS.skip_booster()
end

DISPATCH["use_consumable"] = function(action, G)
  local consumable_id = action.target_ids[1]
  local target_card_ids = {}
  for i = 2, #action.target_ids do
    target_card_ids[#target_card_ids + 1] = action.target_ids[i]
  end

  -- Balatro spells this two ways across versions
  local consumables_area = G.consumeables or G.consumables
  if not consumables_area then
    error("use_consumable: no consumables area")
  end

  local consumable = handlers.find_card_by_id(consumables_area.cards, consumable_id)
  if not consumable then
    error("use_consumable: consumable not found with ID " .. tostring(consumable_id))
  end

  if #target_card_ids > 0 then
    select_cards_in_area(G.hand, target_card_ids)
  end

  G.FUNCS.use_card({ config = { ref_table = consumable } })
end

-- ============================================================
-- dispatch: routes an action to the right handler
-- Returns nil on success, error string on failure.
-- ============================================================

function handlers.dispatch(action, G)
  local kind = action and action.kind
  local handler = kind and DISPATCH[kind]
  if not handler then
    return "unknown action kind: " .. tostring(kind)
  end
  local success, err = pcall(handler, action, G)
  if not success then
    return tostring(err)
  end
  return nil
end

return handlers
