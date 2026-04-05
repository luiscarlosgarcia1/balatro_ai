local phase = dofile("mods/live_state_exporter/state/phase.lua")

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

local blind_select_root = {
  GAME = {
    round_resets = {
      blind_choices = {
        small = "bl_small",
        big = "bl_big",
        boss = "bl_hook",
      },
      blind_states = {
        small = "selectable",
        big = "upcoming",
        boss = "upcoming",
      },
    },
  },
}

eq(phase.infer(blind_select_root), "blind_select", "phase should infer blind_select from blind rows")
eq(
  phase.derive_blind_key(blind_select_root, "blind_select", {
    { key = "bl_small", state = "selectable" },
    { key = "bl_big", state = "upcoming" },
    { key = "bl_hook", state = "upcoming" },
  }),
  "bl_small",
  "blind_select should choose the first selectable blind in row order"
)

local shop_root = {
  GAME = {
    blind = { key = "bl_big" },
    current_round = { reroll_cost = 5 },
  },
}

eq(phase.infer(shop_root), "shop", "phase should infer shop from reroll state")
eq(
  phase.derive_blind_key(shop_root, "shop"),
  "bl_big",
  "shop should prefer the active blind key"
)

local pack_root = {
  GAME = {
    blind = { key = "bl_big" },
    pack_choices = 2,
  },
}

eq(phase.infer(pack_root), "pack_reward", "phase should infer pack_reward from pack choices")

local play_root = {
  GAME = {
    blind = { key = "bl_hook" },
    current_round = { hands_left = 2 },
  },
}

eq(phase.infer(play_root), "play_hand", "phase should fall back to play_hand during hands")
eq(
  phase.derive_blind_key(play_root, "play_hand"),
  "bl_hook",
  "play_hand should prefer the active blind key"
)

ok(true, "phase tests completed")
