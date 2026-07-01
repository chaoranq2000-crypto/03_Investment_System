# Project Journal

This directory is the collaboration log and guidance system for `03_Investment_System`.
It records project setup, migration, audits, handoffs, guidance, and
cross-session coordination. It is not a source of truth for formal research
claims or live behavior.

## Directory Roles

- `项目日志总索引.md` is the lightweight catalog for listing and selecting logs or guidance without reading bodies.
- `INDEX.md` records the journal system state, active logs, guidance, and archive batches.
- `LOG_CONTROL.md` defines how the user controls reading and writing logs or guidance.
- `CHANGELOG.md` records project-setup and workflow changes in chronological order.
- `guidance/` stores current project rules, build plans, work-system instructions, and skill/workflow guidance.
- `archive/` stores immutable snapshots of legacy seed documents, plans, audits, and setup records.
- `sessions/` stores one working log per Codex session or focused workstream.
- `handoffs/` stores short handoff notes when work is paused, split, or delegated; it also stores `协作日志` for web GPT/ChatGPT after GitHub sync.
- `decisions/` stores lightweight project-building decisions.
- `templates/` stores copy-ready templates for session logs, handoffs, decisions, and guidance.

## Rules

1. If the user gives no logging or guidance instruction, default to no journal reads, no guidance reads, no journal writes, and no guidance writes.
2. If the user wants to choose a log or guidance document, read only `项目日志总索引.md` first.
3. Do not read deeper logs or guidance until a document is selected.
4. Prefer one primary log per conversation/thread.
5. Update `项目日志总索引.md` when adding a new active session, handoff, decision, guidance document, or archive batch.
6. Archive by copy/snapshot first. Do not move live files unless explicitly requested.
7. Put GitHub-sync collaboration logs for web GPT/ChatGPT under `handoffs/`, not `sessions/`.
8. Put current project-wide instructions under `guidance/`, not `sessions/` or `handoffs/`.
