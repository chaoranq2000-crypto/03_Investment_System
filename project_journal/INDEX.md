# Project Journal Index

Project: `03_Investment_System`
Created: 2026-07-01
Purpose: multi-session project-building coordination.

## Current State

- Journal status: initialized on 2026-07-01.
- Journal and guidance access is user-controlled through `LOG_CONTROL.md`.
- Default behavior is no journal reads, no guidance reads, and no writes unless the user explicitly asks.
- Lightweight log and guidance discovery uses `项目日志总索引.md`.
- Current project-wide rules, plans, and workflow instructions belong under `guidance/`.
- Current handoff log: `project_journal/handoffs/2026-07-01-P1.5加固更新日志.md`.

## Reading Rule For New Sessions

If the user gives no explicit logging or guidance instruction:

1. Do not read journal logs.
2. Do not read guidance files.
3. Do not read `项目日志总索引.md` or full log bodies.
4. Do not write session, handoff, decision, guidance, changelog, or archive files.
5. Use live config and validation commands to verify anything that may have changed.

If the user gives an explicit logging or guidance instruction:

1. `只列日志`, `只列指引`, `读日志菜单`, or `读指引菜单`: read only `项目日志总索引.md`.
2. `读日志 <中文日志名>` or `读指引 <中文指引名>`: resolve the path from `项目日志总索引.md`, then read only the selected item.
3. `写日志`: write or append one primary conversation log unless the user asks for a separate handoff, decision, guidance, or archive.
4. `写指引`: write or update a current project-wide guidance document under `guidance/`.

## Boundaries

- `project_journal/` is coordination memory, not formal evidence.
- `guidance/` is living project instruction, not proof that live code still behaves that way.
- `archive/` preserves historical context, not active runtime ownership.
- Current project behavior should still be verified against live config and validation commands.

## Handoffs

| Date | Name | Status | Path | Notes |
|---|---|---|---|---|
| 2026-07-01 | P1.5加固更新日志 | ready | `project_journal/handoffs/2026-07-01-P1.5加固更新日志.md` | P1.5 hardening summary, verification snapshot, remaining TODOs, and limited P2 boundary. |
