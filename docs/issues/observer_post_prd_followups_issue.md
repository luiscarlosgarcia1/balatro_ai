## Purpose

Track observation-layer follow-up ideas that should be revisited only after all seven phases of the JSON-first observer PRD are complete.

This is a living backlog document for later cleanup, simplification, and expansion ideas. It is explicitly out of scope for the current PRD and its active issue sequence, and it must not be treated as blocking, redefining, or amending the current seven planned phases.

## Status

- Not part of the current `observer_json_first_schema_prd` delivery scope.
- Not to be considered when implementing the current PRD issues unless explicitly pulled forward in a later decision.
- Safe to edit over time as new post-PRD thoughts come up.

## Initial Follow-Ups

- Remove `joker_count`; it can be derived from `jokers`.
- Merge `shop_vouchers` into the main visible shop payload so vouchers are represented like other shop-visible items.
- Remove the `skip_tags` payload; it can be derived from `blinds`.
- Audit every object and remove fields that can be derived from the item's key. Candidate examples include `kind`, `name`, `rarity`, blind `slot`, and likely others still to be identified.
- Reconsider `shop_discounts`; its long-term purpose is still unclear.
- Reconsider `interest` and `inflation`; their long-term purpose is still unclear.
- Revisit whether `selected_cards` and `highlighted_card` are actually the same concept.
- Remove `cost` and `sell_price` from `cards_in_hand` and `cards_in_deck`; those keys should not appear on hand/deck card objects.
- Add a `run_info` payload that includes played-hand levels plus their chips and multiplier status.

## Desired Order After The Current PRD

Once all seven phases of the current observer PRD are complete:

1. Refactor and improve the codebase architecture before starting these follow-up payload changes.
2. Work through the post-PRD observer follow-ups in this backlog.
3. When all observer issues are complete and the observer payload output feels right, create a new root `README.md` for the project.
4. At that same finalization stage, add `balatro_ai/observation/notes.md` to capture the constraints and lessons learned during observer development so future changes do not repeat the same mistakes.
5. After that closeout work is done, merge the branch into `main`.

## Later Use

When the current observer PRD is fully complete, this issue can be split into fresh scoped issues or a follow-up PRD. Until then, treat it as notes for future direction only.
