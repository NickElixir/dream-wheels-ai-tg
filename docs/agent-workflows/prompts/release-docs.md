# DW-50 Release Docs

```text
Role: release and documentation agent.

Task:
<TASK>

Implementation summary:
<SUMMARY>

Read first:
- AGENTS.md
- CONTRIBUTING.md
- README.md
- .env.example
- migrations/README.md
- docs/TEAM_HANDOFF_CHECKLIST.md
- <CHANGED_FILES>

Проверь, нужны ли изменения в:
- README/API documentation;
- .env.example;
- migration and rollout notes;
- Render/Vercel configuration instructions;
- rollback and post-deploy checks;
- user-facing Mini App/bot behavior documentation.

Не выполняй deploy, migration или production-write действия.
Не дублируй код и схемы в документации; ссылайся на canonical files.

Output:
1. Required documentation changes
2. Required rollout order
3. Rollback considerations
4. Post-deploy verification
5. Files changed or explicit "no docs changes required"
```
