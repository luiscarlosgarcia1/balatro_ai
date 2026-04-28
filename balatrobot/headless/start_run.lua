local util = require("headless.util")

local wait_until = util.wait_until

-- This module waits for Balatro globals to be ready, resolves the requested
-- deck, and calls G:start_run() to begin a run.  It is called once from
-- run.lua after boot_game() and returns immediately without advancing the game.
--
-- Boot wait:
--   Waits up to 120 ticks for G, G.FUNCS, G.start_run, and G.delete_run to
--   all be non-nil before proceeding.  Errors with a timeout message if they
--   do not appear in time.
--
-- Constants:
--   DEFAULT_SEED  = "HEADLESS" — used when opts.seed is nil.
--   DEFAULT_DECK  = "Red Deck" — used when opts.deck is nil.
--   DEFAULT_STAKE = 1          — hardcoded; not overridable via opts.
--
-- Deck resolution:
--   resolve_deck() first tries G.P_CENTERS[name] (must have .set == "Back").
--   If that misses, it falls back to the global get_deck_from_name(name).
--   Errors if neither lookup succeeds.
--
-- Run startup sequence:
--   1. prime_selected_back() initialises G.GAME (via G:init_game_object() if
--      needed) and sets viewed_back, selected_back, viewed_back_key, and
--      selected_back_key to match the resolved deck center.
--   2. G:delete_run() is called to clear any prior run state before starting.
--   3. G:start_run({seed, stake}) is called with the resolved seed and
--      DEFAULT_STAKE.
--
-- Shared helpers (tick_once, current_state_name, wait_until) live in
-- headless/util.lua and are used by both this module and run.lua.

-- -----------------------------------------------
--
--               CONSTANTS
--
-- -----------------------------------------------

local DEFAULT_SEED  = "HEADLESS"
local DEFAULT_DECK  = "Red Deck"
local DEFAULT_STAKE = 1

-- -----------------------------------------------
--
--               DECK
--
-- -----------------------------------------------

local function resolve_deck(deck_name)
    local requested = deck_name or DEFAULT_DECK

    if type(G) ~= "table" or type(G.P_CENTERS) ~= "table" then
        error("Balatro globals are not initialised; boot the game before calling start_run()")
    end

    local by_key = G.P_CENTERS[requested]
    if by_key and by_key.set == "Back" then
        return by_key
    end

    local by_name = get_deck_from_name(requested)
    if by_name then
        return by_name
    end

    error(string.format("Unknown deck %q", tostring(requested)))
end

local function prime_selected_back(deck_center)
    G.GAME = G.GAME or G:init_game_object()
    G.GAME.viewed_back       = Back(deck_center)
    G.GAME.selected_back     = Back(deck_center)
    G.GAME.viewed_back_key   = deck_center.key
    G.GAME.selected_back_key = deck_center.key
end

-- -----------------------------------------------
--
--               PUBLIC API
--
-- -----------------------------------------------

local M = {}

function M.start_run(opts)
    opts = opts or {}

    wait_until(function()
        return type(G) == "table"
            and type(G.FUNCS) == "table"
            and type(G.start_run) == "function"
            and type(G.delete_run) == "function"
    end, 120, "game boot")

    local seed = opts.seed or DEFAULT_SEED
    local deck_center = resolve_deck(opts.deck or DEFAULT_DECK)

    G:delete_run()
    prime_selected_back(deck_center)
    G:start_run({
        seed  = seed,
        stake = DEFAULT_STAKE,
    })
end

return M
