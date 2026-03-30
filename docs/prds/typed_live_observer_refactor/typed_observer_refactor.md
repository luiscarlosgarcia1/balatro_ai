# PRD: Typed Live Observer Refactor And Runtime Simplification

## Problem Statement

The current Balatro AI scaffold still carries an older observation architecture that is more interwoven than it needs to be. The codebase currently mixes:

- a typed observation model and a dict-shaped observation contract
- a live-export-first direction and a save-file-first public naming/story
- runtime orchestration and demo/mock scaffolding
- policy decision-making and a separate validator stage
- real public behavior tests and tests that mainly lock in transitional structure

From the user's perspective, this creates exactly the kind of code they do not want: old code woven through still-used structural code, plus some compatibility and demo layers that may no longer deserve to exist. The result is extra convolution, slower understanding, more indirection than the project needs, and more difficulty identifying what is truly essential.

The user wants the next architecture pass to optimize for speed, simplicity, and less convolution. They specifically prefer the most lightweight path that removes structural ambiguity, even if that means deleting old code, old public names, or old tests that only protect legacy structure. They do not want a compatibility-preserving cleanup that leaves the old architecture mentally in place.

The key architectural problem is at the observation contract seam:

- the observation layer can already produce a structured in-process model
- that model is currently serialized back into a dict before runtime and policy consume it
- public naming still centers the save-file path even though the live exporter is the intended direction
- the save fallback and transitional schema logic increase code and test burden
- downstream runtime and policy code still depend on the dict-shaped contract, so the legacy bridge remains structural instead of being pushed to the edges

If this seam stays ambiguous, future cleanup will keep stacking on top of both shapes at once. That would preserve the current knot instead of removing it.

## Solution

Refactor the architecture so that typed live observations become the normal in-process contract of the application, while JSON remains only at the Lua-to-Python ingress boundary. Python-side observation serialization, dumps, and export helpers are not part of the target architecture and should be removed unless a concrete external consumer requires them.

This PRD establishes the following core direction:

- the app should treat live-exported observations as the normal supported source
- the app should use a typed `GameObservation`-style model internally
- the JSON boundary where Lua hands live state to Python must remain, but Python-side observation serialization and JSON-shaped internal flow should be removed unless a concrete external consumer requires them
- the current observation service layer that turns typed observations back into dicts must be updated to match the new typed contract
- public save-first naming should be removed and replaced with a generic observer name that matches the intended architecture
- runtime should be simplified while keeping a separate validator boundary for safety and future modification
- policy should remain focused on choosing actions rather than absorbing the validator role
- refactors in any touched area should move code toward smaller files and purpose-based folders instead of extending broad mixed-responsibility files
- nonessential demo/mock scaffolding should be deleted rather than preserved for symmetry
- tests should be replaced in the right order: establish the surviving boundary smoke coverage first, then delete old structure-locking coverage

The desired end state for this first pass is:

1. A generic public `BalatroObserver` concept that reflects the product-level observer rather than the historical save-source implementation.
2. A single typed in-process observation contract used by observer, runtime, and policy code.
3. A simplified runtime loop that consumes typed observations, uses a validator as the final safety boundary before execution, and executes validated actions.
4. A simpler direct observation inspection path for `GameObservation`, with `obs_test` either slimmed down heavily or removed entirely if a cleaner replacement exists, without reintroducing JSON as a Python-side contract.
5. A reduced codebase with less transitional naming, fewer adapters and serialization helpers, fewer parallel shapes, and fewer tests that only defend obsolete structure.

This PRD deliberately chooses clean simplification over long compatibility. The default implementation path is to remove fallback functionality completely and fix any fallout directly. Only if implementation discovers a real blocker that cannot be reasonably removed should a tiny internal adapter be reintroduced, hidden behind the typed observer boundary and prevented from shaping the public architecture.

## User Stories

1. As the Balatro AI developer, I want one canonical in-process observation shape, so that the runtime and policy do not need to reason about both typed objects and dict payloads.
2. As the Balatro AI developer, I want the observation layer to stop converting structured observations back into dicts for normal app flow, so that we remove unnecessary transformation and mental overhead.
3. As the Balatro AI developer, I want the live exporter to be treated as the normal observation source, so that the public architecture reflects the direction the project is actually going.
4. As the Balatro AI developer, I want save-first public naming removed, so that new work does not keep preserving an outdated mental model.
5. As the Balatro AI developer, I want a generic `BalatroObserver`-style public concept, so that callers depend on product behavior rather than historical implementation details.
6. As the Balatro AI developer, I want runtime, policy, and observation code to share the same typed observation contract, so that downstream logic has fewer seams and fewer adapter layers.
7. As the Balatro AI developer, I want the first architecture pass focused on the observation contract seam, so that we untangle the real knot instead of spreading cleanup across the whole repo at once.
8. As the Balatro AI developer, I want this pass to propagate through runtime and policy, so that the old dict contract does not remain structurally important above the observer layer.
9. As the Balatro AI developer, I want the Lua-to-Python handoff to remain JSON-based while unnecessary JSON behavior inside Python is removed, so that the real interchange boundary stays intact without dicts remaining the app core.
10. As the Balatro AI developer, I want the runtime loop to do orchestration only, so that it is easy to read and easier to change safely later.
11. As the Balatro AI developer, I want demo observer and executor scaffolding deleted when nonessential, so that runtime does not keep carrying developer-only structure inside product flow.
12. As the Balatro AI developer, I want the validator to remain as a separate safety boundary before execution, so that later automation changes still have a dedicated place for final execution guards.
13. As the Balatro AI developer, I want policy to keep returning a single `GameAction`, so that the runtime contract stays simple without collapsing safety and decision logic into one place.
14. As the Balatro AI developer, I want no-op behavior expressed through an ordinary action such as `continue`, so that the contract stays simple and explicit.
15. As the Balatro AI developer, I want `StepRecord`-style logging to store typed observations rather than dict payloads, so that evaluation and debugging follow the same app contract.
16. As the Balatro AI developer, I want the current observation service layer updated to stop forcing typed observations back into dicts, so that the typed contract is real instead of cosmetic.
17. As the Balatro AI developer, I want the legacy save fallback removed as the default and decisive plan, so that we stop carrying compatibility complexity by habit.
18. As the Balatro AI developer, I want the save-parser-backed fallback path removed along with the fallback itself, so that the old source path does not linger as a structural influence.
19. As the Balatro AI developer, I want any fallback reintroduced only as a last resort internal adapter for a real blocker, so that callers do not regain source-specific branching.
20. As the Balatro AI developer, I want the manual observation inspection workflow preserved only if it stays simple, so that `obs_test` can be removed when a cleaner direct `GameObservation` inspection path exists.
21. As the Balatro AI developer, I want the refactor to prefer deletion over relocation for obsolete structure, so that cleanup actually reduces the code surface.
22. As the Balatro AI developer, I want tests that mainly protect transitional structure to be removable, so that the test suite stops freezing the architecture in place.
23. As the Balatro AI developer, I want a few strong boundary smoke tests to remain, so that we still have safety around the behavior that survives the cleanup.
24. As the Balatro AI developer, I want replacement smoke coverage to land before broad legacy test deletion, so that cleanup preserves confidence while still achieving a clean break.
25. As the Balatro AI developer, I want tests to verify public behavior rather than helper structure, so that future refactors remain possible.
26. As the Balatro AI developer, I want the resulting architecture to be easier for future coding agents to understand, so that delegated work can target clear boundaries instead of navigating a knot of adapters and legacy names.
27. As the Balatro AI developer, I want old code that is still structurally interwoven to be isolated or removed, so that the repo no longer hides the true execution path behind historical leftovers.
28. As the Balatro AI developer, I want old code that is neither structurally needed nor behaviorally important to be deleted outright, so that the codebase gets smaller instead of merely reorganized.
29. As the Balatro AI developer, I want any touched area to move toward files grouped by functionality and folders grouped by purpose, so that cleanup improves navigability instead of only changing behavior.
30. As the Balatro AI developer, I want giant files such as the current live observer test file to be broken into smaller focused files, but I also want the same regrouping mindset applied to any file we meaningfully refactor.
31. As the Balatro AI developer, I want a soft file-size limit of roughly 500 lines, so that new code stays easier to reason about while still allowing sensible exceptions.
32. As the Balatro AI developer, I want the implementation to choose simplicity over architectural ceremony without turning `GameObservation` into a new giant dumping ground, so that the cleanup replaces the old knot instead of renaming it.
33. As the Balatro AI developer, I want public documentation to match the new typed live-observer reality, so that the repo teaches the correct model to future readers.
34. As the Balatro AI developer, I want the Lua-to-Python `live_state.json` handoff to be the only required JSON observation contract, so that Python-side observation dumps and serializer helpers do not survive by default.
35. As the Balatro AI developer, I want the first pass to remove as many ambiguities as possible, so that the implementer does not have to invent key architectural decisions mid-refactor.

## Implementation Decisions

- The first pass is centered on the observation contract seam, not on a broad full-repo cleanup.
- The in-process observation contract should be typed and object-based.
- The typed in-process contract should propagate through the observer, runtime, policy, and step-record flow in the first pass.
- Dict-shaped or JSON-shaped observations should not remain the primary app contract after this refactor.
- The `live_state.json` handoff from Lua to Python remains a required external boundary.
- Unnecessary JSON conversion, JSON-shaped intermediate representations, and JSON-centric internal helpers on the Python side should be removed as part of this refactor.
- Outside the Lua-to-Python handoff, JSON should not be part of the Python-side observation architecture. Existing debug/export JSON functionality is not protected by default and should be removed unless a concrete external consumer still requires it.
- The current observation service layer must be updated to return or preserve typed observations through normal app flow instead of immediately converting them back into dicts.
- The app should treat the live exporter as the intended normal source of observations.
- Public save-first naming should be removed rather than preserved.
- The preferred public observer name is a generic product-level name such as `BalatroObserver`, not a source-specific name such as `LiveStateObserver`.
- No temporary compatibility alias is planned for the old save-first public observer name in the first pass.
- The default plan is to remove fallback functionality completely rather than preserve it preemptively.
- If implementation discovers a real blocker after fallback removal, the first response should be to fix the caller, flow, or dependency directly rather than restoring the old fallback path.
- Only if that blocker cannot be reasonably eliminated may a tiny internal adapter be reintroduced behind the typed observer contract.
- The save-parser-backed fallback path should be removed as part of the decisive fallback removal, not left behind as dormant structure.
- Save fallback is not to remain a co-equal public architecture, naming driver, or design constraint.
- The runtime loop should be simplified to orchestrate observe, choose, execute, and record behavior.
- The separate `Validator` role should remain in the main runtime architecture as the final safety boundary before execution.
- Policy should keep a simple `choose_action` style interface and return exactly one `GameAction`.
- The policy contract should not be widened to return `None`, a richer decision object, or a parallel acceptance structure in this pass.
- No-op behavior should use an ordinary action such as `continue`.
- `StepRecord` should carry the typed observation, the chosen action, and validation output.
- Demo and mock scaffolding currently embedded in runtime should be deleted if it is not essential to smoke testing or manual development flow.
- The manual observation inspection workflow should survive only in its simplest useful form.
- `obs_test` should be slimmed down only if it remains the cleanest way to inspect `GameObservation`; otherwise it should be removed and replaced with a simpler direct inspection path.
- Any surviving inspection tool should accept typed observations as input and should not require JSON serialization as part of its normal operation.
- Pretty output is a derived view; it should not define the internal runtime contract.
- Any touched area in this refactor should move toward files grouped by functionality and folders grouped by purpose rather than by accident of history.
- Meaningful refactors should prefer splitting mixed-responsibility files into smaller focused files instead of continuing to accrete unrelated behavior in the same place.
- The current giant live observer test file should be treated as a breakup target: replacement tests should be introduced as smaller focused files so later deletion or cleanup of the legacy file becomes easier.
- Use a soft limit of roughly 500 lines per file for new or heavily rewritten files. This limit may be exceeded when it is genuinely the clearest option, but exceeding it should be a deliberate exception rather than the default.
- The refactor should prefer deletion over relocation for nonessential legacy helpers, compatibility bridges, and tests that only freeze transitional structure.
- The test strategy should shift to a small number of high-value boundary smoke tests.
- Replacement smoke coverage should land before broad deletion of legacy tests, so the clean break happens with confidence rather than guesswork.
- Good tests in this refactor verify public behavior of the surviving contracts rather than implementation details or intermediate helper shapes.
- Boundary smoke tests should cover at least typed observation acquisition, observation-service behavior under the typed contract, typed runtime-policy-validator interaction, basic execution flow, direct observation inspection or its replacement, and public import surface.
- Boundary smoke tests should verify that the Lua-to-Python JSON handoff still parses correctly while the internal Python flow no longer depends on JSON-shaped observations.
- The refactor should preserve only the required `live_state.json` ingress boundary; it does not preserve Python-side canonical JSON export helpers by default.
- This pass should not redesign executor automation, game-playing strategy quality, or broader policy intelligence beyond the contract simplification needed to absorb validation into policy.
- This pass should not preserve old architecture solely because it is already present. Legacy structure must justify itself through current behavior or a hard dependency.
- `GameObservation` must not become a new giant dumping ground for every lingering concept. As the cleanup proceeds, any overloaded or awkwardly grouped observation concerns should be split into cleaner typed boundaries instead of merely moving the knot into one large object.
- Clean breaks are preferred. Anything necessary to complete those clean breaks in the touched area should be done as part of the refactor instead of being deferred into a vague later cleanup.
- The implementation should optimize for speed, simplicity, and lower mental overhead, even when that means accepting a clean break from older names, tests, or compatibility assumptions.

## Testing Decisions

- Good tests should verify externally visible behavior at the contract boundaries and avoid locking in transient helper structure.
- The test suite should shrink rather than grow if that is what it takes to stop protecting obsolete architecture.
- The order of operations matters: first add or adapt the small replacement smoke tests for the surviving boundaries, then delete the broad legacy tests that were protecting the old structure.
- New or rewritten tests should be split into smaller focused files instead of accreting more behavior into a single giant test module.
- Keep boundary smoke tests for the behavior that survives:
  - typed observation acquisition from the supported live path
  - observation-service behavior under the typed contract
  - runtime consumption of typed observations with validator participation intact
  - policy returning one executable `GameAction`
  - step recording of typed observations, chosen actions, and validation outcomes
  - direct `GameObservation` inspection or the chosen replacement for `obs_test`
  - public imports and names for the cleaned observer surface
- Remove or rewrite tests that exist primarily to defend dict-first flow, save-first naming, transitional serializer bridges, or demo-runtime scaffolding that is being deleted.
- If a tiny internal adapter must be reintroduced, test only the shared typed observer behavior it produces, not the old public save-first contract.
- The best prior art in the existing repo is the live observer contract coverage and exporter signature regression coverage, but those should be treated as sources to simplify and adapt, not as constraints to preserve verbatim.
- Manual debugging support still matters, so one smoke-level test or equivalent verification path should protect the chosen direct inspection path from silently drifting away from the typed contract.

## Out of Scope

- A full redesign of the entire codebase beyond the observation-contract-driven cleanup required here
- Major strategy improvements to the game-playing policy beyond absorbing validation into policy output
- Executor automation redesign or richer input-automation abstractions
- Screenshot-system redesign beyond what is necessary to remove or replace `obs_test` cleanly
- Preserving backward compatibility for old save-first public naming or old dict-first internal contracts
- Keeping old tests solely because they already exist
- Expanding the observer roadmap beyond what is needed to establish a typed live-observer core and clean downstream contract

## Further Notes

- This PRD is intentionally more decision-complete than the earlier plan because the user explicitly wants ambiguities removed before implementation.
- The user prefers the most lightweight path in terms of mental model and maintenance burden, not necessarily the smallest possible line diff.
- The user is comfortable deleting old code that is still structurally interwoven if the replacement makes the real architecture clearer and simpler.
- The user is also comfortable deleting tests when those tests mainly defend structure they no longer want.
- The user prefers to keep the validator boundary because it improves safety and future modification flexibility.
- The user wants file layout cleanup to happen alongside behavioral cleanup in any touched area, not just the most obviously oversized files.
- The user wants unnecessary JSON functionality removed, but still wants the JSON handoff where Lua passes live state to Python to remain intact. Existing debug/export JSON paths should be removed unless a concrete external consumer still requires them.
- Earlier JSON-first observer work remains relevant only at the Lua-to-Python ingress boundary; this PRD moves the internal architectural center of gravity to typed in-process observations, live-first flow, simpler runtime, and fewer roles.
- If implementation discovers an unavoidable dependency that contradicts one of these defaults, the preferred resolution order is:
  1. remove the dependency
  2. fix the fallout directly at the affected caller or flow
  3. only then add the smallest possible hidden compatibility island behind the new typed contract
- Acceptance criteria for this PRD:
  - runtime and policy no longer consume raw observation dicts as their primary contract
  - the observation service no longer forces typed observations back into dicts during normal app flow
  - the Lua-to-Python JSON handoff still exists and still parses into the typed observation contract
  - unnecessary JSON conversion and JSON-shaped internal flow on the Python side are removed
  - Python-side observation serialization and debug/export JSON tooling are removed unless a concrete external consumer still requires them
  - the main public observer concept no longer uses save-first naming
  - the main runtime path keeps a separate validator safety boundary
  - `obs_test` is either removed cleanly or replaced by a simpler direct `GameObservation` inspection path
  - fallback functionality is removed decisively, including the save-parser-backed path, unless a real blocker forces a tiny hidden adapter
  - nonessential demo or compatibility scaffolding touched by this refactor is deleted rather than preserved
  - replacement smoke tests are in place before broad legacy test deletion
  - meaningful refactors in touched areas regroup code into smaller purpose-based files and folders where that improves clarity
  - new or heavily rewritten files generally stay under the soft 500-line guideline unless there is a clear reason not to
  - `GameObservation` has not become the new catch-all dumping ground for unresolved old structure
  - the surviving tests emphasize boundary behavior instead of historical structure
