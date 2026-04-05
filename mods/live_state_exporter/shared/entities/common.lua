-- Shared field readers for ids, keys, costs, and selected references.
return function(values)
  local common = {}

  local as_table = values.as_table
  local first_defined = values.first_defined
  local to_number = values.to_number

  function common.read_instance_id(card)
    return to_number(first_defined(card and card.instance_id, card and card.id, card and card.ID))
  end

  function common.read_card_key(card)
    local config = as_table(card and card.config) or {}
    local key = first_defined(config.card_key, config.key)
    if type(key) == "string" and key ~= "" then
      return key
    end
    return nil
  end

  function common.read_center_key(card)
    local config = as_table(card and card.config) or {}
    local key = first_defined(config.center_key, config.key)
    if type(key) == "string" and key ~= "" then
      return key
    end
    return nil
  end

  function common.read_edition(card)
    local edition = as_table(card and card.edition) or {}
    if type(edition.type) == "string" and edition.type ~= "" then
      return edition.type
    end
    return nil
  end

  function common.read_card_enhancement(card)
    local config = as_table(card and card.config) or {}
    local key = config.center_key
    if type(key) == "string" and key ~= "" and key ~= "c_base" then
      return key
    end
    return nil
  end

  function common.read_cost(card)
    return to_number(card and card.cost)
  end

  function common.read_sell_cost(card)
    return to_number(first_defined(card and card.sell_cost, card and card.sell_price))
  end

  function common.read_joker_stickers(card)
    local ability = as_table(card and card.ability) or {}
    return {
      eternal = ability.eternal == true,
      perishable = ability.perishable == true,
      rental = ability.rental == true,
      perish_tally = to_number(ability.perish_tally),
    }
  end

  function common.read_selected_reference(card, zone, key)
    if not card or (card.highlighted ~= true and card.selected ~= true) then
      return nil
    end

    local instance_id = common.read_instance_id(card)
    key = key or common.read_card_key(card) or common.read_center_key(card)
    if instance_id == nil or key == nil then
      return nil
    end

    return {
      zone = zone,
      instance_id = instance_id,
      key = key,
    }
  end

  return common
end
