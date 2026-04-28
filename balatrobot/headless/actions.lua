local stub = require("headless.love_stub")

local M = {}

-- -----------------------------------------------
--
--               CONFIGURATION
--
-- -----------------------------------------------

local TICKS_PLAY_HAND  = 1800
local TICKS_DISCARD    = 600
local TICKS_GENERIC    = 300

-- -----------------------------------------------
--
--               INTERNAL HELPERS
--
-- -----------------------------------------------

local function tick_once()
    stub.advance()
    if type(love) == "table" and type(love.update) == "function" then
        love.update(stub.state.fixed_dt)
    end
end

local function tick(frames)
    for _ = 1, frames do
        tick_once()
    end
end

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

local function wait_until(predicate, max_ticks, label, on_tick)
    if predicate() then
        return true
    end

    for _ = 1, max_ticks do
        tick_once()
        if on_tick then
            on_tick()
        end
        if predicate() then
            return true
        end
    end

    error(string.format(
        "Timed out waiting for %s (state=%s, hand=%s, deck=%s, play=%s)",
        label,
        state_name(G and G.STATE),
        tostring(G and G.hand and G.hand.cards and #G.hand.cards or "nil"),
        tostring(G and G.deck and G.deck.cards and #G.deck.cards or "nil"),
        tostring(G and G.play and G.play.cards and #G.play.cards or "nil")
    ))
end

local function assert_run_ready()
    if type(G) ~= "table"
        or type(G.STATES) ~= "table"
        or type(G.FUNCS) ~= "table"
        or type(G.GAME) ~= "table"
        or type(G.hand) ~= "table"
        or type(G.hand.cards) ~= "table"
    then
        error("Balatro run is not ready; boot the game and call start_run.start_run() first")
    end
end

local function current_round()
    return G and G.GAME and G.GAME.current_round or nil
end

local function is_round_over(state)
    local states = G and G.STATES or {}
    return state ~= nil
        and state ~= states.SELECTING_HAND
        and state ~= states.DRAW_TO_HAND
        and state ~= states.HAND_PLAYED
        and state ~= states.PLAY_TAROT
        and state ~= states.NEW_ROUND
end

-- -----------------------------------------------
--
--               CARD SNAPSHOTS
--
-- -----------------------------------------------

local function snapshot_card(card, index)
    if not card then
        return nil
    end

    local ability = card.ability or {}
    local base = card.base or {}
    local edition = card.edition or nil
    local id = nil
    if type(card.get_id) == "function" then
        id = card:get_id()
    end

    return {
        index = index,
        key = card.config and card.config.card_key or nil,
        suit = base.suit,
        rank = base.value,
        id = id,
        nominal = base.nominal,
        facing = card.facing,
        highlighted = card.highlighted == true,
        debuffed = card.debuff == true,
        edition = edition and edition.type or nil,
        seal = card.seal,
        center_key = card.config and card.config.center_key or nil,
        ability_name = ability.name,
        ability_set = ability.set,
        cost = card.cost,
    }
end

local function snapshot_cards(cards)
    local out = {}
    for i, card in ipairs(cards or {}) do
        out[i] = snapshot_card(card, i)
    end
    return out
end

-- -----------------------------------------------
--
--               SELECTION
--
-- -----------------------------------------------

local function set_selection(selected_cards)
    for _, card in ipairs(G.hand.cards) do
        card:highlight(false)
    end

    G.hand.highlighted = {}
    for _, card in ipairs(selected_cards) do
        card:highlight(true)
        G.hand.highlighted[#G.hand.highlighted + 1] = card
    end

    if G.STATE == G.STATES.SELECTING_HAND and type(G.hand.parse_highlighted) == "function" then
        G.hand:parse_highlighted()
    end
end

local function selected_hand_name()
    if type(G) ~= "table"
        or type(G.FUNCS) ~= "table"
        or type(G.FUNCS.get_poker_hand_info) ~= "function"
        or type(G.hand) ~= "table"
        or type(G.hand.highlighted) ~= "table"
    then
        return nil
    end

    local text = select(1, G.FUNCS.get_poker_hand_info(G.hand.highlighted))
    if text and text ~= "NULL" then
        return text
    end
    return nil
end

-- -----------------------------------------------
--
--               ACTIONS
--
-- -----------------------------------------------

local function read_hand_progress(observed, score_before)
    local hand = current_round() and current_round().current_hand or nil
    if G.GAME.last_hand_played and G.GAME.last_hand_played ~= "" then
        observed.hand_name = G.GAME.last_hand_played
    end
    if hand then
        if type(hand.chips) == "number" and hand.chips > observed.chips then
            observed.chips = hand.chips
        end
        if type(hand.mult) == "number" and hand.mult > observed.mult then
            observed.mult = hand.mult
        end
        if type(hand.chip_total) == "number" and hand.chip_total > observed.score_gained then
            observed.score_gained = hand.chip_total
        end
    end

    local gained = (tonumber(G.GAME.chips) or 0) - score_before
    if gained > observed.score_gained then
        observed.score_gained = gained
    end
end

function M.select_cards(indices)
    assert_run_ready()

    if type(indices) ~= "table" then
        error("select_cards(indices) expects a table of 1-based hand indices")
    end

    local selected_cards = {}
    local seen = {}

    for _, raw_index in ipairs(indices) do
        local index = tonumber(raw_index)
        if index ~= math.floor(index or 0) then
            error(string.format("Hand index %q is not an integer", tostring(raw_index)))
        end
        if index < 1 or index > #G.hand.cards then
            error(string.format(
                "Hand index %d is out of range (hand has %d cards)",
                index,
                #G.hand.cards
            ))
        end
        if not seen[index] then
            seen[index] = true
            selected_cards[#selected_cards + 1] = G.hand.cards[index]
        end
    end

    set_selection(selected_cards)
end

function M.play_hand()
    assert_run_ready()

    if #G.hand.highlighted == 0 then
        error("Cannot play a hand with no selected cards")
    end

    local round = current_round()
    local score_before = tonumber(G.GAME.chips) or 0
    local observed = {
        hand_name = selected_hand_name(),
        chips = 0,
        mult = 0,
        score_gained = 0,
    }

    read_hand_progress(observed, score_before)
    G.FUNCS.play_cards_from_highlighted()

    wait_until(function()
        local state = G.STATE
        local play_count = G.play and G.play.cards and #G.play.cards or 0
        return state ~= G.STATES.SELECTING_HAND or play_count > 0
    end, TICKS_PLAY_HAND, "play hand start", function()
        read_hand_progress(observed, score_before)
    end)

    wait_until(function()
        local state = G.STATE
        return state == G.STATES.SELECTING_HAND or is_round_over(state)
    end, TICKS_PLAY_HAND, "play hand resolution", function()
        read_hand_progress(observed, score_before)
    end)

    tick(2)
    read_hand_progress(observed, score_before)
    round = current_round()

    return {
        hand_name = observed.hand_name,
        chips = observed.chips,
        mult = observed.mult,
        score_gained = observed.score_gained,
        hands_left = round and round.hands_left or nil,
        discards_left = round and round.discards_left or nil,
    }
end

function M.discard()
    assert_run_ready()

    if #G.hand.highlighted == 0 then
        error("Cannot discard with no selected cards")
    end

    local seen_before = {}
    for _, card in ipairs(G.hand.cards) do
        seen_before[card] = true
    end

    G.FUNCS.discard_cards_from_highlighted()

    wait_until(function()
        return G.STATE ~= G.STATES.SELECTING_HAND
    end, TICKS_DISCARD, "discard start")

    wait_until(function()
        local state = G.STATE
        return state == G.STATES.SELECTING_HAND or is_round_over(state)
    end, TICKS_DISCARD, "discard resolution")

    tick(2)

    local new_cards_count = 0
    for _, card in ipairs(G.hand.cards) do
        if not seen_before[card] then
            new_cards_count = new_cards_count + 1
        end
    end

    local round = current_round()
    return {
        discards_left = round and round.discards_left or nil,
        new_cards_count = new_cards_count,
    }
end

-- -----------------------------------------------
--
--               STATE
--
-- -----------------------------------------------

function M.get_state()
    assert_run_ready()

    local round = current_round() or {}
    local blind = G.GAME.blind or {}

    return {
        state = state_name(G.STATE),
        hand_cards = snapshot_cards(G.hand.cards),
        jokers = snapshot_cards(G.jokers and G.jokers.cards or {}),
        money = G.GAME.dollars,
        score = G.GAME.chips,
        chips_needed = math.max(0, (blind.chips or 0) - (G.GAME.chips or 0)),
        hands_left = round.hands_left,
        discards_left = round.discards_left,
        round = G.GAME.round,
        ante = G.GAME.round_resets and G.GAME.round_resets.ante or nil,
    }
end

-- -----------------------------------------------
--
--               EXPORTS
--
-- -----------------------------------------------

return M
