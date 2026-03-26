## Parent PRD

#23

## What to build

Create the canonical JSON-first observation contract and serializer baseline for the Balatro agent. This slice should establish the approved top-level field order, score object structure, top-level empty-array versus null behavior, lowercase-with-underscores normalization rules for machine-readable fields, and the general array-of-objects style that the rest of the observer will build on.

## Acceptance criteria

- [ ] The canonical observation serializer emits the approved top-level fields in the approved order.
- [ ] `score` is represented exactly as a structured object with `current` and `target`, rather than a formatted string or split scalar fields.
- [ ] Top-level collection fields use empty arrays when empty, while top-level optional object fields use `null` when inactive.
- [ ] Machine-readable ids, categories, and enum-like values are normalized to lowercase-with-underscores where required by the PRD.
- [ ] The pretty output is derived from the canonical JSON contract rather than maintaining its own separate schema.
- [ ] Contract coverage verifies field order, field names, normalization behavior, and top-level empty-array versus null behavior, including the canonical representation of compact note strings.

## Blocked by

None - can start immediately.

## User stories addressed

- User story 1
- User story 2
- User story 3
- User story 7
- User story 29
- User story 30
