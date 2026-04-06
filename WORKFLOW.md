# Coding Agent Workflow

This project is meant to help practice coding-agent collaboration while building a Balatro player.

## Important Clarification

Inside the game, the current architecture is still a normal control loop:

1. observe the state
2. choose an action
3. validate the action
4. execute the action

The "agent workflow" part is about how the code gets built.

## Good Delegation Boundaries

These modules are intentionally small so coding agents can own one area at a time:

- `balatro_ai/models.py`: shared data contracts
- `balatro_ai/interfaces.py`: core boundaries between modules
- `balatro_ai/policy.py`: decision logic and validation rules
- `balatro_ai/runtime.py`: orchestration and logging

## Example Task Splits

- one coding agent extends live-state parsing in the observer module
- one coding agent adds input automation in a new executor module
- one coding agent writes tests for state parsing and action validation
- one coding agent reviews logs and proposes heuristic improvements

## Validation In This Repo

Validation can happen in two places:

- runtime validation: reject bad in-game actions before clicking
- development validation: tests, reviews, and result checks on delegated code changes

Both are useful, but they solve different problems.

