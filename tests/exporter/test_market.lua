local market = dofile("mods/live_state_exporter/collectors/market.lua")

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

local shop = market.collect({
  shop = {
    cards = {
      {
        ID = 101,
        cost = 7,
        sell_cost = 3,
        config = {
          card_key = "S_A",
          center_key = "m_bonus",
        },
        edition = {
          type = "foil",
        },
        seal = "Red",
        facing = "front",
      },
      {
        ID = 102,
        sell_cost = 5,
        config = {
          center_key = "j_greedy_joker",
        },
        ability = {
          eternal = true,
          perishable = false,
          rental = true,
          perish_tally = 1,
        },
        edition = {
          type = "negative",
        },
      },
      {
        ID = 103,
        cost = 4,
        sell_cost = 2,
        config = {
          center_key = "c_fool",
        },
        edition = {
          type = "holo",
        },
      },
      {
        ID = 104,
        cost = 6,
        config = {
          center_key = "p_arcana_normal_1",
        },
      },
      {
        config = {
          center_key = "j_missing_id",
        },
      },
    },
  },
  shop_vouchers = {
    cards = {
      {
        cost = 10,
        config = {
          center_key = "v_clearance_sale",
        },
      },
      {
        config = {
          center_key = "v_missing_cost",
        },
      },
    },
  },
}, "shop")

eq(#shop.shop_items, 6, "collector should keep UI-visible shop items and vouchers in row order")
eq(shop.shop_items[1].card.card_key, "S_A", "collector should classify visible playing cards")
eq(shop.shop_items[1].card.instance_id, 101, "collector should keep playing card ids")
eq(shop.shop_items[1].card.enhancement, "m_bonus", "collector should keep playing card enhancement")
ok(shop.shop_items[1].joker == nil, "card wrapper should leave other shop members nil")
eq(shop.shop_items[2].joker.key, "j_greedy_joker", "collector should classify visible jokers")
eq(shop.shop_items[2].joker.perish_tally, 1, "collector should keep joker state")
eq(shop.shop_items[3].consumable.key, "c_fool", "collector should classify visible consumables")
eq(shop.shop_items[4].pack.key, "p_arcana_normal_1", "collector should classify visible packs")
eq(shop.shop_items[4].pack.instance_id, 104, "collector should keep pack ids")
eq(shop.shop_items[5].voucher.key, "v_clearance_sale", "collector should append voucher row after shop row")
eq(shop.shop_items[5].voucher.cost, 10, "collector should keep voucher cost")
eq(shop.shop_items[6].voucher.key, "v_missing_cost", "collector should keep voucher keys without cost")
eq(shop.shop_items[6].voucher.cost, 0, "collector should default voucher cost to 0")
ok(shop.shop_items[6].pack == nil, "voucher wrapper should leave other shop members nil")

local inactive = market.collect({}, "play_hand")
eq(#inactive.shop_items, 0, "non-shop phases should export empty shop_items")
eq(inactive.pack_contents, nil, "non-pack phases should not export pack_contents")

local pack = market.collect({
  pack = {
    ID = 201,
    cost = 6,
    skip_available = true,
    config = {
      center_key = "p_arcana_normal_1",
    },
  },
  pack_cards = {
    cards = {
      {
        ID = 301,
        cost = 5,
        sell_cost = 2,
        facing = "front",
        config = {
          card_key = "H_A",
          center_key = "m_mult",
        },
        edition = {
          type = "foil",
        },
      },
      {
        ID = 302,
        sell_cost = 4,
        config = {
          center_key = "j_blue_joker",
        },
        ability = {
          perishable = true,
        },
      },
      {
        ID = 303,
        cost = 3,
        config = {
          center_key = "c_fool",
        },
      },
      {
        config = {
          center_key = "c_missing_id",
        },
      },
    },
  },
  GAME = {
    pack_choices = 2,
  },
}, "pack_reward")

ok(type(pack.pack_contents) == "table", "pack phase should export pack_contents")
eq(pack.pack_contents.pack.key, "p_arcana_normal_1", "collector should export opened pack key")
eq(pack.pack_contents.pack.instance_id, 201, "collector should export opened pack id")
eq(pack.pack_contents.pack.cost, 6, "collector should export opened pack cost")
eq(pack.pack_contents.choices_remaining, 2, "collector should export pack choices remaining")
eq(pack.pack_contents.skip_available, true, "collector should honor explicit pack skip flag")
eq(#pack.pack_contents.items, 3, "collector should keep only valid pack reward items")
eq(pack.pack_contents.items[1].card_key, "H_A", "collector should export pack playing cards first in UI order")
eq(pack.pack_contents.items[1].enhancement, "m_mult", "collector should preserve card fields for pack items")
eq(pack.pack_contents.items[2].key, "j_blue_joker", "collector should classify pack jokers")
eq(pack.pack_contents.items[2].perishable, true, "collector should preserve joker state in pack items")
eq(pack.pack_contents.items[3].key, "c_fool", "collector should classify pack consumables")

local pack_skip_fallback = market.collect({
  pack = {
    ID = 202,
    config = {
      center_key = "p_celestial_normal_1",
    },
  },
  pack_cards = {
    cards = {},
  },
  GAME = {
    pack_choices = 1,
    pack_skip_available = true,
  },
}, "pack_reward")

eq(pack_skip_fallback.pack_contents.skip_available, true, "collector should fallback to explicit game-level skip flag")

local pack_no_skip = market.collect({
  pack = {
    ID = 203,
    config = {
      center_key = "p_standard_normal_1",
    },
  },
  pack_cards = {
    cards = {},
  },
  GAME = {
    pack_choices = 1,
  },
}, "pack_reward")

eq(pack_no_skip.pack_contents.skip_available, false, "collector should default skip_available to false without explicit booleans")
