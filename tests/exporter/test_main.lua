local function eq(a, b, msg)
  if a ~= b then
    error(msg or ("expected " .. tostring(b) .. ", got " .. tostring(a)), 2)
  end
end

local old = {
  love = rawget(_G, "love"),
  Game = rawget(_G, "Game"),
  G = rawget(_G, "G"),
  SMODS = rawget(_G, "SMODS"),
  NFS = rawget(_G, "NFS"),
}

local t = 0
local writes = {}

_G.SMODS = nil
_G.NFS = nil
_G.Game = nil
_G.G = {
  STATE = 9,
  GAME = {},
}

_G.love = {
  timer = {
    getTime = function()
      return t
    end,
  },
  filesystem = {
    createDirectory = function(_)
      return true
    end,
    write = function(path, body)
      writes[#writes + 1] = { path = path, body = body }
      return true
    end,
  },
  update = function()
    return "ok"
  end,
}

dofile("mods/live_state_exporter/main.lua")

eq(#writes, 1, "boot should attempt an initial write")
eq(writes[1].path, "ai/live_state.json", "main should write to canonical path")

t = 0.02
_G.love.update()
eq(#writes, 1, "wrapped update should respect throttle")

t = 0.10
_G.G.GAME.dollars = 6
_G.love.update()
eq(#writes, 2, "wrapped update should delegate changed payload writes")

_G.love = old.love
_G.Game = old.Game
_G.G = old.G
_G.SMODS = old.SMODS
_G.NFS = old.NFS
