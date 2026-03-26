## Parent PRD

#23

## What to build

Normalize blind and skip-tag state into compact machine-readable arrays. This slice should expose `skip_tags` and `blinds` with raw ids, ordering, state, claimed information, and tag associations where relevant.

## Acceptance criteria

- [ ] `skip_tags` is represented as a structured array ordered for the current ante.
- [ ] `blinds` is represented as a structured array with slot, blind id, state, and tag/claimed data where relevant.
- [ ] The canonical output avoids human-readable blind and tag labels as primary values.
- [ ] Contract coverage verifies ordering and representative blind/skip payloads.

## Blocked by

- Blocked by #30

## User stories addressed

- User story 14
- User story 15
- User story 20
- User story 30
