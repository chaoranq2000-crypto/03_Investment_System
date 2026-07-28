---
schema_version: "1"
task_id: "investment_review_periodic_v1"
contract_path: "docs/codex_tasks/investment_review_periodic_v1/CONTRACT.md"
contract_sha256: "585ef450730b0d105f418112d50ac597a9a98ba576e04ec5e0365b27a29a5fff"
state: "ready"
execution_branch: "codex/investment-review-periodic-v1"
source_baseline: "7df75562eb7c7123ff066406f92fd6b844be994b"
last_completed_phase: "none"
next_phase: "P1"
last_validation: "pass"
updated_at: "2026-07-28T03:22:55+00:00"
---
# 在新 Codex 聊天中启动或恢复本阶段

在 `C:\Projects\03_Investment_System_periodic_review_v1` 打开仓库，启动一个新的 Codex 聊天，然后完整粘贴：

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/investment_review_periodic_v1
Active contract: docs/codex_tasks/investment_review_periodic_v1/CONTRACT.md
Recorded contract SHA-256: 585ef450730b0d105f418112d50ac597a9a98ba576e04ec5e0365b27a29a5fff
Execution worktree: C:\Projects\03_Investment_System_periodic_review_v1
Execution branch: codex/investment-review-periodic-v1
Source baseline: 7df75562eb7c7123ff066406f92fd6b844be994b

Read the complete applicable AGENTS.md instruction chain, .agents/skills/investment-review/SKILL.md, CONTRACT.md, and START_HERE.md before acting. Treat the current active contract as the living source of task truth. Do not rely on prior conversation, memory, another task package, or unstated decisions.

Run the lightweight package validator and inspect only repository state needed for the next action. Resume from the earliest useful outcome not yet proven. Preserve the formal portfolio SQLite as read-only. Build the real P1 portfolio daily report and no-Decision instrument daily report before generalizing. When P1 engineering validation passes, checkpoint and stop for the contract's explicit user sample-acceptance grant; never fabricate that approval. After the grant is recorded, continue through P2-P4 until all criteria pass or a genuine hard stop occurs.

Keep ordinary reports lightweight. Reuse existing episode, fact, market, API/UI and automation capabilities; do not add P2G/P2H, behavior profiles, complex models or new audit layers. Motive hypotheses must be labeled system inference and use only operation-time information. Recommendations may directly say buy/sell/hold/add/reduce/exit and give a position size, but must use report-cutoff information, state risks and invalidation, never guarantee returns, and never execute orders.

Reconcile ordinary drift and conflicts in this same package. Revise CONTRACT.md in place when the user or repository reality changes, record the reason with record-contract or the next milestone checkpoint, and rerun only affected validators. Local in-scope edits, tests and commits are authorized. Do not push, merge, deploy, install an OS scheduler/service, add credentials/dependencies, perform bulk deletion, write the formal portfolio database, or access a broker without explicit new authority.
```

## Current checkpoint

- **State:** `ready`
- **Last completed phase:** `none`
- **Next phase:** `P1`
- **Latest validation:** `pass`
- **Runtime authorizations:** none
- **Current blocker:** none
- **Next safe action:** Open a new Codex chat in the execution worktree and paste the launch block.

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

## Checkpoint history

- 2026-07-28T10:57:04+08:00 — Package drafted from original candidate `c2db0d957778c97bf0a1240f8ff2112716592d05`; not yet safe for unattended execution.
- 2026-07-28T11:21:38+08:00 — Boundary and implementation-plan foundation committed as `7df75562eb7c7123ff066406f92fd6b844be994b`; this is now the execution baseline.
