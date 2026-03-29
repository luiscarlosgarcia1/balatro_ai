local Signature = {}

local function safe_table(value)
  if type(value) == "table" then
    return value
  end
  return nil
end

local function string_part(value)
  if value == nil then
    return ""
  end
  local ok, result = pcall(tostring, value)
  if ok and result ~= nil then
    return result
  end
  return ""
end

local function add_named_items(parts, items, field_name)
  local labels = {}
  for _, item in ipairs(safe_table(items) or {}) do
    if type(item) == "table" then
      labels[#labels + 1] = string_part(item[field_name])
    else
      labels[#labels + 1] = string_part(item)
    end
  end
  parts[#parts + 1] = table.concat(labels, "|")
end

local function add_structured_items(parts, items, field_names)
  local values = {}
  for _, item in ipairs(safe_table(items) or {}) do
    if type(item) == "table" then
      local item_parts = {}
      for _, field_name in ipairs(field_names) do
        item_parts[#item_parts + 1] = string_part(item[field_name])
      end
      values[#values + 1] = table.concat(item_parts, "/")
    else
      values[#values + 1] = string_part(item)
    end
  end
  parts[#parts + 1] = table.concat(values, "|")
end

function Signature.make(snapshot)
  if type(snapshot) ~= "table" then
    return "nil"
  end

  local state = safe_table(snapshot.state) or {}
  local score = safe_table(state.score) or {}
  local pack_contents = safe_table(state.pack_contents) or {}
  local parts = {
    string_part(state.interaction_phase),
    string_part(state.state_id),
    string_part(state.ante),
    string_part(state.round_count),
    string_part(state.stake_id),
    string_part(state.money),
    string_part(state.hands_left),
    string_part(state.discards_left),
    string_part(state.reroll_cost),
    string_part(state.interest),
    string_part(state.blind_key),
    string_part(state.deck_key),
    string_part(score.current),
    string_part(score.target),
    string_part(state.joker_slots),
    string_part(state.consumable_slots),
    string_part(state.hand_size),
    string_part(pack_contents.pack_key),
    string_part(pack_contents.pack_size),
    string_part(pack_contents.choose_limit),
    string_part(pack_contents.choices_remaining),
    string_part(pack_contents.skip_available),
  }

  add_structured_items(parts, state.cards_in_hand, {
    "card_key",
    "rarity",
    "enhancement",
    "edition",
    "seal",
    "facing",
    "cost",
    "sell_price",
    "debuffed",
  })
  add_structured_items(parts, state.cards_in_deck, {
    "card_key",
    "rarity",
    "enhancement",
    "edition",
    "seal",
    "facing",
    "cost",
    "sell_price",
    "debuffed",
  })
  add_structured_items(parts, state.selected_cards, {
    "zone",
    "card_key",
    "joker_key",
    "consumable_key",
    "pack_key",
    "voucher_key",
  })
  add_structured_items(parts, state.jokers, { "key", "rarity", "edition", "sell_price", "debuffed" })
  add_named_items(parts, state.vouchers, "key")
  add_structured_items(parts, state.consumables, { "key", "edition", "sell_price", "debuffed" })
  add_structured_items(parts, state.shop_items, {
    "key",
    "cost",
    "rarity",
    "edition",
    "sell_price",
    "enhancement",
    "seal",
    "debuffed",
    "card_key",
  })
  add_structured_items(parts, pack_contents.cards, {
    "card_key",
    "rarity",
    "enhancement",
    "edition",
    "seal",
    "facing",
    "cost",
    "sell_price",
    "debuffed",
  })
  add_named_items(parts, state.tags, "key")
  add_structured_items(parts, state.blinds, { "key", "state", "tag_key", "tag_claimed" })

  return table.concat(parts, "::")
end

return Signature
