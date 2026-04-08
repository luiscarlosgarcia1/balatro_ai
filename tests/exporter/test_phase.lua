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

local STATES = {
  SELECTING_HAND = 1,
  SHOP           = 2,
  BLIND_SELECT   = 3,
  TAROT_PACK     = 4,
  PLANET_PACK    = 5,
  SPECTRAL_PACK  = 6,
  BUFFOON_PACK   = 7,
  STANDARD_PACK  = 8,
}

eq(phase.infer({ STATE = STATES.SELECTING_HAND, STATES = STATES }), "play_hand",    "SELECTING_HAND -> play_hand")
eq(phase.infer({ STATE = STATES.SHOP,           STATES = STATES }), "shop",         "SHOP -> shop")
eq(phase.infer({ STATE = STATES.BLIND_SELECT,   STATES = STATES }), "blind_select", "BLIND_SELECT -> blind_select")
eq(phase.infer({ STATE = STATES.TAROT_PACK,     STATES = STATES }), "pack_reward",  "TAROT_PACK -> pack_reward")
eq(phase.infer({ STATE = STATES.PLANET_PACK,    STATES = STATES }), "pack_reward",  "PLANET_PACK -> pack_reward")
eq(phase.infer({ STATE = STATES.SPECTRAL_PACK,  STATES = STATES }), "pack_reward",  "SPECTRAL_PACK -> pack_reward")
eq(phase.infer({ STATE = STATES.BUFFOON_PACK,   STATES = STATES }), "pack_reward",  "BUFFOON_PACK -> pack_reward")
eq(phase.infer({ STATE = STATES.STANDARD_PACK,  STATES = STATES }), "pack_reward",  "STANDARD_PACK -> pack_reward")

eq(phase.infer({ STATE = 99,  STATES = STATES }), "play_hand", "unknown state -> play_hand fallback")
eq(phase.infer({ STATES = STATES }),               "play_hand", "nil STATE -> play_hand fallback")
eq(phase.infer({}),                                "play_hand", "empty root -> play_hand fallback")

ok(true, "phase tests completed")
