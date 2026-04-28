local stub = require("headless.love_stub")
local actions = require("headless.actions")
local start_run = require("headless.start_run")
local util = require("headless.util")

local tick_once          = util.tick_once
local current_state_name = util.current_state_name
local wait_until         = util.wait_until

-- This module boots a headless Balatro instance, drives a complete run,
-- and exchanges JSON messages with a Python controller over stdin/stdout.
--
-- Boot and startup:
--   DEFAULT_BOOT_TICKS (10) frames are ticked after love.load to stabilise
--   the engine.  start_run.start_run() waits for Balatro globals, configures
--   the deck and seed, and calls G:start_run() — it returns immediately after
--   without advancing the game.  Once both complete, emits {type="ready"} on
--   stdout and the main loop takes over from the first state.
--
-- Main loop:
--   Repeatedly waits up to DEFAULT_MAX_TICKS (1800) frames for an actionable
--   state (BLIND_SELECT, ROUND_EVAL, SHOP, SELECTING_HAND, or GAME_OVER).
--     BLIND_SELECT   -> automatically selects the current blind; ticks 2 frames.
--     ROUND_EVAL     -> automatically cashes out; ticks 2 frames.
--     SHOP           -> automatically leaves the shop; ticks 2 frames.
--     SELECTING_HAND -> emits {type="state", state=<snapshot>} and blocks on
--                       stdin until a valid action is received.
--     GAME_OVER      -> emits {type="done", score=<chips>, ante=<ante>,
--                       round=<round>} and returns.
--
-- Stdin protocol (one JSON object per line):
--   Required fields: "type" ("play" or "discard") and "cards" (array of
--   integer 1-based hand indices).
--   Example: {"type":"play","cards":[1,3,5]}
--
-- Stdout protocol (one JSON object per line):
--   {type="ready"}                           emitted once after boot
--   {type="state", state={...}}              emitted each SELECTING_HAND turn
--   {type="done", score=N, ante=N, round=N}  emitted on GAME_OVER
--   {type="error", message="..."}            emitted on recoverable parse or
--                                            action errors during SELECTING_HAND;
--                                            the loop retries and waits for the
--                                            next action line
--
-- Fatal errors:
--   Any unhandled error (timeout, boot failure, unknown game state, stdin
--   closed) is caught by the top-level pcall, emits {type="error",
--   message="..."} on stdout, and exits the process with code 1.

-- -----------------------------------------------
--
--               CONSTANTS
--
-- -----------------------------------------------

local DEFAULT_BOOT_TICKS = 10
local DEFAULT_MAX_TICKS = 1800

local STRING_ESCAPE_REPLACEMENTS = {
    ['"']  = '\\"',
    ["\\"] = "\\\\",
    ["\b"] = "\\b",
    ["\f"] = "\\f",
    ["\n"] = "\\n",
    ["\r"] = "\\r",
    ["\t"] = "\\t",
}

local ACTIONABLE_STATES = {
    BLIND_SELECT = true,
    GAME_OVER = true,
    ROUND_EVAL = true,
    SELECTING_HAND = true,
    SHOP = true,
}

-- -----------------------------------------------
--
--               TICK
--
-- -----------------------------------------------

local function tick(frames)
    for _ = 1, frames do
        tick_once()
    end
end

-- -----------------------------------------------
--
--               JSON
--
-- -----------------------------------------------

local function is_array(value)
    if type(value) ~= "table" then
        return false
    end

    local count = 0
    for key in pairs(value) do
        if type(key) ~= "number" or key < 1 or key ~= math.floor(key) then
            return false
        end
        count = count + 1
    end

    for i = 1, count do
        if value[i] == nil then
            return false
        end
    end

    return true
end

local function escape_string(value)
    return (tostring(value):gsub('[%z\1-\31\\"]', function(char)
        return STRING_ESCAPE_REPLACEMENTS[char] or string.format("\\u%04x", char:byte())
    end))
end

local function json_encode(value)
    local value_type = type(value)

    if value_type == "nil" then
        return "null"
    end

    if value_type == "number" then
        if value ~= value or value == math.huge or value == -math.huge then
            error("Cannot encode non-finite number as JSON")
        end
        return tostring(value)
    end

    if value_type == "boolean" then
        return value and "true" or "false"
    end

    if value_type == "string" then
        return '"' .. escape_string(value) .. '"'
    end

    if value_type ~= "table" then
        error(string.format("Unsupported JSON value type %q", value_type))
    end

    if is_array(value) then
        local items = {}
        for index = 1, #value do
            items[index] = json_encode(value[index])
        end
        return "[" .. table.concat(items, ",") .. "]"
    end

    local keys = {}
    for key in pairs(value) do
        if type(key) ~= "string" then
            error("JSON object keys must be strings")
        end
        keys[#keys + 1] = key
    end
    table.sort(keys)

    local items = {}
    for index, key in ipairs(keys) do
        items[index] = '"' .. escape_string(key) .. '":' .. json_encode(value[key])
    end
    return "{" .. table.concat(items, ",") .. "}"
end

local function print_json(value)
    io.write(json_encode(value), "\n")
    io.stdout:flush()
end

-- -----------------------------------------------
--
--               GAME FLOW
--
-- -----------------------------------------------

local function boot_game()
    local main_path = stub.state.source_root .. "/main.lua"
    local chunk, err = loadfile(main_path)
    if not chunk then
        error("Could not load main.lua: " .. tostring(err))
    end

    chunk()

    if type(love) == "table" and type(love.load) == "function" then
        love.load({})
    end

    tick(DEFAULT_BOOT_TICKS)
end

local function wait_for_actionable_state(label)
    wait_until(function()
        return ACTIONABLE_STATES[current_state_name()] == true
    end, DEFAULT_MAX_TICKS, label)
end

local function select_current_blind()
    wait_until(function()
        return current_state_name() == "BLIND_SELECT"
            and G.blind_select ~= nil
            and G.blind_prompt_box ~= nil
            and G.GAME ~= nil
            and G.GAME.blind_on_deck ~= nil
    end, DEFAULT_MAX_TICKS, "blind select UI")

    local blind_slot = G.GAME.blind_on_deck or "Small"
    local blind_choices = G.GAME.round_resets and G.GAME.round_resets.blind_choices or nil
    local blind_key = blind_choices and blind_choices[blind_slot] or nil
    local blind = G.P_BLINDS and blind_key and G.P_BLINDS[blind_key] or nil

    if not blind then
        error(string.format("Could not resolve blind for slot %q", tostring(blind_slot)))
    end

    G.FUNCS.select_blind({
        config = {
            ref_table = blind,
        }
    })

    wait_until(function()
        return current_state_name() ~= "BLIND_SELECT"
    end, DEFAULT_MAX_TICKS, "blind selection start")

    wait_for_actionable_state("blind selection resolution")
    tick(2)
end

local function cash_out_round()
    wait_until(function()
        return current_state_name() == "ROUND_EVAL" and G.round_eval ~= nil
    end, DEFAULT_MAX_TICKS, "round evaluation")

    G.FUNCS.cash_out({
        config = {},
    })

    wait_until(function()
        local name = current_state_name()
        return name == "SHOP" or name == "GAME_OVER"
    end, DEFAULT_MAX_TICKS, "cash out")

    tick(2)
end

local function leave_shop()
    wait_until(function()
        return current_state_name() == "SHOP" and G.shop ~= nil
    end, DEFAULT_MAX_TICKS, "shop")

    G.FUNCS.toggle_shop({})

    wait_until(function()
        local name = current_state_name()
        return name == "BLIND_SELECT" or name == "GAME_OVER"
    end, DEFAULT_MAX_TICKS, "leave shop")

    tick(2)
end

-- -----------------------------------------------
--
--               PROTOCOL
--
-- -----------------------------------------------

local function parse_cards(raw_cards)
    if raw_cards == nil then
        error('Missing "cards"')
    end

    local cards = {}
    for token in raw_cards:gmatch("[^,%s]+") do
        local index = tonumber(token)
        if index == nil or index ~= math.floor(index) then
            error(string.format('Invalid card index %q', tostring(token)))
        end
        cards[#cards + 1] = index
    end

    return cards
end

local function parse_action_line(line)
    if type(line) ~= "string" or line == "" then
        error("Expected a JSON action line")
    end

    local action_type = line:match('%"type%"%s*:%s*%"([^"]+)"')
    if action_type == nil then
        error('Missing "type"')
    end

    local raw_cards = line:match('%"cards%"%s*:%s*%[(.-)%]')
    return {
        type = action_type,
        cards = parse_cards(raw_cards),
    }
end

local function read_action()
    local line = io.read("*l")
    if line == nil then
        return nil
    end

    return parse_action_line(line)
end

local function execute_action(action)
    if type(action) ~= "table" then
        error("Action must be a table")
    end

    if action.type ~= "play" and action.type ~= "discard" then
        error(string.format('Unsupported action type %q', tostring(action.type)))
    end

    actions.select_cards(action.cards)

    if action.type == "play" then
        actions.play_hand()
        return
    end

    actions.discard()
end

local function handle_selecting_hand(state)
    print_json({
        type = "state",
        state = state,
    })

    while true do
        local ok, action_or_err = pcall(read_action)
        if not ok then
            print_json({
                type = "error",
                message = tostring(action_or_err),
            })
        elseif action_or_err == nil then
            error("stdin closed while waiting for an action")
        else
            local action_ok, action_err = pcall(execute_action, action_or_err)
            if action_ok then
                return
            end

            print_json({
                type = "error",
                message = tostring(action_err),
            })
        end
    end
end

-- -----------------------------------------------
--
--               RUN
--
-- -----------------------------------------------

local function run()
    boot_game()
    start_run.start_run()
    print_json({ type = "ready" })

    while true do
        wait_for_actionable_state("main loop")
        local state = actions.get_state()

        if state.state == "GAME_OVER" then
            print_json({
                type = "done",
                score = tonumber(G and G.GAME and G.GAME.chips) or 0,
                ante = G and G.GAME and G.GAME.round_resets and G.GAME.round_resets.ante or nil,
                round = G and G.GAME and G.GAME.round or nil,
            })
            return
        end

        if state.state == "BLIND_SELECT" then
            select_current_blind()
        elseif state.state == "ROUND_EVAL" then
            cash_out_round()
        elseif state.state == "SHOP" then
            leave_shop()
        elseif state.state == "SELECTING_HAND" then
            handle_selecting_hand(state)
        else
            error("Unhandled state " .. tostring(state.state))
        end
    end
end

local ok, err = pcall(run)
if not ok then
    print_json({
        type = "error",
        message = tostring(err),
    })
    os.exit(1)
end
