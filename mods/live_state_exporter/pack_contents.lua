local PackContents = {}

local function safe_table(value)
  if type(value) == "table" then
    return value
  end
  return nil
end

local function safe_number(value)
  if type(value) == "number" then
    return value
  end
  if type(value) == "string" then
    local parsed = tonumber(value)
    if parsed ~= nil then
      return parsed
    end
  end
  return nil
end

function PackContents.build(args)
  if args and args.interaction_phase ~= "pack_reward" then
    return nil
  end

  local cards = safe_table(args and args.cards) or {}
  local choose_limit = safe_number(args and args.choose_limit)
  local selected_count = safe_number(args and args.selected_count) or 0
  local choices_remaining = choose_limit
  if choose_limit then
    choices_remaining = math.max(0, choose_limit - selected_count)
  end

  return {
    choices_remaining = choices_remaining,
    skip_available = not not (args and args.skip_available),
    cards = cards,
  }
end

return PackContents
