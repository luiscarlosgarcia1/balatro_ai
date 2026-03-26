## Parent PRD

#23

## What to build

Export and normalize the core run-state scalars that the AI needs for tempo and economy decisions. This slice should carry `source`, `state_id`, `interaction_phase`, raw blind/deck/stake ids, score, money, hands, discards, ante, round count, joker slots/count, consumable slots, reroll cost, interest, inflation, hand size, and notes all the way through the exporter, parser, canonical JSON output, and debug view. It should also lock in operational note entries like `screenshot_status` and `seen_at` when those are emitted by the observer.

## Acceptance criteria

- [ ] The canonical output includes the run-state scalar fields approved in the PRD using raw ids where required.
- [ ] `stake_id` preserves the raw game-exported identifier in the most direct efficient form available instead of being remapped to a prettier label.
- [ ] `score` is emitted as the exact `{current, target}` object shape used by the canonical schema.
- [ ] Notes remain string entries in `notes`, including operational entries like `screenshot_status` and `seen_at` when emitted.
- [ ] The preferred operational note format is compact strings such as `screenshot_status=true` and `seen_at=<iso8601 timestamp>`.
- [ ] The pretty output derives these scalars from the canonical JSON contract rather than a separate display-only structure.
- [ ] Contract coverage verifies representative scalar payloads, note entries, and omission rules.

## Blocked by

- Blocked by #30

## User stories addressed

- User story 4
- User story 5
- User story 6
- User story 8
- User story 9
- User story 18
- User story 29
- User story 30
