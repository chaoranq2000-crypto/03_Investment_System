---
schema_version: "1"
task_id: "v1_governance_integration_cleanup"
contract_path: "docs/codex_tasks/v1_governance_integration_cleanup/CONTRACT.md"
contract_sha256: "a681812f9e91993d4a009ebcd972df1b06fc3f808323574387b84afa2ca3353e"
state: "ready"
execution_branch: "codex/v1-governance-integration-cleanup"
source_baseline: "f60f220ae252262a537c612ce193fc779901984b"
last_completed_phase: "none"
next_phase: "P1"
last_validation: "pass"
updated_at: "2026-07-25T02:46:36+00:00"
---
# Start or resume this stage in a new Codex chat

本任务包已固定为发布模式 A，并已获得 Night → Bundle11R–17R → old 002837 三个有序手动删除检查点授权。只有 front matter 为 `state: ready`、启动块包含真实 contract hash 且 `--require-ready` 校验通过时才可启动。

最终 ready 后，在专用工作树 `C:\Projects\03_Investment_System_v1_governance_cleanup` 打开一个全新 Codex 聊天，并原样粘贴：

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/v1_governance_integration_cleanup
Frozen contract: docs/codex_tasks/v1_governance_integration_cleanup/CONTRACT.md
Expected contract SHA-256: a681812f9e91993d4a009ebcd972df1b06fc3f808323574387b84afa2ca3353e
Execution branch: codex/v1-governance-integration-cleanup
Source baseline: f60f220ae252262a537c612ce193fc779901984b
Dedicated worktree: C:\Projects\03_Investment_System_v1_governance_cleanup

Read the complete applicable AGENTS.md instruction chain, CONTRACT.md, START_HERE.md, and every phase-required skill file before acting. Treat the frozen contract as the complete objective, constraints, authority, and definition of done. Do not rely on any previous chat, memory, project journal, Night queue, or unstated decision.

Validate package integrity and repository preflight, then resume from the earliest phase whose postconditions are not proven. After each phase, run its validators, inspect scope, update START_HERE.md, and create the specified Git checkpoint. Continue through P1-P5 until every completion criterion passes or a contract hard stop occurs.

Never edit the frozen contract, add phases, weaken a criterion, fabricate data or reviewer decisions, touch the user's dirty main worktree, perform recursive/bulk deletion, direct-push main, or publish beyond the authorization envelope. In P5, stop in order at the Night, Bundle, and old-002837 deletion waves with the exact per-file manifest; wait for the user to delete only that wave manually, then verify the complete Git status vector before continuing.
```

## Current checkpoint

- **State:** `ready`
- **Last completed phase:** `none`
- **Next phase:** `P1`
- **Latest validation:** `pass`（草案包校验 `ok: true`、P1–P5 连续、0 errors、0 warnings）
- **Current blocker:** `none`。P5 三个 manual deletion checkpoint 是用户已批准的安全暂停，不是未解决决定。
- **Next safe action:** 在专用工作树打开一个全新 Codex 聊天并原样粘贴上方启动块；执行者先验证 frozen contract hash、package-only setup commit 和远端基线，再从 P1 连续执行。

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

## Checkpoint history

- 2026-07-25T03:23:36+08:00 — 根据 V1/main、质量规则、002837 正式披露和历史目录引用审计创建草案；未 finalize，未授权执行或发布。
- 2026-07-25T03:47:03+08:00 — 修正 method 状态推导、三波 clean arm-wave checkpoint、durable ref 与发布前后远端状态；草案验证通过，唯一剩余 blocker 为 D-012 用户授权。
- 2026-07-25T04:02:00+08:00 — 用户选择发布模式 A，并批准 Night→Bundle11R–17R→old002837 三个手动删除检查点；删除全部 B 路径，准备冻结。
