## Parent PRD

#23

## What to build

Export and normalize the owned run objects that shape the agent's persistent state: jokers, consumables, shop vouchers, active vouchers, skip tags, and active tags. This slice should move these objects to compact raw-id-first schemas and keep vouchers separate from the general shop market. `shop_vouchers` should remain an array even when there is only one current shop voucher.

## Acceptance criteria

- [ ] `jokers`, `consumables`, `shop_vouchers`, `vouchers`, `skip_tags`, and `tags` are represented as structured arrays in the canonical JSON contract.
- [ ] `shop_vouchers` remains an array even when the current shop contains only a single voucher.
- [ ] Jokers and consumables include relevant structural properties like rarity, edition, stickers, sell price, and debuff state only when meaningful.
- [ ] Shop vouchers are not duplicated inside `shop_items`.
- [ ] Contract coverage verifies ordering and non-duplication behavior.

## Blocked by

- Blocked by #30

## User stories addressed

- User story 10
- User story 11
- User story 12
- User story 13
- User story 14
- User story 15
- User story 26
- User story 27
- User story 28
- User story 30
