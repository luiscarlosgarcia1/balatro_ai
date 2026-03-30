local PackContents = dofile("mods/live_state_exporter/pack_contents.lua")

local function assert_equal(left, right, message)
  if left ~= right then
    error(message or ("expected " .. tostring(right) .. ", got " .. tostring(left)), 2)
  end
end

local function test_build_keeps_active_pack_contents_without_reconstructing_identity()
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
  })

  assert_equal(pack_contents.choices_remaining, 1, "choices_remaining should start at choose_limit")
  assert_equal(pack_contents.skip_available, true, "pack reward should preserve skip availability")
  assert_equal(#pack_contents.cards, 5, "visible pack cards should stay attached to pack_contents")
end

local function test_build_reduces_choices_remaining_by_selected_count()
  local pack_contents = PackContents.build({
    interaction_phase = "pack_reward",
    cards = {
      { card_key = "c_fool" },
      { card_key = "c_magician" },
      { card_key = "c_world" },
    },
    choose_limit = 2,
    selected_count = 1,
    skip_available = true,
  })

  assert_equal(pack_contents.choices_remaining, 1, "choices_remaining should reflect already selected cards")
end

local function test_build_keeps_partial_pack_contents_when_metadata_is_missing()
  local pack_contents = PackContents.build({
    interaction_phase = "pack_reward",
    cards = {
      {},
      {},
    },
    choose_limit = 1,
    selected_count = 0,
    skip_available = false,
  })

  assert_equal(pack_contents.choices_remaining, 1, "pack_contents should remain present during active pack reward")
  assert_equal(pack_contents.skip_available, false, "partial pack_contents should preserve boolean flags")
end

test_build_keeps_active_pack_contents_without_reconstructing_identity()
test_build_reduces_choices_remaining_by_selected_count()
test_build_keeps_partial_pack_contents_when_metadata_is_missing()
