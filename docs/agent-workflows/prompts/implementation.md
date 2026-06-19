# DW-30 Implementation

```text
Role: implementation agent.

Goal:
<GOAL>

Branch/base:
<BRANCH_BASE>

Read first:
- AGENTS.md
- CONTRIBUTING.md
- docs/agent-skills/<PRIMARY_SKILL_NAME>/SKILL.md
- <RELEVANT_FILES>

Scope:
- May change: <ALLOWED_FILES_OR_MODULES>
- Must not change: <EXCLUDED_FILES_OR_MODULES>

Constraints:
- Preserve: <DOMAIN_INVARIANTS>
- Meet: <ACCEPTANCE_CRITERIA>
- Do not touch secrets or .env.
- Do not apply migrations or call production APIs.
- Do not perform unrelated refactoring.
- Add/update tests for changed behavior.

Verification:
- ruff check .
- ruff format --check .
- <RELEVANT_PYTEST_COMMANDS>
- If a command cannot run, report why.

Output:
1. Summary
2. Changed files
3. Tests and results
4. Assumptions
5. Residual risks
```
