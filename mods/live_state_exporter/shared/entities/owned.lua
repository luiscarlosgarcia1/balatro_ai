-- Readers that shape owned cards, jokers, and consumables for export.
return function(common)
  local owned = {}

  function owned.read_playing_card(card)
    local instance_id = common.read_instance_id(card)
    local card_key = common.read_card_key(card)
    if instance_id == nil or card_key == nil then
      return nil
    end

    return {
      card_key = card_key,
      instance_id = instance_id,
      enhancement = common.read_card_enhancement(card),
      edition = common.read_edition(card),
      seal = card.seal,
      facing = card.facing,
      debuffed = card.debuff == true,
    }
  end

  function owned.read_joker(card, key)
    local instance_id = common.read_instance_id(card)
    key = key or common.read_center_key(card)
    if instance_id == nil or key == nil then
      return nil
    end

    local stickers = common.read_joker_stickers(card)
    return {
      key = key,
      instance_id = instance_id,
      eternal = stickers.eternal,
      perishable = stickers.perishable,
      rental = stickers.rental,
      perish_tally = stickers.perish_tally,
      edition = common.read_edition(card),
      debuffed = card.debuff == true,
      sell_cost = common.read_sell_cost(card),
    }
  end

  function owned.read_consumable(card, key)
    local instance_id = common.read_instance_id(card)
    key = key or common.read_center_key(card)
    if instance_id == nil or key == nil then
      return nil
    end

    return {
      key = key,
      instance_id = instance_id,
      edition = common.read_edition(card),
      sell_cost = common.read_sell_cost(card),
    }
  end

  return owned
end
