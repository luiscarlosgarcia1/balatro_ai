## Parent PRD

#23

## What to build

Refit the live Lua exporter and signature coverage so the live observation path emits canonical-oriented field names and gameplay-relevant scalar structure early, instead of forcing broad legacy translation inside Python. This slice should align the live exporter with the canonical observer contract where Phase 1 already established the public shape, while leaving deeper owned-object, market, card-zone, and save-fallback redesign to later issues.

## In scope

- Emit the main gameplay phase canonically through `interaction_phase`.
- Prefer canonical scalar/public field names already established by the baseline contract.
- Remove obviously obsolete split live-only fields once the canonical replacement exists.
- Update signature coverage to follow canonical gameplay-relevant fields rather than legacy split names.
- Reduce Python live-path compatibility bridges that only exist because the exporter still emits old field names.

## Out of scope

- Full save-fallback redesign.
- Final owned-object, market, card-zone, or pack-content schemas beyond what is needed to stop emitting obsolete live-only fields.
- Full internal-model deletion in one pass.

## Acceptance criteria

- [ ] The live exporter no longer requires `phase -> interaction_phase` compatibility for the main gameplay state.
- [ ] Canonical scalar/public field names established by the baseline contract are emitted directly by the live path where available.
- [ ] Signature tests assert canonical gameplay-relevant fields rather than legacy split names.
- [ ] Python live-path compatibility bridges marked as transitional for old exporter fields are reduced where the exporter now emits canonical data directly.
- [ ] Contract tests still pass end to end with live-style fixtures updated to the new exporter shape.
- [ ] The issue explicitly preserves the assumption that save fallback may lag behind the live exporter.

## Blocked by

- Blocked by #30

## User stories addressed

- User story 1
- User story 2
- User story 3
- User story 4
- User story 5
- User story 7
- User story 29
- User story 30
