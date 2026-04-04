local zones = dofile("mods/live_state_exporter/zones.lua")

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

local first = zones.collect({
  hand = {
    config = {
      type = "hand",
    },
    cards = {
      {
        ID = 101,
        highlighted = true,
        debuff = true,
        facing = "front",
        cost = 4,
        sell_cost = 2,
        config = {
          card_key = "S_A",
          center_key = "m_bonus",
        },
        edition = {
          type = "foil",
        },
        seal = "Red",
      },
      {
        ID = 102,
        config = {
          card_key = "H_10",
        },
      },
      {
        highlighted = true,
        config = {
          card_key = "C_3",
        },
      },
      {
        ID = 103,
        highlighted = true,
      },
    },
  },
})

eq(#first.cards_in_hand, 2, "collector should export only hand cards with real id and card_key")
eq(first.cards_in_hand[1].card_key, "S_A", "collector should export card_key")
eq(first.cards_in_hand[1].instance_id, 101, "collector should export instance_id")
eq(first.cards_in_hand[1].enhancement, "m_bonus", "collector should export enhancement from center_key")
eq(first.cards_in_hand[1].edition, "foil", "collector should export edition")
eq(first.cards_in_hand[1].seal, "Red", "collector should export seal")
eq(first.cards_in_hand[1].facing, "front", "collector should export facing")
eq(first.cards_in_hand[1].debuffed, true, "collector should export debuffed state")
eq(first.cards_in_hand[1].cost, 4, "collector should export cost")
eq(first.cards_in_hand[1].sell_cost, 2, "collector should export sell_cost")
eq(first.cards_in_hand[2].card_key, "H_10", "collector should preserve visible hand order")

eq(#first.selected_cards, 1, "collector should export only selected cards with real id and key")
eq(first.selected_cards[1].zone, "hand", "collector should preserve area zone naming")
eq(first.selected_cards[1].instance_id, 101, "collector should export selected instance_id")
eq(first.selected_cards[1].key, "S_A", "collector should export selected key")

ok(type(first.jokers) == "table", "collector should always return jokers array")
ok(type(first.consumables) == "table", "collector should always return consumables array")
ok(type(first.cards_in_deck) == "table", "collector should always return deck array")

local second = zones.collect({
  jokers = {
    config = {
      type = "joker",
    },
    cards = {
      {
        ID = 201,
        debuff = true,
        sell_cost = 6,
        config = {
          center_key = "j_greedy_joker",
        },
        ability = {
          eternal = true,
          perishable = false,
          rental = true,
          perish_tally = 2,
        },
        edition = {
          type = "negative",
        },
      },
      {
        config = {
          center_key = "j_missing_id",
        },
      },
    },
  },
  consumeables = {
    config = {
      type = "consumeable",
    },
    cards = {
      {
        ID = 301,
        cost = 3,
        sell_cost = 1,
        config = {
          center_key = "c_fool",
        },
        edition = {
          type = "holo",
        },
      },
      {
        ID = 302,
      },
    },
  },
})

eq(#second.jokers, 1, "collector should drop jokers without real ids or keys")
eq(second.jokers[1].key, "j_greedy_joker", "collector should export joker key")
eq(second.jokers[1].instance_id, 201, "collector should export joker instance_id")
eq(second.jokers[1].eternal, true, "collector should export joker eternal sticker state")
eq(second.jokers[1].perishable, false, "collector should export joker perishable sticker state")
eq(second.jokers[1].rental, true, "collector should export joker rental sticker state")
eq(second.jokers[1].perish_tally, 2, "collector should export joker perish_tally")
eq(second.jokers[1].edition, "negative", "collector should export joker edition")
eq(second.jokers[1].debuffed, true, "collector should export joker debuffed state")
eq(second.jokers[1].sell_cost, 6, "collector should export joker sell_cost")

eq(#second.consumables, 1, "collector should drop consumables without real ids or keys")
eq(second.consumables[1].key, "c_fool", "collector should export consumable key")
eq(second.consumables[1].instance_id, 301, "collector should export consumable instance_id")
eq(second.consumables[1].edition, "holo", "collector should export consumable edition")
eq(second.consumables[1].cost, 3, "collector should export consumable cost")
eq(second.consumables[1].sell_cost, 1, "collector should export consumable sell_cost")

local third = zones.collect({
  GAME = {
    playing_cards = {
      {
        ID = 403,
        base = {
          suit = "Clubs",
          value = "2",
        },
        config = {
          card_key = "C_2",
        },
      },
      {
        ID = 401,
        base = {
          suit = "Hearts",
          value = "Ace",
        },
        config = {
          card_key = "H_A",
        },
      },
      {
        ID = 404,
        base = {
          suit = "Spades",
          value = "Ace",
        },
        config = {
          card_key = "S_A",
        },
      },
      {
        ID = 405,
        base = {
          suit = "Diamonds",
          value = "King",
        },
        config = {
          card_key = "D_K",
        },
      },
      {
        ID = 402,
        base = {
          suit = "Spades",
          value = "Ace",
        },
        config = {
          card_key = "S_A_ALT",
        },
      },
      {
        ID = 499,
        base = {
          suit = "Spades",
          value = "3",
        },
      },
    },
  },
})

eq(#third.cards_in_deck, 5, "collector should drop deck cards without real id or card_key")
eq(third.cards_in_deck[1].card_key, "S_A_ALT", "deck should sort spades first and tie-break by instance_id")
eq(third.cards_in_deck[2].card_key, "S_A", "deck should keep later instance_ids after tie-break")
eq(third.cards_in_deck[3].card_key, "H_A", "deck should place hearts after spades")
eq(third.cards_in_deck[4].card_key, "C_2", "deck should place clubs after hearts")
eq(third.cards_in_deck[5].card_key, "D_K", "deck should place diamonds last")
