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

local shop_root = {
  shop_booster = {
    cards = {},
  },
  GAME = {
    blind = { key = "bl_big" },
    current_round = { reroll_cost = 5 },
  },
}

eq(phase.infer(shop_root), "shop", "phase should infer shop from reroll state")

local pack_root = {
  pack = {
    cards = {},
  },
  GAME = {
    blind = { key = "bl_big" },
    pack_choices = 2,
  },
}

eq(phase.infer(pack_root), "pack_reward", "phase should infer pack_reward from pack choices")

local stale_pack_choices_shop_root = {
  shop_jokers = {
    cards = {
      {
        ID = 1,
      },
    },
  },
  shop_vouchers = {
    cards = {
      {
        ID = 2,
      },
    },
  },
  GAME = {
    blind = { key = "bl_big" },
    pack_choices = 1,
    current_round = { reroll_cost = 5 },
  },
}

eq(stale_pack_choices_shop_root.GAME.pack_choices, 1, "fixture should carry stale pack choice state")
eq(phase.infer(stale_pack_choices_shop_root), "shop", "phase should ignore stale pack choices when shop evidence is present")

local play_root = {
  GAME = {
    blind = { key = "bl_hook" },
    current_round = { hands_left = 2 },
  },
}

eq(phase.infer(play_root), "play_hand", "phase should fall back to play_hand during hands")

ok(true, "phase tests completed")
