## Parent PRD

#34

## GitHub Issue

#38

## What to build

Remove save fallback and related observer baggage so the live typed observer becomes the only supported normal observation path. This slice should make `live_state.json -> LiveObservationParser -> GameObservation` the only ingress, define explicit failure behavior for missing or invalid live-state input, and remove save-parser/save-decoder and capture-related observer coupling where they only exist to preserve the old architecture, following the PRD and Phase 4 of `docs/prds/typed_live_observer_refactor/plan.md`.

## Acceptance criteria

- [ ] Save fallback is removed from the normal observer path.
- [ ] `save_parser.py`, `save_decoder.py`, and their public exports are deleted unless a real blocker requires the smallest possible hidden adapter.
- [ ] `BalatroObserver.observe()` raises `FileNotFoundError` when `live_state.json` is missing.
- [ ] `BalatroObserver.observe()` raises `ValueError` when `live_state.json` exists but cannot be parsed into a valid observation.
- [ ] Capture-plan coupling and related public exports are removed from the observer service if they only supported `obs_test.py`.

## Blocked by

- Blocked by #37

## User stories addressed

- User story 17
- User story 18
- User story 19
- User story 27
- User story 28
