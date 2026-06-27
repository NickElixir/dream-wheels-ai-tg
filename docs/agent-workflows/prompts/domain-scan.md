# DW-10 Domain Scan

```text
Role: domain analyst.

Task:
<TASK>

Primary skill:
docs/agent-skills/<SKILL_NAME>/SKILL.md

Read first:
- AGENTS.md
- CONTRIBUTING.md
- docs/agent-skills/<SKILL_NAME>/SKILL.md
- <RELEVANT_REFERENCES>

Не изменяй файлы.

Найди:
- бизнес-инварианты;
- security/data-loss риски;
- требования внешних сервисов;
- затронутые API/data contracts;
- idempotency, race и retry risks;
- неизвестные или спорные предположения;
- обязательные acceptance criteria.

Для поведения внешних сервисов используй official docs.
Не выполняй production-write действия.

Output:
1. Constraints
2. Invariants
3. Risks ordered by severity
4. Required files/docs
5. Acceptance criteria
6. Open questions
```
