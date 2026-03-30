## Parent PRD

#34

## GitHub Issue

#36

## What to build

Refactor the observer seam so the app exposes a product-level `BalatroObserver` that returns `GameObservation` directly in normal flow. This slice should remove the dict-shaped observation contract from the observer seam, preserve explicit JSON export only at the edge, and update the public import surface to match the typed live-observer architecture described in the PRD and Phase 2 of `docs/prds/typed_live_observer_refactor/plan.md`.

## Acceptance criteria

- [ ] The public observer name is `BalatroObserver` with no compatibility alias for `BalatroSaveObserver`.
- [ ] `Observer.observe()` returns `GameObservation`, and `ObservationPayload` no longer defines the main observer/runtime contract.
- [ ] `StepRecord` stores typed observations.
- [ ] The normal observer/runtime path no longer serializes observations into dict payloads.
- [ ] `serialize_observation(GameObservation)` remains only as an explicit export/debug helper.

## Blocked by

- Blocked by #35

## User stories addressed

- User story 1
- User story 2
- User story 3
- User story 4
- User story 5
- User story 6
- User story 8
- User story 9
- User story 16
- User story 33
- User story 35
