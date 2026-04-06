-- Entity cloners for cards, jokers, consumables, packs, and references.
return function(values, primitives)
  local entities = {}

  local as_table = values.as_table
  local to_number = values.to_number
  local clone_mapped_array = primitives.clone_mapped_array
  local optional_or_null = primitives.optional_or_null
  local required_or = primitives.required_or

  function entities.clone_card(card)
    card = as_table(card) or {}
    return {
      card_key = card.card_key,
      instance_id = card.instance_id,
      enhancement = optional_or_null(card.enhancement),
      edition = optional_or_null(card.edition),
      seal = optional_or_null(card.seal),
      facing = optional_or_null(card.facing),
      debuffed = card.debuffed == true,
      cost = optional_or_null(card.cost),
      sell_cost = optional_or_null(card.sell_cost),
    }
  end

  function entities.clone_cards(source)
    return clone_mapped_array(source, entities.clone_card)
  end

  function entities.clone_joker(joker)
    joker = as_table(joker) or {}
    return {
      key = joker.key,
      instance_id = joker.instance_id,
      eternal = joker.eternal == true,
      perishable = joker.perishable == true,
      rental = joker.rental == true,
      perish_tally = optional_or_null(joker.perish_tally),
      edition = optional_or_null(joker.edition),
      debuffed = joker.debuffed == true,
      cost = optional_or_null(joker.cost),
      sell_cost = optional_or_null(joker.sell_cost),
    }
  end

  function entities.clone_jokers(source)
    return clone_mapped_array(source, entities.clone_joker)
  end

  function entities.clone_consumable(consumable)
    consumable = as_table(consumable) or {}
    return {
      key = consumable.key,
      instance_id = consumable.instance_id,
      edition = optional_or_null(consumable.edition),
      cost = optional_or_null(consumable.cost),
      sell_cost = optional_or_null(consumable.sell_cost),
    }
  end

  function entities.clone_consumables(source)
    return clone_mapped_array(source, entities.clone_consumable)
  end

  function entities.clone_voucher(voucher)
    voucher = as_table(voucher) or {}
    return {
      key = voucher.key,
      cost = required_or(to_number(voucher.cost), 0),
    }
  end

  function entities.clone_pack(pack)
    pack = as_table(pack) or {}
    return {
      key = pack.key,
      instance_id = pack.instance_id,
      cost = optional_or_null(pack.cost),
    }
  end

  function entities.clone_references(source)
    return clone_mapped_array(source, function(reference)
      return {
        zone = reference.zone,
        instance_id = reference.instance_id,
        key = reference.key,
      }
    end)
  end

  return entities
end
