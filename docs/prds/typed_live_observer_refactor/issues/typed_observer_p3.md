## Parent PRD

#34

## GitHub Issue

#37

## What to build

Simplify the runtime loop around the typed observer contract so runtime, policy, validator, and step recording all consume `GameObservation` directly. This slice should keep the validator as the final safety boundary, keep policy output as exactly one `GameAction`, and remove dict-based access and unnecessary demo scaffolding from the main runtime path, as described in the PRD and Phase 3 of `docs/prds/typed_live_observer_refactor/plan.md`.

## Acceptance criteria

- [ ] `Policy.choose_action()` accepts `GameObservation`.
- [ ] `Validator.validate()` accepts `GameObservation` and remains a separate safety boundary before execution.
- [ ] `EpisodeRunner` uses a typed observe/choose/validate/execute/record loop with no dict `.get(...)` flow in the main path.
- [ ] `StepRecord` captures typed observations, chosen actions, and validation results.
- [ ] Demo-only scaffolding is removed from the main runtime module unless it remains clearly necessary for tests or a separate demo entrypoint.

## Blocked by

- Blocked by #36

## User stories addressed

- User story 6
- User story 8
- User story 10
- User story 12
- User story 13
- User story 14
- User story 15
