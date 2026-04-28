local stub = require("headless.love_stub")

-- Shared tick, state, and wait helpers.  Extracted here so that run.lua and
-- start_run.lua do not each carry their own copies.

-- -----------------------------------------------
--
--               TICK
--
-- -----------------------------------------------

local function tick_once()
    stub.advance()
    if type(love) == "table" and type(love.update) == "function" then
        love.update(stub.state.fixed_dt)
    end
end

-- -----------------------------------------------
--
--               STATE
--
-- -----------------------------------------------

local function state_name(state)
    if type(G) == "table" and type(G.STATES) == "table" then
        for name, value in pairs(G.STATES) do
            if value == state then
                return name
            end
        end
    end
    return tostring(state)
end

local function current_state_name()
    return state_name(G and G.STATE)
end

-- -----------------------------------------------
--
--               WAIT
--
-- -----------------------------------------------

local function wait_until(predicate, max_ticks, label)
    if predicate() then
        return true
    end

    for _ = 1, max_ticks do
        tick_once()
        if predicate() then
            return true
        end
    end

    error(string.format(
        "Timed out waiting for %s (state=%s, hand=%s, deck=%s)",
        label,
        current_state_name(),
        tostring(G and G.hand and G.hand.cards and #G.hand.cards or "nil"),
        tostring(G and G.deck and G.deck.cards and #G.deck.cards or "nil")
    ))
end

return {
    tick_once           = tick_once,
    current_state_name  = current_state_name,
    wait_until          = wait_until,
}
