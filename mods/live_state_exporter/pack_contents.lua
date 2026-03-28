local PackContents = {}

local function safe_table(value)
  if type(value) == "table" then
    return value
  end
  return nil
end

local function safe_tostring(value)
  if value == nil then
    return nil
  end
  local ok, result = pcall(tostring, value)
  if ok and result ~= nil then
    return result
  end
  return nil
end

local function safe_number(value)
  if type(value) == "number" then
    return value
  end
  if type(value) == "string" then
    local parsed = tonumber(value)
    if parsed ~= nil then
      return parsed
    end
  end
  return nil
end

local function normalize_token(value)
  local text = safe_tostring(value)
  if not text or text == "" then
    return nil
  end

  text = string.lower(text)
  text = text:gsub("[^a-z0-9]+", "_")
  text = text:gsub("^_+", "")
  text = text:gsub("_+$", "")
  if text == "" then
    return nil
  end
  return text
end

local function first_non_nil(...)
  for i = 1, select("#", ...) do
    local value = select(i, ...)
    if value ~= nil then
      return value
    end
  end
  return nil
end

local function pack_offer_keys(shop_items)
  local keys = {}
  local seen = {}
  for _, item in ipairs(safe_table(shop_items) or {}) do
    if type(item) == "table" and normalize_token(item.kind) == "pack" then
      local key = normalize_token(first_non_nil(item.key, item.pack_key))
      if key and not seen[key] then
        seen[key] = true
        keys[#keys + 1] = key
      end
    end
  end
  return keys
end

local function extract_suffix(key)
  local normalized = normalize_token(key)
  if not normalized then
    return nil
  end
  return normalized:match("_(%d+)$")
end

local function extract_variant_from_key(key)
  local normalized = normalize_token(key)
  if not normalized then
    return nil
  end
  if string.find(normalized, "_mega_", 1, true) then
    return "mega"
  end
  if string.find(normalized, "_jumbo_", 1, true) then
    return "jumbo"
  end
  if string.find(normalized, "_normal_", 1, true) then
    return "normal"
  end
  return nil
end

local function extract_family_from_key(key)
  local normalized = normalize_token(key)
  if not normalized then
    return nil
  end
  for _, family in ipairs({ "arcana", "celestial", "spectral", "standard", "buffoon" }) do
    if string.find(normalized, "p_" .. family .. "_", 1, true) == 1 then
      return family
    end
  end
  return nil
end

local function infer_family_from_cards(cards)
  local saw_standard = false
  local saw_buffoon = false
  local saw_arcana = false
  local saw_celestial = false
  local saw_spectral = false

  for _, card in ipairs(safe_table(cards) or {}) do
    if type(card) == "table" then
      local card_kind = normalize_token(first_non_nil(card.card_kind, card.kind))
      local consumable_kind = normalize_token(card.consumable_kind)
      local key = normalize_token(first_non_nil(card.key, card.card_key))
      if normalize_token(card.suit) and normalize_token(card.rank) then
        saw_standard = true
      end
      if card_kind == "joker" or (key and string.find(key, "j_", 1, true) == 1) then
        saw_buffoon = true
      end
      if consumable_kind == "tarot" then
        saw_arcana = true
      elseif consumable_kind == "planet" then
        saw_celestial = true
      elseif consumable_kind == "spectral" then
        saw_spectral = true
      end
    end
  end

  if saw_standard then
    return "standard"
  end
  if saw_buffoon then
    return "buffoon"
  end
  if saw_arcana then
    return "arcana"
  end
  if saw_celestial then
    return "celestial"
  end
  if saw_spectral then
    return "spectral"
  end
  return nil
end

local function infer_variant(cards, choose_limit, fallback_key)
  local card_count = #(safe_table(cards) or {})
  local normalized_choose_limit = safe_number(choose_limit)

  if card_count >= 5 then
    if normalized_choose_limit and normalized_choose_limit >= 2 then
      return "mega"
    end
    return "jumbo"
  end
  if card_count > 0 then
    return "normal"
  end
  return extract_variant_from_key(fallback_key)
end

local function resolve_suffix(shop_items, remembered_pack_key)
  local suffix = nil
  for _, key in ipairs(pack_offer_keys(shop_items)) do
    local current_suffix = extract_suffix(key)
    if current_suffix then
      if suffix and suffix ~= current_suffix then
        return nil
      end
      suffix = current_suffix
    end
  end
  if suffix then
    return suffix
  end
  return extract_suffix(remembered_pack_key)
end

function PackContents.remembered_key(interaction_phase, shop_items, previous_pack_key)
  if interaction_phase == "shop" then
    local keys = pack_offer_keys(shop_items)
    if #keys == 1 then
      return keys[1]
    end
    return previous_pack_key
  end

  if interaction_phase == "pack_reward" then
    return previous_pack_key
  end

  return nil
end

function PackContents.resolve_pack_key(args)
  local cards = safe_table(args and args.cards) or {}
  local shop_items = safe_table(args and args.shop_items) or {}
  local remembered_pack_key = normalize_token(args and args.remembered_pack_key)

  local family = infer_family_from_cards(cards) or extract_family_from_key(remembered_pack_key)
  local variant = infer_variant(cards, args and args.choose_limit, remembered_pack_key)
  local suffix = resolve_suffix(shop_items, remembered_pack_key)

  if family and variant and suffix then
    return "p_" .. family .. "_" .. variant .. "_" .. suffix
  end

  if #cards == 0 then
    return remembered_pack_key
  end

  return nil
end

function PackContents.build(args)
  local interaction_phase = normalize_token(args and args.interaction_phase)
  if interaction_phase ~= "pack_reward" then
    return nil
  end

  local cards = safe_table(args and args.cards) or {}
  local pack_key = PackContents.resolve_pack_key(args)
  if not pack_key then
    return nil
  end

  local choose_limit = safe_number(args and args.choose_limit)
  local selected_count = safe_number(args and args.selected_count) or 0
  local choices_remaining = choose_limit
  if choose_limit then
    choices_remaining = math.max(0, choose_limit - selected_count)
  end

  local pack_size = #cards
  if pack_size == 0 then
    pack_size = safe_number(args and args.pack_size)
  end

  return {
    pack_key = pack_key,
    pack_size = pack_size,
    choose_limit = choose_limit,
    choices_remaining = choices_remaining,
    skip_available = not not (args and args.skip_available),
    cards = cards,
  }
end

return PackContents
