---
name: dreamwheels-review
description: Use for Dream Wheels AI code review, PR review, risk assessment, findings-first validation, test selection, security checks, change impact analysis, and deciding whether docs/migrations/env updates are required.
---

# Dream Wheels Review

Use this skill for review, validation, and test planning.

## Read First

- `CONTRIBUTING.md`
- `README.md`
- `.env.example`
- Relevant changed files and tests.
- Domain skill if the change touches payments, data/storage, or runtime/release.

Load references only when needed:

- `references/review-checklist.md` for project-specific review points.
- `references/test-playbook.md` for selecting verification commands.

## Workflow

1. Review the diff first, then inspect surrounding call paths.
2. Present findings first, ordered by severity, with file/line references.
3. Focus on bugs, behavioral regressions, security/data-loss risks, missing tests, migration/env/doc gaps.
4. If no findings, say that explicitly and list residual risks or unrun checks.
5. Do not turn review into a broad refactor unless the user asks.

## Do Not

- Do not approve changes that hide errors with broad `except` and no `logger.exception`.
- Do not ignore secrets, logs, payment callbacks, idempotency, RLS, or migration ordering.
- Do not claim production safety if verification did not run against production-like services.

## Output Shape

Use this order:

1. Findings
2. Open questions / assumptions
3. Verification run or missing
4. Brief change summary only if useful
