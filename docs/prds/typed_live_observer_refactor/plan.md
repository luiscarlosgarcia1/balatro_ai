# Plan: Typed Live Observer Refactor And Runtime Simplification

> Source PRD: `docs/prds/typed_live_observer_refactor/typed_live_observer_refactor.md`

## Summary

- There are no existing issue docs for this PRD, so the work is sliced directly from the PRD and the current repo seams.
- Use thin resumable phases rather than broad milestones.
- Remove the dedicated manual inspection tool instead of preserving `obs_test.py`.
- End state: the app treats live-exported state as the only supported observer source, uses `GameObservation` as the in-process contract everywhere, keeps JSON only at the Lua-to-Python ingress, preserves a separate validator boundary, and removes save-first naming, fallback code, and Python-side observation serializers.

## Durable Decisions

- `GameObservation` is the only in-process observation contract after this refactor.
- `Observer.observe()` returns `GameObservation`, not a dict payload.
- `Policy.choose_action()` and `Validator.validate()` both accept `GameObservation`.
- `StepRecord.observation` stores `GameObservation`.
- The public observer name is `BalatroObserver`; no compatibility alias for `BalatroSaveObserver`.
- Save fallback removal is the default path, not deferred cleanup.
- The only supported observer ingress is `live_state.json -> LiveObservationParser -> GameObservation`.
- No Python-side observation serializer or JSON export helper is part of the target architecture; add one later only if a concrete external boundary truly needs it.
- No dedicated manual inspection tool survives this refactor.
- If fallback deletion discovers a blocker, fix the caller or flow first; only then allow the smallest possible hidden adapter.

## Ordered Issue Sequence

1. `PRD slice: replacement smoke tests and public-contract lock`
   Why now: the current safety net is concentrated in `tests/test_live_observer_contract.py`, so cleanup needs smaller surviving tests before structural deletion starts.
   Depends on: none.

2. `PRD slice: typed observer seam and public rename`
   Why now: the observation contract seam is the architectural knot called out by the PRD and has to move before runtime cleanup becomes real.
   Depends on: replacement smoke tests.

3. `PRD slice: typed runtime, policy, validator, and step recording`
   Why now: once the observer seam is typed, the runtime loop can be simplified without carrying dict adapters or mixed responsibilities.
   Depends on: typed observer seam and public rename.

4. `PRD slice: fallback removal and observer-surface purge`
   Why now: once typed contracts and replacement tests are in place, save fallback can be removed decisively instead of partially.
   Depends on: typed runtime, policy, validator, and step recording.

5. `PRD slice: final legacy purge, docs alignment, and file breakup`
   Why now: the last phase should mostly be deletion, regrouping, and doc cleanup after the real runtime path has already switched over.
   Depends on: fallback removal and observer-surface purge.

## Phase 1: Replacement Smoke Tests And Contract Lock

**Issues**: PRD-derived slice

### Goal

Create focused tests for the behavior that survives the refactor, so later phases can delete legacy structure safely.

### Why this phase now

The repo currently concentrates most observer behavior in one giant contract suite. Smaller replacement tests need to exist before broad deletion starts.

### Implementation notes

- Add focused smoke tests for:
  - live `live_state.json` parsing into `GameObservation`
  - public observer imports
  - typed runtime-policy-validator interaction
  - typed `StepRecord`
  - missing or invalid live-state input
- Freeze `tests/test_live_observer_contract.py` as a breakup target; do not add new coverage there.
- Keep new test modules focused and small rather than recreating another giant file.

### Acceptance criteria

- [ ] Surviving observer/runtime behavior is covered by focused smoke tests.
- [ ] No new behavior is added to `tests/test_live_observer_contract.py`.
- [ ] The new tests are sufficient to support later deletion of dict-first and save-fallback coverage.

### Read before starting

- Source PRD
- `tests/test_live_observer_contract.py`
- `balatro_ai/observation/live_parser.py`
- `balatro_ai/observation/canonical.py`

## Phase 2: Typed Observer Seam And Public Rename

**Issues**: PRD-derived slice

### Goal

Make the observer seam typed end to end and expose the product-level `BalatroObserver` name publicly.

### Why this phase now

This is the central contract change from the PRD. Runtime and cleanup work should build on the final seam, not on another temporary bridge.

### Implementation notes

- Replace the public `BalatroSaveObserver` concept with `BalatroObserver`.
- Change `Observer.observe()` to return `GameObservation`.
- Remove `ObservationPayload` from observer, runtime, policy, validator, and `StepRecord`.
- Remove Python-side observation serializers and JSON export helpers unless a concrete external caller in the repo still requires one right now.
- Update `balatro_ai` and `balatro_ai.observation` exports to expose `BalatroObserver` and remove save-first names.

### Acceptance criteria

- [ ] Public imports expose `BalatroObserver`.
- [ ] Observer interfaces and step records use `GameObservation`.
- [ ] Normal observer/runtime flow no longer depends on serialized dict payloads.
- [ ] Python-side observation JSON serialization is removed unless a concrete external caller still requires it.

### Read before starting

- Source PRD
- `balatro_ai/observation/service.py`
- `balatro_ai/interfaces.py`
- `balatro_ai/models.py`

## Phase 3: Typed Runtime, Policy, Validator, And Step Recording

**Issues**: PRD-derived slice

### Goal

Simplify the runtime loop so it orchestrates typed observation, decision, validation, execution, and recording without dict adapters.

### Why this phase now

Once the observer seam is typed, runtime simplification becomes straightforward and can remove mixed responsibilities cleanly.

### Implementation notes

- Update `Policy.choose_action()` and `Validator.validate()` to accept `GameObservation`.
- Simplify `EpisodeRunner` to a typed observe/choose/validate/execute/record loop with no dict `.get(...)` access.
- Keep validator as the final safety boundary and keep policy output as exactly one `GameAction`.
- Keep `continue` as the ordinary no-op action.
- Remove demo-only scaffolding from the main runtime module unless it still serves tests or a clearly separate demo module.

### Acceptance criteria

- [ ] Runtime, policy, and validator consume `GameObservation`.
- [ ] `StepRecord` stores typed observations.
- [ ] The main runtime module no longer mixes product flow with unnecessary demo scaffolding.

### Read before starting

- Source PRD
- `balatro_ai/runtime.py`
- `balatro_ai/policy.py`
- `balatro_ai/interfaces.py`

## Phase 4: Fallback Removal And Observer-Surface Purge

**Issues**: PRD-derived slice

### Goal

Remove save fallback and other observer baggage so the live typed observer becomes the only normal supported path.

### Why this phase now

This phase should happen only after the typed seam and replacement tests exist, so fallback removal is a clean break rather than a risky partial transition.

### Implementation notes

- Remove save fallback from the normal observer path.
- Delete `save_parser.py`, `save_decoder.py`, and their public exports unless an implementation blocker proves a tiny hidden adapter is unavoidable.
- Define observer failure behavior explicitly:
  - `BalatroObserver.observe()` raises `FileNotFoundError` when `live_state.json` is missing.
  - `BalatroObserver.observe()` raises `ValueError` when `live_state.json` exists but cannot be parsed into a valid observation.
- Remove `LightweightCapturePlan` coupling from the observer service and remove capture-related public exports if they only existed for `obs_test.py`.

### Acceptance criteria

- [ ] The only supported observer ingress is `live_state.json -> LiveObservationParser -> GameObservation`.
- [ ] Save fallback code and save-first exports are removed.
- [ ] Observer failure behavior is explicit and tested.

### Read before starting

- Source PRD
- `balatro_ai/observation/service.py`
- `balatro_ai/observation/api.py`
- `balatro_ai/observation/__init__.py`

## Phase 5: Final Legacy Purge, Docs Alignment, And File Breakup

**Issues**: PRD-derived slice

### Goal

Finish the refactor by deleting obsolete tooling and updating docs and test layout to match the new typed live-observer architecture.

### Why this phase now

Once the real runtime path is already switched over, the remaining work should mostly be deletion, regrouping, and documentation cleanup.

### Implementation notes

- Delete `obs_test.py` and its README/mod README workflows; do not replace it with another dedicated inspection command.
- Remove any remaining Python-side observation JSON helpers, dumps, and serializer-driven workflows unless a concrete external boundary still requires them.
- Replace the giant contract suite with smaller focused test modules.
- Remove tests that exist mainly to protect:
  - dict-first runtime/policy flow
  - save fallback behavior
  - save-first naming
  - `obs_test.py` formatting/capture behavior
- Regroup touched code into smaller purpose-based modules, keeping new or heavily rewritten files near the soft 500-line target where practical.
- Update documentation so the repo teaches the typed live-observer architecture instead of the old save-first or dict-first model.

### Acceptance criteria

- [ ] `obs_test.py` and its dependent workflows are removed.
- [ ] Tests emphasize surviving boundary behavior instead of historical structure.
- [ ] Touched docs and module layout reflect the typed live-observer architecture.

### Read before starting

- Source PRD
- `README.md`
- `mods/live_state_exporter/README.md`
- `tests/test_live_observer_contract.py`

## Resume Instructions

To implement a phase in a fresh chat, read this plan section, the source PRD, and the linked code/tests first. Treat the phases as PRD-derived slices, preserve the typed observer contract as the central decision, and prefer deletion over compatibility when the replacement behavior is already covered.
