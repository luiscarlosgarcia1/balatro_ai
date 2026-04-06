# Docs Layout

This directory keeps planning artifacts grouped by PRD so a fresh chat can find the right context quickly.

## Current Structure

- `docs/prds/` contains one folder per PRD.
- `docs/prds/<name>/observer_json_prd.md` is the PRD itself.
- `docs/prds/<name>/plan.md` is the canonical implementation plan for that PRD.
- `docs/prds/<name>/prd_followups.md` holds follow-up notes that still belong to that PRD package.
- `docs/issues/` is reserved for general purpose issue docs.

## Convention

- Prefer `docs/prds/<name>/` as the home for a PRD and its closely related planning artifacts.
- Keep the PRD, plan, and PRD-scoped follow-ups together in the same folder.
- Reference GitHub issue numbers in plans instead of local issue-doc filenames when the plan should survive issue-doc cleanup.
- Move only clearly mapped artifacts into a PRD folder; leave ambiguous or legacy items in `docs/issues/` until they are rehomed intentionally.