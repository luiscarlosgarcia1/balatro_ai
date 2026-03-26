## Parent PRD

#23

## What to build

Refit the canonical shop market view so `shop_items` becomes the efficient raw-id-first list of buyable non-voucher items, with `shop_discounts` modeled explicitly and booster packs represented through the same market structure. This slice should also preserve cost, sell price where relevant, other structural item metadata, and the visible UI order of shop items.

## Acceptance criteria

- [ ] `shop_items` is the canonical buyable market list for non-voucher shop items.
- [ ] `shop_items` preserves the visible UI order of market items rather than re-sorting them into a different machine-only order.
- [ ] `shop_discounts` is exposed explicitly when available.
- [ ] Shop items preserve structural fields like cost, edition, enhancement, seal, consumable kind, stickers, and sell price when relevant.
- [ ] Contract coverage verifies that shop vouchers are excluded from `shop_items`.

## Blocked by

- Blocked by #30

## User stories addressed

- User story 16
- User story 17
- User story 18
- User story 28
- User story 30
