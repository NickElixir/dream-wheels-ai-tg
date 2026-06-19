# DW-40 Validation

```text
Role: independent reviewer.

Task:
Review the implementation for <TASK>.

Read first:
- AGENTS.md
- CONTRIBUTING.md
- docs/agent-skills/dreamwheels-review/SKILL.md
- <PRIMARY_DOMAIN_SKILL>
- current git diff and surrounding call paths

Не изменяй код без отдельного запроса.

Проверь:
- bugs and behavioral regressions;
- security/data-loss risks;
- domain invariant violations;
- idempotency, race and retry behavior;
- missing or weak tests;
- migration/env/docs/release gaps;
- scope creep and unrelated changes.

Output findings-first:
1. Findings ordered by severity with file:line
2. Open questions / assumptions
3. Verification run or missing
4. Residual risks

Если findings нет, явно напиши это и перечисли непроверенные риски.
```
