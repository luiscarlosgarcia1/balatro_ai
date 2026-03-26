## Parent PRD

#23

## What to build

Export and normalize the active card zones and selection state that the AI needs for play decisions. This slice should cover `cards_in_hand`, `selected_cards`, `highlighted_card`, and `cards_in_deck`, with explicit suit/rank fields and stable suit-and-rank ordering for both hand and deck output using the agreed exact order.

## Acceptance criteria

- [ ] `cards_in_hand` and `cards_in_deck` are arrays of structured card objects rather than mixed count-plus-text output.
- [ ] `cards_in_hand` and `cards_in_deck` use the exact agreed ordering: suits `clubs`, `diamonds`, `hearts`, `spades`; ranks `ace`, `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, `10`, `jack`, `queen`, `king`.
- [ ] Card objects expose structural fields such as `card_key`, `card_kind`, `suit`, `rank`, `rarity`, `enhancement`, `edition`, `seal`, `stickers`, `facing`, `cost`, `sell_price`, and `debuffed` when relevant.
- [ ] `selected_cards` is represented as a lightweight-reference array and uses `[]` when nothing is selected.
- [ ] `highlighted_card` is represented as a lightweight reference using a compact shape such as `{zone, card_key}` or `{zone, joker_key}`, and uses `null` when nothing is highlighted.
- [ ] Contract coverage verifies suit-and-rank ordering for both hand and deck zones, lightweight reference shape, and empty-array versus null behavior for selection state.

## Blocked by

- Blocked by #30

## User stories addressed

- User story 21
- User story 22
- User story 23
- User story 24
- User story 25
- User story 27
- User story 30
