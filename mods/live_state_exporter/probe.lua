local probe = {}

local dir = "ai"
local path = dir .. "/live_state_probe.json"
local ENABLED = false

local load_module = rawget(_G, "__live_state_exporter_load_module")
if not load_module then
  local mod = rawget(_G, "SMODS") and SMODS.current_mod
  local mod_path = mod and mod.path
  local nfs = rawget(_G, "NFS")
  if mod_path and nfs and type(nfs.read) == "function" then
    local chunk, err = load(
      nfs.read(mod_path .. "shared/loader.lua"),
      '=[SMODS live_state_exporter "shared/loader.lua"]'
    )
    assert(chunk, err)
    load_module = chunk().load
  else
    load_module = dofile("mods/live_state_exporter/shared/loader.lua").load
  end
  _G.__live_state_exporter_load_module = load_module
end

local out = load_module("out.lua")
local values = load_module("shared/values.lua")
local as_table = values.as_table
local to_number = values.to_number

local last_signature = nil

local function sorted_keys(value)
  local keys = {}
  for key, _ in pairs(value) do
    keys[#keys + 1] = tostring(key)
  end
  table.sort(keys)
  return keys
end

local function capture_value(value)
  local kind = type(value)
  local captured = {
    kind = kind,
    coerced_number = to_number(value),
  }

  if kind == "nil" or kind == "number" or kind == "string" or kind == "boolean" then
    captured.value = value
    return captured
  end

  if kind ~= "table" then
    captured.value = tostring(value)
    return captured
  end

  captured.value = tostring(value)
  captured.keys = sorted_keys(value)

  local config = as_table(value.config)
  local text_source = config or value
  if text_source.text ~= nil then
    captured.text = tostring(text_source.text)
  end
  if value.string ~= nil then
    captured.string = tostring(value.string)
  end
  if value.key ~= nil then
    captured.key = value.key
  end
  if value.chips ~= nil then
    captured.chips = capture_value(value.chips)
  end
  if value.mult ~= nil then
    captured.mult = capture_value(value.mult)
  end
  if value.level ~= nil then
    captured.level = capture_value(value.level)
  end
  if value.played ~= nil then
    captured.played = capture_value(value.played)
  end
  if value.played_this_round ~= nil then
    captured.played_this_round = capture_value(value.played_this_round)
  end

  return captured
end

local function capture_hand(game, hand_name)
  local hands = as_table(game and game.hands)
  local hand = hands and as_table(hands[hand_name])
  if not hand then
    return nil
  end

  return {
    level = capture_value(hand.level),
    chips = capture_value(hand.chips),
    mult = capture_value(hand.mult),
    played = capture_value(hand.played),
    played_this_round = capture_value(hand.played_this_round),
  }
end

local function capture_probe(root)
  root = as_table(root) or {}

  local game = as_table(root.GAME) or {}
  local blind = as_table(game.blind) or {}
  local previous_round = as_table(game.previous_round) or {}
  local hand_text = as_table(root.hand_text_area) or {}

  return {
    state = {
      root_STATE = capture_value(root.STATE),
      game_state = capture_value(game.state),
      current_round_state = capture_value(game.current_round_state),
    },
    money = {
      game_dollars = capture_value(game.dollars),
      game_money = capture_value(game.money),
      previous_round_dollars = capture_value(previous_round.dollars),
    },
    score = {
      game_chips = capture_value(game.chips),
      game_current_round_score = capture_value(game.current_round_score),
      game_score = capture_value(game.score),
      blind_chips = capture_value(blind.chips),
      game_score_to_beat = capture_value(game.score_to_beat),
      game_target_score = capture_value(game.target_score),
    },
    hud = {
      chips = capture_value(hand_text.chips),
      mult = capture_value(hand_text.mult),
      game_chips = capture_value(hand_text.game_chips),
      blind_chips = capture_value(hand_text.blind_chips),
      handname = capture_value(hand_text.handname),
      hand_level = capture_value(hand_text.hand_level),
    },
    hands = {
      ["High Card"] = capture_hand(game, "High Card"),
      Pair = capture_hand(game, "Pair"),
      Flush = capture_hand(game, "Flush"),
    },
  }
end

local function write_body(body)
  local love = rawget(_G, "love")
  local filesystem = love and love.filesystem
  if type(filesystem) ~= "table" then
    return false
  end
  if type(filesystem.createDirectory) == "function" then
    local ok = pcall(filesystem.createDirectory, dir)
    if not ok then
      return false
    end
  end
  if type(filesystem.write) ~= "function" then
    return false
  end
  local ok = pcall(filesystem.write, path, body)
  return ok
end

function probe.path()
  return path
end

function probe.capture(root)
  return capture_probe(root)
end

function probe.tick(root)
  if not ENABLED then
    return false
  end

  local payload = capture_probe(root)
  local signature = out.make_signature(payload)
  if signature == last_signature then
    return false
  end

  local body = out.encode_json(payload)
  local wrote = write_body(body)
  if not wrote then
    return false
  end

  last_signature = signature
  return true
end

return probe
