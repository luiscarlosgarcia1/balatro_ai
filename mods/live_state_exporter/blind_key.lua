local BlindKey = {}

local EXPECTED_STATE_BY_PHASE = {
  blind_select = "select",
  play_hand = "current",
  shop = "upcoming",
}

local function normalize_state(value)
  if type(value) ~= "string" then
    return nil
  end
  return string.lower(value)
end

function BlindKey.derive(interaction_phase, blinds)
  local expected_state = EXPECTED_STATE_BY_PHASE[interaction_phase]
  if expected_state == nil then
    return nil
  end
  if type(blinds) ~= "table" then
    return nil
  end

  for _, blind in ipairs(blinds) do
    if type(blind) == "table"
      and normalize_state(blind.state) == expected_state
      and blind.key ~= nil
    then
      return blind.key
    end
  end

  return nil
end

return BlindKey
