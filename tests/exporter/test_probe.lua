local probe = dofile("mods/live_state_exporter/probe.lua")

local function eq(a, b, msg)
  if a ~= b then
    error(msg or ("expected " .. tostring(b) .. ", got " .. tostring(a)), 2)
  end
end

local function ok(v, msg)
  if not v then
    error(msg or "expected truthy value", 2)
  end
end

local capture = probe.capture({
  STATE = 1,
  hand_text_area = {
    game_chips = {
      config = { text = "90" },
    },
    blind_chips = {
      text = "300",
    },
  },
  GAME = {
    dollars = "12",
    money = 11,
    chips = "90",
    blind = {
      chips = "300",
    },
    hands = {
      Flush = {
        level = "2",
        chips = "80",
        mult = "8",
        played = 1,
        played_this_round = 0,
      },
    },
  },
})

eq(capture.money.game_dollars.kind, "string", "probe should preserve raw value kinds")
eq(capture.money.game_dollars.coerced_number, 12, "probe should record numeric coercion alongside the raw value")
eq(capture.score.game_chips.coerced_number, 90, "probe should inspect score candidates")
eq(capture.score.blind_chips.coerced_number, 300, "probe should inspect blind score candidates")
eq(capture.hud.game_chips.text, "90", "probe should extract config.text from HUD nodes")
eq(capture.hands.Flush.level.coerced_number, 2, "probe should inspect run-hand fields")

local old_love = rawget(_G, "love")
local writes = {}

_G.love = {
  filesystem = {
    createDirectory = function(_)
      return true
    end,
    write = function(path, body)
      writes[#writes + 1] = { path = path, body = body }
      return true
    end,
  },
}

local wrote_first = probe.tick({
  GAME = {
    dollars = 4,
  },
})
local wrote_second = probe.tick({
  GAME = {
    dollars = 4,
  },
})
local wrote_third = probe.tick({
  GAME = {
    dollars = 5,
  },
})

eq(wrote_first, false, "probe should stay silent when disabled")
eq(wrote_second, false, "probe should dedupe unchanged payloads")
eq(wrote_third, false, "probe should stay silent even when payload changes")
eq(#writes, 0, "disabled probe should not write probe snapshots")

_G.love = old_love
