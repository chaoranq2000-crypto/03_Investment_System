# Log Control

This file defines how the user controls whether project journal and guidance
files are read or written. The journal is useful for cross-session continuity,
but it should not take control away from the user.

## User Commands

| Command | Meaning |
|---|---|
| `不读日志` | Do not read project journal files for this task. |
| `不读指引` | Do not read project guidance files for this task. |
| `不写日志` | Do not create or update project journal files for this task. |
| `不写指引` | Do not create or update project guidance files for this task. |
| `只列日志` | Show available logs from `项目日志总索引.md`; do not read log contents yet. |
| `只列指引` / `读指引菜单` | Show available guidance from `项目日志总索引.md`; do not read guidance contents yet. |
| `读日志菜单` | Open `项目日志总索引.md` and let the user choose which log to read. |
| `读日志 <中文日志名>` | Resolve the selected item from `项目日志总索引.md`, then read only that one log or document. |
| `读指引 <中文指引名>` | Resolve the selected item from `项目日志总索引.md`, then read only that one guidance document. |
| `写日志` | Create or update one primary session log for this conversation. |
| `写交接` | Write a handoff note only. |
| `写协作日志` | Write a handoff-style collaboration log under `handoffs/` for web GPT/ChatGPT after GitHub sync. |
| `写决策` | Write a decision record only. |
| `写指引` / `写项目规则` / `写项目计划` | Write or update a living guidance document under `guidance/`. |

## Default Behavior

If the user gives no logging or guidance instruction:

1. Do not read project journal or guidance files, including indexes.
2. Do not create or update project journal or guidance files.
3. Work from the current user request, live repository files, and validation commands.
4. If older logs or guidance may help, mention the likely candidate if known, but wait for `读日志 <中文日志名>`, `读指引 <中文指引名>`, `只列日志`, or `只列指引` before reading.

## Guidance Documents

- Put current project-building plans, project rules, work-system instructions, and skill/workflow guidance under `guidance/`.
- Keep `guidance/` for living instructions. Put superseded plans, old setup records, and historical snapshots under `archive/`.
- Use `project_journal/guidance/` for project-wide instructions that may affect multiple skills or workflows.
- Use `.codex/skills/<skill-name>/references/` for reference material that belongs to one specific reusable skill.

## One Conversation, One Log

- Default to one primary session log per conversation/thread.
- If the conversation already has a session log, append to it instead of creating a new session log.
- Put small decisions, validation summaries, and next steps inside the same session log.
- Create separate `handoffs/`, `decisions/`, or `guidance/` files only when the user asks for them.
- Treat `协作日志` as a separate `handoffs/` file by default when it is meant for web GPT/ChatGPT to read after the project is pushed to GitHub.

## Naming Rules

- Prefer Chinese semantic names for session, handoff, decision, and guidance documents.
- Keep the date prefix for sorting: `YYYY-MM-DD-中文语义主题.md`.
- Avoid vague names such as `update`, `misc`, `fix`, or `log1`.

## Safety

- Never write secrets or local tokens into project journal or guidance files.
- Never treat logs, guidance, or archives as formal evidence.
- If a selected log or guidance document conflicts with live config, verify live config first.
- Do not read full log or guidance bodies merely to discover what exists; use `项目日志总索引.md`.
