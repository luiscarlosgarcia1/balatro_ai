# T-51: BalatroBot composition behind the Watchable session seam

## Outcome: Implement

Create a scoped follow-up implementation ticket for a deep `BalatroBotSession`
adapter. This exploration does not authorize or include that refactor.

The adapter's small interface should let the Watchable session start and stop a
managed instance, obtain its ready `Bridge`, and read the instance log path.
It must take the diagnostics stream at construction (or start) so its
implementation, rather than the Watchable session, contains coroutine
invocation and BalatroBot launcher stdout redirection. Configuration from the
`BALATROBOT_*` environment, the lazy BalatroBot import, `Config` construction,
`BalatroInstance` creation, `BalatroClient` creation, and the `asyncio.run`
calls belong behind that interface.

The Watchable session remains the module at the public seam. It continues to
own the versioned JSONL lifecycle contract, `launching` / `bridge_ready` /
`session_ready` ordering, Round Tactics reset and policy driving, terminal
outcome mapping, inspection-mode waiting, failure phase mapping, and the
decision of when to start or stop the adapter.

## Evidence

`watchable_session.py` currently combines two unrelated implementations:

1. Watchable-session behavior: lifecycle events, Round Tactics driving,
   settlement, and cleanup policy.
2. BalatroBot composition: environment configuration, optional dependency
   import, instance lifecycle, bridge creation, event-loop crossing, and
   launcher-output routing.

The first is specific to the Watchable session's external interface; the
second is a true-external dependency integration. Its five private helpers
already expose a shallow, accidental test surface. In particular,
`test_watchable_session.py` patches `_create_instance`, `_create_bridge`,
`RoundTacticsEnvironment`, `DeterministicLegalHeuristic`, and UUID generation
to reach lifecycle behavior. A fake managed instance and fake bridge are
already a test adapter in substance, while the production BalatroBot
composition is the production adapter.

BalatroBot itself has separate `BalatroInstance`, `BalatroClient`, and
`Config` classes, but none represents this repository's required composition:
visible launch diagnostics plus a ready synchronous bridge. A local adapter is
therefore not a pass-through wrapper; it hides the coordination that its
callers should not learn.

## Interface alternatives considered

### A. One-call launch function

`open_balatrobot_session(session_id, diagnostics) -> ManagedBalatroSession`

This has maximum apparent depth, but it makes the adapter responsible for the
moment a bridge becomes ready. The Watchable session would no longer naturally
place its `bridge_ready` JSONL event after its explicit health check. Returning
an already-ready bridge also obscures the distinct launch and bridge failure
phases. It is too compressed for the public lifecycle contract.

### B. Lifecycle adapter (recommended)

`BalatroBotSession.start() -> Bridge`, `BalatroBotSession.stop() -> None`, and
`log_path`.

The Watchable session emits `launching`, calls `start`, verifies `health` on
the returned bridge, then emits `bridge_ready`. It calls `stop` on settlement
and on failure. This gives callers three facts to learn (start, stop, log
path), while hiding all BalatroBot-specific composition. Error modes remain
natural: `start` and `stop` propagate the underlying failure, and the
Watchable session maps them to its existing lifecycle phases.

### C. Broad factory plus injected primitives

A factory receiving configuration, event-loop runner, stdout redirector,
instance constructor, and bridge constructor would maximize flexibility. It
would also export every implementation decision currently making the module
shallow. It has little leverage and poor locality, so it should not be
implemented.

## Depth, locality, and deletion test

Alternative B is deep at the adapter interface: callers receive a managed
BalatroBot session and bridge without knowing how imports, environment values,
configuration, lifecycle coroutines, or stdout routing work. The production
adapter and a fake adapter make the seam real, not hypothetical. Tests can
cross the same seam with a fake `BalatroBotSession` instead of patching private
implementation names, increasing locality for integration behavior.

If the adapter were deleted, the coordination of BalatroBot configuration,
optional import, instance construction, lifecycle execution, diagnostics
routing, bridge construction, and teardown would reappear in each visible
launch path. The repository currently has one production Watchable launch
path, so this is modest current caller leverage; however, it is enough
leverage because that path has a stable public lifecycle contract and a
separate fake adapter is already required by the tests. The adapter also
prevents a future evaluator or experiment launch path from duplicating this
true-external integration.

## Dependency and sibling decision check

BalatroBot is a true external dependency, so the follow-up should define an
injected adapter at this seam and use a fake adapter in Watchable-session tests.
The real adapter remains the only place importing BalatroBot. Do not expose an
adapter merely to inject Round Tactics or policy behavior; those are separate
concerns.

T-50 was re-read before this conclusion. It has no recorded decision or
comments yet. This outcome does not assume its episode-driving direction and
does not change T-50's stated ownership: Watchable session still drives the
visible lifecycle and retains its settlement/outcome mapping.

## Follow-up scope

The implementation ticket should introduce the adapter and fake-adapter test
surface, migrate Watchable-session tests away from private BalatroBot helper
patching, and preserve the current JSONL trace and cleanup behavior. It should
not combine this work with the T-50 episode-driving exploration.
