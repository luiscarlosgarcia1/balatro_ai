-- Higher-level shell sections built from shared entity cloners.
return function(values, primitives, entities)
  local sections = {}

  local as_table = values.as_table
  local to_number = values.to_number
  local mark_array = primitives.mark_array
  local clone_mapped_array = primitives.clone_mapped_array
  local optional_or_null = primitives.optional_or_null
  local required_or = primitives.required_or

  function sections.clone_blinds(source)
    local out = {}
    if type(source) == "table" then
      for i = 1, #source do
        local blind = as_table(source[i]) or {}
        out[i] = {
          key = blind.key,
          state = blind.state,
          tag_key = optional_or_null(blind.tag_key),
        }
      end
    end
    return mark_array(out)
  end

  function sections.clone_shop_items(source)
    return clone_mapped_array(source, function(item)
      item = as_table(item) or {}
      return {
        card = optional_or_null(item.card ~= nil and entities.clone_card(item.card) or nil),
        joker = optional_or_null(item.joker ~= nil and entities.clone_joker(item.joker) or nil),
        consumable = optional_or_null(item.consumable ~= nil and entities.clone_consumable(item.consumable) or nil),
        voucher = optional_or_null(item.voucher ~= nil and entities.clone_voucher(item.voucher) or nil),
        pack = optional_or_null(item.pack ~= nil and entities.clone_pack(item.pack) or nil),
      }
    end)
  end

  local function clone_pack_item(item)
    item = as_table(item) or {}
    if item.card_key ~= nil then
      return entities.clone_card(item)
    end
    if item.eternal ~= nil or item.perishable ~= nil or item.rental ~= nil or item.perish_tally ~= nil or item.debuffed ~= nil or item.sell_cost ~= nil then
      return entities.clone_joker(item)
    end
    return entities.clone_consumable(item)
  end

  function sections.clone_pack_contents(source)
    source = as_table(source)
    if not source then
      return optional_or_null(nil)
    end
    return {
      pack = optional_or_null(source.pack ~= nil and entities.clone_pack(source.pack) or nil),
      choices_remaining = optional_or_null(source.choices_remaining),
      skip_available = source.skip_available == true,
      items = clone_mapped_array(source.items, clone_pack_item),
    }
  end

  function sections.clone_run_info(source)
    source = as_table(source)
    local hands = as_table(source and source.hands)
    if not hands then
      return optional_or_null(nil)
    end

    local out = {}
    local count = 0
    for hand_name, hand in pairs(hands) do
      if type(hand_name) == "string" and type(hand) == "table" then
        out[hand_name] = hand
        count = count + 1
      end
    end

    if count == 0 then
      return optional_or_null(nil)
    end

    return {
      hands = out,
    }
  end

  function sections.clone_interest(source)
    source = as_table(source)
    if not source then
      return optional_or_null(nil)
    end

    local amount = to_number(source.amount)
    local cap = to_number(source.cap)
    local no_interest = source.no_interest
    if amount == nil and cap == nil and no_interest == nil then
      return optional_or_null(nil)
    end

    return {
      amount = required_or(amount, 0),
      cap = required_or(cap, 0),
      no_interest = no_interest == true,
    }
  end

  return sections
end
