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
    if type(item) == "table" then
      local key = normalize_token(item.key)
      if key and string.find(key, "p_", 1, true) == 1 and not seen[key] then
        seen[key] = true
        keys[#keys + 1] = key
      end
    end
  end
  return keys
end

local TAROT_KEYS = {
  c_fool = true,
  c_magician = true,
  c_high_priestess = true,
  c_empress = true,
  c_emperor = true,
  c_hierophant = true,
  c_lovers = true,
  c_chariot = true,
  c_justice = true,
  c_hermit = true,
  c_wheel_of_fortune = true,
  c_strength = true,
  c_hanged_man = true,
  c_death = true,
  c_temperance = true,
  c_devil = true,
  c_tower = true,
  c_star = true,
  c_moon = true,
  c_sun = true,
  c_judgement = true,
  c_world = true,
}

local PLANET_KEYS = {
  c_mercury = true,
  c_venus = true,
  c_earth = true,
  c_mars = true,
  c_jupiter = true,
  c_saturn = true,
  c_uranus = true,
  c_neptune = true,
  c_pluto = true,
  c_planet_x = true,
  c_ceres = true,
  c_eris = true,
}

local SPECTRAL_KEYS = {
  c_familiar = true,
  c_grim = true,
  c_incantation = true,
  c_talisman = true,
  c_aura = true,
  c_wraith = true,
  c_sigil = true,
  c_ouija = true,
  c_ectoplasm = true,
  c_immolate = true,
  c_ankh = true,
  c_deja_vu = true,
  c_hex = true,
  c_trance = true,
  c_medium = true,
  c_cryptid = true,
  c_soul = true,
  c_black_hole = true,
}

local function is_standard_playing_card_key(key)
  local normalized = normalize_token(key)
  if not normalized then
    return false
  end
  local suit, rank = normalized:match("^([cdhs])_(.+)$")
  if not suit or not rank then
    return false
  end
  return rank == "a"
    or rank == "j"
    or rank == "q"
    or rank == "k"
    or rank == "10"
    or rank == "2"
    or rank == "3"
    or rank == "4"
    or rank == "5"
    or rank == "6"
    or rank == "7"
    or rank == "8"
    or rank == "9"
end

local function infer_family_from_key(key)
  local normalized = normalize_token(key)
  if not normalized then
    return nil
  end
  if is_standard_playing_card_key(normalized) then
    return "standard"
  end
  if string.find(normalized, "j_", 1, true) == 1 then
    return "buffoon"
  end
  if TAROT_KEYS[normalized] then
    return "arcana"
  end
  if PLANET_KEYS[normalized] then
    return "celestial"
  end
  if SPECTRAL_KEYS[normalized] then
    return "spectral"
  end
  return nil
end

local function infer_family_from_cards(cards)
  for _, card in ipairs(safe_table(cards) or {}) do
    if type(card) == "table" then
      local family = infer_family_from_key(first_non_nil(card.card_key, card.key))
      if family then
        return family
      end
    end
  end
  return nil
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
