## Parent PRD

#34

## GitHub Issue

#35

## What to build

Add the replacement smoke-test baseline for the typed live-observer refactor. This slice should establish small focused tests for the behavior that survives the cleanup, so later phases can remove save-first naming, dict-first runtime flow, and legacy scaffolding without losing confidence. It should cover the surviving contract boundaries described in the PRD and the Phase 1 section of `docs/prds/typed_live_observer_refactor/plan.md`.

## Acceptance criteria

- [ ] Focused smoke tests cover live `live_state.json` parsing into `GameObservation`.
- [ ] Focused smoke tests cover the surviving public observer import surface and typed `StepRecord` behavior.
- [ ] Focused smoke tests cover typed runtime-policy-validator interaction and explicit JSON export from a typed observation.
- [ ] Missing or invalid live-state input has smoke-level coverage.
- [ ] No new behavior is added to `tests/test_live_observer_contract.py`; it remains a breakup target instead.

## Blocked by

None - can start immediately.

## User stories addressed

- User story 22
- User story 23
- User story 24
- User story 25
- User story 26
