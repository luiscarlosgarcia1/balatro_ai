local PackContents = dofile("mods/live_state_exporter/pack_contents.lua")

local function assert_equal(left, right, message)
  if left ~= right then
    error(message or ("expected " .. tostring(right) .. ", got " .. tostring(left)), 2)
  end
end

local function assert_nil(value, message)
  if value ~= nil then
    error(message or ("expected nil, got " .. tostring(value)), 2)
  end
end

local function test_build_prefers_active_pack_cards_over_stale_shop_pack_identity()
  local pack_contents = PackContents.build({
    interaction_phase = "pack_reward",
    cards = {
      { card_key = "c_j" },
      { card_key = "h_6" },
      { card_key = "s_2" },
      { card_key = "d_5" },
      { card_key = "c_q" },
    },
    choose_limit = 1,
    selected_count = 0,
    skip_available = true,
    shop_items = {
      { key = "p_buffoon_normal_1" },
    },
    remembered_pack_key = "p_buffoon_normal_1",
    pack_size = 2,
  })

  assert_equal(pack_contents.pack_key, "p_standard_jumbo_1", "active pack cards should override stale shop family")
  assert_equal(pack_contents.pack_size, 5, "pack_size should reflect visible pack cards")
end

local function test_build_derives_arcana_pack_from_tarot_cards()
  local pack_contents = PackContents.build({
    interaction_phase = "pack_reward",
    cards = {
      { card_key = "c_fool" },
      { card_key = "c_magician" },
      { card_key = "c_world" },
    },
    choose_limit = 1,
    selected_count = 0,
    skip_available = true,
    shop_items = {
      { key = "p_buffoon_normal_2" },
    },
    remembered_pack_key = "p_buffoon_normal_2",
    pack_size = 99,
  })

  assert_equal(pack_contents.pack_key, "p_arcana_normal_2", "tarot cards should resolve to arcana pack family")
  assert_equal(pack_contents.pack_size, 3, "pack_size should use card count for normal packs")
end

local function test_build_returns_nil_when_pack_identity_cannot_be_resolved()
  local pack_contents = PackContents.build({
    interaction_phase = "pack_reward",
    cards = {
      {},
      {},
    },
    choose_limit = 1,
    selected_count = 0,
    skip_available = true,
    shop_items = {},
    remembered_pack_key = nil,
    pack_size = 2,
  })

  assert_nil(pack_contents, "unidentifiable active packs should not emit a fake pack key")
end

local function test_remembered_key_tracks_single_visible_pack_offer_in_shop()
  local remembered = PackContents.remembered_key("shop", {
    { key = "j_greedy_joker" },
    { key = "p_standard_jumbo_1" },
  }, nil)

  assert_equal(remembered, "p_standard_jumbo_1", "shop phase should remember a single visible pack offer")
end

test_build_prefers_active_pack_cards_over_stale_shop_pack_identity()
test_build_derives_arcana_pack_from_tarot_cards()
test_build_returns_nil_when_pack_identity_cannot_be_resolved()
test_remembered_key_tracks_single_visible_pack_offer_in_shop()
