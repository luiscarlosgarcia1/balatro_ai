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
local EXPORT_MAX_PACKS = 4
local EXPORT_MAX_STRING = 80
local unpack_fn = table.unpack or unpack

local function load_signature_module()
  local mod = rawget(_G, "SMODS") and SMODS.current_mod
  local mod_path = mod and mod.path
  if mod_path and rawget(_G, "NFS") and type(NFS.read) == "function" then
    local chunk, err = load(
      NFS.read(mod_path .. "signature.lua"),
      '=[SMODS live_state_exporter "signature.lua"]'
    )
    assert(chunk, err)
    return chunk()
  end
  error("live_state_exporter could not load signature.lua")
end

local Signature = load_signature_module()

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

local function card_list_from_area(area)
  local area_table = safe_table(area)
  if not area_table then
    return {}
  end
  return safe_table(area_table.cards) or {}
end

local function summarize_card(card, area_name)
  if type(card) ~= "table" then
    return nil
  end

  local base = safe_table(card.base) or {}
  local save_fields = safe_table(card.save_fields) or {}
  local ability = safe_table(card.ability) or {}
  local edition = safe_table(card.edition) or {}

  local enhancement = safe_tostring(first_non_nil(ability.effect, card.enhancement))
  if enhancement == "Base" then
    enhancement = nil
  end

  local modifiers = {}
  local function add_modifier(name, value, default)
    local formatted = format_modifier(name, value, default)
    if formatted then
      modifiers[#modifiers + 1] = formatted
    end
  end

  add_modifier("bonus", first_non_nil(ability.bonus, card.bonus), 0)
  add_modifier("mult", first_non_nil(ability.mult, card.mult), 0)
  add_modifier("x_mult", first_non_nil(ability.x_mult, card.x_mult), 1)
  add_modifier("x_chips", first_non_nil(ability.x_chips, card.x_chips), 1)
  add_modifier("perma_bonus", first_non_nil(ability.perma_bonus, card.perma_bonus), 0)
  add_modifier("perma_mult", first_non_nil(ability.perma_mult, card.perma_mult), 0)
  add_modifier("perma_x_mult", first_non_nil(ability.perma_x_mult, card.perma_x_mult), 0)
  add_modifier("perma_x_chips", first_non_nil(ability.perma_x_chips, card.perma_x_chips), 0)
  add_modifier("h_mult", ability.h_mult, 0)
  add_modifier("h_chips", ability.h_chips, 0)
  add_modifier("h_x_mult", ability.h_x_mult, 0)
  add_modifier("h_x_chips", ability.h_x_chips, 1)
  add_modifier("h_dollars", ability.h_dollars, 0)
  add_modifier("p_dollars", ability.p_dollars, 0)
  add_modifier("t_mult", ability.t_mult, 0)
  add_modifier("t_chips", ability.t_chips, 0)
  add_modifier("d_size", ability.d_size, 0)
  add_modifier("h_size", ability.h_size, 0)

  if first_non_nil(card.debuffed, card.debuff) then
    modifiers[#modifiers + 1] = "debuffed"
  end

  if ability.played_this_ante then
    modifiers[#modifiers + 1] = "played_this_ante"
  end

  return {
    area = area_name,
    code = safe_tostring(first_non_nil(save_fields.card, card.card_key, card.key)),
    name = trim_text(
      safe_tostring(first_non_nil(base.name, card.label, ability.name, card.name, card.key)) or "card",
      EXPORT_MAX_STRING
    ),
    facing = safe_tostring(card.facing),
    enhancement = enhancement,
    edition = safe_tostring(first_non_nil(edition.type, edition.key, edition.name)),
    seal = safe_tostring(first_non_nil(card.seal, base.seal)),
    debuffed = safe_bool(first_non_nil(card.debuffed, card.debuff)),
    modifiers = modifiers,
  }
end

local function summarize_joker(card)
  if type(card) ~= "table" then
    return nil
  end

  local ability = safe_table(card.ability) or {}
  local edition = safe_table(card.edition) or {}
  local modifiers = {}
  local function add_modifier(name, value, default)
    local formatted = format_modifier(name, value, default)
    if formatted then
      modifiers[#modifiers + 1] = formatted
    end
  end

  add_modifier("mult", first_non_nil(ability.mult, card.mult), 0)
  add_modifier("chips", first_non_nil(ability.chips, card.chips), 0)
  add_modifier("x_mult", first_non_nil(ability.x_mult, card.x_mult), 1)
  add_modifier("x_chips", first_non_nil(ability.x_chips, card.x_chips), 1)
  add_modifier("dollars", first_non_nil(ability.dollars, card.dollars), 0)
  add_modifier("extra", ability.extra, 0)

  for _, flag in ipairs({ "eternal", "perishable", "rental", "pinned" }) do
    if ability[flag] or card[flag] then
      modifiers[#modifiers + 1] = flag
    end
  end

  if first_non_nil(card.debuffed, card.debuff) then
    modifiers[#modifiers + 1] = "debuffed"
  end

  local name = safe_tostring(first_non_nil(card.label, ability.name, ability.key, card.name, card.key))
  if not name then
    return nil
  end

  return {
    name = trim_text(name, EXPORT_MAX_STRING),
    key = safe_tostring(first_non_nil(ability.key, card.key)),
    edition = safe_tostring(first_non_nil(edition.type, edition.key, edition.name)),
    debuffed = safe_bool(first_non_nil(card.debuffed, card.debuff)),
    modifiers = modifiers,
  }
end

local function summarize_voucher(value, key_hint)
  local voucher = safe_table(value) or {}
  local key = safe_tostring(first_non_nil(voucher.key, key_hint))
  local name = safe_tostring(first_non_nil(voucher.name, voucher.label, key))
  if not name and not key then
    return nil
  end
  return {
    name = trim_text(name or key or "voucher", EXPORT_MAX_STRING),
    key = key,
  }
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

local function normalize_consumable_kind(raw_kind, fallback_key)
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
  local name = safe_tostring(first_non_nil(ability.name, card.label, card.name, key))
  if not kind or not name then
    return nil
  end

  return {
    kind = kind,
    name = trim_text(name, EXPORT_MAX_STRING),
    key = key,
    cost = safe_number(first_non_nil(card.cost, card.base_cost, ability.cost)),
  }
end

local function summarize_tag(value, key_hint)
  local tag = safe_table(value) or {}
  local key = safe_tostring(first_non_nil(tag.key, key_hint))
  local name = safe_tostring(first_non_nil(tag.name, tag.label, key))
  if not name and not key then
    return nil
  end
  return {
    name = trim_text(name or key or "tag", EXPORT_MAX_STRING),
    key = key,
  }
end

local function summarize_booster_pack(card)
  if type(card) ~= "table" then
    return nil
  end

  local ability = safe_table(card.ability) or {}
  local key = safe_tostring(first_non_nil(ability.key, card.key))
  local set_name = safe_tostring(first_non_nil(ability.set, card.set))
  local kind = nil
  if set_name then
    kind = string.lower(set_name)
  end

  local name = safe_tostring(first_non_nil(ability.name, card.label, card.name, key))
  if not name and not key then
    return nil
  end

  return {
    name = trim_text(name or key or "pack", EXPORT_MAX_STRING),
    key = key,
    kind = kind,
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

local function collect_jokers(area, limit)
  local result = {}
  local count = 0
  for _, card in ipairs(card_list_from_area(area)) do
    count = count + 1
    if #result < limit then
      local summary = summarize_joker(card)
      if summary then
        result[#result + 1] = summary
      end
    end
  end
  return result, count
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
        push_unique(result, seen, summary.key or summary.name, summary)
      end
    end
  end

  local current_round = safe_table(game.current_round) or {}
  local current_round_vouchers = current_round.voucher
  if current_round_vouchers then
    local voucher_entries = collect_value_entries(
      current_round_vouchers,
      EXPORT_MAX_VOUCHERS,
      function(item, key_hint)
        if type(item) == "table" then
          return summarize_voucher(item, key_hint)
        end
        return summarize_voucher(nil, item or key_hint)
      end
    )
    for _, summary in ipairs(voucher_entries) do
      if #result >= EXPORT_MAX_VOUCHERS then
        break
      end
      push_unique(result, seen, summary.key or summary.name, summary)
    end
  end

  local round_resets = safe_table(game.round_resets) or {}
  local round_reset_vouchers = round_resets.vouchers or round_resets.voucher_choices
  if round_reset_vouchers then
    local voucher_entries = collect_value_entries(
      round_reset_vouchers,
      EXPORT_MAX_VOUCHERS,
      function(item, key_hint)
        if type(item) == "table" then
          return summarize_voucher(item, key_hint)
        end
        return summarize_voucher(nil, item or key_hint)
      end
    )
    for _, summary in ipairs(voucher_entries) do
      if #result >= EXPORT_MAX_VOUCHERS then
        break
      end
      push_unique(result, seen, summary.key or summary.name, summary)
    end
  end

  for _, card in ipairs(card_list_from_area(root and root.vouchers)) do
    if #result >= EXPORT_MAX_VOUCHERS then
      break
    end
    local summary = summarize_voucher(safe_table(card.ability) or card, safe_tostring(first_non_nil(card.key, safe_table(card.ability) and card.ability.key)))
    if summary then
      push_unique(result, seen, summary.key or summary.name, summary)
    end
  end
  return result
end

local function collect_tags(game, root)
  local result = {}
  local seen = {}

  local function add_tag(value, key_hint)
    if #result >= EXPORT_MAX_TAGS then
      return
    end
    local summary = summarize_tag(value, key_hint)
    if summary then
      push_unique(result, seen, summary.key or summary.name, summary)
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

  local round_resets = safe_table(game.round_resets) or {}
  local blind_tags = safe_table(round_resets.blind_tags) or {}
  for _, key in pairs(blind_tags) do
    add_tag(nil, key)
  end

  return result
end

local function collect_booster_packs(game, root)
  local result = {}
  local seen = {}
  local candidates = {
    safe_table(game.current_round) and game.current_round.booster_packs,
    safe_table(game.current_round) and game.current_round.pack_choices,
    safe_table(game.current_round) and game.current_round.shop_boosters,
    safe_table(game.current_round) and game.current_round.shop_booster,
    game and rawget(game, "booster_packs"),
    root and rawget(root, "shop_booster"),
    root and rawget(root, "shop_boosters"),
    game and rawget(game, "shop_booster"),
    game and rawget(game, "shop_boosters"),
  }

  for _, candidate in ipairs(candidates) do
    if candidate then
      local entries = card_list_from_area(candidate)
      if #entries == 0 and is_array(candidate) then
        entries = candidate
      elseif #entries == 0 and type(candidate) == "table" and not candidate.cards then
        entries = { candidate }
      end

      for _, card in ipairs(entries) do
        if #result >= EXPORT_MAX_PACKS then
          return result
        end
        local summary = summarize_booster_pack(card)
        if summary then
          push_unique(result, seen, summary.key or summary.name, summary)
        end
      end
    end
  end

  return result
end

local function collect_blind_choices(game)
  local result = {}
  local round_resets = safe_table(game.round_resets) or {}
  local blind_choices = safe_table(round_resets.blind_choices) or {}
  local blind_states = safe_table(round_resets.blind_states) or {}
  local blind_tags = safe_table(round_resets.blind_tags) or {}
  local slot_order = { "Small", "Big", "Boss" }
  local seen = {}

  for _, slot in ipairs(slot_order) do
    local key = safe_tostring(blind_choices[slot])
    if key then
      result[#result + 1] = {
        slot = slot,
        key = key,
        state = safe_tostring(blind_states[slot]),
        tag = safe_tostring(blind_tags[slot]),
      }
      seen[slot] = true
    end
  end

  for slot, key in pairs(blind_choices) do
    if not seen[slot] then
      result[#result + 1] = {
        slot = safe_tostring(slot),
        key = safe_tostring(key),
        state = safe_tostring(blind_states[slot]),
        tag = safe_tostring(blind_tags[slot]),
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
  local item_cost = safe_number(first_non_nil(card.cost, card.base_cost, ability.cost))

  if area_kind == "voucher" then
    local voucher = summarize_voucher(ability, safe_tostring(first_non_nil(card.key, ability.key)))
    if voucher then
      return {
        kind = "voucher",
        name = voucher.name,
        key = voucher.key,
        cost = item_cost,
      }
    end
  end

  if area_kind == "pack" then
    local pack = summarize_booster_pack(card)
    if pack then
      return {
        kind = "pack",
        name = pack.name,
        key = pack.key,
        cost = pack.cost,
      }
    end
  end

  local consumable = summarize_consumable(card)
  if consumable then
    return {
      kind = "consumable",
      name = consumable.name,
      key = consumable.key,
      cost = consumable.cost,
    }
  end

  local joker = summarize_joker(card)
  if joker then
    return {
      kind = "joker",
      name = joker.name,
      key = joker.key,
      cost = item_cost,
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
  }
end

local function collect_shop_items(root)
  local result = {}
  local seen = {}
  local areas = {
    { area = root and rawget(root, "shop_jokers"), kind = "joker" },
    { area = root and rawget(root, "shop_vouchers"), kind = "voucher" },
    { area = root and rawget(root, "shop_booster"), kind = "pack" },
  }

  for _, entry in ipairs(areas) do
    for _, card in ipairs(card_list_from_area(entry.area)) do
      local summary = summarize_shop_item(card, entry.kind)
      if summary then
        local unique_key = (summary.kind or "item") .. "::" .. (summary.key or summary.name)
        push_unique(result, seen, unique_key, summary)
      end
    end
  end

  return result
end

local function collect_shop_packs(root)
  local result = {}
  local seen = {}
  for _, card in ipairs(card_list_from_area(root and rawget(root, "shop_booster"))) do
    if #result >= EXPORT_MAX_PACKS then
      break
    end
    local summary = summarize_booster_pack(card)
    if summary then
      push_unique(result, seen, summary.key or summary.name, summary)
    end
  end
  return result
end

local function collect_skip_tag_claim(root, game)
  local round_resets = safe_table(game.round_resets) or {}
  local blind_states = safe_table(round_resets.blind_states) or {}
  local blind_tags = safe_table(round_resets.blind_tags) or {}
  local last_claimed = nil

  for _, slot in ipairs({ "Small", "Big", "Boss" }) do
    if blind_states[slot] == "Skipped" then
      last_claimed = summarize_tag(nil, blind_tags[slot])
    end
  end

  if last_claimed then
    return true, last_claimed
  end
  return false, nil
end

local function infer_phase(root, game)
  local current_state = root and root.STATE
  local states = root and root.STATES
  local blind = safe_table(game.blind) or {}
  local pack_state_map = states and {
    [states.TAROT_PACK] = "tarot_pack",
    [states.PLANET_PACK] = "planet_pack",
    [states.SPECTRAL_PACK] = "spectral_pack",
    [states.STANDARD_PACK] = "standard_pack",
    [states.BUFFOON_PACK] = "buffoon_pack",
    [states.SMODS_BOOSTER_OPENED] = "modded_booster_pack",
  } or nil

  if states and current_state == states.BLIND_SELECT then
    return "blind_select", nil
  end

  if pack_state_map and pack_state_map[current_state] then
    return "pack_reward", pack_state_map[current_state]
  end

  if states and current_state == states.SHOP then
    return "shop", nil
  end

  if blind.in_blind then
    return "play_hand", nil
  end

  local state_id = first_non_nil(root and root.STATE, game.state, game.current_round_state)
  if state_id ~= nil then
    return "state_" .. tostring(state_id), nil
  end

  return "unknown", nil
end

local function snapshot_game()
  local root = rawget(_G, "G")
  local game = root and root.GAME
  if type(game) ~= "table" then
    return nil
  end

  local hand_cards, hand_count = collect_cards(root and root.hand, EXPORT_MAX_HAND_CARDS, "hand")
  local jokers, joker_count = collect_jokers(root and root.jokers, EXPORT_MAX_JOKERS)

  local blind = safe_table(game.blind) or {}
  local current_round = safe_table(game.current_round) or {}
  local round_resets = safe_table(game.round_resets) or {}
  local consumeables_area = first_non_nil(root and rawget(root, "consumeables"), root and rawget(root, "consumables"))
  local consumables_inventory = collect_consumables_from_area(consumeables_area, EXPORT_MAX_CONSUMABLES)
  local consumables_shop = collect_consumables_from_area(root and rawget(root, "shop_jokers"), EXPORT_MAX_CONSUMABLES)
  local shop_items = collect_shop_items(root)
  local shop_packs = collect_shop_packs(root)
  local deck = summarize_deck(game)
  local stake = summarize_stake(game, root)
  local vouchers = collect_used_vouchers(game, root)
  local tags = collect_tags(game, root)
  local booster_packs = collect_booster_packs(game, root)
  local blind_choices = collect_blind_choices(game)
  local skip_tag_claimed, skip_tag = collect_skip_tag_claim(root, game)
  local consumable_capacity = safe_number(first_non_nil(
    safe_table(consumeables_area) and safe_table(consumeables_area.config) and consumeables_area.config.card_limit,
    safe_table(consumeables_area) and safe_table(consumeables_area.config) and consumeables_area.config.temp_limit,
    safe_table(game.starting_params) and game.starting_params.consumable_slots
  ))
  local phase, interaction_phase = infer_phase(root, game)

  return {
    meta = {
      captured_at_seconds = now(),
      exporter_version = 2,
    },
    state = {
      source = "live_state_exporter",
      phase = phase,
      interaction_phase = interaction_phase,
      state_id = safe_number(first_non_nil(root and root.STATE, game.state, game.current_round_state)),
      ante = safe_number(round_resets.ante),
      round_count = safe_number(game.round),
      stake = stake and stake.name or nil,
      stake_key = stake and stake.key or nil,
      stake_index = stake and stake.index or nil,
      money = safe_number(first_non_nil(game.dollars, game.money)),
      hands_left = safe_number(first_non_nil(current_round.hands_left, round_resets.hands, game.hands_left, game.hands)),
      discards_left = safe_number(first_non_nil(current_round.discards_left, round_resets.discards, game.discards_left, game.discards)),
      reroll_cost = safe_number(current_round.reroll_cost),
      blind_name = safe_tostring(first_non_nil(blind.name, game.blind_name)),
      blind_key = safe_tostring(first_non_nil(blind.config_blind, blind.key, game.blind_key)),
      blind_choices = blind_choices,
      deck = deck,
      vouchers = vouchers,
      current_score = safe_number(first_non_nil(game.chips, game.current_round_score, game.score)),
      score_to_beat = safe_number(first_non_nil(blind.chips, game.score_to_beat, game.target_score)),
      cards_in_hand = hand_count,
      jokers_count = joker_count,
      jokers = jokers,
      hand_cards = hand_cards,
      consumables_inventory = consumables_inventory,
      consumables_shop = consumables_shop,
      consumable_capacity = consumable_capacity,
      shop_items = shop_items,
      shop_packs = shop_packs,
      tags = tags,
      booster_packs = booster_packs,
      skip_tag_claimed = skip_tag_claimed,
      skip_tag = skip_tag,
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
