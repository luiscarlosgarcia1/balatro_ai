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

function Signature.make(snapshot)
  if type(snapshot) ~= "table" then
    return "nil"
  end

  local state = safe_table(snapshot.state) or {}
  local pack_contents = safe_table(state.pack_contents) or {}
  local parts = {
    string_part(state.interaction_phase),
    string_part(state.state_id),
    string_part(state.ante),
    string_part(state.round_count),
    string_part(state.stake_id or state.stake),
    string_part(state.money),
    string_part(state.hands_left),
    string_part(state.discards_left),
    string_part(state.reroll_cost),
    string_part(state.blind_key),
    string_part(safe_table(state.deck) and state.deck.key),
    string_part(state.current_score),
    string_part(state.score_to_beat),
    string_part(state.cards_in_hand),
    string_part(state.jokers_count or state.joker_count),
    string_part(state.consumable_slots or state.consumable_capacity),
    string_part(pack_contents.open_pack_kind),
    string_part(state.skip_tag_claimed),
    string_part(safe_table(state.skip_tag) and state.skip_tag.key),
  }

  add_named_items(parts, state.hand_cards, "name")
  add_named_items(parts, state.jokers, "name")
  add_named_items(parts, state.shop_vouchers, "key")
  add_named_items(parts, state.vouchers, "key")
  add_named_items(parts, state.consumables, "key")
  add_named_items(parts, state.consumables_shop, "key")
  add_named_items(parts, state.shop_items, "key")
  add_named_items(parts, state.skip_tags, "tag_key")
  add_named_items(parts, state.tags, "key")
  add_named_items(parts, state.booster_packs, "key")
  add_named_items(parts, state.blinds, "key")

  return table.concat(parts, "::")
end

return Signature
