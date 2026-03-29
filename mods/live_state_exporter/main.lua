--- STEAMODDED HEADER
--- MOD_ID: live_state_exporter
--- MOD_NAME: Live State Exporter
--- MOD_AUTHOR: [luiga]
--- MOD_DESCRIPTION: Writes compact live Balatro state snapshots to ai/live_state.json for external agents.
--- PREFIX: live_state_exporter
--- VERSION: 0.2.0

local EXPORT_DIR = "ai"
local EXPORT_FILE = "live_state.json"
local EXPORT_PATH = EXPORT_DIR .. "/" .. EXPORT_FILE
local EXPORT_INTERVAL_SECONDS = 0.05
local EXPORT_MAX_HAND_CARDS = 20
local EXPORT_MAX_JOKERS = 8
local EXPORT_MAX_CONSUMABLES = 10
local EXPORT_MAX_VOUCHERS = 8
local EXPORT_MAX_TAGS = 8
local EXPORT_MAX_DECK_CARDS = 80
local EXPORT_MAX_PACK_CARDS = 16
local EXPORT_MAX_STRING = 80
local unpack_fn = table.unpack or unpack
local remembered_shop_pack_key = nil

local function load_module(filename)
  local mod = rawget(_G, "SMODS") and SMODS.current_mod
  local mod_path = mod and mod.path
  if mod_path and rawget(_G, "NFS") and type(NFS.read) == "function" then
    local chunk, err = load(
      NFS.read(mod_path .. filename),
      '=[SMODS live_state_exporter "' .. filename .. '"]'
    )
    assert(chunk, err)
    return chunk()
  end
  error("live_state_exporter could not load " .. filename)
end

local Signature = load_module("signature.lua")
local BlindKey = load_module("blind_key.lua")
local PackContents = load_module("pack_contents.lua")

local function now()
  if love and love.timer and love.timer.getTime then
    return love.timer.getTime()
  end
  return os.clock()
end

local function trim_text(value, limit)
  local text = tostring(value or "")
  if #text <= limit then
    return text
  end
  return text:sub(1, math.max(0, limit - 3)) .. "..."
end

local function safe_tostring(value)
  if value == nil then
    return nil
  end
  local ok, result = pcall(tostring, value)
  if ok then
    return result
  end
  return nil
end

local function safe_number(value)
  if type(value) == "number" then
    return value
  end
  if type(value) == "table" then
    local direct = value[1]
    if type(direct) ~= "number" then
      direct = value.value
    end
    if type(direct) ~= "number" then
      direct = value.n
    end
    if type(direct) == "number" then
      return direct
    end
  end
  local text = safe_tostring(value)
  if text and string.match(text, "^%-?%d+$") then
    return tonumber(text)
  end
  return nil
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

local function safe_table(value)
  if type(value) == "table" then
    return value
  end
  return nil
end

local function safe_bool(value)
  return not not value
end

local function normalize_token(value)
  local text = safe_tostring(value)
  if not text or text == "" then
    return nil
  end
  text = string.lower(text)
  text = text:gsub("[^%w]+", "_")
  text = text:gsub("_+", "_")
  text = text:gsub("^_", "")
  text = text:gsub("_$", "")
  if text == "" then
    return nil
  end
  return text
end

local function normalize_rarity(value)
  local numeric = safe_number(value)
  if numeric == 1 then
    return "common"
  elseif numeric == 2 then
    return "uncommon"
  elseif numeric == 3 then
    return "rare"
  elseif numeric == 4 then
    return "legendary"
  end

  local text = normalize_token(value)
  if text then
    return text
  end
  return nil
end

local function is_array(tbl)
  if type(tbl) ~= "table" then
    return false
  end
  local count = 0
  for key, _ in pairs(tbl) do
    if type(key) ~= "number" then
      return false
    end
    count = count + 1
  end
  return count > 0
end

local function escape_json_string(value)
  local replacements = {
    ['\\'] = '\\\\',
    ['"'] = '\\"',
    ["\b"] = "\\b",
    ["\f"] = "\\f",
    ["\n"] = "\\n",
    ["\r"] = "\\r",
    ["\t"] = "\\t",
  }

  return value:gsub('[%z\1-\31\\"]', function(char)
    return replacements[char] or string.format("\\u%04x", char:byte())
  end)
end

local function encode_json(value, seen)
  local kind = type(value)
  if kind == "nil" then
    return "null"
  end
  if kind == "boolean" then
    return value and "true" or "false"
  end
  if kind == "number" then
    if value ~= value or value == math.huge or value == -math.huge then
      return "null"
    end
    return tostring(value)
  end
  if kind == "string" then
    return '"' .. escape_json_string(value) .. '"'
  end
  if kind ~= "table" then
    return "null"
  end

  seen = seen or {}
  if seen[value] then
    return "null"
  end
  seen[value] = true

  local parts = {}
  if is_array(value) then
    local n = #value
    for i = 1, n do
      parts[#parts + 1] = encode_json(value[i], seen)
    end
    seen[value] = nil
    return "[" .. table.concat(parts, ",") .. "]"
  end

  local keys = {}
  for key, _ in pairs(value) do
    keys[#keys + 1] = key
  end
  table.sort(keys, function(a, b)
    return tostring(a) < tostring(b)
  end)

  for _, key in ipairs(keys) do
    local encoded_value = encode_json(value[key], seen)
    parts[#parts + 1] = '"' .. escape_json_string(tostring(key)) .. '":' .. encoded_value
  end
  seen[value] = nil
  return "{" .. table.concat(parts, ",") .. "}"
end

local function format_modifier(name, value, default)
  if value == nil or value == default then
    return nil
  end
  return tostring(name) .. "=" .. tostring(value)
end

local function push_unique(items, seen, key, value)
  if key == nil or seen[key] then
    return
  end
  seen[key] = true
  items[#items + 1] = value
end

local function append_modifier_value(modifiers, name, value)
  if value == nil then
    return
  end

  local kind = type(value)
  if kind == "table" then
    if is_array(value) then
      for _, item in ipairs(value) do
        append_modifier_value(modifiers, name, item)
      end
      return
    end

    for key, item in pairs(value) do
      if item then
        if type(item) == "boolean" and item then
          modifiers[#modifiers + 1] = tostring(name) .. "=" .. tostring(key)
        else
          modifiers[#modifiers + 1] = tostring(name) .. "=" .. trim_text(safe_tostring(item) or tostring(key), 24)
        end
      end
    end
    return
  end

  if kind == "boolean" then
    if value then
      modifiers[#modifiers + 1] = tostring(name)
    end
    return
  end

  modifiers[#modifiers + 1] = tostring(name) .. "=" .. trim_text(safe_tostring(value), 24)
end

local function card_list_from_area(area)
  local area_table = safe_table(area)
  if not area_table then
    return {}
  end
  return safe_table(area_table.cards) or {}
end

local normalize_consumable_kind

local function build_standard_card_identity(card, base, save_fields)
  local config = safe_table(card.config) or {}
  local rank = normalize_token(first_non_nil(base.value, card.rank))
  local suit = normalize_token(first_non_nil(base.suit, card.suit))
  local card_key = normalize_token(first_non_nil(config.card_key, save_fields.card, card.card_key, card.key))

  if (not card_key or card_key == "c_base") and rank and suit then
    card_key = "c_" .. rank .. "_" .. suit
  end

  return card_key, rank, suit
end

local function build_typed_reference(card, zone)
  if type(card) ~= "table" then
    return nil
  end

  local ability = safe_table(card.ability) or {}
  local save_fields = safe_table(card.save_fields) or {}
  local base = safe_table(card.base) or {}
  local set_name = normalize_token(first_non_nil(ability.set, card.set))
  local key = normalize_token(first_non_nil(ability.key, save_fields.center, save_fields.card, card.card_key, card.key))
  local consumable_kind = normalize_consumable_kind(first_non_nil(ability.set, card.set, ability.consumeable_type), key)

  local ref = {
    zone = zone,
  }

  if set_name == "voucher" then
    ref.voucher_key = key
    return ref.voucher_key and ref or nil
  end

  if set_name == "joker" then
    ref.joker_key = key
    return ref.joker_key and ref or nil
  end

  if set_name == "booster" then
    ref.pack_key = key
    return ref.pack_key and ref or nil
  end

  if consumable_kind then
    ref.consumable_key = key
    return ref.consumable_key and ref or nil
  end

  local card_key = build_standard_card_identity(card, base, save_fields)
  if type(card_key) == "table" then
    card_key = nil
  end
  ref.card_key = card_key
  return ref.card_key and ref or nil
end

local function collect_stickers(card, ability, save_fields)
  local stickers = {}
  local seen = {}

  local function add_sticker(value)
    local text = safe_tostring(value)
    if text and text ~= "" and not seen[text] then
      seen[text] = true
      stickers[#stickers + 1] = text
    end
  end

  local function add_many(value)
    if type(value) == "table" then
      if is_array(value) then
        for _, item in ipairs(value) do
          add_sticker(item)
        end
      else
        for key, item in pairs(value) do
          if item then
            add_sticker(item == true and key or item)
          end
        end
      end
      return
    end
    add_sticker(value)
  end

  add_many(first_non_nil(card.sticker, card.stickers))
  add_many(first_non_nil(ability.sticker, ability.stickers))
  add_many(first_non_nil(save_fields.sticker, save_fields.stickers))

  for _, flag in ipairs({ "eternal", "perishable", "rental", "pinned" }) do
    if card[flag] or ability[flag] then
      add_sticker(flag)
    end
  end

  return stickers
end

local function summarize_card(card, area_name)
  if type(card) ~= "table" then
    return nil
  end

  local base = safe_table(card.base) or {}
  local save_fields = safe_table(card.save_fields) or {}
  local ability = safe_table(card.ability) or {}
  local edition = safe_table(card.edition) or {}
  local center = safe_table(card.config) and safe_table(card.config.center) or {}

  local enhancement = safe_tostring(first_non_nil(ability.effect, card.enhancement))
  if enhancement == "Base" then
    enhancement = nil
  end

  local stickers = collect_stickers(card, ability, save_fields)
  local card_key, rank, suit = build_standard_card_identity(card, base, save_fields)

  return {
    area = area_name,
    zone = area_name,
    kind = safe_tostring(first_non_nil(ability.set, card.set, base.set, card.ability_name)),
    card_kind = normalize_token(first_non_nil(ability.set, card.set, base.set, card.ability_name)),
    key = safe_tostring(first_non_nil(ability.key, save_fields.center, save_fields.card, card.card_key, card.key)),
    card_key = card_key,
    code = safe_tostring(first_non_nil(save_fields.card, card.card_key, card.key)),
    name = trim_text(
      safe_tostring(first_non_nil(base.name, card.label, ability.name, card.name, card.key)) or "card",
      EXPORT_MAX_STRING
    ),
    rank = rank,
    suit = suit,
    rarity = normalize_rarity(first_non_nil(center.rarity, ability.rarity)),
    facing = safe_tostring(card.facing),
    enhancement = enhancement,
    edition = safe_tostring(first_non_nil(edition.type, edition.key, edition.name)),
    seal = safe_tostring(first_non_nil(card.seal, base.seal)),
    cost = safe_number(first_non_nil(card.cost, card.base_cost, ability.cost)),
    sell_price = safe_number(card.sell_cost),
    consumable_kind = normalize_consumable_kind(first_non_nil(ability.set, card.set, ability.consumeable_type), first_non_nil(ability.key, card.key)),
    debuffed = safe_bool(first_non_nil(card.debuffed, card.debuff)),
    stickers = stickers,
  }
end

local function summarize_joker(card)
  if type(card) ~= "table" then
    return nil
  end

  local ability = safe_table(card.ability) or {}
  local save_fields = safe_table(card.save_fields) or {}
  local edition = safe_table(card.edition) or {}
  local center = safe_table(card.config) and safe_table(card.config.center) or {}
  local stickers = collect_stickers(card, ability, {})

  local key = safe_tostring(first_non_nil(ability.key, center.key, save_fields.center, card.card_key, card.key))
  if not key then
    return nil
  end

  return {
    key = key,
    rarity = normalize_rarity(first_non_nil(center.rarity, ability.rarity)),
    edition = safe_tostring(first_non_nil(edition.type, edition.key, edition.name)),
    sell_price = safe_number(card.sell_cost),
    debuffed = safe_bool(first_non_nil(card.debuffed, card.debuff)),
    stickers = stickers,
  }
end

local function summarize_voucher(value, key_hint, cost_hint)
  local voucher = safe_table(value) or {}
  local key = safe_tostring(first_non_nil(voucher.key, voucher.center_key, key_hint))
  if not key then
    return nil
  end
  local cost = safe_number(first_non_nil(voucher.cost, voucher.base_cost, cost_hint))
  local summary = {
    key = key,
  }
  if cost ~= nil then
    summary.cost = cost
  end
  return summary
end

local function collect_value_entries(payload, limit, summarize_fn)
  local result = {}
  local seen = {}
  local function add_summary(summary)
    if summary and #result < limit then
      push_unique(result, seen, summary.key or summary.name, summary)
    end
  end

  local kind = type(payload)
  if kind == "table" then
    if payload.cards then
      for _, item in ipairs(card_list_from_area(payload)) do
        add_summary(summarize_fn(item))
      end
      return result
    end

    local found_entry = false
    for key, item in pairs(payload) do
      if type(key) == "number" then
        found_entry = true
        if type(item) == "table" then
          add_summary(summarize_fn(item, key))
        else
          add_summary(summarize_fn(nil, item))
        end
      elseif type(item) == "table" and (item.name or item.label or item.key) then
        found_entry = true
        add_summary(summarize_fn(item, key))
      elseif type(item) == "string" then
        found_entry = true
        add_summary(summarize_fn(nil, item))
      end
    end
    if found_entry then
      return result
    end

    add_summary(summarize_fn(payload))
    return result
  end

  if kind == "string" then
    add_summary(summarize_fn(nil, payload))
  end

  return result
end

normalize_consumable_kind = function(raw_kind, fallback_key)
  local kind = safe_tostring(raw_kind)
  if kind then
    kind = string.lower(kind)
    if kind == "tarot" or kind == "planet" or kind == "spectral" then
      return kind
    end
    if kind == "tarot card" then
      return "tarot"
    end
    if kind == "planet card" then
      return "planet"
    end
    if kind == "spectral card" then
      return "spectral"
    end
  end

  local key = safe_tostring(fallback_key)
  if key then
    local lowered = string.lower(key)
    if string.find(lowered, "tarot", 1, true) then
      return "tarot"
    end
    if string.find(lowered, "planet", 1, true) then
      return "planet"
    end
    if string.find(lowered, "spectral", 1, true) then
      return "spectral"
    end
  end

  return nil
end

local function summarize_consumable(card)
  if type(card) ~= "table" then
    return nil
  end

  local ability = safe_table(card.ability) or {}
  local save_fields = safe_table(card.save_fields) or {}
  local set_name = first_non_nil(ability.set, card.set, ability.consumeable_type)
  local key = safe_tostring(first_non_nil(ability.key, save_fields.center, card.key))
  local kind = normalize_consumable_kind(set_name, key)
  if not kind or not key then
    return nil
  end

  return {
    key = key,
    edition = safe_tostring(first_non_nil(safe_table(card.edition) and card.edition.type, safe_table(card.edition) and card.edition.key, safe_table(card.edition) and card.edition.name)),
    sell_price = safe_number(card.sell_cost),
    debuffed = safe_bool(first_non_nil(card.debuffed, card.debuff)),
    stickers = collect_stickers(card, ability, save_fields),
    cost = safe_number(first_non_nil(card.cost, card.base_cost, ability.cost)),
  }
end

local function summarize_tag(value, key_hint)
  local tag = safe_table(value) or {}
  local key = safe_tostring(first_non_nil(tag.key, key_hint))
  if not key then
    return nil
  end
  return {
    key = key,
  }
end

local function summarize_booster_pack(card)
  if type(card) ~= "table" then
    return nil
  end

  local ability = safe_table(card.ability) or {}
  local save_fields = safe_table(card.save_fields) or {}
  local center = safe_table(card.config) and safe_table(card.config.center) or {}
  local key = safe_tostring(first_non_nil(
    ability.key,
    center.key,
    save_fields.center,
    save_fields.card,
    card.card_key,
    card.key
  ))
  local has_label = safe_tostring(first_non_nil(ability.name, card.label, card.name, key))
  if not has_label and not key then
    return nil
  end

  return {
    key = key,
    cost = safe_number(first_non_nil(card.cost, card.base_cost, ability.cost)),
  }
end

local function collect_cards(area, limit, area_name)
  local result = {}
  local count = 0
  for _, card in ipairs(card_list_from_area(area)) do
    count = count + 1
    if #result < limit then
      local summary = summarize_card(card, area_name)
      if summary then
        result[#result + 1] = summary
      end
    end
  end
  return result, count
end

local CARD_SUIT_ORDER = {
  clubs = 0,
  diamonds = 1,
  hearts = 2,
  spades = 3,
}

local CARD_RANK_ORDER = {
  ace = 0,
  ["2"] = 1,
  ["3"] = 2,
  ["4"] = 3,
  ["5"] = 4,
  ["6"] = 5,
  ["7"] = 6,
  ["8"] = 7,
  ["9"] = 8,
  ["10"] = 9,
  jack = 10,
  queen = 11,
  king = 12,
}

local function sort_canonical_cards(cards)
  local decorated = {}
  for index, card in ipairs(cards or {}) do
    local suit = normalize_token(card and card.suit)
    local rank = normalize_token(card and card.rank)
    decorated[#decorated + 1] = {
      index = index,
      suit_order = CARD_SUIT_ORDER[suit] or 99,
      rank_order = CARD_RANK_ORDER[rank] or 99,
      suit = suit or "",
      rank = rank or "",
      card = card,
    }
  end

  table.sort(decorated, function(left, right)
    if left.suit_order ~= right.suit_order then
      return left.suit_order < right.suit_order
    end
    if left.rank_order ~= right.rank_order then
      return left.rank_order < right.rank_order
    end
    if left.suit ~= right.suit then
      return left.suit < right.suit
    end
    if left.rank ~= right.rank then
      return left.rank < right.rank
    end
    return left.index < right.index
  end)

  local sorted = {}
  for _, entry in ipairs(decorated) do
    sorted[#sorted + 1] = entry.card
  end
  return sorted
end

local function to_public_card(card)
  if type(card) ~= "table" then
    return nil
  end

  local public = {}
  if card.card_key ~= nil then
    public.card_key = card.card_key
  else
    if card.card_kind ~= nil then
      public.card_kind = card.card_kind
    end
    if card.suit ~= nil then
      public.suit = card.suit
    end
    if card.rank ~= nil then
      public.rank = card.rank
    end
    if card.rarity ~= nil then
      public.rarity = card.rarity
    end
  end
  if card.enhancement ~= nil then
    public.enhancement = card.enhancement
  end
  if card.edition ~= nil then
    public.edition = card.edition
  end
  if card.seal ~= nil then
    public.seal = card.seal
  end
  if card.stickers ~= nil and #card.stickers > 0 then
    public.stickers = card.stickers
  end
  if card.facing ~= nil then
    public.facing = card.facing
  end
  if card.cost ~= nil then
    public.cost = card.cost
  end
  if card.sell_price ~= nil then
    public.sell_price = card.sell_price
  end
  if card.debuffed then
    public.debuffed = true
  end
  return public
end

local function to_public_cards(cards)
  local result = {}
  for _, card in ipairs(cards or {}) do
    local public = to_public_card(card)
    if public then
      result[#result + 1] = public
    end
  end
  return result
end

local function card_entries_from_source(source)
  local area = safe_table(source)
  if not area then
    return {}
  end
  if area.cards then
    return card_list_from_area(area)
  end
  if is_array(area) then
    return area
  end
  if area.base or area.ability or area.label or area.name then
    return { area }
  end
  return {}
end

local function collect_cards_from_sources(sources, limit, area_name)
  if type(sources) ~= "table" then
    return {}
  end

  for _, source in ipairs(sources) do
    local entries = card_entries_from_source(source)
    if #entries > 0 then
      local result = {}
      for _, card in ipairs(entries) do
        if #result >= limit then
          return result
        end
        local summary = summarize_card(card, area_name)
        if summary then
          result[#result + 1] = summary
        end
      end
      return result
    end
  end

  return {}
end

local function collect_jokers(area, limit)
  local result = {}
  for _, card in ipairs(card_list_from_area(area)) do
    if #result < limit then
      local summary = summarize_joker(card)
      if summary then
        result[#result + 1] = summary
      end
    end
  end
  return result
end

local function collect_consumables_from_area(area, limit)
  local result = {}
  local seen = {}
  for _, card in ipairs(card_list_from_area(area)) do
    if #result >= limit then
      break
    end
    local summary = summarize_consumable(card)
    if summary then
      push_unique(result, seen, summary.key or summary.name, summary)
    end
  end
  return result
end

local function collect_used_vouchers(game, root)
  local result = {}
  local seen = {}
  local used_vouchers = safe_table(game.used_vouchers) or {}
  for key, value in pairs(used_vouchers) do
    if value then
      local summary = summarize_voucher(nil, key)
      if summary then
        push_unique(result, seen, summary.key, summary)
      end
    end
  end

  for _, card in ipairs(card_list_from_area(root and root.vouchers)) do
    if #result >= EXPORT_MAX_VOUCHERS then
      break
    end
    local ability = safe_table(card.ability) or {}
    local summary = summarize_voucher(
      ability,
      safe_tostring(first_non_nil(card.key, ability.key)),
      first_non_nil(card.cost, card.base_cost, ability.cost)
    )
    if summary then
      push_unique(result, seen, summary.key, summary)
    end
  end
  return result
end

local function collect_tags(game, root)
  local result = {}

  local function add_tag(value, key_hint)
    if #result >= EXPORT_MAX_TAGS then
      return
    end
    local summary = summarize_tag(value, key_hint)
    if summary then
      result[#result + 1] = summary
    end
  end

  local tags = safe_table(root and root.tags) or safe_table(game.tags) or {}
  if is_array(tags) then
    for _, tag in ipairs(tags) do
      add_tag(tag, nil)
    end
  else
    for key, tag in pairs(tags) do
      add_tag(tag, key)
    end
  end

  return result
end

local function collect_blinds(game)
  local result = {}
  local round_resets = safe_table(game.round_resets) or {}
  local blind_keys_by_slot = safe_table(round_resets.blind_choices) or {}
  local blind_states = safe_table(round_resets.blind_states) or {}
  local blind_tags = safe_table(round_resets.blind_tags) or {}
  local slot_order = { "Small", "Big", "Boss" }
  local seen = {}

  for _, slot in ipairs(slot_order) do
    local key = safe_tostring(blind_keys_by_slot[slot])
    if key then
      local state = safe_tostring(blind_states[slot])
      local tag_key = safe_tostring(blind_tags[slot])
      result[#result + 1] = {
        key = key,
        state = state,
        tag_key = tag_key,
        tag_claimed = state == "Skipped" and tag_key ~= nil,
      }
      seen[slot] = true
    end
  end

  for slot, key in pairs(blind_keys_by_slot) do
    if not seen[slot] then
      local state = safe_tostring(blind_states[slot])
      local tag_key = safe_tostring(blind_tags[slot])
      result[#result + 1] = {
        key = safe_tostring(key),
        state = state,
        tag_key = tag_key,
        tag_claimed = state == "Skipped" and tag_key ~= nil,
      }
    end
  end

  return result
end

local function summarize_deck(game)
  local deck = safe_table(first_non_nil(game.selected_back_key, game.selected_back))
  if not deck then
    return nil
  end
  return {
    name = safe_tostring(deck.name),
    key = safe_tostring(deck.key),
  }
end

local function summarize_stake(game, root)
  local stake_index = safe_number(game.stake)
  if not stake_index then
    return nil
  end

  local stake_pool = safe_table(root and root.P_CENTER_POOLS) and safe_table(root.P_CENTER_POOLS.Stake) or {}
  local stake = stake_pool[stake_index]
  if type(stake) ~= "table" then
    return {
      name = "Stake " .. tostring(stake_index),
      key = nil,
      index = stake_index,
    }
  end

  return {
    name = safe_tostring(first_non_nil(stake.name, stake.key)) or ("Stake " .. tostring(stake_index)),
    key = safe_tostring(stake.key),
    index = stake_index,
  }
end

local function summarize_shop_item(card, area_kind)
  if type(card) ~= "table" then
    return nil
  end

  local ability = safe_table(card.ability) or {}
  local save_fields = safe_table(card.save_fields) or {}
  local edition = safe_table(card.edition) or {}
  local center = safe_table(card.config) and safe_table(card.config.center) or {}
  local item_cost = safe_number(first_non_nil(card.cost, card.base_cost, ability.cost))

  if area_kind == "voucher" then
    local voucher = summarize_voucher(
      {
        key = safe_tostring(first_non_nil(ability.key, center.key, save_fields.center, card.card_key, card.key)),
        center_key = safe_tostring(first_non_nil(center.key, save_fields.center)),
        cost = safe_number(first_non_nil(ability.cost, center.cost, card.base_cost)),
      },
      safe_tostring(first_non_nil(card.key, ability.key, center.key, save_fields.center, card.card_key)),
      item_cost
    )
    if not voucher then
      return nil
    end
    return {
      key = voucher.key,
      cost = voucher.cost,
    }
  end

  if area_kind == "pack" then
    local pack = summarize_booster_pack(card)
    if pack then
      return {
        key = pack.key,
        cost = pack.cost,
        edition = safe_tostring(first_non_nil(edition.type, edition.key, edition.name)),
        sell_price = safe_number(card.sell_cost),
        stickers = collect_stickers(card, ability, save_fields),
      }
    end
  end

  local consumable = summarize_consumable(card)
  if consumable then
      return {
        key = consumable.key,
        cost = consumable.cost,
        edition = safe_tostring(first_non_nil(edition.type, edition.key, edition.name)),
        sell_price = safe_number(card.sell_cost),
        stickers = collect_stickers(card, ability, save_fields),
        debuffed = safe_bool(first_non_nil(card.debuffed, card.debuff)),
      }
  end

  local joker = summarize_joker(card)
  if joker and area_kind == "joker" then
      return {
        key = joker.key,
        cost = item_cost,
        rarity = joker.rarity,
        edition = joker.edition,
        sell_price = joker.sell_price,
        debuffed = joker.debuffed,
        stickers = joker.stickers,
      }
  end

  local generic_card = summarize_card(card, "shop")
  if generic_card then
    if generic_card.key then
      return {
        key = generic_card.key,
        card_key = generic_card.card_key,
        cost = generic_card.cost,
        sell_price = generic_card.sell_price,
        enhancement = generic_card.enhancement,
        edition = generic_card.edition,
        seal = generic_card.seal,
        debuffed = generic_card.debuffed,
        stickers = generic_card.stickers,
      }
    end
    return {
      kind = generic_card.kind or area_kind or "shop",
      name = generic_card.name,
      key = generic_card.key,
      card_key = generic_card.card_key,
      card_kind = generic_card.card_kind,
      suit = generic_card.suit,
      rank = generic_card.rank,
      rarity = generic_card.rarity,
      cost = generic_card.cost,
      sell_price = generic_card.sell_price,
      enhancement = generic_card.enhancement,
      edition = generic_card.edition,
      seal = generic_card.seal,
      consumable_kind = generic_card.consumable_kind,
      debuffed = generic_card.debuffed,
      stickers = generic_card.stickers,
    }
  end

  local label = safe_tostring(first_non_nil(card.label, ability.name, card.name, card.key))
  if not label then
    return nil
  end

  return {
    kind = area_kind or string.lower(safe_tostring(first_non_nil(ability.set, card.set)) or "shop"),
    name = trim_text(label, EXPORT_MAX_STRING),
    key = safe_tostring(first_non_nil(ability.key, card.key)),
    cost = item_cost,
    sell_price = safe_number(card.sell_cost),
    stickers = collect_stickers(card, ability, safe_table(card.save_fields) or {}),
    debuffed = safe_bool(first_non_nil(card.debuffed, card.debuff)),
  }
end

local function collect_shop_items(root, interaction_phase)
  local decorated = {}
  local seen = {}
  local sequence = 0
  local areas = {
    { area = root and rawget(root, "shop_jokers"), kind = "joker", row = 0, column = 0 },
  }
  if interaction_phase == "shop" then
    areas[#areas + 1] = { area = root and rawget(root, "shop_vouchers"), kind = "voucher", row = 1, column = 0 }
  end
  areas[#areas + 1] = { area = root and rawget(root, "shop_booster"), kind = "pack", row = 1, column = 1 }

  for _, entry in ipairs(areas) do
    for _, card in ipairs(card_list_from_area(entry.area)) do
      sequence = sequence + 1
      local summary = summarize_shop_item(card, entry.kind)
      if summary then
        local unique_key = summary.key or summary.name or ("item::" .. tostring(sequence))
        if not seen[unique_key] then
          seen[unique_key] = true
          local transform = safe_table(card.T) or {}
          local visual_transform = safe_table(card.VT) or {}
          decorated[#decorated + 1] = {
            item = summary,
            row = entry.row or 99,
            column = entry.column or 99,
            x = safe_number(first_non_nil(transform.x, visual_transform.x)),
            y = safe_number(first_non_nil(transform.y, visual_transform.y)),
            sequence = sequence,
          }
        end
      end
    end
  end

  table.sort(decorated, function(left, right)
    if left.row ~= right.row then
      return left.row < right.row
    end

    if left.column ~= right.column then
      return left.column < right.column
    end

    local left_y = left.y or math.huge
    local right_y = right.y or math.huge
    if left_y ~= right_y then
      return left_y < right_y
    end

    local left_x = left.x or math.huge
    local right_x = right.x or math.huge
    if left_x ~= right_x then
      return left_x < right_x
    end

    return left.sequence < right.sequence
  end)

  local result = {}
  for _, entry in ipairs(decorated) do
    result[#result + 1] = entry.item
  end
  return result
end

local function collect_selected_cards(root)
  local result = {}
  local seen = {}
  local areas = {
    { area = root and rawget(root, "hand"), zone = "cards_in_hand" },
    { area = root and rawget(root, "jokers"), zone = "jokers" },
    { area = root and first_non_nil(root and rawget(root, "consumeables"), root and rawget(root, "consumables")), zone = "consumables" },
    { area = root and rawget(root, "shop_jokers"), zone = "shop_items" },
    { area = root and rawget(root, "shop_booster"), zone = "shop_items" },
    { area = root and rawget(root, "shop_vouchers"), zone = "shop_items" },
    { area = root and rawget(root, "pack_cards"), zone = "pack_contents" },
  }

  for _, entry in ipairs(areas) do
    local area = safe_table(entry.area)
    local highlighted = area and safe_table(area.highlighted) or {}
    for _, card in ipairs(highlighted) do
      local ref = build_typed_reference(card, entry.zone)
      if ref then
        local unique_key = encode_json(ref)
        push_unique(result, seen, unique_key, ref)
      end
    end
  end

  return result
end

local function collect_highlighted_card(root)
  local areas = {
    { area = root and rawget(root, "hand"), zone = "cards_in_hand" },
    { area = root and rawget(root, "jokers"), zone = "jokers" },
    { area = root and first_non_nil(root and rawget(root, "consumeables"), root and rawget(root, "consumables")), zone = "consumables" },
    { area = root and rawget(root, "shop_jokers"), zone = "shop_items" },
    { area = root and rawget(root, "shop_booster"), zone = "shop_items" },
    { area = root and rawget(root, "shop_vouchers"), zone = "shop_items" },
    { area = root and rawget(root, "pack_cards"), zone = "pack_contents" },
    { area = root and rawget(root, "deck"), zone = "cards_in_deck" },
  }

  for _, entry in ipairs(areas) do
    for _, card in ipairs(card_list_from_area(entry.area)) do
      local hover_state = safe_table(card.states) and safe_table(card.states.hover)
      if card.hovering or (hover_state and hover_state.is) then
        return build_typed_reference(card, entry.zone)
      end
    end
  end

  return nil
end

local function collect_shop_discounts(game)
  local discounts = {}
  local discount_percent = safe_number(game.discount_percent)
  if discount_percent and discount_percent ~= 0 then
    discounts[#discounts + 1] = {
      kind = "discount_percent",
      value = discount_percent,
    }
  end
  if game.shop_free then
    discounts[#discounts + 1] = {
      kind = "shop_free",
    }
  end
  return discounts
end

local function collect_pack_cards(root, game)
  return collect_cards_from_sources(
    {
      root and rawget(root, "pack_cards"),
      safe_table(game) and rawget(game, "pack_cards"),
      safe_table(game and game.current_round) and game.current_round.pack_cards,
      safe_table(game and game.current_round) and game.current_round.pack_choices,
      root and rawget(root, "pack_choices"),
    },
    EXPORT_MAX_PACK_CARDS,
    "pack_reward"
  )
end

local function collect_pack_contents(root, game, interaction_phase, shop_items)
  local cards = to_public_cards(collect_pack_cards(root, game))

  local selected_count = 0
  local pack_cards = safe_table(root and rawget(root, "pack_cards"))
  if pack_cards and pack_cards.highlighted then
    selected_count = #pack_cards.highlighted
  end

  remembered_shop_pack_key = PackContents.remembered_key(interaction_phase, shop_items, remembered_shop_pack_key)
  return PackContents.build({
    interaction_phase = interaction_phase,
    cards = cards,
    choose_limit = safe_number(game.pack_choices),
    selected_count = selected_count,
    skip_available = pack_cards ~= nil,
    shop_items = shop_items,
    remembered_pack_key = remembered_shop_pack_key,
    pack_size = safe_number(game.pack_size),
  })
end

local function collect_deck_cards(root, game)
  return collect_cards_from_sources(
    {
      root and rawget(root, "deck"),
      safe_table(game) and rawget(game, "deck"),
      safe_table(game and game.current_round) and game.current_round.deck,
    },
    EXPORT_MAX_DECK_CARDS,
    "deck"
  )
end

local function infer_phase(root, game)
  local current_state = root and root.STATE
  local states = root and root.STATES
  local blind = safe_table(game.blind) or {}
  local pack_states = states and {
    [states.TAROT_PACK] = true,
    [states.PLANET_PACK] = true,
    [states.SPECTRAL_PACK] = true,
    [states.STANDARD_PACK] = true,
    [states.BUFFOON_PACK] = true,
    [states.SMODS_BOOSTER_OPENED] = true,
  } or nil

  if states and current_state == states.BLIND_SELECT then
    return "blind_select"
  end

  if pack_states and pack_states[current_state] then
    return "pack_reward"
  end

  if states and current_state == states.SHOP then
    return "shop"
  end

  if blind.in_blind then
    return "play_hand"
  end

  local state_id = first_non_nil(root and root.STATE, game.state, game.current_round_state)
  if state_id ~= nil then
    return "state_" .. tostring(state_id)
  end

  return "unknown"
end

local function snapshot_game()
  local root = rawget(_G, "G")
  local game = root and root.GAME
  if type(game) ~= "table" then
    remembered_shop_pack_key = nil
    return nil
  end

  local hand_cards, _hand_count = collect_cards(root and root.hand, EXPORT_MAX_HAND_CARDS, "hand")
  local jokers = collect_jokers(root and root.jokers, EXPORT_MAX_JOKERS)
  local deck_cards = collect_deck_cards(root, game)
  hand_cards = to_public_cards(sort_canonical_cards(hand_cards))
  deck_cards = to_public_cards(sort_canonical_cards(deck_cards))

  local blind = safe_table(game.blind) or {}
  local current_round = safe_table(game.current_round) or {}
  local round_resets = safe_table(game.round_resets) or {}
  local consumeables_area = first_non_nil(root and rawget(root, "consumeables"), root and rawget(root, "consumables"))
  local jokers_area = safe_table(root and rawget(root, "jokers"))
  local hand_area = safe_table(root and rawget(root, "hand"))
  local interaction_phase = infer_phase(root, game)
  local consumables = collect_consumables_from_area(consumeables_area, EXPORT_MAX_CONSUMABLES)
  local shop_items = collect_shop_items(root, interaction_phase)
  local deck = summarize_deck(game)
  local stake = summarize_stake(game, root)
  local vouchers = collect_used_vouchers(game, root)
  local blinds = collect_blinds(game)
  local tags = collect_tags(game, root)
  local selected_cards = collect_selected_cards(root)
  local highlighted_card = collect_highlighted_card(root)
  local shop_discounts = collect_shop_discounts(game)
  local consumable_slots = safe_number(first_non_nil(
    safe_table(consumeables_area) and safe_table(consumeables_area.config) and consumeables_area.config.card_limit,
    safe_table(consumeables_area) and safe_table(consumeables_area.config) and consumeables_area.config.temp_limit,
    safe_table(game.starting_params) and game.starting_params.consumable_slots
  ))
  local joker_slots = safe_number(first_non_nil(
    jokers_area and safe_table(jokers_area.config) and jokers_area.config.card_limit,
    jokers_area and safe_table(jokers_area.config) and jokers_area.config.temp_limit,
    safe_table(game.starting_params) and game.starting_params.joker_slots
  ))
  local hand_size = safe_number(first_non_nil(
    hand_area and safe_table(hand_area.config) and hand_area.config.card_limit,
    hand_area and safe_table(hand_area.config) and hand_area.config.temp_limit,
    safe_table(game.starting_params) and game.starting_params.hand_size
  ))
  local pack_contents = collect_pack_contents(root, game, interaction_phase, shop_items)

  return {
    meta = {
      captured_at_seconds = now(),
      exporter_version = 2,
    },
    state = {
      source = "live_state_exporter",
      interaction_phase = interaction_phase,
      state_id = safe_number(first_non_nil(root and root.STATE, game.state, game.current_round_state)),
      ante = safe_number(round_resets.ante),
      round_count = safe_number(game.round),
      stake_id = stake and first_non_nil(stake.key, stake.index) or nil,
      money = safe_number(first_non_nil(game.dollars, game.money)),
      hands_left = safe_number(first_non_nil(current_round.hands_left, round_resets.hands, game.hands_left, game.hands)),
      discards_left = safe_number(first_non_nil(current_round.discards_left, round_resets.discards, game.discards_left, game.discards)),
      joker_slots = joker_slots,
      consumable_slots = consumable_slots,
      hand_size = hand_size,
      interest = safe_number(game.interest_amount),
      inflation = safe_number(game.inflation),
      shop_discounts = shop_discounts,
      reroll_cost = safe_number(current_round.reroll_cost),
      blind_key = BlindKey.derive(interaction_phase, blinds),
      blinds = blinds,
      deck_key = deck and deck.key or nil,
      cards_in_deck = deck_cards,
      vouchers = vouchers,
      score = {
        current = safe_number(first_non_nil(game.chips, game.current_round_score, game.score)),
        target = safe_number(first_non_nil(blind.chips, game.score_to_beat, game.target_score)),
      },
      cards_in_hand = hand_cards,
      jokers = jokers,
      consumables = consumables,
      shop_items = shop_items,
      selected_cards = selected_cards,
      highlighted_card = highlighted_card,
      pack_contents = pack_contents,
      tags = tags,
      notes = {
        "exporter=live_state_exporter",
      },
    },
  }
end

local function make_signature(snapshot)
  return Signature.make(snapshot)
end

local function ensure_export_dir()
  if love and love.filesystem and love.filesystem.createDirectory then
    pcall(love.filesystem.createDirectory, EXPORT_DIR)
  end
end

local function write_snapshot(payload)
  ensure_export_dir()
  if love and love.filesystem and love.filesystem.write then
    local ok = pcall(love.filesystem.write, EXPORT_PATH, payload)
    if ok then
      return true
    end
  end
  return false
end

local Exporter = {
  last_write_at = 0,
  last_signature = nil,
}

function Exporter:flush(reason)
  local snapshot = snapshot_game()
  if not snapshot then
    return false
  end

  local signature = make_signature(snapshot)
  local current_time = now()
  if signature == self.last_signature and (current_time - self.last_write_at) < EXPORT_INTERVAL_SECONDS then
    return false
  end

  snapshot.meta.reason = reason or "update"
  local payload = encode_json(snapshot)
  if write_snapshot(payload) then
    self.last_write_at = current_time
    self.last_signature = signature
    return true
  end

  return false
end

function Exporter:tick(reason)
  local current_time = now()
  if (current_time - self.last_write_at) < EXPORT_INTERVAL_SECONDS and reason ~= "startup" then
    return false
  end
  return self:flush(reason)
end

local function wrap_update(target, method_name, reason)
  if type(target) ~= "table" or type(target[method_name]) ~= "function" then
    return false
  end
  if target["__live_state_exporter_wrapped_" .. method_name] then
    return false
  end

  local original = target[method_name]
  target["__live_state_exporter_wrapped_" .. method_name] = true
  target[method_name] = function(...)
    local result = { original(...) }
    Exporter:tick(reason)
    return unpack_fn(result)
  end
  return true
end

local function install_hooks()
  if not wrap_update(rawget(_G, "love"), "update", "love.update") then
    wrap_update(rawget(_G, "Game"), "update", "Game.update")
  end
end

install_hooks()
Exporter:tick("startup")
