# Project Guidance

This directory stores living project instructions for `03_Investment_System`.
Use it for project-building plans, project rules, setup notes, workflow
contracts, and guidance that Codex should consult when the user explicitly asks
to follow project guidance.

## Put Here

- Current project construction plans.
- Project rules and collaboration boundaries.
- Work-system setup notes.
- Skill or workflow design guidance that applies across the project.
- Codex operating instructions that are too project-specific for global memory.

## Do Not Put Here

- Raw session transcripts; use `sessions/`.
- Handoff summaries for another GPT context; use `handoffs/`.
- Accepted single decisions; use `decisions/`.
- Superseded plans or historical snapshots; use `archive/`.
- Reference material that belongs to one reusable skill; use `.codex/skills/<skill-name>/references/`.
- Secrets, tokens, or private local config.

## Naming

Use dated Chinese semantic names:

- `YYYY-MM-DD-项目规则.md`
- `YYYY-MM-DD-项目构建计划.md`
- `YYYY-MM-DD-skill工作流指引.md`
- `YYYY-MM-DD-Codex协作规则.md`

Register each guidance file in `project_journal/项目日志总索引.md` under `项目指引索引`.
