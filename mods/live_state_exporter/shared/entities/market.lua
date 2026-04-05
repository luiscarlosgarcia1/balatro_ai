-- Readers that classify shop rows and pack rewards for visible market state.
return function(common, owned)
  local market = {}

  local function wrap_shop_item(kind, value)
    return {
      card = kind == "card" and value or nil,
      joker = kind == "joker" and value or nil,
      consumable = kind == "consumable" and value or nil,
      voucher = kind == "voucher" and value or nil,
      pack = kind == "pack" and value or nil,
    }
  end

  function market.read_pack(card, key)
    local instance_id = common.read_instance_id(card)
    key = key or common.read_center_key(card)
    if instance_id == nil or key == nil then
      return nil
    end

    return {
      key = key,
      instance_id = instance_id,
      cost = common.read_cost(card),
    }
  end

  function market.read_voucher(card, key)
    key = key or common.read_center_key(card)
    if key == nil then
      return nil
    end

    return {
      key = key,
      cost = common.read_cost(card) or 0,
    }
  end

  function market.classify_shop_item(card)
    local card_key = common.read_card_key(card)
    if card_key ~= nil then
      local item = owned.read_playing_card(card)
      if item ~= nil then
        return wrap_shop_item("card", item)
      end
      return nil
    end

    local center_key = common.read_center_key(card)
    if type(center_key) ~= "string" then
      return nil
    end

    local prefix = center_key:sub(1, 2)
    if prefix == "j_" then
      local item = owned.read_joker(card, center_key)
      return item ~= nil and wrap_shop_item("joker", item) or nil
    end
    if prefix == "c_" then
      local item = owned.read_consumable(card, center_key)
      return item ~= nil and wrap_shop_item("consumable", item) or nil
    end
    if prefix == "p_" then
      local item = market.read_pack(card, center_key)
      return item ~= nil and wrap_shop_item("pack", item) or nil
    end
    if prefix == "v_" then
      local item = market.read_voucher(card, center_key)
      return item ~= nil and wrap_shop_item("voucher", item) or nil
    end

    return nil
  end

  function market.classify_pack_reward_item(card)
    local card_key = common.read_card_key(card)
    if card_key ~= nil then
      return owned.read_playing_card(card)
    end

    local center_key = common.read_center_key(card)
    if type(center_key) ~= "string" then
      return nil
    end

    local prefix = center_key:sub(1, 2)
    if prefix == "j_" then
      return owned.read_joker(card, center_key)
    end
    if prefix == "c_" then
      return owned.read_consumable(card, center_key)
    end

    return nil
  end

  return market
end
