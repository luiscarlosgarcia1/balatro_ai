## Parent PRD

#34

## GitHub Issue

#39

## What to build

Finish the refactor by deleting obsolete inspection tooling, breaking up the giant legacy contract suite, and updating docs and file layout so the repo teaches the typed live-observer architecture directly. This slice should remove `obs_test.py`, remove any remaining Python-side observation JSON tooling that survived earlier phases, and complete the doc/test cleanup described in the PRD and Phase 5 of `docs/prds/typed_live_observer_refactor/plan.md`.

## Acceptance criteria

- [ ] `obs_test.py` and its dependent README or mod-README workflows are removed without replacement by another dedicated inspection command.
- [ ] The giant legacy contract suite is replaced by smaller focused test modules that protect surviving boundary behavior instead of historical structure.
- [ ] Tests that mainly defend dict-first flow, save fallback, save-first naming, serializer bridges, or `obs_test.py` behavior are removed or rewritten.
- [ ] Touched docs describe the typed live-observer architecture, with JSON limited to the Lua-to-Python ingress rather than Python-side observation tooling.
- [ ] Meaningfully rewritten files move toward smaller purpose-based modules and the soft file-size guideline where practical.

## Blocked by

- Blocked by #38

## User stories addressed

- User story 20
- User story 21
- User story 22
- User story 25
- User story 29
- User story 30
- User story 31
- User story 33
