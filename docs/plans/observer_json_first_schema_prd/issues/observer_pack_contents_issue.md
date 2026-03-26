## Parent PRD

#23

## What to build

Add the dedicated `pack_contents` object for opened packs. This slice should expose the pack metadata and visible pack cards after `shop_items`, without mixing pack interaction state into the ordinary market list.

## Acceptance criteria

- [ ] `pack_contents` is emitted as a structured object containing pack metadata plus the visible pack cards.
- [ ] The pack cards use the same card object shape as other visible card zones where possible.
- [ ] `pack_contents` appears after `shop_items` in the canonical top-level order.
- [ ] Contract coverage verifies representative pack-open payloads and skip metadata.

## Blocked by

- Blocked by #30
- Blocked by #25

## Sequencing Note

Exporter-first cleanup in #31 should reduce the live-path translation work in this slice, but this issue only needs a hard dependency on that refit if its implementation starts changing live exporter field names directly.

## User stories addressed

- User story 19
- User story 20
- User story 27
- User story 30
