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
  CONTROLLER = {},
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

eq(#writes, 2, "boot should attempt initial snapshot and probe writes")
eq(writes[1].path, "ai/live_state.json", "main should write to canonical path")
eq(writes[2].path, "ai/live_state_probe.json", "main should write probe output alongside the canonical snapshot")

t = 0.02
_G.love.update()
eq(#writes, 2, "wrapped update should respect throttle and probe dedupe")

t = 0.10
_G.G.GAME.dollars = 6
_G.love.update()
eq(#writes, 4, "wrapped update should delegate changed payload and probe writes")

t = 0.16
_G.G.CONTROLLER.locked = true
_G.G.GAME.dollars = 7
_G.love.update()
eq(#writes, 5, "readiness false should still allow probe writes without canonical export")
eq(writes[5].path, "ai/live_state_probe.json", "probe should remain ungated when canonical export is blocked")

_G.love = old.love
_G.Game = old.Game
_G.G = old.G
_G.SMODS = old.SMODS
_G.NFS = old.NFS

local update_calls = 0

_G.SMODS = {
  current_mod = {
    path = "virtual/",
  },
}
_G.NFS = {
  read = function(path)
    if path == "virtual/shared/loader.lua" then
      return "return { load = function(name) if name == 'state/raw.lua' then return { read_state = function() return {} end } end if name == 'state/schema.lua' then return { build_shell = function() return {} end } end if name == 'state/readiness.lua' then return { is_ready = function() return true end } end if name == 'out.lua' then return { new_exporter = function() return { tick = function() error('boom from exporter tick') end } end, make_signature = function() return 'sig' end, encode_json = function() return '{}' end } end if name == 'probe.lua' then return { tick = function() error('boom from probe tick') end } end error('unexpected module name: ' .. tostring(name)) end }"
    end
    if path == "virtual/state/raw.lua" then
      return "return { read_state = function() return {} end }"
    end
    if path == "virtual/state/schema.lua" then
      return "return { build_shell = function() return {} end }"
    end
    if path == "virtual/state/readiness.lua" then
      return "return { is_ready = function() return true end }"
    end
    if path == "virtual/out.lua" then
      return "return { new_exporter = function() return { tick = function() error('boom from exporter tick') end } end, make_signature = function() return 'sig' end, encode_json = function() return '{}' end }"
    end
    if path == "virtual/probe.lua" then
      return "return { tick = function() error('boom from probe tick') end }"
    end
    error("unexpected module path: " .. tostring(path))
  end,
}
_G.Game = nil
_G.G = {}
_G.love = {
  timer = {
    getTime = function()
      return 0
    end,
  },
  filesystem = {
    createDirectory = function(_)
      return true
    end,
    write = function(_, _)
      return true
    end,
  },
  update = function()
    update_calls = update_calls + 1
    return "wrapped-ok"
  end,
}

local boot_ok, boot_err = pcall(function()
  dofile("mods/live_state_exporter/main.lua")
end)

eq(boot_ok, true, "main should survive exporter tick failures during install")
eq(boot_err, nil, "successful boot should not surface an error")

local update_ok, update_result = pcall(function()
  return _G.love.update()
end)

eq(update_ok, true, "wrapped update should survive exporter tick failures")
eq(update_result, "wrapped-ok", "wrapped update should preserve the original return value")
eq(update_calls, 1, "wrapped update should still call the original update function")

_G.love = old.love
_G.Game = old.Game
_G.G = old.G
_G.SMODS = old.SMODS
_G.NFS = old.NFS
