local run_state = dofile("mods/live_state_exporter/run_state.lua")

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

local root = {
  tags = {
    { key = "tag_top_up" },
    { key = "tag_skip" },
  },
  jokers = {
    config = {
      card_limit = 5,
    },
  },
  consumeables = {
    config = {
      card_limit = 2,
    },
  },
  hand = {
    config = {
      card_limit = 8,
    },
  },
  GAME = {
    blind = { key = "bl_big" },
    round = 3,
    current_round = {
      reroll_cost = 6,
    },
    round_resets = {
      blind_choices = {
        small = "bl_small",
        big = "bl_big",
        boss = "bl_hook",
      },
      blind_states = {
        small = "defeated",
        big = "current",
        boss = "upcoming",
      },
      blind_tags = {
        small = "tag_garbage",
        big = "tag_coupon",
      },
      ante = 2,
    },
    hands = {
      ["High Card"] = {
        level = 2,
        chips = 15,
        mult = 1,
        played = 3,
        played_this_round = 1,
        ignored = "x",
      },
      ["Flush Five"] = {
        level = 1,
        chips = 160,
        mult = 16,
        played = 0,
        played_this_round = 0,
      },
      ["Pair"] = {
        level = 4,
        chips = 25,
        mult = 3,
        played = 5,
        played_this_round = 2,
      },
      Unknown = {
        level = 9,
        chips = 999,
        mult = 99,
        played = 99,
        played_this_round = 99,
      },
    },
    interest_amount = 2,
    interest_cap = 25,
    modifiers = {
      no_interest = false,
    },
    used_vouchers = {
      v_planet_merchant = true,
      v_overstock = {
        cost = 10,
      },
    },
  },
}

local collected = run_state.collect(root, "shop")

eq(#collected.blinds, 3, "collector should shape three blind rows")
eq(collected.blinds[1].key, "bl_small", "collector should keep small blind first")
eq(collected.blinds[1].state, "defeated", "collector should keep blind state")
eq(collected.blinds[1].tag_key, "tag_garbage", "collector should keep blind tag")
eq(collected.blinds[2].key, "bl_big", "collector should keep big blind second")
eq(collected.blinds[2].tag_key, "tag_coupon", "collector should keep second blind tag")
eq(collected.blinds[3].key, "bl_hook", "collector should keep boss blind third")
eq(collected.blinds[3].tag_key, nil, "collector should keep missing tag_key nil before shell shaping")

ok(type(collected.run_info) == "table", "collector should shape run_info")
ok(type(collected.run_info.hands) == "table", "collector should shape run_info.hands")
eq(collected.run_info.hands["Flush Five"].chips, 160, "collector should include ordered known hands")
eq(collected.run_info.hands["Pair"].played_this_round, 2, "collector should keep hand counters")
eq(collected.run_info.hands["Unknown"], nil, "collector should omit unknown hand names")

eq(collected.interest.amount, 2, "collector should read interest amount")
eq(collected.interest.cap, 25, "collector should read interest cap")
eq(collected.interest.no_interest, false, "collector should read no_interest")
eq(collected.joker_slots, 5, "collector should read joker_slots")
eq(collected.consumable_slots, 2, "collector should read consumable_slots")
eq(collected.hand_size, 8, "collector should read hand_size")

eq(#collected.vouchers, 2, "collector should export owned vouchers")
eq(collected.vouchers[1].key, "v_overstock", "collector should sort vouchers by key")
eq(collected.vouchers[1].cost, 10, "collector should keep known voucher cost")
eq(collected.vouchers[2].key, "v_planet_merchant", "collector should include key-only voucher")
eq(collected.vouchers[2].cost, 0, "collector should fallback voucher cost to 0")

eq(#collected.tags, 2, "collector should export active tags")
eq(collected.tags[1].key, "tag_top_up", "collector should preserve tag order")
eq(collected.tags[2].key, "tag_skip", "collector should preserve later tag order")
