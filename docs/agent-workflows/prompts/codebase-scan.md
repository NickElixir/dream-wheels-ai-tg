# DW-20 Codebase Scan

```text
Role: codebase analyst.

Task:
<TASK>

Read first:
- AGENTS.md
- CONTRIBUTING.md
- README.md
- <RELEVANT_FILES>

Не изменяй файлы.

Проследи текущий call flow и найди:
- entry points;
- затронутые модули и ownership boundaries;
- текущие tests;
- migrations, env и docs impact;
- behavioral regressions;
- partial-failure paths;
- файлы, которые implementation agent не должен трогать.

Output:
1. Current flow
2. Change surface
3. Relevant file list
4. Suggested implementation scope
5. Required tests and verification
6. Risks / unknowns
```
